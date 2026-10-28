"""Adapter for the datos.gov.co dataset metadata API (Socrata "views" API).

Endpoint verified on 2026-10-27: https://www.datos.gov.co/api/views/{dataset_id}
Used to show provenance in CityMove: publisher (attribution), licence,
last data update (rowsUpdatedAt, epoch seconds) and column names.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.opendata.model import DatasetMetadata
from app.domain.opendata.ports import DatasetCatalogPort
from app.domain.shared.errors import ExternalDataUnavailable
from app.infrastructure.resilience.http_client import ResilientJsonClient

VIEWS_URL = "https://www.datos.gov.co/api/views/{dataset_id}"


class DatosGovCatalogAdapter(DatasetCatalogPort):
    def __init__(self, client: ResilientJsonClient, url_template: str = VIEWS_URL):
        self._client = client
        self._url = url_template
        self._cache: dict[str, DatasetMetadata] = {}

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        if dataset_id in self._cache:
            return self._cache[dataset_id]
        data = self._client.get_json(self._url.format(dataset_id=dataset_id))
        if not isinstance(data, dict) or "id" not in data:
            raise ExternalDataUnavailable(self._client.source, "unexpected payload shape")
        updated = data.get("rowsUpdatedAt")
        meta = DatasetMetadata(
            dataset_id=data["id"],
            name=data.get("name", ""),
            publisher=data.get("attribution") or data.get("owner", {}).get("displayName", ""),
            license=(data.get("license") or {}).get("name", data.get("licenseId", "")),
            rows_updated_at=datetime.fromtimestamp(updated, tz=timezone.utc) if updated else None,
            columns=tuple(c.get("fieldName", "") for c in data.get("columns", [])),
        )
        self._cache[dataset_id] = meta
        return meta
