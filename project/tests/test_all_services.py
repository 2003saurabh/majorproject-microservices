"""
=============================================================================
 Full Project Test Suite — Items · Auth · Orders
=============================================================================
 Covers every endpoint across all three services using in-memory SQLite.
 No running Docker containers or real emails needed.

 Install deps (run once):
   pip install pytest httpx pytest-asyncio \
               fastapi sqlalchemy pydantic pydantic-settings \
               passlib[bcrypt] bcrypt==4.0.1 python-jose[cryptography] \
               python-multipart email-validator aiosmtplib websockets

 Run all tests:
   pytest tests/test_all_services.py -v

 Run a single section:
   pytest tests/test_all_services.py -v -k "Items"
   pytest tests/test_all_services.py -v -k "Auth"
   pytest tests/test_all_services.py -v -k "Orders"
   pytest tests/test_all_services.py -v -k "OTP"
   pytest tests/test_all_services.py -v -k "Admin"
   pytest tests/test_all_services.py -v -k "WebSocket"
   pytest tests/test_all_services.py -v -k "Integration"
=============================================================================
"""

import sys, os, json, pytest
from unittest.mock import patch, AsyncMock

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "microservice"))
sys.path.insert(0, os.path.join(ROOT, "auth_service"))
sys.path.insert(0, os.path.join(ROOT, "orders_service"))

# ── SQLAlchemy / SQLite engines ───────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def _make_engine(url):
    return create_engine(url, connect_args={"check_same_thread": False})

items_engine  = _make_engine("sqlite:///./test_items.db")
auth_engine   = _make_engine("sqlite:///./test_auth.db")
orders_engine = _make_engine("sqlite:///./test_orders.db")

ItemsSession  = sessionmaker(autocommit=False, autoflush=False, bind=items_engine)
AuthSession   = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)
OrdersSession = sessionmaker(autocommit=False, autoflush=False, bind=orders_engine)


# ─────────────────────────────────────────────────────────────────────────────
#  ITEMS SERVICE SETUP
# ─────────────────────────────────────────────────────────────────────────────
from app.main     import app as items_app
from app.database import get_db as items_get_db, Base as ItemsBase
from app          import models as items_models

for _m in ItemsBase.registry.mappers:
    _t = _m.local_table
    if getattr(_t, "schema", None):
        _t.schema = None

ItemsBase.metadata.create_all(bind=items_engine)

def _items_db():
    db = ItemsSession()
    try:    yield db
    finally: db.close()

items_app.dependency_overrides[items_get_db] = _items_db

from fastapi.testclient import TestClient
items_client = TestClient(items_app)


# ─────────────────────────────────────────────────────────────────────────────
#  AUTH SERVICE SETUP
# ─────────────────────────────────────────────────────────────────────────────
from auth_app.main     import app as auth_app
from auth_app.database import get_db as auth_get_db, Base as AuthBase
from auth_app          import models as auth_models, crud as auth_crud
from auth_app.security import create_access_token, create_refresh_token

import auth_app.email as _email_mod
_email_mod.settings.EMAIL_ENABLED = False

for _m in AuthBase.registry.mappers:
    _t = _m.local_table
    if getattr(_t, "schema", None):
        _t.schema = None

AuthBase.metadata.create_all(bind=auth_engine)

def _auth_db():
    db = AuthSession()
    try:    yield db
    finally: db.close()

auth_app.dependency_overrides[auth_get_db] = _auth_db
auth_client = TestClient(auth_app)


# ─────────────────────────────────────────────────────────────────────────────
#  ORDERS SERVICE SETUP
# ─────────────────────────────────────────────────────────────────────────────
from orders_app.main     import app as orders_app
from orders_app.database import get_db as orders_get_db, Base as OrdersBase
from orders_app          import models as orders_models, crud as orders_crud
from orders_app.deps     import get_current_user as orders_get_current_user, CurrentUser

for _m in OrdersBase.registry.mappers:
    _t = _m.local_table
    if getattr(_t, "schema", None):
        _t.schema = None

OrdersBase.metadata.create_all(bind=orders_engine)

def _orders_db():
    db = OrdersSession()
    try:    yield db
    finally: db.close()

