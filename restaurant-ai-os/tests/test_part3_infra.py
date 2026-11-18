from datetime import datetime, time
from types import SimpleNamespace
from test_core import c, book, org, table
from app.hours import within_hours
from app.security import auth_limiter, client_ip

D = datetime


def req(peer, xff=None):
    return SimpleNamespace(client=SimpleNamespace(host=peer),
                           headers={"x-forwarded-for": xff} if xff else {})


def test_client_ip_ignores_xff_without_trusted_proxy(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    assert client_ip(req("1.2.3.4", "9.9.9.9")) == "1.2.3.4"


def test_client_ip_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")
    assert client_ip(req("10.0.0.5", "8.8.8.8")) == "8.8.8.8"
    assert client_ip(req("10.0.0.5", "6.6.6.6, 8.8.8.8, 10.0.0.9")) == "8.8.8.8"  # подделка слева
    assert client_ip(req("5.5.5.5", "8.8.8.8")) == "5.5.5.5"  # прокси не доверенный
    assert client_ip(req("10.0.0.5", "не-ip")) == "10.0.0.5"


def test_rate_limit_is_shared_across_limiter_instances(monkeypatch):
    from app.security import RateLimiter
    a, b = RateLimiter(2, 60, "t"), RateLimiter(2, 60, "t")  # как два процесса
    a.reset()
    a(req("7.7.7.7")); b(req("7.7.7.7"))
    try:
        a(req("7.7.7.7"))
        assert False
    except Exception as e:
        assert getattr(e, "status_code", None) == 429
    a.reset()


def test_within_hours_same_day_and_overnight():
    o, cl = time(10, 0), time(23, 0)
    assert within_hours(D(2030, 1, 1, 21, 30), D(2030, 1, 1, 23, 0), o, cl)
    assert not within_hours(D(2030, 1, 1, 22, 0), D(2030, 1, 1, 23, 30), o, cl)
    o, cl = time(18, 0), time(2, 0)
    assert within_hours(D(2030, 1, 1, 23, 30), D(2030, 1, 2, 1, 0), o, cl)
    assert within_hours(D(2030, 1, 2, 0, 30), D(2030, 1, 2, 1, 30), o, cl)
    assert not within_hours(D(2030, 1, 2, 1, 0), D(2030, 1, 2, 2, 30), o, cl)
    assert not within_hours(D(2030, 1, 2, 10, 0), D(2030, 1, 2, 11, 0), o, cl)
    assert not within_hours(D(2030, 1, 1, 17, 0), D(2030, 1, 1, 18, 30), o, cl)


def test_overnight_reservation_api():
    h = org(); t = table(h)
    r = c.put("/settings/hours", headers=h, json={
        "tz_name": "Europe/Moscow", "open_time": "18:00:00", "close_time": "02:00:00"})
    assert r.status_code == 200
    assert book(h, t, "2030-04-01T23:30:00+03:00").status_code == 201   # до 01:00
    assert book(h, t, "2030-04-02T01:00:00+03:00", dur=60).status_code == 201
    assert book(h, t, "2030-04-03T01:00:00+03:00", dur=90).status_code == 422  # до 02:30
    assert book(h, t, "2030-04-03T10:00:00+03:00").status_code == 422
