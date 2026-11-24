from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field

from app.api.container import Container
from app.api.deps import get_container
from app.api.security import admin_only, any_user
from app.domain.users.model import User

router = APIRouter(prefix="/api/v1", tags=["auth"])


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # "role" cannot be sent (mass assignment)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _out(u: User) -> UserOut:
    return UserOut(id=u.id, username=u.username, role=u.role.value)


@router.post("/auth/register", response_model=UserOut, status_code=201,
             summary="Register a citizen account (always role USER)")
def register(body: RegisterIn, c: Container = Depends(get_container)):
    return _out(c.auth.register(body.username, body.password))


@router.post("/auth/login", response_model=TokenOut, summary="Log in and get a JWT")
def login(form: OAuth2PasswordRequestForm = Depends(), c: Container = Depends(get_container)):
    return TokenOut(access_token=c.auth.login(form.username, form.password),
                    expires_in=c.auth.tokens.ttl)


@router.get("/users/me", response_model=UserOut, summary="Current user")
def me(user: User = Depends(any_user)):
    return _out(user)


@router.get("/admin/users", response_model=list[UserOut], summary="List users (ADMIN)")
def list_users(_: User = Depends(admin_only), c: Container = Depends(get_container)):
    return [_out(u) for u in c.auth.users.list()]
