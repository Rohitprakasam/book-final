import regex as re
from typing import Dict, List, Any


def escape_latex(text: str) -> str:
    """
    Escapes LaTeX special characters in normal text.
    NOTE: We intentionally do NOT escape { and } because the text may
    contain legitimate LaTeX commands (e.g. \frac{a}{b}).
    """
    if not text:
        return ""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "²": r"$^2$",
        "³": r"$^3$",
        "°": r"$^\circ$",
        "—": r"---",
        "–": r"--",
        "≤": r"$\le$",
        "≥": r"$\ge$",
        "×": r"$\times$",
        "⋅": r"$\cdot$",
        "→": r"$\rightarrow$",
        "←": r"$\leftarrow$",
        "↑": r"$\uparrow$",
        "↓": r"$\downarrow$",
        "∞": r"$\infty$",
        "∑": r"$\sum$",
        "∏": r"$\prod$",
        "∫": r"$\int$",
        "∂": r"$\partial$",
        "√": r"$\sqrt{}$",
        "α": r"$\alpha$",
        "β": r"$\beta$",
        "γ": r"$\gamma$",
        "δ": r"$\delta$",
        "η": r"$\eta$",
        "θ": r"$\theta$",
        "μ": r"$\mu$",
        "π": r"$\pi$",
        "ρ": r"$\rho$",
        "σ": r"$\sigma$",
        "τ": r"$\tau$",
        "φ": r"$\phi$",
        "ψ": r"$\psi$",
        "ω": r"$\omega$",
        "Δ": r"$\Delta$",
        "Σ": r"$\Sigma$",
        "Ω": r"$\Omega$",
    }
    escaped = "".join(replacements.get(c, c) for c in text)
    # Neutralize rogue list items that the LLM hallucinated outside of list environments
    escaped = escaped.replace(r"\item", r"\textbullet{} ")
    return escaped


# B5: Index Optimizer — Strip 90% of \index{} tags to save ~10 min per xelatex pass.
# Only keep tags for these core academic terms (customise per subject).
_CORE_INDEX_TERMS = {
    # Thermodynamics & Fluid
    "entropy",
    "enthalpy",
    "thermodynamics",
    "heat transfer",
    "combustion",
    "pressure",
    "temperature",
    "energy",
    "work",
    "efficiency",
    "cycle",
    "turbine",
    "compressor",
    "pump",
    "nozzle",
    "diffuser",
    "bernoulli",
    # Engineering general
    "stress",
    "strain",
    "force",
    "torque",
    "moment",
    "velocity",
    "acceleration",
    "momentum",
    "newton",
    "coulomb",
    "ohm",
    "pascal",
    "joule",
    "watt",
    # Math
    "differential equation",
    "integral",
    "derivative",
    "matrix",
    "vector",
    "eigenvalue",
    "fourier",
    "laplace",
    "calculus",
}


def prune_index_tags(latex: str) -> str:
    """B5: Strip \\index{} tags not in the core term whitelist."""

    def keep_tag(m):
        term = m.group(1).lower().strip()
        return m.group(0) if any(core in term for core in _CORE_INDEX_TERMS) else ""

    return re.sub(r"\\index\{([^}]+)\}", keep_tag, latex)


# E2: Security — Strip dangerous LaTeX shell-escape commands.
# Previously allowed relative paths like \input{../../etc/passwd}, now blocks ALL inclusions.
_DANGEROUS_LATEX = re.compile(
    r"\\(write18|immediate\\write18|input|include|openin|openout|read|write)\b",
    re.IGNORECASE,
)


def sanitize_latex_commands(latex: str) -> str:
    """E2: Remove dangerous LaTeX commands that could trigger shell execution."""
    sanitised = _DANGEROUS_LATEX.sub(r"% [BLOCKED: \\g<1>]", latex)
    return sanitised


