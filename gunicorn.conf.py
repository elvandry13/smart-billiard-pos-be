"""
Gunicorn configuration for Smart Billiard POS.
https://docs.gunicorn.org/en/stable/settings.html
"""
import os
import multiprocessing

# Bind
bind = "0.0.0.0:8000"

# Worker processes
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeout
timeout = 30
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "smart-billiard-pos"

# Server hooks
def on_starting(server):
    server.log.info("Starting Smart Billiard POS API")