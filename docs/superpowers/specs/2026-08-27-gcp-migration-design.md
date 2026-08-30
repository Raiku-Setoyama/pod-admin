---
title: GCP 移行設計（Railway/Vercel → GCP、Terraform IaC、本番/ステージング 2 環境）
date: 2026-08-27
status: draft
---

# GCP 移行設計

## 1. 目的とスコープ

Railway（API）と Vercel（フロント）で簡易的にホスティングしている POD Admin を、
本格運用に耐える構成として GCP へ移行する。インフラは Terraform で IaC 管理し、
**ステージングを先に構築して動作確認が取れてから本番を移行する。**

### スコープに含む

- Terraform による GCP リソースの構築（本番 `tosyo-api-504104` / ステージング `tosyo-api-stg`）
- Cloud Run 上で動くようにするためのアプリ改修
- GitHub Actions + Workload Identity 連携による CI/CD
- 本番データ（PostgreSQL・GCS）の移行とカットオーバー
- `illustrator-vm` の会社組織への移送と閉域化（フェーズ 5）

### スコープに含まない

- 機能追加・UI 変更
- 既存の技術的負債の解消（`REQ-0042` のテスト赤、API キー平文保存など）
- 監視・アラートの本格整備（最低限のものだけ入れる）

### 前提

- ステージングにデータ移行はない（本番のみ既存データを持つ）
- 当面は Cloud Run の `*.run.app` URL で運用する（独自ドメインは後日）
- 本番カットオーバーには**数時間のメンテナンス枠**を取れる

---

## 2. 現状（2026-08-27 実測）

### 2.1 稼働中の構成

| 層 | 現状 | 根拠 |
|---|---|---|
| API | Railway（`railway up` でデプロイ） | `api/railway.toml`, `api/DEPLOY.md` |
| フロント | **Vercel**（project `pod-admin`） | `web/.vercel/project.json`, `CORS_ORIGINS` の既定値 |
| DB | Railway PostgreSQL | `DATABASE_URL` |
| ファイル | GCS `gs://pod-admin-prod` | `api/app/utils/file_storage.py` |
| 製造データ生成 | GCE Windows VM `illustrator-vm-preview` | `ILLUSTRATOR_VM_BASE_URL` |
| 日次バッチ | GitHub Actions cron（15 分毎） | `.github/workflows/manufacturer-daily-digest.yml` |

依頼時の認識は「フロント・バックともに Railway」だったが、**フロントは Vercel** である。

### 2.2 GCP の実測結果

| 項目 | 結果 |
|---|---|
| 組織 | `tosyoworkspace.tokyo`（ID `635705009532`） |
| 本番プロジェクト | `tosyo-api-504104`（TOSYO-API、番号 858634860577）— **完全に空**。既定 API のみ、`compute` 未有効、バケット 0 |
| ステージングプロジェクト | `tosyo-api-stg`（TOSYO-API-STG、番号 644320531544）— 同上、完全に空 |
| 請求先 | 両プロジェクトとも `015882-BA1EA2-B71809` に紐付け済み・有効 |
| 組織ポリシー | `iam.allowedPolicyMemberDomains` / `compute.vmExternalIpAccess` / `run.allowedIngress` / `compute.restrictVpcPeering` はすべて ALLOW。`sql.restrictPublicIp` / `iam.disableServiceAccountKeyCreation` / `compute.requireShieldedVm` は未適用 |
| 作業者の権限 | `setoyama_ironiwa@tosyoworkspace.tokyo` は両プロジェクトで **`roles/editor`** |
| Owner | `admin@` / `eguchi_ay@` / `fujita_ma@` / `nakagawa_hi@`（すべて tosyoworkspace.tokyo） |

**組織ポリシーに Cloud Run の公開を妨げる制約がないことを確認済み**（`allUsers` の invoker 付与が可能）。

### 2.3 個人アカウント配下にある本番資産

`raiku6019@gmail.com` の `lively-transit-334610`（"My First Project"、請求先 `01AB65-9E05D7-B878D2`）に、
稼働中の本番資産がある。**会社の請求先とは別の請求先である。**

| 資産 | 詳細 |
|---|---|
| GCS `pod-admin-prod` | asia-northeast1 / **約 30MB** / UBLA 有効 / 公開防止 enforced / soft-delete 7 日 / ライフサイクル未設定 / 作成 2026-07-11 |
| GCE `illustrator-vm-preview` | e2-standard-2 / Windows Server 2025 DC / 100GB / asia-northeast1-a / 内部 IP `10.146.0.3` / 外部 IP `34.84.121.166` / RUNNING |

VM のサービスアカウントは既定の Compute SA（`103807024687-compute@developer`）で、
スコープは `devstorage.read_only` ほか。

### 2.4 セキュリティ上の発見（REQ-0055 で是正）

`lively-transit-334610` の `default` ネットワークのファイアウォール:

