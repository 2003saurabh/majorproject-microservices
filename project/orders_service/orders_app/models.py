from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Numeric, ForeignKey, func, Index, Text
)
from sqlalchemy.orm import relationship
from orders_app.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id",  "user_id"),
        Index("ix_orders_status",   "status"),
        {"schema": "orders"},
    )

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, nullable=False)           # FK to auth.users (cross-schema ref)
    status      = Column(String(30), nullable=False, default="pending")
    # Statuses: pending → confirmed → processing → shipped → delivered | cancelled
    notes       = Column(Text, nullable=True)
    total_price = Column(Numeric(10, 2), nullable=False, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    items            = relationship("OrderItem",          back_populates="order", cascade="all, delete-orphan")
    status_history   = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan",
                                    order_by="OrderStatusHistory.id")

    def __repr__(self):
        return f"<Order id={self.id} user={self.user_id} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = {"schema": "orders"}

    id          = Column(Integer, primary_key=True, index=True)
    order_id    = Column(Integer, ForeignKey("orders.orders.id"), nullable=False)
    item_id     = Column(Integer, nullable=False)           # FK to items.items (cross-schema ref)
    item_name   = Column(String(255), nullable=False)       # snapshot at order time
    quantity    = Column(Integer, nullable=False, default=1)
    unit_price  = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")


class OrderStatusHistory(Base):
    """Immutable audit trail of every status transition for an order."""
    __tablename__ = "order_status_history"
    __table_args__ = {"schema": "orders"}

    id          = Column(Integer, primary_key=True, index=True)
    order_id    = Column(Integer, ForeignKey("orders.orders.id"), nullable=False)
    from_status = Column(String(30), nullable=True)         # null for initial creation
    to_status   = Column(String(30), nullable=False)
    changed_by  = Column(Integer, nullable=True)            # user_id who triggered the change
    note        = Column(String(255), nullable=True)
    changed_at  = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="status_history")
