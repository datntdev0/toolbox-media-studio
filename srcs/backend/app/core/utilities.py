import time
from collections.abc import Callable


def retry_with_exponential_backoff[T](
    operation: Callable[[], T],
    *,
    max_retries: int = 3,
    initial_delay_seconds: float = 2.0,
    backoff_multiplier: float = 2.0,
) -> T:
    """Run an operation again after failures, increasing the delay between attempts."""
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds must be non-negative")
    if backoff_multiplier < 1:
        raise ValueError("backoff_multiplier must be at least 1")

    delay_seconds = initial_delay_seconds
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(delay_seconds)
            delay_seconds *= backoff_multiplier

    raise RuntimeError("Retry operation did not return or raise")
