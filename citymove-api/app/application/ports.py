"""Output ports owned by the application layer (not part of the business model)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from app.domain.reports.model import Report
from app.domain.territory.model import Municipality


class AnalyticsPort(ABC):
    @abstractmethod
    def load_municipalities(self, municipalities: list[Municipality]) -> int: ...

    @abstractmethod
    def load_reports(self, reports: list[Report]) -> int: ...

    @abstractmethod
    def municipalities_by_department(self, top: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def coordinate_stats_by_kind(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def reports_by_department(self) -> list[dict[str, Any]]: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, stored: str) -> bool: ...


class TokenPort(Protocol):
    ttl: int
    def issue(self, user_id: int, username: str, role: str) -> str: ...
    def decode(self, token: str) -> dict: ...
