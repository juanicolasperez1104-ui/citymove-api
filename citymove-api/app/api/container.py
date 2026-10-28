"""Composition root: the only place that knows concrete adapters.

Everything is wired by constructor injection. Tests build a Container with
fakes/mocks and pass it to create_app()."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from app.application.open_data_service import OpenDataService
from app.application.ports import AnalyticsPort
from app.application.report_service import ReportService
from app.domain.opendata.ports import DatasetCatalogPort
from app.domain.reports.ports import ReportRepository
from app.domain.territory.ports import TerritorialDataPort
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker


@dataclass
class Container:
    repository: ReportRepository
    territory: TerritorialDataPort
    catalog: DatasetCatalogPort
    analytics: AnalyticsPort
    breakers: list[CircuitBreaker] = field(default_factory=list)

    @property
    def report_service(self) -> ReportService:
        return ReportService(self.repository, self.territory)

    @property
    def open_data_service(self) -> OpenDataService:
        return OpenDataService(self.territory, self.catalog, self.analytics, self.repository)


def build_production_container() -> Container:
    from app.infrastructure.analytics.duckdb_analytics import DuckDBAnalytics
    from app.infrastructure.opendata.catalog_adapter import DatosGovCatalogAdapter
    from app.infrastructure.opendata.divipola_adapter import DaneDivipolaAdapter
    from app.infrastructure.persistence.database import make_session_factory
    from app.infrastructure.persistence.sqlalchemy_report_repository import SqlAlchemyReportRepository
    from app.infrastructure.resilience.http_client import ResilientJsonClient, breaker_failure_rule
    from app.infrastructure.resilience.retry import RetryPolicy

    headers = {"Accept": "application/json"}
    token = os.getenv("DATOS_GOV_APP_TOKEN")  # optional Socrata app token
    if token:
        headers["X-App-Token"] = token
    http = httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))

    divipola_breaker = CircuitBreaker("dane-divipola", failure_threshold=3, recovery_timeout=30,
                                      counts_as_failure=breaker_failure_rule)
    catalog_breaker = CircuitBreaker("datosgov-catalog", failure_threshold=3, recovery_timeout=60,
                                     counts_as_failure=breaker_failure_rule)
    divipola = DaneDivipolaAdapter(ResilientJsonClient("DANE DIVIPOLA (datos.gov.co)", http,
                                                       divipola_breaker, RetryPolicy(), headers))
    catalog = DatosGovCatalogAdapter(ResilientJsonClient("datos.gov.co catalog", http,
                                                         catalog_breaker, RetryPolicy(), headers))
    sessions = make_session_factory(os.getenv("DATABASE_URL", "sqlite:///./citymove.db"))
    return Container(repository=SqlAlchemyReportRepository(sessions), territory=divipola,
                     catalog=catalog, analytics=DuckDBAnalytics(snapshot_dir="data/raw"),
                     breakers=[divipola_breaker, catalog_breaker])
