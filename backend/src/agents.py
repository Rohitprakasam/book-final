"""
BookUdecate V1.0 — Agent Node Functions (Expansion Swarm)
=======================================================
Three LangGraph nodes forming the per-chunk expansion loop:
    analyst_node → drafter_node → critic_node (→ loop or END)

Persona and subject are configured via environment variables:
    BOOK_SUBJECT  (default: "Engineering")
    BOOK_PERSONA  (default: "Elite Professor specializing in the subject matter")
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import lru_cache
from pathlib import Path

import litellm
from dotenv import load_dotenv

from src.state import BookState

load_dotenv()

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
LLM_TIMEOUT = 1800  # 30 minutes — gives CPU-based Ollama time to finish
DEFAULT_FALLBACK_MODEL = "gemini/gemini-2.0-flash"


def _get_model() -> str:
    """Return the model identifier from the environment."""
    model = os.getenv("DEFAULT_MODEL", DEFAULT_FALLBACK_MODEL)
    if not model:
        print("[Config] ⚠️ WARNING: DEFAULT_MODEL not set, using fallback")
        return DEFAULT_FALLBACK_MODEL
    return model


# B3: Tiered Model Router
# Math-heavy content uses a more capable model; prose uses the fast/cheap model.
_MATH_KEYWORDS = [
    "\\frac",
    "\\int",
    "\\sum",
    "\\partial",
    "differential",
    "derivation",
    "equation",
    "thermodynamic",
    "calculus",
    "matrix",
    "eigenvalue",
    "Laplace",
    "Fourier",
    "\\nabla",
    "\\Delta",
]


def _select_model(chunk: str = "") -> str:
    """
    Route to the most appropriate model based on content type.
    - If LLM_PROVIDER is ollama, route to the local network Ollama instance.
    - Math/derivation heavy → powerful accurate model (gemini-pro)
    - Standard prose/definitions → fast cheap model (gemini-flash)
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider == "ollama":
        # Litellm natively maps "ollama/*" to the local ollama server API
        return "ollama/llama3"
        
    base = os.getenv("DEFAULT_MODEL", DEFAULT_FALLBACK_MODEL)
    pro_model = os.getenv("MATH_MODEL", base)  # Override for math if set
    flash_model = os.getenv("FLASH_MODEL", base)

    if chunk and any(kw in chunk for kw in _MATH_KEYWORDS):
        return pro_model
    return flash_model


def _test_llm_connection() -> bool:
    """Test if LLM API is accessible. Returns True if working."""
    model = _get_model()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    # Check if API key is set for Gemini models
    if model.startswith("gemini/") and not api_key:
        print(
            f"[Config] ⚠️ WARNING: Gemini model ({model}) requires GOOGLE_API_KEY or GEMINI_API_KEY"
        )
        print(
            f"[Config]    Current keys: GOOGLE_API_KEY={'SET' if os.getenv('GOOGLE_API_KEY') else 'NOT SET'}, "
            f"GEMINI_API_KEY={'SET' if os.getenv('GEMINI_API_KEY') else 'NOT SET'}"
        )
        return False

    try:
        # For Gemini, LiteLLM needs the API key passed explicitly or via env
        # Test with a minimal request
        test_response = litellm.completion(
            model=model,
            timeout=15,  # Short timeout for test
            messages=[{"role": "user", "content": "Say OK"}],
            api_key=api_key if api_key else None,  # Pass API key explicitly
        )
        if (
            test_response
            and hasattr(test_response, "choices")
            and test_response.choices
        ):
            content = test_response.choices[0].message.content
            print(f"[Config] ✅ LLM connection test passed (model: {model})")
            return True
        else:
            print(f"[Config] ⚠️ LLM test returned empty response")
            return False
    except Exception as e:
        error_msg = str(e)
        print(f"[Config] ⚠️ LLM connection test failed: {error_msg}")

        # Provide helpful diagnostics
        if "401" in error_msg or "authentication" in error_msg.lower():
            print(f"[Config] 💡 Authentication error - check your GOOGLE_API_KEY")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print(f"[Config] 💡 Model not found - verify model name: {model}")
            print(
                f"[Config]    For Gemini, try: gemini/gemini-2.0-flash or gemini/gemini-1.5-flash"
            )
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            print(f"[Config] 💡 Rate limit hit - wait a moment and retry")

        return False


