# -*- coding: utf-8 -*-
import requests

TOKEN = "husMdoFtAnykvMIaYfWX7axfBZtSbbUokGbtAd7qn48"
URL = "http://127.0.0.1:8000/menu/dishes"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

dish = {
    "name": "Тест аллергенов",
    "price_kop": 0,
    "description": "Проверка допустимых аллергенов",
    "ingredients": ["тест"],
    "allergens": ["eggs", "milk", "gluten", "fish", "nuts"]
}

response = requests.post(URL, json=dish, headers=HEADERS)
print(response.status_code)
print(response.json())