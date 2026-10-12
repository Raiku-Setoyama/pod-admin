# infra — GCP のインフラ定義（Terraform）

POD Admin の GCP リソースをコードで管理する。設計の詳細は
`docs/superpowers/specs/2026-08-27-gcp-migration-design.md`、
判断の記録は `docs/02-decisions/ADR-0026`〜`ADR-0028`、`ADR-0030`〜`ADR-0032`。

## 構成

```
infra/
├── modules/
│   ├── stack/     アプリ 1 環境ぶんの構成（下記）
│   ├── manufacturing-monitoring/  製造データ生成の監視とアラート（本番だけ）
│   └── その他/     汎用の GCP ラッパー（cloud-run-service, cloud-sql, ...）
├── envs/
│   ├── staging/   ステージング（tosyo-api-stg）
│   └── prod/      本番（tosyo-api-504104）
└── scripts/       state バケットのブートストラップ
```

**`modules/stack/` は「アプリ 1 環境ぶんの構成」を持つ層である。**
その下の `modules/*` は汎用の GCP ラッパーで、POD Admin のことを何も知らない。
「api と worker と migrate が同じイメージで動く」「`CORS_ORIGINS` は JSON で渡す」
といった知識はすべて `stack` に集める。

**例外は `modules/manufacturing-monitoring/` である。** 本番だけが必要とする構成は、
`envs/prod/` から直接呼んでよい。判断と、なぜ `stack` のトグルにしなかったかは **ADR-0036**。

**`envs/<env>/` は値だけを持つ**（上の例外を除く）。そのため
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
./scripts/migrate-data.sh dump "$RAILWAY_DATABASE_URL" ~/pod-admin-dump/prod.sql
```

**`railway ssh` を経由して取ったダンプは改行が CRLF になる**（擬似端末が割り当てられるため）。
**取り直しても同じになる**ので、`normalize` で直してから渡す。

```bash
./scripts/migrate-data.sh normalize ~/pod-admin-dump/prod.sql ~/pod-admin-dump/prod-lf.sql
```

以降は `prod-lf.sql` のほうを使う。`counts-dump` は CRLF を拒否するが、
**そのエラーメッセージがこのコマンドを名指しする**ので、覚えておく必要はない。

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

# 移送先の接続 URL は Secret Manager から組み立てる。**手で書かない。**
# Terraform が書いた database-url は Cloud Run 用の unix ソケット形式なので、
# そのままでは proxy 越しに使えない。組み替えは dst-url がやる。
DST_URL=$(./scripts/migrate-data.sh dst-url tosyo-api-504104)

DUMP=~/pod-admin-dump/prod-lf.sql   # **リポジトリの外**。normalize を通したほう
./scripts/migrate-data.sh counts-dump "$DUMP"    > src.txt   # 移送元の件数（DB に繋がない）
./scripts/migrate-data.sh reset   "$DST_URL"                 # **破壊的**
./scripts/migrate-data.sh restore "$DST_URL" "$DUMP"         # **破壊的**
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
  区別できない。** その確認が、後戻りできない切替に進むかどうかの判断材料になる

ファイルは旧バケット（個人プロジェクト `lively-transit-334610`）から複製する。
**`gcloud storage rsync` は使えない**（`key.json` のサービスアカウントは
オブジェクトを読めるが `storage.buckets.get` を持たない）。一度ローカルへ降ろす。

```bash
CLOUDSDK_CONFIG=$(mktemp -d) gcloud auth activate-service-account --key-file=../key.json
gcloud storage cp -r gs://pod-admin-prod/prod /tmp/stage/     # 旧 → ローカル（読み取りのみ）
gcloud storage rsync -r /tmp/stage gs://tosyo-pod-admin-prod  # ローカル → 新
```

**旧バケットを宛先にしない。** 約 30MB なので、当日の差分取り込みも全件やり直してよい。

## 製造データ生成を手動で動かす

製造データはワーカー（Cloud Run Job `pod-admin-worker`）の中で、VectorCraft を使って生成する
（REQ-0067 / ADR-0039）。**本番もステージングも、Cloud Scheduler が 5 分ごとに起動している。**
受注を入れれば放っておいても作られる。

手で起動するのは、5 分を待たずに今すぐ流したいときだけである。定期実行と重なった場合、
後から入ったほうは advisory lock を取れずに `processed=0` で降りる（`api/app/worker.py`）。
**壊れているのではない。**

```bash
# 本番
gcloud run jobs execute pod-admin-worker \
  --project tosyo-api-504104 --region asia-northeast1 --wait
