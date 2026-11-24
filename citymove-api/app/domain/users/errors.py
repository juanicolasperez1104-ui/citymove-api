class AuthError(Exception):
    """Authentication failed (maps to 401)."""


class Forbidden(Exception):
    """Authenticated but not allowed (maps to 403)."""


class UsernameTaken(Exception):
    """Registration with an existing username (maps to 409)."""
