"""FastAPI entry point (driving adapter)."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.container import Container, build_production_container
from app.api.errors import register_error_handlers
from app.api.routers import auth, dashboard, open_data, reports


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="CityMove API", version="1.0.0",
                  description="Citizen reports of urban-infrastructure issues (SDG 11), "
                              "hexagonal architecture with Colombian open data.")
    app.state.container = container or build_production_container()
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(reports.router)
    app.include_router(open_data.router)
    app.include_router(dashboard.router)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health", tags=["health"], summary="Liveness and database check")
    def health():
        app.state.container.repository.list(skip=0, limit=1)  # fails -> 500 -> unhealthy
        return {"status": "ok", "version": app.version}

    return app
