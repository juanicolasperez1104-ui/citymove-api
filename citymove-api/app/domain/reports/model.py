"""Reports bounded context: the citizen report aggregate."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum

from app.domain.reports.errors import InvalidReport, InvalidStatusTransition


class Category(str, Enum):
    POTHOLE = "pothole"
    STREETLIGHT = "streetlight"
    SIDEWALK = "sidewalk"
    DRAINAGE = "drainage"
    SIGNAGE = "signage"
    OTHER = "other"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Allowed lifecycle of a report. Resolved and rejected are terminal states.
_TRANSITIONS: dict[Status, set[Status]] = {
    Status.OPEN: {Status.IN_PROGRESS, Status.REJECTED},
    Status.IN_PROGRESS: {Status.RESOLVED, Status.OPEN},
    Status.RESOLVED: set(),
    Status.REJECTED: set(),
}


@dataclass(frozen=True)
class Report:
    title: str
    description: str
    category: Category
    address: str
    latitude: float
    longitude: float
    municipality_code: str | None = None
    municipality_verified: bool = False
    status: Status = Status.OPEN
    priority: Priority | None = None
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if len(self.title.strip()) < 5:
            raise InvalidReport("title", "must have at least 5 characters")
        if not -90 <= self.latitude <= 90:
            raise InvalidReport("latitude", "must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise InvalidReport("longitude", "must be between -180 and 180")
        code = self.municipality_code
        if code is not None and (len(code) != 5 or not code.isdigit()):
            raise InvalidReport("municipality_code", "must be a 5-digit DIVIPOLA code")

    def change_status(self, new_status: Status) -> "Report":
        if new_status == self.status:
            return self
        if new_status not in _TRANSITIONS[self.status]:
            raise InvalidStatusTransition(self.status.value, new_status.value)
        return replace(self, status=new_status)

    def with_changes(self, **changes) -> "Report":
        status = changes.pop("status", None)
        updated = replace(self, **changes)  # re-runs __post_init__ validation
        return updated.change_status(status) if status is not None else updated
