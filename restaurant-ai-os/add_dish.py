# -*- coding: utf-8 -*-
import requests

TOKEN = "husMdoFtAnykvMIaYfWX7axfBZtSbbUokGbtAd7qn48"

url = "http://127.0.0.1:8000/menu/dishes"
headers = {"Authorization": f"Bearer {TOKEN}"}

dish = {
    "name": "Блины с Вологодским пломбиром",
    "price_kop": 0,
    "description": "Блины с вологодским пломбиром",
    "ingredients": ["блины", "вологодский пломбир"],
    "allergens": []
}

response = requests.post(url, json=dish, headers=headers)
print(response.status_code)
print(response.json())