| ルール | 送信元 | ポート | ターゲットタグ |
|---|---|---|---|
| `allow-tshirt-api` | `0.0.0.0/0` | tcp:8000 | **なし（全インスタンスに適用）** |
| `default-allow-rdp` | `0.0.0.0/0` | tcp:3389 | なし |
| `default-allow-ssh` | `0.0.0.0/0` | tcp:22 | なし |

外部から実測して確認した:

```
http://34.84.121.166:8000/      → HTTP 200
http://34.84.121.166:8000/docs  → HTTP 200
```

`api/app/services/illustrator_vm_client.py` の docstring にも「認証なし / CORS * /
既定 127.0.0.1:8000（**プライベートVM前提**）」と明記されている。**前提が満たされていない。**
第三者がジョブ投入も成果物ダウンロードもできる状態にある。

なお VM に送信しているのは商品種別・サイズ・注文ID・デザイン画像であり、**顧客の氏名・住所・
電話番号・メールアドレスは含まれない**（`app/utils/mfg_product_mapping.py` と
`illustrator_vm_client.submit` で確認）。個人情報の漏えいには当たらない。

**不具合ではなく要件として扱う**（判定の根拠は 12.2 節）。`REQ-0055` の受入基準に含め、
フェーズ 5（VM 移送・閉域化）で解消する。

### 2.5 Cloud Run に載せる前に潰す必要がある不整合

| # | 内容 | 該当 |
|---|---|---|
| 1 | production イメージが**ビルドできない**。`.next/standalone` を COPY するが `output: "standalone"` 未設定 | `web/Dockerfile`, `web/next.config.ts` |
| 2 | `NEXT_PUBLIC_API_URL` はビルド時に焼き込まれる（10 箇所で参照） | `web/src/lib/api/client.ts` ほか |
| 3 | `alembic upgrade head` が API の起動 CMD に同居。複数インスタンス同時起動で競合 | `api/Dockerfile` |
| 4 | `BackgroundTasks` が 3 経路。Cloud Run はレスポンス後に CPU が絞られるため完走しない | `orders.py` / `orders_v2.py` / `manufacturing_data.py` |
| 5 | DB プールが固定（`pool_size=5, max_overflow=10` = 15 接続/インスタンス）。`db-f1-micro` の `max_connections` を超える | `api/app/database.py` |

### 2.6 移行に有利な既存の性質（確認済み）

- `manufacturing_data_service.py` は WeasyPrint を import しない（PDF は `app/utils/pdf_generator.py` に閉じている）
- `Settings.async_database_url` は `postgresql://` を前置換するだけ → **Cloud SQL の Unix ソケット URL がそのまま通る**
- `alembic/env.py` も `settings.async_database_url` を使う → migrate Job で同じ設定が効く
- `file_storage.py` の `file_path` は**バックエンド非依存の相対キー**（docstring に明記）→ **バケット名を変えても DB の書き換えが不要**
- GCS バケットは約 30MB → 複製は一瞬（`rsync` は権限不足で使えない。9.1 を参照）

---

## 3. 着手前に解消が必要な前提（ブロッカー）

### 3.1 IAM 権限が足りない

Resource Manager の `testIamPermissions` で実測した結果、`roles/editor` では次の 4 つを持っていない。

| 欠けている権限 | これが無いと |
|---|---|
| `resourcemanager.projects.setIamPolicy` | `google_project_iam_member` が全滅（SA にロールを付与できない） |
| `iam.workloadIdentityPools.create` | Workload Identity 連携プールが作れない＝ CI/CD 方式が成立しない |
| `run.services.setIamPolicy` | Cloud Run を公開できない（`allUsers` invoker を付与できない） |
| `iam.serviceAccounts.setIamPolicy` | WIF の impersonation 設定ができない |

作成系（`cloudsql.instances.create` / `run.services.create` / `compute.networks.create` /
`storage.buckets.create` / `secretmanager.secrets.create` / `artifactregistry.repositories.create` /
`cloudscheduler.jobs.create` / `serviceusage.services.enable`）は**すべて保有している**。

**依頼内容:** 両プロジェクトに `roles/owner`。渋られる場合は最小構成として次の 4 ロール。

- `roles/resourcemanager.projectIamAdmin`
- `roles/iam.workloadIdentityPoolAdmin`
- `roles/iam.serviceAccountAdmin`
- `roles/run.admin`

### 3.2 予算アラートは Owner 作業になる

`google_billing_budget` は請求先アカウントに対する権限を要する。作業者は
`gcloud billing accounts list` すら通らない（0 件が返る）ため、**Terraform の対象外**とし、
Owner にコンソールで設定してもらう。設定値は本設計の「コスト」節を使う。

---

