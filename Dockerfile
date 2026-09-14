# syntax=docker/dockerfile:1
#
# Multi-stage build with two explicit targets:
#   * `api`       — runs the FastAPI service via entrypoint.sh
#   * `migration` — applies pending schema migrations and exits
#
# Build a specific target with:
#   docker build --target api -t libraflow:latest .
#   docker build --target migration -t libraflow:migrate .

FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIBRAFLOW_STORAGE=postgres

# Runtime dependencies only — the dev extras (pytest, locust, coverage)
# are not installed in images.
COPY requirements.txt .
RUN pip install --no-cache-dir \
    $(grep -vE "^(#|pytest|pytest-cov|locust|httpx|coverage)" requirements.txt)

COPY libflow/ libflow/
COPY alembic/ alembic/
COPY alembic.ini .
COPY models/ models/
COPY scripts/ scripts/

# ---------------------------------------------------------------------------- 
FROM base AS migration

COPY docker/entrypoint_migrate.sh /entrypoint_migrate.sh
RUN chmod +x /entrypoint_migrate.sh

CMD ["/entrypoint_migrate.sh"]

# ----------------------------------------------------------------------------
FROM base AS api

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

CMD ["/entrypoint.sh"]

# ----------------------------------------------------------------------------
# Test target: installs test tooling and runs the suite. Used by CI and
# docker-compose.test.yml.
FROM base AS test

COPY tests/ tests/
RUN pip install --no-cache-dir pytest pytest-cov coverage

CMD ["python", "-m", "pytest", "tests/", "-q"]