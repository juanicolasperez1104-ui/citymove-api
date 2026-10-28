from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.container import Container
from app.api.deps import get_container
from app.api.schemas import ErrorResponse, ReportCreate, ReportOut, ReportUpdate
from app.domain.reports.model import Category, Report, Status

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
          422: {"model": ErrorResponse}}


@router.post("", response_model=ReportOut, status_code=201, responses=ERRORS,
             summary="Create a report",
             description="Registers an urban-infrastructure issue. If municipality_code is "
                         "sent it is checked against DANE DIVIPOLA; when the open-data source "
                         "is down the report is stored with municipality_verified=false.")
def create_report(payload: ReportCreate, response: Response,
                  c: Container = Depends(get_container)):
    report = c.report_service.create(Report(**payload.model_dump()))
    response.headers["Location"] = f"/api/v1/reports/{report.id}"
    return report


@router.get("", response_model=list[ReportOut], summary="List reports")
def list_reports(status: Status | None = None, category: Category | None = None,
                 skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                 c: Container = Depends(get_container)):
    return c.report_service.list(status=status, category=category, skip=skip, limit=limit)


@router.get("/{report_id}", response_model=ReportOut, responses=ERRORS, summary="Get a report by ID")
def get_report(report_id: int, c: Container = Depends(get_container)):
    return c.report_service.get(report_id)


@router.put("/{report_id}", response_model=ReportOut, responses=ERRORS, summary="Update a report")
def update_report(report_id: int, payload: ReportUpdate, c: Container = Depends(get_container)):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Send at least one field to update")
    return c.report_service.update(report_id, **changes)


@router.delete("/{report_id}", status_code=204, responses=ERRORS, summary="Delete a report")
def delete_report(report_id: int, c: Container = Depends(get_container)):
    c.report_service.delete(report_id)
    return Response(status_code=204)
