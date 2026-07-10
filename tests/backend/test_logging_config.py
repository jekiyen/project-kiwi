"""Regression tests for real bugs found during manual verification:
1. LocalTimeFormatter was shifting timestamps by +7h twice when the host
   machine's own system timezone was already Asia/Jakarta.
2. httpx (used by python-telegram-bot) logs full request URLs at INFO —
   for the Telegram Bot API that URL contains the bot token in the path,
   leaking it straight to the console/log files.
"""
import logging
from datetime import datetime, timezone

from backend.logging_config import LocalTimeFormatter, SecretRedactionFilter


def test_format_time_matches_known_utc_instant():
    # 2026-07-10 09:52:29 UTC == 2026-07-10 16:52:29 in Asia/Jakarta (UTC+7).
    known_utc = datetime(2026, 7, 10, 9, 52, 29, tzinfo=timezone.utc)
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    record.created = known_utc.timestamp()

    formatter = LocalTimeFormatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    assert formatter.formatTime(record) == "2026-07-10T16:52:29"


def test_format_time_is_independent_of_host_local_timezone(monkeypatch):
    """The bug only reproduced when the host's own local tz happened to be
    Asia/Jakarta — assert correctness regardless of what datetime.fromtimestamp()
    would produce under the host's local tz."""
    known_utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hi", args=(), exc_info=None,
    )
    record.created = known_utc.timestamp()

    formatter = LocalTimeFormatter("%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    # Midnight UTC on Jan 1 is 07:00 the same day in Asia/Jakarta (no DST).
    assert formatter.formatTime(record) == "2026-01-01T07:00:00"


# ── Secret redaction ──────────────────────────────────────────────────────────

def test_redacts_bot_token_from_url_in_log_message(monkeypatch):
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "123456:AAsecretTokenValue")
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg='HTTP Request: POST https://api.telegram.org/bot%s/getMe "HTTP/1.1 200 OK"',
        args=("123456:AAsecretTokenValue",), exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert "123456:AAsecretTokenValue" not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()


def test_does_not_touch_messages_without_the_token(monkeypatch):
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "123456:AAsecretTokenValue")
    record = logging.LogRecord(
        name="application", level=logging.INFO, pathname=__file__, lineno=1,
        msg="GET /api/v1/health -> 200 (1ms)", args=(), exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "GET /api/v1/health -> 200 (1ms)"


def test_noop_when_telegram_not_configured(monkeypatch):
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "")
    record = logging.LogRecord(
        name="httpx", level=logging.INFO, pathname=__file__, lineno=1,
        msg="HTTP Request: GET https://example.com/", args=(), exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "HTTP Request: GET https://example.com/"
