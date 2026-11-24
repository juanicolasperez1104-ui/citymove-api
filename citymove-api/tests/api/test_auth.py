"""JWT authentication and RBAC (OWASP API1/API2/API3/API5)."""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.container import Container
from app.application.auth_service import AuthService
from app.infrastructure.analytics.duckdb_analytics import DuckDBAnalytics
from app.infrastructure.persistence.database import make_session_factory
from app.infrastructure.persistence.sqlalchemy_report_repository import SqlAlchemyReportRepository
from app.infrastructure.persistence.user_repositories import SqlAlchemyUserRepository
from app.infrastructure.security.passwords import Pbkdf2Hasher, hash_password, verify_password
from app.infrastructure.security.tokens import TokenService
from app.main import create_app
from tests.api.test_api import PAYLOAD
from tests.conftest import FakeCatalog

SECRET = "test-secret-that-is-long-enough-1234567890"


@pytest.fixture
def client(tmp_path, fake_territory):
    sessions = make_session_factory("sqlite://")
    auth = AuthService(SqlAlchemyUserRepository(sessions), TokenService(SECRET), Pbkdf2Hasher(1000))
    auth.ensure_admin("admin", "Admin-Pass-2026")
    c = Container(SqlAlchemyReportRepository(sessions), fake_territory, FakeCatalog(),
                  DuckDBAnalytics(snapshot_dir=tmp_path), [], auth=auth)
    return TestClient(create_app(c))


def login(client, user, pwd):
    return client.post("/api/v1/auth/login", data={"username": user, "password": pwd})


def bearer(client, user, pwd):
    return {"Authorization": f"Bearer {login(client, user, pwd).json()['access_token']}"}


def test_register_login_and_me(client):
    r = client.post("/api/v1/auth/register", json={"username": "maria", "password": "Maria-12345"})
    assert r.status_code == 201 and r.json()["role"] == "USER"
    tok = login(client, "maria", "Maria-12345").json()
    assert tok["token_type"] == "bearer" and tok["expires_in"] == 1800
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.json() == {"id": 2, "username": "maria", "role": "USER"}


def test_register_cannot_choose_role_and_duplicates_conflict(client):
    bad = client.post("/api/v1/auth/register",
                      json={"username": "eve", "password": "Eve-1234567", "role": "ADMIN"})
    assert bad.status_code == 422
    client.post("/api/v1/auth/register", json={"username": "ana", "password": "Ana-1234567"})
    again = client.post("/api/v1/auth/register", json={"username": "ana", "password": "Ana-1234567"})
    assert again.status_code == 409


def test_wrong_password_and_unknown_user_look_the_same(client):
    a = login(client, "admin", "wrong-password")
    b = login(client, "ghost", "wrong-password")
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"] == "Invalid username or password"
    assert a.headers["www-authenticate"] == "Bearer"


def test_rbac_on_reports(client):
    client.post("/api/v1/auth/register", json={"username": "maria", "password": "Maria-12345"})
    user = bearer(client, "maria", "Maria-12345")
    admin = bearer(client, "admin", "Admin-Pass-2026")
    assert client.post("/api/v1/reports", json=PAYLOAD).status_code == 401
    assert client.post("/api/v1/reports", json=PAYLOAD, headers=user).status_code == 201
    assert client.get("/api/v1/reports").status_code == 200          # reading is public
    denied = client.delete("/api/v1/reports/1", headers=user)
    assert denied.status_code == 403 and denied.json()["detail"] == "Requires role: ADMIN"
    assert client.get("/api/v1/admin/users", headers=user).status_code == 403
    assert len(client.get("/api/v1/admin/users", headers=admin).json()) == 2
    assert client.delete("/api/v1/reports/1", headers=admin).status_code == 204


@pytest.mark.parametrize("token", [
    "not-a-jwt",
    jwt.encode({"sub": "1", "role": "ADMIN", "iss": "citymove-api", "aud": "citymove-clients",
                "iat": 0, "exp": 9999999999}, "another-secret-that-is-long-enough-123456",
               algorithm="HS256"),
    jwt.encode({"sub": "1", "role": "ADMIN", "iss": "citymove-api", "aud": "citymove-clients",
                "iat": 0, "exp": 9999999999}, None, algorithm="none"),
    jwt.encode({"sub": "1", "role": "ADMIN", "iss": "citymove-api", "aud": "citymove-clients",
                "iat": 0, "exp": 10}, SECRET, algorithm="HS256"),
], ids=["garbage", "forged-secret", "alg-none", "expired"])
def test_invalid_tokens_are_rejected(client, token):
    r = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_role_comes_from_database_not_from_token(client):
    client.post("/api/v1/auth/register", json={"username": "maria", "password": "Maria-12345"})
    now = int(time.time())
    forged = jwt.encode({"sub": "2", "role": "ADMIN", "iss": "citymove-api",
                         "aud": "citymove-clients", "iat": now, "exp": now + 600},
                        SECRET, algorithm="HS256")
    r = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


def test_security_headers_and_health(client):
    r = client.get("/health")
    assert r.json() == {"status": "ok", "version": "1.0.0"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_password_hashing_and_short_secret():
    h = hash_password("Correct-Horse-1", iterations=1000)
    assert h.startswith("pbkdf2_sha256$1000$") and "Correct-Horse-1" not in h
    assert verify_password("Correct-Horse-1", h) and not verify_password("wrong", h)
    assert not verify_password("x", "garbage")
    with pytest.raises(ValueError):
        TokenService("short")
