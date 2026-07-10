# Railway デプロイ手順

## 前提条件

- Railway アカウント
- Railway CLI (`brew install railway` または `npm install -g @railway/cli`)

## デプロイ手順

### 1. Railway にログイン

```bash
railway login
```

### 2. プロジェクト作成

```bash
cd api
railway init
```

### 3. PostgreSQL 追加

Railway Dashboard で:
1. プロジェクトを開く
2. 「+ New」→「Database」→「PostgreSQL」

### 4. 環境変数設定

**方法A: CLI**
```bash
railway variables --set SECRET_KEY="$(openssl rand -hex 32)"
railway variables --set DEBUG="false"
railway variables --set CORS_ORIGINS='["https://your-frontend.railway.app"]'
```

**方法B: Dashboard（推奨）**

Railway Dashboard → プロジェクト → Variables タブで以下を設定:

| 変数名 | 値 |
|--------|-----|
| `SECRET_KEY` | `openssl rand -hex 32` で生成した値 |
| `DEBUG` | `false` |
| `CORS_ORIGINS` | `["https://your-frontend.railway.app"]` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |

### 5. デプロイ

```bash
railway up
```

### 6. 動作確認

```bash
# ドメイン確認
railway domain

# ヘルスチェック
curl https://<your-app>.railway.app/health

# API ドキュメント
open https://<your-app>.railway.app/api/v1/docs
```

## ファイル永続化（GCS）

Railway のローカルディスクは**再デプロイ/再起動で消える**ため、本番では製造データ
（.ai/.pdf）・チャット添付・出荷ファイルを Google Cloud Storage（GCS）に永続化する。
`GCS_BUCKET` を設定すると全 `FileStorage` が GCS 経由になり、未設定ならローカル保存を
継続する（既定・挙動不変）。アクセスはサーバ経由（`get()` で bytes 取得）のため、バケットは
非公開のままでよく、署名URLも不要。

### 1. GCS バケット作成

- リージョン: `asia-northeast1`（illustrator-vm と同一）
- アクセス制御: Uniform bucket-level access
- 公開設定: 非公開（Public access prevention: on）

```bash
gcloud storage buckets create gs://<your-bucket> \
  --location=asia-northeast1 \
  --uniform-bucket-level-access \
  --public-access-prevention
```

### 2. サービスアカウント作成 → バケットに権限付与

当該バケットに `roles/storage.objectAdmin` を付与する（バケット単位でスコープ）。

```bash
gcloud iam service-accounts create pod-admin-storage \
  --display-name="pod-admin GCS storage"

gcloud storage buckets add-iam-policy-binding gs://<your-bucket> \
  --member="serviceAccount:pod-admin-storage@<project>.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### 3. JSON 鍵を作成し Railway に設定

```bash
gcloud iam service-accounts keys create key.json \
  --iam-account=pod-admin-storage@<project>.iam.gserviceaccount.com
```

Railway Dashboard → プロジェクト → Variables タブで以下を設定 → 再デプロイ:

| 変数名 | 値 |
|--------|-----|
| `GCS_BUCKET` | 作成したバケット名（例: `pod-admin-prod`） |
| `GCS_CREDENTIALS_JSON` | `key.json` の中身（JSON 全体を1行で貼り付け） |
| `GCS_PREFIX` | 任意の名前空間（例: `prod`。未設定可） |

> `GCS_CREDENTIALS_JSON` が空の場合は ADC（Application Default Credentials）へ
> フォールバックする（GCE / ワークロードID 環境向け）。Railway は GCP ワークロードID
> 非対応のため、鍵 JSON をシークレットとして保持する。

### 4. ローカル開発

`GCS_BUCKET` を空のままにすればローカル保存（`UPLOAD_DIR`）を継続する。GCS を検証したい
場合のみ `GCS_BUCKET` を設定する（認証は `GCS_CREDENTIALS_JSON` か `gcloud auth
application-default login` による ADC）。

## 再デプロイ

コード変更後:

```bash
cd api
railway up
```

## ログ確認

```bash
railway logs
```
