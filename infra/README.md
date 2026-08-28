# infra — GCP のインフラ定義（Terraform）

POD Admin の GCP リソースをコードで管理する。設計の詳細は
`docs/superpowers/specs/2026-08-27-gcp-migration-design.md`、
判断の記録は `docs/02-decisions/ADR-0026`〜`ADR-0028`。

## 構成

```
infra/
├── modules/       環境をまたいで共用する部品
├── envs/
│   └── staging/   ステージング（tosyo-api-stg）
└── scripts/       state バケットのブートストラップ
```

**環境ごとにプロジェクトが分かれる。** そのためリソース名に環境サフィックスは付けない
（`pod-admin-api` はステージングにも本番にも 1 つずつ存在する）。
グローバルに一意である必要がある GCS バケットだけ `tosyo-pod-admin-<env>` とする。

## 初回の手順

### 1. state バケットを作る

Terraform 自身の state 置き場は Terraform で作れない（鶏卵）ので、ここだけ手で作る。

```bash
./scripts/bootstrap-state-bucket.sh tosyo-api-stg
```

**state には DB のパスワードが平文で入る。** バージョニングを有効にし、
バケットへのアクセスは IAM で絞る。

### 2. apply する

```bash
cd envs/staging
terraform init
terraform apply
```

Cloud Run のサービスと Job は、**Google 公開のサンプルイメージで作られる。**
実物のイメージはデプロイ側（GitHub Actions、または下記の手動手順）が入れる。
Terraform はイメージのタグを `ignore_changes` で無視するので、
デプロイのたびに差分が出ることはない。

### 3. イメージを作って入れる

```bash
cd envs/staging
REGISTRY=$(terraform output -raw artifact_registry_url)
API_URL=$(terraform output -raw next_public_api_url)
gcloud auth configure-docker "${REGISTRY%%/*}"

# API（と migrate / worker Job は同じイメージ）
docker buildx build --platform linux/amd64 --target production \
  -t "$REGISTRY/api:latest" --push ../../../api

# 管理画面。API の向き先はビルド時に焼き込まれる
docker buildx build --platform linux/amd64 --target production \
  --build-arg "NEXT_PUBLIC_API_URL=$API_URL" \
  -t "$REGISTRY/web:latest" --push ../../../web

gcloud run deploy pod-admin-api --image "$REGISTRY/api:latest" --region asia-northeast1
gcloud run deploy pod-admin-web --image "$REGISTRY/web:latest" --region asia-northeast1
gcloud run jobs update pod-admin-migrate --image "$REGISTRY/api:latest" --region asia-northeast1
gcloud run jobs update pod-admin-worker  --image "$REGISTRY/api:latest" --region asia-northeast1
```

### 4. マイグレーションを流す

```bash
gcloud run jobs execute pod-admin-migrate --region asia-northeast1 --wait
```

**API イメージの起動コマンドにマイグレーションは含まれていない。**
複数インスタンスが同時に起動すると alembic が競合して起動そのものが壊れるため、
独立した Job として流す（`api/Dockerfile` のコメントを参照）。

## Terraform が管理しないもの

| もの | 誰がやるか | なぜ |
|---|---|---|
| state バケット | `scripts/bootstrap-state-bucket.sh` | 鶏卵 |
| Cloud Run のイメージタグ | デプロイ（CI / gcloud） | apply のたびに巻き戻るため |
| `sendgrid-api-key` の中身 | 人間（`gcloud secrets versions add`） | 値をリポジトリにも state にも置かない |
| 予算アラート | プロジェクト所有者 | 請求先アカウントの権限が要る |

## 設定の依存関係で気をつけること

- **`api_max_instances × (db_pool_size + db_max_overflow)` が `db_max_connections` に収まること。**
  worker Job と migrate Job のぶんも足して数える。`terraform.tfvars` に計算を書いてある
- **ワーカー Job のタイムアウトは直接指定しない。** `worker_max_runtime_seconds` から
  `main.tf` の `locals` が導出する。先に殺されると、生成中の行がリース期限まで宙吊りになる
- `local.generation_worst_case_seconds` は `api/app/config.py` の
  `Settings.generation_worst_case_seconds` の写しである。`ILLUSTRATOR_VM_*` を変えたら両方直す

## SendGrid の鍵を入れる

Terraform はシークレットの入れ物と `REPLACE_ME` というプレースホルダだけを作る。
**Secret Manager は空のペイロードを受け付けない**ため、「未設定」を空文字で表せない。

プレースホルダのままでもアプリは起動し、業務フローも壊れない
（送信系はすべて例外を握って `False` を返す）。ログに認証エラーが残るだけである。

実物の鍵はコマンドで足す。Cloud Run は `latest` を見るので、再デプロイは要らない。

```bash
printf '%s' "SG.xxxxx" | gcloud secrets versions add sendgrid-api-key \
  --project=tosyo-api-stg --data-file=-
```

Terraform は追加したバージョンを `ignore_changes` で無視するので、
以後の `apply` でプレースホルダに戻ることはない。
