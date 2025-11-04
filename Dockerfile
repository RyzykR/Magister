# =========================
# Base image and shared env
# =========================
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# API dependencies
FROM base AS api-deps
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    python-dotenv \
    motor \
    pymongo \
    celery \
    redis

# -------------------------
# Worker dependencies
# -------------------------
FROM base AS worker-deps
# Full heavy stack
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ================
# API runtime
# ================
FROM python:3.11-slim AS api
WORKDIR /app
COPY --from=api-deps /usr/local /usr/local
COPY --from=base /app /app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ================
# Worker runtime
# ================
FROM python:3.11-slim AS worker
WORKDIR /app
ENV TRANSFORMERS_CACHE=/cache/huggingface
RUN useradd --create-home appuser \
    && mkdir -p /cache/huggingface \
    && chown -R appuser:appuser /cache /app
COPY --from=worker-deps /usr/local /usr/local
COPY --from=base /app /app
USER appuser
CMD ["celery", "-A", "celery_app.celery_app", "worker", "--loglevel=info", "-Q", "ai_queue"]
