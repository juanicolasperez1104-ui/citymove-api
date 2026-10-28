"""Minimal server-rendered dashboard (inline SVG, no external JS/CDN)."""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.container import Container
from app.api.deps import get_container
from app.domain.shared.errors import ExternalDataUnavailable

router = APIRouter(tags=["dashboard"])


def bar_chart(rows: list[dict], label: str, value: str, width: int = 640) -> str:
    if not rows:
        return "<p>No data loaded yet. Run POST /api/v1/open-data/refresh.</p>"
    bar_h, gap, left = 22, 6, 190
    peak = max(r[value] for r in rows) or 1
    height = len(rows) * (bar_h + gap)
    parts = [f'<svg role="img" aria-label="bar chart" viewBox="0 0 {width} {height}" '
             f'width="100%" style="max-width:{width}px">']
    for i, r in enumerate(rows):
        y = i * (bar_h + gap)
        w = (width - left - 60) * r[value] / peak
        parts.append(f'<text x="{left - 8}" y="{y + 16}" text-anchor="end" font-size="12">'
                     f'{escape(str(r[label]))}</text>'
                     f'<rect x="{left}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="#4a6fa5"/>'
                     f'<text x="{left + w + 6:.1f}" y="{y + 16}" font-size="12">{r[value]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No data.</p>"
    head = "".join(f"<th>{escape(k)}</th>" for k in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in r.values()) + "</tr>"
                   for r in rows)
    return f"<div style='overflow-x:auto'><table><tr>{head}</tr>{body}</table></div>"


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard(c: Container = Depends(get_container)):
    svc = c.open_data_service
    by_dept, stats, by_reports = svc.municipalities_by_department(10), svc.coordinate_stats(), []
    try:
        by_reports = svc.reports_by_department()
    except ExternalDataUnavailable:
        pass
    breakers = "".join(f"<li><b>{escape(b['name'])}</b>: {b['state'].upper()} "
                       f"(failures {b['failures']}/{b['failure_threshold']})</li>"
                       for b in (x.snapshot() for x in c.breakers)) or "<li>none</li>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CityMove open data</title>
<style>body{{font-family:system-ui,sans-serif;margin:1.5rem;max-width:900px}}
table{{border-collapse:collapse;font-size:.85rem}}td,th{{border:1px solid #bbb;padding:4px 8px}}
th{{background:#eee}}</style></head><body>
<h1>CityMove – Colombian open data</h1>
<p>Source: DANE DIVIPOLA (dataset gdxc-w37w, datos.gov.co), processed with DuckDB.</p>
<h2>Circuit breakers</h2><ul>{breakers}</ul>
<h2>Top 10 departments by number of municipalities</h2>{bar_chart(by_dept, 'department_name', 'municipalities')}
<h2>Latitude statistics by entity type</h2>{table(stats)}
<h2>CityMove reports by department</h2>{table(by_reports)}
</body></html>"""