# ──────────────────────────────────────────────
# 1. ANALYST NODE
# ──────────────────────────────────────────────
ANALYST_SYSTEM_PROMPT = """\
You are a {BOOK_PERSONA} focusing on \
{BOOK_SUBJECT}. You are planning the expansion of a chapter \
for a publication-ready {ACADEMIC_LEVEL} textbook.

Your Master Blueprint:
{SYLLABUS_CONTEXT}

Read the provided chapter text carefully. Your task is to create a \
DETAILED EXPANSION PLAN that will guide the Drafter agent. The Drafter MUST produce a MASSIVE expansion of this chunk, aiming for at least {TARGET_CHARS} characters.

For each section you identify, your plan MUST specify:

1. **Theoretical Introduction** — What is the "Why" behind the concept? \
What fundamental {BOOK_SUBJECT} principles should be derived from first principles?

2. **Mathematical Derivations Needed** — List the key equations that \
must be DERIVED from scratch using original notation. Example: if the \
source says "Work", you must plan to derive the specific mathematical relationship for the {BOOK_SUBJECT} context.

3. **Mirror Problems** — Plan 3-5 original numerical problems per \
section with RANDOMIZED input values strictly relevant to {BOOK_SUBJECT}. Specify the problem type and \
value ranges.

4. **Diagram Needs** — For every complex concept or mechanism, \
specify a [NEW_DIAGRAM: ...] tag with a technical \
description suitable for technical illustration.

5. **Variable Consistency Dictionary** — To prevent "Drift", you MUST define the specific Typst symbols the Drafter should use for this chapter.
   Example:
   - Primary Variable 1: $X$
   - Primary Variable 2: $Y$

IMPORTANT: You are aware that the Drafter will use Typst environments for complex blocks. Your plan should explicitly request "Structure: Example Problem X" for numerical sections.

Return ONLY the bulleted expansion plan in Markdown. No preambles."""


@lru_cache(maxsize=1)
def _get_syllabus_context() -> str:
    syllabus_context = "No syllabus provided."
    _base = Path(__file__).resolve().parent.parent
    syllabus_path = _base / "data" / "output" / "syllabus.json"
    if syllabus_path.exists():
        try:
            syllabus_data = json.loads(syllabus_path.read_text(encoding="utf-8"))
            parsed_syllabus = json.dumps(syllabus_data, indent=2)
            syllabus_context = (
                f"=== MASTER SYLLABUS ===\n{parsed_syllabus}\n======================="
            )
        except Exception as e:
            print(f"⚠️ Failed to load syllabus JSON: {e}")
    return syllabus_context


