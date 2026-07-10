from backend.notifications.base import (
    NotificationEvent,
    NotificationEventType,
    NotificationProvider,
    NotificationResult,
)
from backend.notifications.service import NotificationService
from backend.notifications.telegram import TelegramProvider


def get_notification_service() -> NotificationService:
    """
    All registered providers. To add a new channel (Email, Discord, Slack):
    create backend/notifications/<name>.py implementing NotificationProvider,
    then add an instance here.
    """
    return NotificationService(providers=[TelegramProvider()])


notification_service = get_notification_service()

__all__ = [
    "NotificationEvent",
    "NotificationEventType",
    "NotificationProvider",
    "NotificationResult",
    "NotificationService",
    "TelegramProvider",
    "get_notification_service",
    "notification_service",
]
