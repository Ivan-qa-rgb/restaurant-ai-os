# -*- coding: utf-8 -*-
import requests

TOKEN = "husMdoFtAnykvMIaYfWX7axfBZtSbbUokGbtAd7qn48"
URL = "http://127.0.0.1:8000/menu"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(URL, headers=HEADERS)
print(response.status_code)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(response.text)