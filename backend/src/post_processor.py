"""
BookUdecate 8.0 — Post-Processor
================================
Fixes for:
  Fault #1 (Duplicated content)  → deduplicate_paragraphs()
  Fault #7 (Over-fragmentation) → merge_micro_chapters()
  Fault #8 (Syllabus restarts)  → strip_syllabus_restarts()
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, Any, List


def _similarity(a: str, b: str) -> float:
    """Return 0-1 similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


# ──────────────────────────────────────────────
# FAULT #1: Deduplicate consecutive paragraphs
# ──────────────────────────────────────────────


def deduplicate_paragraphs(latex: str, threshold: float = 0.85) -> str:
    """
    Remove consecutive duplicate paragraphs from the LaTeX body.

    Splits on double-newline, compares adjacent blocks, and removes
    any block that's >85% similar to the previous one.
    """
    blocks = re.split(r"\n\s*\n", latex)
    if len(blocks) <= 1:
        return latex

    deduped = [blocks[0]]
    removed = 0

    for i in range(1, len(blocks)):
        current = blocks[i].strip()
        previous = deduped[-1].strip()

        # Skip empty blocks
        if not current:
            continue

        # Skip very short blocks (headings, labels) — don't dedup those
        if len(current) < 100:
            deduped.append(blocks[i])
            continue

        sim = _similarity(current, previous)
        if sim >= threshold:
            removed += 1
            continue  # Skip this duplicate

        deduped.append(blocks[i])

    if removed > 0:
        print(f"[PostProcessor] 🧹 Removed {removed} duplicate paragraph(s)")

    return "\n\n".join(deduped)


# ──────────────────────────────────────────────
# FAULT #7: Merge micro-chapters
# ──────────────────────────────────────────────


def merge_micro_chapters(
    chapters: List[Dict[str, Any]], min_chars: int = 3000, max_chapters: int = 60
) -> List[Dict[str, Any]]:
    """
    Merge consecutive micro-chapters (< min_chars of content) into
    their preceding chapter to reduce over-fragmentation.

    Also caps total chapter count at max_chapters by merging the
    shortest adjacent chapters until the limit is met.

    Operates on the JSON structure (list of chapter dicts from book_structure.json).
    """
    if not chapters or len(chapters) <= 1:
        return chapters

    def _chapter_text_len(ch: Dict) -> int:
        """Estimate content length of a chapter using JSON dump size."""
        import json

        try:
            return len(json.dumps(ch, ensure_ascii=False))
        except Exception:
            return 0

    # Pass 1: Merge chapters below min_chars into preceding chapter
    merged = [chapters[0]]
    merge_count = 0

    for i in range(1, len(chapters)):
        ch = chapters[i]
        ch_len = _chapter_text_len(ch)

        if ch_len < min_chars and merged:
            # Merge this micro-chapter into the previous one
            prev = merged[-1]
            prev_sections = prev.get("sections", [])
            new_sections = ch.get("sections", [])
            prev["sections"] = prev_sections + new_sections
            merge_count += 1
        else:
            merged.append(ch)

    if merge_count > 0:
        print(
            f"[PostProcessor] 📎 Merged {merge_count} micro-chapter(s) "
            f"({len(chapters)} → {len(merged)} chapters)"
        )

    # Pass 2: If still over max_chapters, merge the shortest adjacent pairs
    while len(merged) > max_chapters:
        # Find shortest adjacent pair
        min_combined = float("inf")
        min_idx = 0
        for i in range(len(merged) - 1):
            combined = _chapter_text_len(merged[i]) + _chapter_text_len(merged[i + 1])
            if combined < min_combined:
                min_combined = combined
                min_idx = i

        # Merge the pair
        merged[min_idx]["sections"] = merged[min_idx].get("sections", []) + merged[
            min_idx + 1
        ].get("sections", [])
        merged.pop(min_idx + 1)

    return merged


# ──────────────────────────────────────────────
# FAULT #8: Strip syllabus restarts
# ──────────────────────────────────────────────