def sanitize_for_zero_errors(latex: str) -> str:
    """
    Master zero-error sanitizer. Fixes ALL known xelatex crash patterns.
    Run this as the LAST step before writing the .tex file.
    """
    # 1. Fix orphan \\right without matching \\left (causes "Extra \\right" crash)
    # Wrap orphan \\right in \\left. pairs
    latex = re.sub(r"(?<!\\left[\s\S]{0,20})\\right\s*([)}\]|.])", r"\\right\1", latex)

    # 2. Fix \\eqno in math mode (causes "You can't use \\eqno in math mode")
    latex = re.sub(r"\\eqno\b", "", latex)

    # 3. Fix \\textasciicircum inside math mode (causes "Command invalid in math mode")
    # Replace with ^ when inside $ ... $ or \[ \]
    latex = re.sub(r"\\textasciicircum\s*\{\}", r"^", latex)
    latex = re.sub(r"\\textasciicircum\b", r"^", latex)

    # 4. Fix \\item outside of list environments
    # If \item appears outside itemize/enumerate/description, replace with bullet
    lines = latex.split("\n")
    in_list = 0
    cleaned = []
    for line in lines:
        if re.search(r"\\begin\{(itemize|enumerate|description)\}", line):
            in_list += 1
        if re.search(r"\\end\{(itemize|enumerate|description)\}", line):
            in_list = max(0, in_list - 1)
        if in_list == 0 and "\\item" in line:
            line = line.replace("\\item", "\\textbullet{}")
        cleaned.append(line)
    latex = "\n".join(cleaned)

    # 5. Fix \\begin{X} ended by \\end{Y} (mismatched environments)
    # Common: \begin{equation} ended by \end{solution} or vice versa
    # Handle multiple \begin/\end per line using findall
    env_stack = []
    out_lines = []
    for line in latex.split("\n"):
        # Process all \begin{} on this line
        for m in re.finditer(r"\\begin\{(\w+)\}", line):
            env_stack.append(m.group(1))
        # Process all \end{} on this line
        for m in re.finditer(r"\\end\{(\w+)\}", line):
            end_env = m.group(1)
            if env_stack and env_stack[-1] == end_env:
                env_stack.pop()
            elif env_stack:
                # Mismatch! Close the actual open env instead
                actual = env_stack.pop()
                line = line.replace(f"\\end{{{end_env}}}", f"\\end{{{actual}}}", 1)

        out_lines.append(line)
    latex = "\n".join(out_lines)

    # 6. Strip Unicode characters that even the template can't handle
    # These cause "Missing character" warnings — replace with safe equivalents
    additional_unicode = {
        "₀": "$_0$",
        "₁": "$_1$",
        "₂": "$_2$",
        "₃": "$_3$",
        "₄": "$_4$",
        "₅": "$_5$",
        "₆": "$_6$",
        "₇": "$_7$",
        "₈": "$_8$",
        "₉": "$_9$",
        "⁰": "$^0$",
        "⁴": "$^4$",
        "⁵": "$^5$",
        "⁻": "$^-$",
        "Θ": "$\\Theta$",
        "Δ": "$\\Delta$",
        "Σ": "$\\Sigma$",
        "λ": "$\\lambda$",
        "ε": "$\\varepsilon$",
        "≈": "$\\approx$",
        "≠": "$\\neq$",
        "·": "$\\cdot$",
        "⋅": "$\\cdot$",
        "′": "'",
        "″": "''",
        "…": "...",
        "\u00a0": " ",  # Non-breaking space
        "\u200b": "",  # Zero-width space
        "\u2013": "--",  # En dash
        "\u2014": "---",  # Em dash
        "\u2018": "`",  # Left single quote
        "\u2019": "'",  # Right single quote
        "\u201c": "``",  # Left double quote
        "\u201d": "''",  # Right double quote
    }
    for char, replacement in additional_unicode.items():
        latex = latex.replace(char, replacement)

    # 7. Fix double $$ that creates empty display math (causes warnings)
    latex = re.sub(r"\$\$\s*\$\$", "", latex)

    # 8. Fix markdown bold ** that leaked into LaTeX (stay within line)
    latex = re.sub(r"\*\*([^\*\n]+?)\*\*", r"\\textbf{\1}", latex)

    # 9. Fix markdown italic * that leaked into LaTeX (stay within line, avoid command *)
    latex = re.sub(r"(?<![a-zA-Z\\])\*([^\*\n]+?)\*(?![a-zA-Z])", r"\\textit{\1}", latex)

    # 10. Strip any remaining ``` code fences
    latex = re.sub(r"```\w*\n?", "", latex)

    # 11. Fix "Double superscript" errors — a^b^c → a^{bc}
    latex = re.sub(r"\^(\w)\^(\w)", r"^{\1\2}", latex)

    # 12. Fix "Double subscript" errors — a_b_c → a_{bc}
    latex = re.sub(r"_(\w)_(\w)", r"_{\1\2}", latex)

    return latex


