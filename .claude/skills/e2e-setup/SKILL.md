---
name: e2e-setup
description: Playwright E2E環境の初期構築ガイド。ユーザーが明示的にE2Eテストを依頼した場合に参照。
allowed-tools: Read, Write, Edit, Bash(docker:*), Bash(npm:*), Bash(npx:*)
---

# Playwright E2E環境 初期構築ガイド

**このスキルはユーザーが明示的にE2Eテストを依頼し、`e2e/` ディレクトリが存在しない場合にのみ参照する。**
（E2Eテストはデフォルトでは生成・実行しない）

## アーキテクチャ

```
Playwright → Dev Server (localhost) → Backend (Docker)
```

## 必須ファイル構成

```
e2e/
├── global-setup.ts      # テストデータ準備・認証
├── auth.setup.ts        # 認証セットアップ（認証が必要な場合）
├── tests/
│   └── *.spec.ts        # テストファイル
├── .auth/               # 認証状態の保存先（.gitignore対象）
│   └── user.json        # ログイン状態
└── .env.test            # テスト用環境変数・認証情報
playwright.config.ts     # Playwright設定
```

## セットアップ手順

### 1. Playwrightインストール

```bash
npm install -D @playwright/test
npx playwright install
```

### 2. playwright.config.ts

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/tests',
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
  },
  webServer: {
    command: 'npm run dev:test',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

### 3. global-setup.ts（テストデータ準備）

```typescript
import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  // テストユーザー作成・シードデータ投入
  // バックエンドに応じて実装（下記参照）
}

export default globalSetup;
```

### 4. package.json スクリプト

```json
{
  "dev:test": "<テスト用環境変数で開発サーバー起動>",
  "test:e2e": "playwright test",
  "test:e2e:local": "<Docker起動> && npm run test:e2e"
}
```

---

## 認証情報の管理（.env.test）

### .env.test の構成

```env
# ===========================================
# E2Eテスト用環境変数
# ===========================================

# アプリケーション
BASE_URL=http://localhost:3000
API_URL=http://localhost:3000/api

# ===========================================
# テストユーザー認証情報
# ===========================================

# 一般ユーザー（通常のテストで使用）
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=TestPassword123!

# 管理者ユーザー（管理機能のテストで使用）
TEST_ADMIN_EMAIL=admin@example.com
TEST_ADMIN_PASSWORD=AdminPassword123!

# ===========================================
# 外部サービス認証（必要に応じて）
# ===========================================

# Supabase
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Firebase（エミュレータ）
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099

# その他のAPIキー
TEST_API_KEY=test-api-key-for-e2e
```

### .gitignore に追加

```gitignore
# E2Eテスト
e2e/.env.test
e2e/.auth/
```

**注意**: `.env.test` には本番の認証情報を絶対に含めないこと。テスト専用の認証情報のみを使用する。

### 認証セットアップ（auth.setup.ts）

```typescript
import { test as setup, expect } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// .env.test を読み込み
dotenv.config({ path: path.resolve(__dirname, '.env.test') });

const authFile = path.join(__dirname, '.auth/user.json');

setup('authenticate', async ({ page }) => {
  // ログインページに移動
  await page.goto('/login');

  // 認証情報を .env.test から取得
  const email = process.env.TEST_USER_EMAIL!;
  const password = process.env.TEST_USER_PASSWORD!;

  // ログインフォームに入力
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // ログイン成功を確認
  await expect(page).toHaveURL('/dashboard');

  // 認証状態を保存
  await page.context().storageState({ path: authFile });
});
```

### playwright.config.ts（認証対応版）

```typescript
import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// .env.test を読み込み
dotenv.config({ path: path.resolve(__dirname, 'e2e/.env.test') });

export default defineConfig({
  testDir: './e2e/tests',
  globalSetup: './e2e/global-setup.ts',

  projects: [
    // 認証セットアップ（最初に実行）
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
    },
    // 認証が必要なテスト
    {
      name: 'authenticated',
      testMatch: /.*\.spec\.ts/,
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        storageState: './e2e/.auth/user.json',
      },
    },
    // 認証不要なテスト（ログインページなど）
    {
      name: 'unauthenticated',
      testMatch: /.*\.unauth\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },

  webServer: {
    command: 'npm run dev:test',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

### global-setup.ts（テストユーザー作成）

```typescript
import { FullConfig } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '.env.test') });

async function globalSetup(config: FullConfig) {
  const email = process.env.TEST_USER_EMAIL!;
  const password = process.env.TEST_USER_PASSWORD!;

  // テストユーザーを作成（既存の場合はスキップ）
  // バックエンドに応じて実装
  await createTestUser(email, password);
}

async function createTestUser(email: string, password: string) {
  // 例: APIエンドポイントでテストユーザーを作成
  const response = await fetch(`${process.env.API_URL}/test/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok && response.status !== 409) {
    throw new Error(`Failed to create test user: ${response.statusText}`);
  }
}

export default globalSetup;
```

---

## バックエンド別の実装

### Supabase

```bash
npm install -g supabase
```

**ローカル開発用キー**（固定値、公開情報）:
```env
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU
```

**global-setup.ts**:
```typescript
await supabase.auth.admin.createUser({
  email, password, email_confirm: true
});
```

**起動**: `supabase stop; supabase start && npm run test:e2e`

### FastAPI / Node.js + Docker

**docker-compose.yml** でバックエンド+DBを定義。

**global-setup.ts**:
```typescript
await fetch('http://localhost:8000/api/test/setup', { method: 'POST' });
// または直接DBに接続してシード
```

**起動**: `docker compose up -d && npm run test:e2e`

**注意**: サービス起動待機が必要な場合は `wait-on` パッケージや `healthcheck` を活用。

---

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| ECONNREFUSED | Dockerサービス未起動 | `docker compose ps` / `supabase status` で確認 |
| テストデータ作成失敗 | 認証キー/エンドポイント誤り | 環境変数を確認 |
| webServer起動タイムアウト | 起動に時間がかかる | `timeout` を増やす |
| 認証状態が保持されない | storageState パスの誤り | `.auth/user.json` の存在確認 |
| ログインに失敗する | 認証情報の不一致 | `.env.test` の値を確認 |

---

## セキュリティベストプラクティス

### やるべきこと

1. **テスト専用の認証情報を使用**: 本番環境とは異なるユーザー/パスワードを使用
2. **`.env.test` を `.gitignore` に追加**: 認証情報をリポジトリにコミットしない
3. **`.env.test.example` を用意**: 必要な環境変数のテンプレートをコミット
4. **CI/CD では環境変数を使用**: GitHub Secrets 等で認証情報を管理

### やってはいけないこと

1. **本番の認証情報を使用しない**: テスト環境専用の認証情報のみ使用
2. **認証情報をハードコードしない**: 必ず `.env.test` から読み込む
3. **`.auth/` ディレクトリをコミットしない**: 認証トークンが含まれる

### .env.test.example（テンプレート）

```env
# E2Eテスト用環境変数のテンプレート
# このファイルをコピーして .env.test を作成してください

BASE_URL=http://localhost:3000
API_URL=http://localhost:3000/api

# テストユーザー（テスト環境専用の値を設定）
TEST_USER_EMAIL=
TEST_USER_PASSWORD=

# 外部サービス（必要に応じて設定）
# SUPABASE_URL=
# SUPABASE_ANON_KEY=
```
