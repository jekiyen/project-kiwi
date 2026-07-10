import json
import logging
import time

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
)

from backend.ai.base import AIProvider, JobAnalysis
from backend.config.settings import settings
from backend.config.user_profile import USER_PROFILE

logger = logging.getLogger("scanner")

_SYSTEM_PROMPT = """\
You are evaluating a New Zealand job listing for a specific candidate who wants to migrate from \
Indonesia. Your task is to score how well this job fits the candidate's goals and profile.

Return ONLY a valid JSON object — no markdown, no code blocks, no extra text.

JSON schema (every field is required):
{
  "score": <integer 0-100, overall fit for this candidate>,
  "priority": "<P1|P2|P3|Reject>",
  "reasons": ["<concise reason 1>", "<concise reason 2>", "<concise reason 3>"],
  "pros": ["<pro 1>", ...],
  "cons": ["<con 1>", ...],
  "visa_accredited_employer": <true|false>,
  "visa_overseas_friendly": <true|false>,
  "visa_sponsorship_potential": <true|false>,
  "visa_nz_rights_required": <true|false>,
  "visa_probability": <integer 0-100, estimated chance this employer will sponsor a work visa>,
  "confidence": <integer 0-100, your confidence given the information available>
}

Priority guide:
- P1: Packhouse / Orchard / Farm / Fruit Picking / Horticulture roles
- P2: Warehouse / Factory / Manufacturing / Production roles
- P3: General Labourer / Construction Labour
- Reject: Does not match any priority category, or explicitly requires NZ work rights

Score guide:
- 80-100: Strong match — right role type, no visa barrier, positive signals
- 60-79:  Good match — right role type with minor concerns
- 40-59:  Moderate match — secondary category or mixed signals
- 20-39:  Weak match — tertiary category or barriers present
- 0-19:   Poor match — wrong category or hard barrier (NZ rights required)
"""

_USER_TEMPLATE = """\
Candidate profile:
{profile}

Job listing:
{job}
"""


def _fallback_analysis(error_msg: str, model: str) -> JobAnalysis:
    """Return a sentinel analysis when the API call fails."""
    return JobAnalysis(
        score=0,
        priority="Reject",
        explanation=f"Analysis failed — verify manually. Error: {error_msg}",
        reasons=[f"Analysis failed: {error_msg}"],
        pros=[],
        cons=["Could not be analysed automatically."],
        visa_accredited_employer=False,
        visa_overseas_friendly=False,
        visa_sponsorship_potential=False,
        visa_nz_rights_required=False,
        visa_probability=0,
        confidence=0,
        provider="claude",
        model=model,
    )


class ClaudeProvider(AIProvider):
    """
    Production AI provider using the Anthropic Claude API.

    Handles:
    - Configurable model (default: claude-haiku-4-5-20251001)
    - Timeout via Anthropic SDK
    - Automatic retries with exponential backoff via Anthropic SDK
    - Strict JSON schema enforcement
    - Latency and token logging
    - Never crashes the pipeline — returns a fallback analysis on any error
    """

    def __init__(self) -> None:
        self._model = settings.claude_model
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.claude_timeout_seconds,
            max_retries=settings.claude_max_retries,
        )

    async def analyze_job(self, job_data: dict, user_profile: dict) -> JobAnalysis:
        model = self._model
        t0 = time.perf_counter()

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=768,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": _USER_TEMPLATE.format(
                            profile=json.dumps(user_profile or USER_PROFILE, indent=2),
                            job=json.dumps(job_data, indent=2),
                        ),
                    }
                ],
            )

            latency_ms = int((time.perf_counter() - t0) * 1000)
            usage = response.usage
            logger.info(
                "Claude analysis: model=%s latency=%dms input_tokens=%d output_tokens=%d job=%s",
                model,
                latency_ms,
                usage.input_tokens,
                usage.output_tokens,
                job_data.get("title", "?"),
            )

            raw = response.content[0].text.strip()
            # Strip accidental markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            data = json.loads(raw)
            return self._build_analysis(data, model)

        except (APITimeoutError, APIConnectionError) as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.error(
                "Claude API connection error after %dms for job '%s': %s",
                latency_ms,
                job_data.get("title", "?"),
                exc,
            )
            return _fallback_analysis(str(exc), model)

        except APIStatusError as exc:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.error(
                "Claude API status %d after %dms for job '%s': %s",
                exc.status_code,
                latency_ms,
                job_data.get("title", "?"),
                exc.message,
            )
            return _fallback_analysis(f"HTTP {exc.status_code}: {exc.message}", model)

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.error(
                "Claude response parse error for job '%s': %s",
                job_data.get("title", "?"),
                exc,
            )
            return _fallback_analysis(f"Response parse error: {exc}", model)

        except Exception as exc:
            logger.exception(
                "Unexpected error in ClaudeProvider for job '%s'",
                job_data.get("title", "?"),
            )
            return _fallback_analysis(str(exc), model)

    async def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_analysis(self, data: dict, model: str) -> JobAnalysis:
        """Validate and convert the raw JSON dict into a JobAnalysis."""
        score = max(0, min(100, int(data["score"])))
        priority = str(data.get("priority", "Reject"))
        if priority not in ("P1", "P2", "P3", "Reject"):
            priority = "Reject"

        reasons = [str(r) for r in data.get("reasons", [])]
        pros    = [str(p) for p in data.get("pros",    [])]
        cons    = [str(c) for c in data.get("cons",    [])]

        visa_prob  = max(0, min(100, int(data.get("visa_probability", 0))))
        confidence = max(0, min(100, int(data.get("confidence", 50))))

        explanation = reasons[0] if reasons else f"Score: {score}/100"

        return JobAnalysis(
            score=score,
            priority=priority,
            explanation=explanation,
            reasons=reasons,
            pros=pros,
            cons=cons,
            visa_accredited_employer=bool(data.get("visa_accredited_employer", False)),
            visa_overseas_friendly=bool(data.get("visa_overseas_friendly", False)),
            visa_sponsorship_potential=bool(data.get("visa_sponsorship_potential", False)),
            visa_nz_rights_required=bool(data.get("visa_nz_rights_required", False)),
            visa_probability=visa_prob,
            confidence=confidence,
            provider="claude",
            model=model,
        )