# ステージング
gcloud run jobs execute pod-admin-worker \
  --project tosyo-api-stg --region asia-northeast1 --wait
```

起動すると、その環境の `pending` を古い順に処理して終了する（`WORKER_MAX_ITEMS` 件まで）。
**自分が入れた受注の分だけとは限らない。** 溜まっている行がまとめて処理される。
1 件 1〜2 秒で終わる。

ワーカーのイメージは API とは別（`api/Dockerfile` の `worker` ステージ）で、
生成の依存（VectorCraft・numpy など）はこちらにだけ入っている。**API のサーバーでは生成しない。**

## 製造データ生成 VM の撤去（REQ-0067・REQ-0068）

製造データは、以前は Windows VM 上の Adobe Illustrator（illustrator-vm）が作っていた。
2026-10-11 に生成をワーカーの中へ切り替え（REQ-0067）、2026-10-12 に VM とそのためのネットワークを
撤去した（REQ-0068。撤去したものの一覧もそちら）。

**撤去直前のブートディスクを、スナップショット `illustrator-vm-final-20261012` に残してある**
（Windows・Illustrator・Adobe のサインイン・自動ログオンの設定を含む）。それより古いスナップショットと
VM を作ったイメージは、撤去のときに消した。
Illustrator での生成へ戻す必要が出たら、REQ-0068 と REQ-0067 の PR を revert して apply し
（ネットワーク・VM・ワーカーの VPC 接続・Job のタイムアウト・監視が戻る）、VM のディスクは
このスナップショットから作る（`source_image` の代わりに `source_snapshot`）。
VM 用サービスアカウントの権限 2 件が、削除済みのアカウントを指したままプロジェクトの IAM ポリシーに残っている
（外すにはオーナー権限が要る。何もできないので害は無い）。オーナーが次で消す。

```bash
for role in roles/logging.logWriter roles/monitoring.metricWriter; do
  gcloud projects remove-iam-policy-binding tosyo-api-504104 --role="$role" \
    --member="deleted:serviceAccount:illustrator-vm@tosyo-api-504104.iam.gserviceaccount.com?uid=<UID>"
done
```

`<UID>` は `gcloud projects get-iam-policy tosyo-api-504104 | grep illustrator-vm` で出る値。

**スナップショットは、戻す見込みが無くなったら消す**（保管料がかかる。見直しの時期は REQ-0068）。

```bash
gcloud compute snapshots delete illustrator-vm-final-20261012 --project=tosyo-api-504104
```

## 製造データ生成の疎通確認（REQ-0061）

カットオーバーの前、両環境とも Cloud Scheduler を止めていた時期に、
**戻れなくなる切替（判断ポイント）より前に生成が通ることを確かめる**ために作った手順である。

**本番の Scheduler は有効になったので、本番でこの手順を使うのは
ワーカーそのものを疑うときだけになった。** ステージングでは今もそのまま使える。

### 流す前に必ず数える

以下の `psql` は、**「データの移送」節と同じ経路で叩く**（Cloud SQL Auth Proxy を立て、
macOS には psql が無いので `postgres:17-alpine` を使う）。接続先の確かめ方も同じである。

```bash
# その環境の待ち行列。**自分が作った行だけとは限らない**
psql -Atc "SELECT status, count(*) FROM manufacturing_data
           WHERE status IN ('pending','generating') GROUP BY status"
```

### 手順

```bash
# 1. 専用の受注元を足す（実データのキャッシュに触れないため。本番のみ）
#    キャッシュキーは (order_source_id, product_code, size, variant)
psql -c "INSERT INTO order_sources (id, code, api_key, name, phone, postal_code,
         address_prefecture, address_city, is_active)
         VALUES (gen_random_uuid(), 'SMOKE_REQ0061', '<APIキー>', '[REQ-0061]疎通確認',
         '03-0000-0061', '150-0001', '東京都', '渋谷区神宮前1-2-3', true)"