async def analyst_node(state: BookState) -> dict:
    """
    Reads the current chunk, analyses core engineering concepts,
    and produces a bulleted expansion plan for the Drafter.
    """
    # Safely extract chunk with validation
    chunk = state.get("current_chunk", "")

    if not chunk or len(chunk.strip()) == 0:
        print("[Analyst] ⚠️ Empty chunk received")
        return {"analysis": "Error: Analyst received empty chunk."}

    model = _select_model(chunk)  # B3: Route math chunks to pro model, prose to flash
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    syllabus_context = _get_syllabus_context()

    try:
        max_retries_analyst = 5
        for attempt in range(max_retries_analyst):
            try:
                # For Gemini models, ensure API key is available
                if model.startswith("gemini/") and not api_key:
                    print(
                        f"[Analyst] ❌ No API key found for Gemini model. Set GOOGLE_API_KEY or GEMINI_API_KEY"
                    )
                    return {"analysis": "Error: Analyst failed - missing API key."}

                response = await litellm.acompletion(
                    model=model,
                    timeout=LLM_TIMEOUT,
                    messages=[
                        {
                            "role": "system",
                            "content": ANALYST_SYSTEM_PROMPT.replace(
                                "{BOOK_PERSONA}",
                                os.getenv(
                                    "BOOK_PERSONA",
                                    "Elite Professor specializing in the subject matter",
                                ),
                            )
                            .replace(
                                "{BOOK_SUBJECT}",
                                os.getenv("BOOK_SUBJECT", "Engineering"),
                            )
                            .replace(
                                "{ACADEMIC_LEVEL}",
                                os.getenv("ACADEMIC_LEVEL", "Undergraduate Course"),
                            )
                            .replace(
                                "{TARGET_CHARS}", str(state.get("target_chars", 8000))
                            )
                            .replace("{SYLLABUS_CONTEXT}", syllabus_context),
                        },
                        {
                            "role": "user",
                            "content": f"Here is the chapter text to analyse:\n\n{chunk}",
                        },
                    ],
                    api_key=api_key if model.startswith("gemini/") else None,
                    api_base=os.getenv("OLLAMA_API_BASE") if provider == "ollama" else None,
                )
                break
            except litellm.APIConnectionError:
                print(f"[Analyst] 📡 Internet disconnected. Sleeping 30s...")
                await asyncio.sleep(30)
            except Exception as other_err:
                if (
                    "11001" in str(other_err).lower()
                    or "getaddrinfo" in str(other_err).lower()
                    or "time" in str(other_err).lower()
                ):
                    print(
                        f"[Analyst] 📡 Internet disconnected/Timeout. Sleeping 30s..."
                    )
                    await asyncio.sleep(30)
                else:
                    raise other_err
        else:
            return {
                "analysis": "Error: Analyst failed to generate plan due to repeated network errors."
            }
    except Exception as e:
        error_msg = str(e)
        print(f"[Analyst] ❌ LLM call failed: {error_msg}")

        # Provide specific error guidance
        if "401" in error_msg or "authentication" in error_msg.lower():
            print(f"[Analyst] 💡 Authentication error - check your GOOGLE_API_KEY")
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            print(f"[Analyst] 💡 Rate limit - Gemini API has usage limits")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print(f"[Analyst] 💡 Model not found - verify model name: {model}")

        return {"analysis": "Error: Analyst failed to generate plan due to API error."}

    if not response or not hasattr(response, "choices") or not response.choices:
        print("[Analyst] ⚠️ Empty or invalid response from LLM")
        return {"analysis": "Error: Analyst failed to generate plan."}

    try:
        analysis = response.choices[0].message.content
        if not analysis:
            print("[Analyst] ⚠️ Empty content in response")
            return {"analysis": "Error: Analyst returned empty content."}
    except (AttributeError, IndexError, KeyError) as e:
        print(f"[Analyst] ⚠️ Failed to extract content from response: {e}")
        return {"analysis": "Error: Analyst response format invalid."}

    print(f"[Analyst] Produced expansion plan ({len(analysis):,} chars)")
    return {"analysis": analysis}


