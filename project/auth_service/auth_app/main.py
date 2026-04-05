import time
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth_app.config import get_settings
from auth_app.database import create_schema, engine
from auth_app import models
from auth_app.routes import router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

settings = get_settings()
START_TIME = time.time()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Users & Auth Service",
    description=(
        "Handles user registration, JWT authentication, email verification, "
        "password reset, and passwordless OTP login."
    ),
    version="1.0.0",
    root_path="/auth",
    docs_url="/docs"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to your S3 / domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    log.info("Creating auth schema and tables...")
    create_schema()
    models.Base.metadata.create_all(bind=engine)
    log.info("Auth service ready.")


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "alive"}


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
        "service": "auth",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@app.get("/health/ready", tags=["Health"])
def readiness():
    from sqlalchemy import text
    from auth_app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"db": str(e)})
    finally:
        db.close()


@app.get("/", tags=["Root"])
def root():
    return {"service": "auth", "docs": "/docs"}