# 2. v2 受注を 1 件入れる（tshirt は position が必須。design 1 レイヤーで足りる）
curl -X POST "$API/api/v2/orders" -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{
  "order_number": "9990061",
  "customer": {"name":"REQ-0061 疎通確認","postal_code":"150-0001",
    "address_prefecture":"東京都","address_city":"渋谷区神宮前1-2-3","phone":"03-0000-0061"},
  "items": [{"uid":"9990611","product_type":"tshirt","product_name":"[REQ-0061] 疎通確認用Tシャツ",
    "price":0,"quantity":1,"size":"M","position":"正面","color":"白",
    "product_code":"SMOKE-REQ0061-TSHIRT-M",
    "source_images":[{"layer_type":"design","url":"<公開httpsのPNG>"}]}]}'

# 3. ワーカーを 1 回だけ起動する（コマンドは「製造データ生成を手動で動かす」節）。
#    **Scheduler は止めたままにする**

# 4. ready になり、その環境のバケットに入ったことを確認する
psql -Atc "SELECT status, output_filename, file_size, file_path FROM manufacturing_data
           WHERE product_code='SMOKE-REQ0061-TSHIRT-M'"
gcloud storage ls -l gs://<環境のバケット>/<prefix>/manufacturing_data/

# 5. 発注資料 ZIP に生成物が入っていることを確認する
#    **成果物を直接ダウンロードする管理画面のエンドポイントは無い。**
#    /orders/{id}/manufacturing-data は v1 用の別系統で、v2 の行は 404 になる
curl -o docs.zip "$API/api/v1/manufacturers/<メーカーID>/order-documents?order_item_ids=<明細ID>" \
  -H "Authorization: Bearer $TOKEN" && unzip -l docs.zip
```

### 片付け

**DB はカットオーバーの `reset`（DROP SCHEMA）で消えるが、GCS の生成物は消えない。**

```bash
psql -c "DELETE FROM manufacturing_data WHERE product_code='SMOKE-REQ0061-TSHIRT-M'"
psql -c "DELETE FROM orders WHERE order_number='9990061'"
psql -c "DELETE FROM order_sources WHERE code='SMOKE_REQ0061'"
psql -c "DELETE FROM users WHERE email='req0061-smoke@example.com'"
gcloud storage rm gs://<環境のバケット>/<prefix>/manufacturing_data/<生成物>
```

## `default` VPC は消す

**`compute.googleapis.com` を有効にすると、GCP が `default` VPC を勝手に作る。**
全リージョンにサブネットが生え、次の規則が最初から付いてくる。

```
default-allow-rdp   INGRESS  0.0.0.0/0  （適用先の指定なし）  tcp:3389
default-allow-ssh   INGRESS  0.0.0.0/0  （適用先の指定なし）  tcp:22
```

本番では 2026-09-02 に削除した（当時 VM は 1 台も無く、空だった）。

```bash
for r in default-allow-icmp default-allow-internal default-allow-rdp default-allow-ssh; do
  gcloud compute firewall-rules delete "$r" --project=tosyo-api-504104 --quiet
