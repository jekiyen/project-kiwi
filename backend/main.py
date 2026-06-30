import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.scan_agent import ScanAgent
from backend.api.v1 import applications, health, jobs, notifications, scans
from backend.config.settings import settings
from backend.database.session import create_db_and_tables
from backend.logging_config import setup_logging
from backend.scheduler.scheduler import register_agent, scheduler

logger = logging.getLogger("application")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(settings.log_level)
    create_db_and_tables()

    scan_agent = ScanAgent()
    register_agent(scan_agent)
    scheduler.start()

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
    allow_origins=[f"http://localhost:{settings.frontend_port}"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"
app.include_router(health.router, prefix=PREFIX)
app.include_router(jobs.router, prefix=PREFIX)
app.include_router(scans.router, prefix=PREFIX)
app.include_router(applications.router, prefix=PREFIX)
app.include_router(notifications.router, prefix=PREFIX)