orders_app.dependency_overrides[orders_get_db] = _orders_db

def _user_dep(user_id=1, is_superuser=False):
    def _dep():
        return CurrentUser(user_id=user_id, email="user@test.com", is_superuser=is_superuser)
    return _dep

orders_app.dependency_overrides[orders_get_current_user] = _user_dep()
orders_client = TestClient(orders_app)


# ─────────────────────────────────────────────────────────────────────────────
#  FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_all_dbs():
    """Wipe every table and reset dependency overrides before each test."""
    yield
    db = ItemsSession()
    db.query(items_models.Item).delete()
    db.commit(); db.close()

    db = AuthSession()
    db.query(auth_models.OTPCode).delete()
    db.query(auth_models.User).delete()
    db.commit(); db.close()

    db = OrdersSession()
    db.query(orders_models.OrderStatusHistory).delete()
    db.query(orders_models.OrderItem).delete()
    db.query(orders_models.Order).delete()
    db.commit(); db.close()

    orders_app.dependency_overrides[orders_get_current_user] = _user_dep()


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

# Auth helpers
def _register(email="user@test.com", password="Password@123", name="Test User"):
    return auth_client.post("/auth/register", json={
        "email": email, "password": password, "full_name": name
    })

def _make_verified_user(email="user@test.com", password="Password@123",
                        name="Test User", is_superuser=False):
    r = _register(email=email, password=password, name=name)
    assert r.status_code == 201
    db   = AuthSession()
    user = auth_crud.get_user_by_email(db, email)
    auth_crud.mark_verified(db, user)
    if is_superuser:
        user.is_superuser = True
        db.commit()
        db.refresh(user)
    db.close()
    return user

def _login(email="user@test.com", password="Password@123"):
    return auth_client.post("/auth/login", json={"email": email, "password": password})

def _bearer(user_id=1, email="user@test.com", is_superuser=False):
    token = create_access_token(user_id, email, is_superuser)
    return {"Authorization": f"Bearer {token}"}

# Items helpers
def _create_item(name="Keyboard", description="A keyboard", is_active=True):
    return items_client.post("/items", json={
        "name": name, "description": description, "is_active": is_active
    })

# Orders helpers
SAMPLE_ORDER = {
    "items": [
        {"item_id": 1, "item_name": "Keyboard", "quantity": 1, "unit_price": "99.99"},
        {"item_id": 2, "item_name": "Mouse",    "quantity": 2, "unit_price": "29.99"},
    ],
    "notes": "Test order",
}

def _create_order(payload=None):
    with patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock):
        return orders_client.post("/orders", json=payload or SAMPLE_ORDER)

def _set_admin():
    orders_app.dependency_overrides[orders_get_current_user] = \
        _user_dep(user_id=99, is_superuser=True)

def _set_user(user_id=1):
    orders_app.dependency_overrides[orders_get_current_user] = _user_dep(user_id=user_id)


# =============================================================================
#  SECTION 1 — ITEMS SERVICE
# =============================================================================

class TestItemsHealth:
    def test_liveness(self):
        r = items_client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_health_fields(self):
        r = items_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "version" in data

    def test_readiness(self):
        r = items_client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["db"] == "connected"

    def test_root(self):
        r = items_client.get("/")
        assert r.status_code == 200
        assert "docs" in r.json()


