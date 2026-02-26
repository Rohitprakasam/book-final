"""
BookEducate 6.0 — Syllabus Generator (Phase 1.5)
================================================
Reads the complete extracted manuscript and generates a strict
5-unit university curriculum syllabus JSON.
"""

import os
import json
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"
SYLLABUS_PATH = OUTPUT_DIR / "syllabus.json"
LLM_TIMEOUT = 300

SYSTEM_PROMPT = """\
You are an Academic Board Curriculum Director specializing in {BOOK_SUBJECT}.
Your task is to review the provided book manuscript text and generate a strict, 
official University Regulation Curriculum Syllabus (similar to Anna University guidelines).

The syllabus MUST:
1. Be exactly 5 Units.
2. Be strictly bounded by the {BOOK_SUBJECT} domain at the {ACADEMIC_LEVEL} level.
3. NEVER drift into unrelated domains.
4. Output ONLY valid JSON containing the structure below. Do not include markdown or explanations.

JSON Schema:
{
  "subject_name": "{BOOK_SUBJECT}",
  "academic_level": "{ACADEMIC_LEVEL}",
  "course_objectives": [
    "Objective 1", "Objective 2"
  ],
  "units": [
    {
      "unit_number": 1,
      "unit_title": "String",
      "topics_covered": ["String", "String"]
    },
    ... (must have exactly 5 units)
  ],
  "course_outcomes": [
    "Outcome 1", "Outcome 2"
  ]
}
"""


def _get_model() -> str:
    return os.getenv("DEFAULT_MODEL", "groq/llama3-8b-8192")


def generate_syllabus(manuscript_path: str | Path) -> dict | None:
    """Generate the syllabus from the manuscript text and save to JSON."""
    model = _get_model()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    # Read manuscript text (truncate if absolutely massive, but we need the outline)
    try:
        text = Path(manuscript_path).read_text(encoding="utf-8")
        # Keep first 100k and last 100k chars to give a full overview of the book's scope
        if len(text) > 250000:
            text = text[:100000] + "\n\n...[SNIP]...\n\n" + text[-100000:]
    except Exception as e:
        print(f"❌ Failed to read manuscript for syllabus generation: {e}")
        return None

    book_subject = os.getenv("BOOK_SUBJECT", "Engineering")
    academic_level = os.getenv("ACADEMIC_LEVEL", "Undergraduate Course")

    prompt = SYSTEM_PROMPT.replace("{BOOK_SUBJECT}", book_subject).replace(
        "{ACADEMIC_LEVEL}", academic_level
    )

    print(f"\n   🎓 Generating {academic_level} Syllabus for {book_subject}...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if model.startswith("gemini/") and not api_key:
                print("   ❌ Gemini API key missing for Syllabus Generator.")
                return None

            response = litellm.completion(
                model=model,
                timeout=LLM_TIMEOUT,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": f"Here is the parsed manuscript:\n\n{text}",
                    },
                ],
                api_key=api_key if model.startswith("gemini/") else None,
            )

            content = response.choices[0].message.content.strip()

            # Clean JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            syllabus_data = json.loads(content)

            # Save to disk
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            SYLLABUS_PATH.write_text(
                json.dumps(syllabus_data, indent=2), encoding="utf-8"
            )

            print(f"   ✅ Syllabus generated and saved to {SYLLABUS_PATH.name}")
            return syllabus_data

        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error on attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"   ⚠️ Syllabus generation failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    print("   ❌ Failed to generate Syllabus after 3 attempts.")
    return None


if __name__ == "__main__":
    generate_syllabus(OUTPUT_DIR / "tagged_manuscript.txt")
