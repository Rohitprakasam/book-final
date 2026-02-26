import json
import re
from pathlib import Path


def run_qa_check(structure_path: str, output_dir: str):
    """
    Validates the structured JSON and image assets.
    Reports issues to the terminal without raising exceptions (No retries).
    """
    print("\n" + "═" * 58)
    print("🔎  PHASE 5 — THE QUALITY ASSURANCE CHECKER")
    print("═" * 58)

    struct_file = Path(structure_path)
    if not struct_file.exists():
        print(f"❌ QA FAILED: {struct_file.name} not found.")
        return

    try:
        with open(struct_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ QA FAILED: Could not decode JSON. {e}")
        return

    # Metrics
    metrics = {
        "chapters": 0,
        "headings": 0,
        "paragraphs": 0,
        "equations": 0,
        "lists": 0,
        "example_problems": 0,
        "images_valid": 0,
        "images_missing": 0,
        "unresolved_tags": 0,
    }

    missing_images = []
    unresolved_list = []

    def check_node(node):
        if not isinstance(node, dict):
            return

        n_type = node.get("type", "")
        if n_type == "chapter":
            metrics["chapters"] += 1
        elif n_type == "heading":
            metrics["headings"] += 1
        elif n_type == "paragraph":
            metrics["paragraphs"] += 1
            text = node.get("text", "")

            # Check for unresolved tags
            if "[NEW_DIAGRAM:" in text or "[ORIGINAL_ASSET:" in text:
                metrics["unresolved_tags"] += 1
                unresolved_list.append(text[:50].replace("\n", " ") + "...")

            # Check for valid image paths: ![alt](path)
            # Standard markdown image regex
            img_matches = re.finditer(r"!\[.*?\]\((.*?)\)", text)
            for m in img_matches:
                img_path = m.group(1).split(" ")[
                    0
                ]  # in case of bounds like (img.png "title")
                # Remove leading slashes/backslashes depending on OS, or treat as relative

                # Check root relative to base dir or output dir
                # If path starts with /data/output, strip it
                clean_path = re.sub(r"^/?data/output/", "", img_path)
                full_path = Path(output_dir) / clean_path

                if full_path.exists():
                    metrics["images_valid"] += 1
                else:
                    metrics["images_missing"] += 1
                    missing_images.append(clean_path)

        elif n_type == "equation":
            metrics["equations"] += 1
            # Check basic math integrity (just checking it's not empty)
            if not node.get("latex", "").strip():
                print("   ⚠️ Warning: Found empty equation string.")
        elif n_type == "example_problem":
            metrics["example_problems"] += 1
        elif n_type == "list":
            metrics["lists"] += 1

        # Recurse
        for value in node.values():
            if isinstance(value, dict):
                check_node(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        check_node(item)

    # Walk the tree
    check_node(data)

    # ── Report Generation ──
    print(f"📊 STRUCTURE METRICS:")
    print(f"   Chapters: {metrics['chapters']}")
    print(f"   Headings: {metrics['headings']}")
    print(f"   Paragraphs: {metrics['paragraphs']}")
    print(f"   Equations: {metrics['equations']}")
    print(f"   Example Problems: {metrics['example_problems']}")
    print(f"   Lists: {metrics['lists']}")

    print(f"\n🖼️  ASSET METRICS:")
    print(f"   Valid Images: {metrics['images_valid']}")

    if metrics["images_missing"] > 0:
        print(f"   ❌ Missing Images: {metrics['images_missing']}")
        for m in missing_images[:5]:
            print(f"      - {m}")
        if len(missing_images) > 5:
            print(f"      ...and {len(missing_images) - 5} more.")
    else:
        print(f"   ✅ All referenced images exist on disk.")

    if metrics["unresolved_tags"] > 0:
        print(f"   ❌ Unresolved Tags: {metrics['unresolved_tags']}")
        for tag in unresolved_list[:5]:
            print(f"      - {tag}")
    else:
        print(f"   ✅ All BookUdecate tags resolved.")

    print("═" * 58 + "\n")
