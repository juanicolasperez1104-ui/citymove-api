"""JWT issuing/verification (HS256, algorithm pinned, all registered claims required)."""
from __future__ import annotations

import time
import uuid

import jwt

from app.domain.users.errors import AuthError

ISSUER = "citymove-api"
AUDIENCE = "citymove-clients"


class TokenService:
    def __init__(self, secret: str, ttl_seconds: int = 1800):
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters")
        self._secret = secret
        self.ttl = ttl_seconds

    def issue(self, user_id: int, username: str, role: str) -> str:
        now = int(time.time())
        claims = {"sub": str(user_id), "username": username, "role": role,
                  "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + self.ttl,
                  "jti": uuid.uuid4().hex}
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def decode(self, token: str) -> dict:
        try:
            return self._decode(token)
        except jwt.PyJWTError:
            raise AuthError("Invalid or expired token") from None

    def _decode(self, token: str) -> dict:
        return jwt.decode(token, self._secret, algorithms=["HS256"], issuer=ISSUER,
                          audience=AUDIENCE,
                          options={"require": ["sub", "iss", "aud", "iat", "exp"]})
