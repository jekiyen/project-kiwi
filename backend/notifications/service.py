import logging
import time

from backend.notifications.base import (
    NotificationEvent,
    NotificationProvider,
    NotificationResult,
)
from backend.notifications.templates import format_message

logger = logging.getLogger("notifications")


class NotificationService:
    """Fans a NotificationEvent out to every registered provider.

    Business logic (routes, agents) builds an event and calls dispatch() —
    it never talks to a provider directly. A provider that isn't configured
    is skipped with a warning; a provider that errors is logged and does
    not affect the others. dispatch() itself never raises.
    """

    def __init__(self, providers: list[NotificationProvider]) -> None:
        self._providers = providers

    async def provider_statuses(self) -> dict[str, bool]:
        """Map of provider name -> is_configured(), for health/status display."""
        statuses: dict[str, bool] = {}
        for provider in self._providers:
            try:
                statuses[provider.name] = await provider.is_configured()
            except Exception:
                logger.exception("provider=%s is_configured() raised", provider.name)
                statuses[provider.name] = False
        return statuses

    async def dispatch(self, event: NotificationEvent) -> list[NotificationResult]:
        message = format_message(event)
        results: list[NotificationResult] = []

        for provider in self._providers:
            start = time.monotonic()
            try:
                configured = await provider.is_configured()
            except Exception as exc:
                configured = False
                logger.error(
                    "provider=%s event=%s is_configured() raised: %s",
                    provider.name, event.type.value, exc,
                )

            if not configured:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning(
                    "provider=%s event=%s success=False duration_ms=%d skipped=True (not configured)",
                    provider.name, event.type.value, duration_ms,
                )
                results.append(NotificationResult(
                    provider=provider.name,
                    event=event.type.value,
                    success=False,
                    duration_ms=duration_ms,
                    skipped=True,
                ))
                continue

            success = False
            error = None
            try:
                success = await provider.send(message)
            except Exception as exc:  # provider must never crash the caller
                error = str(exc)
                logger.error(
                    "provider=%s event=%s raised during send: %s",
                    provider.name, event.type.value, exc,
                )

            duration_ms = int((time.monotonic() - start) * 1000)
            log_fn = logger.info if success else logger.warning
            log_fn(
                "provider=%s event=%s success=%s duration_ms=%d%s",
                provider.name, event.type.value, success, duration_ms,
                f" error={error}" if error else "",
            )
            results.append(NotificationResult(
                provider=provider.name,
                event=event.type.value,
                success=success,
                duration_ms=duration_ms,
                error=error,
            ))

        return results
