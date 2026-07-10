from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from telegram.error import TelegramError

from backend.config.settings import settings
from backend.notifications import NotificationEvent, NotificationEventType, notification_service
from backend.notifications.telegram import TelegramProvider

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Response models ──────────────────────────────────────────────────────────

class ProviderStatus(BaseModel):
    enabled: bool
    bot_token_present: bool
    bot_connected: bool
    chat_id_present: bool
    configured: bool


class NotificationConfigResponse(BaseModel):
    telegram: ProviderStatus


class TestNotificationResponse(BaseModel):
    success: bool
    configured: bool
    missing: list[str] = []
    message: str


class DetectedChatResponse(BaseModel):
    chat_id: int
    type: str
    username: Optional[str] = None
    title: Optional[str] = None
    display_name: str


class ChatIdDetectionResponse(BaseModel):
    success: bool
    bot_token_present: bool
    detected: list[DetectedChatResponse] = []
    message: str


# ── Config / health ──────────────────────────────────────────────────────────

@router.get("/config", response_model=NotificationConfigResponse)
async def get_notification_config() -> NotificationConfigResponse:
    """Report Telegram's setup status, for the Notifications page and Dashboard health card."""
    telegram = TelegramProvider()
    bot_token_present = bool(settings.telegram_bot_token)
    chat_id_present = bool(settings.telegram_chat_id)
    bot_connected = await telegram.check_connection() if bot_token_present else False
    configured = await telegram.is_configured()
    return NotificationConfigResponse(
        telegram=ProviderStatus(
            enabled=settings.telegram_enabled,
            bot_token_present=bot_token_present,
            bot_connected=bot_connected,
            chat_id_present=chat_id_present,
            configured=configured,
        )
    )


# ── Test notification ────────────────────────────────────────────────────────

@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification() -> TestNotificationResponse:
    """Send a real test message through every configured provider."""
    telegram = TelegramProvider()
    missing = telegram.missing_config()
    if missing:
        return TestNotificationResponse(
            success=False,
            configured=False,
            missing=missing,
            message=(
                "Telegram isn't fully configured yet. Missing: " + ", ".join(missing) + ". "
                "Set these in your .env file and restart the backend, then try again."
            ),
        )

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    results = await notification_service.dispatch(
        NotificationEvent(type=NotificationEventType.TEST, data={"timestamp": timestamp})
    )
    telegram_result = next((r for r in results if r.provider == "telegram"), None)

    if telegram_result is None or telegram_result.skipped:
        return TestNotificationResponse(
            success=False,
            configured=False,
            missing=["TELEGRAM_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
            message="Telegram isn't configured. Check your .env file.",
        )
    if telegram_result.success:
        return TestNotificationResponse(
            success=True,
            configured=True,
            message="Test notification sent — check Telegram for \"🥝 Kiwi Test\".",
        )
    return TestNotificationResponse(
        success=False,
        configured=True,
        message=(
            f"Telegram is configured but the test message failed to send: "
            f"{telegram_result.error or 'unknown error'}. Double check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
        ),
    )


# ── Chat ID detection ────────────────────────────────────────────────────────

@router.get("/chat-id", response_model=ChatIdDetectionResponse)
async def detect_chat_id() -> ChatIdDetectionResponse:
    """
    Look up chats that have messaged this bot, via Telegram's getUpdates API.
    Read-only — nothing is written to TELEGRAM_CHAT_ID automatically. The user
    copies the chat ID they want into .env themselves.
    """
    if not settings.telegram_bot_token:
        return ChatIdDetectionResponse(
            success=False,
            bot_token_present=False,
            message="Set TELEGRAM_BOT_TOKEN in your .env file and restart the backend, then try again.",
        )

    telegram = TelegramProvider()
    try:
        chats = await telegram.detect_chats()
    except TelegramError as exc:
        return ChatIdDetectionResponse(
            success=False,
            bot_token_present=True,
            message=f"Couldn't reach Telegram with this bot token — double check TELEGRAM_BOT_TOKEN. ({exc})",
        )
    except Exception:
        return ChatIdDetectionResponse(
            success=False,
            bot_token_present=True,
            message="Unexpected error contacting Telegram. Check the backend logs for details.",
        )

    if not chats:
        return ChatIdDetectionResponse(
            success=True,
            bot_token_present=True,
            message=(
                "No messages found yet. Open Telegram, find your bot, and send it any "
                "message (e.g. /start), then click Detect Chat ID again."
            ),
        )
    return ChatIdDetectionResponse(
        success=True,
        bot_token_present=True,
        detected=[
            DetectedChatResponse(
                chat_id=c.chat_id, type=c.type, username=c.username,
                title=c.title, display_name=c.display_name,
            )
            for c in chats
        ],
        message=(
            f"Found {len(chats)} chat(s). Copy the Chat ID you want into TELEGRAM_CHAT_ID "
            "in your .env file, then restart the backend."
        ),
    )
