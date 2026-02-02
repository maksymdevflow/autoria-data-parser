# autoria-data-parser
AutoRia Scraper Demo a parser that collects all car listings from autoria by a given link. Each vehicle’s data is stored in the database with reference to its owner. The information is structured for further use, analysis, or integration with other systems.

## Локальний запуск (Redis + Celery)

**Redis** (потрібен для Celery broker/backend):

```bash
# Варіант 1: тільки Redis через Docker
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Варіант 2: Redis з docker-compose (з кореня проєкту)
docker-compose up -d redis
```

Перевірка: `redis-cli ping` → `PONG`.

Якщо змінна середовища `CELERY_RESULT_BACKEND` задана без схеми (наприклад `redis/1`), воркер може падати з помилкою `module 'redis' has no attribute '/1'`. Або не задавай `CELERY_RESULT_BACKEND`, або вкажи повний URL: `redis://localhost:6379/1`.

**Playwright** (потрібен для парсингу — збір посилань і сторінок авто):

```bash
playwright install chromium
```

Без цього таск `process_link_car_urls` може зависати або падати при запуску браузера.

**Опційно:** `SQLALCHEMY_ECHO=true` у `.env` — виводити всі SQL-запити в консоль (для відлагодження).

### Розклад Celery Beat (Europe/Kiev)

| Таск | Розклад |
|------|--------|
| Перевірка to_create / to_delete | Понеділок 00:00, 01:00, 02:00 |
| Парсинг авто по URL (links_to_create) | Вт–Нд 03:00, 04:00, 05:00, 06:00 |
| Додавання на TruckMarket | Кожну годину (:00) |
| Видалення з TruckMarket (links_to_delete) | Кожну годину (:00) |
| Дамп БД (pg_dump) | Щодня о 09:00 (Київ) |

Час у Celery Beat — **Europe/Kiev** (`enable_utc = False`). Дампи зберігаються у volume `backup_data` (в контейнері `/app/backups`), файли: `autoria_dump_YYYY-MM-DD.sql`.

### Docker: БД і .env

У Docker **DATABASE_DEVELOPMENT_URI** для web/celery збирається з **POSTGRES_USER**, **POSTGRES_PASSWORD**, **POSTGRES_DB** у `docker-compose.yml`, тому достатньо задати в `.env`:

- **POSTGRES_USER** (за замовчуванням `postgres`)
- **POSTGRES_PASSWORD** — той самий, з яким вперше ініціалізувався Postgres у volume
- **POSTGRES_DB** (за замовчуванням `truck_partner_db`)

Якщо з’являється **"password authentication failed"** — volume БД створено з іншими credentials. Або вкажи в `.env` той самий **POSTGRES_PASSWORD**, з яким запускав перший раз, або перествори volume (дані втрачаться):

```bash
docker-compose down -v
docker-compose up --build
```

## Безпека: Конфігурація через .env

**Усі чутливі дані зберігаються у `.env` файлі** (він у `.gitignore` і не комітиться).

**Перший запуск:**
1. Скопіюй: `cp .env.example .env`
2. Відредагуй `.env` - заповни реальні паролі та ключі
3. Запусти: `docker-compose up --build -d`

Docker Compose автоматично завантажує змінні через `env_file: .env` для всіх сервісів.

### Docker: міграції БД

Після першого запуску або якщо таблиці відсутні, застосуй міграції:

```bash
docker-compose exec web alembic upgrade head
```

Якщо web ще не піднятий: `docker-compose up -d` і знову виконай команду вище.

### Production WSGI Server (Gunicorn)

Застосунок використовує **Gunicorn** як production WSGI server замість Flask development server для:
- Кращої продуктивності
- Підтримки множинних workers
- Стабільності під навантаженням

**Конфігурація** (у `.env`):
- `GUNICORN_WORKERS` - кількість worker процесів (за замовчуванням: 4)
- `GUNICORN_LOG_LEVEL` - рівень логування (за замовчуванням: info)

Детальна конфігурація: `gunicorn.conf.py`

### Деплой за nginx (HTTPS)

Flask підтримує проксі: використовується `ProxyFix` (X-Forwarded-Proto, X-Forwarded-For, Host), щоб посилання були `https://` за nginx.

- У docker-compose сервіс `web` відкриває порт **5000**.
- У nginx вкажи `proxy_pass http://127.0.0.1:5000;`
- Приклад конфігурації: `deploy/nginx-fincar.conf.example`.
