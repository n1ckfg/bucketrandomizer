#!/usr/bin/env python3
"""
Automates the ODT formatting fix process (README.txt steps 2.1-2.6).

Converts ODT -> DOCX -> ODT via LibreOffice headless mode, then normalizes
newlines in the resulting ODT's content.xml.

Usage: python fix_formatting.py <input.odt> [output.odt]
If no output is specified, the input file is overwritten.
"""

import sys
import os
import shutil
import subprocess
import tempfile
import zipfile

from extractor import clean_extracted


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
        output_odt = input_odt

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


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} <input.odt> [output.odt]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) == 3 else None
    fix_formatting(input_file, output_file)
