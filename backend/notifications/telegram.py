import logging

from telegram import Bot
from telegram.error import TelegramError

from backend.config.settings import settings

logger = logging.getLogger("telegram")


class TelegramNotifier:
    def __init__(self) -> None:
        self._bot: Bot | None = None

    def _get_bot(self) -> Bot:
        if not self._bot:
            self._bot = Bot(token=settings.telegram_bot_token)
        return self._bot

    async def send(self, message: str) -> bool:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            logger.warning("Telegram not configured — skipping notification")
            return False
        try:
            await self._get_bot().send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.info("Telegram notification sent: %s", message[:80])
            return True
        except TelegramError as e:
            logger.error("Telegram notification failed: %s", e)
            return False

    async def send_test(self) -> bool:
        return await self.send(
            "🥝 <b>Project Kiwi</b> is online.\nNotifications are working correctly."
        )


notifier = TelegramNotifier()
