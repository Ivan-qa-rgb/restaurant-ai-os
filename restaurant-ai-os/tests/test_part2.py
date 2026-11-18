from test_core import PW, bearer, book, c, login, org, table
from app.security import auth_limiter


def hdr(email):
    return login(email)


def test_logout_revokes_token():
    h = org()
    assert c.post("/auth/logout", headers=h).status_code == 200
    assert c.get("/tables", headers=h).status_code == 401


def test_logout_all():
    h = org()
    c.post("/staff", headers=h, json={"email": "la@x.ru", "password": PW, "role": "host"})
    a, b = login("la@x.ru"), login("la@x.ru")
    assert c.post("/auth/logout-all", headers=a).status_code == 200
    assert c.get("/tables", headers=b).status_code == 401
    assert c.get("/tables", headers=h).status_code == 200  # сессии другого пользователя целы


def test_deactivate_revokes_sessions():
    h = org()
    sid = c.post("/staff", headers=h, json={"email": "dz@x.ru", "password": PW,
                                             "role": "waiter"}).json()["id"]
    w = login("dz@x.ru")
    assert c.post(f"/staff/{sid}/deactivate", headers=h).status_code == 200
    assert c.get("/tables", headers=w).status_code == 401
    assert c.post("/auth/login", json={"email": "dz@x.ru", "password": PW}).status_code == 401


def test_deactivate_other_org_404():
    a, b = org(), org()
    sid = c.post("/staff", headers=a, json={"email": "xo@x.ru", "password": PW,
                                             "role": "waiter"}).json()["id"]
    assert c.post(f"/staff/{sid}/deactivate", headers=b).status_code == 404


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(auth_limiter, "max", 3)
    auth_limiter.reset()
    try:
        codes = [c.post("/auth/login", json={"email": "no@x.ru", "password": "bad"}).status_code
                 for _ in range(4)]
        assert codes == [401, 401, 401, 429]
    finally:
        auth_limiter.reset()


def test_working_hours():
    h = org(); t = table(h)
    assert book(h, t, "2030-03-01T08:00:00+03:00").status_code == 422   # до открытия
    assert book(h, t, "2030-03-01T22:00:00+03:00").status_code == 422   # закончится после 23:00
    assert book(h, t, "2030-03-01T21:30:00+03:00").status_code == 201   # ровно до закрытия
    assert book(h, t, "2030-03-02T16:00:00+00:00").status_code == 201   # 19:00 по Москве
    r = c.put("/settings/hours", headers=h, json={
        "tz_name": "Europe/Moscow", "open_time": "12:00:00", "close_time": "20:00:00"})
    assert r.status_code == 200
    assert book(h, t, "2030-03-03T19:00:00+03:00").status_code == 422   # 20:30 > 20:00
    assert c.put("/settings/hours", headers=h, json={
        "tz_name": "Mars/Base", "open_time": "10:00:00", "close_time": "20:00:00"}).status_code == 422
    assert c.put("/settings/hours", headers=h, json={
        "tz_name": "Europe/Moscow", "open_time": "20:00:00", "close_time": "20:00:00"}).status_code == 422


DISH = {"name": "Тестовое блюдо", "price_kop": 10000,
        "ingredients": ["мука", "молоко"], "allergens": ["gluten", "milk"]}


def test_menu_unverified_is_hidden_and_refused():
    h = org()
    d = c.post("/menu/dishes", headers=h, json=DISH).json()
    assert d["card_verified"] is False and "ingredients" not in d
    assert "allergens" not in c.get("/menu", headers=h).json()[0]
    r = c.get(f"/menu/dishes/{d['id']}/allergens", headers=h)
    assert r.status_code == 409 and "сотруднику" in r.json()["detail"]


def test_menu_verify_and_edit_resets():
    h = org()
    did = c.post("/menu/dishes", headers=h, json=DISH).json()["id"]
    assert c.post(f"/menu/dishes/{did}/verify", headers=h).json()["card_verified"] is True
    ok = c.get(f"/menu/dishes/{did}/allergens", headers=h)
    assert ok.status_code == 200 and ok.json()["allergens"] == ["gluten", "milk"]
    c.put(f"/menu/dishes/{did}", headers=h, json=dict(DISH, allergens=["gluten"]))
    assert c.get(f"/menu/dishes/{did}/allergens", headers=h).status_code == 409
    c.post(f"/menu/dishes/{did}/verify", headers=h)
    c.post(f"/menu/dishes/{did}/available", headers=h, json={"available": False})
    assert c.get(f"/menu/dishes/{did}/allergens", headers=h).status_code == 200


def test_menu_validation_roles_isolation():
    h = org(); other = org()
    assert c.post("/menu/dishes", headers=h, json=dict(DISH, allergens=["lava"])).status_code == 422
    empty = c.post("/menu/dishes", headers=h, json=dict(DISH, ingredients=[])).json()["id"]
    assert c.post(f"/menu/dishes/{empty}/verify", headers=h).status_code == 422
    did = c.post("/menu/dishes", headers=h, json=DISH).json()["id"]
    c.post("/staff", headers=h, json={"email": "mw@x.ru", "password": PW, "role": "waiter"})
    w = login("mw@x.ru")
    assert c.get("/menu", headers=w).status_code == 200
    assert c.post("/menu/dishes", headers=w, json=DISH).status_code == 403
    assert c.post(f"/menu/dishes/{did}/verify", headers=w).status_code == 403
    assert c.get(f"/menu/dishes/{did}/allergens", headers=other).status_code == 404
    assert c.get("/menu", headers=other).json() == []
