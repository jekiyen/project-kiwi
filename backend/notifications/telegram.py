import logging
from dataclasses import dataclass
from typing import Optional

from telegram import Bot
from telegram.error import NetworkError, TelegramError, TimedOut

from backend.config.settings import settings
from backend.core.retry import retry_async
from backend.notifications.base import NotificationProvider

logger = logging.getLogger("telegram")


def redact_token(text: str) -> str:
    """Strip the bot token out of error text before it's logged or shown to the user."""
    token = settings.telegram_bot_token
    if token and token in text:
        return text.replace(token, "***REDACTED***")
    return text


@dataclass
class DetectedChat:
    chat_id: int
    type: str
    username: Optional[str] = None
    title: Optional[str] = None
    display_name: str = ""


class TelegramProvider(NotificationProvider):
    name = "telegram"

    def __init__(self) -> None:
        self._bot: Bot | None = None

    def _get_bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=settings.telegram_bot_token)
        return self._bot

    def missing_config(self) -> list[str]:
        """Env vars that still need to be set for this provider to go ACTIVE."""
        missing = []
        if not settings.telegram_enabled:
            missing.append("TELEGRAM_ENABLED")
        if not settings.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not settings.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return missing

    async def is_configured(self) -> bool:
        """ACTIVE iff TELEGRAM_ENABLED=true and both bot token and chat ID are set.

        This is a local, no-network check — it's called on every dispatched
        event, so it must stay fast and must never make an API call.
        """
        return not self.missing_config()

    async def check_connection(self) -> bool:
        """Live check that the bot token is valid and Telegram is reachable.

        Unlike is_configured(), this hits the network (getMe) — only call it
        from status/settings endpoints, never from the hot dispatch path.
        """
        if not settings.telegram_bot_token:
            return False
        try:
            await self._get_bot().get_me()
            return True
        except TelegramError as exc:
            logger.warning("Telegram connection check failed: %s", redact_token(str(exc)))
            return False
        except Exception:
            logger.exception("Unexpected error checking Telegram connection")
            return False

    async def detect_chats(self) -> list[DetectedChat]:
        """Query Telegram's getUpdates API for chats that have messaged this bot.

        Read-only — never writes TELEGRAM_CHAT_ID anywhere. The caller decides
        what to do with the result.
        """
        updates = await self._get_bot().get_updates(limit=100, timeout=0)
        seen: dict[int, DetectedChat] = {}
        for update in updates:
            chat = None
            if update.message is not None:
                chat = update.message.chat
            elif update.channel_post is not None:
                chat = update.channel_post.chat
            elif update.my_chat_member is not None:
                chat = update.my_chat_member.chat
            if chat is None:
                continue

            display_name = (
                chat.title
                or " ".join(filter(None, [getattr(chat, "first_name", None), getattr(chat, "last_name", None)]))
                or (f"@{chat.username}" if chat.username else str(chat.id))
            )
            seen[chat.id] = DetectedChat(
                chat_id=chat.id,
                type=str(chat.type),
                username=chat.username,
                title=chat.title,
                display_name=display_name,
            )
        return list(seen.values())

    async def send(self, message: str) -> bool:
        if not await self.is_configured():
            logger.warning("Telegram not configured — skipping notification")
            return False
        try:
            await retry_async(
                lambda: self._get_bot().send_message(
                    chat_id=settings.telegram_chat_id,
                    text=message,
                    parse_mode="HTML",
                ),
                retries=2,
                base_delay=1.0,
                exceptions=(NetworkError, TimedOut),
                label="Telegram send_message",
            )
            logger.info("Telegram notification sent: %s", message.replace("\n", " ")[:80])
            return True
        except TelegramError as exc:
            # NetworkError/TimedOut retried above; anything else (bad token, bad
            # chat id, forbidden) is permanent — fail immediately, no retry.
            logger.error("Telegram notification failed: %s", redact_token(str(exc)))
            return False
