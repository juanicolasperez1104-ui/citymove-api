"""Adapter for DANE's DIVIPOLA municipality codes published on datos.gov.co.

Dataset: "DIVIPOLA- Códigos municipios" (id gdxc-w37w), owner DANE, licence
CC BY-SA 4.0. Endpoint (Socrata SODA): https://www.datos.gov.co/resource/gdxc-w37w.json
Fields verified on 2026-10-27 from https://www.datos.gov.co/api/views/gdxc-w37w:
cod_dpto, dpto, cod_mpio, nom_mpio, tipo_municipio, longitud, latitud.
Coordinates come as text with a decimal comma ("-73,308399").
Without $limit the endpoint returned a truncated list, so $limit is always sent.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from app.domain.shared.errors import ExternalDataUnavailable
from app.domain.territory.model import Municipality
from app.domain.territory.ports import TerritorialDataPort
from app.infrastructure.resilience.http_client import ResilientJsonClient

DIVIPOLA_URL = "https://www.datos.gov.co/resource/gdxc-w37w.json"
PAGE_LIMIT = 2000  # dataset has ~1,122 rows


def parse_coordinate(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def to_municipality(row: dict[str, Any]) -> Municipality:
    return Municipality(
        code=str(row["cod_mpio"]).zfill(5),
        name=row.get("nom_mpio", "").strip(),
        department_code=str(row["cod_dpto"]).zfill(2),
        department_name=row.get("dpto", "").strip(),
        kind=row.get("tipo_municipio", "").strip(),
        latitude=parse_coordinate(row.get("latitud")),
        longitude=parse_coordinate(row.get("longitud")),
    )


class DaneDivipolaAdapter(TerritorialDataPort):
    def __init__(self, client: ResilientJsonClient, url: str = DIVIPOLA_URL,
                 cache_ttl_s: float = 24 * 3600, clock: Callable[[], float] = time.monotonic):
        self._client = client
        self._url = url
        self._ttl = cache_ttl_s
        self._clock = clock
        self._cache: list[Municipality] | None = None
        self._cached_at = 0.0
        self.last_raw: list[dict[str, Any]] = []   # kept for DuckDB / JSON snapshot

    def list_municipalities(self) -> list[Municipality]:
        fresh = self._cache is not None and self._clock() - self._cached_at < self._ttl
        if fresh:
            return list(self._cache)  # type: ignore[arg-type]
        try:
            rows = self._client.get_json(self._url, {"$limit": PAGE_LIMIT, "$order": "cod_mpio"})
        except ExternalDataUnavailable:
            if self._cache is not None:   # stale-but-usable beats nothing
                return list(self._cache)
            raise
        if not isinstance(rows, list):
            raise ExternalDataUnavailable(self._client.source, "unexpected payload shape")
        self.last_raw = rows
        self._cache = [to_municipality(r) for r in rows if r.get("cod_mpio") and r.get("cod_dpto")]
        self._cached_at = self._clock()
        return list(self._cache)

    def get_municipality(self, code: str) -> Municipality | None:
        if self._cache is not None:
            return next((m for m in self._cache if m.code == code), None)
        rows = self._client.get_json(self._url, {"cod_mpio": code, "$limit": 1})
        if not isinstance(rows, list):
            raise ExternalDataUnavailable(self._client.source, "unexpected payload shape")
        return to_municipality(rows[0]) if rows else None
