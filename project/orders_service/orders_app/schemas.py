from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class OrderStatus(str, Enum):
    pending    = "pending"
    confirmed  = "confirmed"
    processing = "processing"
    shipped    = "shipped"
    delivered  = "delivered"
    cancelled  = "cancelled"


# Valid transitions: what each status can move to
STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending":    ["confirmed", "cancelled"],
    "confirmed":  ["processing", "cancelled"],
    "processing": ["shipped", "cancelled"],
    "shipped":    ["delivered"],
    "delivered":  [],
    "cancelled":  [],
}


# ── Order Item schemas ────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    item_id:    int
    item_name:  str = Field(..., max_length=255)
    quantity:   int = Field(..., ge=1, le=1000)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)


class OrderItemResponse(BaseModel):
    id:         int
    item_id:    int
    item_name:  str
    quantity:   int
    unit_price: Decimal

    model_config = {"from_attributes": True}


# ── Status History schemas ────────────────────────────────────────────────────

class StatusHistoryResponse(BaseModel):
    id:          int
    from_status: Optional[str]
    to_status:   str
    changed_by:  Optional[int]
    note:        Optional[str]
    changed_at:  datetime

    model_config = {"from_attributes": True}


# ── Order schemas ─────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(..., min_length=1)
    notes: Optional[str] = Field(None, max_length=1000)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    note:   Optional[str] = Field(None, max_length=255)


class OrderResponse(BaseModel):
    id:             int
    user_id:        int
    status:         str
    notes:          Optional[str]
    total_price:    Decimal
    created_at:     datetime
    updated_at:     Optional[datetime]
    items:          list[OrderItemResponse]
    status_history: list[StatusHistoryResponse]

    model_config = {"from_attributes": True}


class OrderSummary(BaseModel):
    """Lightweight response for list endpoints."""
    id:          int
    user_id:     int
    status:      str
    total_price: Decimal
    item_count:  int
    created_at:  datetime
    updated_at:  Optional[datetime]

    model_config = {"from_attributes": True}


# ── WebSocket message schemas ─────────────────────────────────────────────────

class WSMessage(BaseModel):
    event:    str          # "order_created" | "status_changed" | "order_cancelled" | "ping"
    order_id: Optional[int] = None
    status:   Optional[str] = None
    payload:  Optional[dict] = None
