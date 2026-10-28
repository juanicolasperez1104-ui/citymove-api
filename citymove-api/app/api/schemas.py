"""HTTP contracts (Pydantic). Kept in the api layer so the domain stays framework-free."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.reports.model import Category, Priority, Status


class ReportCreate(BaseModel):
    title: str = Field(min_length=5, max_length=120, examples=["Pothole on Av. Boyaca"])
    description: str = Field(min_length=10, max_length=2000)
    category: Category
    address: str = Field(min_length=3, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$",
                                          description="DANE DIVIPOLA code, e.g. 11001 (Bogota)")
    priority: Priority | None = None


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=120)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    category: Category | None = None
    address: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    municipality_code: str | None = Field(default=None, pattern=r"^\d{5}$")


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    category: Category
    address: str
    latitude: float
    longitude: float
    municipality_code: str | None
    municipality_verified: bool
    status: Status
    priority: Priority | None
    created_at: datetime


class MunicipalityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    department_code: str
    department_name: str
    kind: str
    latitude: float | None
    longitude: float | None


class ErrorResponse(BaseModel):
    status: int
    error: str
    detail: str | list[dict]
    path: str
