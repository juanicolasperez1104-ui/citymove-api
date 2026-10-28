from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.container import Container
from app.api.deps import get_container
from app.api.schemas import ErrorResponse, MunicipalityOut

router = APIRouter(prefix="/api/v1", tags=["open data"])
UNAVAILABLE = {503: {"model": ErrorResponse, "description": "Open-data source unavailable"}}


@router.get("/territory/municipalities/{code}", response_model=MunicipalityOut,
            responses={404: {"model": ErrorResponse}, **UNAVAILABLE},
            summary="Look up a DIVIPOLA municipality (DANE via datos.gov.co)")
def get_municipality(code: str, c: Container = Depends(get_container)):
    municipality = c.territory.get_municipality(code)
    if municipality is None:
        raise HTTPException(status_code=404, detail=f"Municipality {code} not found in DIVIPOLA")
    return municipality


@router.post("/open-data/refresh", responses=UNAVAILABLE,
             summary="Download DIVIPOLA and reload the DuckDB analytics tables")
def refresh(c: Container = Depends(get_container)):
    result = c.open_data_service.refresh()
    src = result.source
    return {"municipalities_loaded": result.municipalities_loaded,
            "reports_loaded": result.reports_loaded,
            "source": None if src is None else {
                "dataset_id": src.dataset_id, "name": src.name, "publisher": src.publisher,
                "license": src.license,
                "rows_updated_at": src.rows_updated_at.isoformat() if src.rows_updated_at else None}}


@router.get("/analytics/municipalities-by-department",
            summary="DuckDB query 1: municipalities per department")
def municipalities_by_department(top: int = Query(10, ge=1, le=40),
                                 c: Container = Depends(get_container)):
    return c.open_data_service.municipalities_by_department(top)


@router.get("/analytics/coordinate-stats",
            summary="DuckDB query 2: descriptive statistics of latitude by entity type")
def coordinate_stats(c: Container = Depends(get_container)):
    return c.open_data_service.coordinate_stats()


@router.get("/analytics/reports-by-department",
            summary="DuckDB query 3: CityMove reports joined with DIVIPOLA")
def reports_by_department(c: Container = Depends(get_container)):
    return c.open_data_service.reports_by_department()


@router.get("/health/integrations", summary="Circuit breaker state of each external API")
def integrations(c: Container = Depends(get_container)):
    return [b.snapshot() for b in c.breakers]
