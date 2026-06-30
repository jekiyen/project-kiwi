from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "Project Kiwi",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
