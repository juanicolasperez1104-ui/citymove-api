"""HTTP JSON client = timeout + retry (inner) + circuit breaker (outer).

The breaker wraps the whole retry sequence: one logical request counts as one
success or one failure, and when the circuit is open no retries are attempted.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.domain.shared.errors import ExternalDataUnavailable
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.infrastructure.resilience.retry import PermanentError, RetryPolicy, TransientError

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ResilientJsonClient:
    def __init__(self, source: str, http: httpx.Client, breaker: CircuitBreaker,
                 retry: RetryPolicy, headers: dict[str, str] | None = None):
        self.source = source
        self._http = http
        self.breaker = breaker
        self._retry = retry
        self._headers = headers or {}

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return self.breaker.call(lambda: self._retry.run(lambda: self._once(url, params)))
        except CircuitOpenError as exc:
            raise ExternalDataUnavailable(self.source, "circuit open", exc.retry_after) from exc
        except TransientError as exc:
            raise ExternalDataUnavailable(self.source, str(exc), exc.retry_after) from exc
        except PermanentError as exc:  # not retried; caller decides what it means
            raise ExternalDataUnavailable(self.source, str(exc)) from exc

    def _once(self, url: str, params: dict[str, Any] | None) -> Any:
        try:
            resp = self._http.get(url, params=params, headers=self._headers)
        except httpx.TimeoutException as exc:
            raise TransientError(f"timeout calling {url}") from exc
        except httpx.TransportError as exc:
            raise TransientError(f"network error: {exc.__class__.__name__}") from exc
        if resp.status_code in RETRYABLE_STATUS:
            raise TransientError(f"HTTP {resp.status_code}", _retry_after(resp))
        if resp.status_code >= 400:
            raise PermanentError(f"HTTP {resp.status_code} from {self.source}")
        try:
            return resp.json()
        except ValueError as exc:
            raise PermanentError(f"{self.source} returned a non-JSON body") from exc


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def breaker_failure_rule(exc: BaseException) -> bool:
    """Which exceptions should open the circuit. A 404/400 means the provider is
    up; a non-JSON 200 (maintenance page) means it is not behaving."""
    if isinstance(exc, PermanentError):
        return "non-JSON" in str(exc)
    return True
