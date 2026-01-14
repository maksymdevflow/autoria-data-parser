@echo off
echo Starting Celery Worker (Windows - using solo pool)...
echo Queues: scraping (додавання), unpublished (обробка), deletion (видалення)
cd /d %~dp0
poetry run celery -A tasks.config worker --loglevel=info --queues=scraping,unpublished,deletion --pool=solo

