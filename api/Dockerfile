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

# 製造データ生成に使う VectorCraft（OSS、MIT / Apache-2.0）の CLI。REQ-0067 / ADR-0039。
# **ワーカー用（worker）と開発用（development）のイメージにだけ入れる。API のイメージには入れない。**
# バージョンを固定し、リリースの SHA256SUMS.txt の値で照合する。実行時には取りに行かない。
# 更新するときは、tests/generator が通り、Illustrator 版との比較（REQ-0067）で差が無いことを確かめる。
FROM base AS vectorcraft
ARG TARGETARCH
ARG VECTORCRAFT_VERSION=0.4.0
ARG VECTORCRAFT_SHA256_AMD64=9bc79a38f605689552ea2afdc6d476c6be780f8c71c740ce12a128f0ebbd5837
ARG VECTORCRAFT_SHA256_ARM64=46a6009982b54e05def859850462608a801540bb26c943e08783f3518d51e181
RUN <<EOF python
import hashlib, io, os, tarfile, urllib.request
arch = {"amd64": "x86_64", "arm64": "aarch64"}[os.environ["TARGETARCH"]]
expected = os.environ[f"VECTORCRAFT_SHA256_{os.environ['TARGETARCH'].upper()}"]
version = os.environ["VECTORCRAFT_VERSION"]
name = f"vectorcraft-{version}-linux-{arch}"
url = f"https://github.com/storytold/vectorcraft/releases/download/v{version}/{name}.tar.gz"
data = urllib.request.urlopen(url, timeout=120).read()
actual = hashlib.sha256(data).hexdigest()
assert actual == expected, f"checksum mismatch for {url}: {actual}"
with tarfile.open(fileobj=io.BytesIO(data)) as tar:
    # CLI とライセンスだけを取り出す（GUI 版の実行ファイルは使わない）
    members = [m for m in tar.getmembers()
               if m.name == f"{name}/bin/vectorcraft-cli" or m.name.startswith(f"{name}/share/doc/")]
    tar.extractall("/tmp/vc", members=members, filter="data")
os.rename(f"/tmp/vc/{name}", "/opt/vectorcraft")
EOF

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

# Install dependencies（製造データ生成のテストも動かせるよう、generator も入れる）
RUN uv sync --frozen --no-install-project --dev --extra generator

# 製造データ生成の VectorCraft（tests/generator が使う）
COPY --from=vectorcraft /opt/vectorcraft /opt/vectorcraft
ENV GENERATOR_VECTORCRAFT_CLI=/opt/vectorcraft/bin/vectorcraft-cli

# Copy application code
COPY . .

# Install project
RUN uv sync --frozen --dev --extra generator

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

# アプリ自身のコードもビルド時にコンパイルしておく（UV_COMPILE_BYTECODE は依存だけが対象で、
# PYTHONDONTWRITEBYTECODE=1 のため実行時にも保存されず、起動のたびにコンパイルし直す）
RUN python -m compileall -q app

# 起動時に `uv run` が環境を同期し直さない（開発用まで PyPI から入れ直してしまう。REQ-0057）。
# Terraform 側の migrate / worker Job の `uv run ...` にも効く。
ENV UV_NO_SYNC=1

# Run with uvicorn (production mode)
# マイグレーションはここで実行しない。複数インスタンスが同時に起動すると alembic が競合し、
# 起動そのものを壊す。デプロイ前の独立したステップ（Cloud Run Job）で
# `uv run alembic upgrade head` を実行する。
# exec で sh を置き換え、Cloud Run の SIGTERM を uvicorn まで届ける（sh が PID 1 のままだと
# 合図を受け流し、猶予の後に強制終了される）。
CMD ["sh", "-c", "exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Worker stage（製造データ生成ワーカー。Cloud Run Job pod-admin-worker が使う）
# API のイメージに、生成の依存（VectorCraft と numpy / scipy / pypdf）だけを足したもの。
# **生成は API のサーバーでは動かさない**（REQ-0067 / ADR-0039）。起動コマンドは
# Terraform の Job 定義（`uv run python -m app.worker`）が持つ。
FROM production AS worker

COPY --from=vectorcraft /opt/vectorcraft /opt/vectorcraft
ENV GENERATOR_VECTORCRAFT_CLI=/opt/vectorcraft/bin/vectorcraft-cli

RUN uv sync --frozen --no-dev --extra generator
