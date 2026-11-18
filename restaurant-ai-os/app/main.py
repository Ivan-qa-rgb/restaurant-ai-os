import os
import threading
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from .db import Base, engine, get_db
from . import menu, orders
from .hours import within_hours
from .models import AuditLog, DiningTable, Organization, Reservation, User
from .models import Session as SessionRow
from .security import (CREATABLE, Principal, auth_limit, current_principal, hash_password,
                       new_session, require, token_digest, verify_password)

app = FastAPI(title="Restaurant AI OS", docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
_auto = "1" if str(engine.url).startswith("sqlite") else "0"
if os.environ.get("AUTO_CREATE_TABLES", _auto) == "1":  # SQLite/dev; PostgreSQL только через Alembic
    Base.metadata.create_all(engine)
@app.get("/menu-page", include_in_schema=False)
def menu_page():
    return FileResponse("static/menu.html")
app.include_router(menu.router)
app.include_router(orders.router)

from .concierge import router as concierge_router
app.include_router(concierge_router)

from .knowledge.router import router as knowledge_router
app.include_router(knowledge_router)
_book_lock = threading.Lock()  # для SQLite; в PostgreSQL дополнительно FOR UPDATE

EMAIL_RE = r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$"


def audit(db, org_id, user_id, action, obj=None):
    db.add(AuditLog(org_id=org_id, user_id=user_id, action=action, object_id=obj))


class RegisterIn(BaseModel):
    org_name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL_RE, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def lower(cls, v): return v.lower()


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=254)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def lower(cls, v): return v.lower()


class StaffIn(RegisterIn):
    org_name: str = Field(default="", max_length=120)
    role: str


class TableIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    capacity: int = Field(ge=1, le=50)


class ReservationIn(BaseModel):
    table_id: int
    guest_name: str = Field(min_length=1, max_length=100)
    party_size: int = Field(ge=1, le=50)
    start: datetime
    duration_min: int = Field(default=90, ge=30, le=240)

    @field_validator("start")
    @classmethod
    def tz_required(cls, v):
        if v.tzinfo is None:
            raise ValueError("Нужен часовой пояс, например 2030-01-01T19:00:00+03:00")
        return v


def res_out(r: Reservation) -> dict:
    return {"id": r.id, "table_id": r.table_id, "guest_name": r.guest_name,
            "party_size": r.party_size, "start_utc": r.start_at.isoformat() + "Z",
            "end_utc": r.end_at.isoformat() + "Z", "status": r.status}


