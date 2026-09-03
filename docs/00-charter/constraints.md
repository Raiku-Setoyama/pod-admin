---
id: CONSTRAINTS
title: 技術制約・前提
status: draft
updated: 2026-09-03
---

<!-- 選択の余地がない前提条件。ADR で覆された場合はここも更新すること。 -->
<!-- 技術スタックは実ファイル（api/pyproject.toml, web/package.json）から読み取った確定値。 -->

## 技術スタック（確定）

| 領域 | 技術 | 決定根拠 |
|---|---|---|
| フロントエンド | Next.js 16 / React 19 / TypeScript 5 / Tailwind CSS 4 / Radix UI / React Hook Form + Zod / SWR | `web/package.json` |
| バックエンド | FastAPI / SQLAlchemy 2（async + asyncpg）/ Alembic / Pydantic 2 | `api/pyproject.toml` |
| データベース | PostgreSQL 17（本番・ステージング）/ 16（ローカル開発） | 部分ユニークインデックス（NULLS NOT DISTINCT, PG15+）を利用。**本番の実測は 17.11**（REQ-0054 で確認） |
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
| illustrator-vm（製造データ生成） | 非同期ジョブ型 REST（process / status / download） | **VPC 内の Windows VM。認証は無く、到達できるのはワーカーの Direct VPC egress と IAP だけ**（REQ-0055）。直列処理、成果物は約72時間で削除。完了後すぐDL・自前保存が前提 |
| SendGrid | メール送信 API | 障害時は握りつぶし、業務処理は継続（ADR-0014） |
| Google Cloud Storage | ファイル永続化 | `GCS_BUCKET` 未設定時はローカル保存にフォールバック（ADR-0010） |
| 内部バッチ（cron） | GitHub Actions → 内部 REST（`X-Internal-Secret`） | メーカー日次ダイジェスト（15分間隔トリガ、ADR-0015） |

## インフラ・運用

- 本番・ステージングとも **GCP**（`tosyo-api-504104` / `tosyo-api-stg`）。API と管理画面は Cloud Run、
  DB は Cloud SQL、ファイルは GCS。インフラは Terraform（`infra/`）で管理し、
  **`apply` は作業者の手元で実行する**（CI に state と機密を渡さない。ADR-0031）。
- デプロイは GitHub Actions（Workload Identity 連携。ADR-0028）。**Railway と Vercel は 2026-09-01 に切り替え済み**（REQ-0054）。
- 製造データ生成の VM も Terraform 管理下にある（`infra/modules/illustrator-vm/`）。
  **作り直さない運用である**（ディスク上の Adobe ライセンス認証を保つため）。
- Alembic マイグレーションは単一ヘッドを維持する（多重ヘッドは本番起動 crash の原因）。
- 開発環境は Docker Compose（api / web / db / e2e）。

## 顧客側の制約

未確認（社内規定・承認プロセス・利用可否のあるサービス等は要確認）。

## 禁止事項

技術面の禁止事項（使用不可ライブラリ・送信不可データ等）は未確認。運用ルール（`main` 直コミット禁止など）は `AGENTS.md` を正本とする。
