import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger("application")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int = 2,
    base_delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """Retry an async callable on transient failures, with linear backoff.

    Bounded — at most `retries` extra attempts (retries=2 means up to 3 total
    attempts), never infinite. Re-raises the last exception once exhausted.
    Only catches `exceptions`; anything else propagates immediately.
    """
    attempt = 0
    while True:
        try:
            return await fn()
        except exceptions as exc:
            attempt += 1
            if attempt > retries:
                logger.warning("%s failed after %d attempt(s), giving up: %s", label, attempt, exc)
                raise
            delay = base_delay * attempt
            logger.warning(
                "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                label, attempt, retries + 1, delay, exc,
            )
            await asyncio.sleep(delay)
