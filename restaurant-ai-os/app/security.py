import hashlib, hmac, os, secrets, threading, time
from datetime import timedelta
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session as DbSession
import ipaddress
from .db import SessionLocal, get_db
from .models import RateHit, Session, User, now_utc

SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "12"))
ROLES = {"owner", "manager", "host", "waiter"}
# Права задаются на сервере, а не клиентом и не LLM.
PERMS = {
    "owner": {
        "staff:write", "tables:write", "tables:read",
        "res:write", "res:read",
        "knowledge:write", "knowledge:read",
    },
    "manager": {
        "staff:write", "tables:write", "tables:read",
        "res:write", "res:read",
        "knowledge:write", "knowledge:read",
    },
    "host": {
        "tables:read", "res:write", "res:read",
        "knowledge:read",
    },
    "waiter": {
        "tables:read", "res:read",
        "knowledge:read",
    },
}
CREATABLE = {"owner": ROLES, "manager": ROLES - {"owner"}}


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
        h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(h.hex(), h_hex)
    except ValueError:
        return False


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(db: DbSession, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=_digest(token), user_id=user_id,
                   expires_at=now_utc() + timedelta(hours=SESSION_HOURS)))
    return token


@dataclass
class Principal:
    user_id: int
    org_id: int
    role: str


def current_principal(authorization: str = Header(default=""),
                      db: DbSession = Depends(get_db)) -> Principal:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Требуется авторизация")
    row = db.execute(
        select(Session, User).join(User, User.id == Session.user_id)
        .where(Session.token_hash == _digest(token))
    ).first()
    if not row or row[0].expires_at < now_utc() or not row[1].active:
        raise HTTPException(401, "Сессия недействительна")
    u = row[1]
    # org_id и роль берутся из БД, а не из запроса.
    return Principal(u.id, u.org_id, u.role)


def require(perm: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if perm not in PERMS.get(p.role, set()):
            raise HTTPException(403, "Недостаточно прав")
        return p
    return dep


# Права меню добавляются отдельно: читать могут все, менять и подтверждать - owner/manager.
for _r in PERMS:
    PERMS[_r].add("menu:read")
for _r in ("owner", "manager"):
    PERMS[_r].add("menu:write")

token_digest = _digest
ROLES.add("cook")
PERMS["cook"] = {"menu:read", "orders:read", "kitchen:read", "kitchen:write"}
for _r in ("owner", "manager"):
    PERMS[_r] |= {"orders:write", "orders:read", "kitchen:read", "kitchen:write"}
PERMS["waiter"] |= {"orders:write", "orders:read"}
PERMS["host"] |= {"orders:read"}
CREATABLE["owner"] = ROLES
CREATABLE["manager"] = ROLES - {"owner"}


def _trusted_nets():
    # Неверная запись в TRUSTED_PROXIES вызовет ошибку (fail closed), а не молчаливый обход.
    return [ipaddress.ip_network(x.strip(), strict=False)
            for x in os.environ.get("TRUSTED_PROXIES", "").split(",") if x.strip()]


def client_ip(request: Request) -> str:
    """X-Forwarded-For учитывается только если соединение пришло от доверенного прокси;
    берётся первый справа адрес, не входящий в доверенные."""
    peer = request.client.host if request.client else "unknown"
    nets = _trusted_nets()

    def trusted(a):
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            return False
        return any(ip in n for n in nets)

    if not nets or not trusted(peer):
        return peer
    chain = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
    for addr in reversed(chain):
        try:
            ipaddress.ip_address(addr)
        except ValueError:
            return peer
        if not trusted(addr):
            return addr
    return chain[0] if chain else peer


class RateLimiter:
    """Скользящее окно, общее для процессов: счётчики в таблице rate_hits.
    В PostgreSQL проверка сериализуется advisory-локом по ключу; в SQLite возможен
    небольшой перерасход при гонке. Недоступность БД = отказ (fail closed)."""

    def __init__(self, max_calls: int, window: float, scope: str = "auth"):
        self.max, self.window, self.scope = max_calls, window, scope

    def reset(self):
        with SessionLocal() as db:
            db.execute(delete(RateHit))
            db.commit()

    def __call__(self, request: Request):
        key = f"{self.scope}:{client_ip(request)}"[:80]
        now = now_utc()
        cutoff = now - timedelta(seconds=self.window)
        with SessionLocal() as db:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": key})
            n = db.scalar(select(func.count()).select_from(RateHit)
                          .where(RateHit.key == key, RateHit.at > cutoff))
            if n >= self.max:
                db.rollback()
                raise HTTPException(429, "Слишком много запросов",
                                    headers={"Retry-After": str(int(self.window))})
            db.add(RateHit(key=key, at=now))
            db.execute(delete(RateHit).where(RateHit.at < now - timedelta(hours=1)))
            db.commit()


auth_limiter = RateLimiter(int(os.environ.get("AUTH_RATE_MAX", "10")), 60)


def auth_limit(request: Request):
    auth_limiter(request)
