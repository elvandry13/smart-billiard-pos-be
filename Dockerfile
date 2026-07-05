# ===================================================
# Stage 1: Builder — install dependencies
# ===================================================
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies to /install prefix
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# ===================================================
# Stage 2: Development image (hot-reload via volume mount)
# ===================================================
FROM python:3.10-slim-bookworm AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings.development \
    DJANGO_ENV=development

WORKDIR /app

# Install runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source code (mounted as volume in docker-compose for hot-reload)
COPY . .

# Entrypoint
COPY scripts/entrypoint-dev.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]


# ===================================================
# Stage 3: Production image (minimal, optimized)
# ===================================================
FROM python:3.10-slim-bookworm AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings.production \
    DJANGO_ENV=production

WORKDIR /app

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Install runtime libs only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=django:django . .

# Copy entrypoint
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Collect static files during build
RUN python manage.py collectstatic --noinput

# Create log directory
RUN mkdir -p /app/logs && chown -R django:django /app/logs

USER django

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]