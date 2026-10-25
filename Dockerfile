# Build the React workbench separately to keep the runtime image focused.
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
RUN npm install -g pnpm@9.15.4
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm run build

# Full QORE runtime. Build from the repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    QORE_ENV=production \
    QORE_REQUIRE_AUTH=true \
    QORE_STORAGE=supabase \
    SUPABASE_URL=https://yxelmlwtggjgbvjpkmrx.supabase.co \
    SUPABASE_PUBLISHABLE_KEY=sb_publishable_opg3e3Knwg3aVkc2sfxIig_C2NDX4d1 \
    SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4ZWxtbHd0Z2dqZ2J2anBrbXJ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI4MjIyNDMsImV4cCI6MjEwODM5ODI0M30.QXdisTynzG5jWvU4XmQdNrZtZ7_4kz6b_bAMijFWv1s \
    QORE_PUBLIC_URL=https://qore-bmh1.onrender.com

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir -e .
RUN groupadd --system qore && useradd --system --gid qore --home-dir /app qore \
    && mkdir -p /app/data && chown qore:qore /app/data

USER qore

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn qore.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
