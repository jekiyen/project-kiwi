"""Tests for the notification foundation: templates, dispatch, provider skip, API."""
import pytest
from fastapi.testclient import TestClient

from backend.notifications.base import (
    NotificationEvent,
    NotificationEventType,
    NotificationProvider,
)
from backend.notifications.service import NotificationService
from backend.notifications.telegram import TelegramProvider
from backend.notifications.templates import format_message


# ── Fake providers for isolated dispatch tests ─────────────────────────────────

class _AlwaysOnProvider(NotificationProvider):
    def __init__(self, succeed: bool = True, raise_on_send: bool = False, name: str = "fake_on") -> None:
        self.name = name
        self.succeed = succeed
        self.raise_on_send = raise_on_send
        self.sent_messages: list[str] = []

    async def is_configured(self) -> bool:
        return True

    async def send(self, message: str) -> bool:
        if self.raise_on_send:
            raise RuntimeError("boom")
        self.sent_messages.append(message)
        return self.succeed


class _NeverConfiguredProvider(NotificationProvider):
    name = "fake_off"

    async def is_configured(self) -> bool:
        return False

    async def send(self, message: str) -> bool:  # pragma: no cover - should never be called
        raise AssertionError("send() should not be called when not configured")


# ── Templates ─────────────────────────────────────────────────────────────────

def test_format_high_score_job():
    event = NotificationEvent(
        type=NotificationEventType.HIGH_SCORE_JOB,
        data={
            "title": "Packhouse Worker",
            "employer": "Test Co",
            "location": "Hastings",
            "score": 95,
            "reasons": ["Kiwi experience", "Seasonal", "Forklift"],
            "url": "https://example.com/job/1",
        },
    )
    msg = format_message(event)
    assert "New High Match Job" in msg
    assert "Packhouse Worker" in msg
    assert "Score: 95/100" in msg
    assert "• Kiwi experience" in msg
    assert "• Seasonal" in msg
    assert "View listing" in msg


def test_format_high_score_job_defaults_reason_when_none_given():
    event = NotificationEvent(type=NotificationEventType.HIGH_SCORE_JOB, data={"title": "X", "score": 90})
    msg = format_message(event)
    assert "• Strong overall match" in msg


def test_format_scan_completed():
    event = NotificationEvent(
        type=NotificationEventType.SCAN_COMPLETED,
        data={"jobs_found": 338, "new_jobs": 10, "high_priority": 3},
    )
    msg = format_message(event)
    assert "Scan Completed" in msg
    assert "338 scanned" in msg
    assert "10 new jobs" in msg
    assert "3 high priority" in msg


def test_format_scan_failed():
    event = NotificationEvent(
        type=NotificationEventType.SCAN_FAILED,
        data={"failed_count": 2, "total_scrapers": 6, "errors": ["seek: timeout"]},
    )
    msg = format_message(event)
    assert "Scan Failed" in msg
    assert "2 of 6 source(s) failed" in msg
    assert "seek: timeout" in msg


def test_format_application_created():
    event = NotificationEvent(
        type=NotificationEventType.APPLICATION_CREATED,
        data={"title": "Dairy Farm Worker", "employer": "Beverley Farms", "status": "saved"},
    )
    msg = format_message(event)
    assert "Application Saved" in msg
    assert "Dairy Farm Worker" in msg
    assert "Beverley Farms" in msg
    assert "Status: Saved" in msg


def test_format_application_status_changed():
    event = NotificationEvent(
        type=NotificationEventType.APPLICATION_STATUS_CHANGED,
        data={"title": "Dairy Farm Worker", "employer": "Beverley Farms", "from_status": "saved", "to_status": "interview"},
    )
    msg = format_message(event)
    assert "Application Updated" in msg
    assert "Saved → Interview" in msg


def test_format_test_event():
    msg = format_message(NotificationEvent(type=NotificationEventType.TEST))
    assert "Kiwi Test" in msg
    assert "Telegram integration successful." in msg


def test_format_test_event_includes_timestamp_when_given():
    msg = format_message(NotificationEvent(type=NotificationEventType.TEST, data={"timestamp": "2026-07-10 14:32:10 UTC"}))
    assert "Current time:" in msg
    assert "2026-07-10 14:32:10 UTC" in msg


