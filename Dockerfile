# VetAgentBench-IN: one container serves the API and the built frontend.
#   docker build -t vetagentbench:1.0.0 .
#   docker compose up            (see docker-compose.yml and docs/DEPLOY.md)

# ---------- 1. frontend build ----------
FROM node:24-bookworm-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. python dependencies ----------
FROM python:3.12-slim-bookworm AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt

# ---------- 3. runtime ----------
FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="VetAgentBench-IN" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.description="Research prototype, not for clinical use." \
      org.opencontainers.image.licenses="MIT"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATA_DIR=/data \
    FRONTEND_DIST=/app/frontend/dist \
    PORT=8000

# Unprivileged user; owns only the data volume.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /data && chown app:app /data

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY backend/app /app/backend/app
COPY backend/gunicorn.conf.py /app/backend/gunicorn.conf.py
COPY snapshots /app/snapshots
# Seed data copied into /data on first start (the SVTG PDF is not baked in; see docs/DEPLOY.md).
COPY data/cases.json data/drug_table.csv data/knowledge_seed.json /app/seed-data/
COPY --from=web /src/frontend/dist /app/frontend/dist
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod 0755 /app/entrypoint.sh && python -m compileall -q /app/backend/app

USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request,json,sys; r=urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=4); sys.exit(0 if json.load(r)['database']['ok'] else 1)"

# Gunicorn forwards SIGTERM to the worker, which cancels any active run and records its status.
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--config", "/app/backend/gunicorn.conf.py", "--chdir", "/app/backend", "app.main:app"]
