# POD Admin — Print-On-Demand 受注管理システム

オリジナルグッズ（POD）の受注〜製造〜出荷を一元管理するフルスタック Web アプリケーション。

**主な機能:** 受注管理 / 出荷管理 / 製品管理 / 製造委託先ポータル / CSV 一括インポート / 配送通知メール / 請求書 PDF 生成 / 外部販売サイト API 連携 / チャット / ダッシュボード

---

## 技術スタック

- フロントエンド: Next.js 16 / React 19 / TypeScript 5 / Tailwind CSS 4 / Radix UI / React Hook Form + Zod / SWR
- バックエンド: FastAPI / SQLAlchemy 2 (async + asyncpg) / Alembic / Pydantic 2 / SendGrid / WeasyPrint
- 言語: TypeScript (フロントエンド) / Python 3.12 (バックエンド)
- データベース: PostgreSQL 16
- テスト: vitest（フロントエンド）, pytest（バックエンド）, Playwright（E2E）
- パッケージ管理: npm（フロントエンド）, uv（バックエンド）
- コンテナ: Docker Compose（api / web / db / e2e）
- コード品質: ESLint 9（フロントエンド）, ruff + mypy（バックエンド）


