"""
BookUdecate V1.0 — Master Orchestrator
=====================================
Chains all four phases into a single end-to-end pipeline:

    Phase 1   Deconstruct   PDF → tagged_manuscript.txt
    Phase 1b  Style Extract PDF → style_config.json
    Phase 1c  Visual Triage Classify images (keep/discard/transcribe)
    Phase 2   Expand Swarm  chunks → analyst → drafter → critic loop
    Phase 3   Art Dept      [ORIGINAL_ASSET] & [NEW_DIAGRAM] → resolved Markdown
    Phase 4   Typesetting   Structured JSON → LaTeX → PDF

Usage
-----
    python main.py "path/to/input.pdf"                  # Full pipeline
    python main.py "path/to/input.pdf" --style "s.pdf"  # With style reference
    python main.py --resume                             # Resume from last checkpoint
    python main.py --phase 4                            # Re-run Phase 4 only
"""

from __future__ import annotations

import os
import sys
import uuid
import time
import argparse
import re
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Fix Windows console encoding (cp1252 can't handle Unicode box chars)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "data" / "output"
EXPANDED_PATH = OUTPUT_DIR / "expanded_draft.md"
RESOLVED_PATH = OUTPUT_DIR / "resolved_manuscript.md"
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"
CHUNK_SEPARATOR = "\n\n--- CHUNK END ---\n\n"
THROTTLE_SECONDS = 5


# ──────────────────────────────────────────────
# CHECKPOINT SYSTEM (Fault Tolerance)
# ──────────────────────────────────────────────
def save_state(phase: int, data: dict = None) -> None:
    """Save checkpoint after each phase completes."""
    state = {
        "completed_phase": phase,
        "timestamp": time.time(),
        "timestamp_human": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if data:
        state.update(data)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"   💾 Checkpoint saved: Phase {phase} complete.")


def load_state() -> dict:
    """Load last checkpoint."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"completed_phase": 0}
    return {"completed_phase": 0}


def clear_directory(directory: Path, keep_file: Path = None) -> None:
    """Helper to wipe data folders without deleting the folder itself."""
    if not directory.exists():
        return
    import shutil

    # Resolve keep_file to absolute path for reliable comparison
    keep_path = keep_file.resolve() if keep_file else None

    for item in directory.iterdir():
        try:
            # Skip the file we want to keep
            if keep_path and item.resolve() == keep_path:
                continue

            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"   ⚠️ Could not delete {item.name}: {e}")


# ──────────────────────────────────────────────
# PIPELINE
# ──────────────────────────────────────────────
def main(
    pdf_path: str = None,
    style_path: str = None,
    start_phase: int = 1,
    is_resume: bool = False,
) -> None:
    """Run the full BookUdecate V1.0 pipeline."""
    start_time = time.time()
    total = 0
    style_config = {}

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          📖  BookUdecate V1.0 — UNIFIED ENGINE           ║")
    print("║       Document Deconstruction & Reassembly Engine       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    print()

    if start_phase == 1 and not is_resume:
        print(
            "   🧹 Starting fresh run. Purging previous book data to prevent cross-contamination..."
        )

        # Pass pdf_path to clear_directory so we don't delete our own input!
        input_file_path = Path(pdf_path) if pdf_path else None

        # Also MUST preserve jobs.json (the server's database)
        to_preserve = [input_file_path, OUTPUT_DIR / "jobs.json"]

        def clear_with_exceptions(dir_path, exceptions):
            if not dir_path.exists():
                return
            import shutil

            abs_exceptions = [Path(e).resolve() for e in exceptions if e]
            for item in dir_path.iterdir():
                if item.resolve() in abs_exceptions:
                    continue
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    print(f"   ⚠️ Could not delete {item.name}: {e}")

        clear_with_exceptions(OUTPUT_DIR, to_preserve)

        clear_directory(BASE_DIR / "data" / "chroma_db")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print()
    elif start_phase > 1:
        print(f"   ⏩  Skipping to Phase {start_phase} (checkpoint/flag)")
        print()

    manuscript_file = OUTPUT_DIR / "tagged_manuscript.txt"

    # ──────────────────────────────────────────
    # PHASE 1: THE DECONSTRUCTOR
    # ──────────────────────────────────────────
    if start_phase <= 1:
        print("━" * 58)
        print("🔬  PHASE 1 — THE DECONSTRUCTOR")
        print("━" * 58)

        if not pdf_path:
            print("❌ No PDF path provided. Cannot run Phase 1.")
            return

        print(f"   Input PDF: {pdf_path}")

        # ── Phase 1b: Style Extraction ──
        if style_path:
            print(f"   Style Ref: {style_path}")
            from src.style_manager import extract_style

            style_config = extract_style(style_path)
        else:
            print("   Style Ref: None (using defaults)")
        print()

        from src.deconstructor import deconstruct

        if is_resume and manuscript_file.exists():
            print("   🔄 Resuming from existing partial manuscript extraction...")
        else:
            deconstruct(pdf_path)

        # ── Phase 1c: Visual Triage ──
        skip_images = os.getenv("SKIP_IMAGES", "").lower() == "true"
        if skip_images:
            print("\n   ⏩ Skipping Visual Triage (No Images mode)")
        else:
            print("\n   🔍 Running Visual Triage...")
            try:
                from src.triage import process_images, clean_manuscript

                extracted_dir = str(OUTPUT_DIR / "assets" / "extracted_images")
                discarded = process_images(cache_dir=extracted_dir)
                clean_manuscript(str(manuscript_file), discarded)
            except Exception as e:
                print(f"   ⚠️  Triage skipped: {e}")

        save_state(1, {"style_config": style_config})
        print(f"\n   ✅ Phase 1 complete → {manuscript_file}\n")

        # ── Phase 1.5: The Curriculum Planner ──
        print("━" * 58)
        print("🎓  PHASE 1.5 — THE CURRICULUM PLANNER")
        print("━" * 58)
        from src.syllabus_generator import generate_syllabus

        generate_syllabus(manuscript_file)
        print()

    # ──────────────────────────────────────────
    # PHASE 2: THE EXPANSION SWARM
    # ──────────────────────────────────────────
    if start_phase <= 2:
        print("━" * 58)
        print("🐝  PHASE 2 — THE EXPANSION SWARM")
        print("━" * 58)

        # Recover style_config from checkpoint if resuming
        if start_phase > 1 and not style_config:
            saved = load_state()
            style_config = saved.get("style_config", {})

        from src.chunker import chunk_manuscript
        from src.graph import build_graph
        from src.agents import _get_model, _test_llm_connection

        if not manuscript_file.exists():
            print("❌ Manuscript not found. Cannot proceed to Phase 2.")
            return

        # Test LLM connectivity before processing chunks
        model = _get_model()
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        print(f"   🔍 Testing LLM connection...")
        print(f"      Model: {model}")
        print(f"      API Key: {'SET' if api_key else 'NOT SET'}")

        if model.startswith("gemini/") and not api_key:
            print("   ❌ ERROR: Gemini model requires GOOGLE_API_KEY or GEMINI_API_KEY")
            print("   💡 Set GOOGLE_API_KEY in your .env file")
            print("   ⚠️  Aborting Phase 2 - cannot proceed without API key")
            return

        if not _test_llm_connection():
            print("   ⚠️  LLM connection test failed. Chunks may fail.")
            print("   💡 Check your DEFAULT_MODEL env var and API keys.")
            print("   ⚠️  Continuing anyway, but expect failures...")

        chunks = chunk_manuscript(str(manuscript_file))
        graph = build_graph()
        total = len(chunks)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # ── Async Phase 2 Swarm ──
        import asyncio

        CHUNKS_DIR = OUTPUT_DIR / "expanded_chunks"
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

        async def process_chunk(sem, i, chunk):
            chunk_file = CHUNKS_DIR / f"chunk_{i:04d}.md"
            if chunk_file.exists():
                print(f"   🔄 Chunk {i + 1}/{total} already exists. Skipping...")
                return chunk_file.read_text(encoding="utf-8")

            async with sem:
                print(
                    f"\n   ── [ASYNC] Processing Chunk {i + 1}/{total} ({len(chunk):,} chars) ──"
                )

                # Validate chunk before processing
                if not chunk or len(chunk.strip()) == 0:
                    print(f"   ⚠️  Chunk {i + 1} is empty, skipping...")
                    expanded = chunk
                else:
                    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

                    target_pages = int(os.getenv("TARGET_PAGES", "600"))
                    chars_per_page = 3000
                    target_chars = max(
                        int((target_pages * chars_per_page) / total), len(chunk) * 4
                    )

                    # Clamp to ~22,000 characters to safely stay under the LLM's 8,192 token max output threshold
                    target_chars = min(target_chars, 22000)

                    # Ensure initial state has all required keys
                    initial_state = {
                        "current_chunk": chunk,
                        "revision_count": 0,
                        "analysis": "",
                        "expanded_chunk": "",
                        "feedback": "",
                        "target_chars": target_chars,
                    }

                    try:
                        result = await graph.ainvoke(initial_state, config)

                        # Safely extract expanded chunk
                        expanded = (
                            result.get("expanded_chunk")
                            or result.get("current_chunk")
                            or chunk
                        )

                        # Validate result
                        if not expanded or len(expanded.strip()) == 0:
                            print(
                                f"   ⚠️  Chunk {i + 1} produced empty expansion, using original"
                            )
                            expanded = chunk
                            with open(
                                OUTPUT_DIR / "dlq_failed_chunks.jsonl",
                                "a",
                                encoding="utf-8",
                            ) as f:
                                f.write(
                                    json.dumps(
                                        {
                                            "chunk_index": i + 1,
                                            "reason": "empty_expansion",
                                            "content": chunk,
                                        }
                                    )
                                    + "\n"
                                )
                        elif expanded == chunk:
                            print(
                                f"   ⚠️  Chunk {i + 1} returned unchanged (may indicate failure)"
                            )
                            with open(
                                OUTPUT_DIR / "dlq_failed_chunks.jsonl",
                                "a",
                                encoding="utf-8",
                            ) as f:
                                f.write(
                                    json.dumps(
                                        {
                                            "chunk_index": i + 1,
                                            "reason": "unchanged_expansion",
                                            "content": chunk,
                                        }
                                    )
                                    + "\n"
                                )
                        else:
                            print(
                                f"   ✅ Chunk {i + 1} expanded → {len(expanded):,} chars"
                            )

                    except KeyboardInterrupt:
                        print(f"\n   ⚠️  Interrupted by user at chunk {i + 1}")
                        raise
                    except Exception as e:
                        import traceback

                        error_type = type(e).__name__
                        error_msg = str(e)
                        print(
                            f"   ⚠️  Chunk {i + 1} failed ({error_type}): {error_msg}"
                        )
                        # Print full traceback for debugging
                        tb_lines = traceback.format_exc().splitlines()
                        for line in tb_lines[:10]:  # Show more lines
                            if line.strip() and not line.startswith("File"):
                                print(f"      {line}")
                        expanded = chunk
                        with open(
                            OUTPUT_DIR / "dlq_failed_chunks.jsonl",
                            "a",
                            encoding="utf-8",
                        ) as f:
                            f.write(
                                json.dumps(
                                    {
                                        "chunk_index": i + 1,
                                        "reason": error_msg,
                                        "content": chunk,
                                    }
                                )
                                + "\n"
                            )

                # Safely write to granular checkpoint
                chunk_file.write_text(expanded, encoding="utf-8")
                return expanded

        async def run_phase_2():
            # Throttle parallel connections based on model rate limits
            model = os.getenv("DEFAULT_MODEL", "groq/llama3-8b-8192")
            if "flash" in model.lower():
                concurrency = 30  # Massive volume
            elif "pro" in model.lower():
                concurrency = 10  # Premium, strict limit
            else:
                concurrency = 15  # Default safe limit

            sem = asyncio.Semaphore(concurrency)
            print(f"   🚀 Starting Async Phase 2 Swarm (Concurrency: {concurrency})...")

            tasks = [process_chunk(sem, i, chunk) for i, chunk in enumerate(chunks)]
            return await asyncio.gather(*tasks)

        # Run the asynchronous loop array
        expanded_chunks_list = asyncio.run(run_phase_2())

        # Merge all cleanly downloaded chunks into the monolithic file
        full_expanded = "\n\n---\n\n".join(expanded_chunks_list).strip()
        EXPANDED_PATH.write_text(full_expanded, encoding="utf-8")

        save_state(2, {"total_chunks": total, "style_config": style_config})
        print(f"\n   ✅ Phase 2 complete → {EXPANDED_PATH}")
        print(f"   📊 {total} chunks expanded ({len(full_expanded):,} total chars)\n")

    # ──────────────────────────────────────────
    # PHASE 3: THE ART DEPARTMENT
    # ──────────────────────────────────────────
    if start_phase <= 3:
        print("━" * 58)
        print("🎨  PHASE 3 — THE ART DEPARTMENT")
        print("━" * 58)

        # Recover data if resuming
        if start_phase > 2:
            saved = load_state()
            style_config = saved.get("style_config", {})
            total = saved.get("total_chunks", 0)

        # Read expanded draft
        if EXPANDED_PATH.exists():
            full_expanded = EXPANDED_PATH.read_text(encoding="utf-8")
            full_expanded = full_expanded.replace("--- CHUNK END ---", "---").strip()
        else:
            print("❌ Expanded draft not found. Cannot proceed to Phase 3.")
            return

        skip_images = os.getenv("SKIP_IMAGES", "").lower() == "true"
        from src.resolver import process_art_department
        # Pass the REAL style_config and the skip_images flat
        process_art_department(full_expanded, style_config, skip_images=skip_images)

        save_state(3, {"total_chunks": total, "style_config": style_config})
        print(f"\n   ✅ Phase 3 complete → {RESOLVED_PATH}\n")

    # ──────────────────────────────────────────
    # PHASE 4: THE TYPESETTING ENGINE
    # ──────────────────────────────────────────
    if start_phase <= 4:
        print("━" * 58)
        print("🖨️  PHASE 4 — THE TYPESETTING ENGINE")
        print("━" * 58)

    # Recover metadata if jumping to Phase 4
    if start_phase > 3:
        saved = load_state()
        total = saved.get("total_chunks", 0)
        style_config = saved.get("style_config", {})

    from src.structurer import structurer_node
    from src.renderer_latex import render_page_latex

    # 1. Read the resolved manuscript (or expanded if resolved missing)
    manuscript_path = RESOLVED_PATH if RESOLVED_PATH.exists() else EXPANDED_PATH
    if not manuscript_path.exists():
        print("❌ No manuscript found to render.")
        return

    print(f"📖 Reading manuscript from {manuscript_path}...")
    text = manuscript_path.read_text(encoding="utf-8")

    # 2. Split using the same chunker as Phase 2 for consistency (Fix #13)
    from src.chunker import chunk_manuscript as _chunker

    # Write temp file for chunker since it reads files
    temp_chunk_file = OUTPUT_DIR / "_phase4_temp.txt"
    temp_chunk_file.write_text(text, encoding="utf-8")
    try:
        chunks = _chunker(str(temp_chunk_file))
    finally:
        temp_chunk_file.unlink(missing_ok=True)

    full_structure = {"title": "Generated Book", "sections": []}

    # 3. Structure — with fault tolerance (skip bad sections)
    print(f"🤖 AI Structuring ({len(chunks)} sections)...")
    print(f"   Using model: {os.getenv('DEFAULT_MODEL', 'groq/llama3-8b-8192')}")

    # Checkpoint support: resume from partial JSON if it exists
    json_path = OUTPUT_DIR / "book_structure.json"
    start_section = 0
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            existing_sections = existing.get("sections", [])
            if existing_sections:
                start_section = len(existing_sections)
                full_structure["sections"] = existing_sections
                print(
                    f"   🔄 Found existing structure with {start_section} sections, resuming from section {start_section + 1}..."
                )
        except Exception as e:
            print(f"   ⚠️ Could not load existing structure: {e}, starting fresh")

    failed_sections = 0
    rate_limit_delays = 0

    # A1: ASYNC PHASE 4 — Parallel structurer using asyncio
    # Drops Phase 4 from ~3 hours (sequential) to ~12 minutes (20 parallel workers)
    import asyncio

    CONCURRENCY = int(os.getenv("STRUCTURER_CONCURRENCY", "20"))
    print(f"   ⚡ Async Mode: {CONCURRENCY} parallel workers")

    remaining_chunks = list(enumerate(chunks[start_section:], start=start_section))
    results_map = {}
    
    # We need a progress counter and a lock for checkpoint saving
    _completed_count = [0]
    _checkpoint_lock = asyncio.Lock()

    async def _async_process_chunk(sem, i, chunk):
        async with sem:
            try:
                data = await structurer_node(chunk)
                if isinstance(data, dict) and "error" in data:
                    error_msg = data["error"]
                    if "rate limit" not in error_msg.lower() and "429" not in error_msg:
                        raise Exception(f"Structurer Error: {error_msg}")
                    return i, None
                
                res_node = None
                if isinstance(data, list):
                    res_node = {"type": "chapter", "sections": data}
                elif isinstance(data, dict) and "error" not in data:
                    res_node = data
                else:
                    raise Exception(f"Unexpected structurer return type: {type(data)}")

                # Update results and save periodic checkpoint
                results_map[i] = res_node
                _completed_count[0] += 1
                
                if _completed_count[0] % 50 == 0 or _completed_count[0] == len(remaining_chunks):
                    async with _checkpoint_lock:
                        print(f"   Processing section {start_section + _completed_count[0]}/{len(chunks)}...")
                        ordered = [results_map[k] for k in sorted(results_map.keys())]
                        full_structure["sections"] = existing_sections + ordered
                        json_path.write_text(json.dumps(full_structure, indent=2), encoding="utf-8")
                        print(f"   💾 Checkpoint saved ({start_section + _completed_count[0]}/{len(chunks)} sections processed)")
                
                return i, res_node

            except Exception as e:
                fallback_text = chunk[:2000] if len(chunk) > 2000 else chunk
                res_node = {
                    "type": "chapter",
                    "sections": [{"type": "paragraph", "text": fallback_text}],
                    "_failed": str(e)[:100],
                }
                results_map[i] = res_node
                return i, res_node

    async def run_phase_4_structuring():
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [_async_process_chunk(sem, i, chunk) for i, chunk in remaining_chunks]
        await asyncio.gather(*tasks)

    # Run the async structuring
    asyncio.run(run_phase_4_structuring())

    # Merge ordered results into full_structure
    ordered_results = [results_map[k] for k in sorted(results_map.keys())]
    full_structure["sections"] = (
        existing_sections if start_section > 0 else []
    ) + ordered_results
    failed_sections = sum(1 for r in ordered_results if r.get("_failed"))

    if failed_sections:
        print(
            f"\n   ⚠️  {failed_sections}/{len(chunks)} sections failed and used fallback text"
        )
        if failed_sections > len(chunks) * 0.5:
            print(
                f"   ⚠️  WARNING: >50% failure rate! Check API key, rate limits, or model availability"
            )
    else:
        print(f"\n   ✅ All {len(chunks)} sections structured successfully")

    # 3.5 Robust Chapter Demotion (DISABLED)
    # Disabled: This was aggressively demoting valid Unit headings if they
    # lacked exact keywords, ruining the final LaTeX chapter numbering.
    # for chapter in full_structure.get("sections", []):
    #     if chapter.get("type") == "chapter":
    #         for sec in chapter.get("sections", []):
    #             if sec.get("type") == "heading" and sec.get("level") == 1:
    #                 heading_text = sec.get("text", "").lower()
    #                 if not any(k in heading_text for k in ["chapter ", "unit ", "module ", "part "]):
    #                     sec["level"] = 2

    # 3.6 Resolve Image Tags & Generate Diagrams (PHASE 3 Integration)
    from src.resolver import resolve_art_tags, resolve_original_assets

    # B1: MAX_NEW_DIAGRAMS — Cap diagram generation to prevent 18-hour runs
    MAX_NEW_DIAGRAMS = int(os.getenv("MAX_NEW_DIAGRAMS", "40"))
    _diagram_count = [0]  # mutable counter accessible inside closure
    print(f"🎨 Resolving AI Diagrams (limit: {MAX_NEW_DIAGRAMS} new diagrams)...")

    def process_node(node):
        if isinstance(node, dict):
            if "text" in node and isinstance(node["text"], str):
                original = node["text"]
                # 1. Resolve ORIGINAL PDF Extractions (no limit — these are pre-existing assets)
                if "ORIGINAL_ASSET" in original:
                    new_text = resolve_original_assets(original)
                    if new_text != original:
                        original = new_text
                        node["text"] = new_text
                # 2. Resolve AI Generated Diagrams — with hard cap
                if "NEW_DIAGRAM" in original:
                    if _diagram_count[0] >= MAX_NEW_DIAGRAMS:
                        # Silent strip: remove the tag, no broken LaTeX include
                        import re as _re

                        node["text"] = _re.sub(
                            r"\[NEW_DIAGRAM:[^\]]*\]", "", original
                        ).strip()
                    else:
                        new_text = resolve_art_tags(original, style_config)
                        if new_text != original:
                            node["text"] = new_text
                            _diagram_count[0] += 1
            for v in node.values():
                process_node(v)
        elif isinstance(node, list):
            for item in node:
                process_node(item)

    # Skip image resolution entirely in No Images mode
    skip_images = os.getenv("SKIP_IMAGES", "").lower() == "true"
    if skip_images:
        print("   ⏩ Skipping AI Diagram resolution (No Images mode)")
        # Strip any remaining image tags from JSON
        def strip_image_tags(node):
            if isinstance(node, dict):
                if "text" in node and isinstance(node["text"], str):
                    node["text"] = re.sub(r"\[ORIGINAL_ASSET:[^\]]*\]", "", node["text"])
                    node["text"] = re.sub(r"\[NEW_DIAGRAM:[^\]]*\]", "", node["text"])
                    node["text"] = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", node["text"])  # strip md images
                    node["text"] = node["text"].strip()
                for v in node.values():
                    strip_image_tags(v)
            elif isinstance(node, list):
                for item in node:
                    strip_image_tags(item)
        strip_image_tags(full_structure)
        print("   ✅ Image tags stripped.")
    else:
        process_node(full_structure)
        print(f"   ✅ Diagrams resolved: {_diagram_count[0]} generated, rest stripped.")

    # 4. Save JSON structure (json_path already declared above at checkpoint section)
    json_path.write_text(json.dumps(full_structure, indent=2), encoding="utf-8")
    print(f"📄 JSON saved: {json_path}")

    # QA CHECK: Validation Agent
    try:
        from src.checker import run_qa_check

        run_qa_check(str(json_path), str(OUTPUT_DIR))
    except Exception as e:
        print(f"⚠️ QA Checker failed to execute: {e}")
    # ── BookUdecate 8.0: Quality post-processing (JSON Level) ──
    from src.post_processor import (
        merge_micro_chapters,
        deduplicate_paragraphs,
        strip_syllabus_restarts,
        strip_empty_chapters,
        strip_heading_only_chapters,
    )

    chapters = full_structure["sections"]
    print(f"   📊 Original chapter count: {len(chapters)}")

    # Strip empty/heading-only chapters BEFORE merging/rendering
    chapters = strip_empty_chapters(chapters)
    chapters = strip_heading_only_chapters(chapters)

    # Merge small chapters
    chapters = merge_micro_chapters(chapters, min_chars=3000, max_chapters=60)
    print(f"   📊 Final chapter count: {len(chapters)}")

    # 5. Render Typst
    from src.renderer_typst import render_page_typst, sanitize_typst_output

    typst_parts = []
    for chapter in chapters:
        try:
            typst_parts.append(render_page_typst(chapter))
        except Exception as e:
            print(f"   ⚠️ Typst render error: {e} — skipping chapter")

    # 6. Build Typst document
    typ_out = OUTPUT_DIR / "BookEducate.typ"
    template_path = BASE_DIR / "templates" / "bookeducate.typ"
    if not template_path.exists():
        print(f"❌ Typst Template not found at {template_path}")
        return

    template_content = template_path.read_text(encoding="utf-8")
    typst_body = "\n".join(typst_parts)

    # ── BookUdecate 8.0: Full post-processing pipeline ──
    print("🔧 Running BookUdecate 8.0 quality post-processors...")

    # Fault #1: Remove consecutive duplicate paragraphs
    typst_body = deduplicate_paragraphs(typst_body)
    # Fault #8: Strip syllabus restarts from chapter 3+
    typst_body = strip_syllabus_restarts(typst_body)

    # Master Typst Sanitizer
    typst_body = sanitize_typst_output(typst_body)
    print("   ✅ All post-processors + Typst sanitizer applied")

    full_typst = template_content.replace("$body$", typst_body)

    typ_out.write_text(full_typst, encoding="utf-8")
    print(f"✅ Typst Generated: {typ_out}")

    # 7. Compile PDF
    print("🚀 Compiling PDF with Typst...")
    output_pdf = OUTPUT_DIR / "BookEducate.pdf"
    try:
        start_compile = time.time()
        result = subprocess.run(
            ["typst", "compile", str(typ_out), str(output_pdf)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        
        compile_time = time.time() - start_compile
        
        if result.returncode != 0:
            print("   ⚠️ Typst compilation warnings/errors:")
            print(result.stderr)
            
        if output_pdf.exists() and output_pdf.stat().st_size > 0:
            size_mb = output_pdf.stat().st_size / (1024 * 1024)
            print(f"\n✅ PDF Compiled: {output_pdf} ({size_mb:.2f} MB) in {compile_time:.2f}s")
        else:
            print("\n❌ PDF file was not created. Check Typst output above.")

    except subprocess.TimeoutExpired:
        print("❌ typst timed out after 300 seconds.")
    except FileNotFoundError:
        print("❌ typst not found. Please install Typst CLI.")

    save_state(4, {"total_chunks": total})

    # ──────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              🎉  BOOKEDUCATE COMPLETE  🎉                 ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  ⏱️  Total time: {minutes}m {seconds}s")
    print(f"║  📄  Chunks processed: {total}")
    print(f"║  📝  Expanded draft: {EXPANDED_PATH}")
    print(f"║  📖  Final PDF: {output_pdf}")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


# ──────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BookUdecate V1.0 Pipeline")
    parser.add_argument("pdf_input", help="Path to input PDF", nargs="?")
    parser.add_argument("--style", help="Path to Style Reference PDF", default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the last completed phase checkpoint",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Jump directly to a specific phase (e.g., --phase 4)",
    )
    parser.add_argument(
        "--is-resume",
        action="store_true",
        help="Internal flag from API to prevent directory wiping when resuming Phase 1",
    )

    args = parser.parse_args()

    # Determine start phase
    start_phase = 1
    if args.resume:
        state = load_state()
        start_phase = state.get("completed_phase", 0) + 1
        if start_phase > 4:
            print("✅ Pipeline already complete. Nothing to resume.")
            sys.exit(0)
        print(f"🔄 Resuming from Phase {start_phase}...")
    elif args.phase:
        start_phase = args.phase

    # Validate: need PDF for Phase 1
    if start_phase <= 1:
        if not args.pdf_input or not Path(args.pdf_input).exists():
            print(f"❌ File not found: {args.pdf_input}")
            sys.exit(1)

    main(
        args.pdf_input,
        args.style,
        start_phase=start_phase,
        is_resume=args.is_resume or args.resume,
    )
