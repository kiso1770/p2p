# syntax=docker/dockerfile:1.7

# ─── Stage 1: builder ─────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install "poetry==${POETRY_VERSION}" "poetry-plugin-export"

COPY pyproject.toml poetry.lock ./

RUN poetry export --without-hashes --without dev -f requirements.txt -o requirements.txt

# ─── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY --from=builder /app/requirements.txt ./requirements.txt

RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