done
gcloud compute networks delete default --project=tosyo-api-504104 --quiet
```

**Terraform では表せない。** 自動生成されたものを「無い状態」に保つ記述が書けないので、
`terraform plan` は消し忘れを検出しない。**compute API を有効にした環境では、毎回これを確認する。**

## 製造データ生成が止まったとき

**2026-09-27 に VM 上の生成 API が止まり、10-02 まで 5 日間誰も気づかなかった。**
ワーカーは注文が来たときしか生成に触れず、失敗は行に書かれるだけで、人に届く経路が 1 つも無かった。
生成をワーカーの中へ移した後（REQ-0067）も、生成処理（VectorCraft）が壊れれば同じことが起きうるので、
同じ形で守っている。**どれか 1 つが効かなくても、次の層が拾う。**

| 層 | 何をするか | どこにあるか |
|---|---|---|
| 止まっても失わない | ワーカーは毎回 VectorCraft を起動してみて、NG なら取り出さない。生成処理を起動できなかった生成は `pending` へ戻して自動で再試行し、5 回起動できなければ `failed` | `api/app/worker.py` |
| 人に知らせる | 下の 4 つのアラートを、**管理画面で設定した宛先**へメールで送る | `modules/manufacturing-monitoring` と `api/app/routers/internal.py` |

**宛先は管理画面「設定 → 製造データ生成のアラート」で変える**（apply は要らない）。
経路は Cloud Monitoring → Webhook（Basic 認証。パスワードは `INTERNAL_API_SECRET`）→
API の `POST /api/v1/internal/monitoring-alerts` → SendGrid である。発生と回復の両方で届く。
宛先が未登録なら何も送られない。**「ワーカーが動いていない」だけは**、API や DB ごと
止まっている場合に備えて、Terraform の `fallback_emails` にも Monitoring から直接送る。

アラートはワーカーのログの目印を数えている。**目印の文字列とフィルタは対になっている**
（変えるときは両方）。

| アラート | 鳴る条件 | 目印 |
|---|---|---|
| 製造データの生成処理が動かない | 15 分で 3 回 NG | `generator_health status=ng` |
| 製造データ生成ワーカーが動いていない | 死活確認のログが 30 分出ていない | `generator_health status=` |
| 製造データの生成が失敗した | `failed` に確定した | `manufacturing_data_failed` |
| 製造データが生成待ちのまま止まっている | 最も古い生成待ちが 60 分動いていない（その起動で 1 件も処理していないとき） | `manufacturing_data_stalled` |

### 鳴ったら

1. **ワーカーのログを見る。** `generator_health status=ng detail=...` に、VectorCraft が起動しない理由が出る
2. 直前のデプロイで壊れたなら、**ワーカーのイメージを 1 つ前のコミットへ戻す**

   ```bash
   gcloud run jobs update pod-admin-worker --project tosyo-api-504104 --region asia-northeast1 \
     --image=asia-northeast1-docker.pkg.dev/tosyo-api-504104/pod-admin/worker:<前の SHA>
   ```

3. **生成処理を起動できなかった生成は放っておいてよい。** 直れば次のワーカーが拾う。
   管理画面で「要対応」になったものだけ、エラー内容を見て再生成する
   （入力の誤り。例: アクリルスタンドの土台が見つからない → ADR-0038）

## Terraform が管理しないもの

| もの | 誰がやるか | なぜ |
|---|---|---|
| state バケット | `scripts/bootstrap-state-bucket.sh` | 鶏卵 |
| Cloud Run のイメージタグ | デプロイ（CI / gcloud） | apply のたびに巻き戻るため |
| `terraform apply` そのもの | 作業者の手元 | CI に state と機密の読み取り権限を渡さないため（ADR-0031） |
| `sendgrid-api-key` の中身 | 人間（`gcloud secrets versions add`） | 値をリポジトリにも state にも置かない |
| 予算アラート | プロジェクト所有者 | 請求先アカウントの権限が要る |
| `default` VPC の削除 | 人間（プロジェクトごとに一度きり） | **compute API を有効にした瞬間に GCP が自動生成する。** Terraform の管理外なので、作られたことに気づいて消すしかない（上記） |
| VM のスナップショット | 人間 | 撤去した VM の切り戻し用（上記「製造データ生成 VM の撤去」） |
| `iap` / `osconfig` の API | （有効のまま） | VM のために有効にしたもの。撤去で Terraform の管理から外れたが、無効にはしていない（`disable_on_destroy = false`）。有効でも費用はかからない |

## 設定の依存関係で気をつけること

- **`api_max_instances × (db_pool_size + db_max_overflow)` が `db_max_connections` に収まること。**
  worker Job と migrate Job のぶんも足して数える。`terraform.tfvars` に計算を書いてある
- **ワーカー Job のタイムアウトは直接指定しない。** `worker_max_runtime_seconds` から
  `main.tf` の `locals` が導出する。先に殺されると、生成中の行がリース期限まで宙吊りになる
- 生成 1 件の上限（`local.generation_timeout_seconds`）は Terraform が正本で、ワーカーに
  `GENERATOR_TIMEOUT_SECONDS` として渡す。Job のタイムアウトも同じ値から導出する
- **ログ指標を差し替える `apply` は 2 回に分ける**（2026-10-11 に本番で 1 回では通らなかった）。
  新しい指標とアラートを `-target` で先に当て、10 分おいて残り（古い指標の削除）を当てる。1 回で当てると、
  古い指標の削除がそれを参照するアラートの書き換えより先に走るか（`still used in an alerting policy`）、
  作ったばかりの指標がまだ使えない（`Cannot find metric(s)`）

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
