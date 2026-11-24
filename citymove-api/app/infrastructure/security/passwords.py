"""PBKDF2-SHA256 password hashing from the standard library (OWASP: >= 600k iterations)."""
from __future__ import annotations

import hashlib
import hmac
import os

ITERATIONS = 600_000


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                        int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest)


class Pbkdf2Hasher:
    """Adapter for the application PasswordHasher port."""

    def __init__(self, iterations: int = ITERATIONS):
        self.iterations = iterations

    def hash(self, password: str) -> str:
        return hash_password(password, self.iterations)

    def verify(self, password: str, stored: str) -> bool:
        return verify_password(password, stored)
