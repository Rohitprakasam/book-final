"""
BookUdecate V1.0 — Shared Configuration
======================================
Centralised path constants and settings used across all modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# ──────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"
AI_ASSETS_DIR = ASSETS_DIR / "ai_generated"
MANUSCRIPT_PATH = OUTPUT_DIR / "tagged_manuscript.txt"
EXPANDED_PATH = OUTPUT_DIR / "expanded_draft.md"
RESOLVED_PATH = OUTPUT_DIR / "resolved_manuscript.md"
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"
TRANSCRIBED_MATH_PATH = OUTPUT_DIR / "transcribed_math.json"

# ──────────────────────────────────────────────
# PIPELINE SETTINGS
# ──────────────────────────────────────────────
CHUNK_SEPARATOR = "\n\n--- CHUNK END ---\n\n"
THROTTLE_SECONDS = 5
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "4000"))
MAX_REVISIONS = 3
LLM_TIMEOUT = 1800  # 30 minutes

# ──────────────────────────────────────────────
# SUBJECT CONFIGURATION (O2: Configurable persona)
# ──────────────────────────────────────────────
BOOK_SUBJECT = os.getenv("BOOK_SUBJECT", "Engineering")
BOOK_PERSONA = os.getenv(
    "BOOK_PERSONA", "Elite Professor specializing in the subject matter"
)


def get_api_key() -> str | None:
    """Return the best available API key for Gemini."""
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def get_model() -> str:
    """Return the model identifier from the environment."""
    model = os.getenv("DEFAULT_MODEL", "groq/llama3-8b-8192")
    if not model:
        print("[Config] ⚠️ WARNING: DEFAULT_MODEL not set, using fallback")
    return model
