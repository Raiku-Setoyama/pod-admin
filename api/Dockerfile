# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Development stage
FROM base AS development

# Install Weasyprint dependencies and Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project --dev

# Copy application code
COPY . .

# Install project
RUN uv sync --frozen --dev

# Expose port
EXPOSE 8000

# Run with uvicorn (development mode with reload)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base AS production

# Install Weasyprint dependencies and Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (production only)
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Install project
RUN uv sync --frozen --no-dev

# Run with uvicorn (production mode)
# マイグレーションはここで実行しない。複数インスタンスが同時に起動すると alembic が競合し、
# 起動そのものを壊す。デプロイ前の独立したステップ（Cloud Run Job）で
# `uv run alembic upgrade head` を実行する。
# 製造データ生成ワーカーは同じイメージのまま `uv run python -m app.worker` で起動する。
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]