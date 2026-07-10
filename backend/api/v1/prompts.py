from fastapi import APIRouter
from pydantic import BaseModel

from backend.prompt_engine import ACTIONS

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptActionResponse(BaseModel):
    id: str
    label: str
    description: str
    icon: str


@router.get("/actions", response_model=list[PromptActionResponse])
async def list_actions() -> list[PromptActionResponse]:
    """Every AI action available in the AI Workspace. Adding a new one to
    backend/prompt_engine/registry.py is all that's needed for it to appear
    here — the frontend renders whatever this returns."""
    return [
        PromptActionResponse(id=a.id, label=a.label, description=a.description, icon=a.icon)
        for a in ACTIONS
    ]
