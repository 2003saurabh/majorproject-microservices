import asyncio
import logging
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orders_app.config import get_settings
from orders_app.database import create_schema, engine
from orders_app import models
from orders_app.routes import router
from orders_app.ws_manager import start_ping_loop

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

settings  = get_settings()
START_TIME = time.time()


# ── Lifespan (startup + background tasks) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Creating orders schema and tables...")
    create_schema()
    models.Base.metadata.create_all(bind=engine)
    log.info("Orders service ready.")

    # Start WebSocket keep-alive ping loop in background
    ping_task = asyncio.create_task(start_ping_loop(interval=25))
    try:
        yield
    finally:
        ping_task.cancel()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Orders Service",
    description=(
        "Manages orders with full CRUD, status lifecycle, and real-time "
        "WebSocket push notifications for every status transition."
    ),
    version="1.0.0",
    root_path="/orders",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "alive"}


@app.get("/health", tags=["Health"])
def health():
    from orders_app.ws_manager import manager
    return {
        "status":            "healthy",
        "service":           "orders",
        "version":           "1.0.0",
        "uptime_seconds":    round(time.time() - START_TIME, 2),
        "ws_connections":    manager.total,
    }


@app.get("/health/ready", tags=["Health"])
def readiness():
    from sqlalchemy import text
    from orders_app.database import SessionLocal
    from fastapi import HTTPException
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"db": str(e)})
    finally:
        db.close()


@app.get("/", tags=["Root"])
def root():
    return {"service": "orders", "docs": "/docs"}
