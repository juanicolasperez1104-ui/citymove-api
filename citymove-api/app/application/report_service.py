"""Use cases of the Reports bounded context."""
from __future__ import annotations

import logging

from app.domain.reports.errors import ReportNotFound, UnknownMunicipality
from app.domain.reports.model import Category, Report, Status
from app.domain.reports.ports import ReportRepository
from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.ports import TerritorialDataPort

log = logging.getLogger(__name__)


class ReportService:
    """Dependencies arrive through the constructor, so tests can pass mocks
    and production code passes the SQLAlchemy and DIVIPOLA adapters."""

    def __init__(self, repository: ReportRepository, territory: TerritorialDataPort):
        self._repository = repository
        self._territory = territory

    def create(self, report: Report) -> Report:
        return self._repository.add(self._verify_municipality(report))

    def get(self, report_id: int) -> Report:
        report = self._repository.get(report_id)
        if report is None:
            raise ReportNotFound(report_id)
        return report

    def list(self, status: Status | None = None, category: Category | None = None,
             skip: int = 0, limit: int = 50) -> list[Report]:
        return self._repository.list(status=status, category=category, skip=skip, limit=limit)

    def update(self, report_id: int, **changes) -> Report:
        current = self.get(report_id)
        updated = current.with_changes(**changes)
        if "municipality_code" in changes:
            updated = self._verify_municipality(updated)
        return self._repository.update(updated)

    def delete(self, report_id: int) -> None:
        if not self._repository.delete(report_id):
            raise ReportNotFound(report_id)

    def _verify_municipality(self, report: Report) -> Report:
        """Business rule: a municipality code must exist in DIVIPOLA.

        If the open-data source is down, the citizen report is NOT lost: it is
        stored with municipality_verified=False so it can be re-checked later.
        A code that the source answers as non-existent is rejected.
        """
        if report.municipality_code is None:
            return report.with_changes(municipality_verified=False)
        try:
            municipality = self._territory.get_municipality(report.municipality_code)
        except ExternalDataUnavailable as exc:
            log.warning("DIVIPOLA check skipped: %s", exc)
            return report.with_changes(municipality_verified=False)
        if municipality is None:
            raise UnknownMunicipality(report.municipality_code)
        return report.with_changes(municipality_verified=True)
