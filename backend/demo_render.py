import json
import os
import re
from pathlib import Path
import subprocess

from src.renderer_latex import render_page_latex, generate_index_tags, prune_index_tags, sanitize_latex_commands, sanitize_for_zero_errors
from src.post_processor import deduplicate_paragraphs

BASE_DIR = Path("c:/Users/rohit/OneDrive/Desktop/Book_Creator/BookUdecate V1.0/backend")
OUTPUT_DIR = BASE_DIR / "data" / "output"
TEMPLATE_PATH = BASE_DIR / "templates" / "bookeducate.latex"

def create_demo_pdf():
    # 1. Load Demo Structure
    json_path = OUTPUT_DIR / "demo_structure.json"
    with open(json_path, "r", encoding="utf-8") as f:
        demo_structure = json.load(f)

    # 2. Render LaTeX parts
    latex_parts = []
    for chapter in demo_structure["sections"]:
        latex_parts.append(render_page_latex(chapter))
    
    latex_body = "\n".join(latex_parts)

    # 3. Apply quality post-processors
    latex_body = prune_index_tags(latex_body)
    latex_body = sanitize_latex_commands(latex_body)
    latex_body = deduplicate_paragraphs(latex_body)
    latex_body = generate_index_tags(latex_body)
    latex_body = sanitize_for_zero_errors(latex_body)

    # 4. Assemble Document
    template_content = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Clean Pandoc conditionals
    template_content = re.sub(r"\$if\(.*?\)\$.*?\$endif\$", "", template_content, flags=re.DOTALL)
    template_content = re.sub(r"\$for\(.*?\)\$.*?\$endfor\$", "", template_content, flags=re.DOTALL)
    
    full_latex = template_content.replace("$body$", latex_body)
    full_latex = full_latex.replace("$title$", "BookEducate Customization Demo")
    full_latex = full_latex.replace("$author$", "BookEducate Engine")
    full_latex = full_latex.replace("$date$", "\\today")
    full_latex = re.sub(r"\$[a-zA-Z_-]+\$", "", full_latex)

    tex_out = OUTPUT_DIR / "DemoBook.tex"
    tex_out.write_text(full_latex, encoding="utf-8")
    print(f"✅ LaTeX Generated: {tex_out}")

    # 5. Compile PDF (Multi-pass for Index/TOC)
    print("🚀 Compiling PDF...")
    try:
        # Pass 1
        subprocess.run(["xelatex", "-interaction=nonstopmode", "DemoBook.tex"], cwd=OUTPUT_DIR, check=True, capture_output=True, text=True)
        print("   Pass 1 complete (AUX generated)")
        
        # Run MakeIndex
        subprocess.run(["makeindex", "DemoBook.idx"], cwd=OUTPUT_DIR, check=True, capture_output=True, text=True)
        print("   Index processed (IDX -> IND)")
        
        # Pass 2 (Final)
        subprocess.run(["xelatex", "-interaction=nonstopmode", "DemoBook.tex"], cwd=OUTPUT_DIR, check=True, capture_output=True, text=True)
        print("   Pass 2 complete (Final PDF)")
        
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Compilation error: {e.stderr[:500] if e.stderr else e.stdout[:500]}")

    pdf_out = OUTPUT_DIR / "DemoBook.pdf"
    if pdf_out.exists():
        print(f"🎉 PDF Created: {pdf_out}")
    else:
        print("❌ PDF Generation Failed.")

if __name__ == "__main__":
    create_demo_pdf()
