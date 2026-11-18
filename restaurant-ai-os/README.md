# Restaurant AI OS (части 1-2)

## Запуск тестов (SQLite, PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python -m pytest -q

## Запуск с PostgreSQL (Docker)
    Copy-Item .env.example .env      # затем замените POSTGRES_PASSWORD
    docker compose up --build        # api: http://127.0.0.1:8000/docs

## Тест защиты от гонок в PostgreSQL (нужны миграции)
    docker compose up -d db
    $env:DATABASE_URL = "postgresql+psycopg://postgres:<пароль>@127.0.0.1:5432/restaurant"
    alembic upgrade head
    $env:TEST_PG_URL = $env:DATABASE_URL
    python -m pytest tests/test_pg_overlap.py -q

## Статус
Код написан, ни один тест не запускался. Реализовано: организации, роли, столы, брони
(вместимость, интервалы, часы работы, идемпотентность, отмена), выход и отзыв сессий,
лимит попыток входа (в памяти процесса), меню с подтверждёнными карточками, Alembic,
exclusion constraint в PostgreSQL.

## Ограничения
- Миграция 0001 - снимок моделей через create_all; новые изменения только явными миграциями.
- Нет шаблона script.py.mako: `alembic revision` не сработает до его добавления.
- Лимитер в памяти процесса, не подходит для нескольких процессов и прокси.
- Часы работы: один интервал в день, без перехода через полночь.
- Подтверждение карточки блюда одним сотрудником (без правила «четырёх глаз»).
- Не реализованы: заказы, склад, аналитика, тарифы, Ollama, RAG, tools, frontend, бэкапы.

## Часть 3a (добавлено)
Явная миграция 0001 (id прежний: базы после старой 0001 не затрагиваются, чистая база не нужна),
script.py.mako, общий лимитер в таблице rate_hits + TRUSTED_PROXIES, часы работы через полночь,
заказы (снимок цены, CAS-переходы статусов, идемпотентность), очередь кухни, роль cook.
Миграции: 0003 (rate_hits), 0004 (orders). Для существующей PostgreSQL: `alembic upgrade head`.
Статусы заказа: open -> sent -> preparing -> ready -> served; отмена только из open/sent.
`items_total_kop` - сумма позиций, не выручка (оплат нет).
Не реализовано: склад, техкарты, аналитика, тарифы, Ollama, RAG, tools, frontend, бэкапы.
Риски: лимитер в SQLite может чуть превысить порог при гонке; отмена после начала
приготовления запрещена до появления обратных движений склада.
