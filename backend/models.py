from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    ForeignKey,
    JSON
)

from sqlalchemy.orm import relationship

from backend.database import Base


# =========================================================
# ORDERS
# =========================================================

class Order(Base):

    __tablename__ = "orders"

    id = Column(
        String(50),
        primary_key=True
    )

    amount = Column(
        Integer,
        nullable=False
    )

    currency = Column(
        String(10),
        nullable=False,
        default="INR"
    )

    status = Column(
        String(30),
        nullable=False,
        default="PENDING_PAYMENT"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    payment = relationship(
        "Payment",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )


# =========================================================
# ORDER ITEMS
# =========================================================

class OrderItem(Base):

    __tablename__ = "order_items"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    order_id = Column(
        String(50),
        ForeignKey("orders.id"),
        nullable=False
    )

    product_id = Column(
        String(50),
        nullable=False
    )

    product_name = Column(
        String(255),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    unit_price = Column(
        Integer,
        nullable=False
    )

    total_price = Column(
        Integer,
        nullable=False
    )

    order = relationship(
        "Order",
        back_populates="items"
    )


# =========================================================
# PAYMENTS
# =========================================================

class Payment(Base):

    __tablename__ = "payments"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    order_id = Column(
        String(50),
        ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    razorpay_order_id = Column(
        String(100),
        nullable=False,
        unique=True
    )

    razorpay_payment_id = Column(
        String(100),
        nullable=True,
        unique=True
    )

    status = Column(
        String(30),
        nullable=False,
        default="CREATED"
    )

    verified_at = Column(
        DateTime,
        nullable=True
    )

    order = relationship(
        "Order",
        back_populates="payment"
    )


# =========================================================
# AUDIT LOGS
# =========================================================

class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    event_type = Column(
        String(100),
        nullable=False
    )

    order_id = Column(
        String(50),
        nullable=True
    )

    details = Column(
        JSON,
        nullable=True
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )