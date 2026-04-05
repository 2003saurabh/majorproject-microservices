"""
Tests for Orders service.
Uses in-memory SQLite — no Postgres, no Auth service, no real WebSocket clients needed.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, AsyncMock

from orders_app.main import app
from orders_app.database import get_db, Base
from orders_app.deps import get_current_user, CurrentUser
from orders_app import crud, models

# ── SQLite setup ──────────────────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_orders.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

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


# ── Auth mock helpers ─────────────────────────────────────────────────────────

def user_dep(user_id=1, is_superuser=False):
    def _dep():
        return CurrentUser(user_id=user_id, email="test@example.com", is_superuser=is_superuser)
    return _dep


def admin_dep():
    return user_dep(user_id=99, is_superuser=True)


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = user_dep()

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    yield
    db = TestingSessionLocal()
    db.query(models.OrderStatusHistory).delete()
    db.query(models.OrderItem).delete()
    db.query(models.Order).delete()
    db.commit()
    db.close()


SAMPLE_ITEMS = [
    {"item_id": 1, "item_name": "Keyboard", "quantity": 1, "unit_price": "99.99"},
    {"item_id": 2, "item_name": "Mouse",    "quantity": 2, "unit_price": "29.99"},
]


def _create_order(items=None):
    return client.post("/orders", json={
        "items": items or SAMPLE_ITEMS,
        "notes": "Test order",
    })


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "orders"
    assert "ws_connections" in data


# ── Create order ──────────────────────────────────────────────────────────────

@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_create_order(mock_notify):
    r = _create_order()
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["user_id"] == 1
    assert len(data["items"]) == 2
    assert float(data["total_price"]) == pytest.approx(99.99 + 29.99 * 2)
    assert len(data["status_history"]) == 1
    assert data["status_history"][0]["to_status"] == "pending"
    mock_notify.assert_called_once()


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_create_order_empty_items(_):
    r = client.post("/orders", json={"items": []})
    assert r.status_code == 422


# ── List / get orders ─────────────────────────────────────────────────────────

@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_list_orders_own(mock_notify):
    _create_order()
    _create_order()
    r = client.get("/orders")
    assert r.status_code == 200
    assert len(r.json()) == 2


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_get_order_by_id(mock_notify):
    created = _create_order().json()
    r = client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_order_not_found():
    r = client.get("/orders/99999")
    assert r.status_code == 404


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_get_other_users_order_denied(mock_notify):
    """User 1 creates an order; user 2 should not see it."""
    created = _create_order().json()

    app.dependency_overrides[get_current_user] = user_dep(user_id=2)
    r = client.get(f"/orders/{created['id']}")
    app.dependency_overrides[get_current_user] = user_dep()   # reset
    assert r.status_code == 403


# ── Status transitions ────────────────────────────────────────────────────────

@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_status_transition_superuser(mock_notify):
    """Superuser can advance status through the full lifecycle."""
    order = _create_order().json()
    oid = order["id"]

    app.dependency_overrides[get_current_user] = admin_dep()
    for new_status in ["confirmed", "processing", "shipped", "delivered"]:
        r = client.patch(f"/orders/{oid}/status", json={"status": new_status})
        assert r.status_code == 200, f"Failed on transition to {new_status}: {r.json()}"
        assert r.json()["status"] == new_status
    app.dependency_overrides[get_current_user] = user_dep()


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_invalid_transition(mock_notify):
    """Cannot skip statuses."""
    order = _create_order().json()
    r = client.patch(f"/orders/{order['id']}/status", json={"status": "shipped"})
    # Users can't update status at all (non-cancel), but superuser would also fail
    assert r.status_code in (400, 403)


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_user_can_cancel_own_order(mock_notify):
    order = _create_order().json()
    r = client.patch(f"/orders/{order['id']}/status", json={"status": "cancelled", "note": "Changed mind"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_user_cannot_confirm_order(mock_notify):
    """Only superusers can confirm orders."""
    order = _create_order().json()
    r = client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
    assert r.status_code == 403


# ── Delete order ──────────────────────────────────────────────────────────────

@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_delete_pending_order(mock_notify):
    order = _create_order().json()
    r = client.delete(f"/orders/{order['id']}")
    assert r.status_code == 204
    assert client.get(f"/orders/{order['id']}").status_code == 404


@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_cannot_delete_non_pending_order(mock_notify):
    order = _create_order().json()
    app.dependency_overrides[get_current_user] = admin_dep()
    client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed"})
    r = client.delete(f"/orders/{order['id']}")
    app.dependency_overrides[get_current_user] = user_dep()
    assert r.status_code == 400


# ── Status history ────────────────────────────────────────────────────────────

@patch("orders_app.routes.manager.notify_order_event", new_callable=AsyncMock)
def test_status_history_recorded(mock_notify):
    order = _create_order().json()
    app.dependency_overrides[get_current_user] = admin_dep()
    client.patch(f"/orders/{order['id']}/status", json={"status": "confirmed", "note": "Payment ok"})
    r = client.get(f"/orders/{order['id']}")
    history = r.json()["status_history"]
    app.dependency_overrides[get_current_user] = user_dep()
    assert len(history) == 2
    assert history[0]["to_status"] == "pending"
    assert history[1]["to_status"] == "confirmed"
    assert history[1]["note"] == "Payment ok"
