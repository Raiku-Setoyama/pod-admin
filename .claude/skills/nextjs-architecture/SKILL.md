---
name: nextjs-architecture
description: Next.js (App Router) フロントエンドアーキテクチャの設計・実装ガイド。フロントエンド新規構築時に参照。
---

# Next.js (App Router) フロントエンド アーキテクチャ

## ディレクトリ構造

```
src/
├── app/                      # App Router（ルーティング・ページ）
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   ├── (auth)/               # 認証関連（ルートグループ）
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── register/
│   │       └── page.tsx
│   └── dashboard/
│       ├── layout.tsx
│       └── page.tsx
│
├── components/               # コンポーネント
│   ├── ui/                   # shadcn/ui（自動生成先）
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── ...
│   ├── common/               # アプリ共通の複合UIコンポーネント
│   │   ├── page-title.tsx
│   │   ├── confirm-dialog.tsx
│   │   ├── data-table.tsx
│   │   └── empty-state.tsx
│   ├── layouts/              # レイアウト部品
│   │   ├── header.tsx
│   │   ├── sidebar.tsx
│   │   └── footer.tsx
│   └── features/             # 機能別コンポーネント
│       ├── auth/
│       │   └── login-form.tsx
│       └── dashboard/
│           └── stats-card.tsx
│
├── hooks/                    # カスタムフック
│   ├── use-auth.ts
│   └── use-api.ts
│
├── lib/                      # ライブラリ・ユーティリティ
│   ├── api-client.ts         # API通信クライアント
│   ├── utils.ts              # 汎用ユーティリティ
│   └── constants.ts          # 定数
│
├── types/                    # 型定義
│   ├── api.ts                # APIレスポンス型
│   └── models.ts             # ドメインモデル型
│
└── stores/                   # 状態管理（Zustand）
    ├── auth-store.ts
    └── ui-store.ts
```

---

## 各ディレクトリの責務

| ディレクトリ | 責務 | 備考 |
|-------------|------|------|
| `app/` | ルーティング・ページ構成 | App Router専用。UIロジックは最小限に |
| `components/ui/` | プリミティブUIコンポーネント | shadcn/uiの出力先。再利用可能な基本部品 |
| `components/common/` | アプリ共通の複合UIコンポーネント | ui/を組み合わせた共通部品。複数機能で再利用 |
| `components/layouts/` | ページレイアウト部品 | Header、Sidebar、Footerなど |
| `components/features/` | 機能固有コンポーネント | ビジネスロジックを含むUI |
| `hooks/` | カスタムフック | データ取得・状態管理ロジック |
| `lib/` | ユーティリティ・設定 | API通信、ヘルパー関数、定数 |
| `types/` | TypeScript型定義 | API・ドメインモデルの型 |
| `stores/` | グローバル状態管理 | Zustandによる状態管理 |

---

## 設計方針

### 1. コンポーネントの4層分離

```
ui/          → プリミティブUI（shadcn/ui）
common/      → アプリ共通の複合UI（ui/を組み合わせたもの）
layouts/     → ページ構造（配置・レイアウト）
features/    → ビジネスロジック＋UI
```

| ディレクトリ | 責務 | 例 |
|-------------|------|-----|
| `ui/` | プリミティブUI（shadcn/ui） | Button, Input, Dialog |
| `common/` | アプリ共通の複合UI | PageTitle, DataTable, ConfirmDialog |
| `layouts/` | ページ構造 | Header, Sidebar, Footer |
| `features/` | 機能固有のUI + ロジック | LoginForm, UserProfile |

### 2. app/ はシンプルに保つ

```tsx
// app/dashboard/page.tsx
import { DashboardView } from '@/components/features/dashboard/dashboard-view'

export default function DashboardPage() {
  return <DashboardView />
}
```

ページファイルは「どのコンポーネントを表示するか」だけを担当します。

### 3. API通信の集約

```tsx
// lib/api-client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL

export const apiClient = {
  get: <T>(path: string) =>
    fetch(`${API_BASE}${path}`).then(res => res.json() as Promise<T>),

  post: <T>(path: string, body: unknown) =>
    fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(res => res.json() as Promise<T>),
}
```

### 4. 型定義の分離

```tsx
// types/models.ts
export type User = {
  id: string
  email: string
  name: string
}

// types/api.ts
import type { User } from './models'

export type LoginResponse = {
  user: User
  token: string
}
```

---

## 状態管理（Zustand）

### 基本的なStore定義

```tsx
// stores/auth-store.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/models'

type AuthState = {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

type AuthActions = {
  login: (user: User, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: (user, token) =>
        set({ user, token, isAuthenticated: true }),

      logout: () =>
        set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
    }
  )
)
```

### UI状態のStore例

```tsx
// stores/ui-store.ts
import { create } from 'zustand'

type UIState = {
  isSidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  isSidebarOpen: true,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setSidebarOpen: (open) => set({ isSidebarOpen: open }),
}))
```

### コンポーネントでの使用

```tsx
// components/layouts/header.tsx
'use client'

import { useAuthStore } from '@/stores/auth-store'
import { useUIStore } from '@/stores/ui-store'

export function Header() {
  const { user, logout } = useAuthStore()
  const { toggleSidebar } = useUIStore()

  return (
    <header>
      <button onClick={toggleSidebar}>メニュー</button>
      {user && (
        <>
          <span>{user.name}</span>
          <button onClick={logout}>ログアウト</button>
        </>
      )}
    </header>
  )
}
```

### Zustand 設計ガイドライン

| 原則 | 説明 |
|------|------|
| Store は機能単位で分割 | `auth-store`, `ui-store` など責務ごとに分ける |
| 型定義を明確に | State と Actions を分離して定義する |
| persist は必要な場合のみ | 認証情報など永続化が必要なものに限定 |
| セレクタを活用 | 不要な再レンダリングを防ぐ |

```tsx
// セレクタによる最適化例
const userName = useAuthStore((state) => state.user?.name)
```

---

## shadcn/ui の初期設定

```bash
# shadcn/ui のセットアップ時に src/components/ui を指定
npx shadcn@latest init
```

`components.json` で出力先を設定：

```json
{
  "aliases": {
    "components": "@/components",
    "ui": "@/components/ui"
  }
}
```

---

## 品質保証

### 最低限の品質チェック構成

| チェック項目 | コマンド | 目的 |
|-------------|----------|------|
| TypeScript型チェック | `tsc --noEmit` | 型エラーの検出 |
| ESLint | `eslint .` | コード品質・一貫性の担保 |
| ビルド確認 | `next build` | 本番ビルドの成功確認 |

### package.json スクリプト設定

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "type-check": "tsc --noEmit",
    "check-all": "npm run type-check && npm run lint && npm run build"
  }
}
```

### 品質チェックの実行タイミング

```
開発中       → npm run lint（随時）
コミット前   → npm run check-all
CI/CD        → npm run check-all
```
