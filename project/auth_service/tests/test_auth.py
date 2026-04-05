"""
Tests for Users & Auth service.
Uses an in-memory SQLite DB — no Postgres or real emails needed.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from auth_app.main import app
from auth_app.database import get_db, Base
from auth_app import crud, models
from auth_app.security import create_access_token

# ── SQLite in-memory setup ────────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Patch the schema prefix — SQLite doesn't support schemas
# Override model __table_args__ at test time
for mapper in Base.registry.mappers:
    table = mapper.local_table
    if hasattr(table, "schema"):
        table.schema = None

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Disable real emails
import auth_app.email as email_module
email_module.settings.EMAIL_ENABLED = False

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    """Wipe tables between tests."""
    yield
    db = TestingSessionLocal()
    db.query(models.OTPCode).delete()
    db.query(models.User).delete()
    db.commit()
    db.close()


def _register(email="test@example.com", password="password123", full_name="Test User"):
    return client.post("/auth/register", json={
        "email": email, "password": password, "full_name": full_name
    })


def _get_verified_user(email="verified@example.com", password="password123"):
    """Helper: register + manually verify the user, return user object."""
    r = _register(email=email, password=password)
    assert r.status_code == 201
    db = TestingSessionLocal()
    user = crud.get_user_by_email(db, email)
    crud.mark_verified(db, user)
    db.close()
    return user


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "auth"


# ── Register ──────────────────────────────────────────────────────────────────

def test_register_success():
    r = _register()
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "test@example.com"
    assert data["is_verified"] is False
    assert "hashed_password" not in data


def test_register_duplicate_email():
    _register()
    r = _register()
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_invalid_email():
    r = client.post("/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert r.status_code == 422


def test_register_short_password():
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "short"})
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success():
    _register()
    r = client.post("/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    _register()
    r = client.post("/auth/login", json={"email": "test@example.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_unknown_email():
    r = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert r.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

def test_token_refresh():
    _register()
    login = client.post("/auth/login", json={"email": "test@example.com", "password": "password123"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_token_refresh_invalid():
    r = client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


# ── Token verify ──────────────────────────────────────────────────────────────

def test_verify_token_valid():
    user = _get_verified_user()
    token = create_access_token(user.id, user.email)
    r = client.post("/auth/verify-token", json={"refresh_token": token})
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["user_id"] == user.id


def test_verify_token_invalid():
    r = client.post("/auth/verify-token", json={"refresh_token": "badtoken"})
    assert r.status_code == 200
    assert r.json()["valid"] is False


# ── OTP email verification ────────────────────────────────────────────────────

def test_verify_email_otp():
    _register(email="otp@example.com")
    db = TestingSessionLocal()
    user = crud.get_user_by_email(db, "otp@example.com")
    otp = crud.create_otp(db, user.id, "verify")
    code = otp.code
    db.close()

    r = client.post("/auth/otp/verify-email", json={
        "email": "otp@example.com", "code": code, "purpose": "verify"
    })
    assert r.status_code == 200
    assert r.json()["user"]["is_verified"] is True


def test_verify_email_wrong_code():
    _register(email="otp2@example.com")
    r = client.post("/auth/otp/verify-email", json={
        "email": "otp2@example.com", "code": "000000", "purpose": "verify"
    })
    assert r.status_code == 400


# ── OTP password reset ────────────────────────────────────────────────────────

def test_forgot_and_reset_password():
    _register(email="reset@example.com", password="oldpassword")
    db = TestingSessionLocal()
    user = crud.get_user_by_email(db, "reset@example.com")
    otp = crud.create_otp(db, user.id, "reset")
    code = otp.code
    db.close()

    r = client.post("/auth/otp/reset-password", json={
        "email": "reset@example.com",
        "code": code,
        "new_password": "newpassword123",
    })
    assert r.status_code == 200

    # Old password should no longer work
    r2 = client.post("/auth/login", json={"email": "reset@example.com", "password": "oldpassword"})
    assert r2.status_code == 401

    # New password should work
    r3 = client.post("/auth/login", json={"email": "reset@example.com", "password": "newpassword123"})
    assert r3.status_code == 200


# ── OTP passwordless login ────────────────────────────────────────────────────

def test_otp_login():
    _register(email="magic@example.com")
    db = TestingSessionLocal()
    user = crud.get_user_by_email(db, "magic@example.com")
    otp = crud.create_otp(db, user.id, "login")
    code = otp.code
    db.close()

    r = client.post("/auth/otp/login", json={
        "email": "magic@example.com", "code": code, "purpose": "login"
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    # OTP login should auto-verify the email
    assert data["user"]["is_verified"] is True


# ── /users/me ─────────────────────────────────────────────────────────────────

def test_get_me():
    user = _get_verified_user()
    token = create_access_token(user.id, user.email)
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == user.email


def test_update_me_name():
    user = _get_verified_user()
    token = create_access_token(user.id, user.email)
    r = client.patch("/users/me",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Name"


def test_get_me_no_token():
    r = client.get("/users/me")
    assert r.status_code == 403