def strip_syllabus_restarts(latex: str) -> str:
    """
    Remove re-introductions of syllabus objectives and unit overviews
    that appear after the first chapter.

    Matches patterns like:
    - "Unit 1: ..." / "UNIT 1 OBJECTIVES" appearing after page 10
    - "In this unit, we will learn..." / "The syllabus covers..."
    - "Course objectives:" / "Learning outcomes:"
    """
    # Split into chunks by \\chapter or \\section
    # Only strip from chapter 2 onwards

    # Patterns that indicate a syllabus restart
    restart_patterns = [
        r"(?i)^\s*(?:Course|Unit|Module)\s+(?:Objectives|Overview|Introduction)\s*:?\s*$",
        r"(?i)^\s*(?:Learning\s+Outcomes?|Syllabus\s+Coverage)\s*:?\s*$",
        r"(?i)In\s+this\s+(?:unit|module|course),?\s+(?:we\s+will|students?\s+will|you\s+will)\s+(?:learn|study|cover|explore)",
        r"(?i)The\s+(?:syllabus|curriculum|course)\s+(?:covers?|includes?|encompasses?)",
        r"(?i)^\s*(?:UNIT|Unit)\s+\d+\s*[-:]\s*(?:Introduction|Overview|Basics)",
    ]

    # Only apply after the first \\chapter{} or after line 200
    lines = latex.split("\n")
    first_chapter_line = 0
    for i, line in enumerate(lines):
        if "\\chapter{" in line:
            first_chapter_line = i
            break

    if first_chapter_line == 0:
        return latex  # No chapters found, don't touch

    chapter_count = 0
    cleaned_lines = []
    for i, line in enumerate(lines):
        if "\\chapter{" in line:
            chapter_count += 1

        # Only strip from chapter 3 onwards (allow ch1 & ch2 to have intros)
        if chapter_count >= 3:
            should_strip = False
            for pattern in restart_patterns:
                if re.search(pattern, line):
                    should_strip = True
                    break
            if should_strip:
                continue  # Skip this line

        cleaned_lines.append(line)

    removed = len(lines) - len(cleaned_lines)
    if removed > 0:
        print(f"[PostProcessor] 🔄 Stripped {removed} syllabus restart line(s)")

    return "\n".join(cleaned_lines)


# ──────────────────────────────────────────────
# EMPTY PAGE FIXES: Strip empty/heading-only chapters at JSON level
# ──────────────────────────────────────────────


def strip_empty_chapters(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove chapters that have zero content sections.
    These produce blank pages in the PDF.
    """
    filtered = []
    removed = 0

    for ch in chapters:
        sections = ch.get("sections", [])
        if not sections or len(sections) == 0:
            removed += 1
            continue
        filtered.append(ch)

    if removed > 0:
        print(
            f"[PostProcessor] 🗑️ Stripped {removed} empty chapter(s) with no sections"
        )
    return filtered


def strip_heading_only_chapters(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove chapters that contain only headings with no actual text content.
    These produce pages with just a title and nothing else.
    """
    import json

    def _has_real_content(ch: Dict) -> bool:
        """Check if a chapter has any substantive content beyond headings."""
        sections = ch.get("sections", [])
        for section in sections:
            stype = section.get("type", "")

            # Headings don't count as content
            if stype == "heading":
                continue

            # Check for text content
            text = section.get("text", "")
            if isinstance(text, str) and len(text.strip()) > 20:
                return True

            # Check for equations
            latex = section.get("latex", "")
            if isinstance(latex, str) and len(latex.strip()) > 5:
                return True

            # Check nested content blocks
            content = section.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        bt = block.get("text", "")
                        bl = block.get("latex", "")
                        if (isinstance(bt, str) and len(bt.strip()) > 20) or (
                            isinstance(bl, str) and len(bl.strip()) > 5
                        ):
                            return True

            # Check solution steps
            steps = section.get("solution_steps", [])
            if isinstance(steps, list) and len(steps) > 0:
                return True

            # Check items (lists)
            items = section.get("items", [])
            if isinstance(items, list) and len(items) > 0:
                return True

        return False

    filtered = []
    removed = 0

    for ch in chapters:
        if _has_real_content(ch):
            filtered.append(ch)
        else:
            removed += 1

    if removed > 0:
        print(
            f"[PostProcessor] 🗑️ Stripped {removed} heading-only chapter(s) with no real content"
        )
    return filtered
