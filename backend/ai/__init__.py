from backend.ai.base import AIProvider
from backend.config.settings import settings


def get_ai_provider() -> AIProvider:
    if settings.ai_provider == "claude":
        from backend.ai.claude import ClaudeProvider
        return ClaudeProvider()
    if settings.ai_provider == "openai":
        from backend.ai.openai_provider import OpenAIProvider
        return OpenAIProvider()
    from backend.ai.manual import ManualProvider
    return ManualProvider()
