import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.agents.scan_agent import ScanAgent
from backend.api.v1 import applications, health, jobs, notifications, resumes, scans
from backend.config.settings import settings
from backend.config.validate import validate_settings
from backend.database.session import create_db_and_tables
from backend.logging_config import request_id_var, setup_logging
from backend.notifications import notification_service
from backend.scheduler.scheduler import register_agent, scheduler

logger = logging.getLogger("application")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(settings.log_level)
    validate_settings(settings)  # fail fast on critical misconfiguration
    create_db_and_tables()

    scan_agent = ScanAgent()
    register_agent(scan_agent)
    scheduler.start()

    for name, active in (await notification_service.provider_statuses()).items():
        logger.info("Notification provider '%s': %s", name, "ACTIVE" if active else "DISABLED")

    logger.info("Project Kiwi backend started (AI provider: %s)", settings.ai_provider)
    yield

    scheduler.shutdown(wait=False)
    logger.info("Project Kiwi backend stopped")


app = FastAPI(
    title="Project Kiwi API",
    description="Personal AI migration copilot for New Zealand",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # "localhost" and "127.0.0.1" are different origins to a browser even
    # though they resolve to the same machine — allow both so the dashboard
    # works regardless of which one the user's browser ends up using.
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Tags every request with a short ID (X-Request-ID) so its log lines can be
    correlated, and logs method/path/status/duration for every request."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
        token = request_id_var.set(req_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "%s %s -> %d (%dms)",
                request.method, request.url.path, response.status_code, duration_ms,
            )
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)


app.add_middleware(RequestIDMiddleware)


# ── Global error handling — consistent shape, never leak internals ────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "The request body or parameters were invalid.",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full detail (including traceback) goes to the server log only — the
    # client never sees anything beyond a generic message.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Something went wrong. Check the server logs for details.",
        },
    )


PREFIX = "/api/v1"
app.include_router(health.router, prefix=PREFIX)
app.include_router(jobs.router, prefix=PREFIX)
app.include_router(scans.router, prefix=PREFIX)
app.include_router(applications.router, prefix=PREFIX)
app.include_router(notifications.router, prefix=PREFIX)
app.include_router(resumes.router, prefix=PREFIX)
