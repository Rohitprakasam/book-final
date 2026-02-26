"""
BookEducate — Structurer Node (Phase 4)
======================================
Converts expanded text chunks into structured JSON for LaTeX rendering.
Uses LiteLLM with Gemini API support.
"""

import asyncio
import json
import litellm
import os
from dotenv import load_dotenv

load_dotenv()

# Simplified prompt for prototyping
SYSTEM_PROMPT = """
You are a Content Structurer. Your ONLY job is to convert the user's raw text into a strict JSON format.
DO NOT generate any markdown or explanation. Output ONLY valid JSON.

Schema:
{
  "type": "chapter",
  "title": "string or null",
  "sections": [
    {
      "type": "heading",
      "level": 1-6,
      "text": "string"
    },
    {
      "type": "paragraph",
      "text": "string"
    },
    {
      "type": "equation",
      "math": "string (including $ delimiters)"
    },
    {
       "type": "example_problem",
       "title": "string",
       "problem_statement": "string",
       "solution_steps": [
         [
           { "type": "paragraph", "text": "Step 1 description..." },
           { "type": "equation", "math": "$ x = y $" }
         ]
       ]
    },
    {
        "type": "list",
        "items": ["item 1", "item 2"]
    }
  ]
}

Rules:
1. Identify "Example Problems" and strictly use the "example_problem" structure.
   - The input will likely use Typst ``#exampleproblem("...")[]`` syntax. 
   - The input will likely use Typst `#exampleproblem("...")[]` syntax. 
   - Parse this into the JSON structure.
   - **CRITICAL:** `solution_steps` is a LIST of LISTS. Each inner list represents a step, and contains blocks (paragraphs/equations).
   - DO NOT use strings for steps. You MUST use objects.
2. **MATH SEGREGATION:** Identify independent display math equations (e.g., $$...$$ or $...$ on its own line) or inline math ($...$) and use "type": "equation". 
   - NEVER put display math inside a "paragraph" type. 
   - Split the paragraph before and after the equation.
   - Example: 
     Text: "The formula is $ x = y $ which means..."
     JSON: [
       { "type": "paragraph", "text": "The formula is" },
       { "type": "equation", "math": "$ x = y $" },
       { "type": "paragraph", "text": "which means..." }
     ]
3. Remove all original markdown formatting from the text fields (clean text).
4. **JSON FORMATTING RULES:**
   - Do NOT include newlines (`\n`) inside string values. collapse them to spaces.
   - Ensure the output is valid, parseable JSON.
5. **CRITICAL:** Preserve the original markdown header level. 
   - `# Heading` -> Level 1
   - `## Heading` -> Level 2
   - `### Heading` -> Level 3
   - Do NOT promote all headers to Level 1.
6. **NO HEADING NUMBERS:** Strip explicit numbers (like "1.1", "3.2.", "A.") from the beginning of heading strings. Provide only the text words of the heading.
7. **MATH SPACING:** Ensure there is a space before and after inline math ($x$). Do not squish words together like "Typeof $Steam$".
8. **TITLE-CONTENT COHERENCE:** The heading text MUST accurately describe the content that follows it. If 90% of the body text discusses "Heat Exchangers", the heading must NOT say "Diffuser". Always match the heading to the dominant topic of the section below it.
"""


