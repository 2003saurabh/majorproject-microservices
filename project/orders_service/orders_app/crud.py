from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from orders_app import models, schemas
from orders_app.schemas import STATUS_TRANSITIONS


# ── Order CRUD ────────────────────────────────────────────────────────────────

def create_order(db: Session, user_id: int, data: schemas.OrderCreate) -> models.Order:
    total = sum(i.unit_price * i.quantity for i in data.items)

    order = models.Order(
        user_id=user_id,
        status="pending",
        notes=data.notes,
        total_price=total,
    )
    db.add(order)
    db.flush()  # get order.id without committing

    for item_data in data.items:
        db.add(models.OrderItem(
            order_id=order.id,
            item_id=item_data.item_id,
            item_name=item_data.item_name,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
        ))

    # Record initial status in history
    db.add(models.OrderStatusHistory(
        order_id=order.id,
        from_status=None,
        to_status="pending",
        changed_by=user_id,
        note="Order created",
    ))

    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> Optional[models.Order]:
    return (
        db.query(models.Order)
        .options(
            joinedload(models.Order.items),
            joinedload(models.Order.status_history),
        )
        .filter(models.Order.id == order_id)
        .first()
    )


def list_orders(
    db: Session,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[models.Order]:
    q = db.query(models.Order).options(
        joinedload(models.Order.items),
        joinedload(models.Order.status_history),
    )
    if user_id is not None:
        q = q.filter(models.Order.user_id == user_id)
    if status:
        q = q.filter(models.Order.status == status)
    return q.order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()


def update_order_status(
    db: Session,
    order: models.Order,
    new_status: str,
    changed_by: int,
    note: Optional[str] = None,
) -> models.Order:
    """
    Transition an order to a new status.
    Raises ValueError if the transition is invalid.
    """
    allowed = STATUS_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{order.status}' to '{new_status}'. "
            f"Allowed: {allowed or ['none']}"
        )

    db.add(models.OrderStatusHistory(
        order_id=order.id,
        from_status=order.status,
        to_status=new_status,
        changed_by=changed_by,
        note=note,
    ))

    order.status = new_status
    db.commit()
    db.refresh(order)
    return order


def delete_order(db: Session, order: models.Order) -> bool:
    """Only pending orders can be deleted (others should be cancelled)."""
    db.delete(order)
    db.commit()
    return True
