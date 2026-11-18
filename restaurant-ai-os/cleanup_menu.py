# -*- coding: utf-8 -*-
import sqlite3

ids_to_delete = list(range(1, 17))
placeholders = ",".join("?" for _ in ids_to_delete)

connection = sqlite3.connect("dev.db")
cursor = connection.cursor()

cursor.execute(
    f"DELETE FROM dishes WHERE id IN ({placeholders})",
    ids_to_delete
)

deleted = cursor.rowcount
connection.commit()

cursor.execute("SELECT id, name, price_kop FROM dishes ORDER BY id")
rows = cursor.fetchall()

print("Удалено записей:", deleted)
print("Осталось блюд:", len(rows))

for row in rows:
    print(row[0], row[1], row[2])

connection.close()