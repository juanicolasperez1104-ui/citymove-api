"""Use cases: register, login, resolve the current user from a token."""
from __future__ import annotations

from app.application.ports import PasswordHasher, TokenPort
from app.domain.users.errors import AuthError, UsernameTaken
from app.domain.users.model import Role, User
from app.domain.users.ports import UserRepository

INVALID = "Invalid username or password"


class AuthService:
    def __init__(self, users: UserRepository, tokens: TokenPort, hasher: PasswordHasher):
        self.users = users
        self.tokens = tokens
        self.hasher = hasher
        self._dummy = hasher.hash("timing-equaliser")

    def register(self, username: str, password: str, role: Role = Role.USER) -> User:
        if self.users.by_username(username):
            raise UsernameTaken(f"Username '{username}' is already registered")
        return self.users.add(User(username, self.hasher.hash(password), role))

    def ensure_admin(self, username: str | None, password: str | None) -> None:
        """Seed the ADMIN account from environment variables (never hard-coded)."""
        if username and password and not self.users.by_username(username):
            self.register(username, password, Role.ADMIN)

    def login(self, username: str, password: str) -> str:
        user = self.users.by_username(username)
        if not user:
            self.hasher.verify(password, self._dummy)  # same timing for unknown users
            raise AuthError(INVALID)
        if not self.hasher.verify(password, user.password_hash):
            raise AuthError(INVALID)
        return self.tokens.issue(user.id, user.username, user.role.value)

    def current_user(self, token: str) -> User:
        claims = self.tokens.decode(token)
        try:
            user = self.users.by_id(int(claims["sub"]))
        except (ValueError, KeyError):
            user = None
        if not user:
            raise AuthError("Invalid or expired token")
        return user  # role comes from the database, not from the token