# ──────────────────────────────────────────────
# 2. DRAFTER NODE
# ──────────────────────────────────────────────
DRAFTER_SYSTEM_PROMPT = """You are an Expert {BOOK_SUBJECT} Textbook Author writing for a {ACADEMIC_LEVEL} audience. You will receive a discrete text chunk extracted from a Source_Manuscript.

Your Master Curriculum Blueprint:
{SYLLABUS_CONTEXT}

Your objective is to produce a MASSIVE expansion of this text chunk to meet a strict length requirement. To achieve your portion of this goal, you MUST expand this text chunk to be AT LEAST {TARGET_CHARS} characters long by expanding VERTICALLY and NEVER HORIZONTALLY.

Expansion Rules:

1. Vertical Expansion (No Domain Drift): To hit your character count, you must go DEEPER into the specific concept (more detailed proofs, 5+ complex step-by-step example problems, real-world industrial case studies). You are FORBIDDEN from discussing topics outside of {BOOK_SUBJECT}.

2. Context: Add relevant historical context or real-world industrial applications for every concept, strictly within the {BOOK_SUBJECT} domain.

3. Step-by-Step: Derive mathematical formulas from first principles, and provide multiple step-by-step example problems.

4. Singular Focus (Anti-Repetition): DO NOT repeat broad, high-level introductory concepts unless they are the direct focus of the input chunk.

5. Art Direction Rules:
   - If the source text contains `[ORIGINAL_ASSET: filepath]` tags, YOU MUST PRESERVE THEM EXACTLY AS THEY ARE in your expanded output. Do not alter or remove them.
   - Whenever an entirely NEW visual aid is necessary to explain a complex mechanism, insert an Image Request block in exact JSON format. DO NOT use standard Markdown image links.
   - "caption": A short, title-case name for the figure (e.g., "Figure 1.2: Hydraulic Gear Pump").
   - "subject": A detailed visual description for the artist.
   - "type": "technical illustration", "schematic", or "graph".

Example:
[NEW_DIAGRAM: {"caption": "Figure 2.1: Double-Acting Cylinder Cross-Section", "subject": "Cross-section of a double-acting hydraulic cylinder showing fluid flow paths and piston seals", "type": "technical illustration"}]

5. Formatting Rules (CRITICAL):
   - For standard text, use standard Markdown text.
   - For "Example Problems", "Definitions", or "Key Takeaways", YOU MUST USE TYPST ENVIRONMENTS.
   - Use Typst math syntax (e.g. `$ x / y $` or `$ integral_a^b x dif x $`). DO NOT use LaTeX commands like `\\frac` or `\\int`. 
   - Format Example Problems exactly like this:
     
     #exampleproblem("Example Problem X: [Title]")[
       *Problem Statement:* [Text]

       #solution[
         1. Step one...
         $ math equation $
       ]
     ]

   - Do NOT use plain Markdown bullet points or bold text for these headers without the Typst structure.
   
6. Output the final expanded text in clean Markdown/Typst mix (no wrappers).

7. ANTI-DUPLICATION: NEVER repeat a derivation, equation, or example problem that you have already written in the current output. If you realize you are restating something, SKIP IT immediately and move to the next concept. Each paragraph must add NEW information.

8. CLEAN OUTPUT — NO SCAFFOLDING: Your output must read like a polished, published textbook. NEVER emit raw template labels like standalone "Problem Statement:", "Solution:", or re-trigger section headers mid-answer. Example problems must ONLY appear inside the `#exampleproblem` Typst function. Outside of those environments, never write "Problem Statement:" or "Solution:" as standalone labels.

9. NUMERICAL PRECISION: When performing unit conversions or calculations, ALWAYS verify the arithmetic before writing it. For example: 1217 kPa = 1.217 MPa (divide by 1000). NEVER produce contradictory numerical results. If you compute a value, use that SAME value consistently throughout the section.

10. HUMAN-READABLE NUMBERS: Use plain numbers whenever possible. Write "2 kg/s" NOT "2.00 × 10⁰ kg/s". Write "100 kW" NOT "1.00 × 10² kW". Only use scientific notation for numbers greater than 10,000 or smaller than 0.01. This is MANDATORY.

11. NO CONTEXT RESET: You are writing ONE CONTINUOUS CHAPTER in a larger book. Do NOT re-introduce syllabus objectives, unit overviews, or foundational definitions that belong in Chapter 1. Assume the reader has read ALL previous chapters. Jump straight into the topic of THIS chunk without preamble."""


