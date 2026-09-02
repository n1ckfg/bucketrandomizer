import json
import os
import re
import sys
import shutil
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

Normalizes newlines in the ODT's content.xml.

Usage: python fix_formatting.py <input.odt> [output.odt]
If no output is specified, the input file is overwritten.
"""

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
        output_odt = input_odt + "_fixed.odt"

    input_odt = os.path.abspath(input_odt)
    output_odt = os.path.abspath(output_odt)

    shutil.copy2(input_odt, output_odt)

    print("Normalizing newlines...")
    normalize_odt_newlines(output_odt)

    print(f"Done: {output_odt}")

    return output_odt


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

    # an opening curly quote that starts a line is not part of the emphasised
    # phrase, so it sits outside the tags: <i>“x”</i> -> “<i>x”</i>
    input = re.sub(r'(?m)^((?:<[bi]>)+)(“)', r'\2\1', input)

    return input

def get_text_formatting(doc, style_name):
    """Resolve a style name to (is_bold, is_italic), following the parent chain.

    Each value is tri-state: True/False when the style chain says something about
    it, None when it says nothing and the enclosing context should win. ODF styles
    cascade like CSS, so an inner span with fo:font-style="normal" cancels the
    italic it inherits from an outer <text:span text:style-name="Emphasis">.
    """
    is_bold = None
    is_italic = None

    seen = set()

    while style_name and style_name not in seen:
        seen.add(style_name)

        try:
            style = doc.getStyleByName(style_name)
        except Exception:
            # odfpy asserts when the name belongs to a non-style (e.g. a list style)
            style = None

        if not style:
            break

        text_props = style.getElementsByType(TextProperties)
        if text_props:
            props = text_props[0]

            if is_bold is None:
                weight = props.getAttribute('fontweight')
                if weight:
                    is_bold = weight not in ('normal', '100', '200', '300', '400')

            if is_italic is None:
                style_attr = props.getAttribute('fontstyle')
                if style_attr:
                    is_italic = style_attr != 'normal'

        if is_bold is not None and is_italic is not None:
            break

        style_name = style.getAttribute('parentstylename')

    return is_bold, is_italic


def apply_style(doc, element, is_bold, is_italic):
    """Override the inherited formatting with whatever this element's style sets."""
    try:
        style_name = element.getAttribute('stylename')
    except Exception:
        return is_bold, is_italic

    if not style_name:
        return is_bold, is_italic

    style_bold, style_italic = get_text_formatting(doc, style_name)

    if style_bold is not None:
        is_bold = style_bold
    if style_italic is not None:
        is_italic = style_italic

    return is_bold, is_italic


def collect_runs(element, doc, is_bold, is_italic, runs):
    """Flatten an element into a list of (text, is_bold, is_italic) runs."""
    for child in element.childNodes:
        if child.nodeType == Node.TEXT_NODE:
            runs.append((clean_extracted(child.data), is_bold, is_italic))
            continue

        if child.nodeType != Node.ELEMENT_NODE:
            continue

        tag_name = child.qname[1]

        # <text:line-break/> is a soft line break. README step 2.6 turns these
        # into real paragraph breaks by hand; do the same here.
        if tag_name == 'line-break':
            runs.append(("\n", is_bold, is_italic))
        else:
            # <text:s/> and <text:tab/> have no children and contribute nothing,
            # which is what the published JSON expects.
            child_bold, child_italic = apply_style(doc, child, is_bold, is_italic)
            collect_runs(child, doc, child_bold, child_italic, runs)

    return runs


def render_runs(runs):
    """Wrap runs in <b>/<i>, merging neighbours and never spanning a newline."""
    output = []
    state = [False, False]  # bold, italic currently open

    def close():
        if state[1]:
            output.append("</i>")
            state[1] = False
        if state[0]:
            output.append("</b>")
            state[0] = False

    for text, is_bold, is_italic in runs:
        is_bold = bool(is_bold)
        is_italic = bool(is_italic)

        for i, segment in enumerate(text.split("\n")):
            if i > 0:
                close()
                output.append("\n")

            if not segment:
                continue

            if [is_bold, is_italic] != state:
                close()
                if is_bold:
                    output.append("<b>")
                    state[0] = True
                if is_italic:
                    output.append("<i>")
                    state[1] = True

            output.append(segment)

    close()

    return ''.join(output)


def extract_text_from_element(element, doc):
    is_bold, is_italic = apply_style(doc, element, False, False)

    runs = collect_runs(element, doc, is_bold, is_italic, [])

    # a leading or trailing <text:line-break/> would otherwise add a blank line;
    # the caller already terminates every paragraph with a newline
    return clean_formatting(render_runs(runs)).strip("\n")


BLOCK_TAGS = ('p', 'h')

# <text:list> is only a wrapper: the text lives in the <text:p>/<text:h> inside
# its list items, and those items may themselves be wrapped in nested lists.
LIST_TAGS = ('list', 'list-item', 'list-header')


def iter_block_lines(element, doc):
    """Yield one rendered line per block-level element.

    A <text:p> or <text:h> is a single line. A <text:list> contributes one line
    per block inside it -- rendering the list as a single element would run its
    items together, because the newline between blocks comes from the caller.
    Anything else (<text:sequence-decls>, ...) contributes nothing.
    """
    tag_name = element.qname[1]

    if tag_name in BLOCK_TAGS:
        yield extract_text_from_element(element, doc)
    elif tag_name in LIST_TAGS:
        for child in element.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                yield from iter_block_lines(child, doc)


def extract_text_to_json(odt_filepath, json_filepath):
    if not os.path.exists(odt_filepath):
        print(f"Error: ODT file not found at {odt_filepath}")
        sys.exit(1)

    print(f"\n2. Loading ODT file: {odt_filepath}")

    doc = load(odt_filepath)

    extracted_text = []

    content_elements = doc.text.childNodes
    print(f"--- {os.path.basename(odt_filepath)} ---")
    print(f"Total elements found: {len(content_elements)}\n")

    new_section_armed = False
    new_line = ""
    new_line_counter = 0
    new_line_counter_max = 2

    for i, element in enumerate(content_elements):
        for text_content in iter_block_lines(element, doc):
            #preview = text_content[:70] + ('...' if len(text_content) > 70 else '')
            #print(f"[{i+1:03d}] BLOCK: '{preview}'")

            if (text_content == "" and new_section_armed == False):
                new_section_armed = True
                new_line = ""
                new_line_counter = 0
            elif (text_content == "" and new_section_armed == True):
                if (len(new_line) > 0):
                    new_line_counter += 1
                    if (new_line_counter > new_line_counter_max):
                        extracted_text.append(new_line)
                        # the section is spent: start the next one clean, so a
                        # block arriving before the next blank cannot append to
                        # what was just emitted
                        new_section_armed = False
                        new_line = ""
                        new_line_counter = 0
                else:
                    pass
            else:
                # only *consecutive* blanks end a section; blank lines inside
                # one must not accumulate towards the threshold
                new_line_counter = 0
                new_line += text_content + "\n"

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


# STEP 3. RUN

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {os.path.basename(__file__)} <input.odt>")
        sys.exit(1)

    ODT_FILE = sys.argv[1]
    ODT_FILE2 = fix_formatting(ODT_FILE)
    extract_text_to_json(ODT_FILE2, JSON_FILE)
