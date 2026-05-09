# ─── Build stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install "poetry==${POETRY_VERSION}" poetry-plugin-export

WORKDIR /build
COPY pyproject.toml poetry.lock* ./

RUN poetry export --without-hashes --only main --output requirements.txt \
    && pip install --prefix=/install --no-warn-script-location -r requirements.txt

# ─── Runtime stage ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY --from=builder /install /usr/local

WORKDIR /app
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

EXPOSE 8002
CMD ["uvicorn", "post_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