async def drafter_node(state: BookState) -> dict:
    """
    Expands the chapter using synthetic authoring with first-principles
    derivation, mirror problems, and diagram tags.
    """
    import json
    from pathlib import Path

    # Safely extract state with defaults
    chunk = state.get("current_chunk", "")
    analysis = state.get("analysis", "")
    feedback = state.get("feedback", "")

    # Validate inputs
    if not chunk or len(chunk.strip()) == 0:
        print("[Drafter] ⚠️ Empty chunk received, returning as-is")
        return {
            "expanded_chunk": chunk,
            "revision_count": state.get("revision_count", 0) + 1,
        }

    # If analysis indicates an error, skip expansion
    if analysis and analysis.startswith("Error: Analyst"):
        print("[Drafter] ⚠️ Analyst failed, skipping expansion")
        return {
            "expanded_chunk": chunk,
            "revision_count": state.get("revision_count", 0) + 1,
        }

    # --- Load Transcribed Math (OCR Data) ---
    math_context = ""
    _base = Path(__file__).resolve().parent.parent
    math_path = _base / "data" / "output" / "transcribed_math.json"
    if math_path.exists():
        try:
            math_data = json.loads(math_path.read_text(encoding="utf-8"))
            # Simple heuristic: Include ALL transcribed math for now,
            # or filter by page if we had page info in chunk.
            # Since we iterate sequentially, passing the whole dict is okay for 128k context,
            # but better to just pass it all as reference.
            if math_data:
                math_formatted = json.dumps(math_data, indent=2)
                math_context = f"\n\n=== TRANSCRIBED MATH (RESCUED FROM IMAGES) ===\n{math_formatted}\n"
        except Exception as e:
            print(f"⚠️ Failed to load math JSON: {e}")

    # --- Load Master Syllabus ---
    syllabus_context = _get_syllabus_context()

    # Build context: if in revision loop, include critic feedback
    revision_context = ""
    if feedback and feedback != "APPROVED":
        revision_context = (
            f"\n\n=== CRITIC FEEDBACK (address these issues) ===\n{feedback}"
        )

    # --- Retry Loop for LLM Stability ---
    max_retries = 3
    expanded = None

    model = _get_model()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    for attempt in range(max_retries):
        try:
            # For Gemini models, ensure API key is available
            if model.startswith("gemini/") and not api_key:
                print(
                    "[Drafter] ❌ No API key found for Gemini model. Set GOOGLE_API_KEY or GEMINI_API_KEY"
                )
                expanded = None
                break  # Exit network loop

            response = await litellm.acompletion(
                model=model,
                timeout=LLM_TIMEOUT,
                max_tokens=8192,
                messages=[
                    {
                        "role": "system",
                        "content": DRAFTER_SYSTEM_PROMPT.replace(
                            "{TARGET_CHARS}", str(state.get("target_chars", 8000))
                        )
                        .replace(
                            "{BOOK_SUBJECT}", os.getenv("BOOK_SUBJECT", "Engineering")
                        )
                        .replace(
                            "{ACADEMIC_LEVEL}",
                            os.getenv("ACADEMIC_LEVEL", "Undergraduate Course"),
                        )
                        .replace("{SYLLABUS_CONTEXT}", syllabus_context),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"=== ORIGINAL CHAPTER ({len(chunk):,} chars — expand to "
                            f"at least {len(chunk) * 5:,} chars) ===\n{chunk}\n\n"
                            f"=== EXPANSION PLAN ===\n{analysis}"
                            f"{math_context}"
                            f"{revision_context}"
                        ),
                    },
                ],
                api_key=api_key if model.startswith("gemini/") else None,
                api_base=os.getenv("OLLAMA_API_BASE") if os.getenv("LLM_PROVIDER") == "ollama" else None,
            )
        except litellm.APIConnectionError:
            print("[Drafter] 📡 Internet disconnected. Sleeping 30s...")
            await asyncio.sleep(30)
            continue
        except Exception as other_err:
            if (
                "11001" in str(other_err).lower()
                or "getaddrinfo" in str(other_err).lower()
                or "time" in str(other_err).lower()
            ):
                print("[Drafter] 📡 Internet disconnected/Timeout. Sleeping 30s...")
                await asyncio.sleep(30)
                continue
            else:
                raise other_err

            if response and hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                if content:
                    expanded = content
                    break  # Success!

            print(
                f"[Drafter] ⚠️ Empty response from LLM (Attempt {attempt+1}/{max_retries})"
            )
        except Exception as e:
            error_msg = str(e)
            print(
                f"[Drafter] ⚠️ LLM Error (Attempt {attempt+1}/{max_retries}): {error_msg}"
            )

            # Provide specific error guidance
            if "401" in error_msg or "authentication" in error_msg.lower():
                print(f"[Drafter] 💡 Authentication error - check your GOOGLE_API_KEY")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                print(f"[Drafter] 💡 Rate limit - waiting before retry...")
                import time

                time.sleep(5 * (attempt + 1))  # Exponential backoff
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(f"[Drafter] 💡 Model not found - verify model name: {model}")
                break  # Don't retry if model doesn't exist

    # If all retries failed, use original chunk
    if expanded is None:
        print(
            "[Drafter] ❌ CRITICAL FAILURE: LLM failed 3 times. Returning original chunk."
        )
        return {
            "expanded_chunk": chunk,
            "revision_count": state.get("revision_count", 0) + 1,
        }

    # If we get here, 'expanded' is defined
    revision = state.get("revision_count", 0) + 1

    # --- Strip Markdown Wrappers (Safety Net) ---
    expanded = expanded.replace("```markdown", "").replace("```", "")

    ratio = len(expanded) / max(len(chunk), 1)
    print(
        f"[Drafter] Expanded chunk ({len(expanded):,} chars, {ratio:.1f}x) — revision {revision}"
    )

    return {"expanded_chunk": expanded, "revision_count": revision}


