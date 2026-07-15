#!/usr/bin/env python3
"""Convert markdown docs to PDF using Unicode font (Arial from Windows)."""
from pathlib import Path
from fpdf import FPDF

BASE = Path(__file__).parent
DOCS_DIR = BASE / "docs"
PDF_DIR = BASE / "pdf"
PDF_DIR.mkdir(exist_ok=True)

ARIAL_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
ARIAL_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")
ARIAL_ITALIC = Path("C:/Windows/Fonts/ariali.ttf")
COURIER_REGULAR = Path("C:/Windows/Fonts/consola.ttf")
COURIER_BOLD = Path("C:/Windows/Fonts/consolab.ttf")


class ArchPDF(FPDF):
    """PDF generator with Unicode support."""
    
    def header(self):
        self.set_font("Arial", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "TNSVT V2 - Architecture Documentation", align="L")
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")
    
    def chapter_title(self, title):
        self.add_page()
        self.set_font("Arial", "B", 18)
        self.set_text_color(20, 50, 100)
        self.cell(0, 14, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(20, 50, 100)
        self.set_line_width(0.6)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(8)
    
    def section_title(self, title):
        self.set_font("Arial", "B", 13)
        self.set_text_color(30, 70, 130)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
    
    def subsection_title(self, title):
        self.set_font("Arial", "B", 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
    
    def body_text(self, text):
        self.set_font("Arial", "", 10)
        self.set_text_color(30, 30, 30)
        safe = self._safe(text)
        self.multi_cell(0, 5.5, safe)
        self.ln(1.5)
    
    def code_block(self, code):
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(40, 40, 40)
        for line in code.split("\n")[:30]:
            safe = self._safe(line)
            self.cell(0, 4.5, "  " + safe[:180], fill=True, new_x="LMARGIN", new_y="NEXT")
        if code.count("\n") > 30:
            self.cell(0, 4.5, "  ... (truncated)", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
    
    def bullet_item(self, text):
        self.set_font("Arial", "", 10)
        self.set_text_color(30, 30, 30)
        safe = self._safe(text)
        self.cell(8, 6, "-")
        self.multi_cell(0, 6, safe)
        self.ln(0.5)
    
    def _safe(self, text):
        return text.encode("latin-1", "replace").decode("latin-1")


def md_to_pdf(md_path: Path, pdf_path: Path):
    """Convert Markdown file to PDF."""
    pdf = ArchPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    pdf.add_font("Arial", "", str(ARIAL_REGULAR))
    pdf.add_font("Arial", "B", str(ARIAL_BOLD))
    pdf.add_font("Arial", "I", str(ARIAL_ITALIC))
    pdf.add_font("Courier", "", str(COURIER_REGULAR))
    pdf.add_font("Courier", "B", str(COURIER_BOLD))
    
    pdf.set_font("Arial", "", 10)
    pdf.add_page()
    
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    in_code_block = False
    code_lines = []
    first_h1 = True
    
    for line in lines:
        stripped = line.rstrip("\n")
        
        if stripped.startswith("```"):
            if in_code_block:
                if code_lines:
                    pdf.code_block("\n".join(code_lines))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue
        
        if in_code_block:
            code_lines.append(stripped)
            continue
        
        if stripped.startswith("# ") and not stripped.startswith("## "):
            if first_h1:
                pdf.set_font("Arial", "B", 18)
                pdf.set_text_color(20, 50, 100)
                title = stripped[2:].encode("latin-1", "replace").decode("latin-1")
                pdf.cell(0, 14, title, new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(20, 50, 100)
                pdf.set_line_width(0.6)
                pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
                pdf.ln(8)
                first_h1 = False
            else:
                pdf.chapter_title(stripped[2:].encode("latin-1", "replace").decode("latin-1"))
        elif stripped.startswith("## "):
            pdf.section_title(stripped[3:].encode("latin-1", "replace").decode("latin-1"))
        elif stripped.startswith("### "):
            pdf.subsection_title(stripped[4:].encode("latin-1", "replace").decode("latin-1"))
        elif stripped.startswith("#### "):
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(70, 70, 70)
            safe = stripped[5:].encode("latin-1", "replace").decode("latin-1")
            pdf.cell(0, 7, safe, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:]
            text = text.replace("**", "")
            pdf.bullet_item(text)
        elif stripped.startswith("> "):
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(90, 90, 90)
            safe = stripped[2:].encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe)
            pdf.ln(2)
        elif stripped.startswith("|"):
            pdf.set_font("Courier", "", 7)
            pdf.set_text_color(50, 50, 50)
            safe = stripped.encode("latin-1", "replace").decode("latin-1")
            pdf.cell(0, 4.5, safe[:190], new_x="LMARGIN", new_y="NEXT")
        elif stripped.strip() == "":
            pdf.ln(2)
        elif stripped.startswith("---"):
            pdf.ln(3)
        else:
            text = stripped.replace("**", "")
            pdf.body_text(text)
    
    pdf.output(str(pdf_path))
    return pdf_path.stat().st_size


def main():
    md_files = sorted(DOCS_DIR.glob("*.md"))
    print(f"Converting {len(md_files)} markdown files to PDF...\n")
    
    total_size = 0
    for md_file in md_files:
        pdf_path = PDF_DIR / f"{md_file.stem}.pdf"
        print(f"  {md_file.name} -> {pdf_path.name}...", end=" ")
        try:
            size = md_to_pdf(md_file, pdf_path)
            total_size += size
            print(f"OK ({size // 1024} KB)")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\nTotal PDF size: {total_size // 1024} KB")
    print(f"Files in: {PDF_DIR}")


if __name__ == "__main__":
    main()