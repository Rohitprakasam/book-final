"""
BookUdecate V1.0 — The Art Department (Phase 3)
==============================================
Post-processes the expanded manuscript by resolving placeholder tags:

    [ORIGINAL_ASSET: /assets/file.png]  →  ![Enhanced Figure](/assets/file.png)
    [NEW_DIAGRAM: {...json...}]         →  ![AI Generated](/assets/ai_generated/file.png)

Usage
-----
    from src.resolver import process_art_department
    final_md = process_art_department(expanded_text, style_config={...})
"""

from __future__ import annotations

import os
import re
import json
from io import BytesIO
from pathlib import Path

# Try importing google-genai
try:
    from google import genai
    from google.genai import types
    from PIL import Image

    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from PIL import Image, ImageEnhance, ImageFilter

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import litellm
except (ImportError, ModuleNotFoundError) as _e:
    litellm = None
    try:
        print("Warning: litellm not found. Some agent features may be disabled.")
    except UnicodeEncodeError:
        pass
from dotenv import load_dotenv

load_dotenv()

# Project-root-relative paths (work regardless of CWD)
_BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = _BASE_DIR / "data" / "output"
RESOLVED_PATH = OUTPUT_DIR / "resolved_manuscript.md"
AI_ASSETS_DIR = OUTPUT_DIR / "assets" / "ai_generated"


def _get_model() -> str:
    """Return the model identifier from the environment."""
    return os.getenv("DEFAULT_MODEL", "groq/llama3-8b-8192")


# ──────────────────────────────────────────────
# TASK A: Resolve Original Asset Tags (With AI Enhancement)
# ──────────────────────────────────────────────
def enhance_image_with_gemini(image_path: Path) -> Path:
    """
    Sends an image to Gemini Vision to describe it, then uses Imagen
    to regenerate a cleaner, enhanced version of the diagram.
    Falls back to Pillow enhancement if Gemini is unavailable.
    Returns the path to the enhanced image.
    """
    if not HAS_GENAI:
        print("[Art Dept] ⚠️ google-genai not installed. Falling back to Pillow.")
        return _enhance_image_with_pillow(image_path)

    # Define output path
    enhanced_dir = AI_ASSETS_DIR.parent / "enhanced_images"
    enhanced_dir.mkdir(parents=True, exist_ok=True)

    enhanced_path = enhanced_dir / image_path.name
    if enhanced_path.exists():
        print(f"  ♻️  Using cached enhanced image: {enhanced_path.name}")
        return enhanced_path

    print(f"  🤖 AI Enhancing: {image_path.name}...")

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)

    try:
        # Step 1: Describe the original image using Gemini Vision (bytes for google.genai)
        prompt = (
            "Describe this technical diagram in precise detail. "
            "Include all labels, arrows, flow directions, component names, "
            "mathematical symbols, dimensions, and spatial relationships. "
            "Be exhaustive — this description will be used to recreate the image."
        )
        image_bytes = image_path.read_bytes()
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        describe_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ],
        )
        description = describe_response.text
        print(f"  📝 Description: {description[:100]}...")

        # Step 2: Regenerate a cleaner version using the description
        success = generate_textbook_diagram(
            subject=f"Regenerate exactly this professional textbook diagram based on this detailed description: {description}",
            theme_config={},
            save_path=enhanced_path,
        )
        if success:
            print(f"  ✅ AI Enhanced: {enhanced_path}")
            return enhanced_path
        else:
            raise Exception("Image generation failed across all fallback models.")

    except Exception as e:
        print(f"  ⚠️ Gemini enhancement failed: {e}")
        print(f"  ↩️ Falling back to Pillow enhancement...")
        return _enhance_image_with_pillow(image_path)

    return image_path  # Should not reach here


def _enhance_image_with_pillow(image_path: Path) -> Path:
    """
    Fallback: Enhance using Pillow (sharpen, contrast, denoise).
    Used when Gemini is unavailable or fails.
    """
    if not HAS_PILLOW:
        return image_path

    enhanced_dir = AI_ASSETS_DIR.parent / "enhanced_images"
    enhanced_dir.mkdir(parents=True, exist_ok=True)
    enhanced_path = enhanced_dir / f"pil_{image_path.name}"

    if enhanced_path.exists():
        return enhanced_path

    try:
        img = Image.open(image_path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.05)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.filter(ImageFilter.SHARPEN)

        img.save(enhanced_path, quality=95)
        return enhanced_path
    except Exception:
        return image_path


