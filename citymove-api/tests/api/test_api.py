"""End-to-end through FastAPI: router -> service -> SQLite repository / DuckDB.
External APIs replaced by in-memory fakes injected through the Container."""
import pytest
from fastapi.testclient import TestClient

from app.api.container import Container
from app.infrastructure.analytics.duckdb_analytics import DuckDBAnalytics
from app.infrastructure.persistence.database import make_session_factory
from app.infrastructure.persistence.sqlalchemy_report_repository import SqlAlchemyReportRepository
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker
from app.main import create_app
from tests.conftest import FakeCatalog

PAYLOAD = {"title": "Pothole on Av. Boyaca", "description": "A cyclist fell into it yesterday",
           "category": "pothole", "address": "Av. Boyaca con calle 80",
           "latitude": 4.69, "longitude": -74.09, "municipality_code": "11001",
           "priority": "high"}


@pytest.fixture
def setup(tmp_path, fake_territory):
    repo = SqlAlchemyReportRepository(make_session_factory("sqlite://"))
    breaker = CircuitBreaker("dane-divipola")
    container = Container(repo, fake_territory, FakeCatalog(),
                          DuckDBAnalytics(snapshot_dir=tmp_path), [breaker])
    return TestClient(create_app(container)), fake_territory


def test_crud_flow(setup):
    client, _ = setup
    r = client.post("/api/v1/reports", json=PAYLOAD)
    assert r.status_code == 201 and r.headers["location"] == "/api/v1/reports/1"
    assert r.json()["municipality_verified"] is True
    assert client.put("/api/v1/reports/1", json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert len(client.get("/api/v1/reports", params={"category": "pothole"}).json()) == 1
    assert client.delete("/api/v1/reports/1").status_code == 204
    body = client.get("/api/v1/reports/1").json()
    assert body == {"status": 404, "error": "Not Found", "detail": "Report 1 was not found",
                    "path": "/api/v1/reports/1"}


def test_unknown_municipality_is_rejected(setup):
    client, _ = setup
    r = client.post("/api/v1/reports", json={**PAYLOAD, "municipality_code": "99999"})
    assert r.status_code == 422 and "99999" in r.json()["detail"]


def test_report_is_kept_when_divipola_is_down(setup):
    client, territory = setup
    territory.down = True
    r = client.post("/api/v1/reports", json=PAYLOAD)
    assert r.status_code == 201 and r.json()["municipality_verified"] is False


def test_invalid_transition_returns_409(setup):
    client, _ = setup
    client.post("/api/v1/reports", json=PAYLOAD)
    assert client.put("/api/v1/reports/1", json={"status": "resolved"}).status_code == 409


def test_validation_and_empty_update(setup):
    client, _ = setup
    bad = client.post("/api/v1/reports", json={**PAYLOAD, "latitude": 120})
    assert bad.status_code == 422 and bad.json()["detail"][0]["field"] == "latitude"
    client.post("/api/v1/reports", json=PAYLOAD)
    assert client.put("/api/v1/reports/1", json={}).status_code == 400


def test_open_data_refresh_and_analytics(setup):
    client, _ = setup
    client.post("/api/v1/reports", json=PAYLOAD)
    refreshed = client.post("/api/v1/open-data/refresh").json()
    assert refreshed["municipalities_loaded"] == 11 and refreshed["reports_loaded"] == 1
    assert refreshed["source"]["dataset_id"] == "gdxc-w37w"
    top = client.get("/api/v1/analytics/municipalities-by-department", params={"top": 3}).json()
    assert top[0]["department_name"] == "ANTIOQUIA"
    assert client.get("/api/v1/analytics/coordinate-stats").status_code == 200
    by_dept = client.get("/api/v1/analytics/reports-by-department").json()
    assert by_dept[0]["department_name"] == "BOGOTÁ, D.C." and by_dept[0]["high_priority"] == 1


def test_municipality_lookup_and_outage(setup):
    client, territory = setup
    assert client.get("/api/v1/territory/municipalities/85001").json()["name"] == "YOPAL"
    assert client.get("/api/v1/territory/municipalities/00000").status_code == 404
    territory.down = True
    r = client.get("/api/v1/territory/municipalities/85001")
    assert r.status_code == 503 and r.headers["retry-after"] == "31"


def test_dashboard_and_breaker_health(setup):
    client, _ = setup
    client.post("/api/v1/open-data/refresh")
    html = client.get("/dashboard").text
    assert "<svg" in html and "ANTIOQUIA" in html and "CLOSED" in html
    assert client.get("/api/v1/health/integrations").json()[0]["state"] == "closed"


def test_openapi_documents_all_operations(setup):
    client, _ = setup
    paths = client.get("/openapi.json").json()["paths"]
    ops = [(m, p) for p, item in paths.items() for m, op in item.items()]
    assert len(ops) >= 12
    assert all(paths[p][m].get("summary") for m, p in ops)
