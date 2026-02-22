---
name: project-init
description: ADD方式での開発に必要な初期設定を行う。技術スタック検出、Docker環境構築、テスト設定。
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(docker:*), Bash(npm:*), Bash(npx:*)
---

# プロジェクト初期設定ガイド

このスキルはADD方式での開発を始める前の初期設定を支援する。

## 実行すべきタスク

### 1. 技術スタックの検出と CLAUDE.md の更新

以下のファイルを確認して技術スタックを特定:

| 検出対象 | 確認ファイル |
|---------|-------------|
| Node.js/TypeScript | `package.json`, `tsconfig.json` |
| Python | `pyproject.toml`, `requirements.txt`, `setup.py` |
| Go | `go.mod` |
| フレームワーク | 依存関係から判断（Next.js, FastAPI, Express等） |
| DB | docker-compose.yml, 環境変数, ORM設定 |

検出後、`CLAUDE.md` の「技術スタック」セクションを更新する。

### 2. Docker環境の構築

プロジェクトの技術スタックに合わせて以下を生成:

#### Node.js プロジェクト

**Dockerfile**:
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

**docker-compose.yml**:
```yaml
services:
  app:
    build: .
    volumes:
      - .:/app
      - node_modules:/app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/app_dev
    depends_on:
      db:
        condition: service_healthy
    tty: true
    command: npm run dev

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  node_modules:
  pgdata:
```

#### Python (FastAPI) プロジェクト

**Dockerfile**:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]
```

**docker-compose.yml**:
```yaml
services:
  app:
    build: .
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/app_dev
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

### 3. テスト用Docker環境

**docker-compose.test.yml**（共通パターン）:
```yaml
services:
  test-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: app_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test -d app_test"]
      interval: 5s
      timeout: 5s
      retries: 5
    tmpfs:
      - /var/lib/postgresql/data
```

### 4. テスト環境の設定

#### Node.js: vitest設定

**vitest.config.ts**:
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'tests/'],
    },
  },
});
```

#### Python: pytest設定

**pyproject.toml** に追加:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --cov=app --cov-report=term-missing"
```

### 5. 必要なスクリプトの追加

#### Node.js: package.json

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:unit": "vitest run tests/unit",
    "test:integration": "vitest run --config vitest.integration.config.ts",
    "test:e2e": "playwright test",
    "lint": "eslint . --ext .ts,.tsx",
    "typecheck": "tsc --noEmit"
  }
}
```

#### Python: Makefile

```makefile
.PHONY: dev test lint

dev:
	docker compose up -d

test:
	docker compose exec app pytest

test-unit:
	docker compose exec app pytest tests/unit

test-integration:
	docker compose -f docker-compose.yml -f docker-compose.test.yml up -d test-db
	docker compose exec app pytest tests/integration
	docker compose -f docker-compose.yml -f docker-compose.test.yml down test-db

lint:
	docker compose exec app ruff check .
	docker compose exec app mypy app

migrate:
	docker compose exec app alembic upgrade head

migrate-new:
	docker compose exec app alembic revision --autogenerate -m "$(MSG)"
```

## チェックリスト

初期設定完了時に以下を確認:

- [ ] CLAUDE.md の技術スタックが正しく設定されている
- [ ] Dockerfile が存在し、ビルドできる
- [ ] docker-compose.yml が存在し、`docker compose up -d` で起動できる
- [ ] docker-compose.test.yml が存在する
- [ ] テスト実行スクリプトが設定されている
- [ ] lint/typecheck スクリプトが設定されている

## 既存プロジェクトへの適用

既存ファイルがある場合:
- **上書きしない**: 既存の設定を尊重
- **不足分を追加**: 必要なスクリプトやDockerファイルのみ追加
- **整合性を確認**: 既存設定とADD方式の要件が矛盾しないか確認
