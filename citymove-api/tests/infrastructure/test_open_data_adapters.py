"""Adapters tested against httpx.MockTransport (no network). Response bodies use
the field names verified on the real endpoints."""
import httpx
import pytest

from app.domain.shared.errors import ExternalDataUnavailable
from app.infrastructure.opendata.catalog_adapter import DatosGovCatalogAdapter
from app.infrastructure.opendata.divipola_adapter import DaneDivipolaAdapter, parse_coordinate
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitState
from app.infrastructure.resilience.http_client import ResilientJsonClient, breaker_failure_rule
from app.infrastructure.resilience.retry import RetryPolicy


def build(handler, threshold=3):
    calls = []

    def recording(request):
        calls.append(request)
        return handler(request, len(calls))

    breaker = CircuitBreaker("divipola", failure_threshold=threshold, recovery_timeout=30,
                             counts_as_failure=breaker_failure_rule)
    client = ResilientJsonClient("DANE DIVIPOLA", httpx.Client(transport=httpx.MockTransport(recording)),
                                 breaker, RetryPolicy(max_attempts=3, sleep=lambda s: None))
    return client, breaker, calls


def test_parses_decimal_comma_and_sends_limit(divipola_rows):
    client, _, calls = build(lambda req, n: httpx.Response(200, json=divipola_rows))
    items = DaneDivipolaAdapter(client).list_municipalities()
    assert len(items) == len(divipola_rows)
    bogota = next(m for m in items if m.code == "11001")
    assert bogota.latitude == pytest.approx(4.65) and bogota.longitude == pytest.approx(-74.10)
    assert calls[0].url.params["$limit"] == "2000"


@pytest.mark.parametrize("raw,expected", [("-73,308399", -73.308399), ("4.5", 4.5),
                                          ("", None), (None, None), ("n/a", None)])
def test_parse_coordinate(raw, expected):
    assert parse_coordinate(raw) == expected


def test_transient_503_is_retried_until_success(divipola_rows):
    def handler(req, n):
        return httpx.Response(503) if n < 3 else httpx.Response(200, json=divipola_rows[:1])
    client, breaker, calls = build(handler)
    assert DaneDivipolaAdapter(client).get_municipality("05001").name == "MEDELLÍN"
    assert len(calls) == 3 and breaker.state is CircuitState.CLOSED


def test_404_is_not_retried_and_does_not_open_circuit():
    client, breaker, calls = build(lambda req, n: httpx.Response(404), threshold=1)
    with pytest.raises(ExternalDataUnavailable):
        DaneDivipolaAdapter(client).get_municipality("05001")
    assert len(calls) == 1 and breaker.state is CircuitState.CLOSED


def test_repeated_timeouts_open_the_circuit_and_then_fail_fast():
    def handler(req, n):
        raise httpx.ReadTimeout("slow", request=req)
    client, breaker, calls = build(handler, threshold=2)
    adapter = DaneDivipolaAdapter(client)
    for _ in range(2):
        with pytest.raises(ExternalDataUnavailable):
            adapter.get_municipality("05001")
    assert breaker.state is CircuitState.OPEN and len(calls) == 6   # 2 logical calls x 3 attempts
    with pytest.raises(ExternalDataUnavailable) as exc:
        adapter.get_municipality("05001")
    assert exc.value.reason == "circuit open" and len(calls) == 6   # no HTTP call made


def test_non_json_body_counts_as_failure_but_is_not_retried():
    client, breaker, calls = build(lambda req, n: httpx.Response(200, text="<html>maintenance"),
                                   threshold=1)
    with pytest.raises(ExternalDataUnavailable):
        DaneDivipolaAdapter(client).get_municipality("05001")
    assert len(calls) == 1 and breaker.state is CircuitState.OPEN


def test_stale_cache_is_served_when_source_goes_down(divipola_rows):
    state = {"down": False}

    def handler(req, n):
        return httpx.Response(503) if state["down"] else httpx.Response(200, json=divipola_rows)
    t = {"now": 0.0}
    client, _, _ = build(handler)
    adapter = DaneDivipolaAdapter(client, cache_ttl_s=10, clock=lambda: t["now"])
    first = adapter.list_municipalities()
    state["down"], t["now"] = True, 100.0          # cache expired and source down
    assert adapter.list_municipalities() == first


def test_catalog_metadata_is_parsed():
    # subset of the real payload of https://www.datos.gov.co/api/views/gdxc-w37w (2026-10-27)
    payload = {"id": "gdxc-w37w", "name": "DIVIPOLA- Códigos municipios",
               "attribution": "Departamento Administrativo Nacional de Estadística - DANE",
               "rowsUpdatedAt": 1737751472,
               "license": {"name": "Creative Commons Attribution | Share Alike 4.0 International"},
               "columns": [{"fieldName": "cod_dpto"}, {"fieldName": "dpto"},
                           {"fieldName": "cod_mpio"}, {"fieldName": "nom_mpio"},
                           {"fieldName": "tipo_municipio"}, {"fieldName": "longitud"},
                           {"fieldName": "latitud"}]}
    client, _, calls = build(lambda req, n: httpx.Response(200, json=payload))
    adapter = DatosGovCatalogAdapter(client)
    meta = adapter.get_metadata("gdxc-w37w")
    adapter.get_metadata("gdxc-w37w")                      # cached
    assert meta.publisher.endswith("DANE") and meta.rows_updated_at.year == 2025
    assert "cod_mpio" in meta.columns and len(calls) == 1
    assert calls[0].url.path == "/api/views/gdxc-w37w"
