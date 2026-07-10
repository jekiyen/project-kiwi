from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class NotificationEventType(str, Enum):
    HIGH_SCORE_JOB = "high_score_job"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    APPLICATION_CREATED = "application_created"
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    TEST = "test"


@dataclass
class NotificationEvent:
    """A domain event to dispatch to all configured notification providers.

    Business logic builds one of these and hands it to NotificationService —
    it never talks to a provider directly.
    """
    type: NotificationEventType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationResult:
    """Outcome of attempting to send one event through one provider."""
    provider: str
    event: str
    success: bool
    duration_ms: int
    skipped: bool = False
    error: Optional[str] = None


class NotificationProvider(ABC):
    """
    All notification channels extend this class. To add a new provider
    (e.g. Email, Discord, Slack): create backend/notifications/<name>.py
    implementing this interface, then register it in
    backend/notifications/__init__.py's get_notification_service().
    """

    name: str

    @abstractmethod
    async def is_configured(self) -> bool:
        """Return True if this provider has everything it needs to send."""
        ...

    @abstractmethod
    async def send(self, message: str) -> bool:
        """Send a pre-formatted message. Must never raise — return False on failure."""
        ...
