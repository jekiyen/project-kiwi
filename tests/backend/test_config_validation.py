"""Tests for startup config validation — must fail fast on real misconfiguration
and never fail on missing-but-optional integrations (Telegram)."""
import pytest

from backend.config.settings import Settings
from backend.config.validate import validate_settings


def _base_settings(**overrides) -> Settings:
    defaults = dict(
        ai_provider="manual",
        anthropic_api_key="",
        scan_interval_hours=6,
        notify_high_score_threshold=80,
        database_url="sqlite:///./kiwi.db",
        telegram_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_valid_manual_settings_pass():
    validate_settings(_base_settings())  # should not raise


def test_valid_claude_settings_pass():
    validate_settings(_base_settings(ai_provider="claude", anthropic_api_key="sk-ant-test"))


def test_claude_without_api_key_fails_fast():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        validate_settings(_base_settings(ai_provider="claude", anthropic_api_key=""))


def test_unimplemented_provider_fails_fast():
    with pytest.raises(RuntimeError, match="not implemented"):
        validate_settings(_base_settings(ai_provider="openai"))


def test_zero_scan_interval_fails_fast():
    with pytest.raises(RuntimeError, match="SCAN_INTERVAL_HOURS"):
        validate_settings(_base_settings(scan_interval_hours=0))


def test_negative_scan_interval_fails_fast():
    with pytest.raises(RuntimeError, match="SCAN_INTERVAL_HOURS"):
        validate_settings(_base_settings(scan_interval_hours=-1))


def test_threshold_out_of_range_fails_fast():
    with pytest.raises(RuntimeError, match="NOTIFY_HIGH_SCORE_THRESHOLD"):
        validate_settings(_base_settings(notify_high_score_threshold=150))


def test_empty_database_url_fails_fast():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        validate_settings(_base_settings(database_url=""))


def test_telegram_incomplete_never_fails_startup():
    """Telegram is fully optional — half-configured or missing must never raise."""
    validate_settings(_base_settings(telegram_enabled=True, telegram_bot_token="", telegram_chat_id=""))
    validate_settings(_base_settings(telegram_enabled=False))


def test_telegram_fully_configured_never_fails_startup():
    validate_settings(_base_settings(telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="c"))
