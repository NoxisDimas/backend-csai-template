# ===================================================================
# Dockerfile khusus untuk Background Worker (ARQ)
# ===================================================================

FROM python:3.13-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by asyncpg and psycopg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Dependencies stage
# ---------------------------------------------------------------------------
FROM base AS dependencies

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Production stage
# ---------------------------------------------------------------------------
FROM dependencies AS production

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

# Run the ARQ Worker instead of Uvicorn API
CMD ["arq", "app.worker.WorkerSettings"]