async def structurer_node(text_chunk: str) -> dict:
    """Convert text chunk to structured JSON. Returns dict with error key on failure."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "ollama":
        model = "ollama/llama3"
    else:
        model = os.getenv("DEFAULT_MODEL", "gemini/gemini-2.0-flash")
        
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    # Validate input
    if not text_chunk or len(text_chunk.strip()) == 0:
        print("[Structurer] ⚠️ Empty chunk received")
        return {"error": "Empty chunk"}

    # Limit chunk size to avoid token limits (Gemini 2.0 Flash has ~1M context, but be safe)
    max_chunk_size = 500000  # ~500k chars
    if len(text_chunk) > max_chunk_size:
        print(
            f"[Structurer] ⚠️ Chunk too large ({len(text_chunk):,} chars), truncating..."
        )
        text_chunk = text_chunk[:max_chunk_size] + "\n\n[... truncated ...]"

    max_retries = 3
    base_delay = 2

    for attempt in range(max_retries):
        try:
            # Check API key for Gemini
            if model.startswith("gemini/") and not api_key:
                print("[Structurer] ❌ No API key for Gemini model")
                return {"error": "Missing GOOGLE_API_KEY"}

            response = await litellm.acompletion(
                model=model,
                timeout=300,  # 5 minutes timeout
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text_chunk},
                ],
                # A3: Force JSON-guaranteed output at the API level
                # Prevents all trailing-comma and missing-bracket crashes
                response_format={"type": "json_object"},
                api_key=api_key if model.startswith("gemini/") else None,
            )

            # Validate response
            if not response or not hasattr(response, "choices") or not response.choices:
                print(
                    f"[Structurer] ⚠️ Empty response (Attempt {attempt+1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                return {"error": "Empty response from LLM"}

            content = response.choices[0].message.content
            if not content:
                print(
                    f"[Structurer] ⚠️ Empty content (Attempt {attempt+1}/{max_retries})"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                return {"error": "Empty content in response"}

            # Try to parse JSON
            try:
                import re

                # Clean up common JSON issues
                content = content.strip()
                # Remove markdown code fences if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                # Replace single backslashes in JSON output with double backslashes
                # to prevent parse errors from LLM escaping output bugs
                content = re.sub(r'(?<!\\)\\(?![\\"/])', r"\\\\", content)

                parsed = json.loads(content)

                # Basic schema validation (O4)
                if isinstance(parsed, dict):
                    if "sections" not in parsed and "type" not in parsed:
                        print(
                            f"[Structurer] ⚠️ Missing 'type'/'sections' keys in response"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(base_delay * (attempt + 1))
                            continue

                # Post-processing to strip explicit heading numbers and fix formatting spaces
                def clean_json_node(node):
                    if isinstance(node, dict):
                        if node.get("type") == "heading" and "text" in node:
                            text = node.get("text")
                            if text:
                                # Strip things like "1.", "3.2.", "A." from the start
                                node["text"] = re.sub(
                                    r"^([A-Z0-9]+\.)+\s*", "", str(text)
                                ).strip()
                        elif node.get("type") == "paragraph" and "text" in node:
                            text = node.get("text")
                            if text:
                                # Ensure spaces around inline math to fix TOC missing space bugs
                                node["text"] = re.sub(
                                    r"([a-zA-Z])\$", r"\1 $", str(text)
                                )
                                node["text"] = re.sub(
                                    r"\$([a-zA-Z])", r"$ \1", node["text"]
                                )

                        for v in node.values():
                            clean_json_node(v)
                    elif isinstance(node, list):
                        for item in node:
                            clean_json_node(item)

                clean_json_node(parsed)

                return parsed
            except json.JSONDecodeError as json_err:
                print(
                    f"[Structurer] ⚠️ JSON parse error (Attempt {attempt+1}/{max_retries}): {json_err}"
                )
                print(f"   First 200 chars of response: {content[:200]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                return {
                    "error": f"JSON parse failed: {json_err}",
                    "raw_content": content[:500],
                }

        except Exception as e:
            error_msg = str(e)
            print(
                f"[Structurer] ⚠️ Error (Attempt {attempt+1}/{max_retries}): {error_msg}"
            )

            # Handle rate limits with exponential backoff
            if (
                "429" in error_msg
                or "rate limit" in error_msg.lower()
                or "RESOURCE_EXHAUSTED" in error_msg
            ):
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt) * 5  # 10s, 20s, 40s
                    print(f"   ⏳ Rate limit hit, waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    return {"error": f"Rate limit exceeded after {max_retries} retries"}

            # Handle authentication errors
            if "401" in error_msg or "authentication" in error_msg.lower():
                return {"error": "Authentication failed - check GOOGLE_API_KEY"}

            # Handle model not found
            if "404" in error_msg or "not found" in error_msg.lower():
                return {"error": f"Model not found: {model}"}

            # For other errors, retry with delay
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (attempt + 1))
                continue

            return {"error": error_msg}

    return {"error": f"Failed after {max_retries} retries"}


if __name__ == "__main__":
    # Test with a snippet relevant to "Page 6" / Example Problems
    test_chunk = r"""
    ## 2.2 Addressing Interference
    
    As the density of small cells increases, so does interference.
    
    \begin{exampleproblem}{Example Problem 1: Comparing Cell Density}
      \textbf{Problem Statement:} Calculate percent increase.
      \begin{solution}
        1. Initial: 1 cell/km2
        2. Final: 100 cell/km2
        $$ Increase = 9900\% $$
      \end{solution}
    \end{exampleproblem}
    """

    result = structurer_node(test_chunk)
    print(json.dumps(result, indent=2))
