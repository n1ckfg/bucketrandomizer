from odf import text, teletype
from odf.opendocument import load
from odf.style import Style, TextProperties

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

def read_odt_formatting(filename):
    doc = load(filename)
    
    paragraphs = doc.getElementsByType(text.P)
    
    for para in paragraphs:
        print("\nNew paragraph:")
        for element in para.childNodes:
            if element.nodeType == element.TEXT_NODE:
                print(f"  '{element.data}' - Plain")
            elif hasattr(element, 'qname'):
                if element.qname[1] == 'span':
                    style_name = element.getAttribute('stylename')
                    text_content = teletype.extractText(element)
                    is_bold, is_italic = get_text_formatting(doc, style_name)
                    
                    formatting = []
                    if is_bold:
                        formatting.append("Bold")
                    if is_italic:
                        formatting.append("Italic")
                    
                    format_str = ", ".join(formatting) if formatting else "Plain"
                    print(f"  '{text_content}' - {format_str}")

read_odt_formatting('test.odt')