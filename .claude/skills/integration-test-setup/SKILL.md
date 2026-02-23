---
name: integration-test-setup
description: バックエンド統合テスト環境の初期構築ガイド。tests/integration/が存在しない場合に参照。
allowed-tools: Read, Write, Edit, Bash(docker:*), Bash(npm:*), Bash(npx:*)
---

# バックエンド統合テスト環境 初期構築ガイド

**このスキルは `tests/integration/` ディレクトリが存在しない場合にのみ参照する。**

## 概要

統合テストは複数モジュール間の連携を実際のDB接続で検証する。
モックを使わず、本番に近い環境でテストすることで信頼性を高める。

```
テストコード → Service → Repository → 実DB（Docker）
```

## 必須ファイル構成

```
tests/
├── integration/
│   ├── setup.ts           # グローバルセットアップ
│   ├── helpers.ts         # テストユーティリティ
│   └── services/
│       └── user.test.ts   # 統合テスト
├── fixtures/
│   └── users.json         # テストデータ
└── vitest.integration.config.ts
docker-compose.test.yml    # テスト用DB定義
.env.test                  # テスト用環境変数
```

---

## セットアップ手順

### 1. docker-compose.test.yml（テスト用DB）

```yaml
version: '3.8'

services:
  test-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test_db
    ports:
      - "5433:5432"  # 本番と異なるポート
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5
    tmpfs:
      - /var/lib/postgresql/data  # メモリ上で高速化
```

### 2. .env.test（テスト用環境変数）

```env
DATABASE_URL=postgresql://test:test@localhost:5433/test_db
NODE_ENV=test
```

### 3. vitest.integration.config.ts

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/integration/**/*.test.ts'],
    globalSetup: './tests/integration/setup.ts',
    testTimeout: 30000,
    hookTimeout: 30000,
    pool: 'forks',        // テスト間の分離
    poolOptions: {
      forks: {
        singleFork: true, // DB接続の競合を防ぐ
      },
    },
    env: {
      DATABASE_URL: 'postgresql://test:test@localhost:5433/test_db',
    },
  },
});
```

### 4. tests/integration/setup.ts（グローバルセットアップ）

```typescript
import { execSync } from 'child_process';

export async function setup() {
  console.log('🔧 Starting test database...');

  // テスト用DBコンテナを起動
  execSync('docker compose -f docker-compose.test.yml up -d --wait', {
    stdio: 'inherit',
  });

  // マイグレーション実行
  execSync('npx prisma migrate deploy', {
    stdio: 'inherit',
    env: { ...process.env, DATABASE_URL: process.env.DATABASE_URL },
  });

  console.log('✅ Test database ready');
}

export async function teardown() {
  console.log('🧹 Stopping test database...');
  execSync('docker compose -f docker-compose.test.yml down -v', {
    stdio: 'inherit',
  });
}
```

### 5. tests/integration/helpers.ts（テストユーティリティ）

```typescript
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// 各テスト前にデータをリセット
export async function resetDatabase() {
  const tables = await prisma.$queryRaw<{ tablename: string }[]>`
    SELECT tablename FROM pg_tables WHERE schemaname = 'public'
  `;

  for (const { tablename } of tables) {
    if (tablename !== '_prisma_migrations') {
      await prisma.$executeRawUnsafe(`TRUNCATE TABLE "${tablename}" CASCADE`);
    }
  }
}

// フィクスチャデータの投入
export async function seedUsers(users: Array<{ email: string; name: string }>) {
  return prisma.user.createMany({ data: users });
}