## 4. 設計判断

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| 1 | Terraform 構成 | `infra/modules/` 共通 ＋ `infra/envs/{staging,prod}` の薄い root | 環境差分が tfvars と root に露出する。workspace 方式は差分が見えず本番を誤爆しやすい |
| 2 | Terraform state | 各プロジェクトの GCS バケットに分離（`gs://tosyo-api-stg-tfstate` / `gs://tosyo-api-504104-tfstate`） | 影響範囲を環境で切る。バケットは gcloud で手動ブートストラップ |
| 3 | Cloud SQL 接続 | **パブリック IP・承認済みネットワーク 0 件**、Cloud Run 内蔵の Cloud SQL 接続（Unix ソケット）のみ | IAM 認証で TLS トンネルを張るため直接叩ける穴は空かない。**コード変更ゼロ**。VPC が不要になる |
| 4 | 非同期処理 | **Cloud Run Job ワーカー** ＋ Cloud Scheduler（1 分毎） | Job は CPU 常時割当・タスクタイムアウト最大 24h。Cloud Run サービスの CPU スロットリング問題が原理的に起きない。**Windows 側の作業がゼロ**。VM が移送されても影響を受けない |
| 4-a | 二重処理の防止 | **行の所有権をリースで表す**（ADR-0029）。取り出しは 1 文、復旧は期限切れのみ | 復旧がワーカーの本数に依存しなくなり、排他ロックをスループットの都合に降格できる |
| 5 | フロント | Cloud Run（`output: "standalone"` ＋ 環境別イメージビルド） | Next.js の標準。実行時注入は 10 箇所の書き換えが要る |
| 6 | シークレット | Secret Manager ＋ Cloud Run の secret env。`GCS_CREDENTIALS_JSON` は廃止し ADC へ | GCP 上では鍵 JSON を持ち回る理由が消える |
| 7 | CI/CD | GitHub Actions ＋ Workload Identity 連携 | 既に `ci.yml` が GitHub Actions。鍵 JSON 不要 |
| 8 | 日次ダイジェスト cron | 当面 GitHub Actions のまま `API_BASE_URL` を差し替え | Cloud Scheduler 化は `X-Internal-Secret` を tfstate に平文で持つ問題があり、移行のクリティカルパスに載せる価値がない |
| 9 | ステージングの Illustrator | `ILLUSTRATOR_VM_BASE_URL` を空にして生成を無効化 | 本番 VM を共有すると本番のジョブキューに混ざる。VM 移送（フェーズ 5）後にステージングから繋ぐのが本筋 |
| 10 | VPC | **フェーズ 4 までは作らない。フェーズ 5（VM 移送）で追加する** | VM が個人プロジェクトにある間は VPC を作る用途がない。追加は additive で作り直しが出ない |

### 4.1 なぜ「VM 上の Python ワーカー」ではなく「Cloud Run Job」か

当初のコスト資料（`docs/gcp-deployment-cost-review.md`）は Windows VM 上でワーカーを常駐させる案だった。
これを変更する。

| | VM ワーカー（当初案） | **Cloud Run Job（採用）** |
|---|---|---|
| VM の SA スコープ変更 | 必要（`devstorage.read_only` → `cloud-platform`、stop/start を伴う） | 不要 |
| クロスプロジェクト IAM | 必要（DB・GCS へのアクセス） | 不要 |
| Windows でのプロセス常駐運用 | 必要（サービス化・自動再起動・Python 環境） | 不要 |
| VM 移送時の影響 | ワーカーごと引っ越す | `ILLUSTRATOR_VM_BASE_URL` の 1 変数のみ |
| コスト | VM に内包 | アイドル時 約 ¥600/月（概算・下記） |

当初案の根拠だった「Cloud Run はリクエスト処理中しか CPU が割り当てられない」は
**Cloud Run サービス**の話であり、**Cloud Run Job には当てはまらない**（Job は CPU 常時割当）。

### 4.2 ワーカーの設計

```
Cloud Scheduler（1 分毎）
   │ POST run.googleapis.com/v2/.../jobs/pod-admin-worker:run （OIDC）
   ▼
Cloud Run Job: pod-admin-worker（parallelism=1, taskCount=1, maxRetries=0, timeout=3600s）
   1. pg_try_advisory_lock(KEY) → 取れなければ即 exit 0
      （直列な VM を奪い合わないための降り方。**正しさの条件ではない**）
   2. リースが切れた generating を pending へ戻す
   3. loop:
        キューから 1 件取り出す（1 文で generating へ確保し、リースを打つ）
        取れなければ break
        生成する（確保済みの行を処理するだけ。ここでは確保しない）
        件数・実行時間の上限に達したら break
   4. unlock, exit 0
```

**同じ行を二度処理しないことは、行の所有権（リース）が保証している**（ADR-0029）。

- 取り出しは 1 つの UPDATE 文で「選ぶ・確保する・リースを打つ」を済ませ、**打ったリースの値を返す**。
  候補の選択に `FOR UPDATE SKIP LOCKED` を使うので、同時に取り出しても互いをブロックしない
- 結果の書き戻しは、**そのリースの値が一致する間だけ**通す。手間取っている間にリースが失効して
  別のワーカーが再確保していれば、古い結果は捨てられて記録に残る
- 復旧は「リースが切れた generating」だけを戻す。**ワーカーの本数に依存しないので単独で正しい**

`illustrator-vm` 自体が直列 1 件ずつ（最大約 300 秒）なので、ワーカーを並列化する意味はない。
VM が並列化されたら、排他ロックを外すだけで並列ワーカーへ移行できる。

