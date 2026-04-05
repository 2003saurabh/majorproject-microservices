import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session

from orders_app import crud, schemas
from orders_app.database import get_db
from orders_app.deps import get_current_user, get_superuser, decode_ws_token, CurrentUser
from orders_app.ws_manager import manager

log = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET  — real-time order updates
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/orders")
async def orders_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time order events.

    Connect: ws://host/ws/orders?token=<access_token>

    Events pushed from server:
      {"event": "order_created",  "order_id": 1,  "status": "pending"}
      {"event": "status_changed", "order_id": 1,  "status": "confirmed"}
      {"event": "order_cancelled","order_id": 1,  "status": "cancelled"}
      {"event": "ping"}

    Expected from client:
      {"event": "pong"}   — keep-alive response
    """
    try:
        user = decode_ws_token(token)
    except HTTPException:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user.user_id, user.is_superuser)
    try:
        # Send a welcome event confirming connection
        await websocket.send_text(json.dumps({
            "event":   "connected",
            "user_id": user.user_id,
            "message": "Listening for order updates...",
        }))

        # Keep connection alive, handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                msg  = json.loads(data)
                if msg.get("event") == "pong":
                    pass  # keep-alive acknowledged
            except (json.JSONDecodeError, KeyError):
                pass  # ignore malformed messages

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.user_id)


# ─────────────────────────────────────────────────────────────────────────────
# ORDERS — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/orders", response_model=schemas.OrderResponse, status_code=201, tags=["Orders"])
async def create_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Create a new order.
    Items are passed with a price snapshot — the caller is responsible for
    fetching current prices from the Items service before submitting.
    """
    order = crud.create_order(db, user.user_id, data)

    # Notify the user and any superusers via WebSocket
    await manager.notify_order_event(
        user_id=user.user_id,
        event="order_created",
        order_id=order.id,
        status=order.status,
        extra={"total_price": str(order.total_price)},
    )
    return order


@router.get("/orders", response_model=list[schemas.OrderResponse], tags=["Orders"])
def list_orders(
    status_filter: str | None = Query(None, alias="status"),
    skip:  int = Query(0,  ge=0),
    limit: int = Query(50, ge=1, le=200),
    db:   Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List orders.
    - Regular users see only their own orders.
    - Superusers see all orders (optionally filtered by status).
    """
    user_filter = None if user.is_superuser else user.user_id
    return crud.list_orders(db, user_id=user_filter, status=status_filter, skip=skip, limit=limit)


@router.get("/orders/{order_id}", response_model=schemas.OrderResponse, tags=["Orders"])
def get_order(
    order_id: int,
    db:   Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not user.is_superuser and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return order


@router.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse, tags=["Orders"])
async def update_order_status(
    order_id: int,
    data: schemas.OrderStatusUpdate,
    db:   Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Advance an order through its status lifecycle.
    Superusers can update any order.
    Regular users can only cancel their own pending/confirmed orders.
    """
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Permission check
    if not user.is_superuser:
        if order.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if data.status != schemas.OrderStatus.cancelled:
            raise HTTPException(status_code=403, detail="Users can only cancel orders")

    try:
        updated = crud.update_order_status(db, order, data.status.value, user.user_id, data.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Real-time notification
    event = "order_cancelled" if data.status == schemas.OrderStatus.cancelled else "status_changed"
    await manager.notify_order_event(
        user_id=order.user_id,
        event=event,
        order_id=order.id,
        status=updated.status,
        extra={"note": data.note},
    )
    return updated


@router.delete("/orders/{order_id}", status_code=204, tags=["Orders"])
async def delete_order(
    order_id: int,
    db:   Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a pending order. Only the owner or a superuser can delete."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not user.is_superuser and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending orders can be deleted. Cancel it first.")

    crud.delete_order(db, order)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — all orders overview
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/orders", response_model=list[schemas.OrderResponse], tags=["Admin"])
def admin_list_all_orders(
    status_filter: str | None = Query(None, alias="status"),
    skip:  int = Query(0,  ge=0),
    limit: int = Query(100, ge=1, le=500),
    db:   Session = Depends(get_db),
    _:    CurrentUser = Depends(get_superuser),
):
    """Superuser-only: list all orders across all users."""
    return crud.list_orders(db, user_id=None, status=status_filter, skip=skip, limit=limit)


@router.get("/admin/ws/stats", tags=["Admin"])
def ws_stats(_: CurrentUser = Depends(get_superuser)):
    """Return current WebSocket connection stats."""
    return {
        "total_connections": manager.total,
        "connected_users":   list(manager._connections.keys()),
        "superusers_online": list(manager._superusers),
    }
