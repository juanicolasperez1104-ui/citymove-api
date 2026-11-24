"""FastAPI dependencies for authentication and role-based access control."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.container import Container
from app.api.deps import get_container
from app.domain.users.errors import Forbidden
from app.domain.users.model import Role, User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str | None = Depends(oauth2),
                     c: Container = Depends(get_container)) -> User:
    from app.domain.users.errors import AuthError
    if not token:
        raise AuthError("Not authenticated")
    return c.auth.current_user(token)


def require_roles(*roles: Role) -> Callable[..., User]:
    allowed = frozenset(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise Forbidden(f"Requires role: {' or '.join(sorted(r.value for r in allowed))}")
        return user
    return checker


any_user = require_roles(Role.USER, Role.ADMIN)
admin_only = require_roles(Role.ADMIN)
