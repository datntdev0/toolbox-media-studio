"""Proxy-service clients for approved crawler fetches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx


@dataclass(slots=True)
class FlareSolverrResult:
    final_url: str
    status_code: int
    html: str
    headers: dict[str, str]
    user_agent: str | None


class FlareSolverrClient(Protocol):
    def get(self, url: str, max_timeout_ms: int | None = None) -> FlareSolverrResult: ...


class ProxyProvider(Protocol):
    """Proxy-service provider contract."""

    def get(self, url: str, max_timeout_ms: int | None = None) -> FlareSolverrResult: ...


class FlareSolverrError(RuntimeError):
    """Base error for FlareSolverr fetch failures."""


class FlareSolverrTimeoutError(FlareSolverrError):
    """Raised when the FlareSolverr request exceeds the configured timeout."""


class FlareSolverrBadResponseError(FlareSolverrError):
    """Raised when FlareSolverr returns a failed or malformed response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FlareSolverHttpClient:
    """Concrete HTTP service for FlareSolverr's `request.get` command."""

    def __init__(self, config: Any) -> None:
        self._base_url = self._normalize_base_url(_base_url(config))
        self._default_max_timeout_ms = _default_max_timeout_ms(config)
        self._client = httpx.Client()
        self._owns_client = True

    def get(self, url: str, max_timeout_ms: int | None = None) -> FlareSolverrResult:
        timeout_ms = self._default_max_timeout_ms if max_timeout_ms is None else max_timeout_ms
        if timeout_ms <= 0:
            raise ValueError("max_timeout_ms must be positive")

        payload: dict[str, object] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": timeout_ms,
            "disableMedia": True,
        }

        try:
            response = self._client.post(
                self._base_url,
                json=payload,
                timeout=httpx.Timeout((timeout_ms / 1000) + 10),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise FlareSolverrTimeoutError("FlareSolverr request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise FlareSolverrBadResponseError(
                "FlareSolverr returned an unsuccessful HTTP status",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise FlareSolverrBadResponseError("FlareSolverr request failed") from exc

        return self._parse_response(response)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FlareSolverHttpClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        self.close()

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if not normalized:
            raise ValueError("base_url must not be empty")
        return normalized if normalized.endswith("/v1") else f"{normalized}/v1"

    @staticmethod
    def _parse_response(response: httpx.Response) -> FlareSolverrResult:
        try:
            raw_data = response.json()
        except ValueError as exc:
            raise FlareSolverrBadResponseError("FlareSolverr returned invalid JSON") from exc

        if not isinstance(raw_data, dict):
            raise FlareSolverrBadResponseError("FlareSolverr returned unexpected JSON")

        data = cast(dict[str, Any], raw_data)
        if data.get("status") != "ok":
            message = data.get("message")
            detail = message if isinstance(message, str) and message else "FlareSolverr failed"
            raise FlareSolverrBadResponseError(detail)

        solution = data.get("solution")
        if not isinstance(solution, dict):
            raise FlareSolverrBadResponseError("FlareSolverr response is missing solution")

        html = solution.get("response")
        if not isinstance(html, str) or not html:
            raise FlareSolverrBadResponseError("FlareSolverr response is missing HTML")

        status_code = solution.get("status")
        if not isinstance(status_code, int):
            raise FlareSolverrBadResponseError("FlareSolverr response is missing status")

        final_url = solution.get("url")
        if not isinstance(final_url, str) or not final_url:
            raise FlareSolverrBadResponseError("FlareSolverr response is missing final URL")

        user_agent = solution.get("userAgent")
        if user_agent is not None and not isinstance(user_agent, str):
            raise FlareSolverrBadResponseError("FlareSolverr response has invalid user agent")

        return FlareSolverrResult(
            final_url=final_url,
            status_code=status_code,
            html=html,
            headers=_string_headers(solution.get("headers")),
            user_agent=user_agent,
        )


class FlareSolverProxyProvider:
    """Proxy provider backed by the concrete FlareSolver HTTP service."""

    def __init__(self, service: FlareSolverrClient) -> None:
        self._service = service

    def get(self, url: str, max_timeout_ms: int | None = None) -> FlareSolverrResult:
        return self._service.get(url, max_timeout_ms=max_timeout_ms)


def build_proxy_provider(config: Any) -> ProxyProvider:
    """Construct the default proxy provider."""

    return FlareSolverProxyProvider(service=FlareSolverHttpClient(config))


def _string_headers(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    return {str(key): str(header_value) for key, header_value in value.items()}


def _base_url(config: Any) -> str:
    flaresolverr = getattr(config, "flaresolverr", None)
    base_url = getattr(flaresolverr, "base_url", None)
    if base_url is None:
        base_url = getattr(config, "flaresolverr_base_url", "http://localhost:8191/v1")
    return str(base_url)


def _default_max_timeout_ms(config: Any) -> int:
    flaresolverr = getattr(config, "flaresolverr", None)
    timeout_ms = getattr(flaresolverr, "default_max_timeout_ms", None)
    if timeout_ms is None:
        timeout_ms = getattr(config, "flaresolverr_max_timeout_ms", 60000)
    return int(timeout_ms)