## 5. 目標アーキテクチャ

### 5.1 フェーズ 4 完了時点（VM は個人プロジェクトのまま）

```
                    ┌───────── tosyo-api-504104（会社組織） ──────────┐
[外部販売サイト] ──> │ Cloud Run: pod-admin-api    1vCPU/2GiB min=0    │
[管理者ブラウザ] ──> │ Cloud Run: pod-admin-web    1vCPU/512MiB min=0  │
                    │ Cloud Run Job: pod-admin-migrate（alembic）      │
 Cloud Scheduler ──> │ Cloud Run Job: pod-admin-worker（製造データ生成）│
                    │ Cloud SQL PostgreSQL 16（パブリックIP・承認網 0）│
                    │ GCS: tosyo-pod-admin-prod                       │
                    │ Artifact Registry: pod-admin                    │
                    │ Secret Manager                                  │
                    └──────────────────┬──────────────────────────────┘
                                       │ HTTPS（公衆網・現状どおり）
                    ┌──────────────────┴── lively-transit-334610（個人・一時的）
                    │ illustrator-vm-preview  34.84.121.166:8000
                    └───────────────────────────────────────────────
```

### 5.2 フェーズ 5 完了時点（VM 移送後・最終形）

```
                    ┌───────── tosyo-api-504104（会社組織） ──────────┐
[外部販売サイト] ──> │ Cloud Run: pod-admin-api ──┐                    │
[管理者ブラウザ] ──> │ Cloud Run: pod-admin-web   │ Direct VPC egress  │
 Cloud Scheduler ──> │ Cloud Run Job: worker  ────┤                    │
                    │ Cloud SQL / GCS / AR / SM  │                    │
                    │                            ▼                    │
                    │  VPC: pod-admin-vpc                             │
                    │   └ GCE: illustrator-vm（外部IPなし・内部IPのみ）│
                    │      FW: Cloud Run のサブネットからの tcp:8000 のみ│
                    └─────────────────────────────────────────────────┘
```

`ILLUSTRATOR_VM_BASE_URL` が `http://10.x.x.x:8000` になり、**認証なし API がインターネットから消える**。
これが `REQ-0055` の中心的な受入基準にあたる。

### 5.3 主要リソースの諸元

| リソース | 本番 | ステージング |
|---|---|---|
| Cloud Run api | 1vCPU / 2GiB / min=0 / max=5 / timeout=300s | 1vCPU / 2GiB / min=0 / **max=1** |
| Cloud Run web | 1vCPU / 512MiB / min=0 / max=5 | 1vCPU / 512MiB / min=0 / max=2 |
| Cloud SQL | `db-custom-1-3840`（1vCPU/3.75GB）/ 30GiB SSD 自動拡張 / **非HA(ZONAL)** / バックアップ＋PITR 有効 / メンテ枠 日曜 03:00 JST / `deletion_protection=true` | `db-f1-micro` / 10GiB / 非HA / バックアップ有効 |
| GCS | `tosyo-pod-admin-prod`（asia-northeast1 / UBLA / 公開防止 / **180 日ライフサイクル**） | `tosyo-pod-admin-stg`（30 日ライフサイクル） |
| Artifact Registry | `pod-admin`（Docker / asia-northeast1 / クリーンアップポリシー付き） | 同左 |
| Cloud Run Job worker | timeout 3600s / Scheduler 1 分毎 | timeout 600s / **Scheduler は paused** |

**ステージングの `max-instances=1` は必須。** `db-f1-micro` の `max_connections` は既定 25 程度であり、
1 インスタンスあたり 15 接続を使うため 2 インスタンス目で枯渇する（`DB_POOL_SIZE` の環境変数化と併せて対応）。

本番も同じ計算が要る。`api max=5` × 15 ＋ worker Job ＋ migrate Job が `max_connections` に収まることを
**フェーズ 4 の前に実測で確認する**（`db-custom-1-3840` の既定値はメモリ量から算出されるため、値を仮定しない）。

### 5.4 サービスアカウント

| SA | 用途 | 主なロール |
|---|---|---|
| `pod-admin-api@` | Cloud Run api / migrate Job | `cloudsql.client`, `storage.objectAdmin`（バケット単位）, `secretmanager.secretAccessor` |
| `pod-admin-worker@` | Cloud Run Job worker | 同上 |
| `pod-admin-web@` | Cloud Run web | （なし。静的配信のみ） |
| `pod-admin-scheduler@` | Cloud Scheduler | `run.invoker`（worker Job に対して） |
| `pod-admin-deployer@` | GitHub Actions（WIF） | `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser` |

WIF の provider には **リポジトリ条件を必ず付ける**（`assertion.repository == 'Raiku-Setoyama/pod-admin'`）。
これが無いと任意の GitHub リポジトリから impersonate できてしまう。

---

## 6. Terraform 構成

