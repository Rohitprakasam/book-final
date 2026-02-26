"""
BookEducate — Visual Triage (Phase 1c)
=====================================
Classifies extracted images as KEEP / DISCARD / TRANSCRIBE using Gemini Vision.
Uses google.genai (new SDK) to match requirements.txt.
"""

from __future__ import annotations

import os
import re
import json
import time
from pathlib import Path

from PIL import Image

# Project-root-relative paths (work regardless of CWD)
_BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _BASE_DIR / "data" / "output"
DEFAULT_CACHE_DIR = str(OUTPUT_DIR / "assets" / "extracted_images")
TRANSCRIBED_MATH_PATH = OUTPUT_DIR / "transcribed_math.json"

# Optional: use google.genai for vision triage
try:
    from google import genai
    from google.genai import types

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

TRIAGE_PROMPT = """You are the Art Director for a professional Engineering Textbook.
Analyze the provided image extracted from a raw PDF. Classify it strictly as KEEP, DISCARD, or TRANSCRIBE.

Rules for KEEP:
- It is a technical diagram, schematic, circuit (e.g., pumps, valves), graph, or free-body diagram.

Rules for DISCARD:
- It is a university logo, company logo, decorative border, or tiny illegible artifact.

Rules for TRANSCRIBE:
- The image is purely a mathematical equation, formula, or data table trapped as a picture.

Output ONLY a raw JSON object with no markdown wrappers: 
{"decision": "KEEP|DISCARD|TRANSCRIBE", "reason": "brief explanation"}
"""

OCR_PROMPT = """Extract the mathematical equations or table from this image. 
Output ONLY valid LaTeX code. For math, wrap in \\[ and \\]. Do not include ```latex wrappers or any conversational text."""


def _get_vision_client():
    """Return a configured genai Client if API key is set."""
    if not HAS_GENAI:
        return None
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _generate_content_with_image(
    client, model: str, prompt: str, image_path: str
) -> str:
    """Call Gemini Vision with one image. Returns response text."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    # Determine mime type from extension
    ext = Path(image_path).suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    contents = [
        types.Content(
            parts=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                types.Part.from_text(text=prompt),
            ]
        )
    ]
    response = client.models.generate_content(model=model, contents=contents)
    return response.text if hasattr(response, "text") and response.text else ""


def process_images(cache_dir: str | None = None) -> list[str]:
    """Scans extracted images, filters garbage, and OCRs trapped math."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    if not os.path.exists(cache_dir):
        print("No image cache found. Skipping triage.")
        return []

    transcribed_assets = {}
    if os.path.exists(TRANSCRIBED_MATH_PATH):
        try:
            transcribed_assets = json.loads(
                TRANSCRIBED_MATH_PATH.read_text(encoding="utf-8")
            )
            print(f"📂 Loaded {len(transcribed_assets)} existing transcriptions.")
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    discarded_images = []
    client = _get_vision_client()
    model = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")

    print("🔍 Starting Visual Triage Agent...")

    all_files = [
        f
        for f in os.listdir(cache_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    total_images = len(all_files)

    for i, filename in enumerate(all_files):
        print(f"[Triage] Processing Image {i+1}/{total_images}")
        time.sleep(2.0)
        filepath = os.path.join(cache_dir, filename)

        try:
            img = Image.open(filepath)

            # 1. Hardware Filter: Delete tiny artifacts without wasting API tokens
            if img.width < 80 or img.height < 80:
                print(f"🗑️ DISCARD: {filename} (Artifact too small)")
                img.close()
                os.remove(filepath)
                discarded_images.append(filename)
                continue

            # 2. Vision API Triage (or default KEEP if no API)
            if client:
                try:
                    result_text = _generate_content_with_image(
                        client, model, TRIAGE_PROMPT, filepath
                    )
                    result_text = (
                        result_text.strip().replace("```json", "").replace("```", "")
                    )
                    result = json.loads(result_text)
                except (json.JSONDecodeError, Exception) as e:
                    print(
                        f"⚠️ Triage API error for {filename}: {e}. Defaulting to KEEP."
                    )
                    result = {"decision": "KEEP", "reason": "API error"}
            else:
                result = {"decision": "KEEP", "reason": "No GEMINI_API_KEY"}

            decision = result.get("decision", "KEEP")

            if decision == "DISCARD":
                print(f"🗑️ DISCARD: {filename} - {result.get('reason')}")
                img.close()
                os.remove(filepath)
                discarded_images.append(filename)

            elif decision == "TRANSCRIBE":
                print(f"🧮 TRANSCRIBE: Rescuing math from {filename}...")
                if client:
                    try:
                        extracted_latex = _generate_content_with_image(
                            client, model, OCR_PROMPT, filepath
                        )
                        extracted_latex = extracted_latex.strip()
                    except Exception as e:
                        print(f"⚠️ OCR failed for {filename}: {e}")
                        extracted_latex = ""
                else:
                    extracted_latex = ""
                transcribed_assets[filename] = extracted_latex
                img.close()
                os.remove(filepath)
                discarded_images.append(filename)

                # Incremental Save (Fault Tolerance for Resumes)
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                TRANSCRIBED_MATH_PATH.write_text(
                    json.dumps(transcribed_assets, indent=4), encoding="utf-8"
                )

            else:
                print(f"✅ KEEP: {filename} - {result.get('reason')}")
                img.close()

        except Exception as e:
            print(f"⚠️ Error analyzing {filename}: {e}. Defaulting to KEEP.")

    # 3. Save Transcribed Math so the Drafter can inject it later
    if transcribed_assets:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # Always update the file count
        TRANSCRIBED_MATH_PATH.write_text(
            json.dumps(transcribed_assets, indent=4), encoding="utf-8"
        )
        print(f"💾 Total transcribed equations in database: {len(transcribed_assets)}")

    return discarded_images


def clean_manuscript(manuscript_path: str | Path, discarded_images: list[str]) -> None:
    """Removes [ORIGINAL_ASSET] tags for images that were deleted or transcribed."""
    manuscript_path = Path(manuscript_path)
    try:
        content = manuscript_path.read_text(encoding="utf-8")
        
        # Strip explicitly discarded images
        removed_count = 0
        for filename in discarded_images:
            pattern = r"\[ORIGINAL_ASSET:\s*.*?" + re.escape(filename) + r"\]"
            content, count = re.subn(pattern, "", content)
            removed_count += count
            
        # Robust fallback: identify ANY asset tags whose files no longer exist (critical for crash resumes)
        def _check_asset(match):
            nonlocal removed_count
            asset_path = match.group(1).strip()
            full_path = OUTPUT_DIR / "assets" / asset_path
            if not full_path.exists():
                removed_count += 1
                return ""  # Strip tag if file is gone
            return match.group(0)
            
        content = re.sub(r"\[ORIGINAL_ASSET:\s*([^\]]+)\]", _check_asset, content)

        manuscript_path.write_text(content, encoding="utf-8")
        print(f"🧹 Cleaned manuscript. Removed {removed_count} dead/transcribed tags.")
    except FileNotFoundError:
        print(f"⚠️ Manuscript file not found: {manuscript_path}")


if __name__ == "__main__":
    discarded = process_images()
    manuscript_path = OUTPUT_DIR / "tagged_manuscript.txt"
    clean_manuscript(manuscript_path, discarded)
