# -*- coding: utf-8 -*-
import requests

TOKEN = "husMdoFtAnykvMIaYfWX7axfBZtSbbUokGbtAd7qn48"
BASE_URL = "http://127.0.0.1:8000"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

menu_response = requests.get(f"{BASE_URL}/menu", headers=HEADERS)

if menu_response.status_code != 200:
    print("Не удалось получить меню:", menu_response.status_code)
    print(menu_response.text)
else:
    dishes = menu_response.json()

    for dish in dishes:
        dish_id = dish["id"]
        name = dish["name"]

        response = requests.post(
            f"{BASE_URL}/menu/dishes/{dish_id}/verify",
            headers=HEADERS
        )

        print(response.status_code, name)

print("Готово")