@app.post("/auth/register", status_code=201)
def register(body: RegisterIn, _: None = Depends(auth_limit), db: DbSession = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Не удалось зарегистрироваться")
    org = Organization(name=body.org_name)
    db.add(org); db.flush()
    user = User(org_id=org.id, email=body.email,
                pw_hash=hash_password(body.password), role="owner")
    db.add(user); db.flush()
    token = new_session(db, user.id)
    audit(db, org.id, user.id, "org.register", org.id)
    db.commit()
    return {"token": token}


@app.post("/auth/login")
def login(body: LoginIn, _: None = Depends(auth_limit), db: DbSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not user.active or not verify_password(body.password, user.pw_hash):
        raise HTTPException(401, "Неверный email или пароль")
    token = new_session(db, user.id)
    audit(db, user.org_id, user.id, "auth.login")
    db.commit()
    return {"token": token}


@app.post("/auth/logout")
def logout(authorization: str = Header(default=""), p: Principal = Depends(current_principal),
           db: DbSession = Depends(get_db)):
    token = authorization.partition(" ")[2]
    db.execute(delete(SessionRow).where(SessionRow.token_hash == token_digest(token)))
    audit(db, p.org_id, p.user_id, "auth.logout")
    db.commit()
    return {"ok": True}


@app.post("/auth/logout-all")
def logout_all(p: Principal = Depends(current_principal), db: DbSession = Depends(get_db)):
    db.execute(delete(SessionRow).where(SessionRow.user_id == p.user_id))
    audit(db, p.org_id, p.user_id, "auth.logout_all")
    db.commit()
    return {"ok": True}


@app.post("/staff/{user_id}/deactivate")
def deactivate_staff(user_id: int, p: Principal = Depends(require("staff:write")),
                     db: DbSession = Depends(get_db)):
    u = db.scalar(select(User).where(User.id == user_id, User.org_id == p.org_id))
    if not u:
        raise HTTPException(404, "Сотрудник не найден")
    if u.id == p.user_id or (u.role == "owner" and p.role != "owner"):
        raise HTTPException(403, "Нельзя отключить этого пользователя")
    u.active = False
    db.execute(delete(SessionRow).where(SessionRow.user_id == u.id))  # отзыв всех сессий
    audit(db, p.org_id, p.user_id, "staff.deactivate", u.id)
    db.commit()
    return {"id": u.id, "active": False}


@app.post("/staff", status_code=201)
def add_staff(body: StaffIn, p: Principal = Depends(require("staff:write")),
              db: DbSession = Depends(get_db)):
    if body.role not in CREATABLE.get(p.role, set()):
        raise HTTPException(403, "Нельзя назначить эту роль")
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Email уже занят")
    u = User(org_id=p.org_id, email=body.email,
             pw_hash=hash_password(body.password), role=body.role)
    db.add(u); db.flush()
    audit(db, p.org_id, p.user_id, "staff.create", u.id)
    db.commit()
    return {"id": u.id, "role": u.role}


@app.post("/tables", status_code=201)
def add_table(body: TableIn, p: Principal = Depends(require("tables:write")),
              db: DbSession = Depends(get_db)):
    t = DiningTable(org_id=p.org_id, name=body.name, capacity=body.capacity)
    db.add(t); db.flush()
    audit(db, p.org_id, p.user_id, "table.create", t.id)
    db.commit()
    return {"id": t.id, "name": t.name, "capacity": t.capacity}


@app.get("/tables")
def list_tables(p: Principal = Depends(require("tables:read")),
                db: DbSession = Depends(get_db)):
    rows = db.scalars(select(DiningTable).where(
        DiningTable.org_id == p.org_id, DiningTable.active)).all()
    return [{"id": t.id, "name": t.name, "capacity": t.capacity} for t in rows]


@app.post("/reservations", status_code=201)
def create_reservation(body: ReservationIn,
                       idempotency_key: str | None = Header(default=None, max_length=80),
                       p: Principal = Depends(require("res:write")),
                       db: DbSession = Depends(get_db)):
    start = body.start.astimezone(timezone.utc).replace(tzinfo=None)
    end = start + timedelta(minutes=body.duration_min)
    org = db.get(Organization, p.org_id)
    local_start = body.start.astimezone(ZoneInfo(org.timezone_name)).replace(tzinfo=None)
    local_end = local_start + timedelta(minutes=body.duration_min)
    if not within_hours(local_start, local_end, org.open_time, org.close_time):
        raise HTTPException(422, "Вне часов работы ресторана")
    with _book_lock:
        if idempotency_key:
            prev = db.scalar(select(Reservation).where(
                Reservation.org_id == p.org_id, Reservation.idempotency_key == idempotency_key))
            if prev:
                same = (prev.table_id, prev.party_size, prev.start_at, prev.end_at) == \
                       (body.table_id, body.party_size, start, end)
                if not same:
                    raise HTTPException(422, "Idempotency-Key уже использован с другими данными")
                return res_out(prev)

        # ??????? ????????? ????????????? ??????, ????? ????????? ????? ????? ? ???????.
        if body.start <= datetime.now(timezone.utc):
            raise HTTPException(422, "???? ? ????? ????? ?????? ???? ? ???????")

        table = db.scalar(select(DiningTable).where(
            DiningTable.id == body.table_id, DiningTable.org_id == p.org_id,
            DiningTable.active).with_for_update())
        if not table:
            raise HTTPException(404, "Стол не найден")
        if body.party_size > table.capacity:
            raise HTTPException(422, "Гостей больше, чем мест за столом")
        clash = db.scalar(select(Reservation.id).where(
            Reservation.table_id == table.id, Reservation.status == "confirmed",
            Reservation.start_at < end, Reservation.end_at > start))
        if clash:
            raise HTTPException(409, "Стол занят на это время")
        r = Reservation(org_id=p.org_id, table_id=table.id, guest_name=body.guest_name,
                        party_size=body.party_size, start_at=start, end_at=end,
                        idempotency_key=idempotency_key)
        db.add(r)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Стол занят или повторный запрос")
        audit(db, p.org_id, p.user_id, "reservation.create", r.id)
        db.commit()
        return res_out(r)


@app.get("/reservations")
def list_reservations(p: Principal = Depends(require("res:read")),
                      db: DbSession = Depends(get_db)):
    rows = db.scalars(select(Reservation).where(Reservation.org_id == p.org_id)
                      .order_by(Reservation.start_at)).all()
    return [res_out(r) for r in rows]


@app.post("/reservations/{res_id}/cancel")
def cancel(res_id: int, p: Principal = Depends(require("res:write")),
           db: DbSession = Depends(get_db)):
    r = db.scalar(select(Reservation).where(
        Reservation.id == res_id, Reservation.org_id == p.org_id))
    if not r:
        raise HTTPException(404, "Бронь не найдена")
    r.status = "cancelled"
    audit(db, p.org_id, p.user_id, "reservation.cancel", r.id)
    db.commit()
    return res_out(r)


class HoursIn(BaseModel):
    tz_name: str = Field(max_length=64)
    open_time: dtime
    close_time: dtime

    @field_validator("tz_name")
    @classmethod
    def known_tz(cls, v):
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Неизвестный часовой пояс")
        return v


@app.put("/settings/hours")
def set_hours(body: HoursIn, p: Principal = Depends(require("tables:write")),
              db: DbSession = Depends(get_db)):
    if body.open_time == body.close_time:
        raise HTTPException(422, "Время открытия и закрытия не должно совпадать")
    org = db.get(Organization, p.org_id)
    org.timezone_name, org.open_time, org.close_time = body.tz_name, body.open_time, body.close_time
    audit(db, p.org_id, p.user_id, "settings.hours", org.id)
    db.commit()
    return {"tz_name": org.timezone_name, "open_time": str(org.open_time),
            "close_time": str(org.close_time)}