```
infra/
├── modules/
│   ├── project-services/     # 必要 API の有効化
│   ├── artifact-registry/    # Docker リポジトリ＋クリーンアップポリシー
│   ├── cloud-sql/            # インスタンス・DB・ユーザー・バックアップ・PITR
│   ├── gcs/                  # バケット・ライフサイクル・IAM
│   ├── secrets/              # Secret Manager のシークレット定義
│   ├── service-accounts/     # SA とプロジェクトロール
│   ├── cloud-run-service/    # api / web で共用
│   ├── cloud-run-job/        # migrate / worker で共用
│   ├── scheduler/            # worker 起動ジョブ
│   ├── github-oidc/          # WIF プール・プロバイダ・デプロイ SA
│   └── network/              # ★フェーズ 5 で追加（VPC / サブネット / FW / Direct VPC egress）
└── envs/
    ├── staging/  { backend.tf, main.tf, variables.tf, terraform.tfvars }
    └── prod/     { backend.tf, main.tf, variables.tf, terraform.tfvars }
```

### 6.1 state のブートストラップ

Terraform 自身の state 置き場は Terraform で作れない（鶏卵）ため、gcloud で先に作る。

```bash
for P in tosyo-api-stg tosyo-api-504104; do
  gcloud storage buckets create gs://${P}-tfstate \
    --project=$P --location=asia-northeast1 \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update gs://${P}-tfstate --versioning
done
```

**state には DB パスワードが平文で入る。** バケットのアクセスを絞り、バージョニングを有効にする。

### 6.2 有効化する API

`run` / `sqladmin` / `secretmanager` / `artifactregistry` / `cloudscheduler` /
`iamcredentials` / `sts` / `cloudresourcemanager` / `compute`（フェーズ 5 で追加）

イメージのビルドは GitHub Actions で行うため `cloudbuild` は有効化しない。

### 6.3 命名規則

- Cloud Run / Job / SA: `pod-admin-<component>`（プロジェクトで環境が分かれるため env サフィックスは付けない）
- GCS: `tosyo-pod-admin-<env>`（グローバル一意が必要）
- Cloud SQL: `pod-admin`（**削除後に同名を再作成するには時間を置く必要があるため、名前を使い回さない運用にする**）
- ラベル: `app=pod-admin`, `env=prod|staging`, `managed-by=terraform`

---

## 7. コード改修一覧

| # | 対象 | 変更内容 |
|---|---|---|
| 1 | `web/next.config.ts` | `output: "standalone"` を追加 |
| 2 | `web/Dockerfile` | builder ステージに `ARG NEXT_PUBLIC_API_URL` → `ENV` で渡す |
| 3 | `api/Dockerfile` | production の CMD から `alembic upgrade head` を外し `uvicorn` のみにする。コメントの「`--reset` flag included temporarily」も除去 |
| 4 | `api/app/worker.py`（新規） | Cloud Run Job のエントリポイント。排他ロック ＋ 取り出しループ（4.2 節） |
| 4-a | `manufacturing_data.lease_expires_at`（新規列） | 生成の所有権。マイグレーション 1 本（ADR-0029） |
| 5 | `api/app/services/manufacturing_data_service.py` | `enqueue_generation` / `_restart_generation` から `background_tasks.add_task` を外し、`pending` 行を作るだけにする |
| 6 | `api/app/services/external_order_notification.py` | `enqueue_if_enabled` を同期送信に変更 |
| 7 | `api/app/main.py` | lifespan の `recover_stranded_generations` を除去（ワーカーの責務へ移す） |
| 8 | `api/app/database.py` | `pool_size` / `max_overflow` を環境変数化（`DB_POOL_SIZE` / `DB_MAX_OVERFLOW`） |
| 9 | `api/app/config.py` | `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `WORKER_POLL_INTERVAL` / `WORKER_MAX_RUNTIME_SECONDS` を追加 |
| 10 | `api/app/routers/{orders,orders_v2,manufacturing_data}.py` | `BackgroundTasks` 引数の除去に伴うシグネチャ更新 |
| 11 | 対応するテスト | `BackgroundTasks` を前提にしたテストの書き換え |
| 12 | `api/DEPLOY.md` | Railway 手順を GCP 手順に置き換え |
| 13 | `docs/00-charter/constraints.md` | インフラ・運用の記述を更新 |

### 7.1 DATABASE_URL の形

```
postgresql://pod_admin:<URLエンコード済みパスワード>@/pod_admin?host=/cloudsql/tosyo-api-504104:asia-northeast1:pod-admin
```

`Settings.async_database_url` が `postgresql+asyncpg://` に置換し、SQLAlchemy が `host` を
asyncpg へ渡す。asyncpg は `/` 始まりの host を Unix ソケットディレクトリとして解釈する。

**この経路はフェーズ 2 のステージングで実地検証する**（本番で初めて試さない）。
パスワードに URL 予約文字が入ると壊れるため、Terraform 側で URL エンコードするか、
`random_password` の `override_special` を絞る。

---

## 8. フェーズ計画

### フェーズ 0 — 前提の解消（人間の作業）

