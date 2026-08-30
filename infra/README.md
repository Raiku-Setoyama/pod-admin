# infra — GCP のインフラ定義（Terraform）

POD Admin の GCP リソースをコードで管理する。設計の詳細は
`docs/superpowers/specs/2026-08-27-gcp-migration-design.md`、
判断の記録は `docs/02-decisions/ADR-0026`〜`ADR-0028`、`ADR-0030`〜`ADR-0032`。

## 構成

```
infra/
├── modules/
│   ├── stack/     アプリ 1 環境ぶんの構成（下記）
│   └── その他/     汎用の GCP ラッパー（cloud-run-service, cloud-sql, ...）
├── envs/
│   ├── staging/   ステージング（tosyo-api-stg）
│   └── prod/      本番（tosyo-api-504104）
└── scripts/       state バケットのブートストラップ
```

**`modules/stack/` がアプリを知っている唯一の層である。** その下の `modules/*` は
汎用の GCP ラッパーで、POD Admin のことを何も知らない。
「api と worker と migrate が同じイメージで動く」「`CORS_ORIGINS` は JSON で渡す」
といった知識はすべて `stack` に集める。

**`envs/<env>/` は値だけを持つ。** そのため
`diff infra/envs/staging/main.tf infra/envs/prod/main.tf` が、そのまま
**「ステージングと本番の違い」の一覧**になる。ここを環境ごとに複製しない（ADR-0027）。

**環境ごとにプロジェクトが分かれる。** そのためリソース名に環境サフィックスは付けない
（`pod-admin-api` はステージングにも本番にも 1 つずつ存在する）。
グローバルに一意である必要がある GCS バケットだけ `tosyo-pod-admin-<env>` とする。

## 初回の手順

### 1. state バケットを作る

Terraform 自身の state 置き場は Terraform で作れない（鶏卵）ので、ここだけ手で作る。

```bash
./scripts/bootstrap-state-bucket.sh tosyo-api-stg      # ステージング
./scripts/bootstrap-state-bucket.sh tosyo-api-504104   # 本番
```

**state には DB のパスワードが平文で入る。** バージョニングを有効にし、
バケットへのアクセスは IAM で絞る。

### 2. apply する

```bash
cd envs/staging   # または envs/prod
terraform init
terraform apply
```

Cloud Run のサービスと Job は、**Google 公開のサンプルイメージで作られる。**
実物のイメージはデプロイ側（GitHub Actions、または下記の手動手順）が入れる。
Terraform はイメージのタグを `ignore_changes` で無視するので、
デプロイのたびに差分が出ることはない。

### 3. 最初のイメージを入れる

**2 回目以降は手で入れない。** 反映はワークフローがやる（下記「デプロイ」）。
ここが要るのは、**Cloud Run のサービスがまだサンプルイメージで動いている初回だけ**である。

```bash
cd envs/staging   # または envs/prod
REGISTRY=$(terraform output -raw artifact_registry_url)
API_URL=$(terraform output -raw next_public_api_url)
TAG=$(git rev-parse HEAD)
gcloud auth configure-docker "${REGISTRY%%/*}"

# API（migrate / worker Job も同じイメージ）
docker buildx build --platform linux/amd64 --target production \
  -t "$REGISTRY/api:$TAG" --push ../../../api

# 管理画面。API の向き先はビルド時に焼き込まれる
docker buildx build --platform linux/amd64 --target production \
  --build-arg "NEXT_PUBLIC_API_URL=$API_URL" \
  -t "$REGISTRY/web:$TAG" --push ../../../web

# 順序は deploy.yml と同じ。マイグレーションが先（ADR-0028）
gcloud run jobs update pod-admin-migrate --image "$REGISTRY/api:$TAG" --region asia-northeast1
gcloud run jobs execute pod-admin-migrate --region asia-northeast1 --wait
gcloud run deploy pod-admin-api --image "$REGISTRY/api:$TAG" --region asia-northeast1
gcloud run deploy pod-admin-web --image "$REGISTRY/web:$TAG" --region asia-northeast1
gcloud run jobs update pod-admin-worker --image "$REGISTRY/api:$TAG" --region asia-northeast1
```

