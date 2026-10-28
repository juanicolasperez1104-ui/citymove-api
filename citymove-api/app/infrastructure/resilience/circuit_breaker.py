"""Circuit breaker with the three classic states.

CLOSED    -> calls pass; consecutive failures are counted.
OPEN      -> calls fail fast (CircuitOpenError) until recovery_timeout elapses.
HALF_OPEN -> a limited number of trial calls pass; one success closes the
             circuit, one failure opens it again.
"""
from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, name: str, retry_after: float):
        super().__init__(f"circuit '{name}' is open; retry in {retry_after:.1f}s")
        self.name = name
        self.retry_after = retry_after


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 1, clock: Callable[[], float] = time.monotonic,
                 counts_as_failure: Callable[[BaseException], bool] = lambda exc: True):
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._clock = clock
        self._counts_as_failure = counts_as_failure
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_calls = 0
        self.transitions: list[tuple[str, str]] = []  # audit trail, useful for demos/tests

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            self._maybe_half_open()
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(self.name, self._remaining())
            if self._state is CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(self.name, self.recovery_timeout)
                self._half_open_calls += 1
        try:
            result = fn()
        except BaseException as exc:
            if self._counts_as_failure(exc):
                self._on_failure()
            else:
                self._on_neutral()
            raise
        self._on_success()
        return result

    def snapshot(self) -> dict:
        state = self.state
        return {"name": self.name, "state": state.value, "failures": self._failures,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_s": self.recovery_timeout,
                "retry_after_s": round(self._remaining(), 1) if state is CircuitState.OPEN else 0}

    # -- internals (call with lock held unless noted) --
    def _remaining(self) -> float:
        return max(0.0, self.recovery_timeout - (self._clock() - self._opened_at))

    def _maybe_half_open(self) -> None:
        if self._state is CircuitState.OPEN and self._remaining() == 0:
            self._move_to(CircuitState.HALF_OPEN)
            self._half_open_calls = 0

    def _move_to(self, new: CircuitState) -> None:
        self.transitions.append((self._state.value, new.value))
        self._state = new

    def _on_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state is CircuitState.HALF_OPEN:
                self._move_to(CircuitState.CLOSED)

    def _on_neutral(self) -> None:
        # e.g. a 404: the provider is healthy, our question was just wrong
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._move_to(CircuitState.CLOSED)
            self._failures = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                if self._state is not CircuitState.OPEN:
                    self._move_to(CircuitState.OPEN)
                self._opened_at = self._clock()