def resolve_original_assets(text: str) -> str:
    """
    Replace ``[ORIGINAL_ASSET: <filepath>]`` tags with
    standard Markdown image syntax, enhancing them with Gemini AI.
    Falls back to Pillow if Gemini is unavailable.
    """
    pattern = r"\[ORIGINAL_ASSET:\s*(.+?)\]"

    def _replacer(match: re.Match) -> str:
        rel_path = match.group(1).strip()
        full_extracted_path = OUTPUT_DIR / "assets" / rel_path

        if full_extracted_path.exists():
            # Primary: Gemini AI enhancement (describe → regenerate)
            # Fallback: Pillow enhancement (sharpen/contrast)
            final_path = enhance_image_with_gemini(full_extracted_path)
            web_path = str(final_path).replace("\\", "/")
            return f"![Enhanced Figure]({web_path})"
        else:
            print(f"[Art Dept] ⚠️ Asset not found: {full_extracted_path}")
            # Empty out the tag so no ugly 'Missing Asset' text appears in the final book
            return ""

    resolved = re.sub(pattern, _replacer, text)
    original_count = len(re.findall(pattern, text))
    print(f"[Art Dept] Resolved & AI-Enhanced {original_count} tags")
    return resolved


# ──────────────────────────────────────────────
# TASK B: AI Image Generation (Imagen 3)
# ──────────────────────────────────────────────
def generate_textbook_diagram(
    subject: str, theme_config: dict, save_path: Path
) -> bool:
    """
    Calls Google's image model to generate a stylized textbook illustration.
    """
    if not HAS_GENAI:
        print("[Art Dept] ⚠️ google-genai not installed. Skipping image generation.")
        return False

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)

    # Extract the illustration style generated by Phase 1
    style_prompt = theme_config.get(
        "illustration_style",
        "Flat vector illustration, clean lines, white background, educational textbook graphic",
    )

    # Combine the Drafter's subject with the Style Extractor's visual rules
    full_prompt = f"{subject}. {style_prompt}. High quality, technical diagram."
    print(f'  🎨 Generating: "{subject[:50]}…"')

    import time
    import concurrent.futures

    max_retries = 4
    base_delay = 5

    primary_model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview")
    fallback_env = os.getenv(
        "IMAGE_MODEL_FALLBACKS",
        "imagen-4.0-generate-001,imagen-4.0-fast-generate-001,gemini-2.5-flash-image",
    )
    fallback_models = [m.strip() for m in fallback_env.split(",") if m.strip()]

    current_model = primary_model
    fallback_index = 0

    for attempt in range(max_retries + 1):
        try:
            print(f'  🎨 Generating (Model: {current_model}): "{subject[:50]}…"')

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                if "gemini" in current_model:
                    # Use GenerateContent for Nano Banana / Gemini Image models
                    config_params = {"response_modalities": ["TEXT", "IMAGE"]}
                    if "pro" in current_model:
                        config_params["image_config"] = types.ImageConfig(
                            aspect_ratio="16:9", image_size="4K"
                        )
                    else:
                        config_params["image_config"] = types.ImageConfig(
                            aspect_ratio="16:9"
                        )

                    future = executor.submit(
                        client.models.generate_content,
                        model=current_model,
                        contents=[full_prompt],
                        config=types.GenerateContentConfig(**config_params),
                    )

                    try:
                        response = future.result(timeout=120)  # 120 second hard-timeout
                    except concurrent.futures.TimeoutError:
                        raise Exception("API Connection Timeout (120s)")

                    for part in response.parts:
                        if part.inline_data:
                            image = Image.open(BytesIO(part.inline_data.data))
                            save_path.parent.mkdir(parents=True, exist_ok=True)
                            image.save(save_path)
                            return True
                else:
                    # Use GenerateImages for Imagen 3 / 4 models
                    future = executor.submit(
                        client.models.generate_images,
                        model=current_model,
                        prompt=full_prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio="16:9",
                            person_generation="DONT_ALLOW",
                        ),
                    )

                    try:
                        response = future.result(timeout=120)  # 120 second hard-timeout
                    except concurrent.futures.TimeoutError:
                        raise Exception("API Connection Timeout (120s)")

                    for generated_image in response.generated_images:
                        image_bytes = generated_image.image.image_bytes
                        image = Image.open(BytesIO(image_bytes))

                        save_path.parent.mkdir(parents=True, exist_ok=True)
                        image.save(save_path)
                        return True

        except Exception as e:
            error_str = str(e)

            # Check for Rate Limits (429), Quota Exhaustion, or Model Not Found
            if any(
                k in error_str
                for k in ["429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND", "quota"]
            ):
                # Switch model if fallbacks are available
                if fallback_index < len(fallback_models):
                    current_model = fallback_models[fallback_index]
                    fallback_index += 1
                    print(
                        f"  🔄 Limit/Error hit. Switching model to {current_model} (Attempt {attempt+1}/{max_retries})..."
                    )
                    time.sleep(2)
                    continue
                # If out of fallbacks, do regular backoff
                elif attempt < max_retries:
                    delay = base_delay * (attempt + 1)
                    print(
                        f"  ⏳ Rate limit hit on all models. Retrying in {delay}s (Attempt {attempt+1}/{max_retries})..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    print(
                        f"  ❌ Image Gen Failed after {max_retries} retries: {error_str[:100]}..."
                    )
                    return False

            print(f"  ❌ Image Generation Failed: {error_str[:200]}...")
            return False

    return False


