"""Download DIVIPOLA (DANE, datos.gov.co), save the raw JSON and run the DuckDB
queries. Run from the repo root:  python scripts/fetch_open_data.py

Expected values below were read from the dataset metadata
(https://www.datos.gov.co/api/views/gdxc-w37w) on 2026-10-27; DANE may update
the dataset, so a mismatch is reported but is not necessarily an error."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.analytics.duckdb_analytics import DuckDBAnalytics  # noqa: E402
from app.infrastructure.opendata.catalog_adapter import DatosGovCatalogAdapter  # noqa: E402
from app.infrastructure.opendata.divipola_adapter import DaneDivipolaAdapter  # noqa: E402
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker  # noqa: E402
from app.infrastructure.resilience.http_client import ResilientJsonClient  # noqa: E402
from app.infrastructure.resilience.retry import RetryPolicy  # noqa: E402

EXPECTED = {"rows": 1122, "Municipio": 1103, "Área no municipalizada": 18, "Isla": 1,
            "ANTIOQUIA": 125, "BOYACÁ": 123, "CUNDINAMARCA": 116}
RAW = Path("data/raw/divipola.json")


def table(rows):
    if not rows:
        return "(no rows)"
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    http = httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
    client = ResilientJsonClient("DANE DIVIPOLA", http, CircuitBreaker("divipola"), RetryPolicy())
    divipola = DaneDivipolaAdapter(client)
    municipalities = divipola.list_municipalities()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(divipola.last_raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(divipola.last_raw)} raw rows to {RAW}")

    meta = DatosGovCatalogAdapter(ResilientJsonClient("catalog", http, CircuitBreaker("catalog"),
                                                      RetryPolicy())).get_metadata("gdxc-w37w")
    print(f"Source: {meta.name} | {meta.publisher} | {meta.license} | updated {meta.rows_updated_at}")

    db = DuckDBAnalytics(snapshot_dir="data/raw")
    loaded = db.load_municipalities_json(RAW)
    q1 = db.municipalities_by_department(top=40)
    q2 = db.coordinate_stats_by_kind()
    found = {"rows": loaded, **{r["kind"]: r["n"] for r in q2},
             **{r["department_name"]: r["municipalities"] for r in q1}}
    print("\nCross-check against metadata:")
    for key, value in EXPECTED.items():
        status = "OK" if found.get(key) == value else "DIFFERENT"
        print(f"  {key}: expected {value}, got {found.get(key)} -> {status}")

    report = (f"# DuckDB results (live data)\n\nSource: {meta.name}, {meta.publisher}, "
              f"rows updated {meta.rows_updated_at}\n\n## Query 1\n\n{table(q1)}\n\n"
              f"## Query 2\n\n{table(q2)}\n")
    Path("data/analytics_results.md").write_text(report, encoding="utf-8")
    print("\nQuery 1 (top 10):\n" + table(q1[:10]))
    print("\nQuery 2:\n" + table(q2))
    print("\nFull results saved to data/analytics_results.md")


if __name__ == "__main__":
    main()
