import itertools

from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
_n = itertools.count()
PW = "correct-horse-1"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def org():
    i = next(_n)
    r = c.post(
        "/auth/register",
        json={
            "org_name": f"O{i}",
            "email": f"knowledge{i}@x.ru",
            "password": PW,
        },
    )

    if r.status_code != 201:
        raise AssertionError(
            f"??????????? ?? ???????: {r.status_code} {r.text}"
        )

    return bearer(r.json()["token"])


def test_knowledge_requires_authorization():
    response = c.post(
        "/knowledge/search",
        json={"question": "??? ???????? ?????????"},
    )
    assert response.status_code == 401


def test_knowledge_documents_require_authorization():
    response = c.get("/knowledge/documents")
    assert response.status_code == 401


def test_knowledge_owner_can_list_documents():
    h = org()

    response = c.get("/knowledge/documents", headers=h)

    assert response.status_code == 200
    assert response.json() == []


def test_knowledge_search_returns_stub():
    h = org()

    response = c.post(
        "/knowledge/search",
        headers=h,
        json={"question": "??? ???????? ?????????"},
    )

    assert response.status_code == 200

    result = response.json()
    assert result["answer"] in {
        "???? ?????? ???? ?? ??????????.",
        "???? ?????? ???????? ??????????.",
        "? ???? ?????? ???? ??? ??????????.",
    }
    assert result["sources"] == []
