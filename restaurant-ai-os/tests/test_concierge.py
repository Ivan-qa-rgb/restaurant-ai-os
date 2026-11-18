from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_concierge_intake_requires_authorization():
    response = client.post(
        "/concierge/intake",
        json={"message": "Хочу стол на 4 человек завтра в 19:00"},
    )
    assert response.status_code == 401

def test_authenticated_concierge_collects_details_without_booking():
    registration = client.post(
        "/auth/register",
        json={
            "org_name": "Concierge test",
            "email": "concierge.integration@example.com",
            "password": "correct-horse-1",
        },
    )
    assert registration.status_code == 201
    headers = {"Authorization": f"Bearer {registration.json()['token']}"}

    response = client.post(
        "/concierge/intake",
        headers=headers,
        json={"message": "Стол на 4 человека 2030-01-01 в 19:00"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["state"]["party_size"] == 4
    assert result["state"]["date"] == "2030-01-01"
    assert result["state"]["time"] == "19:00"
    assert result["reservation_created"] is False
    assert client.get("/reservations", headers=headers).json() == []
