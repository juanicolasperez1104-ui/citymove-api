"""Output port: how the Reports context expects to persist its aggregate."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.reports.model import Category, Report, Status


class ReportRepository(ABC):
    @abstractmethod
    def add(self, report: Report) -> Report: ...

    @abstractmethod
    def get(self, report_id: int) -> Report | None: ...

    @abstractmethod
    def list(self, status: Status | None = None, category: Category | None = None,
             skip: int = 0, limit: int = 50) -> list[Report]: ...

    @abstractmethod
    def update(self, report: Report) -> Report: ...

    @abstractmethod
    def delete(self, report_id: int) -> bool: ...
