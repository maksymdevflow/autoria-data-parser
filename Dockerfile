# Playwright image: Python + Chromium, щоб не тягнути системні залежності вручну
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Залежності з pyproject (кеш шару) + pg_dump для щоденного дампу БД
COPY pyproject.toml poetry.lock* ./
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-root

# Код проєкту (COPY . . надійно на Windows замість списку папок)
COPY . .
RUN test -d /app/alembic && test -d /app/tasks && test -d /app/web || (echo "Missing dirs in /app" && exit 1)

RUN poetry install --without dev --no-interaction 2>/dev/null || true

EXPOSE 5000
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]
