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
    SUPABASE_PUBLISHABLE_KEY=sb_publishable_opg3e3Knwg3aVkc2sfxIig_C2NDX4d1 \
    SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4ZWxtbHd0Z2dqZ2J2anBrbXJ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI4MjIyNDMsImV4cCI6MjEwODM5ODI0M30.QXdisTynzG5jWvU4XmQdNrZtZ7_4kz6b_bAMijFWv1s \
    SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4ZWxtbHd0Z2dqZ2J2anBrbXJ4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MjgyMjI0MywiZXhwIjoyMTA4Mzk4MjQzfQ.iHof7K3F2djonA-37Ei_T5kFeGxTJN0SaTx-ZXrt1OU \
    QORE_PUBLIC_URL=https://qore-bmh1.onrender.com

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "setuptools>=75"

COPY backend ./backend
COPY frontend/dist ./frontend/dist
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8080
CMD ["sh", "-c", "uvicorn qore.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
