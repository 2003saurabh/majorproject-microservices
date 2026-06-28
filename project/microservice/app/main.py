from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
import os

from app.database import get_db, engine
from app import models, schemas, crud
from app.seed import seed_database
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Python Microservice",
    description="Production-ready microservice — ECS on EC2, RDS PostgreSQL, health checks",
    version="1.0.0",
    root_path="/items",
    docs_url="/docs"
)

START_TIME = time.time()

# CORS — required for S3-hosted frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # replace "*" with your S3 URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Runs once when the app starts — creates tables and seeds DB with 50 dummy items if empty."""
    models.Base.metadata.create_all(bind=engine)
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


# ─────────────────────────────────────────────
# HEALTH ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """Basic health info — uptime, version."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@app.get("/health/ready", tags=["Health"])
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe — verifies the app can reach the RDS database.
    Point your ALB target-group health check here.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        raise HTTPException(status_code=503, detail={"status": "not ready", "db": db_status})

    return {
        "status": "ready",
        "db": db_status,
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@app.get("/health/live", tags=["Health"])
def liveness_check():
    """
    Lightweight liveness probe — no DB call.
    Used by ECS EC2 container HEALTHCHECK and ALB.
    """
    return {"status": "alive"}


# ─────────────────────────────────────────────
# ITEMS RESOURCE
# ─────────────────────────────────────────────

@app.get("/", tags=["Root"])
def root():
    return {"message": "Microservice is running", "docs": "/docs"}


@app.post("/items", response_model=schemas.ItemResponse, status_code=201, tags=["Items"])
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, item)


@app.get("/items", response_model=list[schemas.ItemResponse], tags=["Items"])
def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_items(db, skip=skip, limit=limit)


@app.get("/items/{item_id}", response_model=schemas.ItemResponse, tags=["Items"])
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.put("/items/{item_id}", response_model=schemas.ItemResponse, tags=["Items"])
def update_item(item_id: int, updates: schemas.ItemUpdate, db: Session = Depends(get_db)):
    item = crud.update_item(db, item_id, updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.delete("/items/{item_id}", status_code=204, tags=["Items"])
def delete_item(item_id: int, db: Session = Depends(get_db)):
    if not crud.delete_item(db, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
