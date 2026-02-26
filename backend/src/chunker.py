"""
BookUdecate V1.0 — Multi-Strategy Manuscript Chunker
===================================================
Splits ``tagged_manuscript.txt`` into logical, LLM-friendly chunks
using a cascading strategy:

    A.  Split by "Chapter" headings (case-insensitive)
    B.  Split by major numerical sections (``\\n1. ``, ``\\n2. ``, …)
    C.  Hard-split any remaining chunk > MAX_CHUNK_CHARS by length
"""

from __future__ import annotations

import re
from pathlib import Path

import os

MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "800"))


def _split_by_chapter(text: str) -> list[str]:
    """Strategy A: Split on 'Chapter', 'Unit', 'Module', or 'Part' headings."""
    parts = re.split(
        r"(?=^(?:Chapter |CHAPTER |Unit |UNIT |Module |MODULE |Part |PART ))",
        text,
        flags=re.MULTILINE,
    )
    return [p.strip() for p in parts if p.strip()]


def _split_by_numbered_sections(text: str) -> list[str]:
    """Strategy B: Split on major numbered sections (e.g., \\n1. Introduction)."""
    parts = re.split(r"(?=^\d+\.\s+)", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def _split_by_length(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Strategy C: Hard-split long text by paragraph boundaries,
    keeping each piece under ``max_chars``.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        # New safe logic:
        # 1. If current buffer + para fits, append it
        if current_len + para_len <= max_chars:
            current.append(para)
            current_len += para_len + 2
        else:
            # 2. If buffer is not empty, flush it first
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0

            # 3. Now handle the PARA itself
            # If the para *alone* is too big, force split it
            if len(para) > max_chars:
                # Semantic split by sentence endings to prevent destroying math/words
                sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZA-Za-z])", para)
                para_current = ""
                for sentence in sentences:
                    if len(para_current) + len(sentence) + 1 <= max_chars:
                        para_current += (sentence + " ").strip()
                    else:
                        if para_current:
                            chunks.append(para_current.strip())
                            para_current = ""

                        # Absolute fallback if a single sentence is STILL too massive
                        if len(sentence) > max_chars:
                            for i in range(0, len(sentence), max_chars):
                                chunks.append(sentence[i : i + max_chars])
                        else:
                            para_current = sentence + " "
                if para_current:
                    chunks.append(para_current.strip())
            else:
                # Otherwise, it fits in a fresh chunk
                current.append(para)
                current_len = len(para) + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_manuscript(filepath: str | Path) -> list[str]:
    """
    Read a tagged manuscript and split it into chunks using
    a multi-strategy approach:

      1. Try splitting by "Chapter" headings
      2. If that produces ≤ 1 chunk, try numbered sections
      3. Hard-split any chunk still over MAX_CHUNK_CHARS

    Parameters
    ----------
    filepath : str | Path
        Path to ``tagged_manuscript.txt``.

    Returns
    -------
    list[str]
        A list of strings, each representing one chunk.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Manuscript not found: {filepath}")

    text = filepath.read_text(encoding="utf-8")

    # Strategy A: Chapter-based split
    chunks = _split_by_chapter(text)

    # Strategy B: If only 1 chunk, try numbered sections
    if len(chunks) <= 1:
        print("[Chunker] No 'Chapter' headings found — trying numbered sections…")
        chunks = _split_by_numbered_sections(text)

    # Strategy B fallback: still 1 chunk? Just use the whole text
    if len(chunks) <= 1:
        print("[Chunker] No numbered sections found — using length-based split…")
        chunks = [text]

    # Strategy C: Hard-split any oversized chunk
    final_chunks: list[str] = []
    for chunk in chunks:
        if len(chunk) > MAX_CHUNK_CHARS:
            sub_chunks = _split_by_length(chunk, MAX_CHUNK_CHARS)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)

    print(f"[Chunker] Split manuscript into {len(final_chunks)} chunk(s)")
    for i, ch in enumerate(final_chunks):
        preview = ch[:80].replace("\n", " ")
        print(f'  Chunk {i + 1}: {len(ch):,} chars — "{preview}…"')

    return final_chunks


# ──────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    chunks = chunk_manuscript("data/output/tagged_manuscript.txt")
    print(f"\nTotal chunks: {len(chunks)}")
