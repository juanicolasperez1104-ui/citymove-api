"""DuckDB adapter: loads the DIVIPOLA JSON snapshot and CityMove reports and
runs the analytical SQL used by the dashboard."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from app.application.ports import AnalyticsPort
from app.domain.reports.model import Report
from app.domain.territory.model import Municipality

Q_MUNICIPALITIES_BY_DEPARTMENT = """
SELECT department_code, department_name,
       COUNT(*)                                            AS municipalities,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_country,
       ROUND(AVG(latitude), 4)                             AS avg_latitude,
       ROUND(AVG(longitude), 4)                            AS avg_longitude
FROM municipalities
GROUP BY department_code, department_name
ORDER BY municipalities DESC, department_code
LIMIT ?
"""

Q_COORDINATE_STATS_BY_KIND = """
SELECT kind,
       COUNT(*)                                   AS n,
       ROUND(MIN(latitude), 4)                    AS lat_min,
       ROUND(quantile_cont(latitude, 0.25), 4)    AS lat_q1,
       ROUND(median(latitude), 4)                 AS lat_median,
       ROUND(AVG(latitude), 4)                    AS lat_mean,
       ROUND(quantile_cont(latitude, 0.75), 4)    AS lat_q3,
       ROUND(MAX(latitude), 4)                    AS lat_max,
       ROUND(stddev_samp(latitude), 4)            AS lat_std
FROM municipalities
WHERE latitude IS NOT NULL
GROUP BY kind
ORDER BY n DESC
"""

Q_REPORTS_BY_DEPARTMENT = """
SELECT COALESCE(m.department_name, 'SIN MUNICIPIO VERIFICADO') AS department_name,
       COUNT(*)                                              AS reports,
       COUNT(*) FILTER (WHERE r.priority = 'high')           AS high_priority,
       COUNT(*) FILTER (WHERE r.status IN ('open','in_progress')) AS pending,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.status = 'resolved') / COUNT(*), 1) AS pct_resolved
FROM reports r
LEFT JOIN municipalities m ON m.code = r.municipality_code AND r.municipality_verified
GROUP BY 1
ORDER BY reports DESC, department_name
"""


class DuckDBAnalytics(AnalyticsPort):
    def __init__(self, database: str = ":memory:", snapshot_dir: str | Path | None = None):
        self._con = duckdb.connect(database)
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else Path(tempfile.mkdtemp())
        self._con.execute("""CREATE TABLE IF NOT EXISTS municipalities (
            code VARCHAR PRIMARY KEY, name VARCHAR, department_code VARCHAR,
            department_name VARCHAR, kind VARCHAR, latitude DOUBLE, longitude DOUBLE)""")
        self._con.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER, category VARCHAR, status VARCHAR, priority VARCHAR,
            municipality_code VARCHAR, municipality_verified BOOLEAN, created_at TIMESTAMPTZ)""")

    def load_municipalities_json(self, path: str | Path) -> int:
        """Load the raw API payload (list of JSON objects) straight with read_json.
        Coordinates are text with decimal comma, so they are converted in SQL."""
        self._con.execute("DELETE FROM municipalities")
        self._con.execute("""
            INSERT INTO municipalities
            SELECT lpad(CAST(cod_mpio AS VARCHAR), 5, '0'), trim(nom_mpio),
                   lpad(CAST(cod_dpto AS VARCHAR), 2, '0'), trim(dpto), trim(tipo_municipio),
                   TRY_CAST(replace(CAST(latitud AS VARCHAR), ',', '.') AS DOUBLE),
                   TRY_CAST(replace(CAST(longitud AS VARCHAR), ',', '.') AS DOUBLE)
            FROM read_json(?, format='array', columns={
                cod_dpto:'VARCHAR', dpto:'VARCHAR', cod_mpio:'VARCHAR', nom_mpio:'VARCHAR',
                tipo_municipio:'VARCHAR', longitud:'VARCHAR', latitud:'VARCHAR'})
        """, [str(path)])
        return self._con.execute("SELECT COUNT(*) FROM municipalities").fetchone()[0]

    def load_municipalities(self, municipalities: list[Municipality]) -> int:
        """Write a JSON snapshot in the API's own shape and load it via read_json,
        so the same SQL path is used for live data and for saved files."""
        rows = [{"cod_dpto": m.department_code, "dpto": m.department_name,
                 "cod_mpio": m.code, "nom_mpio": m.name, "tipo_municipio": m.kind,
                 "latitud": None if m.latitude is None else str(m.latitude),
                 "longitud": None if m.longitude is None else str(m.longitude)}
                for m in municipalities]
        path = self._snapshot_dir / "divipola_snapshot.json"
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return self.load_municipalities_json(path)

    def load_reports(self, reports: list[Report]) -> int:
        self._con.execute("DELETE FROM reports")
        if reports:
            self._con.executemany(
                "INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(r.id, r.category.value, r.status.value, r.priority.value if r.priority else None,
                  r.municipality_code, r.municipality_verified, r.created_at) for r in reports])
        return len(reports)

    def municipalities_by_department(self, top: int = 10) -> list[dict[str, Any]]:
        return self._rows(Q_MUNICIPALITIES_BY_DEPARTMENT, [top])

    def coordinate_stats_by_kind(self) -> list[dict[str, Any]]:
        return self._rows(Q_COORDINATE_STATS_BY_KIND)

    def reports_by_department(self) -> list[dict[str, Any]]:
        return self._rows(Q_REPORTS_BY_DEPARTMENT)

    def _rows(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        cur = self._con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
