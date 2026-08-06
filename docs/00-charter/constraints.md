---
id: CONSTRAINTS
title: 技術制約・前提
status: draft
updated: 2026-08-06
---

<!-- 選択の余地がない前提条件。ADR で覆された場合はここも更新すること。 -->
<!-- 技術スタックは実ファイル（api/pyproject.toml, web/package.json）から読み取った確定値。 -->

## 技術スタック（確定）

| 領域 | 技術 | 決定根拠 |
|---|---|---|
| フロントエンド | Next.js 16 / React 19 / TypeScript 5 / Tailwind CSS 4 / Radix UI / React Hook Form + Zod / SWR | `web/package.json` |
| バックエンド | FastAPI / SQLAlchemy 2（async + asyncpg）/ Alembic / Pydantic 2 | `api/pyproject.toml` |
| データベース | PostgreSQL 16 | 部分ユニークインデックス（NULLS NOT DISTINCT, PG15+）を利用 |
| 認証 | JWT（python-jose, HS256）/ passlib + bcrypt | ADR-0001 |
| 帳票（PDF） | WeasyPrint + Jinja2 | ADR-0014 |
| メール送信 | SendGrid | ADR-0014 |
| 祝日判定 | jpholiday | ADR-0013 |
| ファイル保存 | Google Cloud Storage（未設定時ローカル） | ADR-0010 |
| パッケージ管理 | npm（web）/ uv（api） | — |
| テスト | vitest（web）/ pytest（api）/ Playwright（E2E） | — |
| 静的解析 | ESLint 9（web）/ ruff + mypy（api） | — |
| コンテナ | Docker Compose（api / web / db / e2e） | `api/docker-compose.yml` |

## 既存システムとの連携

| システム | 連携方式 | 制約 |
|---|---|---|
| 外部販売サイト（受注元） | 受注取り込み・照会 REST API（`X-API-Key` 認証、v1/v2） | APIキーは `order_sources` テーブル駆動（現状は平文保存） |
| illustrator-vm（製造データ生成） | 非同期ジョブ型 REST（process / status / download） | 認証は任意ヘッダ、直列処理、成果物は約72時間で削除。完了後すぐDL・自前保存が前提 |
| SendGrid | メール送信 API | 障害時は握りつぶし、業務処理は継続（ADR-0014） |
| Google Cloud Storage | ファイル永続化 | `GCS_BUCKET` 未設定時はローカル保存にフォールバック（ADR-0010） |
| 内部バッチ（cron） | GitHub Actions → 内部 REST（`X-Internal-Secret`） | メーカー日次ダイジェスト（15分間隔トリガ、ADR-0015） |

## インフラ・運用

- 本番 API: Railway。デプロイは `api/` で `railway up`（環境変数変更の自動再デプロイは不可）。手順は `api/DEPLOY.md`。
- フロントエンド: Vercel（CORS 許可オリジンに `https://pod-admin-beige.vercel.app`）。
- Alembic マイグレーションは単一ヘッドを維持する（多重ヘッドは本番起動 crash の原因）。
- 開発環境は Docker Compose（api / web / db / e2e）。

## 顧客側の制約

未確認（社内規定・承認プロセス・利用可否のあるサービス等は要確認）。

## 禁止事項

技術面の禁止事項（使用不可ライブラリ・送信不可データ等）は未確認。運用ルール（`main` 直コミット禁止など）は `AGENTS.md` を正本とする。