| 作業 | 担当 | 完了条件 |
|---|---|---|
| 両プロジェクトへの `roles/owner`（または代替 4 ロール）付与依頼 | Owner のいずれか | `testIamPermissions` で 4 権限が返る |
| tfstate バケットのブートストラップ | 作業者 | 2 バケットが versioning 有効で存在 |
| 予算アラート設定 | Owner | 本番・ステージングそれぞれに閾値設定 |

**フェーズ 0 が終わるまで Terraform apply は必ず失敗する。** ここを飛ばさない。

### フェーズ 1 — アプリの Cloud Run 適合改修

7 節の 1〜11 を実施。ローカルの Docker Compose で回帰確認する。
**この時点ではまだ GCP に何も作らない。**

検証項目:
- `docker build --target production` が web / api ともに成功する
- `NEXT_PUBLIC_API_URL` を build-arg で変えたイメージが、その URL を向く
- 製造データ生成が `pending` で止まり、ワーカーを手動実行すると処理される
- 受注通知メールが同期送信になっている

### フェーズ 2 — Terraform 基盤とステージング構築

`infra/` を新設し、`envs/staging` を apply する。

検証項目:
- `terraform plan` が差分ゼロで安定する（apply 冪等）
- Cloud SQL に **Unix ソケット経由で接続できる**（7.1 節の実地検証）
- migrate Job が `alembic upgrade head` を完走する
- Cloud Run api / web が `*.run.app` で応答する
- `db-f1-micro` の `max_connections` に対し `DB_POOL_SIZE` が収まっている

### フェーズ 3 — CI/CD 整備とステージング動作確認

- `github-oidc` モジュールを apply
- `.github/workflows/` に `terraform.yml` / `deploy-staging.yml` / `deploy-prod.yml` を追加
- main マージ → ステージングへ自動デプロイが通ることを確認
- 業務シナリオのスモークテスト（ログイン、受注一覧、発注、配送、請求書 PDF、外部 API v1/v2、チャット）

**「動作確認が取れた」の判定はここ。** ここを通らないうちは本番に進まない。

### フェーズ 4 — 本番インフラ構築とカットオーバー

9 節の手順に従う。

### フェーズ 5 — `illustrator-vm` の移送と閉域化

1. `lively-transit-334610` で `illustrator-vm-preview` のマシンイメージを作成
2. **そのマシンイメージに対して**、`tosyo-api-504104` 側のプリンシパルへ `roles/compute.imageUser` を付与する
   （付与作業は `lively-transit-334610` 側＝`raiku6019@gmail.com` で行う）
3. `infra/modules/network/` を追加し、`pod-admin-vpc` / サブネット / FW を作成
4. マシンイメージから **外部 IP なし**で VM を起動
5. **Adobe Illustrator のライセンス認証を確認**（ハードウェア紐付けの場合は再サインインが要る）
6. Cloud Run api / worker に Direct VPC egress を設定し、`ILLUSTRATOR_VM_BASE_URL` を内部 IP へ
7. 旧 VM を停止 → 動作確認 → 削除
8. `REQ-0055` の受入基準をすべて満たし、`done` にする

**リスク:** Adobe のライセンス認証が移送先で通らない可能性がある。通らなければ
新規 VM に Illustrator を再インストールする（手順は同じで、5 の代わりに再インストール）。

### フェーズ 6 — 旧環境の廃止と運用整備

- Railway プロジェクトの停止・削除
- Vercel プロジェクトの停止・削除
- `gs://pod-admin-prod`（旧バケット）の削除（複製完了とバックアップ確認の後）
- Cloud Logging のログベースアラート（5xx 率、ワーカーの失敗）
- Cloud Monitoring のアップタイムチェック（`/health`）
- Cloud SQL バックアップからの復旧リハーサル

---

## 9. 本番カットオーバー手順とロールバック

### 9.1 事前準備（前日まで）

1. 外部販売サイト運営者へ、**新 API URL とメンテナンス枠**を通知して合意を取る
2. `envs/prod` を apply（Cloud SQL / GCS / Secret Manager / Cloud Run を空の状態で構築）
3. 本番イメージをビルドして Artifact Registry へ push
4. 旧バケットからファイルを複製する（初回・全量）。**`rsync` は使えない** —
   `key.json` のサービスアカウントは `storage.buckets.get` を持たないので、
   `gcloud storage cp -r` で一度ローカルへ降ろす（`infra/README.md`）
5. Railway の `pg_dump` をリハーサルし、Cloud SQL への restore を一度通しておく

### 9.2 当日（メンテナンス枠）

| # | 手順 | 戻せるか |
|---|---|---|
| 1 | メンテナンス告知。外部販売サイト側の送信を停止してもらう | ○ |
| 2 | Railway API を停止（新規書き込みを止める） | ○ |
| 3 | `pg_dump --no-owner --no-acl`（Railway）→ Cloud SQL へ restore | ○ |
| 4 | ファイルの複製（30MB なので全件やり直してよい。`infra/README.md`） | ○ |
| 5 | migrate Job を実行（既に head なら no-op。整合確認を兼ねる） | ○ |
| 6 | Cloud Run api / web をデプロイ（シークレット・環境変数を確定） | ○ |
| 7 | スモークテスト（`/health`、ログイン、受注一覧、請求書 PDF、外部 API v1/v2 の疎通） | ○ |
| — | **★ 判断ポイント。ここまでは Railway/Vercel を再開するだけで戻せる** | |
| 8 | `manufacturer-daily-digest.yml` の `API_BASE_URL` を新 URL へ | △ |
| 9 | 外部販売サイトへ新 URL の適用を依頼 → 疎通確認 | **×** |
| 10 | Vercel を停止（または新 URL へリダイレクト） | △ |
| 11 | Cloud Scheduler（worker）を有効化。監視・アラートを確認 | △ |

