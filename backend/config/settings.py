from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AI
    ai_provider: Literal["claude", "openai", "gemini", "ollama", "manual"] = "manual"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # Claude-specific
    claude_model: str = "claude-haiku-4-5-20251001"
    claude_timeout_seconds: float = 30.0
    claude_max_retries: int = 2

    # Telegram
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Notifications
    notify_high_score_threshold: int = 80

    # Database
    database_url: str = "sqlite:///./kiwi.db"

    # Scheduler
    scan_interval_hours: int = 6

    # Server
    backend_port: int = 8000
    frontend_port: int = 5173

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