def generate_index_tags(latex: str) -> str:
    """
    Auto-generate \\index{} entries for each \\chapter{} and \\part{} heading.
    This produces a short index (Units + Chapters only) that fits in ~3 pages.

    For every \\chapter{Title Here}, inserts \\index{Title Here} right after.
    For every \\part{Unit X}, inserts \\index{Unit X} right after.
    """

    def _add_index_after_heading(match):
        full = match.group(0)
        cmd = match.group(1)  # 'chapter' or 'part'
        title = match.group(2)  # The heading text

        # Clean title for index: strip LaTeX commands, keep plain text
        clean_title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)  # \textbf{X} → X
        clean_title = re.sub(r"[\\${}]", "", clean_title).strip()  # Strip remaining

        if not clean_title or len(clean_title) < 2:
            return full  # Skip empty/trivial titles

        # Truncate very long titles for the index
        if len(clean_title) > 60:
            clean_title = clean_title[:57] + "..."

        return f"{full}\n\\index{{{clean_title}|topicindex}}"

    # Match \chapter{...}, \chapter*{...}, \part{...}, and \part*{...} headings
    latex = re.sub(r"\\(chapter|part)\*?\{([^}]+)\}", _add_index_after_heading, latex)

    count = latex.count("\\index{")
    print(f"[Index] 📑 Generated {count} index entries (Units + Chapters only)")
    return latex


def strip_empty_pages(latex: str) -> str:
    """
    Remove empty chapters/sections that produce blank pages.

    Targets:
    1. \\chapter{Title} followed immediately by another \\chapter{} (no content between)
    2. \\section{Title} followed immediately by another \\section{} or \\chapter{} (no content)
    3. Standalone headings with only whitespace after them
    """
    # Pattern 1: Chapter with no content before next chapter
    # \chapter{A}\n\n\chapter{B} → keep only \chapter{B}
    latex = re.sub(r"\\chapter\{([^}]+)\}\s*\n\s*\\chapter\{", r"\\chapter{", latex)

    # Pattern 2: Section with no content before next section/chapter
    latex = re.sub(
        r"\\section\{([^}]+)\}\s*\n\s*\\(section|chapter)\{", r"\\\2{", latex
    )

    # Pattern 3: Subsection with no content before next heading
    latex = re.sub(
        r"\\subsection\{([^}]+)\}\s*\n\s*\\(subsection|section|chapter)\{",
        r"\\\2{",
        latex,
    )

    # Pattern 4: Remove pages that are ONLY a chapter heading + whitespace
    # (chapter heading followed by only \n until next \chapter or \end)

    return latex


def auto_balance_braces(text: str) -> str:
    """
    Ensures that curly braces {} are balanced. If the LLM generated an unclosed
    bracket inside a block (e.g. `\text{`), this appends `}` to prevent Emergency Stops.
    If it generated an extra closing brace, this prepends `{` to prevent fatal group errors.
    """
    if not text:
        return ""
    open_braces = text.count("{") - text.count(r"\{")
    close_braces = text.count("}") - text.count(r"\}")
    net_braces = open_braces - close_braces
    if net_braces > 0:
        return text + "}" * net_braces
    elif net_braces < 0:
        return "{" * (-net_braces) + text
    return text


