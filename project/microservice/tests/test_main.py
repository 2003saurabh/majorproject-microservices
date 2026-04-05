import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base

# ── In-memory SQLite for tests (no RDS needed) ────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── Health tests ─────────────────────────────────────────────────────────────

def test_health_live():
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_health_basic():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_health_ready():
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["db"] == "connected"


# ── Items CRUD tests ──────────────────────────────────────────────────────────

def test_create_item():
    r = client.post("/items", json={"name": "Test Item", "description": "A test"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Item"
    assert data["id"] is not None


def test_list_items():
    r = client.get("/items")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_item():
    created = client.post("/items", json={"name": "Fetch Me"}).json()
    r = client.get(f"/items/{created['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Fetch Me"


def test_get_item_not_found():
    r = client.get("/items/99999")
    assert r.status_code == 404


def test_update_item():
    created = client.post("/items", json={"name": "Old Name"}).json()
    r = client.put(f"/items/{created['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_delete_item():
    created = client.post("/items", json={"name": "Delete Me"}).json()
    r = client.delete(f"/items/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/items/{created['id']}").status_code == 404