# ──────────────────────────────────────────────
# 3. CRITIC NODE
# ──────────────────────────────────────────────
MIN_EXPANSION_RATIO = 4.0  # Must be at least 4x-5x the original

CRITIC_SYSTEM_PROMPT = """You are a strict Textbook Editor evaluating for a {BOOK_SUBJECT} textbook. Review the Drafter's expanded text against the original chunk from the Source_Manuscript.

Rejection Criteria (Return to Drafter if any are met):

1. Domain Drift (CRITICAL): If the expanded text discusses topics, signals, or theories completely outside of {BOOK_SUBJECT}, REJECT it immediately with feedback to stay strictly on topic.

2. Low Effort: If the generated text is not at least {TARGET_CHARS} characters long, REJECT it with feedback to add more case studies, historical context, or step-by-step examples. You MUST enforce the length requirement.

3. Hallucination: If the Drafter introduced mathematical formulas NOT derived from the Source_Manuscript, REJECT it.

4. Malformed Tags: If the [NEW_DIAGRAM] tags are not valid JSON, REJECT it.

5. DUPLICATED CONTENT: If the same equation, derivation, worked example, or paragraph appears twice (even paraphrased), REJECT with feedback: "DUPLICATE DETECTED: Remove repeated content at [location]. Each concept must appear exactly once."

6. LEAKED SCAFFOLDING: If raw template labels like standalone "Problem Statement:", "Solution:", "Solve for X:", or "Calculate the Y:" appear OUTSIDE of a proper `#exampleproblem` / `#solution` environment, REJECT with feedback: "SCAFFOLDING LEAK: Move all problem/solution labels inside Typst environments."

7. SCIENTIFIC NOTATION ABUSE: If the draft uses scientific notation for simple everyday numbers (e.g., "2.00 × 10⁰ kg/s" instead of "2 kg/s", or "1.00 × 10² kW" instead of "100 kW"), REJECT with feedback: "Use plain numbers. Scientific notation is only for values > 10,000 or < 0.01."

8. MATH INCONSISTENCY: If two different numerical answers are given for the same calculation in the same section, REJECT with feedback specifying which values conflict and which is correct.

NOTE: The Drafter has been instructed to use Typst block functions (e.g., `#exampleproblem`) for "Example Problems". This is EXPECTED and should NOT be flagged as an artifact.

If the draft passes all checks, output 'APPROVED' followed by the final markdown."""