def test_format_escapes_html_in_user_data():
    event = NotificationEvent(
        type=NotificationEventType.APPLICATION_CREATED,
        data={"title": "<script>alert(1)</script>", "employer": "Evil & Co", "status": "saved"},
    )
    msg = format_message(event)
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg
    assert "Evil &amp; Co" in msg


# ── NotificationService dispatch ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_skips_unconfigured_provider():
    provider = _NeverConfiguredProvider()
    service = NotificationService(providers=[provider])
    results = await service.dispatch(NotificationEvent(type=NotificationEventType.TEST))
    assert len(results) == 1
    assert results[0].skipped is True
    assert results[0].success is False


@pytest.mark.asyncio
async def test_dispatch_sends_to_configured_provider():
    provider = _AlwaysOnProvider(succeed=True)
    service = NotificationService(providers=[provider])
    results = await service.dispatch(
        NotificationEvent(type=NotificationEventType.APPLICATION_CREATED, data={"title": "X", "status": "saved"})
    )
    assert results[0].success is True
    assert results[0].skipped is False
    assert len(provider.sent_messages) == 1


@pytest.mark.asyncio
async def test_dispatch_never_raises_when_provider_send_throws():
    provider = _AlwaysOnProvider(raise_on_send=True)
    service = NotificationService(providers=[provider])
    results = await service.dispatch(NotificationEvent(type=NotificationEventType.TEST))
    assert results[0].success is False
    assert results[0].error == "boom"


@pytest.mark.asyncio
async def test_dispatch_fans_out_to_multiple_providers_independently():
    ok = _AlwaysOnProvider(succeed=True, name="fake_ok")
    off = _NeverConfiguredProvider()
    broken = _AlwaysOnProvider(raise_on_send=True, name="fake_broken")
    service = NotificationService(providers=[ok, off, broken])
    results = await service.dispatch(NotificationEvent(type=NotificationEventType.TEST))
    by_provider = {r.provider: r for r in results}
    assert by_provider["fake_ok"].success is True
    assert by_provider["fake_off"].skipped is True
    assert by_provider["fake_broken"].success is False
    assert by_provider["fake_broken"].error == "boom"


@pytest.mark.asyncio
async def test_provider_statuses():
    ok = _AlwaysOnProvider()
    off = _NeverConfiguredProvider()
    service = NotificationService(providers=[ok, off])
    statuses = await service.provider_statuses()
    assert statuses == {"fake_on": True, "fake_off": False}


# ── TelegramProvider configuration gating ───────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_provider_not_configured_by_default(monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    provider = TelegramProvider()
    assert await provider.is_configured() is False


@pytest.mark.asyncio
async def test_telegram_provider_requires_enabled_flag_even_with_credentials(monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "some-chat-id")
    provider = TelegramProvider()
    assert await provider.is_configured() is False


@pytest.mark.asyncio
async def test_telegram_provider_configured_when_all_three_set(monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "some-chat-id")
    provider = TelegramProvider()
    assert await provider.is_configured() is True


