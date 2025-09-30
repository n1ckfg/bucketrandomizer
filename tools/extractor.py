import json
import os
from odf.opendocument import OpenDocumentText
from odf.opendocument import load
from odf.text import P
from odf.element import Node

ODT_FILE = 'test.odt'
JSON_FILE = 'test.json'

def extract_text_from_element(element):
    text_content = []
    
    if hasattr(element, 'data') and element.data:
        text_content.append(element.data)
    
    for child in element.childNodes:
        if child.nodeType == Node.TEXT_NODE:
            text_content.append(child.data)
        elif child.nodeType == Node.ELEMENT_NODE:
            text_content.append(extract_text_from_element(child))
    
    return ''.join(text_content)

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
        print(f"Total top-level content elements found: {len(content_elements)}\n")

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

        for i, element in enumerate(content_elements):
            tag_name = element.qname[1]

            text_content = extract_text_from_element(element)
            preview = text_content[:70] + ('...' if len(text_content) > 70 else '')

            if tag_name == 'p':
                print(f"[{i+1:03d}] PARAGRAPH: '{preview}'")

                if (text_content == "" and new_section_armed == False):
                    new_section_armed = True
                    new_line = ""
                elif (text_content == "" and new_section_armed == True):
                    if (len(new_line) > 0):
                        extracted_text.append(new_line)
                        new_section_armed = False
                    else:
                        pass
                else:
                    new_line += text_content + "\n"

            elif tag_name == 'h':
                # Headings usually have an outline-level attribute
                level = element.attributes.get(('urn:oasis:names:tc:opendocument:xmlns:text:1.0', 'outline-level'), 'N/A')
                print(f"[{i+1:03d}] HEADING (L{level}): '{preview}'")
            elif tag_name == 'list':
                # This element contains list items (<text:list-item>)
                item_count = len([c for c in element.childNodes if c.qname[1] == 'list-item'])
                print(f"[{i+1:03d}] LIST ({item_count} items found)")
            elif tag_name == 'table':
                print(f"[{i+1:03d}] TABLE found.")
            else:
                print(f"[{i+1:03d}] Other Element: <{tag_name}>")            

        with open(json_filepath, 'w', encoding='utf-8') as f:
            #json.dump(extracted_text, f, ensure_ascii=False, indent=4) # Use json.dump for clean formatting

            json_objects = []

            for i, item in enumerate(extracted_text):
                new_object = { 
                    "index": i, 
                    "body": item 
                }
                json_objects.append(new_object)

            json.dump(json_objects, f, ensure_ascii=False,  indent=4)
        
        print(f"Extracted {len(extracted_text)} text elements to {json_filepath}.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    extract_text_to_json(ODT_FILE, JSON_FILE)
