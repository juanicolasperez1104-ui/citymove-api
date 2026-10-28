from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.opendata.model import DatasetMetadata


class DatasetCatalogPort(ABC):
    """Provenance of the open datasets used by CityMove (who publishes them,
    licence and freshness)."""

    @abstractmethod
    def get_metadata(self, dataset_id: str) -> DatasetMetadata: ...
