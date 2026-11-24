"""User aggregate and roles (pure Python, no framework imports)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


@dataclass
class User:
    username: str
    password_hash: str
    role: Role = Role.USER
    id: int | None = None
