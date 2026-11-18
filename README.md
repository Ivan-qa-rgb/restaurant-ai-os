# Restaurant AI OS: часть 1 (ядро backend)

## Запуск (PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python -m pytest -q
    uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs

## Реализовано
Организации, регистрация/вход (scrypt, серверные сессии с хешем токена), роли
owner/manager/host/waiter, столы, брони (вместимость, пересечение интервалов,
часовой пояс, отмена, Idempotency-Key, защита от гонок), аудит без ПДн, тесты.

## Не реализовано (следующие части)
Alembic и PostgreSQL-режим, лимиты запросов, часы работы, меню/аллергены, заказы,
склад, аналитика, биллинг, Ollama-консьерж, RAG, реестр tools, frontend, бэкапы.

## Известные ограничения
- Защита от гонок проверена только на SQLite (процессный lock). Для нескольких
  процессов нужен PostgreSQL: SELECT FOR UPDATE уже в коде, плюс EXCLUDE-ограничение
  (btree_gist) добавим миграцией.
- Регистрация открыта и без rate limit. Нет сброса пароля и отзыва сессий.
- create_all вместо миграций. Не production-ready.
