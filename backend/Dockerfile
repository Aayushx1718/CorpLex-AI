FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_CACHE_DIR=/tmp/uv-cache
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
ARG INCLUDE_ML=false
RUN --mount=type=secret,id=build_ca if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; if [ "$INCLUDE_ML" = "true" ]; then uv sync --frozen --no-dev --group ml; else uv sync --frozen --no-dev; fi
COPY --chown=10001:10001 backend/app ./app
COPY --chown=10001:10001 db /app/db
COPY --chown=10001:10001 docs/ml/experiment-results.json /app/docs/ml/experiment-results.json
RUN groupadd --gid 10001 corplex && useradd --uid 10001 --gid 10001 --no-create-home corplex
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 CMD ["/app/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["/bin/sh", "-c", ".venv/bin/python -m app.migrate && exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-server-header"]