@pytest.mark.asyncio
async def test_telegram_provider_send_skips_and_returns_false_when_not_configured(monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    provider = TelegramProvider()
    assert await provider.send("hello") is False


# ── API: GET /notifications/config ──────────────────────────────────────────────

@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_config_endpoint_reports_not_configured_by_default(client, monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    r = client.get("/api/v1/notifications/config")
    assert r.status_code == 200
    data = r.json()
    assert data["telegram"]["enabled"] is False
    assert data["telegram"]["configured"] is False
    assert data["telegram"]["bot_token_present"] is False
    assert data["telegram"]["bot_connected"] is False
    assert data["telegram"]["chat_id_present"] is False


def test_config_endpoint_reports_configured_when_all_set_and_bot_reachable(client, monkeypatch):
    import telegram
    from backend.config.settings import settings

    async def _fake_get_me(self, *args, **kwargs):
        return telegram.User(id=1, first_name="Kiwi Bot", is_bot=True)

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "some-chat-id")
    monkeypatch.setattr(telegram.Bot, "get_me", _fake_get_me)

    r = client.get("/api/v1/notifications/config")
    assert r.status_code == 200
    data = r.json()
    assert data["telegram"]["enabled"] is True
    assert data["telegram"]["bot_token_present"] is True
    assert data["telegram"]["bot_connected"] is True
    assert data["telegram"]["chat_id_present"] is True
    assert data["telegram"]["configured"] is True


def test_config_endpoint_bot_connected_false_when_token_invalid(client, monkeypatch):
    import telegram
    from telegram.error import TelegramError
    from backend.config.settings import settings

    async def _fake_get_me(self, *args, **kwargs):
        raise TelegramError("Unauthorized")

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bad-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "some-chat-id")
    monkeypatch.setattr(telegram.Bot, "get_me", _fake_get_me)

    r = client.get("/api/v1/notifications/config")
    assert r.status_code == 200
    data = r.json()
    assert data["telegram"]["bot_token_present"] is True
    assert data["telegram"]["bot_connected"] is False
    # is_configured() is a local check (enabled+token+chat_id) — stays True even
    # though the token turns out to be bad; that's what /test and /chat-id are for.
    assert data["telegram"]["configured"] is True


# ── API: POST /notifications/test ───────────────────────────────────────────────

def test_test_endpoint_friendly_message_when_not_configured(client, monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    r = client.post("/api/v1/notifications/test")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["configured"] is False
    assert "TELEGRAM_ENABLED" in data["message"]


def test_test_endpoint_missing_lists_only_actually_missing_vars(client, monkeypatch):
    """Bot token is set but enabled/chat_id aren't — missing should name exactly those two."""
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "")
    r = client.post("/api/v1/notifications/test")
    data = r.json()
    assert data["missing"] == ["TELEGRAM_ENABLED", "TELEGRAM_CHAT_ID"]
    assert "TELEGRAM_BOT_TOKEN" not in data["missing"]


def test_test_endpoint_sends_real_message_with_timestamp_when_configured(client, monkeypatch):
    import telegram
    from backend.config.settings import settings

    captured: dict = {}

    async def _fake_send_message(self, chat_id, text, **kwargs):
        captured["chat_id"] = chat_id
        captured["text"] = text
        return None

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "12345")
    monkeypatch.setattr(telegram.Bot, "send_message", _fake_send_message)

    r = client.post("/api/v1/notifications/test")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["configured"] is True

    assert captured["chat_id"] == "12345"
    assert "Kiwi Test" in captured["text"]
    assert "Telegram integration successful." in captured["text"]
    assert "Current time:" in captured["text"]


def test_test_endpoint_never_crashes_when_telegram_api_fails(client, monkeypatch):
    """Configured-but-failing Telegram must fail gracefully, not 500 — and not hit the network."""
    import telegram
    from telegram.error import TelegramError

    from backend.config.settings import settings

    async def _raise(*args, **kwargs):
        raise TelegramError("Unauthorized")

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "invalid-token-value")
    monkeypatch.setattr(settings, "telegram_chat_id", "12345")
    monkeypatch.setattr(telegram.Bot, "send_message", _raise)

    r = client.post("/api/v1/notifications/test")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["success"] is False


# ── TelegramProvider.check_connection() ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_connection_true_when_get_me_succeeds(monkeypatch):
    import telegram
    from backend.config.settings import settings

    async def _fake_get_me(self, *args, **kwargs):
        return telegram.User(id=1, first_name="Kiwi Bot", is_bot=True)

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_me", _fake_get_me)
    provider = TelegramProvider()
    assert await provider.check_connection() is True


