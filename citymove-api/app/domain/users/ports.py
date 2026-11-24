from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.users.model import User


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def list(self) -> list[User]: ...