**タグに `latest` を使わない。** 動いているリビジョンからコミットが辿れなくなる。

**API イメージの起動コマンドにマイグレーションは含まれていない。**
複数インスタンスが同時に起動すると alembic が競合して起動そのものが壊れるため、
独立した Job として流す（`api/Dockerfile` のコメントを参照）。

## デプロイ

手順の本体は `.github/workflows/deploy.yml` にあり、環境ごとの呼び出し側から使う。
**契機が環境で違う**（ADR-0028）。

| 環境 | ワークフロー | 契機 |
|---|---|---|
| ステージング | `deploy-staging.yml` | `main` へのマージで**自動** |
| 本番 | `deploy-prod.yml` | **手動実行のみ**（`deploy-prod` と入力して確認する） |

**本番は `main` への push では動かない。** 取り違えの事故が「反映されない」で
済まないため（`deploy.yml` は最初に migrate Job を流すので本番のスキーマが動く）、
呼び出し側に確認の入力を置いている。

```
build api → build web → migrate Job 実行 → api 反映 → web 反映 → worker のイメージを揃える → 疎通確認
```

- 認証は Workload Identity 連携。**鍵 JSON は存在しない**
- イメージのタグはコミット SHA。動いているリビジョンからコミットが一意に辿れる
- `NEXT_PUBLIC_API_URL` はワークフローに書かず、デプロイ済みの API から引く

ワークフローに書く 2 つの値は `terraform output` から取れる。

```bash
cd envs/staging   # または envs/prod
terraform output -raw github_actions_workload_identity_provider
terraform output -raw github_actions_service_account
```

**`terraform plan` / `apply` は CI では動かさない**（ADR-0031）。
差分確認に state と Secret Manager の読み取りが要り、それは DB パスワードを
読める権限と等しいためである。CI がやるのは `fmt` と `validate` だけ
（`scripts/terraform-check.sh`）。

そのため運用は次の順になる。**Pull Request は適用済みの構成を記録するもの**である。

1. 手元で `terraform apply` まで済ませる
2. `terraform plan -detailed-exitcode` が差分なしを返すことを確認する
3. その結果を添えて Pull Request を出す

## データの移送（カットオーバー）

`scripts/migrate-data.sh` が移送の道具である。**当日その場で手順を組み立てない。**

**前日までに `docker pull postgres:17-alpine` を済ませる**（400MB 超。当日に引くと待ち時間になる）。

### 1. 移送元のダンプを取る（**人間が手元で行う**）

Railway の Postgres には TCP プロキシが無く、外から接続できない。
**ダンプの取得は依頼者が手元で行い、ファイルを受け渡す**（REQ-0054 で決めた）。
このリポジトリから移送元へ接続する経路は存在しない。

```bash
./scripts/migrate-data.sh dump "$RAILWAY_DATABASE_URL" prod.sql
```

**`pg_dump` を手で叩かず、この script を通す。** 必要なオプションが決まっており、
**手で打つとパスワードが `ps` に出る**（script は接続情報を環境変数へ分解する）。
`psql` / `pg_dump` が入っていない環境では docker で動く。

やむを得ず直接叩く場合、**次の 3 つは必須である。**

| オプション | 無いとどうなるか |
|---|---|
| `--no-owner` | 移送先に Railway のロールが無く、所有者の付け替えで restore が落ちる |
| `--no-acl` | 同上。権限の付与先が存在しない |
| `--format=plain` | `restore` と `counts-dump` がテキスト形式を前提にしている |

そのときも `PGPASSWORD` などに逃がし、URL をコマンド行に置かないこと。

### 2. 移送先へ流し込む