export { prisma };
```

### 6. tests/integration/services/user.test.ts（テスト例）

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { resetDatabase, seedUsers, prisma } from '../helpers';
import { createUser, getUserById } from '../../../src/services/user';

describe('UserService Integration', () => {
  beforeEach(async () => {
    await resetDatabase();
  });

  describe('createUser', () => {
    it('should create a user in the database', async () => {
      const result = await createUser({
        email: 'test@example.com',
        name: 'Test User',
      });

      expect(result.id).toBeDefined();
      expect(result.email).toBe('test@example.com');

      // DBに実際に保存されているか確認
      const saved = await prisma.user.findUnique({
        where: { id: result.id },
      });
      expect(saved).not.toBeNull();
      expect(saved?.email).toBe('test@example.com');
    });

    it('should reject duplicate email', async () => {
      await seedUsers([{ email: 'existing@example.com', name: 'Existing' }]);

      await expect(
        createUser({ email: 'existing@example.com', name: 'New' })
      ).rejects.toThrow('Email already exists');
    });
  });

  describe('getUserById', () => {
    it('should return user when exists', async () => {
      const [created] = await seedUsers([
        { email: 'find@example.com', name: 'Find Me' },
      ]);

      const result = await getUserById(created.id);

      expect(result).not.toBeNull();
      expect(result?.name).toBe('Find Me');
    });

    it('should return null when not exists', async () => {
      const result = await getUserById(99999);
      expect(result).toBeNull();
    });
  });
});
```

### 7. package.json スクリプト

```json
{
  "scripts": {
    "test:unit": "vitest run tests/unit",
    "test:integration": "vitest run --config vitest.integration.config.ts",
    "test:integration:watch": "vitest --config vitest.integration.config.ts",
    "test": "npm run test:unit && npm run test:integration"
  }
}
```

---

## フレームワーク別の補足

### Prisma (Node.js)

```typescript
// setup.ts
execSync('npx prisma migrate deploy', { ... });

// helpers.ts - トランザクションでロールバック
export async function withTransaction<T>(
  fn: (tx: Prisma.TransactionClient) => Promise<T>
): Promise<T> {
  return prisma.$transaction(async (tx) => {
    const result = await fn(tx);
    throw new Error('ROLLBACK'); // 強制ロールバック
  }).catch((e) => {
    if (e.message === 'ROLLBACK') return result;
    throw e;
  });
}
```

### SQLAlchemy (FastAPI/Python)

```python
# conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

TEST_DATABASE_URL = "postgresql://test:test@localhost:5433/test_db"

@pytest.fixture(scope="session")
def engine():
    return create_engine(TEST_DATABASE_URL)

@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()  # 各テスト後にロールバック
    connection.close()
```

```python
# tests/integration/test_user_service.py
def test_create_user(db_session):
    result = user_service.create(db_session, UserCreate(
        email="test@example.com",
        name="Test User"
    ))

    assert result.id is not None
    assert result.email == "test@example.com"

    # DBに保存されているか確認
    saved = db_session.query(User).filter(User.id == result.id).first()
    assert saved is not None
```

---

## テストデータ戦略

### 方式1: 各テスト前にリセット + シード

```typescript
beforeEach(async () => {
  await resetDatabase();
  await seedUsers(fixtures.users);
});
```

- シンプルで確実
- テスト間の独立性が高い
- 大量データでは遅くなる可能性

### 方式2: トランザクションロールバック

```typescript
beforeEach(async () => {
  await prisma.$executeRaw`BEGIN`;
});

afterEach(async () => {
  await prisma.$executeRaw`ROLLBACK`;
});
```

- 高速
- 複数接続では動作しない場合あり

### 推奨: 方式1（リセット + シード）

信頼性を優先し、テストの独立性を確保する。

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| ECONNREFUSED | テストDBコンテナ未起動 | `docker compose -f docker-compose.test.yml up -d` |
| マイグレーション失敗 | スキーマ不整合 | `docker compose -f docker-compose.test.yml down -v` で初期化 |
| テストがハング | 接続プール枯渇 | `singleFork: true` を設定 |
| データ残留 | リセット漏れ | `beforeEach` で `resetDatabase()` を確実に呼ぶ |

---

## チェックリスト

新規プロジェクトで統合テスト環境を構築する際：

1. [ ] `docker-compose.test.yml` を作成
2. [ ] `.env.test` を作成
3. [ ] `vitest.integration.config.ts` を作成
4. [ ] `tests/integration/setup.ts` を作成
5. [ ] `tests/integration/helpers.ts` を作成
6. [ ] `package.json` にスクリプト追加
7. [ ] `.gitignore` に `.env.test` を追加（必要に応じて）
8. [ ] 最初の統合テストを作成して動作確認
