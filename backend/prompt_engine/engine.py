"""Prompt Engine — loads Markdown templates and substitutes runtime variables.

This is intentionally the only thing this module does: load a template file,
inject variables, return plain text. No AI calls, no API integrations, no
parsing of a response — Kiwi never talks to an AI provider directly. The
rendered text is meant to be copied by the user and pasted into Claude by
hand (see docs/ROADMAP.md Phase 7.4).
"""
import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class TemplateNotFoundError(Exception):
    pass


def render_template(template_file: str, variables: dict[str, str]) -> str:
    """Load a Markdown template and substitute every {{placeholder}}.

    A missing variable renders as a visible `[name not provided]` marker
    rather than raising or leaving a raw `{{name}}` — this is plain text
    generation for a human to read and edit, not a strict template language.
    Adding a new placeholder to a template never requires code changes here;
    it just needs to be present in the `variables` dict passed by the caller.
    """
    path = TEMPLATES_DIR / template_file
    if not path.exists():
        raise TemplateNotFoundError(f"Prompt template not found: {template_file}")
    raw = path.read_text(encoding="utf-8")

    def _substitute(match: re.Match) -> str:
        key = match.group(1)
        return str(variables[key]) if key in variables else f"[{key} not provided]"

    return _PLACEHOLDER_RE.sub(_substitute, raw)
