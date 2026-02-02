"""
Gunicorn configuration for production deployment.
"""
import os
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"  # або "gevent" для async (потребує gevent у залежностях)
worker_connections = 1000
timeout = 120  # 2 хвилини для довгих запитів (парсинг може бути повільним)
keepalive = 5

# Worker restart
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "autoria-data-parser"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Forwarded headers (за nginx/reverse proxy)
forwarded_allow_ips = "*"
proxy_protocol = False
proxy_allow_ips = "*"