async def critic_node(state: BookState) -> dict:
    """
    Reviews the expanded chunk for mathematical correctness,
    problem quality, copyright independence, and formatting.
    """
    # Safely extract state with defaults
    expanded = state.get("expanded_chunk", "")
    original = state.get("current_chunk", "")

    # Validate inputs
    if not expanded or len(expanded.strip()) == 0:
        print("[Critic] ⚠️ Empty expanded chunk, approving by default")
        return {"feedback": "APPROVED"}

    if not original or len(original.strip()) == 0:
        print("[Critic] ⚠️ Empty original chunk, approving by default")
        return {"feedback": "APPROVED"}

    # ── Low-Effort Check ──
    target_chars = state.get("target_chars", 8000)
    if len(expanded) < target_chars:
        rejection = (
            f"LOW EFFORT: The expanded text is only {len(expanded):,} characters long, "
            f"which is below the strict requirement of {target_chars:,} characters. "
            "You MUST produce a much longer expansion. "
            "Go deeper: add more derivations, more mirror problems with "
            "randomized values, more [NEW_DIAGRAM: ...] tags. "
            "Do not summarize — DERIVE and EXPAND."
        )
        print(
            f"[Critic] ❌ Low effort ({len(expanded):,} vs {target_chars:,} chars) — forcing re-draft"
        )
        return {"feedback": rejection}

    # ── Cut-off / Truncation Check ──
    # If the LLM hit a token limit, it usually ends mid-word, mid-sentence, or mid-equation.
    clean_ends = (".", "!", "?", '"', "'", "```", "}", "]", ")", "_", "*")
    if expanded and not expanded.strip().endswith(clean_ends):
        rejection = (
            "TRUNCATION DETECTED: The text abruptly cuts off at the very end. "
            "You likely hit the maximum output token limit. "
            "You MUST rewrite the ending to ensure it finishes its thought cleanly with proper punctuation or closing tags like \\end{equation}."
        )
        clipped_end = expanded.strip()[-10:].replace("\n", " ")
        print(
            f"[Critic] ❌ Cut-off detected (ends with '{clipped_end}') — forcing re-draft"
        )
        return {"feedback": rejection}

    # ── Artifact Check ──
    if "```markdown" in expanded or expanded.strip().startswith("```"):
        rejection = "ARTIFACT DETECTED: Remove ```markdown code fences from the output."
        print(f"[Critic] ❌ Artifact detected")
        return {"feedback": rejection}

    model = _get_model()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    try:
        max_retries_critic = 5
        for attempt in range(max_retries_critic):
            try:
                # For Gemini models, ensure API key is available
                if model.startswith("gemini/") and not api_key:
                    print(
                        "[Critic] ❌ No API key found for Gemini model. Approving by default."
                    )
                    return {"feedback": "APPROVED"}

                response = await litellm.acompletion(
                    model=model,
                    timeout=LLM_TIMEOUT,
                    messages=[
                        {
                            "role": "system",
                            "content": CRITIC_SYSTEM_PROMPT.replace(
                                "{TARGET_CHARS}", str(state.get("target_chars", 8000))
                            ).replace(
                                "{BOOK_SUBJECT}",
                                os.getenv("BOOK_SUBJECT", "Engineering"),
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"=== ORIGINAL SOURCE ({len(original):,} chars) ===\n{original}\n\n"
                                f"=== EXPANDED DRAFT ({len(expanded):,} chars) ===\n{expanded}"
                            ),
                        },
                    ],
                    api_key=api_key if model.startswith("gemini/") else None,
                    api_base=os.getenv("OLLAMA_API_BASE") if os.getenv("LLM_PROVIDER") == "ollama" else None,
                )
                break
            except litellm.APIConnectionError:
                print("[Critic] 📡 Internet disconnected. Sleeping 30s...")
                await asyncio.sleep(30)
            except Exception as other_err:
                if (
                    "11001" in str(other_err).lower()
                    or "getaddrinfo" in str(other_err).lower()
                    or "time" in str(other_err).lower()
                ):
                    print("[Critic] 📡 Internet disconnected/Timeout. Sleeping 30s...")
                    await asyncio.sleep(30)
                else:
                    raise other_err
        else:
            return {"feedback": "APPROVED"}

    except Exception as e:
        error_msg = str(e)
        print(f"[Critic] ❌ LLM call failed: {error_msg}. Approving by default.")

        # Provide specific error guidance
        if "401" in error_msg or "authentication" in error_msg.lower():
            print(f"[Critic] 💡 Authentication error - check your GOOGLE_API_KEY")
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            print(f"[Critic] 💡 Rate limit - Gemini API has usage limits")

        return {"feedback": "APPROVED"}  # Fallback to approve if critic API fails

    if not response or not hasattr(response, "choices") or not response.choices:
        print("[Critic] ⚠️ Empty or invalid response from LLM. Approving by default.")
        return {"feedback": "APPROVED"}  # Fallback to approve if critic fails

    try:
        content = response.choices[0].message.content
        if not content:
            print("[Critic] ⚠️ Empty content in response. Approving by default.")
            return {"feedback": "APPROVED"}
        feedback = content.strip()
    except (AttributeError, IndexError, KeyError) as e:
        print(f"[Critic] ⚠️ Failed to extract content: {e}. Approving by default.")
        return {"feedback": "APPROVED"}

    is_approved = "APPROVED" in feedback.upper()
    ratio = len(expanded) / max(len(original), 1)

    if is_approved:
        print(f"[Critic] ✅ APPROVED ({ratio:.1f}x expansion)")
    else:
        print(f"[Critic] ❌ Revision needed — {feedback[:100]}…")

    return {"feedback": feedback}
