import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.agents.base import BaseAgent

logger = logging.getLogger("application")

scheduler = AsyncIOScheduler()


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
