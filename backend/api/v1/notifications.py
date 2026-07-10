from fastapi import APIRouter
from pydantic import BaseModel

from backend.config.settings import settings
from backend.notifications import NotificationEvent, NotificationEventType, notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ProviderStatus(BaseModel):
    enabled: bool
    configured: bool


class NotificationConfigResponse(BaseModel):
    telegram: ProviderStatus


class TestNotificationResponse(BaseModel):
    success: bool
    configured: bool
    message: str


@router.get("/config", response_model=NotificationConfigResponse)
async def get_notification_config() -> NotificationConfigResponse:
    """Report which notification channels are configured, for settings/health UI."""
    statuses = await notification_service.provider_statuses()
    return NotificationConfigResponse(
        telegram=ProviderStatus(
            enabled=settings.telegram_enabled,
            configured=statuses.get("telegram", False),
        )
    )


@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification() -> TestNotificationResponse:
    """Send a test message through every configured provider."""
    results = await notification_service.dispatch(NotificationEvent(type=NotificationEventType.TEST))
    telegram_result = next((r for r in results if r.provider == "telegram"), None)

    if telegram_result is None or telegram_result.skipped:
        return TestNotificationResponse(
            success=False,
            configured=False,
            message=(
                "Telegram isn't configured yet. Set TELEGRAM_ENABLED=true, "
                "TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID in your .env file, then try again."
            ),
        )
    if telegram_result.success:
        return TestNotificationResponse(
            success=True,
            configured=True,
            message="Test notification sent successfully.",
        )
    return TestNotificationResponse(
        success=False,
        configured=True,
        message=f"Telegram is configured but the test message failed to send: "
                f"{telegram_result.error or 'unknown error'}",
    )
