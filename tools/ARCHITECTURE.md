# CONVERSION.py Architecture

This document describes the architecture and workflow of the `CONVERSION.py` script. The script is designed to process an OpenDocument Text (`.odt`) file, normalize its formatting, and extract its textual content into a structured JSON file.

## Overview

The execution pipeline is divided into two main steps:
1. **Formatting Fix (Normalization):** Sanitizes the ODT file by fixing newline anomalies in the internal XML.
2. **JSON Extraction:** Parses the normalized ODT file using `odfpy`, reconstructs text formatting into HTML-like tags (`<b>`, `<i>`), groups logical sections, and outputs a JSON array.

The pipeline is pure Python and has no external dependency beyond `odfpy`.

---

## Step 1: Formatting Fix (`fix_formatting`)

This step ensures the input `.odt` file has a standard, predictable internal structure before extraction. 

### Process Flow
1. **Copy:** The input `.odt` is copied to the output path, so the original is never modified in place.
2. **XML Newline Normalization (`normalize_odt_newlines`):**
   - The script unzips the resulting `.odt` file.
   - It reads `content.xml` and runs string replacements to standardize non-standard line breaks (e.g., `\r\n`, `\r`, `\l` to `\n`) and replace curly apostrophes (`’`) with straight ones (`'`).
   - Finally, it repacks the uncompressed `mimetype` and the rest of the contents back into a valid ZIP archive (the final fixed `.odt` file).

### Removed: the LibreOffice headless round trip

Step 1 used to convert the input `.odt` to `.docx` and back through `soffice --headless`
first, to emulate the Word round trip in `MANUAL_WORKFLOW.txt` steps 2.2-2.6. It was
measured against `reference_sample.json` and removed: it produces a byte-identical
`sample.json`. See `REPORT3.md` for the measurements.

---

## Step 2: Extraction to JSON (`extract_text_to_json`)

This step reads the normalized ODT file and extracts the content while preserving basic styling (bold and italic) and logical groupings.

### Block Enumeration (`iter_block_lines`)
- The top level of `office:text` is not all `<text:p>`: it also holds `<text:h>` headings
  and `<text:list>` wrappers (any outline-numbered paragraph is wrapped in nested lists).
  `iter_block_lines` yields one rendered line per block, descending through
  `list` / `list-item` / `list-header` so a list contributes one line per item.

### Text Parsing and Style Resolution
- **ODF Parsing:** Uses `odf.opendocument.load` to load the ODT document.
- **Style Resolution (`get_text_formatting` & `apply_style`):** 
  - Styles in ODF cascade like CSS. The script resolves a style name by traversing up the parent chain (`parentstylename`) to determine if a node should be bold or italic.
  - Properties like `fontweight` and `fontstyle` are examined.
- **Run Collection (`collect_runs`):** 
  - Flattening an element into a list of "runs": `(text, is_bold, is_italic)`.
  - It handles soft line breaks (`<text:line-break/>`) by converting them to actual newline characters.
- **Rendering Runs (`render_runs`):** 
  - Iterates over the runs and conditionally wraps the text segments in `<b>...</b>` or `<i>...</i>` tags based on the active style state.
  - It handles boundaries well, ensuring tags don't span across newlines inappropriately.
  - Adjacent runs with the same formatting are merged into a single tag pair. This is what makes the output independent of how a given document happens to split its `<text:span>` runs.

### Chunking Logic
Instead of saving each paragraph individually, the script implements a state machine to group text blocks into larger sections. 
- A section is built up by concatenating text blocks (`new_line += text_content + "\n"`).
- Empty paragraphs (`text_content == ""`) act as delimiters.
- The script uses a counter (`new_line_counter`) to accumulate *consecutive* empty lines. When it exceeds a threshold (`new_line_counter_max = 2`), it finalizes the current section, appends it to the extraction list, and resets the buffer.

### JSON Output
The extracted sections are mapped into dictionaries and dumped to the destination JSON file (`sample.json`). The schema is simple:
```json
[
    {
        "index": 0,
        "body": "Formatted content here...\nMore content."
    }
]
```

---

## Execution
When executed as a standalone script:
```bash
python CONVERSION.py input.odt
```
1. Reads `input.odt`.
2. Creates `input.odt_fixed.odt`.
3. Extracts content from `input.odt_fixed.odt` into `sample.json`.

A missing argument, a missing input file, or an unreadable ODT exits non-zero.
