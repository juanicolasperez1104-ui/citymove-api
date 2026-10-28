from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.opendata.model import DatasetMetadata
from app.domain.opendata.ports import DatasetCatalogPort
from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.ports import TerritorialDataPort
from app.infrastructure.opendata.divipola_adapter import to_municipality

FIXTURE = Path(__file__).parent / "fixtures" / "divipola_sample.json"


@pytest.fixture
def divipola_rows() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FakeTerritory(TerritorialDataPort):
    """In-memory territory port; `down=True` simulates an outage."""

    def __init__(self, rows: list[dict]):
        self.items = [to_municipality(r) for r in rows]
        self.down = False

    def _check(self):
        if self.down:
            raise ExternalDataUnavailable("fake divipola", "simulated outage", retry_after=30)

    def get_municipality(self, code):
        self._check()
        return next((m for m in self.items if m.code == code), None)

    def list_municipalities(self):
        self._check()
        return list(self.items)


class FakeCatalog(DatasetCatalogPort):
    def get_metadata(self, dataset_id):
        return DatasetMetadata(dataset_id, "DIVIPOLA- Códigos municipios",
                               "Departamento Administrativo Nacional de Estadística - DANE",
                               "CC BY-SA 4.0", None, ("cod_dpto", "cod_mpio"))


@pytest.fixture
def fake_territory(divipola_rows):
    return FakeTerritory(divipola_rows)
