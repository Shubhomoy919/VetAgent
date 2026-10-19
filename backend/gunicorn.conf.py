"""Gunicorn settings for the container (Linux only; on Windows use `npm run dev` or uvicorn directly).

One worker, deliberately: the run manager, its SSE event log, the rate limiter and the access-code lockout all
live in process memory, and SQLite has one writer. One async worker handles the expected load (a research
site) comfortably; scale up by moving that state to Redis/Postgres first (docs/DEPLOY.md).
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1
worker_class = "uvicorn_worker.UvicornWorker"

# Graceful shutdown: on SIGTERM, stop accepting, let requests finish, run the app's shutdown (which cancels an
# active run and records its status), then exit. Keep below the platform's kill timeout (Fly/Render: 30 s+).
graceful_timeout = int(os.environ.get("GRACEFUL_TIMEOUT", "25"))
timeout = 120  # worker heartbeat; long SSE streams are fine with uvicorn workers
keepalive = 5

# Trust X-Forwarded-For / -Proto only from the platform's proxy. "*" is right behind Render/Railway/Fly,
# where the container is reachable only through their load balancer.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "*")

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
# Method, path and status only: no query strings, headers or bodies in the access log.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(B)s %(M)sms'
