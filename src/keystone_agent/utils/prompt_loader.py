"""Prompt loading utilities with philosophy and date injection."""

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

# Base path for prompts (inside the package)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"


@lru_cache(maxsize=1)
def load_philosophy() -> str:
    """
    Load the company philosophy from docs/PHILOSOPHY.md.

    Returns:
        The philosophy text, or a default placeholder if not found.
    """
    philosophy_path = DOCS_DIR / "PHILOSOPHY.md"

    if not philosophy_path.exists():
        return (
            "Focus on shipping fast, validating with real users, "
            "and cutting scope ruthlessly. Time is the only non-renewable resource."
        )

    content = philosophy_path.read_text()

    # Extract content after the title (skip first line if it's a header)
    lines = content.split("\n")
    philosophy_lines = []
    skip_header = True

    for line in lines:
        # Skip the first header
        if skip_header and line.startswith("#"):
            skip_header = False
            continue

        # Include everything else
        philosophy_lines.append(line)

    philosophy = "\n".join(philosophy_lines).strip()

    # If we didn't extract anything useful, return default
    if len(philosophy) < 50:
        return (
            "Focus on shipping fast, validating with real users, "
            "and cutting scope ruthlessly. Time is the only non-renewable resource."
        )

    return philosophy


def get_current_date_context() -> str:
    """Get current date context for prompt injection."""
    now = datetime.now(timezone.utc)
    return f"""**Current Date:** {now.strftime("%B %d, %Y")} ({now.strftime("%A")})
**Time:** {now.strftime("%H:%M")} UTC"""


def load_prompt(agent_name: str) -> str:
    """
    Load a prompt file and inject company philosophy and current date.

    Args:
        agent_name: Name of the agent (e.g., 'orchestrator', 'product_operator')

    Returns:
        The prompt with philosophy and date injected

    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / f"{agent_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text()

    # Inject philosophy
    philosophy = load_philosophy()
    content = content.replace("{PHILOSOPHY_PLACEHOLDER}", philosophy)

    # Inject current date context at the beginning (after the first header)
    date_context = get_current_date_context()

    # Find the first --- separator and insert date context after it
    if "---" in content:
        parts = content.split("---", 2)
        if len(parts) >= 2:
            content = f"{parts[0]}---\n\n{date_context}\n\n---{parts[2] if len(parts) > 2 else ''}"
    else:
        # No separator, add at the beginning after first line
        lines = content.split("\n", 1)
        content = f"{lines[0]}\n\n{date_context}\n\n{lines[1] if len(lines) > 1 else ''}"

    return content


def get_available_prompts() -> list[str]:
    """Get list of available prompt names."""
    if not PROMPTS_DIR.exists():
        return []

    return [p.stem for p in PROMPTS_DIR.glob("*.md")]
