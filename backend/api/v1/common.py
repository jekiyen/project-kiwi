from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Shared shape for simple 'operation queued/triggered' endpoint responses."""
    message: str
