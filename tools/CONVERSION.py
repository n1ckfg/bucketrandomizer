import json
import os
import sys
import shutil
import subprocess
import tempfile
import zipfile
from odf.opendocument import OpenDocumentText
from odf.opendocument import load
from odf.text import P, Span
from odf.element import Node
from odf.style import Style, TextProperties

ODT_FILE = 'test.odt'
JSON_FILE = 'sample.json'

# STEP 1. FIX FORMATTING.
"""
Automates the ODT formatting fix process (README.txt steps 2.1-2.6).

Converts ODT -> DOCX -> ODT via LibreOffice headless mode, then normalizes
newlines in the resulting ODT's content.xml.

Usage: python fix_formatting.py <input.odt> [output.odt]
If no output is specified, the input file is overwritten.
"""

def find_libreoffice():
    """Find the LibreOffice soffice binary."""
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac_path):
        return mac_path

    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path

    return None


def convert(soffice, input_path, output_format, output_dir):
    """Run LibreOffice headless conversion and return the output file path."""
    subprocess.run(
        [soffice, "--headless", "--convert-to", output_format,
         "--outdir", output_dir, input_path],
        check=True,
        capture_output=True,
    )
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(output_dir, f"{base}.{output_format}")


def normalize_odt_newlines(odt_path):
    """Open the ODT zip, normalize newlines in content.xml, repack."""
    with tempfile.TemporaryDirectory() as unzip_dir:
        # Extract all files
        with zipfile.ZipFile(odt_path, "r") as zf:
            zf.extractall(unzip_dir)

        # Normalize content.xml
        content_path = os.path.join(unzip_dir, "content.xml")
        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = clean_extracted(content)
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Repack into a new ODT (ZIP with mimetype first, uncompressed)
        new_odt = odt_path + ".tmp"
        with zipfile.ZipFile(new_odt, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype must be first and uncompressed per ODF spec
            mimetype_path = os.path.join(unzip_dir, "mimetype")
            if os.path.exists(mimetype_path):
                zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            for root, dirs, files in os.walk(unzip_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    arcname = os.path.relpath(full_path, unzip_dir)
                    if arcname == "mimetype":
                        continue
                    zf.write(full_path, arcname)

        shutil.move(new_odt, odt_path)


def fix_formatting(input_odt, output_odt=None):
    """Run the full ODT formatting fix pipeline."""
    if output_odt is None:
        output_odt = input_odt.split()[0] + "_fixed.odt"

    soffice = find_libreoffice()
    if not soffice:
        print("Error: LibreOffice not found. Install it or add soffice to PATH.")
        sys.exit(1)

    input_odt = os.path.abspath(input_odt)
    output_odt = os.path.abspath(output_odt)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: ODT -> DOCX
        print("Converting ODT to DOCX...")
        docx_path = convert(soffice, input_odt, "docx", tmpdir)

        # Step 2: DOCX -> ODT
        print("Converting DOCX back to ODT...")
        odt_path = convert(soffice, docx_path, "odt", tmpdir)

        # Copy to output location before normalizing
        shutil.copy2(odt_path, output_odt)

    # Step 3: Normalize newlines in the final ODT
    print("Normalizing newlines...")
    normalize_odt_newlines(output_odt)

    print(f"Done: {output_odt}")


# STEP 2. EXTRACTION TO JSON.

def clean_extracted(input):
    # fix nonstandard line breaks
    input = input.replace("\r\n", "\n")
    input = input.replace("\r", "\n")
    input = input.replace("\\l", "\n")

    input = input.replace("’", "\'") # curly apostrophe

    return input

def clean_formatting(input):
    input = input.replace("<i></i>", "") # empty italics element
    input = input.replace("<b></b>", "") # empty bold element

    return input

def get_text_formatting(doc, style_name):
    is_bold = False
    is_italic = False
    
    if not style_name:
        return is_bold, is_italic
    
    style = doc.getStyleByName(style_name)
    
    if style:
        text_props = style.getElementsByType(TextProperties)
        if text_props:
            props = text_props[0]
            
            weight = props.getAttribute('fontweight')
            is_bold = weight == 'bold'
            
            style_attr = props.getAttribute('fontstyle')
            is_italic = style_attr == 'italic'
    
    return is_bold, is_italic

def extract_text_from_element(element, doc):
    text_content = []
    
    if hasattr(element, 'data') and element.data:
        text_content.append(clean_extracted(element.data))
    
    for child in element.childNodes:
        if child.nodeType == Node.TEXT_NODE:
            text_content.append(clean_extracted(child.data))
        elif child.nodeType == Node.ELEMENT_NODE:
            is_bold = False
            is_italic = False

            try:
                style_name = child.getAttribute('stylename')
                is_bold, is_italic = get_text_formatting(doc, style_name)
            except:
                pass

            if (is_italic == True and is_bold == False):
                text_content.append("<i>" + extract_text_from_element(child, doc) + "</i>")         
            elif (is_italic == False and is_bold == True):
                text_content.append("<b>" + extract_text_from_element(child, doc) + "</b>")  
            elif (is_italic == True and is_bold == True):
                text_content.append("<b><i>" + extract_text_from_element(child, doc) + "</i></b>")                                        
            else:
                text_content.append(extract_text_from_element(child, doc))
    
    returns = ''.join(text_content)
    returns = clean_formatting(returns)
    
    return returns

def extract_text_to_json(odt_filepath, json_filepath):
    if not os.path.exists(odt_filepath):
        print(f"Error: ODT file not found at {odt_filepath}")
        return

    print(f"\n2. Loading ODT file: {odt_filepath}")
    
    try:
        doc = load(odt_filepath)
        
        extracted_text = []

        content_elements = doc.text.childNodes
        print(f"--- {os.path.basename(odt_filepath)} ---")
        print(f"Total elements found: {len(content_elements)}\n")

        '''
        paragraphs = doc.text.getElementsByType(P)
        
        print(f"Found {len(paragraphs)} paragraphs.")
        
        for p in paragraphs:
            text_content = extract_text_from_element(p)
            if text_content.strip(): # Only include non-empty paragraphs
                extracted_text.append(text_content.strip())
        '''

        new_section_armed = False
        new_line = ""
        new_line_counter = 0
        new_line_counter_max = 2

        for i, element in enumerate(content_elements):
            tag_name = element.qname[1]

            text_content = extract_text_from_element(element, doc)
            preview = text_content[:70] + ('...' if len(text_content) > 70 else '')

            if tag_name == 'p':
                #print(f"[{i+1:03d}] PARAGRAPH: '{preview}'")

                if (text_content == "" and new_section_armed == False):
                    new_section_armed = True
                    new_line = ""
                    new_line_counter = 0
                elif (text_content == "" and new_section_armed == True):
                    if (len(new_line) > 0):
                        new_line_counter += 1
                        if (new_line_counter > new_line_counter_max):
                            extracted_text.append(new_line)
                            new_section_armed = False
                    else:
                        pass
                else:
                    new_line += text_content + "\n"

            '''
            elif tag_name == 'h':
                # Headings usually have an outline-level attribute
                level = element.attributes.get(('urn:oasis:names:tc:opendocument:xmlns:text:1.0', 'outline-level'), 'N/A')
                print(f"[{i+1:03d}] HEADING (L{level}): '{preview}'")
            elif tag_name == 'list':
                # This element contains list items (<text:list-item>)
                item_count = len([c for c in element.childNodes if c.qname[1] == 'list-item'])
                print(f"[{i+1:03d}] LIST ({item_count} items found): '{preview}'")
            elif tag_name == 'table':
                print(f"[{i+1:03d}] TABLE found: '{preview}'")
            else:
                print(f"[{i+1:03d}] Other Element: <{tag_name}>: '{preview}'")            
            '''

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json_array = []

            for i, item in enumerate(extracted_text):
                json_object = { 
                    "index": i, 
                    "body": item 
                }
                json_array.append(json_object)

            json.dump(json_array, f, ensure_ascii=False,  indent=4)
        
        print(f"Extracted {len(extracted_text)} objects to {json_filepath}.")

    except Exception as e:
        print(f"An error occurred: {e}")


# STEP 3. RUN

if __name__ == "__main__":
    ODT_FILE  = sys.argv[1]
    ODT_FILE2  = ODT_FILE.split()[0] + "_fixed.odt"
    fix_formatting(ODT_FILE)
    extract_text_to_json(ODT_FILE2, JSON_FILE)
