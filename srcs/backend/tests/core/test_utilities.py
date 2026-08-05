import time

import pytest

from app.core.utilities import retry_with_exponential_backoff


def test_retry_with_exponential_backoff_retries_until_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise RuntimeError("temporary failure")
        return "success"

    monkeypatch.setattr(time, "sleep", delays.append)
    result = retry_with_exponential_backoff(operation)

    assert result == "success"
    assert attempts == 4
    assert delays == [2, 4, 8]


def test_retry_with_exponential_backoff_reraises_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("permanent failure")

    monkeypatch.setattr(time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="permanent failure"):
        retry_with_exponential_backoff(operation)

    assert attempts == 4


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_retries": -1}, "max_retries"),
        ({"initial_delay_seconds": -1}, "initial_delay_seconds"),
        ({"backoff_multiplier": 0.5}, "backoff_multiplier"),
    ],
)
def test_retry_with_exponential_backoff_validates_configuration(
    kwargs: dict[str, float | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        retry_with_exponential_backoff(lambda: None, **kwargs)
