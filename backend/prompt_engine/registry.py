"""Registry of AI actions available in the AI Workspace, loaded from a
configuration file so that adding a new AI workflow never requires touching
Python code.

Adding a new AI workflow to Kiwi only ever requires two steps:
1. Create a new Markdown template in backend/prompt_engine/templates/.
2. Add one entry to backend/prompt_engine/actions.json.

Nothing else — not this file, not the frontend, not the API route — needs
to change to add a new action. The frontend renders whatever this registry
returns.
"""
import json
from dataclasses import dataclass
from pathlib import Path

ACTIONS_CONFIG_FILE = Path(__file__).parent / "actions.json"


@dataclass(frozen=True)
class PromptAction:
    id: str
    label: str
    description: str
    template_file: str
    icon: str = "✨"


def _load_actions() -> list[PromptAction]:
    raw = json.loads(ACTIONS_CONFIG_FILE.read_text(encoding="utf-8"))
    return [PromptAction(**entry) for entry in raw]


ACTIONS: list[PromptAction] = _load_actions()
_BY_ID = {action.id: action for action in ACTIONS}


def get_action(action_id: str) -> PromptAction | None:
    return _BY_ID.get(action_id)
