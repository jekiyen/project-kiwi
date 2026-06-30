from backend.ai.base import AIProvider, JobAnalysis
from backend.config.settings import settings


class OpenAIProvider(AIProvider):
    """OpenAI provider — implement in a future phase if needed."""

    async def analyze_job(self, job_data: dict, user_profile: dict) -> JobAnalysis:
        raise NotImplementedError("OpenAI provider not yet implemented.")

    async def is_available(self) -> bool:
        return bool(settings.openai_api_key)
