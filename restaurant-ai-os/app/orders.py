"""Заказы и очередь кухни. Цена и название фиксируются в позиции на момент заказа.
Стоимость позиций - не выручка: оплаты в системе нет."""
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from .db import get_db
from .models import AuditLog, DiningTable, Dish, Order, OrderItem
from .security import PERMS, Principal, current_principal, require

router = APIRouter()
FLOW = {("open", "sent"): "orders:write", ("open", "cancelled"): "orders:write",
        ("sent", "cancelled"): "orders:write", ("sent", "preparing"): "kitchen:write",
        ("preparing", "ready"): "kitchen:write", ("ready", "served"): "orders:write"}
MAX_ITEMS = 100
KEY = Header(default=None, max_length=80)


class OrderIn(BaseModel):
    table_id: int | None = None


class ItemIn(BaseModel):
    dish_id: int
    qty: int = Field(ge=1, le=50)


class StatusIn(BaseModel):
    status: Literal["sent", "preparing", "ready", "served", "cancelled"]


def _audit(db, p, action, obj):
    db.add(AuditLog(org_id=p.org_id, user_id=p.user_id, action=action, object_id=obj))


def _order(db, p, order_id) -> Order:
    o = db.scalar(select(Order).where(Order.id == order_id, Order.org_id == p.org_id))
    if not o:
        raise HTTPException(404, "Заказ не найден")
    return o


def _out(db, o: Order) -> dict:
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == o.id)
                       .order_by(OrderItem.id)).all()
    return {"id": o.id, "table_id": o.table_id, "status": o.status,
            "created_at_utc": o.created_at.isoformat() + "Z",
            "items": [{"id": i.id, "dish_id": i.dish_id, "dish_name": i.dish_name,
                       "unit_price_kop": i.unit_price_kop, "qty": i.qty} for i in items],
            "items_total_kop": sum(i.unit_price_kop * i.qty for i in items)}


@router.post("/orders", status_code=201)
def create_order(body: OrderIn, idempotency_key: str | None = KEY,
                 p: Principal = Depends(require("orders:write")),
                 db: DbSession = Depends(get_db)):
    def find():
        return db.scalar(select(Order).where(Order.org_id == p.org_id,
                                             Order.idempotency_key == idempotency_key))
    if idempotency_key and (prev := find()):
        if prev.table_id != body.table_id:
            raise HTTPException(422, "Idempotency-Key уже использован с другими данными")
        return _out(db, prev)
    if body.table_id is not None and not db.scalar(select(DiningTable.id).where(
            DiningTable.id == body.table_id, DiningTable.org_id == p.org_id,
            DiningTable.active)):
        raise HTTPException(404, "Стол не найден")
    o = Order(org_id=p.org_id, table_id=body.table_id, created_by=p.user_id,
              idempotency_key=idempotency_key)
    db.add(o)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (prev := find()):
            return _out(db, prev)
        raise HTTPException(409, "Конфликт при создании заказа")
    _audit(db, p, "order.create", o.id)
    db.commit()
    return _out(db, o)


@router.post("/orders/{order_id}/items", status_code=201)
def add_item(order_id: int, body: ItemIn, idempotency_key: str | None = KEY,
             p: Principal = Depends(require("orders:write")), db: DbSession = Depends(get_db)):
    o = _order(db, p, order_id)

    def find():
        return db.scalar(select(OrderItem).where(OrderItem.order_id == o.id,
                                                 OrderItem.idempotency_key == idempotency_key))
    if idempotency_key and (prev := find()):
        if (prev.dish_id, prev.qty) != (body.dish_id, body.qty):
            raise HTTPException(422, "Idempotency-Key уже использован с другими данными")
        return _out(db, o)
    dish = db.scalar(select(Dish).where(Dish.id == body.dish_id, Dish.org_id == p.org_id))
    if not dish:
        raise HTTPException(404, "Блюдо не найдено")
    if not dish.available:
        raise HTTPException(409, "Блюдо недоступно")
    # Атомарная проверка статуса: позиции добавляются только пока заказ open.
    n = db.execute(update(Order).where(Order.id == o.id, Order.org_id == p.org_id,
                                       Order.status == "open")
                   .values(version=Order.version + 1)).rowcount
    if n != 1:
        db.rollback()
        raise HTTPException(409, "Заказ уже отправлен или закрыт")
    cnt = db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.order_id == o.id))
    if cnt >= MAX_ITEMS:
        db.rollback()
        raise HTTPException(422, "Слишком много позиций в заказе")
    db.add(OrderItem(order_id=o.id, org_id=p.org_id, dish_id=dish.id, dish_name=dish.name,
                     unit_price_kop=dish.price_kop, qty=body.qty,
                     idempotency_key=idempotency_key))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key and find():
            return _out(db, o)
        raise HTTPException(409, "Конфликт при добавлении позиции")
    _audit(db, p, "order.add_item", o.id)
    db.commit()
    return _out(db, o)


@router.get("/orders/{order_id}")
def get_order(order_id: int, p: Principal = Depends(require("orders:read")),
              db: DbSession = Depends(get_db)):
    return _out(db, _order(db, p, order_id))


@router.post("/orders/{order_id}/status")
def set_status(order_id: int, body: StatusIn, p: Principal = Depends(current_principal),
               db: DbSession = Depends(get_db)):
    o = _order(db, p, order_id)
    if o.status == body.status:
        return _out(db, o)  # повтор того же перехода безвреден
    need = FLOW.get((o.status, body.status))
    if not need:
        raise HTTPException(409, "Недопустимый переход статуса")
    if need not in PERMS.get(p.role, set()):
        raise HTTPException(403, "Недостаточно прав")
    # compare-and-set: срабатывает только если статус не изменился с момента чтения.
    n = db.execute(update(Order).where(Order.id == o.id, Order.org_id == p.org_id,
                                       Order.status == o.status)
                   .values(status=body.status, version=Order.version + 1)).rowcount
    if n != 1:
        db.rollback()
        raise HTTPException(409, "Заказ изменён другим запросом, повторите")
    _audit(db, p, f"order.status.{body.status}", o.id)
    db.commit()
    return _out(db, _order(db, p, order_id))


@router.get("/kitchen/queue")
def kitchen_queue(p: Principal = Depends(require("kitchen:read")),
                  db: DbSession = Depends(get_db)):
    rows = db.scalars(select(Order).where(Order.org_id == p.org_id,
                                          Order.status.in_(("sent", "preparing")))
                      .order_by(Order.created_at, Order.id).limit(200)).all()
    return [_out(db, o) for o in rows]
