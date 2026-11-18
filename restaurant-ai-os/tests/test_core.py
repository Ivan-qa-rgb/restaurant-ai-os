import itertools
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
_n = itertools.count()
PW = "correct-horse-1"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def org():
    i = next(_n)
    r = c.post("/auth/register", json={"org_name": f"O{i}", "email": f"o{i}@x.ru", "password": PW})
    return bearer(r.json()["token"])


def table(h, cap=4):
    return c.post("/tables", json={"name": "T", "capacity": cap}, headers=h).json()["id"]


def book(h, tid, start="2030-01-01T19:00:00+03:00", n=2, key=None, dur=90):
    hd = dict(h, **({"Idempotency-Key": key} if key else {}))
    return c.post("/reservations", headers=hd, json={
        "table_id": tid, "guest_name": "Гость", "party_size": n,
        "start": start, "duration_min": dur})


def login(email):
    return bearer(c.post("/auth/login", json={"email": email, "password": PW}).json()["token"])


def test_requires_auth():
    assert c.get("/tables").status_code == 401


def test_capacity():
    h = org(); t = table(h, 2)
    assert book(h, t, n=3).status_code == 422
    assert book(h, t, n=2).status_code == 201


def test_overlap_and_adjacent():
    h = org(); t = table(h)
    assert book(h, t, "2030-01-01T19:00:00+03:00").status_code == 201
    assert book(h, t, "2030-01-01T20:00:00+03:00").status_code == 409
    assert book(h, t, "2030-01-01T20:30:00+03:00").status_code == 201


def test_timezone_required():
    h = org(); t = table(h)
    assert book(h, t, "2030-01-01T19:00:00").status_code == 422


def test_cancel_frees_slot():
    h = org(); t = table(h)
    rid = book(h, t).json()["id"]
    assert c.post(f"/reservations/{rid}/cancel", headers=h).status_code == 200
    assert book(h, t).status_code == 201


def test_idempotency():
    h = org(); t = table(h)
    a = book(h, t, key="k1"); b = book(h, t, key="k1")
    assert a.status_code == b.status_code == 201 and a.json()["id"] == b.json()["id"]
    assert book(h, t, "2030-02-01T19:00:00+03:00", key="k1").status_code == 422


def test_tenant_isolation():
    a, b = org(), org()
    ta = table(a); rid = book(a, ta).json()["id"]
    assert book(b, ta).status_code == 404
    assert c.post(f"/reservations/{rid}/cancel", headers=b).status_code == 404
    assert c.get("/reservations", headers=b).json() == []
    assert c.get("/tables", headers=b).json() == []


def test_roles():
    h = org()
    for email, role in (("w@x.ru", "waiter"), ("m@x.ru", "manager")):
        r = c.post("/staff", headers=h, json={"email": email, "password": PW, "role": role})
        assert r.status_code == 201
    w, m = login("w@x.ru"), login("m@x.ru")
    assert c.post("/tables", json={"name": "T", "capacity": 2}, headers=w).status_code == 403
    assert c.post("/staff", headers=w, json={"email": "z@x.ru", "password": PW,
                                              "role": "waiter"}).status_code == 403
    assert c.post("/staff", headers=m, json={"email": "o2@x.ru", "password": PW,
                                              "role": "owner"}).status_code == 403


def test_bad_login():
    org()
    assert c.post("/auth/login", json={"email": "o0@x.ru", "password": "wrong"}).status_code == 401


def test_concurrent_same_slot():
    h = org(); t = table(h)
    with ThreadPoolExecutor(8) as ex:
        codes = list(ex.map(lambda _: book(h, t, "2031-01-01T19:00:00+03:00").status_code,
                            range(8)))
    assert codes.count(201) == 1 and codes.count(409) == 7
def test_past_reservation_rejected():
    h = org()
    t = table(h)
    response = book(h, t, "2000-01-01T19:00:00+03:00")
    assert response.status_code == 422
