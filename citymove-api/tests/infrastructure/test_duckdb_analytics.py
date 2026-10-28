from app.domain.reports.model import Category, Priority, Report, Status
from app.infrastructure.analytics.duckdb_analytics import DuckDBAnalytics
from tests.conftest import FIXTURE


def test_loads_raw_json_with_read_json(tmp_path):
    db = DuckDBAnalytics(snapshot_dir=tmp_path)
    assert db.load_municipalities_json(FIXTURE) == 11


def test_query1_municipalities_by_department(tmp_path):
    db = DuckDBAnalytics(snapshot_dir=tmp_path)
    db.load_municipalities_json(FIXTURE)
    rows = db.municipalities_by_department(top=40)
    assert rows[0]["department_name"] == "ANTIOQUIA" and rows[0]["municipalities"] == 3
    assert round(sum(r["pct_of_country"] for r in rows)) == 100
    assert db.municipalities_by_department(top=2)[1]["municipalities"] == 2


def test_query2_descriptive_statistics_by_kind(tmp_path):
    db = DuckDBAnalytics(snapshot_dir=tmp_path)
    db.load_municipalities_json(FIXTURE)
    stats = {r["kind"]: r for r in db.coordinate_stats_by_kind()}
    assert stats["Municipio"]["n"] == 8 and stats["Área no municipalizada"]["n"] == 2
    m = stats["Municipio"]
    assert m["lat_min"] <= m["lat_q1"] <= m["lat_median"] <= m["lat_q3"] <= m["lat_max"]
    assert m["lat_min"] == -4.2 and m["lat_max"] == 7.12


def test_query3_joins_reports_with_divipola(tmp_path, fake_territory):
    db = DuckDBAnalytics(snapshot_dir=tmp_path)
    db.load_municipalities(fake_territory.items)
    base = dict(description="test report text", address="x", latitude=4.6, longitude=-74.1,
                category=Category.POTHOLE, title="Report title")
    db.load_reports([
        Report(id=1, municipality_code="11001", municipality_verified=True,
               priority=Priority.HIGH, **base),
        Report(id=2, municipality_code="11001", municipality_verified=True,
               status=Status.RESOLVED, **base),
        Report(id=3, municipality_code="68001", municipality_verified=False, **base),
    ])
    rows = {r["department_name"]: r for r in db.reports_by_department()}
    assert rows["BOGOTÁ, D.C."]["reports"] == 2 and rows["BOGOTÁ, D.C."]["high_priority"] == 1
    assert rows["BOGOTÁ, D.C."]["pct_resolved"] == 50.0
    assert rows["SIN MUNICIPIO VERIFICADO"]["reports"] == 1
