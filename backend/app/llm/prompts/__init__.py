from functools import cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    """Loads backend/app/llm/prompts/<name>.md."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
