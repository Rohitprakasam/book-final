"""
BookUdecate V1.0 — The Deconstructor (Phase 1)
=============================================
Ingests a PDF, extracts all text and images, and produces a single
``tagged_manuscript.txt`` where every extracted image is replaced with
an inline ``[ORIGINAL_ASSET: /assets/filename.png]`` tag.

Usage
-----
    from src.deconstructor import deconstruct
    deconstruct("data/raw_draft/mybook.pdf")
"""

from __future__ import annotations

from pathlib import Path

import hashlib

import fitz  # PyMuPDF

# ──────────────────────────────────────────────
# CONFIGURATION (project-root-relative; works regardless of CWD)
# ──────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _BASE_DIR / "data" / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"
MANUSCRIPT_PATH = OUTPUT_DIR / "tagged_manuscript.txt"


def deconstruct(pdf_path: str) -> str:
    """
    Read a PDF file and produce a tagged manuscript.

    Parameters
    ----------
    pdf_path : str
        Path to the input PDF file.

    Returns
    -------
    str
        The full tagged manuscript text.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Ensure output dirs exist
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    manuscript_parts: list[str] = []
    image_counter = 0

    print(f"[Deconstructor] Opened '{pdf_path.name}' — {len(doc)} pages")

    for page_num, page in enumerate(doc):
        print(f"[Deconstructor] Processing Page {page_num + 1}/{len(doc)}")
        # --- Extract images on this page ---
        page_images = _extract_images(doc, page, page_num, image_counter)
        image_counter += len(page_images)

        # --- Extract text blocks with positions ---
        text_blocks = page.get_text(
            "blocks"
        )  # (x0, y0, x1, y1, text, block_no, block_type)

        # Build a combined list of text + image items sorted by vertical position
        items: list[tuple[float, str]] = []

        for block in text_blocks:
            y_pos = block[1]  # y0
            block_type = block[6]  # 0 = text, 1 = image

            if block_type == 0:
                # Text block
                text = block[4].strip()
                if text:
                    items.append((y_pos, text))

        # Insert image tags at their vertical positions
        for img_info in page_images:
            items.append((img_info["y_pos"], img_info["tag"]))

        # Sort by vertical position (top to bottom)
        items.sort(key=lambda x: x[0])

        # Append page content
        if items:
            page_text = "\n\n".join(item[1] for item in items)
            manuscript_parts.append(f"\n\n--- Page {page_num + 1} ---\n\n{page_text}")

    doc.close()

    # --- Write the tagged manuscript ---
    manuscript = "\n".join(manuscript_parts).strip()

    # RISK CHECK: Empty PDF
    if len(manuscript) < 100:
        error_msg = (
            f"CRITICAL ERROR: Extracted text is suspiciously short ({len(manuscript)} chars).\n"
            "This likely means the PDF is SCANNED (images only) and has no text layer.\n"
            "We cannot process this file without OCR. Please provide a text-based PDF."
        )
        print(f"[Deconstructor] ❌ {error_msg}")
        raise ValueError(error_msg)

    MANUSCRIPT_PATH.write_text(manuscript, encoding="utf-8")

    print(f"[Deconstructor] Extracted {image_counter} images to {ASSETS_DIR}")
    print(
        f"[Deconstructor] Saved tagged manuscript ({len(manuscript):,} chars) → {MANUSCRIPT_PATH}"
    )

    return manuscript


def _extract_images(
    doc: fitz.Document,
    page: fitz.Page,
    page_num: int,
    counter_start: int,
) -> list[dict]:
    """
    Extract all images from a page and save them to the assets directory.
    Filters out small artifacts (<100px) similar to extract.py.
    """
    # Filter constants (from extract.py)
    MIN_WIDTH = 100
    MIN_HEIGHT = 100
    MIN_PIXELS = 10000

    results = []
    image_list = page.get_images(full=True)

    for img_idx, img_info in enumerate(image_list):
        xref = img_info[0]

        try:
            pix = fitz.Pixmap(doc, xref)

            # Convert CMYK / other color spaces to RGB
            if pix.n - pix.alpha > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            # --- Size Filter (Integration of extract.py logic) ---
            if pix.width < MIN_WIDTH or pix.height < MIN_HEIGHT:
                print(f"  Size skip: {pix.width}x{pix.height} (too small)")
                continue

            if (pix.width * pix.height) < MIN_PIXELS:
                print(f"  Size skip: {pix.width}x{pix.height} (area too small)")
                continue

            # Calculate hash for unique ID (shortened to 6 chars)
            img_data = pix.tobytes()
            img_hash = hashlib.md5(img_data).hexdigest()[:6]

            # Filename Format: pg{page_num}_img{img_idx}_{hash}.png
            filename = f"pg{page_num + 1}_img{img_idx + 1}_{img_hash}.png"

            # Subdirectory for extracted images
            extract_dir = ASSETS_DIR / "extracted_images"
            extract_dir.mkdir(parents=True, exist_ok=True)

            save_path = extract_dir / filename
            pix.save(str(save_path))
            pix = None  # free memory

            # Try to find the image position on the page
            y_pos = _get_image_y_pos(page, xref, img_idx)

            # Tag Format: [ORIGINAL_ASSET:extracted_images/filename]
            tag = f"[ORIGINAL_ASSET:extracted_images/{filename}]"

            results.append(
                {
                    "filename": filename,
                    "tag": tag,
                    "y_pos": y_pos,
                }
            )

            print(f"  → Saved {filename} ({img_info[2]}x{img_info[3]})")

        except Exception as e:
            print(f"  ⚠ Skipped image xref={xref} on page {page_num + 1}: {e}")

    return results


def _get_image_y_pos(page: fitz.Page, xref: int, fallback_idx: int) -> float:
    """
    Attempt to find the vertical (y) position of an image on the page
    by scanning the page's image list with bounding-box info.
    Falls back to a heuristic if position cannot be determined.
    """
    try:
        image_block_idx = 0
        for img_block in page.get_text("dict")["blocks"]:
            if img_block.get("type") == 1:  # image block
                if image_block_idx == fallback_idx:
                    bbox = img_block.get("bbox", (0, 0, 0, 0))
                    return bbox[1]  # y0
                image_block_idx += 1
    except Exception:
        pass

    # Fallback: place images after text, spaced by index
    return 9999.0 + fallback_idx


# ──────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.deconstructor <path_to_pdf>")
        sys.exit(1)

    deconstruct(sys.argv[1])
