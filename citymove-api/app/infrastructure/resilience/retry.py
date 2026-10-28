"""Retry with exponential backoff and full jitter."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    """Worth retrying: timeouts, connection errors, HTTP 429 and 5xx."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(Exception):
    """Never retried: 4xx (except 429), malformed payloads."""


@dataclass
class RetryPolicy:
    max_attempts: int = 3          # total attempts, including the first one
    base_delay: float = 0.5        # seconds
    max_delay: float = 8.0
    sleep: Callable[[float], None] = time.sleep
    rand: Callable[[], float] = random.random
    delays: list[float] = field(default_factory=list)  # what was actually waited

    def backoff(self, attempt: int) -> float:
        """attempt starts at 1. Ceiling grows 0.5, 1, 2, 4... capped at max_delay;
        full jitter picks a value in [0, ceiling] to avoid synchronized retries."""
        ceiling = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        return ceiling * self.rand()

    def run(self, fn: Callable[[], T]) -> T:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn()
            except TransientError as exc:
                if attempt == self.max_attempts:
                    raise
                delay = self.backoff(attempt)
                if exc.retry_after is not None:  # respect the server, but cap it
                    delay = min(max(delay, exc.retry_after), self.max_delay)
                self.delays.append(delay)
                self.sleep(delay)
        raise AssertionError("unreachable")