**手順 9 以降は片道である。** 外部販売サイトが新 URL を向いた後の注文は Cloud SQL にしか存在しないため、
切り戻すには差分の移送が要る。**判断は手順 7 の結果を見て、手順 8 に入る前に行う。**

### 9.3 ロールバック

| 時点 | 手順 |
|---|---|
| 手順 7 まで | Railway API を再開する。Cloud SQL のデータは破棄してよい（Railway 側が正） |
| 手順 8〜10 | `API_BASE_URL` を戻す。外部販売サイトに旧 URL への差し戻しを依頼。**Cloud SQL に入った新規注文を Railway へ手作業で移す必要がある** |
| 手順 11 以降 | 原則として前進復旧。Cloud SQL の PITR で時点復旧する |

### 9.4 コールドスタートの扱い

Cloud Run（api）を `min-instances=0` で運用すると、外部販売サイトからの受注リクエストが
コールドスタートを踏む。**外部販売サイト側のタイムアウトが 10 秒未満、またはリトライしない実装なら
`min-instances=1`（+ 約 ¥6,000/月）にする。** 事前に相手方へ確認する。

---

## 10. コスト

### 10.1 フェーズ 4 完了時点（VM は個人プロジェクト）

| 環境 | 内訳 | ¥/月 |
|---|---|---|
| 本番（会社請求） | Cloud Run api 3,433 ＋ web 3,056 ＋ Cloud SQL 11,434 ＋ GCS 〜3,717 ＋ Job ワーカー 600〜2,000 | **22,200〜23,600** |
| ステージング（会社請求） | 見積もりどおり | **約 2,600** |
| **会社請求 合計** | | **約 25,000** |
| illustrator-vm（**個人請求 `01AB65-…`**） | e2-standard-2 24/7 ＋ Windows ライセンス ＋ 100GB | **23,099** |

GCS の 3,717 は 1TB を上限とした見積もり。**実測 30MB のため当面はほぼゼロ**である。

Cloud Run Job ワーカーの概算根拠: 1vCPU/2GiB、Cloud Scheduler が 1 分毎に起動し、
キューが空なら約 3 秒で終了する前提。43,200 回/月 × 3 秒 ≒ 130,000 vCPU 秒 → 約 ¥600/月。
処理が走る時間だけ上乗せされる（24/7 常駐なら約 ¥11,000/月なので、**空なら即終了する実装が費用面で重要**）。

### 10.2 フェーズ 5 完了時点（VM 移送後・最終形）

| 環境 | ¥/月 |
|---|---|
| 本番（VM 込み） | 約 45,300〜46,700 |
| ステージング | 約 2,600 |
| **会社請求 合計** | **約 48,000** |
| 個人請求 | **0** |

元の見積もり ¥47,284 とほぼ一致する（差分は Cloud Run Job ワーカー分）。

**報告事項:** フェーズ 4 と 5 の間は、月額 ¥23,099 が個人の請求先アカウントに乗り続ける。
社内で認識を揃えておく必要がある。

---

## 11. 管理外資産とリスク

### 11.1 Terraform の管理外に残るもの

| 資産 | 期間 | 理由 |
|---|---|---|
| `lively-transit-334610` の `illustrator-vm-preview` | フェーズ 5 まで | 別アカウント・別請求先のため |
| `gs://pod-admin-prod`（旧バケット） | フェーズ 6 まで | 同上 |
| 予算アラート | 恒久 | 作業者に請求先アカウントの権限がない |
| Adobe Illustrator のライセンス | 恒久 | GCP 請求外。別途予算化が必要 |

### 11.2 リスク一覧

| # | リスク | 影響 | 対応 |
|---|---|---|---|
| 1 | IAM 権限が付与されない | **着手できない** | フェーズ 0 で解消。代替ロール案を提示済み |
| 2 | Adobe ライセンスが移送先で通らない | フェーズ 5 が延びる | 再インストールにフォールバック。旧 VM は認証成功まで消さない |
| 3 | asyncpg + Unix ソケットが想定どおり動かない | 設計変更 | フェーズ 2 のステージングで実地検証。駄目なら `cloud-sql-python-connector` に切り替え |
| 4 | 外部販売サイト側の URL 変更調整が長引く | カットオーバーが延びる | フェーズ 3 完了時点で先方に着手依頼 |
| 5 | コールドスタートで外部注文を取りこぼす | 受注欠損 | 先方のタイムアウト値を事前確認。必要なら `min-instances=1` |
| 6 | `db-f1-micro` の接続枯渇 | ステージングが不安定 | `DB_POOL_SIZE` 環境変数化 ＋ `max-instances=1` |
| 7 | 認証なし API が移行完了まで公開されたまま | 第三者によるジョブ投入・成果物の窃取 | `REQ-0055` で解消。**それまでの期間はリスクを受容する判断である**（依頼者決定） |
| 8 | tfstate に DB パスワードが平文で入る | 漏洩時の影響 | バケットのアクセスを絞る。バージョニング有効化 |

