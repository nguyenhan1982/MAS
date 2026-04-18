#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from fpdf import FPDF

WORKSPACE_ROOT = Path(__file__).parent.parent
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
INPUT_FILE = WORKSPACE_ROOT / "final_report.md"
OUTPUT_FILE = WORKSPACE_ROOT / "final_report.pdf"

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(FONT_PATH):
        pdf.add_font("Arial", "", FONT_PATH)
        pdf.set_font("Arial", size=12)
    else:
        pdf.set_font("Helvetica", size=12)

    # Use epw (effective page width) instead of 0
    width = pdf.epw 
    
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(5)
            continue
        
        # Super simple render to debug
        pdf.multi_cell(w=width, h=8, text=line)
        pdf.ln(2)

    pdf.output(str(OUTPUT_FILE))

if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print("Missing input")
        sys.exit(1)
    content = INPUT_FILE.read_text(encoding="utf-8")
    print("Converting...")
    try:
        create_pdf(content)
        print("Done")
    except Exception as e:
        print(f"Error: {e}")
