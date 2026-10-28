"""Translate domain/application errors into the uniform JSON error format."""
from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.reports.errors import (InvalidReport, InvalidStatusTransition,
                                       ReportNotFound, UnknownMunicipality)
from app.domain.shared.errors import ExternalDataUnavailable

log = logging.getLogger(__name__)


def _body(status: int, detail, request: Request) -> dict:
    return {"status": status, "error": HTTPStatus(status).phrase, "detail": detail,
            "path": request.url.path}


def register_error_handlers(app: FastAPI) -> None:
    def simple(status: int):
        async def handler(request: Request, exc: Exception):
            return JSONResponse(_body(status, str(exc), request), status_code=status)
        return handler

    app.add_exception_handler(ReportNotFound, simple(404))
    app.add_exception_handler(InvalidStatusTransition, simple(409))
    app.add_exception_handler(UnknownMunicipality, simple(422))

    @app.exception_handler(InvalidReport)
    async def invalid_report(request: Request, exc: InvalidReport):
        detail = [{"field": exc.field, "message": exc.message}]
        return JSONResponse(_body(422, detail, request), status_code=422)

    @app.exception_handler(ExternalDataUnavailable)
    async def unavailable(request: Request, exc: ExternalDataUnavailable):
        headers = {"Retry-After": str(int(exc.retry_after) + 1)} if exc.retry_after else None
        return JSONResponse(_body(503, str(exc), request), status_code=503, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        detail = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                  for e in exc.errors()]
        return JSONResponse(_body(422, detail, request), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(exc.status_code, str(exc.detail), request),
                            status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(_body(500, "Unexpected server error", request), status_code=500)