---

## 12. 起票（REQ / ADR）

AGENTS.md の規約に従い、`docs/intake-2026-08-27` ブランチで以下を起票した。

| ID | 種別 | タイトル | area | priority / status | depends_on |
|---|---|---|---|---|---|
| `REQ-0052` | 要件 | 非同期処理（製造データ生成・受注通知メール）をコンテナ実行基盤で完走する形に改める | `common` | must / not-started | — |
| `REQ-0053` | 要件 | インフラを Terraform で管理し、ステージング環境を GCP に構築する | `common` | must / not-started | REQ-0052 |
| `REQ-0054` | 要件 | 本番環境を Railway / Vercel から GCP へ移行する | `common` | must / not-started | REQ-0053 |
| `REQ-0055` | 要件 | 製造データ生成VMを会社組織のGCPプロジェクトへ移し、認証なしでインターネットから到達できない状態にする | `common` | must / not-started | REQ-0054 |
| `ADR-0026` | 決定 | GCP 移行の全体構成（実行基盤・DB 接続方式・非同期処理の置き場） | `common` | accepted | — |
| `ADR-0027` | 決定 | Terraform のディレクトリ構成と state の管理方法 | `common` | accepted | — |
| `ADR-0028` | 決定 | GCP へのデプロイ方式（GitHub Actions と Workload Identity 連携） | `common` | accepted | — |

`priority: must` の根拠は、いずれも依頼者の発言をそのまま引用できる（PR 本文に記載）。
**確定するのは PR のマージであり、ここに書いたのは提案である。**

### 12.1 なぜ REQ を 4 本に分けるか

AGENTS.md「作業の単位」に従い、**顧客との合意の単位**で切っている。

- `REQ-0052` はインフラ抜きでも独立して価値がある（Cloud Run に載せる前提を整える）
- `REQ-0053` はステージングという成果物で完結する
- `REQ-0054` は「本番が GCP で動いている」という検収可能な状態
- `REQ-0055` は「会社組織への集約とセキュリティ是正」という別の目的を持つ

「実装が大きいから」ではなく、**それぞれ別の完了判定を持つから**分けている。

### 12.2 認証なし API の公開を「不具合」ではなく「要件」にした理由

2.4 節で確認した露出は、当初 `BUG-XXXX` として起票する想定だった。**これを撤回した。**

AGENTS.md「不具合か、仕様変更か」の判定は「**既存の受入基準に違反しているか**」であり、
違反しているなら**その受入基準を引用できなければならない**。実際に確認した結果:

- `nfr.md` のセキュリティ節が定めているのは pod-admin 自身の認証方式であり、外部 VM の話ではない
- `nfr.md` の法令・規約節（個人情報）は、**VM に PII が流れていない**ため当たらない
  （送信内容は商品種別・サイズ・注文ID・デザイン画像のみ。`mfg_product_mapping.py` と
  `illustrator_vm_client.submit` で確認）
- `constraints.md` はむしろ illustrator-vm の認証を「任意ヘッダ」と**現状のまま記録している**

**引用できる受入基準が存在しない。** 同じ形の指摘（本番で認証なしに公開されているデバッグ用
エンドポイント）が `REQ-0040` という**要件**として起票されている前例もあり、`nfr.md` 自身が
同種の発見を「ADR/要件化して対応方針を決めるべき」と書いている。

**商売の観点でも要件が正しい。** 不具合として出すと「瑕疵担保の対象」を意味してしまう。
書いていない約束を新たに求められている話なので、要件である。

対応内容は `REQ-0055` と完全に重なるため、別 ID を立てず、**`REQ-0055` のタイトルと受入基準に
セキュリティ是正を明示した**（「認証なしでインターネットから到達できない状態にする」）。

## 13. 未決事項

| # | 内容 | 判断が要るタイミング |
|---|---|---|
| 1 | Cloud Run（api）を `min-instances=1` にするか（+ 約 ¥6,000/月） | フェーズ 4 の前。外部販売サイトのタイムアウト値の確認が先 |
| 2 | 独自ドメインの導入時期 | フェーズ 6 以降。導入すると外部販売サイトへの URL 通知が 2 回発生する |
| 3 | 日次ダイジェストを Cloud Scheduler へ移すか | フェーズ 6 以降 |
| 4 | ステージング用の illustrator スタブを立てるか | フェーズ 5 完了後、ステージングから移送後の VM に繋げれば不要になる |
| 5 | Cloud SQL の 1 年 CUD 適用（vCPU + RAM 25% オフ） | 本番稼働が安定した後 |