```bash
cloud-sql-proxy --port 5434 tosyo-api-504104:asia-northeast1:pod-admin &

./scripts/migrate-data.sh counts-dump prod.sql   > src.txt   # 移送元の件数（DB に繋がない）
./scripts/migrate-data.sh reset   "$DST_URL"                 # **破壊的**
./scripts/migrate-data.sh restore "$DST_URL" prod.sql        # **破壊的**
./scripts/migrate-data.sh counts  "$DST_URL"     > dst.txt
./scripts/migrate-data.sh compare src.txt dst.txt            # 差があれば異常終了
```

**移送元の件数はダンプそのものから数える**（`counts-dump`）。移送元に接続できない
からでもあるが、そのほうが正確でもある。理由は `migrate-data.sh` の
`cmd_counts_dump` のコメントを参照。

- **`reset` は必ず実行する。** 移送先には既にスキーマが入っており
  （REQ-0054 PR 1 で migrate Job を流したため）、`pg_dump` の `CREATE TABLE` が衝突する。
  「今どうなっているか」で分岐せず、常に同じ状態から始める
- **破壊的な操作は「許可した宛先」でしか動かない。** Cloud SQL Auth Proxy 越し
  （ループバック）で、かつ繋がった先が `pod_admin/pod_admin` であることを
  **サーバに問い合わせて**確かめ、最後に人間へ確認を求める。
  移送元の Railway は `railway/postgres` なので、ホスト名でも IP でも必ず止まる。
  **除外ではなく許可にしてある** — 除外は空振りしたときに通ってしまい、
  空文字を渡すと `PG*` の既定接続（`railway run` の下では移送元そのもの）に落ちる
- **突合は `compare` にやらせる。** 枠の終わりに 2 画面を見比べる作業にしない
  （`counts-dump` と `counts` の出力が一致することは検証済み）
- `alembic_version` はダンプに含まれるので、移送後の migrate Job は no-op になる。
  **それでも流す。** スキーマが揃っていることの確認を兼ねる
- `restore` は `--single-transaction` で流し、最後に `VACUUM ANALYZE` する。
  **統計が無いまま動作確認に入ると、「壊れている」のか「統計がまだ無い」のかを
  区別できない。** その確認が、後戻りできない手順 8 の判断材料になる

ファイルは旧バケット（個人プロジェクト `lively-transit-334610`）から複製する。
**`gcloud storage rsync` は使えない**（`key.json` のサービスアカウントは
オブジェクトを読めるが `storage.buckets.get` を持たない）。一度ローカルへ降ろす。

```bash
CLOUDSDK_CONFIG=$(mktemp -d) gcloud auth activate-service-account --key-file=../key.json
gcloud storage cp -r gs://pod-admin-prod/prod /tmp/stage/     # 旧 → ローカル（読み取りのみ）
gcloud storage rsync -r /tmp/stage gs://tosyo-pod-admin-prod  # ローカル → 新
```

**旧バケットを宛先にしない。** 約 30MB なので、当日の差分取り込みも全件やり直してよい。

## Terraform が管理しないもの

| もの | 誰がやるか | なぜ |
|---|---|---|
| state バケット | `scripts/bootstrap-state-bucket.sh` | 鶏卵 |
| Cloud Run のイメージタグ | デプロイ（CI / gcloud） | apply のたびに巻き戻るため |
| `terraform apply` そのもの | 作業者の手元 | CI に state と機密の読み取り権限を渡さないため（ADR-0031） |
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
  --project=tosyo-api-stg --data-file=-       # 本番は --project=tosyo-api-504104
```

**本番では必ず実物を入れる。** ステージングと違い、配送通知とメーカー向けダイジェストが
実際の宛先に届かなくなる。プレースホルダのままでも例外は握られるので、
**画面上は成功したように見える。**

Terraform は追加したバージョンを `ignore_changes` で無視するので、
以後の `apply` でプレースホルダに戻ることはない。