def resolve_art_tags(text: str, theme_config: dict = None, skip_images: bool = False) -> str:
    """
    Finds [NEW_DIAGRAM] tags (even malformed ones), generates images, and replaces tags.
    """
    if theme_config is None:
        theme_config = {}

    # Forgiving Regex Suite
    # 1. Matches nicely formatted JSON with or without brackets: [NEW_DIAGRAM: {...}] or NEW_DIAGRAM: {...}
    pattern_json_tag = r"\[?NEW_DIAGRAM:\s*(\{.*?\})\]?"
    # 2. Matches plain text descriptions (no JSON): [NEW_DIAGRAM: Cross-sectional diagram of...]
    pattern_text_tag = r"\[NEW_DIAGRAM:\s*([^\{].*?)\]"

    matches_json = list(re.finditer(pattern_json_tag, text, re.DOTALL))
    matches_text = list(re.finditer(pattern_text_tag, text, re.DOTALL))

    total_matches = len(matches_json) + len(matches_text)
    if total_matches == 0:
        return text

    AI_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    from src.placeholder_generator import PlaceholderImageGenerator
    placeholder_gen = PlaceholderImageGenerator()

    def generate_and_link(subject: str, caption: str) -> str:
        safe_subject = re.sub(r"[^a-zA-Z0-9]", "_", subject)[:30]
        filename = f"ai_{safe_subject}.png"
        save_path = AI_ASSETS_DIR / filename

        if save_path.exists():
            return f"![{caption}](/data/output/assets/ai_generated/{filename})"
            
        if skip_images:
            placeholder_gen.generate_image(f"Placeholder for: {subject}", str(save_path))
            return f"![{caption}](/data/output/assets/ai_generated/{filename})"

        success = generate_textbook_diagram(subject, theme_config, save_path)
        if success:
            return f"![{caption}](/data/output/assets/ai_generated/{filename})"
        else:
            # Generate a distinct placeholder via our new Placeholder generator
            print(f"  ⚠️ Generated fallback placeholder for {filename}")
            placeholder_gen.generate_image(f"FAILED TO GENERATE:\n{subject}", str(save_path))
            return f"![{caption}](/data/output/assets/ai_generated/{filename})"

    # First, replace JSON-formatted tags
    def replace_json(match):
        try:
            art_request = json.loads(match.group(1).replace("\n", " "))
            subject = art_request.get("subject", "Engineering diagram")
            caption = art_request.get("caption", " ".join(subject.split()[:5]) + "...")
            return generate_and_link(subject, caption)
        except json.JSONDecodeError:
            # Fallback: Treat the malformed JSON string as the subject itself
            raw_text = match.group(1).strip()
            return generate_and_link(raw_text, "Diagram")

    text = re.sub(pattern_json_tag, replace_json, text, flags=re.DOTALL)

    # Second, replace Plain-Text formatted tags
    def replace_text(match):
        subject = match.group(1).strip()
        caption = " ".join(subject.split()[:5]) + "..."
        return generate_and_link(subject, caption)

    text = re.sub(pattern_text_tag, replace_text, text, flags=re.DOTALL)

    return text


# ──────────────────────────────────────────────
# TASK C: Master Function
# ──────────────────────────────────────────────
def process_art_department(expanded_text: str, style_config: dict = None, skip_images: bool = False) -> str:
    """
    Run the full Art Department pipeline:
      1. Resolve [ORIGINAL_ASSET] → Enhanced Markdown images
      2. Resolve [NEW_DIAGRAM]    → AI Generated Images (or placeholders)
      3. Save to ``resolved_manuscript.md``
    """
    print("\n══════════════════════════════════════════")
    if skip_images:
        print("  ART DEPARTMENT — Generating Placeholders (No Images Mode)…")
    else:
        print("  ART DEPARTMENT — Processing tags…")
    print("══════════════════════════════════════════\n")

    # Step 1: Original assets (with Pillow enhancement)
    text = resolve_original_assets(expanded_text)

    # Step 2: New diagrams (AI Generation or placeholders)
    text = resolve_art_tags(text, style_config, skip_images=skip_images)

    # Step 3: Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESOLVED_PATH.write_text(text, encoding="utf-8")

    print(
        f"\n[Art Dept] ✅ Resolved manuscript saved ({len(text):,} chars) → {RESOLVED_PATH}"
    )

    return text


# ──────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    input_path = (
        sys.argv[1] if len(sys.argv) > 1 else "data/output/tagged_manuscript.txt"
    )
    text = Path(input_path).read_text(encoding="utf-8")
    process_art_department(text)
