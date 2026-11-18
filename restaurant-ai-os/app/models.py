from datetime import datetime, time as dtime, timezone
from sqlalchemy import (ForeignKey, String, Integer, DateTime, Boolean, Text, Time,
                        UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now_utc() -> datetime:
    """Время хранится как наивное UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone_name: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    open_time: Mapped[dtime] = mapped_column(Time, default=dtime(10, 0))
    close_time: Mapped[dtime] = mapped_column(Time, default=dtime(23, 0))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    pw_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class DiningTable(Base):
    __tablename__ = "dining_tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    capacity: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_res_idem"),
        Index("ix_res_table_time", "table_id", "start_at", "end_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("dining_tables.id"))
    guest_name: Mapped[str] = mapped_column(String(100))
    party_size: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="confirmed")
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AuditLog(Base):
    """Без персональных данных: только id и тип действия."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    org_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Dish(Base):
    __tablename__ = "dishes"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    price_kop: Mapped[int] = mapped_column(Integer)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    ingredients: Mapped[str] = mapped_column(Text, default="")
    allergens: Mapped[str] = mapped_column(String(200), default="")

    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="Другое")
    image_url: Mapped[str] = mapped_column(String(300), default="")
    weight_g: Mapped[int] = mapped_column(Integer, default=0)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spicy: Mapped[bool] = mapped_column(Boolean, default=False)

    card_status: Mapped[str] = mapped_column(String(10), default="draft")
    verified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RateHit(Base):
    __tablename__ = "rate_hits"
    __table_args__ = (Index("ix_rate_hits_key_at", "key", "at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80))
    at: Mapped[datetime] = mapped_column(DateTime)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("org_id", "idempotency_key", name="uq_order_idem"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "idempotency_key", name="uq_item_idem"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"))
    dish_name: Mapped[str] = mapped_column(String(120))
    unit_price_kop: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id")
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)