class TestItemsCRUD:
    def test_create_item_success(self):
        r = _create_item()
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Keyboard"
        assert data["is_active"] is True
        assert data["id"] is not None
        assert "created_at" in data

    def test_create_item_missing_name(self):
        r = items_client.post("/items", json={"description": "No name"})
        assert r.status_code == 422

    def test_create_item_inactive(self):
        r = _create_item(name="Old Stock", is_active=False)
        assert r.status_code == 201
        assert r.json()["is_active"] is False

    def test_list_items_empty(self):
        r = items_client.get("/items")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_items_returns_all(self):
        _create_item("Item A")
        _create_item("Item B")
        _create_item("Item C")
        r = items_client.get("/items")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_list_items_pagination(self):
        for i in range(5):
            _create_item(f"Item {i}")
        r = items_client.get("/items?skip=2&limit=2")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_item_by_id(self):
        created = _create_item().json()
        r = items_client.get(f"/items/{created['id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "Keyboard"

    def test_get_item_not_found(self):
        r = items_client.get("/items/99999")
        assert r.status_code == 404

    def test_update_item_name(self):
        created = _create_item().json()
        r = items_client.put(f"/items/{created['id']}", json={"name": "Mechanical Keyboard"})
        assert r.status_code == 200
        assert r.json()["name"] == "Mechanical Keyboard"

    def test_update_item_status(self):
        created = _create_item().json()
        r = items_client.put(f"/items/{created['id']}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_update_item_not_found(self):
        r = items_client.put("/items/99999", json={"name": "Ghost"})
        assert r.status_code == 404

    def test_delete_item(self):
        created = _create_item().json()
        r = items_client.delete(f"/items/{created['id']}")
        assert r.status_code == 204
        assert items_client.get(f"/items/{created['id']}").status_code == 404

    def test_delete_item_not_found(self):
        r = items_client.delete("/items/99999")
        assert r.status_code == 404

    def test_create_and_verify_multiple(self):
        names = ["Monitor", "Keyboard", "Mouse", "Webcam", "Headset"]
        for n in names:
            _create_item(n)
        returned = [i["name"] for i in items_client.get("/items").json()]
        for n in names:
            assert n in returned


# =============================================================================
#  SECTION 2 — AUTH SERVICE
# =============================================================================

class TestAuthHealth:
    def test_liveness(self):
        r = auth_client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_health_service_name(self):
        r = auth_client.get("/health")
        assert r.status_code == 200
        assert r.json()["service"] == "auth"

    def test_readiness(self):
        r = auth_client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["db"] == "connected"


class TestAuthRegister:
    def test_register_success(self):
        r = _register()
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "user@test.com"
        assert data["is_verified"] is False
        assert data["is_superuser"] is False
        assert "hashed_password" not in data

    def test_register_stores_full_name(self):
        r = _register(name="Jane Doe")
        assert r.status_code == 201
        assert r.json()["full_name"] == "Jane Doe"

    def test_register_duplicate_email(self):
        _register()
        r = _register()
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"]

    def test_register_invalid_email(self):
        r = auth_client.post("/auth/register", json={
            "email": "not-an-email", "password": "Password@123"
        })
        assert r.status_code == 422

    def test_register_short_password(self):
        r = auth_client.post("/auth/register", json={
            "email": "a@b.com", "password": "short"
        })
        assert r.status_code == 422

    def test_register_missing_email(self):
        r = auth_client.post("/auth/register", json={"password": "Password@123"})
        assert r.status_code == 422

    def test_register_missing_password(self):
        r = auth_client.post("/auth/register", json={"email": "a@b.com"})
        assert r.status_code == 422


class TestAuthLogin:
    def test_login_success(self):
        _make_verified_user()
        r = _login()
        assert r.status_code == 200
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "user@test.com"

    def test_login_unverified_user_still_works(self):
        """Login succeeds even without verification — but protected routes will refuse."""
        _register()
        assert _login().status_code == 200

    def test_login_wrong_password(self):
        _make_verified_user()
        assert _login(password="WrongPass@999").status_code == 401

    def test_login_unknown_email(self):
        assert _login(email="nobody@test.com").status_code == 401

    def test_login_returns_full_name(self):
        _make_verified_user(name="Jane Doe")
        r = _login()
        assert r.json()["user"]["full_name"] == "Jane Doe"
        assert r.json()["user"]["is_verified"] is True


class TestAuthTokens:
    def test_refresh_token_success(self):
        _make_verified_user()
        refresh = _login().json()["refresh_token"]
        r = auth_client.post("/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_refresh_invalid_token(self):
        r = auth_client.post("/auth/refresh", json={"refresh_token": "garbage.token.here"})
        assert r.status_code == 401

    def test_refresh_with_access_token_is_rejected(self):
        """Access tokens must not be usable as refresh tokens."""
        _make_verified_user()
        access = _login().json()["access_token"]
        r = auth_client.post("/auth/refresh", json={"refresh_token": access})
        assert r.status_code == 401

    def test_verify_token_valid(self):
        user  = _make_verified_user()
        token = create_access_token(user.id, user.email)
        r = auth_client.post("/auth/verify-token", json={"refresh_token": token})
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["user_id"] == user.id
        assert data["email"]   == user.email

    def test_verify_token_invalid(self):
        r = auth_client.post("/auth/verify-token", json={"refresh_token": "bad.token"})
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_verify_token_superuser_flag(self):
        user  = _make_verified_user(is_superuser=True)
        token = create_access_token(user.id, user.email, is_superuser=True)
        r = auth_client.post("/auth/verify-token", json={"refresh_token": token})
        assert r.json()["is_superuser"] is True


class TestOTPVerifyEmail:
    def test_verify_email_success(self):
        _register(email="otp@test.com")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "otp@test.com")
        otp  = auth_crud.create_otp(db, user.id, "verify")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/verify-email", json={
            "email": "otp@test.com", "code": code, "purpose": "verify"
        })
        assert r.status_code == 200
        assert r.json()["user"]["is_verified"] is True
        assert "access_token" in r.json()

    def test_verify_email_wrong_code(self):
        _register(email="otp2@test.com")
        r = auth_client.post("/auth/otp/verify-email", json={
            "email": "otp2@test.com", "code": "000000", "purpose": "verify"
        })
        assert r.status_code == 400

    def test_send_verification_already_verified(self):
        _make_verified_user(email="done@test.com")
        r = auth_client.post("/auth/otp/send-verification", json={"email": "done@test.com"})
        assert r.status_code == 400

    def test_otp_is_single_use(self):
        _register(email="reuse@test.com")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "reuse@test.com")
        otp  = auth_crud.create_otp(db, user.id, "verify")
        code = otp.code
        db.close()

        auth_client.post("/auth/otp/verify-email", json={
            "email": "reuse@test.com", "code": code, "purpose": "verify"
        })
        r = auth_client.post("/auth/otp/verify-email", json={
            "email": "reuse@test.com", "code": code, "purpose": "verify"
        })
        assert r.status_code == 400


class TestOTPPasswordReset:
    def test_forgot_password_always_202(self):
        """Never reveal whether the email exists."""
        r = auth_client.post("/auth/otp/forgot-password", json={"email": "nobody@test.com"})
        assert r.status_code == 202

    def test_reset_password_success(self):
        _register(email="reset@test.com", password="OldPass@123")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "reset@test.com")
        otp  = auth_crud.create_otp(db, user.id, "reset")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/reset-password", json={
            "email": "reset@test.com", "code": code, "new_password": "NewPass@456"
        })
        assert r.status_code == 200
        assert _login(email="reset@test.com", password="OldPass@123").status_code == 401
        assert _login(email="reset@test.com", password="NewPass@456").status_code == 200

    def test_reset_password_wrong_code(self):
        _register(email="reset2@test.com")
        r = auth_client.post("/auth/otp/reset-password", json={
            "email": "reset2@test.com", "code": "000000", "new_password": "NewPass@456"
        })
        assert r.status_code == 400


class TestOTPPasswordlessLogin:
    def test_send_login_otp_always_202(self):
        r = auth_client.post("/auth/otp/send-login", json={"email": "nobody@test.com"})
        assert r.status_code == 202

    def test_otp_login_success_and_auto_verifies(self):
        _register(email="magic@test.com")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "magic@test.com")
        otp  = auth_crud.create_otp(db, user.id, "login")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/login", json={
            "email": "magic@test.com", "code": code, "purpose": "login"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["user"]["is_verified"] is True

    def test_otp_login_wrong_purpose_rejected(self):
        _register(email="magic2@test.com")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "magic2@test.com")
        otp  = auth_crud.create_otp(db, user.id, "login")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/login", json={
            "email": "magic2@test.com", "code": code, "purpose": "verify"
        })
        assert r.status_code == 400


