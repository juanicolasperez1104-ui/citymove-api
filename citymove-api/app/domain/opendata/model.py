from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    name: str
    publisher: str
    license: str
    rows_updated_at: datetime | None
    columns: tuple[str, ...]