def render_mixed_content_latex(text: str) -> str:
    r"""
    Splits text by $$ ... $$, $ ... $, \[ ... \], \( ... \), and \begin{math_env} ... \end{math_env} blocks.
    - Text parts are escaped.
    - Math parts are kept as is (or wrapped appropriately).
    """
    if not text:
        return ""

    envs = r"equation|equation\*|align|align\*|eqnarray|eqnarray\*|cases|pmatrix|bmatrix|vmatrix|math|displaymath"
    pattern = rf"(\$\$.*?\$\$|\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\)|\\begin\{{(?:{envs})\}}[\s\S]*?\\end\{{(?:{envs})\}})"
    parts = re.split(pattern, text, flags=re.DOTALL)
    latex_out = []

    for part in parts:
        if not part:
            continue

        if part.startswith("$$") and part.endswith("$$"):
            # Display math: $$ ... $$
            math_content = part[2:-2].strip()
            if math_content.endswith("\\"):
                math_content = math_content[:-1].strip()
            latex_out.append(f"\\[ {math_content} \\]")
        elif part.startswith("$") and part.endswith("$"):
            # Inline math: $ ... $
            math_content = part[1:-1].strip()
            if math_content.endswith("\\"):
                math_content = math_content[:-1].strip()
            latex_out.append(f"\\( {math_content} \\)")
        elif part.startswith(r"\[") and part.endswith(r"\]"):
            # Display math: \[ ... \]
            math_content = part[2:-2].strip()
            if math_content.endswith("\\"):
                math_content = math_content[:-1].strip()
            latex_out.append(f"\\[ {math_content} \\]")
        elif part.startswith(r"\(") and part.endswith(r"\)"):
            # Inline math: \( ... \)
            math_content = part[2:-2].strip()
            if math_content.endswith("\\"):
                math_content = math_content[:-1].strip()
            latex_out.append(f"\\( {math_content} \\)")
        elif part.startswith(r"\begin{"):
            # Raw LaTeX math environment inside paragraph -> Pass through untouched
            latex_out.append(part)
        else:
            if part.strip():
                # Text node -> Escape it
                escaped = escape_latex(part)
                # Neutralize stray math delimiters that would force LaTeX into math mode
                # Only neutralize standalone \( \) \[ \] NOT preceded by another backslash
                escaped = re.sub(r'(?<!\\)\\\(', '( ', escaped)
                escaped = re.sub(r'(?<!\\)\\\)', ' )', escaped)
                escaped = re.sub(r'(?<!\\)\\\[', '[ ', escaped)
                escaped = re.sub(r'(?<!\\)\\\]', ' ]', escaped)
                # Neutralize orphan $ signs that leaked into text segments
                escaped = escaped.replace('$', r'\$')
                latex_out.append(escaped)
            else:
                # Preserve whitespace if strictly needed
                if part:
                    latex_out.append(" ")

    final_out = "".join(latex_out)
    # Neutralize orphaned backslashes caused by LLMs writing \$...\$ markdown math
    final_out = final_out.replace(r"\\(", r"\(")
    final_out = final_out.replace(r"\\\[", r"\[")
    return final_out


def render_paragraph_with_images(text: str) -> str:
    """
    Detects markdown image syntax `![alt](path)` inside a paragraph and
    converts it to LaTeX figure environments, preserving surrounding text.

    This ensures images from the Art Department render correctly in LaTeX.
    """
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    out: List[str] = []
    last_end = 0

    for match in image_pattern.finditer(text):
        # Text before the image
        before = text[last_end : match.start()]
        if before.strip():
            out.append(escape_latex(before) + "\n\n")

        alt = match.group(1).strip()
        path = match.group(2).strip().replace("\\", "/")

        # Normalize path for LaTeX: strip leading /data/output/ if present
        path = re.sub(r"^/data/output/", "", path)

        caption = escape_latex(alt) if alt else ""

        figure_latex = (
            "\\begin{figure}[h]\n"
            "\\centering\n"
            f"\\includegraphics[width=0.9\\textwidth]{{{path}}}\n"
            f"\\caption{{{caption}}}\n"
            "\\end{figure}\n"
        )
        out.append(figure_latex)

        last_end = match.end()

    # Any remaining text after the last image
    after = text[last_end:]
    if after.strip():
        out.append(escape_latex(after) + "\n\n")

    return "".join(out)


