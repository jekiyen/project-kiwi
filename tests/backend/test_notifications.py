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
    assert "Test Notification" in msg


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


def test_config_endpoint_reports_configured_when_all_set(client, monkeypatch):
    from backend.config.settings import settings
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "some-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "some-chat-id")
    r = client.get("/api/v1/notifications/config")
    assert r.status_code == 200
    data = r.json()
    assert data["telegram"]["enabled"] is True
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
