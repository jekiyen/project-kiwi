"""Startup configuration validation — fail fast with a clear message rather
than crash deep inside a background task hours later.

Anything genuinely optional (Telegram, alternate AI providers not currently
selected) must never be validated here — only the configuration actually
required for the app to run correctly as configured.
"""
import logging

from backend.config.settings import Settings

logger = logging.getLogger("application")

# AI providers with a real implementation today. Anything else in the
# AI_PROVIDER Literal (e.g. "gemini", "ollama") — and "openai", which is a
# stub that raises NotImplementedError — would otherwise silently behave
# unexpectedly instead of failing fast.
_IMPLEMENTED_AI_PROVIDERS = {"manual", "claude"}


def validate_settings(settings: Settings) -> None:
    errors: list[str] = []

    if settings.ai_provider not in _IMPLEMENTED_AI_PROVIDERS:
        errors.append(
            f"AI_PROVIDER={settings.ai_provider!r} is not implemented yet "
            f"(available: {sorted(_IMPLEMENTED_AI_PROVIDERS)}) — refusing to start "
            "rather than silently fall back to a different scorer."
        )
    if settings.ai_provider == "claude" and not settings.anthropic_api_key:
        errors.append("AI_PROVIDER=claude requires ANTHROPIC_API_KEY to be set in .env")

    if settings.scan_interval_hours <= 0:
        errors.append("SCAN_INTERVAL_HOURS must be greater than 0")
    if not (0 <= settings.notify_high_score_threshold <= 100):
        errors.append("NOTIFY_HIGH_SCORE_THRESHOLD must be between 0 and 100")
    if not settings.database_url:
        errors.append("DATABASE_URL must not be empty")
    if settings.resume_max_file_size_mb <= 0:
        errors.append("RESUME_MAX_FILE_SIZE_MB must be greater than 0")

    if errors:
        details = "\n".join(f"  - {e}" for e in errors)
        raise RuntimeError(f"Invalid configuration — refusing to start:\n{details}")

    # Telegram is intentionally never a startup error — fully optional, and
    # TelegramProvider already stays silently disabled when incomplete. Just
    # give a one-time heads-up if it looks half-configured.
    if settings.telegram_enabled and not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.warning(
            "TELEGRAM_ENABLED=true but TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID "
            "are missing — notifications will stay disabled until both are set."
        )
