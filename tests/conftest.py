import pytest


@pytest.fixture(autouse=True)
def _disable_real_telegram_by_default(monkeypatch):
    """Tests must never depend on, or send messages through, a real Telegram bot.

    Force Telegram off for every test regardless of what's in the developer's
    local .env — without this, a developer who has completed the real Telegram
    setup (Phase 6.2B) would have every test run silently message their own
    Telegram chat and make the whole suite slow and network-dependent.

    Tests that need to exercise the "configured" path explicitly monkeypatch
    these back on (and mock the Telegram SDK calls) for themselves.
    """
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