@pytest.mark.asyncio
async def test_check_connection_false_when_no_token(monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    provider = TelegramProvider()
    assert await provider.check_connection() is False


@pytest.mark.asyncio
async def test_check_connection_false_when_get_me_raises(monkeypatch):
    import telegram
    from telegram.error import TelegramError
    from backend.config.settings import settings

    async def _raise(self, *args, **kwargs):
        raise TelegramError("Unauthorized")

    monkeypatch.setattr(settings, "telegram_bot_token", "bad-token")
    monkeypatch.setattr(telegram.Bot, "get_me", _raise)
    provider = TelegramProvider()
    assert await provider.check_connection() is False


# ── TelegramProvider.detect_chats() ──────────────────────────────────────────────

def _make_update(update_id: int, chat_id: int, chat_type: str, **chat_kwargs):
    import telegram
    from datetime import datetime

    chat = telegram.Chat(id=chat_id, type=chat_type, **chat_kwargs)
    message = telegram.Message(message_id=1, date=datetime.utcnow(), chat=chat, text="hi")
    return telegram.Update(update_id=update_id, message=message)


@pytest.mark.asyncio
async def test_detect_chats_returns_private_chat(monkeypatch):
    import telegram
    from backend.config.settings import settings

    update = _make_update(1, 555, "private", username="rizky", first_name="Rizky")

    async def _fake_get_updates(self, *args, **kwargs):
        return (update,)

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _fake_get_updates)

    provider = TelegramProvider()
    chats = await provider.detect_chats()
    assert len(chats) == 1
    assert chats[0].chat_id == 555
    assert chats[0].type == "private"
    assert chats[0].username == "rizky"
    assert "Rizky" in chats[0].display_name


@pytest.mark.asyncio
async def test_detect_chats_dedupes_same_chat(monkeypatch):
    import telegram
    from backend.config.settings import settings

    updates = (
        _make_update(1, 555, "private", first_name="Rizky"),
        _make_update(2, 555, "private", first_name="Rizky"),
    )

    async def _fake_get_updates(self, *args, **kwargs):
        return updates

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _fake_get_updates)

    provider = TelegramProvider()
    chats = await provider.detect_chats()
    assert len(chats) == 1


@pytest.mark.asyncio
async def test_detect_chats_empty_when_no_updates(monkeypatch):
    import telegram
    from backend.config.settings import settings

    async def _fake_get_updates(self, *args, **kwargs):
        return ()

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _fake_get_updates)

    provider = TelegramProvider()
    chats = await provider.detect_chats()
    assert chats == []


# ── API: GET /notifications/chat-id ──────────────────────────────────────────────

def test_chat_id_endpoint_no_token(client, monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    r = client.get("/api/v1/notifications/chat-id")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["bot_token_present"] is False
    assert data["detected"] == []
    assert "TELEGRAM_BOT_TOKEN" in data["message"]


def test_chat_id_endpoint_success(client, monkeypatch):
    import telegram
    from backend.config.settings import settings

    update = _make_update(1, 555, "private", username="rizky", first_name="Rizky")

    async def _fake_get_updates(self, *args, **kwargs):
        return (update,)

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _fake_get_updates)

    r = client.get("/api/v1/notifications/chat-id")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["bot_token_present"] is True
    assert len(data["detected"]) == 1
    assert data["detected"][0]["chat_id"] == 555
    assert data["detected"][0]["type"] == "private"
    # Never auto-stores anything — settings.telegram_chat_id must stay untouched.
    from backend.config.settings import settings as live_settings
    assert live_settings.telegram_chat_id != "555"


def test_chat_id_endpoint_no_messages_yet(client, monkeypatch):
    import telegram
    from backend.config.settings import settings

    async def _fake_get_updates(self, *args, **kwargs):
        return ()

    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _fake_get_updates)

    r = client.get("/api/v1/notifications/chat-id")
    data = r.json()
    assert data["success"] is True
    assert data["detected"] == []
    assert "send it any" in data["message"].lower() or "message" in data["message"].lower()


def test_chat_id_endpoint_bad_token(client, monkeypatch):
    import telegram
    from telegram.error import TelegramError
    from backend.config.settings import settings

    async def _raise(self, *args, **kwargs):
        raise TelegramError("Unauthorized")

    monkeypatch.setattr(settings, "telegram_bot_token", "bad-token")
    monkeypatch.setattr(telegram.Bot, "get_updates", _raise)

    r = client.get("/api/v1/notifications/chat-id")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is False
    assert data["bot_token_present"] is True
    assert data["detected"] == []
