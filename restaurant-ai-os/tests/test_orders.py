import itertools
from concurrent.futures import ThreadPoolExecutor

from test_core import PW, c, login, org, table

_u = itertools.count()
DISH = {
    "name": "Тест",
    "price_kop": 15000,
    "ingredients": ["мука"],
    "allergens": ["gluten"],
}

def dish(h, **kw):
    response = c.post(
        "/menu/dishes",
        headers=h,
        json=dict(DISH, **kw),
    )
    assert response.is_success, (
        f"Создание блюда не удалось: "
        f"status={response.status_code}, body={response.text[:500]}"
    )
    data = response.json()
    assert "id" in data, f"В ответе API нет id блюда: {data}"
    return data["id"]

def staff(h, role):
    email = f"s{next(_u)}@o.ru"
    response = c.post(
        "/staff",
        headers=h,
        json={"email": email, "password": PW, "role": role},
    )
    assert response.status_code == 201, (
        f"Создание сотрудника не удалось: "
        f"status={response.status_code}, body={response.text[:500]}"
    )
    return login(email)

def new_order(h, key=None, **body):
    headers = dict(h)
    if key:
        headers["Idempotency-Key"] = key
    return c.post("/orders", headers=headers, json=body)

def add(h, oid, did, qty=1, key=None):
    headers = dict(h)
    if key:
        headers["Idempotency-Key"] = key
    return c.post(
        f"/orders/{oid}/items",
        headers=headers,
        json={"dish_id": did, "qty": qty},
    )

def status(h, oid, st):
    return c.post(
        f"/orders/{oid}/status",
        headers=h,
        json={"status": st},
    )

def ready_order(h, menu_h=None):
    """Создать заказ от h; блюдо создать от menu_h (или от h, если не задан)."""
    order_response = new_order(h)
    assert order_response.is_success, (
        f"Создание заказа не удалось: "
        f"status={order_response.status_code}, body={order_response.text[:500]}"
    )
    oid = order_response.json()["id"]

    did = dish(menu_h or h)
    item_response = add(h, oid, did)
    assert item_response.status_code == 201, (
        f"Добавление блюда в заказ не удалось: "
        f"status={item_response.status_code}, body={item_response.text[:500]}"
    )
    return oid

def test_price_snapshot():
    h = org()
    did = dish(h)
    oid = new_order(h).json()["id"]

    assert add(h, oid, did, 2).status_code == 201

    c.put(
        f"/menu/dishes/{did}",
        headers=h,
        json=dict(DISH, price_kop=99999, name="Другое"),
    )
    order = c.get(f"/orders/{oid}", headers=h).json()

    assert order["items"][0]["unit_price_kop"] == 15000
    assert order["items"][0]["dish_name"] == "Тест"
    assert order["items_total_kop"] == 30000

def test_unavailable_foreign_and_invalid_qty():
    h, other = org(), org()
    did = dish(h)
    oid = new_order(h).json()["id"]

    c.post(
        f"/menu/dishes/{did}/available",
        headers=h,
        json={"available": False},
    )
    assert add(h, oid, did).status_code == 409
    assert add(other, new_order(other).json()["id"], did).status_code == 404

    c.post(
        f"/menu/dishes/{did}/available",
        headers=h,
        json={"available": True},
    )
    assert add(h, oid, did, qty=0).status_code == 422
    assert add(h, oid, did, qty=51).status_code == 422

def test_items_only_while_open():
    h = org()
    oid = ready_order(h)

    assert status(h, oid, "sent").status_code == 200
    assert add(h, oid, dish(h)).status_code == 409

def test_transitions_and_roles():
    h = org()
    waiter = staff(h, "waiter")
    cook = staff(h, "cook")

    # Меню редактирует владелец; заказ создаёт официант.
    oid = ready_order(waiter, menu_h=h)

    assert status(waiter, oid, "ready").status_code == 409
    assert status(waiter, oid, "sent").status_code == 200
    assert status(waiter, oid, "preparing").status_code == 403
    assert status(cook, oid, "preparing").status_code == 200
    assert status(cook, oid, "ready").status_code == 200
    assert status(cook, oid, "served").status_code == 403
    assert status(waiter, oid, "served").status_code == 200
    assert status(waiter, oid, "cancelled").status_code == 409

    assert new_order(cook).status_code == 403
    assert c.get("/kitchen/queue", headers=cook).status_code == 200
    assert c.get("/kitchen/queue", headers=waiter).status_code == 403

def test_queue_and_tenant_isolation():
    tenant_a, tenant_b = org(), org()
    oid = ready_order(tenant_a)
    status(tenant_a, oid, "sent")

    queue_a = c.get("/kitchen/queue", headers=tenant_a).json()
    assert [order["id"] for order in queue_a] == [oid]
    assert c.get("/kitchen/queue", headers=tenant_b).json() == []

    assert c.get(f"/orders/{oid}", headers=tenant_b).status_code == 404
    assert status(tenant_b, oid, "preparing").status_code == 404
    assert add(tenant_b, oid, dish(tenant_b)).status_code == 404
    assert new_order(
        tenant_b,
        table_id=table(tenant_a),
    ).status_code == 404

def test_create_idempotent():
    h = org()
    table_id = table(h)

    first = new_order(h, "k1", table_id=table_id)
    second = new_order(h, "k1", table_id=table_id)

    assert first.json()["id"] == second.json()["id"]
    assert new_order(h, "k1").status_code == 422

def test_item_idempotency_and_concurrency():
    h = org()
    did = dish(h)
    oid = new_order(h).json()["id"]

    with ThreadPoolExecutor(8) as executor:
        codes = list(
            executor.map(
                lambda _: add(h, oid, did, 1, "same").status_code,
                range(8),
            )
        )

    assert set(codes) == {201}
    assert len(c.get(f"/orders/{oid}", headers=h).json()["items"]) == 1

    with ThreadPoolExecutor(8) as executor:
        list(
            executor.map(
                lambda i: add(h, oid, did, 1, f"k{i}"),
                range(8),
            )
        )

    assert len(c.get(f"/orders/{oid}", headers=h).json()["items"]) == 9

def test_concurrent_conflicting_transitions():
    h = org()
    oid = ready_order(h)
    status(h, oid, "sent")

    targets = ["preparing", "cancelled"] * 4
    with ThreadPoolExecutor(8) as executor:
        results = list(
            executor.map(
                lambda target: (target, status(h, oid, target).status_code),
                targets,
            )
        )

    winners = {
        target
        for target, code in results
        if code == 200
    }

    assert len(winners) == 1
    assert c.get(f"/orders/{oid}", headers=h).json()["status"] == winners.pop()
