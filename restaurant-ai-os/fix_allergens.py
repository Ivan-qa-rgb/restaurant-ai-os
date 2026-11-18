# -*- coding: utf-8 -*-
import sqlite3

updates = {
    17: "gluten,milk,eggs",
    18: "gluten,milk,eggs",
    19: "gluten,milk,eggs",
    20: "gluten,milk,eggs",
    22: "gluten,milk,eggs",
    40: "milk",
    42: "fish,nuts,sesame",
    57: "milk,gluten"
}

connection = sqlite3.connect("dev.db")
cursor = connection.cursor()

for dish_id, allergens in updates.items():
    cursor.execute(
        "UPDATE dishes SET allergens = ? WHERE id = ?",
        (allergens, dish_id)
    )
    print("Обновлено:", dish_id, allergens)

connection.commit()

cursor.execute("SELECT id, name, allergens FROM dishes ORDER BY id")
rows = cursor.fetchall()

print("\nПроверка:")
for row in rows:
    print(row[0], row[1], row[2])

connection.close()