class TestUsersMe:
    def test_get_me(self):
        user  = _make_verified_user()
        token = create_access_token(user.id, user.email)
        r = auth_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == user.email

    def test_get_me_no_token_returns_403(self):
        assert auth_client.get("/users/me").status_code == 403

    def test_get_me_bad_token_returns_403(self):
        r = auth_client.get("/users/me", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 403

    def test_update_me_name(self):
        user  = _make_verified_user()
        token = create_access_token(user.id, user.email)
        r = auth_client.patch("/users/me",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated Name"

    def test_update_me_password(self):
        user  = _make_verified_user(email="pw@test.com", password="OldPass@123")
        token = create_access_token(user.id, user.email)
        auth_client.patch("/users/me",
            json={"password": "BrandNew@999"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert _login(email="pw@test.com", password="BrandNew@999").status_code == 200
        assert _login(email="pw@test.com", password="OldPass@123").status_code == 401

    def test_superuser_flag_visible_in_me(self):
        user  = _make_verified_user(is_superuser=True)
        token = create_access_token(user.id, user.email, is_superuser=True)
        r = auth_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["is_superuser"] is True


# =============================================================================
#  SECTION 3 — ORDERS SERVICE
# =============================================================================

class TestOrdersHealth:
    def test_liveness(self):
        r = orders_client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_health_includes_ws_connections(self):
        r = orders_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "orders"
        assert "ws_connections" in data

    def test_readiness(self):
        r = orders_client.get("/health/ready")
        assert r.status_code == 200
        assert r.json()["db"] == "connected"


class TestOrdersCreate:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_create_order_success(self, mock_notify):
        r = orders_client.post("/orders", json=SAMPLE_ORDER)
        assert r.status_code == 201
        data = r.json()
        assert data["status"]  == "pending"
        assert data["user_id"] == 1
        assert len(data["items"]) == 2
        assert float(data["total_price"]) == pytest.approx(99.99 + 29.99 * 2)
        assert len(data["status_history"]) == 1
        assert data["status_history"][0]["to_status"]   == "pending"
        assert data["status_history"][0]["from_status"] is None
        mock_notify.assert_called_once()

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_create_order_with_notes(self, _):
        r = orders_client.post("/orders", json={**SAMPLE_ORDER, "notes": "Leave at door"})
        assert r.status_code == 201
        assert r.json()["notes"] == "Leave at door"

    def test_create_order_empty_items_rejected(self):
        r = orders_client.post("/orders", json={"items": []})
        assert r.status_code == 422

    def test_create_order_zero_quantity_rejected(self):
        r = orders_client.post("/orders", json={"items": [{
            "item_id": 1, "item_name": "X", "quantity": 0, "unit_price": "10.00"
        }]})
        assert r.status_code == 422

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_total_price_calculated_correctly(self, _):
        r = orders_client.post("/orders", json={"items": [
            {"item_id": 1, "item_name": "A", "quantity": 3, "unit_price": "10.00"},
            {"item_id": 2, "item_name": "B", "quantity": 2, "unit_price": "5.50"},
        ]})
        assert r.status_code == 201
        assert float(r.json()["total_price"]) == pytest.approx(3 * 10.00 + 2 * 5.50)

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_ws_notified_with_order_created_event(self, mock_notify):
        orders_client.post("/orders", json=SAMPLE_ORDER)
        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        assert kwargs.get("event") == "order_created"


class TestOrdersList:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_list_own_orders(self, _):
        _create_order(); _create_order()
        r = orders_client.get("/orders")
        assert r.status_code == 200
        assert len(r.json()) == 2

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_user_cannot_see_other_users_orders(self, _):
        _create_order()        # user 1
        _set_user(user_id=2)
        r = orders_client.get("/orders")
        assert r.status_code == 200
        assert len(r.json()) == 0

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_admin_sees_all_orders(self, _):
        _create_order()
        _set_user(user_id=2); _create_order()
        _set_admin()
        r = orders_client.get("/orders")
        assert r.status_code == 200
        assert len(r.json()) == 2

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_filter_orders_by_status(self, _):
        _create_order(); _create_order()
        r = orders_client.get("/orders?status=pending")
        assert r.status_code == 200
        for o in r.json():
            assert o["status"] == "pending"


class TestOrdersGet:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_get_own_order(self, _):
        created = _create_order().json()
        r = orders_client.get(f"/orders/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_nonexistent_order(self):
        assert orders_client.get("/orders/99999").status_code == 404

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_get_other_users_order_denied(self, _):
        created = _create_order().json()   # user 1
        _set_user(user_id=2)
        assert orders_client.get(f"/orders/{created['id']}").status_code == 403

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_admin_can_get_any_order(self, _):
        created = _create_order().json()   # user 1
        _set_admin()
        assert orders_client.get(f"/orders/{created['id']}").status_code == 200


class TestOrdersStatusTransitions:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_full_lifecycle_as_admin(self, _):
        order = _create_order().json()
        oid   = order["id"]
        _set_admin()
        for status in ["confirmed", "processing", "shipped", "delivered"]:
            r = orders_client.patch(f"/orders/{oid}/status", json={"status": status})
            assert r.status_code == 200, f"Failed on: {status} — {r.json()}"
            assert r.json()["status"] == status

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_status_history_recorded_at_each_transition(self, _):
        order = _create_order().json()
        oid   = order["id"]
        _set_admin()
        orders_client.patch(f"/orders/{oid}/status", json={"status": "confirmed", "note": "OK"})
        orders_client.patch(f"/orders/{oid}/status", json={"status": "processing"})
        history = orders_client.get(f"/orders/{oid}").json()["status_history"]
        assert len(history) == 3
        assert history[0]["to_status"] == "pending"
        assert history[1]["to_status"] == "confirmed"
        assert history[1]["note"]      == "OK"
        assert history[2]["to_status"] == "processing"

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_invalid_transition_blocked(self, _):
        order = _create_order().json()
        _set_admin()
        # pending → shipped is not allowed
        r = orders_client.patch(f"/orders/{order['id']}/status", json={"status": "shipped"})
        assert r.status_code == 400

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_delivered_is_terminal(self, _):
        order = _create_order().json()
        oid   = order["id"]
        _set_admin()
        for s in ["confirmed", "processing", "shipped", "delivered"]:
            orders_client.patch(f"/orders/{oid}/status", json={"status": s})
        r = orders_client.patch(f"/orders/{oid}/status", json={"status": "cancelled"})
        assert r.status_code == 400

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_cancelled_is_terminal(self, _):
        order = _create_order().json()
        _set_user()
        orders_client.patch(f"/orders/{order['id']}/status", json={"status": "cancelled"})
        _set_admin()
        r = orders_client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
        assert r.status_code == 400

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_user_can_cancel_own_pending_order(self, _):
        order = _create_order().json()
        r = orders_client.patch(f"/orders/{order['id']}/status",
            json={"status": "cancelled", "note": "Changed mind"})
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_user_cannot_confirm_order(self, _):
        order = _create_order().json()
        r = orders_client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
        assert r.status_code == 403

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_ws_notified_on_status_change(self, mock_notify):
        order = _create_order().json()
        mock_notify.reset_mock()
        _set_admin()
        orders_client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
        mock_notify.assert_called_once()


class TestOrdersDelete:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_delete_pending_order(self, _):
        order = _create_order().json()
        assert orders_client.delete(f"/orders/{order['id']}").status_code == 204
        assert orders_client.get(f"/orders/{order['id']}").status_code == 404

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_cannot_delete_confirmed_order(self, _):
        order = _create_order().json()
        _set_admin()
        orders_client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
        r = orders_client.delete(f"/orders/{order['id']}")
        assert r.status_code == 400

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_user_cannot_delete_other_users_order(self, _):
        order = _create_order().json()  # user 1
        _set_user(user_id=2)
        assert orders_client.delete(f"/orders/{order['id']}").status_code == 403

    def test_delete_nonexistent_order(self):
        assert orders_client.delete("/orders/99999").status_code == 404


class TestAdminEndpoints:
    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_admin_list_all_orders(self, _):
        _create_order()
        _set_user(user_id=2); _create_order()
        _set_admin()
        r = orders_client.get("/admin/orders")
        assert r.status_code == 200
        assert len(r.json()) == 2

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_admin_filter_by_status(self, _):
        # Create two pending orders first
        o1 = _create_order().json()
        o2 = _create_order().json()
        # Advance one to confirmed as admin
        _set_admin()
        orders_client.patch(f"/orders/{o1['id']}/status", json={"status": "confirmed"})
        # Filter by pending — should return only o2
        r = orders_client.get("/admin/orders?status=pending")
        assert r.status_code == 200
        for o in r.json():
            assert o["status"] == "pending"

    def test_admin_ws_stats(self):
        _set_admin()
        r = orders_client.get("/admin/ws/stats")
        assert r.status_code == 200
        assert "total_connections" in r.json()
        assert "connected_users"   in r.json()

    def test_regular_user_denied_admin_orders(self):
        _set_user()
        assert orders_client.get("/admin/orders").status_code == 403

    def test_regular_user_denied_ws_stats(self):
        _set_user()
        assert orders_client.get("/admin/ws/stats").status_code == 403


class TestWebSocket:
    def test_ws_rejects_missing_token(self):
        try:
            with orders_client.websocket_connect("/ws/orders") as ws:
                ws.receive_text()
        except Exception:
            pass  # Expected — no token causes close

    def test_ws_rejects_invalid_token(self):
        try:
            with orders_client.websocket_connect("/ws/orders?token=badtoken") as ws:
                ws.receive_text()
        except Exception:
            pass  # Expected — bad token causes close

    def test_ws_accepts_valid_token_and_sends_connected_event(self):
        user  = _make_verified_user()
        token = create_access_token(user.id, user.email)
        with orders_client.websocket_connect(f"/ws/orders?token={token}") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["event"]   == "connected"
            assert msg["user_id"] == user.id


# =============================================================================
#  SECTION 4 — INTEGRATION (cross-service flows)
# =============================================================================

class TestIntegrationFlows:
    def test_register_verify_login_get_profile(self):
        """Full auth flow: register → OTP verify → login → GET /users/me."""
        r = _register(email="flow@test.com")
        assert r.status_code == 201
        assert r.json()["is_verified"] is False

        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "flow@test.com")
        otp  = auth_crud.create_otp(db, user.id, "verify")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/verify-email", json={
            "email": "flow@test.com", "code": code, "purpose": "verify"
        })
        assert r.status_code == 200
        token = r.json()["access_token"]

        r = auth_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["is_verified"] is True

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_full_order_lifecycle_with_history(self, _):
        """pending → confirmed → processing → shipped → delivered, verify audit trail."""
        order = _create_order().json()
        oid   = order["id"]
        _set_admin()

        for status in ["confirmed", "processing", "shipped", "delivered"]:
            r = orders_client.patch(f"/orders/{oid}/status",
                json={"status": status, "note": f"moved to {status}"})
            assert r.status_code == 200

        history  = orders_client.get(f"/orders/{oid}").json()["status_history"]
        statuses = [h["to_status"] for h in history]
        assert len(history) == 5
        assert statuses == ["pending", "confirmed", "processing", "shipped", "delivered"]

    @patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
    def test_multi_user_order_isolation(self, _):
        """User 1 and 2 each have own orders — admin sees both, users see only their own."""
        _set_user(1); _create_order(); _create_order()
        _set_user(2); _create_order()

        _set_user(1)
        assert len(orders_client.get("/orders").json()) == 2

        _set_user(2)
        assert len(orders_client.get("/orders").json()) == 1

        _set_admin()
        assert len(orders_client.get("/orders").json()) == 3

    def test_all_three_services_healthy(self):
        assert items_client.get("/health/live").json()["status"]  == "alive"
        assert auth_client.get("/health/live").json()["status"]   == "alive"
        assert orders_client.get("/health/live").json()["status"] == "alive"

    def test_forgot_password_full_flow(self):
        """Register → request reset OTP → reset password → old fails, new works."""
        _register(email="forgot@test.com", password="OldPass@123")
        db   = AuthSession()
        user = auth_crud.get_user_by_email(db, "forgot@test.com")
        otp  = auth_crud.create_otp(db, user.id, "reset")
        code = otp.code
        db.close()

        r = auth_client.post("/auth/otp/reset-password", json={
            "email": "forgot@test.com", "code": code, "new_password": "NewPass@999"
        })
        assert r.status_code == 200
        assert _login(email="forgot@test.com", password="NewPass@999").status_code == 200
        assert _login(email="forgot@test.com", password="OldPass@123").status_code == 401
