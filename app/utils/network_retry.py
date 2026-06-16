"""
Network retry decorator using tenacity for resilient external API calls.
"""

import logging
from typing import Callable, TypeVar, Any
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Exceptions considered transient / retryable
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import httpx
    RETRYABLE_EXCEPTIONS = (
        *RETRYABLE_EXCEPTIONS,
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadTimeout,
    )
except ImportError:
    pass


F = TypeVar("F", bound=Callable[..., Any])


def network_retry(
    max_retries: int = 3,
    wait_seconds: float = 2.0,
) -> Callable[[F], F]:
    """
    Decorator that wraps an async function with exponential-backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts.
        wait_seconds: Base wait time in seconds (multiplied exponentially).

    Usage:
        @network_retry(max_retries=3, wait_seconds=2.0)
        async def call_external_api():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(
                multiplier=wait_seconds, min=wait_seconds, max=30
            ),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]
    return decorator  # type: ignore[return-value]
