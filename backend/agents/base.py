from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentResult:
    success: bool
    message: str
    data: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """
    All agents extend this class. To add a new agent (e.g. VisaAgent):
    1. Create backend/agents/visa_agent.py extending BaseAgent
    2. Register it in backend/main.py lifespan
    """

    name: str
    description: str

    @abstractmethod
    async def run(self) -> AgentResult:
        """Execute the agent's primary task and return a result."""
        ...

    @property
    def schedule_interval_hours(self) -> Optional[int]:
        """Return the auto-run interval in hours. None = not scheduled."""
        return None
