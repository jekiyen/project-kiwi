import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.agents.base import BaseAgent
from backend.core.timezone import APP_TZ

logger = logging.getLogger("application")

scheduler = AsyncIOScheduler(
    timezone=APP_TZ,
    job_defaults={
        # A slow scan must finish (or be skipped) before the next interval
        # fires again — never run two instances of the same job concurrently.
        "max_instances": 1,
        "coalesce": True,
        "misfire_grace_time": 60,
    },
)


def register_agent(agent: BaseAgent) -> None:
    """Register an agent with the scheduler if it defines a schedule interval."""
    if agent.schedule_interval_hours is None:
        return
    scheduler.add_job(
        agent.run,
        trigger="interval",
        hours=agent.schedule_interval_hours,
        id=agent.name,
        replace_existing=True,
    )
    logger.info(f"Agent '{agent.name}' scheduled every {agent.schedule_interval_hours}h")
