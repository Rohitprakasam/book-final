"""
BookUdecate V1.0 — LangGraph Compilation & Routing
=================================================
Per-chunk expansion pipeline with a conditional critic loop
and low-effort detection:

    START → analyst → drafter → critic ─┬─ APPROVED ──→ END
                                         ├─ LOW EFFORT ─→ drafter (higher temp)
                                         └─ REVISE ───→ drafter (max 3 retries)
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents import analyst_node, critic_node, drafter_node
from src.state import BookState

MAX_REVISIONS = 3  # Allow up to 3 revision loops


# ──────────────────────────────────────────────
# CONDITIONAL ROUTING
# ──────────────────────────────────────────────
def _should_revise(state: BookState) -> str:
    """
    Decide whether to loop back to the drafter or finish.

    Returns 'END' if the critic approved or we've hit the revision cap.
    Returns 'drafter' to request another revision.
    """
    feedback = state.get("feedback", "APPROVED")
    revision_count = state.get("revision_count", 0)

    if feedback.upper().startswith("APPROVED"):
        return END
    if revision_count >= MAX_REVISIONS:
        print(f"[Router] Hit revision cap ({revision_count}). Moving on.")
        return END

    print(f"[Router] Sending back for revision {revision_count + 1}")
    return "drafter"


# ──────────────────────────────────────────────
# GRAPH BUILDER
# ──────────────────────────────────────────────
def build_graph():
    """
    Compile the per-chunk expansion graph.

    Returns
    -------
    CompiledGraph
        Ready to invoke with ``{"current_chunk": "..."}``
    """
    builder = StateGraph(BookState)

    # --- Register nodes ---
    builder.add_node("analyst", analyst_node)
    builder.add_node("drafter", drafter_node)
    builder.add_node("critic", critic_node)

    # --- Define edges ---
    builder.add_edge(START, "analyst")
    builder.add_edge("analyst", "drafter")
    builder.add_edge("drafter", "critic")

    # --- Conditional edge: critic decides loop or exit ---
    builder.add_conditional_edges("critic", _should_revise)

    # --- Compile ---
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    return graph
