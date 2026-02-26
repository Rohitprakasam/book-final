import regex as re
from typing import Dict, List, Any

def escape_typst(text: str) -> str:
    """
    Escapes Typst special characters in normal text.
    """
    if not text:
        return ""
    # Typst special chars: # $ * _ < > @ \ ` 
    # We only escape the ones likely to cause syntax errors in plain text.
    replacements = {
        "#": r"\#",
        "$": r"\$",
        "*": r"\*",
        "_": r"\_",
        "<": r"\<",
        ">": r"\>",
        "@": r"\@",
        "\\": r"\\",
        "`": r"\`",
        "~": r"\~",
    }
    escaped = "".join(replacements.get(c, c) for c in text)
    return escaped


def render_mixed_content_typst(text: str) -> str:
    r"""
    Splits text by inline math `$ ... $` or display math `$$ ... $$`
    Text parts are escaped. Math parts are kept as is and wrapped correctly.
    """
    if not text:
        return ""

    # Typst uses $...$ for both inline and display math. 
    # Display math is just $...$ with at least one space/newline inside the delimiters.
    # LLMs might still output $$...$$ for display math occasionally, so we handle both.
    pattern = r"(\$\$.*?\$\$|\$.*?\$)"
    parts = re.split(pattern, text, flags=re.DOTALL)
    typst_out = []

    for part in parts:
        if not part:
            continue

        if part.startswith("$$") and part.endswith("$$"):
            math_content = part[2:-2].strip()
            typst_out.append(f"$ {math_content} $")
        elif part.startswith("$") and part.endswith("$"):
            math_content = part[1:-1].strip()
            # If math content has no spaces, it's inline. If we want display, user normally spaces it.
            typst_out.append(f"${math_content}$")
        else:
            if part.strip():
                # Text node -> Escape it
                escaped = escape_typst(part)
                typst_out.append(escaped)
            else:
                # Preserve whitespace
                if part:
                    typst_out.append(part)

    return "".join(typst_out)


def render_paragraph_with_images(text: str) -> str:
    """
    Detects markdown image syntax `![alt](path)` inside a paragraph and
    converts it to Typst figure environments.
    """
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    out: List[str] = []
    last_end = 0

    for match in image_pattern.finditer(text):
        before = text[last_end : match.start()]
        if before.strip():
            out.append(escape_typst(before) + "\n\n")

        alt = match.group(1).strip()
        path = match.group(2).strip().replace("\\", "/")

        # Normalize path: strip leading /data/output/ if present
        path = re.sub(r"^/data/output/", "", path)
        
        caption = escape_typst(alt) if alt else ""

        if caption:
            figure_typst = f'#figure(image("{path}", width: 90%), caption: [{caption}])\n'
        else:
            figure_typst = f'#figure(image("{path}", width: 90%))\n'
            
        out.append(figure_typst)
        last_end = match.end()

    after = text[last_end:]
    if after.strip():
        out.append(escape_typst(after) + "\n\n")

    return "".join(out)


def render_section_typst(section: Dict[str, Any]) -> str:
    """
    Renders a single structure block into Typst syntax.
    """
    if not section:
        return ""
    stype = section.get("type")

    if stype == "heading":
        level = section.get("level", 1)
        text = render_mixed_content_typst(section.get("text", ""))
        
        # Typst uses = for headers (=, ==, ===)
        header_marker = "=" * level
        return f"{header_marker} {text}\n"

    elif stype == "paragraph":
        text = section.get("text", "")
        if "![" in text and "](" in text:
            rendered = render_paragraph_with_images(text)
            return rendered + "\n\n"

        text = render_mixed_content_typst(text)
        return f"{text}\n\n"

    elif stype == "equation":
        # Check if the math block already includes $ delimiters
        math_str = section.get("math", section.get("latex", ""))
        math_str = math_str.strip()
        
        if math_str.startswith("$$") and math_str.endswith("$$"):
            math_str = math_str[2:-2].strip()
            return f"$ {math_str} $\n\n"
        elif math_str.startswith("$") and math_str.endswith("$"):
            math_str = math_str[1:-1].strip()
            return f"$ {math_str} $\n\n"
        else:
            # Wrap unmarked math as display math
            return f"$ {math_str} $\n\n"

    elif stype == "example_problem":
        title = escape_typst(section.get("title", "Example Problem"))
        prob_stmt = render_mixed_content_typst(section.get("problem_statement", ""))
        steps = section.get("solution_steps") or []
        
        if prob_stmt.lower().startswith("problem statement:"):
            prob_stmt = prob_stmt[18:].strip()

        # Using custom Typst `#exampleproblem` function from template
        typst_out = [
            f'#exampleproblem(title: "{title}")[',
            f"  *Problem Statement:* {prob_stmt}",
            "",
            "  #solution[",
        ]

        for step in steps:
            for block in step:
                btype = block.get("type")
                if btype == "paragraph":
                    typst_out.append("    " + render_mixed_content_typst(block.get("text", "")))
                elif btype == "equation":
                    m_str = block.get("math", block.get("latex", "")).strip()
                    if m_str.startswith("$$") and m_str.endswith("$$"):
                        m_str = m_str[2:-2].strip()
                    elif m_str.startswith("$") and m_str.endswith("$"):
                        m_str = m_str[1:-1].strip()
                    typst_out.append(f"    $ {m_str} $")

        typst_out.append("  ]")
        typst_out.append("]\n")
        return "\n".join(typst_out)

    elif stype == "list":
        items = section.get("items") or []
        typst_out = []
        for item in items:
            item_str = item.get("text", "") if isinstance(item, dict) else str(item)
            item_text = render_mixed_content_typst(item_str)
            typst_out.append(f"- {item_text}")
        typst_out.append("") # Extra newline to close list
        return "\n".join(typst_out)

    return ""


def render_page_typst(chapter_structure: Dict[str, Any]) -> str:
    """
    Renders a full chapter from JSON structure to Typst text.
    """
    title = chapter_structure.get("title")
    sections = chapter_structure.get("sections") or []
    
    typst_parts = []

    # Handle Unit/Chapter titles
    if title:
        title_text = render_mixed_content_typst(title).strip()
        # Case 1: Unit Heading (e.g., "UNIT I")
        if "UNIT" in title_text.upper():
            import re
            m = re.search(r"UNIT\s+([IVXLCDM\d]+)", title_text.upper())
            if m:
                u_val = m.group(1)
                valid_units = ["1", "2", "3", "4", "5", "I", "II", "III", "IV", "V"]
                if u_val not in valid_units:
                    print(f"[Renderer] 🚫 Skipping {title_text} (Limit reached)")
                    return ""
            
            # Typst: Use a custom function or plain large heading
            typst_parts.append(f"#pagebreak()\n#align(center)[#text(size: 24pt, weight: \"bold\")[{title_text}]]\n#v(1cm)\n")
        else:
            # Case 2: Standard Chapter Title
            typst_parts.append(f"#pagebreak()\n= {title_text}\n")

    # Render sections
    for section in sections:
        typst_parts.append(render_section_typst(section))

    return "\n".join(typst_parts)


def sanitize_typst_output(typst_text: str) -> str:
    """
    Post-processing sanitizer for Typst output.
    Cleans up any LLM hallucinations or structural oddities.
    """
    import re
    # Strip Unicode that shouldn't be there or causes issues
    replacements = {
        "\u00a0": " ",  # Non-breaking space
        "\u200b": "",   # Zero-width space
        "```typst": "",
        "```": "",
    }
    for char, rep in replacements.items():
        typst_text = typst_text.replace(char, rep)
        
    return typst_text
