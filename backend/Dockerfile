FROM python:3.13-slim-bookworm AS builder

WORKDIR /build
RUN adduser --disabled-password --gecos "" --uid 65532 --home /nonexistent --shell /usr/sbin/nologin app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim-bookworm

# python:slim still has a package manager; drop it from the runtime? No —
# distroless cannot run uvicorn with CPython extensions (bcrypt) without a
# custom copy. slim + non-root + no extra pkgs is the honest baseline.
RUN adduser --disabled-password --gecos "" --uid 65532 --home /nonexistent --shell /usr/sbin/nologin app \
    && mkdir -p /data /app \
    && chown -R 65532:65532 /data /app

COPY --from=builder /install /usr/local
COPY --chown=65532:65532 backend/app /app/app
COPY --chown=65532:65532 backend/alembic.ini /app/alembic.ini
COPY --chown=65532:65532 backend/alembic /app/alembic
COPY --chown=65532:65532 backend/scripts /app/scripts

USER 65532:65532
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

# workers=1 still: sqlite write lock + in-process nothing on API after APP_ROLE=api.
# Scheduler lives in `python -m app.worker`.
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=2)"

# Bind 0.0.0.0 *inside* the compose network. Host publish is forbidden in compose.yaml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "10.200.20.0/24,10.200.30.0/24"]
