"""
BookUdecate V1.0 — Style Manager (Phase 1)
=======================================
Analyzes a Style Reference Guide (PDF) to extract visual identity rules
(colors, fonts, illustration style) as a JSON object.

Usage
-----
    from src.style_manager import extract_style
    style_config = extract_style("data/input/sample.pdf")
"""

import os
import json
from pathlib import Path

# Try importing google-genai; handle missing dependency gracefully
try:
    from google import genai
    from google.genai import types

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

import fitz  # PyMuPDF

# Project-root-relative paths (optional; style output can be in memory only)
_BASE_DIR = Path(__file__).resolve().parent.parent


def extract_style(guide_path: str) -> dict:
    """
    Extract visual style configuration from a PDF reference.

    Parameters
    ----------
    guide_path : str
        Path to the Style Reference PDF.

    Returns
    -------
    dict
        JSON object with keys: primary_color, secondary_color,
        background_color, font_style, illustration_style.
    """
    guide_path = Path(guide_path)
    if not guide_path.exists():
        print(f"[Style Manager] ⚠️ Reference guide not found: {guide_path}")
        return {}

    if not HAS_GENAI:
        print(
            "[Style Manager] ⚠️ google-genai not installed. Skipping style extraction."
        )
        return {}

    print(f"[Style Manager] Extracting visual identity from {guide_path.name}…")

    # 1. Convert first page to image for analysis
    try:
        doc = fitz.open(guide_path)
        if len(doc) < 1:
            return {}

        page = doc[0]
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")

        # 2. Call Gemini for visual analysis
        client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        )

        prompt = """
        You are an expert Art Director and Layout Designer. I am providing you with a visual sample from a target Style_Reference_Guide. Your task is to extract its exact visual identity so the system can replicate it programmatically.

        Analyze the provided visual sample and output a strict JSON object containing the following:

        primary_color: The dominant hex color code used for major headings or UI blocks.
        secondary_color: The secondary hex color code used for subheadings or accents.
        background_color: The hex color for page backgrounds or text boxes.
        font_style: Describe the font pairings (e.g., 'Sans-serif for headers, Serif for body').
        illustration_style: A precise prompt snippet that describes the aesthetic of the diagrams (e.g., 'Flat vector illustration, clean modern lines, white background, utilizing the primary and secondary colors').

        Output ONLY valid JSON.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=img_data, mime_type="image/png"),
                    ],
                )
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        style_config = json.loads(response.text)
        print("[Style Manager] ✅ Style extracted successfully!")
        return style_config

    except Exception as e:
        print(f"[Style Manager] ❌ Extraction failed: {e}")
        return {}
