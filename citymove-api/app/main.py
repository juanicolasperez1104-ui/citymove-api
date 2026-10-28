"""FastAPI entry point (driving adapter)."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.container import Container, build_production_container
from app.api.errors import register_error_handlers
from app.api.routers import dashboard, open_data, reports


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="CityMove API", version="0.6.0",
                  description="Citizen reports of urban-infrastructure issues (SDG 11), "
                              "hexagonal architecture with Colombian open data.")
    app.state.container = container or build_production_container()
    register_error_handlers(app)
    app.include_router(reports.router)
    app.include_router(open_data.router)
    app.include_router(dashboard.router)

    @app.get("/health", tags=["health"], summary="Health check")
    def health():
        return {"status": "ok"}

    return app
