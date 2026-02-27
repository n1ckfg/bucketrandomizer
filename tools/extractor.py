import json
import os
from odf.opendocument import OpenDocumentText
from odf.opendocument import load
from odf.text import P, Span
from odf.element import Node
from odf.style import Style, TextProperties

ODT_FILE = 'test.odt'
JSON_FILE = '../sample.json'

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

if __name__ == "__main__":
    extract_text_to_json(ODT_FILE, JSON_FILE)
