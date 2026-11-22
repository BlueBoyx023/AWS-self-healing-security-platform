import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATUS_FILE = PROJECT_ROOT / "documentation" / "project_status.json"
OUTPUT_FILE = PROJECT_ROOT / "docs" / "generated" / "documentation_inventory.md"

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
}


def load_project_status():
    with STATUS_FILE.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def discover_markdown_files():
    markdown_files = []

    for path in PROJECT_ROOT.rglob("*.md"):
        relative_path = path.relative_to(PROJECT_ROOT)

        if any(
            part in EXCLUDED_DIRECTORIES or part.startswith(".pytest-tmp")
            for part in relative_path.parts
        ):
            continue

        if relative_path == OUTPUT_FILE.relative_to(PROJECT_ROOT):
            continue

        markdown_files.append(path)

    return sorted(markdown_files)


def extract_headings(path):
    headings = []

    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return [f"Unable to read headings: {error}"]

    for line in content.splitlines():
        stripped = line.strip()

        if stripped.startswith("#"):
            headings.append(stripped)

    return headings


def generate_inventory():
    status = load_project_status()

    human_review = set(
        status["documentation"]["human_review_required"]
    )

    markdown_files = discover_markdown_files()

    lines = [
        "# Documentation Inventory",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Total Markdown documents: {len(markdown_files)}",
        "",
        "## Document Index",
        "",
        "| Document | Size (bytes) | Review requirement |",
        "|---|---:|---|",
    ]

    for path in markdown_files:
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        size = path.stat().st_size

        review_status = (
            "Human review required"
            if relative_path in human_review
            else "Standard"
        )

        lines.append(
            f"| `{relative_path}` | {size} | {review_status} |"
        )

    lines.extend(["", "## Document Headings", ""])

    for path in markdown_files:
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()

        lines.append(f"### `{relative_path}`")
        lines.append("")

        headings = extract_headings(path)

        if headings:
            lines.extend(f"- {heading}" for heading in headings)
        else:
            lines.append("- No Markdown headings found.")

        lines.append("")

    lines.extend([
        "---",
        "",
        "This inventory is automatically generated.",
        "Manually maintained source documents are not modified.",
        "",
    ])

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = OUTPUT_FILE.with_suffix(".md.tmp")

    temporary_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    temporary_file.replace(OUTPUT_FILE)

    print("===== DOCUMENTATION INVENTORY GENERATED =====")
    print(f"Documents discovered: {len(markdown_files)}")
    print(f"Human-review documents: {len(human_review)}")
    print(
        f"Output: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    generate_inventory()