def render_section_latex(section: Dict[str, Any]) -> str:
    """
    Renders a single structure block into LaTeX.
    """
    if not section:
        return ""
    stype = section.get("type")

    if stype == "heading":
        level = section.get("level", 1)
        text = auto_balance_braces(render_mixed_content_latex(section.get("text", "")))
        if level == 1:
            return f"\\chapter*{{{text}}}\n\\addcontentsline{{toc}}{{chapter}}{{{text}}}\n"
        elif level == 2:
            return f"\\section*{{{text}}}\n\\addcontentsline{{toc}}{{section}}{{{text}}}\n"
        elif level == 3:
            return f"\\subsection*{{{text}}}\n\\addcontentsline{{toc}}{{subsection}}{{{text}}}\n"
        elif level >= 4:
            return f"\\subsubsection*{{{text}}}\n"

    elif stype == "paragraph":
        text = section.get("text", "")
        if "![" in text and "](" in text:
            rendered = render_paragraph_with_images(text)
            return auto_balance_braces(rendered) + "\n\n"

        text = auto_balance_braces(render_mixed_content_latex(text))
        return f"{text}\n\n"

    elif stype == "equation":
        latex = auto_balance_braces(section.get("latex", ""))
        return f"\\begin{{equation}}\n{latex}\n\\end{{equation}}\n"

    elif stype == "example_problem":
        title = auto_balance_braces(
            escape_latex(section.get("title", "Example Problem"))
        )
        prob_stmt = auto_balance_braces(
            render_mixed_content_latex(section.get("problem_statement", ""))
        )
        steps = section.get("solution_steps") or []
        # Clean up repetitive prefix if the LLM auto-generated it
        if prob_stmt.lower().startswith("problem statement:"):
            prob_stmt = prob_stmt[18:].strip()

        # Using standard breakable environment defined in template
        latex = [
            f"\\begin{{exampleproblem}}[{title}]",
            f"\\textbf{{Problem Statement:}} {prob_stmt}",
            "",
            "\\begin{solution}",
        ]

        for step in steps:
            for block in step:
                # blocks inside steps are just paragraphs or equations
                btype = block.get("type")
                if btype == "paragraph":
                    latex.append(
                        auto_balance_braces(
                            render_mixed_content_latex(block.get("text", ""))
                        )
                    )
                elif btype == "equation":
                    eq_latex = auto_balance_braces(block.get("latex", ""))
                    latex.append(f"\\begin{{equation}}\n{eq_latex}\n\\end{{equation}}")

        latex.append("\\end{solution}")
        latex.append("\\end{exampleproblem}\n")
        return "\n".join(latex)

    elif stype == "list":
        items = section.get("items") or []
        latex = ["\\begin{itemize}"]
        for item in items:
            if isinstance(item, dict):
                item_str = item.get("text", "")
            else:
                item_str = str(item)
            item_text = auto_balance_braces(render_mixed_content_latex(item_str))
            latex.append(f"  \\item {item_text}")
        latex.append("\\end{itemize}\n")
        return "\n".join(latex)

    return ""


def render_page_latex(chapter_structure: Dict[str, Any]) -> str:
    """
    Renders a full chapter from JSON structure to LaTeX body.
    """
    title = chapter_structure.get("title")
    sections = chapter_structure.get("sections") or []
    
    latex_parts = []

    # Handle Unit/Chapter titles
    if title:
        title_text = render_mixed_content_latex(title).strip()
        # Case 1: Unit Heading (e.g., "UNIT I", "UNIT 1")
        if "UNIT" in title_text.upper():
            # Extract unit number for filtering if possible
            import re
            m = re.search(r"UNIT\s+([IVXLCDM\d]+)", title_text.upper())
            if m:
                u_val = m.group(1)
                # Filter: only units 1-5 (I-V)
                valid_units = ["1", "2", "3", "4", "5", "I", "II", "III", "IV", "V"]
                if u_val not in valid_units:
                    print(f"[Renderer] 🚫 Skipping {title_text} (Limit reached)")
                    return ""
            
            latex_parts.append(f"\\part{{{title_text}}}\n")
        else:
            # Case 2: Standard Chapter Title (Unnumbered)
            latex_parts.append(f"\\chapter*{{{title_text}}}\n")
            latex_parts.append(f"\\addcontentsline{{toc}}{{chapter}}{{{title_text}}}\n")

    # Render sections
    for section in sections:
        latex_parts.append(render_section_latex(section))

    return "\n".join(latex_parts)


# ──────────────────────────────────────────────
# POST-PROCESSING SANITIZERS (BookUdecate 8.0)
# ──────────────────────────────────────────────


