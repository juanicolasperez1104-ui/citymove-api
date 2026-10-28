from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.territory.model import Municipality


class TerritorialDataPort(ABC):
    """Source of official territorial data. Implementations may call DANE data
    published on datos.gov.co, read a local file or return fixtures."""

    @abstractmethod
    def get_municipality(self, code: str) -> Municipality | None: ...

    @abstractmethod
    def list_municipalities(self) -> list[Municipality]: ...
