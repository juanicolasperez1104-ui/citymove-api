"""Use cases that combine Colombian open data with CityMove reports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.ports import AnalyticsPort
from app.domain.opendata.model import DatasetMetadata
from app.domain.opendata.ports import DatasetCatalogPort
from app.domain.reports.ports import ReportRepository
from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.ports import TerritorialDataPort

DIVIPOLA_DATASET_ID = "gdxc-w37w"


@dataclass(frozen=True)
class RefreshResult:
    municipalities_loaded: int
    reports_loaded: int
    source: DatasetMetadata | None


class OpenDataService:
    def __init__(self, territory: TerritorialDataPort, catalog: DatasetCatalogPort,
                 analytics: AnalyticsPort, reports: ReportRepository):
        self._territory = territory
        self._catalog = catalog
        self._analytics = analytics
        self._reports = reports

    def refresh(self) -> RefreshResult:
        """Pull DIVIPOLA, load it with the current reports into DuckDB.
        ExternalDataUnavailable from the territory port propagates on purpose:
        without municipalities there is nothing to analyse."""
        municipalities = self._territory.list_municipalities()
        loaded = self._analytics.load_municipalities(municipalities)
        reports = self._reports.list(skip=0, limit=10_000)
        loaded_reports = self._analytics.load_reports(reports)
        return RefreshResult(loaded, loaded_reports, self.source_metadata())

    def source_metadata(self) -> DatasetMetadata | None:
        """Provenance is nice to have: if the catalog is down we still answer."""
        try:
            return self._catalog.get_metadata(DIVIPOLA_DATASET_ID)
        except ExternalDataUnavailable:
            return None

    def municipalities_by_department(self, top: int = 10) -> list[dict[str, Any]]:
        return self._analytics.municipalities_by_department(top)

    def coordinate_stats(self) -> list[dict[str, Any]]:
        return self._analytics.coordinate_stats_by_kind()

    def reports_by_department(self) -> list[dict[str, Any]]:
        self._analytics.load_reports(self._reports.list(skip=0, limit=10_000))
        return self._analytics.reports_by_department()
