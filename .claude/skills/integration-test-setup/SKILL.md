---
name: integration-test-setup
description: バックエンド統合テスト環境の初期構築ガイド（DBモック方式）。tests/integration/が存在しない場合に参照。
allowed-tools: Read, Write, Edit, Bash(docker:*), Bash(npm:*), Bash(npx:*)
---

# バックエンド統合テスト環境 初期構築ガイド

**このスキルは `tests/integration/` ディレクトリが存在しない場合にのみ参照する。**

## 概要

統合テストは複数モジュール間の連携（API層〜サービス層）を検証する。
DB操作はモック/スタブで分離し、実DBには接続しない。これにより:
- テスト用DBコンテナの起動・停止が不要で高速
- DB接続エラー・ポート競合等の環境依存問題が発生しない
- CI/CD環境でも安定して動作する

```
テストコード → API/Router → Service → Repository（モック）
```

## 必須ファイル構成

### TypeScript (vitest)

```
tests/
├── integration/
│   ├── helpers.ts         # テストユーティリティ
│   └── services/
│       └── user.test.ts   # 統合テスト
└── vitest.integration.config.ts
```

### Python (pytest)

```
tests/
├── integration/
│   ├── conftest.py        # フィクスチャ・モック設定
│   └── test_user_api.py   # 統合テスト
```

---

## TypeScript セットアップ

### 1. vitest.integration.config.ts

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/integration/**/*.test.ts'],
    testTimeout: 10000,
  },
});
```

### 2. tests/integration/helpers.ts（テストユーティリティ）

```typescript
import { vi } from 'vitest';

// Repository のモックファクトリ
export function createMockRepository() {
  return {
    findById: vi.fn(),
    findAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  };
}

// API テスト用ヘルパー（フレームワークに合わせて調整）
// Express の場合: supertest を使用
// Hono の場合: app.request() を使用
// Nest.js の場合: @nestjs/testing を使用
```

### 3. tests/integration/services/user.test.ts（テスト例）

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createMockRepository } from '../helpers';

// モジュールのモック（実際のパスに合わせて調整）
vi.mock('../../../src/repositories/user', () => ({
  userRepository: createMockRepository(),
}));

import { userRepository } from '../../../src/repositories/user';
import { createUser, getUserById } from '../../../src/services/user';

describe('UserService Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createUser', () => {
    it('should create a user via service layer', async () => {
      const mockUser = { id: 1, email: 'test@example.com', name: 'Test User' };
      vi.mocked(userRepository.create).mockResolvedValue(mockUser);

      const result = await createUser({
        email: 'test@example.com',
        name: 'Test User',
      });

      expect(result.id).toBeDefined();
      expect(result.email).toBe('test@example.com');
      expect(userRepository.create).toHaveBeenCalledWith({
        email: 'test@example.com',
        name: 'Test User',
      });
    });

    it('should reject duplicate email', async () => {
      vi.mocked(userRepository.create).mockRejectedValue(
        new Error('Email already exists')
      );

      await expect(
        createUser({ email: 'existing@example.com', name: 'New' })
      ).rejects.toThrow('Email already exists');
    });
  });

  describe('getUserById', () => {
    it('should return user when exists', async () => {
      const mockUser = { id: 1, email: 'find@example.com', name: 'Find Me' };
      vi.mocked(userRepository.findById).mockResolvedValue(mockUser);

      const result = await getUserById(1);

      expect(result).not.toBeNull();
      expect(result?.name).toBe('Find Me');
      expect(userRepository.findById).toHaveBeenCalledWith(1);
    });

    it('should return null when not exists', async () => {
      vi.mocked(userRepository.findById).mockResolvedValue(null);

      const result = await getUserById(99999);
      expect(result).toBeNull();
    });
  });
});
```

### 4. package.json スクリプト

```json
{
  "scripts": {
    "test:unit": "vitest run tests/unit",
    "test:integration": "vitest run --config vitest.integration.config.ts",
    "test": "npm run test:unit && npm run test:integration"
  }
}
```

---

## Python セットアップ

### 1. tests/integration/conftest.py（フィクスチャ・モック設定）

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db_session():
    """DB セッションのモック"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_user_repository():
    """UserRepository のモック"""
    repo = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_all = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo
```

### 2. tests/integration/test_user_api.py（テスト例 — FastAPI）

```python
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_create_user(mock_user_repository):
    mock_user = {"id": 1, "email": "test@example.com", "name": "Test User"}
    mock_user_repository.create.return_value = mock_user

    with patch("app.services.user.user_repository", mock_user_repository):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/users",
                json={"email": "test@example.com", "name": "Test User"},
            )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    mock_user_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_not_found(mock_user_repository):
    mock_user_repository.find_by_id.return_value = None

    with patch("app.services.user.user_repository", mock_user_repository):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/users/99999")

    assert response.status_code == 404
```

---

## モック方針

### 何をモックするか

| モック対象 | 理由 |
|-----------|------|
| Repository 層（DB操作） | DB接続不要で安定・高速 |
| 外部API呼び出し | ネットワーク依存を排除 |
| ファイルシステム操作 | テスト環境の汚染を防止 |

### 何をモックしないか

| モックしない対象 | 理由 |
|-----------------|------|
| Router → Service の結合 | 統合テストの本質（層間の連携検証） |
| バリデーション | 入力チェックの動作確認が必要 |
| ミドルウェア | 認証・エラーハンドリングの検証が必要 |

---

## チェックリスト

新規プロジェクトで統合テスト環境を構築する際：

1. [ ] テスト設定ファイルを作成（`vitest.integration.config.ts` or pytest設定）
2. [ ] `tests/integration/` ディレクトリを作成
3. [ ] テストヘルパー/フィクスチャを作成（モックファクトリ）
4. [ ] `package.json`（or `pyproject.toml`）にスクリプト追加
5. [ ] 最初の統合テストを作成して動作確認
