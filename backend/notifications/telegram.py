import logging

from telegram import Bot
from telegram.error import TelegramError

from backend.config.settings import settings
from backend.notifications.base import NotificationProvider

logger = logging.getLogger("telegram")


class TelegramProvider(NotificationProvider):
    name = "telegram"

    def __init__(self) -> None:
        self._bot: Bot | None = None

    def _get_bot(self) -> Bot:
        if self._bot is None:
            self._bot = Bot(token=settings.telegram_bot_token)
        return self._bot

    async def is_configured(self) -> bool:
        return bool(
            settings.telegram_enabled
            and settings.telegram_bot_token
            and settings.telegram_chat_id
        )

    async def send(self, message: str) -> bool:
        if not await self.is_configured():
            logger.warning("Telegram not configured — skipping notification")
            return False
        try:
            await self._get_bot().send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.info("Telegram notification sent: %s", message.replace("\n", " ")[:80])
            return True
        except TelegramError as exc:
            logger.error("Telegram notification failed: %s", exc)
            return False
