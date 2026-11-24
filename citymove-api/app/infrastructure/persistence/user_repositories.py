from __future__ import annotations

from sqlalchemy import select

from app.domain.users.model import Role, User
from app.domain.users.ports import UserRepository
from app.infrastructure.persistence.orm import UserRow


def _to_domain(r: UserRow) -> User:
    return User(id=r.id, username=r.username, password_hash=r.password_hash, role=Role(r.role))


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory):
        self._sessions = session_factory

    def add(self, user: User) -> User:
        with self._sessions() as s:
            row = UserRow(username=user.username, password_hash=user.password_hash,
                          role=user.role.value)
            s.add(row)
            s.commit()
            return _to_domain(row)

    def by_username(self, username: str) -> User | None:
        with self._sessions() as s:
            row = s.scalar(select(UserRow).where(UserRow.username == username))
            return _to_domain(row) if row else None

    def by_id(self, user_id: int) -> User | None:
        with self._sessions() as s:
            row = s.get(UserRow, user_id)
            return _to_domain(row) if row else None

    def list(self) -> list[User]:
        with self._sessions() as s:
            return [_to_domain(r) for r in s.scalars(select(UserRow).order_by(UserRow.id))]


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self._items: dict[int, User] = {}

    def add(self, user: User) -> User:
        user.id = len(self._items) + 1
        self._items[user.id] = user
        return user

    def by_username(self, username: str) -> User | None:
        return next((u for u in self._items.values() if u.username == username), None)

    def by_id(self, user_id: int) -> User | None:
        return self._items.get(user_id)

    def list(self) -> list[User]:
        return list(self._items.values())
