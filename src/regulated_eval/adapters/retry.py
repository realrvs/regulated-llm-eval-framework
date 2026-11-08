"""Retry policy with exponential backoff for LLM adapters.

Covers FR-003, NFR-008, TM-07.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from tenacity import (
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from regulated_eval.exceptions import RateLimitExhausted

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when provider returns rate limit (HTTP 429)."""


def _should_retry(retry_state: RetryCallState) -> bool:
    """Determine if we should retry based on the exception."""
    if retry_state.outcome is None:
        return False
    exc = retry_state.outcome.exception()
    if exc is None:
        return False
    # Retry on rate limit or connection errors
    return isinstance(exc, (RateLimitError, ConnectionError, TimeoutError))


def get_retry_decorator(
    max_retries: int = 5,
    base_delay_ms: int = 1000,
    max_delay_ms: int = 30000,
) -> Callable:
    """Create a tenacity retry decorator for LLM calls.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay_ms: Base delay in milliseconds for exponential backoff.
        max_delay_ms: Maximum delay in milliseconds.

    Returns:
        Tenacity retry decorator.
    """
    from tenacity import retry as tenacity_retry  # noqa: PLC0415

    return tenacity_retry(
        retry=retry_if_exception_type((RateLimitError, ConnectionError, TimeoutError)),
        wait=wait_exponential(
            multiplier=base_delay_ms / 1000.0,
            min=base_delay_ms / 1000.0,
            max=max_delay_ms / 1000.0,
        ),
        stop=stop_after_attempt(max_retries),
        after=lambda state: logger.warning(
            "Retry %d/%d after %.1fs delay: %s",
            state.attempt_number,
            max_retries,
            state.next_action.sleep if state.next_action else 0,
            state.outcome.exception() if state.outcome else None,
        ),
        reraise=True,
    )


async def retry_with_backoff(
    func: Callable,
    *args: Any,
    max_retries: int = 5,
    base_delay_ms: int = 1000,
    max_delay_ms: int = 30000,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff retry.

    Args:
        func: Async function to execute.
        *args: Positional arguments for the function.
        max_retries: Maximum number of retry attempts.
        base_delay_ms: Base delay in milliseconds.
        max_delay_ms: Maximum delay in milliseconds.
        **kwargs: Keyword arguments for the function.

    Returns:
        Result of the function call.

    Raises:
        RateLimitExhausted: If all retry attempts are exhausted.
    """
    retry_dec = get_retry_decorator(
        max_retries=max_retries,
        base_delay_ms=base_delay_ms,
        max_delay_ms=max_delay_ms,
    )

    try:
        return await retry_dec(func)(*args, **kwargs)
    except Exception as e:
        raise RateLimitExhausted(f"All {max_retries} retry attempts exhausted. Last error: {e}") from e


def check_rate_limit(response: Any) -> None:
    """Check if a response indicates rate limiting.

    Args:
        response: HTTP response or similar object with status_code attribute.

    Raises:
        RateLimitError: If status code is 429.
    """
    if hasattr(response, "status_code") and response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "1")
        logger.warning("Rate limit hit (429), Retry-After: %s", retry_after)
        raise RateLimitError(f"Rate limited. Retry-After: {retry_after}")
