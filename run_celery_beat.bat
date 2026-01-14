@echo off
echo Starting Celery Beat (Scheduler)...
cd /d %~dp0
poetry run celery -A tasks.config beat --loglevel=info

