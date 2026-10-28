"""Driven adapter: implements the ReportRepository port with SQLAlchemy 2.0.
Mapping between ORM rows and domain objects happens only here."""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import select

from app.domain.reports.model import Category, Priority, Report, Status
from app.domain.reports.ports import ReportRepository
from app.infrastructure.persistence.orm import ReportRow


def _to_domain(row: ReportRow) -> Report:
    created = row.created_at
    if created.tzinfo is None:  # SQLite drops the offset; values are stored in UTC
        created = created.replace(tzinfo=timezone.utc)
    return Report(id=row.id, title=row.title, description=row.description,
                  category=Category(row.category), address=row.address,
                  latitude=row.latitude, longitude=row.longitude,
                  municipality_code=row.municipality_code,
                  municipality_verified=row.municipality_verified,
                  status=Status(row.status),
                  priority=Priority(row.priority) if row.priority else None,
                  created_at=created)


def _fill(row: ReportRow, r: Report) -> None:
    row.title, row.description, row.category = r.title, r.description, r.category.value
    row.address, row.latitude, row.longitude = r.address, r.latitude, r.longitude
    row.municipality_code, row.municipality_verified = r.municipality_code, r.municipality_verified
    row.status = r.status.value
    row.priority = r.priority.value if r.priority else None
    row.created_at = r.created_at.astimezone(timezone.utc)


class SqlAlchemyReportRepository(ReportRepository):
    def __init__(self, session_factory):
        self._sessions = session_factory

    def add(self, report: Report) -> Report:
        with self._sessions() as s:
            row = ReportRow()
            _fill(row, report)
            s.add(row)
            s.commit()
            s.refresh(row)
            return _to_domain(row)

    def get(self, report_id: int) -> Report | None:
        with self._sessions() as s:
            row = s.get(ReportRow, report_id)
            return _to_domain(row) if row else None

    def list(self, status=None, category=None, skip=0, limit=50) -> list[Report]:
        stmt = select(ReportRow).order_by(ReportRow.id)
        if status is not None:
            stmt = stmt.where(ReportRow.status == status.value)
        if category is not None:
            stmt = stmt.where(ReportRow.category == category.value)
        with self._sessions() as s:
            return [_to_domain(r) for r in s.scalars(stmt.offset(skip).limit(limit))]

    def update(self, report: Report) -> Report:
        with self._sessions() as s:
            row = s.get(ReportRow, report.id)
            _fill(row, report)
            s.commit()
            s.refresh(row)
            return _to_domain(row)

    def delete(self, report_id: int) -> bool:
        with self._sessions() as s:
            row = s.get(ReportRow, report_id)
            if row is None:
                return False
            s.delete(row)
            s.commit()
            return True
