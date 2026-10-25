# QORE Production Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app/backend \
    QORE_ENV=production \
    QORE_REQUIRE_AUTH=true \
    QORE_STORAGE=supabase \
    SUPABASE_URL=https://yxelmlwtggjgbvjpkmrx.supabase.co \
    QORE_PUBLIC_URL=https://qore-bmh1.onrender.com

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "setuptools>=75"

COPY backend ./backend
COPY frontend/dist ./frontend/dist
RUN pip install --no-cache-dir --no-deps -e .
RUN groupadd --system qore && useradd --system --gid qore --home-dir /app qore \
    && mkdir -p /app/data && chown qore:qore /app/data

USER qore

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn qore.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
