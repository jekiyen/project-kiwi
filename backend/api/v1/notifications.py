from fastapi import APIRouter

from backend.notifications.telegram import notifier

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/test")
async def send_test_notification() -> dict:
    success = await notifier.send_test()
    if success:
        return {"message": "Test notification sent successfully"}
    return {"message": "Telegram not configured — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"}
