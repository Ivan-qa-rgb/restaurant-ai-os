"""Меню: состав и аллергены отдаются только из подтверждённых карточек."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from .db import get_db
from .models import AuditLog, Dish, now_utc
from .security import Principal, require

router = APIRouter()

ALLERGENS = {"gluten", "milk", "eggs", "fish", "shellfish", "nuts", "peanuts",
             "soy", "celery", "mustard", "sesame"}
Item = Annotated[str, StringConstraints(min_length=1, max_length=80)]
UNVERIFIED = "Состав и аллергены не подтверждены. Передайте вопрос сотруднику."


class DishIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price_kop: int = Field(ge=0, le=1_000_000)
    ingredients: list[Item] = Field(max_length=100)
    allergens: list[str] = Field(max_length=len(ALLERGENS))

    @field_validator("allergens")
    @classmethod
    def known(cls, v):
        if not set(v) <= ALLERGENS:
            raise ValueError("Неизвестный аллерген")
        return v


class AvailIn(BaseModel):
    available: bool


def _audit(db, p, action, obj):
    db.add(AuditLog(org_id=p.org_id, user_id=p.user_id, action=action, object_id=obj))


def _get(db, p, dish_id) -> Dish:
    d = db.scalar(select(Dish).where(Dish.id == dish_id, Dish.org_id == p.org_id))
    if not d:
        raise HTTPException(404, "Блюдо не найдено")
    return d


def _fill(d: Dish, body: DishIn):
    d.name, d.price_kop = body.name, body.price_kop
    d.ingredients = "\n".join(body.ingredients)
    d.allergens = ",".join(sorted(set(body.allergens)))
    d.card_status, d.verified_by, d.verified_at = "draft", None, None


def _out(d: Dish) -> dict:
    ok = d.card_status == "verified"
    out = {
        "id": d.id,
        "name": d.name,
        "price_kop": d.price_kop,
        "available": d.available,
        "card_verified": ok
    }

    if ok:
        out["ingredients"] = d.ingredients.split("\n") if d.ingredients else []
        out["allergens"] = d.allergens.split(",") if d.allergens else []

    return out


@router.get("/menu/public")
def public_menu(db: DbSession = Depends(get_db)):
    dishes = db.scalars(
        select(Dish).where(Dish.available)
    ).all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "price_kop": d.price_kop,
            "ingredients": d.ingredients.split("\n") if d.ingredients else [],
            "allergens": d.allergens.split(",") if d.allergens else []
        }
        for d in dishes
        if d.card_status == "verified"
    ]


@router.post("/menu/dishes", status_code=201)
def create_dish(body: DishIn, p: Principal = Depends(require("menu:write")),
                db: DbSession = Depends(get_db)):
    d = Dish(org_id=p.org_id)
    _fill(d, body)
    db.add(d)
    db.flush()
    _audit(db, p, "dish.create", d.id)
    db.commit()
    return _out(d)


@router.put("/menu/dishes/{dish_id}")
def update_dish(dish_id: int, body: DishIn, p: Principal = Depends(require("menu:write")),
                db: DbSession = Depends(get_db)):
    d = _get(db, p, dish_id)
    _fill(d, body)
    d.version += 1
    _audit(db, p, "dish.update", d.id)
    db.commit()
    return _out(d)


@router.post("/menu/dishes/{dish_id}/verify")
def verify_dish(dish_id: int, p: Principal = Depends(require("menu:write")),
                db: DbSession = Depends(get_db)):
    d = _get(db, p, dish_id)

    if not d.ingredients:
        raise HTTPException(422, "Нельзя подтвердить карточку без состава")

    d.card_status, d.verified_by, d.verified_at = "verified", p.user_id, now_utc()
    _audit(db, p, "dish.verify", d.id)
    db.commit()
    return _out(d)


@router.post("/menu/dishes/{dish_id}/available")
def set_available(dish_id: int, body: AvailIn, p: Principal = Depends(require("menu:write")),
                  db: DbSession = Depends(get_db)):
    d = _get(db, p, dish_id)
    d.available = body.available
    _audit(db, p, "dish.availability", d.id)
    db.commit()
    return _out(d)


@router.get("/menu")
def menu(p: Principal = Depends(require("menu:read")), db: DbSession = Depends(get_db)):
    return [_out(d) for d in db.scalars(select(Dish).where(Dish.org_id == p.org_id))]


@router.get("/menu/dishes/{dish_id}/allergens")
def allergens(dish_id: int, p: Principal = Depends(require("menu:read")),
              db: DbSession = Depends(get_db)):
    d = _get(db, p, dish_id)

    if d.card_status != "verified":
        raise HTTPException(409, UNVERIFIED)

    return _out(d)