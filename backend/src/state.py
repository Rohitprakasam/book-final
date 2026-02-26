"""
BookUdecate V1.0 — LangGraph State Definition
============================================
TypedDict for the per-chunk expansion pipeline:
    analyst → drafter → critic (with conditional loop)
"""

from __future__ import annotations

from typing import TypedDict


class BookState(TypedDict, total=False):
    """
    Shared state for the Expansion Swarm graph (per-chunk).

    Attributes
    ----------
    current_chunk : str
        The original text of the current chapter extracted by the Deconstructor.

    analysis : str
        The Analyst's bulleted expansion plan for this chunk.

    expanded_chunk : str
        The Drafter's expanded Markdown output (preserves asset tags).

    feedback : str
        The Critic's review — either "APPROVED" or revision notes.

    revision_count : int
        Number of drafter revisions so far (prevents infinite loops).
    """

    current_chunk: str
    analysis: str
    expanded_chunk: str
    feedback: str
    revision_count: int
    target_chars: int
