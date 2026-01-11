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
