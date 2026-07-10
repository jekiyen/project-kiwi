from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.timezone import now_local
from backend.database.session import engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service="Project Kiwi",
        version="1.0.0",
        timestamp=now_local().isoformat(),
        database="ok" if db_ok else "unreachable",
    )