def strip_leaked_scaffolding(latex: str) -> str:
    """
    Fault #2 fix: Remove raw template labels that leaked outside of
    \\begin{exampleproblem}/\\begin{solution} environments.

    Targets: standalone "Problem Statement:", "Solution:", "Solve for X:" lines
    that are NOT inside an exampleproblem/solution block.
    """
    import re

    # Remove standalone "Problem Statement:" / "Solution:" lines that appear
    # outside of exampleproblem environments (i.e., preceded by blank line or start)
    # We keep them if they're inside \\textbf{} (that's the expected format)

    # Strip bare "Problem Statement:" not inside \\textbf{}
    latex = re.sub(r"(?<!\\textbf\{)(?<!\{)\bProblem\s+Statement\s*:\s*", "", latex)

    # Strip bare "Solution:" on its own line (not inside \\begin{solution})
    latex = re.sub(r"^Solution\s*:\s*$", "", latex, flags=re.MULTILINE)

    # Strip "Solve for X:" / "Calculate the Y:" patterns on bare lines
    latex = re.sub(
        r"^\s*(Solve for|Calculate the|Find the|Determine the)\s+[^:]+:\s*$",
        "",
        latex,
        flags=re.MULTILINE,
    )

    # Clean up triple+ newlines left by removals
    latex = re.sub(r"\n{3,}", "\n\n", latex)

    return latex


def normalize_scientific_notation(latex: str) -> str:
    """
    Fault #5 fix: Convert trivial scientific notation to plain numbers.

    2.00 × 10⁰ → 2       (×10^0 = 1)
    3.00 × 10¹ → 30       (×10^1 = 10)
    1.00 × 10² → 100      (×10^2 = 100)

    Only normalizes when the result is a "simple" number (≤ 9999).
    Leaves legitimate sci-notation (10⁵, 10⁻³, etc.) untouched.
    """
    import re

    # Pattern: X.XX × 10^N where N is 0, 1, or 2 (superscript Unicode)
    superscript_map = {"⁰": 0, "¹": 1, "²": 2, "³": 3, "⁴": 4}

    def _replace_unicode_sci(match):
        coeff = float(match.group(1))
        exp_char = match.group(2)
        exp = superscript_map.get(exp_char, None)
        if exp is None or exp > 4:
            return match.group(0)  # Leave untouched
        result = coeff * (10**exp)
        if result == int(result) and result <= 9999:
            return str(int(result))
        elif result <= 9999:
            return f"{result:.2f}".rstrip("0").rstrip(".")
        return match.group(0)

    # Unicode superscript pattern: "2.00 × 10⁰", "1.50 × 10²"
    latex = re.sub(
        r"(\d+\.?\d*)\s*[×x\\times]\s*10([⁰¹²³⁴])", _replace_unicode_sci, latex
    )

    # LaTeX pattern: "2.00 \times 10^{0}", "1.50 \times 10^{2}"
    def _replace_latex_sci(match):
        coeff = float(match.group(1))
        exp = int(match.group(2))
        if exp < 0 or exp > 4:
            return match.group(0)
        result = coeff * (10**exp)
        if result == int(result) and result <= 9999:
            return str(int(result))
        elif result <= 9999:
            return f"{result:.2f}".rstrip("0").rstrip(".")
        return match.group(0)

    latex = re.sub(
        r"(\d+\.?\d*)\s*\\times\s*10\^\{([0-4])\}", _replace_latex_sci, latex
    )

    return latex


def strip_empty_tables(latex: str) -> str:
    """
    Fault #6 fix: Remove tabular environments that have a header row
    but zero data rows (empty stubs).
    """
    import re

    def _is_empty_table(match):
        table_body = match.group(0)
        # Count non-header rows by splitting on \\. 
        # Do not require "&" as single-column tables are valid.
        # Filter out purely structural lines
        rows = [
            line.strip()
            for line in table_body.split("\\\\")
            if line.strip() and not re.search(r"\\(?:hline|toprule|midrule|bottomrule)\b", line)
        ]
        # If there's only 0 or 1 row (just the header), it's empty
        if len(rows) <= 1:
            return ""  # Strip the entire empty table
        return table_body  # Keep non-empty tables

    latex = re.sub(
        r"\\begin\{tabular\}[^}]*\}.*?\\end\{tabular\}",
        _is_empty_table,
        latex,
        flags=re.DOTALL,
    )

    return latex
