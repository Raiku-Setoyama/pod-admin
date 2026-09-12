# infra — GCP のインフラ定義（Terraform）

POD Admin の GCP リソースをコードで管理する。設計の詳細は
`docs/superpowers/specs/2026-08-27-gcp-migration-design.md`、
判断の記録は `docs/02-decisions/ADR-0026`〜`ADR-0028`、`ADR-0030`〜`ADR-0032`。

## 構成

```
infra/
├── modules/
│   ├── stack/     アプリ 1 環境ぶんの構成（下記）
│   ├── network/   製造データ生成 VM を置く閉じた VPC（下記）
│   ├── illustrator-vm/  製造データ生成 VM そのもの（本番だけ）
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

**例外は `modules/network/` と `modules/illustrator-vm/` の 2 つである。**
環境の一部ではあるがアプリの構成ではない（プロジェクト単位の土台である）ものは、
`envs/<env>/` から直接呼んでよい。判断と、なぜ `stack` のトグルにしなかったかは **ADR-0036**。

**この 2 つは 1 つに統合する**（ADR-0037・REQ-0055 の PR 3）。
`illustrator-vm` の必須入力は両方とも `network` から来るので、実際には 1 つの単位である。

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

## 切り戻す（デプロイが原因のとき）

**先に切り戻す。原因の究明はそのあとでよい。**

Cloud Run はリビジョンを残すので、**イメージを作り直さずに前の状態へ戻せる。**
所要は 1 分程度である。

```bash
# 1. いま動いているリビジョンと、その 1 つ前を確認する
#    （新しい順に並ぶ。ACTIVE が付いているのが今のもの）
gcloud run revisions list --service pod-admin-api --region asia-northeast1

# 戻す先のイメージ（= コミット SHA）を確かめる
gcloud run revisions describe <前のリビジョン名> --region asia-northeast1 \
  --format='value(containers[0].image)'

# 2. 前のリビジョンへ 100% 戻す
gcloud run services update-traffic pod-admin-api --region asia-northeast1 \
  --to-revisions <前のリビジョン名>=100

# 3. 管理画面も同じように戻す（API と web は別サービスである）
gcloud run services update-traffic pod-admin-web --region asia-northeast1 \
  --to-revisions <前のリビジョン名>=100

# 4. **ワーカーも戻す。** Job にはリビジョンもトラフィック分割も無いので、
#    前のイメージを指し直す。**ここを忘れると、API だけ戻ってワーカーは
#    新しいコードのまま動き続ける。**
gcloud run jobs update pod-admin-worker --region asia-northeast1 \
  --image asia-northeast1-docker.pkg.dev/tosyo-api-504104/pod-admin/api:<戻す先のコミットSHA>
```

イメージのタグはコミット SHA なので、戻す先のコミットは一意に辿れる（`deploy.yml` 参照）。

### スキーマが進んでいるときは、そのままでは戻せない

`deploy.yml` は **migrate Job を最初に流す**ので、デプロイが完了していれば
**スキーマは新しいまま**である。上の手順で戻すのは**コードだけ**であり、
古いコードが新しいスキーマの上で動くことになる。

**列の追加だけなら動く**（古いコードはその列を知らないまま無視する）。
**列の削除・改名・NOT NULL 化を含むマイグレーションを流したあとは動かない。**
その場合はコードを戻すのではなく、**次の修正を前に進めて出す**ほうが速い。

どちらかは `api/alembic/versions/` の当該リビジョンを読めば分かる。
`op.add_column` だけなら前者、`op.drop_column` / `op.alter_column` があれば後者である。

**このため、後方互換でないマイグレーションは避ける。** 列を消すなら、
「使うのをやめる」変更を先に出し、次のデプロイで消す。

### データを戻す（Cloud SQL）

コードでもスキーマでもなく、**データが壊れた**とき（誤った一括更新など）に使う。

本番は PITR が有効（`db_pitr_enabled = true`・バックアップ 14 世代）なので、
**任意の時点へ復元できる。** ただし**既存のインスタンスは上書きしない。**
新しいインスタンスとして復元し、中身を確かめてから差し替える。

```bash
# 復元先を新しいインスタンスとして作る（既存には触らない）
gcloud sql instances clone pod-admin pod-admin-restore-<日付> \
  --point-in-time '2026-09-12T04:30:00.000Z'   # UTC で指定する
```

確認してから切り替える。**切り替えは接続先（Secret Manager の `database-url`）を
書き換えるのではなく、`infra/scripts/migrate-data.sh` で必要なデータだけを
戻すほうが安全である**（インスタンス名が変わると Terraform の管理から外れるため）。

**復元の前に、まずワーカーの Cloud Scheduler を止めること。**
止めないと、復元中の DB に対して生成が走る。

```bash
gcloud scheduler jobs pause pod-admin-worker --location asia-northeast1
```

### 製造データの生成が止まったとき

**切り戻しは要らない。** 生成待ちの行は `pending` のまま残り、VM が戻れば
ワーカーが自動で作り直す（到達不能は再試行され、上限に達した分だけが `failed` になる）。

1. 管理画面の「製造データ」で、生成待ち・生成失敗の件数を見る
2. VM を戻す（下記「外部 IP を持たない VM に入る」）
3. `failed` に落ちた行を「失敗した全件を戻す」でまとめて生成待ちへ戻す

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

**本番とステージングで前提が違う。**

| | Cloud Scheduler | 受注を入れると |
|---|---|---|
| 本番 | **5 分間隔で動いている**（カットオーバーで有効化した） | **放っておけば作られる** |
| ステージング | **止めてある** | 作られない。手で起動する |

**本番で手で起動するのは、5 分を待たずに今すぐ流したいときだけである。**
定期実行と重なった場合、後から入ったほうは advisory lock を取れずに
`processed=0` で降りる（`api/app/worker.py`）。**壊れているのではない。**

**ステージングから生成は動かせない**（REQ-0055 の移送後）。移送先の VM は
`tosyo-api-stg` から見て別プロジェクトの VPC の中にあり、外部 IP も、ピアリングも、
共有 VPC も無い。**URL を上書きしても到達しない。**
恒久的に繋ぐかどうかは未判断である（ADR-0034）。

```bash
# 本番（**上書きは要らない**）
gcloud run jobs execute pod-admin-worker \
  --project tosyo-api-504104 --region asia-northeast1 --wait
```

起動すると、その環境の `pending` を古い順に処理して終了する（`WORKER_MAX_ITEMS` 件まで）。
**自分が入れた受注の分だけとは限らない。** 溜まっている行がまとめて処理される。

### なぜ環境で違うのか

| | `ILLUSTRATOR_VM_BASE_URL` | 上書き |
|---|---|---|
| 本番 | Terraform で設定済み | **要らない** |
| ステージング | **空**（REQ-0053 の決定） | **要る** |

ステージングを VM に繋ぎっぱなしにしないのは、illustrator-vm が 1 件ずつの直列処理で、
**繋いだまま Scheduler が回ると本番の生成を 5 分ごとに待たせる**ためである
（本番の Scheduler は現に 5 分間隔で動いている）。
`--update-env-vars` は **その 1 回の実行にだけ**効き、Job の定義には残らない（ADR-0034）。

**上書きを忘れると、生成は静かに `failed` に落ちる**（`illustrator-vm is not configured`）。
`manufacturing_data.error_message` に理由が残るので、そこを見る。

恒久的に繋ぐかどうかは、illustrator-vm を会社組織へ移送したあとに判断する（REQ-0055）。

### 叩く前に見るもの

VM は外部 IP を持たないので、IAP トンネル越しに見る（下記「外部 IP を持たない VM に入る」）。

```bash
# illustrator-vm は 1 件ずつ。空でないなら、その分だけ本番の生成を待たせる
curl -sS --fail localhost:18000/health
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

VM の混み具合は「製造データ生成を手動で動かす」節の「叩く前に見るもの」で確かめる。

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

## 製造データ生成 VM のネットワーク（REQ-0055）

`modules/network/` が custom mode の VPC・サブネット 2 つ・ファイアウォール 2 本を作る。
**本番だけが呼ぶ**（ADR-0036）。ステージングは `illustrator_vm_base_url = ""` で
生成機能ごと止めているので、繋ぐ先が無い。

| もの | 何のためか |
|---|---|
| VPC（custom mode） | auto mode は全リージョンにサブネットを作り、`default-allow-ssh` / `default-allow-rdp` を 0.0.0.0/0 で持ってくる |
| サブネット（VM） | 外部 IP を持たない VM を置く |
| サブネット（Cloud Run） | Direct VPC egress。**インスタンスごとに 1 アドレス使い、デプロイ中は新旧のリビジョンが同時に持つ** |
| FW: run → illustrator | 生成 API を呼ぶ唯一の経路 |
| FW: IAP → illustrator | 運用の入口（RDP と、VM 単体の疎通確認） |

**名前と CIDR の正本は `modules/network/main.tf` の `locals` である。** ここには写さない。

**Cloud NAT が VM のサブネットだけを NAT する。** 外部 IP を持たない VM の下り
（Adobe のライセンス確認・Windows Update・Ops Agent）に要る。
**NAT ゲートウェイは VM が 1 台も無くても課金される**ので、VM と同じ PR で作った。

VM 本体は `modules/illustrator-vm/` にある。**stop/start で運用し、delete/recreate しない** —
理由はそのファイルの冒頭にある。`deletion_protection = true` とイメージの
`ignore_changes` がそれを守っている。

**どうしても作り直すときは、`deletion_protection` を false にする apply を先に通す。**
`-replace` は削除保護に阻まれる。**その前に、いま動いているディスクの
イメージかスナップショットを取る**（Adobe の認証はそこにしかない。REQ-0062）。

**VPC に入っているのはワーカー Job だけで、`ILLUSTRATOR_VM_BASE_URL` もワーカーにしか渡さない。**
理由の正本は `modules/stack/variables.tf` の `worker_vpc_egress` の説明。
`egress` は `PRIVATE_RANGES_ONLY` なので、SendGrid と Cloud SQL は公衆網のままである。

**タグを付け忘れた VM には、どちらの規則も効かない。** 到達できないだけなので壊れ方は静かである。
VM を作るときは `modules/network` の `illustrator_target_tag` 出力から渡し、**値を直書きしない。**

### VM の中のアプリを更新する

**Windows 側の手順の正本は `illustrator-vm/scripts/setup_windows/README.md`
「コード更新時の再起動手順」である。ここには写さない。**
ここに書くのは **pod-admin 側で先にやること**と、**移送で変わった入口**だけである。

#### なぜワーカーを止めるのか

VM が応答しない間に pod-admin のワーカーが動くと、`generate()` の例外ハンドラが
製造データの行を `failed` にする（`api/app/services/manufacturing_data_service.py`）。

**ワーカーは `failed` を拾い直さない。** `claim_next_generation` は `pending` しか取らず、
`reclaim_expired_leases()` が戻すのはリースの切れた `generating` だけである。
復旧の道はあるが、**どちらも自動ではない。**

- 管理画面から `POST /manufacturing-data/{id}/retry`（**1 件ずつ**。一括は無い）
- 同じキャッシュキーで受注が入り直せば `_resolve_or_create()` が `pending` に戻す

被害は **1 回の起動あたり最大 20 件**である（`worker_max_items`。`worker_max_runtime_seconds`
は 600 秒）。**一瞬の瞬断では落ちない** — `IllustratorVmClient` が接続エラーと 503 を
3 回まで再試行する。効いてくるのは、再起動のように数分単位で止まるときである。

#### 窓に入る前（本番は動いたまま）

**止めなくてよいことは、止める前に済ませる。**

```bash
# トンネルは 2 本とも先に開ける（PID を控えて、あとで確実に閉じる）
gcloud compute start-iap-tunnel illustrator-vm 3389 \
  --local-host-port=localhost:13389 --zone=asia-northeast1-a --project=tosyo-api-504104 &
RDP_TUNNEL=$!
gcloud compute start-iap-tunnel illustrator-vm 8000 \
  --local-host-port=localhost:18000 --zone=asia-northeast1-a --project=tosyo-api-504104 &
API_TUNNEL=$!
```

**接続できないときは、まず VM ではなくトンネルを疑う。** IAP のトンネルは
ラップトップのスリープで落ちる。手順の詳細は下記「外部 IP を持たない VM に入る」。

RDP で入り、**作業ツリーが汚れていないことと、いまの版**を控えておく。
**戻り先を知らないまま更新しない。**

```powershell
cd C:\illustrator-vm
git status          # 誰かが VM 上で直接直していないか
git rev-parse HEAD  # 戻り先。控える
```

#### 窓（ここから生成が待つ）

**`terraform apply` を並行して走らせないこと。** 下の `pause` は Terraform の管理下にある値
（`modules/scheduler` の `paused`）に対する差分であり、**誰かが `envs/prod` で apply すると
黙って ENABLED に戻る。** 移送のときは、それを利用して最後に戻した。

```bash
gcloud scheduler jobs pause pod-admin-worker \
  --location=asia-northeast1 --project=tosyo-api-504104
```

**止めただけでは、走っているワーカーは止まらない。** 起動済みの実行は最大 600 秒
処理を続けるので、**空になるまで待つ。**

```bash
gcloud run jobs executions list --job=pod-admin-worker \
  --region=asia-northeast1 --project=tosyo-api-504104 \
  --filter="status.completionTime=null" --format="value(name)"
# 何も出なくなるまで待つ
```

そのうえで **VM 側の待ち行列が空になったこと**を確かめる。VM は 1 件ずつの直列処理なので、
`pending_count` が 0 でないかぎり、まだ処理し切っていない。

```bash
curl -sS --fail localhost:18000/health   # queue.pending_count と active_jobs が 0
```

ここで **`illustrator-vm` リポジトリの手順**（`git pull` → `Stop-ScheduledTask` →
python 停止 → `Start-ScheduledTask`）を実行する。**pull に `install_service.ps1` や
`setup_*.ps1` 自体の変更が含まれていたら、タスクの再起動だけでは足りない**
（向こうの README を参照）。

#### 窓を出る

**起動しただけでは、Illustrator が描けるかは分からない。** `/health` を見て、
実際に 1 件生成を通す。**`/` の `version` は当てにならない**（文字列が直書きされており、
`git pull` では動かない）。

```bash
curl -sS --fail localhost:18000/health   # config_loaded と worker_running が true
```

生成の確認は、**トンネル越しに VM へ直接ジョブを投げるのが速い**（pod-admin の DB にも
GCS にも触れない）。REQ-0055 の段階 3 で使った方法である。
pod-admin を通した端から端までの確認をしたいときは「製造データ生成の疎通確認」の節。

```bash
gcloud scheduler jobs resume pod-admin-worker \
  --location=asia-northeast1 --project=tosyo-api-504104
gcloud scheduler jobs describe pod-admin-worker \
  --location=asia-northeast1 --project=tosyo-api-504104 --format="value(state)"  # ENABLED
kill $RDP_TUNNEL $API_TUNNEL
```

**窓の間に落ちた行がないかを数える。** 落ちていたら 1 件ずつ `retry` を叩く
（自動では戻らない）。

```sql
SELECT id, product_code, error_message FROM manufacturing_data
WHERE status = 'failed' AND updated_at > '<窓に入った時刻>';
```

#### 移送で落ちた運用ポリシー

**イメージはディスクを運ぶが、VM に付いたリソースポリシーは運ばない。**
旧 VM（`lively-transit-334610`）に付いていたもののうち、**移送先には 1 つも無い。**

| 旧 VM に付いていたもの | 実測（2026-09-07） | 扱い |
|---|---|---|
| `illustrator-vm-daily-snapshot` | 日次・14 日保持・03:00 JST。**旧ディスクに付いていた** | REQ-0062 |
| Uptime Check `illustrator-api-health` ＋ 自動再起動 | 外部 IP 前提。**そのままは移せない** | REQ-0063 |
| `illustrator-vm-nightly-restart` | 毎晩 03:50→03:55 の stop/start | **戻さない**（`illustrator-vm` の Issue #5） |

死活監視の作り直しは REQ-0063、スナップショットは REQ-0062 が追う。
**この表は「何が旧環境にあったか」の記録であり、現状の宣言ではない。**
いま何があるかは `terraform plan` と `gcloud compute resource-policies list` が正本である。

### `default` VPC は消す

**`compute.googleapis.com` を有効にすると、GCP が `default` VPC を勝手に作る。**
全リージョンにサブネットが生え、次の規則が最初から付いてくる。

```
default-allow-rdp   INGRESS  0.0.0.0/0  （適用先の指定なし）  tcp:3389
default-allow-ssh   INGRESS  0.0.0.0/0  （適用先の指定なし）  tcp:22
```

**REQ-0055 が個人プロジェクトで消そうとしているものと同じ形である。**
本番では 2026-09-02 に削除した（当時 VM は 1 台も無く、空だった）。

```bash
for r in default-allow-icmp default-allow-internal default-allow-rdp default-allow-ssh; do
  gcloud compute firewall-rules delete "$r" --project=tosyo-api-504104 --quiet
done
gcloud compute networks delete default --project=tosyo-api-504104 --quiet
```

**Terraform では表せない。** 自動生成されたものを「無い状態」に保つ記述が書けないので、
`terraform plan` は消し忘れを検出しない。**compute API を有効にした環境では、毎回これを確認する。**

### 外部 IP を持たない VM に入る

外部 IP が無いので RDP も直接は繋がらない。IAP TCP forwarding でトンネルを掘る。
`roles/iap.tunnelResourceAccessor`（または Owner）が要る。

```bash
# 生成 API の生死を確かめる（Cloud Run を経由しないので、VM 単体を検証できる）
gcloud compute start-iap-tunnel illustrator-vm 8000 \
  --local-host-port=localhost:18000 --zone=asia-northeast1-a --project=tosyo-api-504104 &
curl -sS --fail localhost:18000/health

# RDP
gcloud compute start-iap-tunnel illustrator-vm 3389 \
  --local-host-port=localhost:13389 --zone=asia-northeast1-a --project=tosyo-api-504104
# 別途 Microsoft Remote Desktop で localhost:13389 へ接続する
```

**繋がらないとき、まず疑うのはトンネルであって VM ではない。**
IAP のトンネルはラップトップのスリープで落ちる。
`&` で背景に置いたものは、用が済んだら `kill` する（残ると次回 `address already in use` になる）。

#### `reset-windows-password` を安易に叩かない

**これは自動ログオンを壊す。** `setup_autologon.ps1` は自動ログオン用のパスワードを
**レジストリに平文で持っている**ので、GCP 側でリセットすると
**アカウント側だけが変わってレジストリが古いまま**になり、**次の再起動でログオンに失敗する。**

サーバーは AtLogOn のタスクでしか起動しないため、**誰かが RDP でログインするまで
上がってこない。** `illustrator-vm` の Issue #5 に、夜間再起動と組み合わさって
9 時間 23 分のダウンになった実測がある。

**しかも悪循環になる** — 入るためにリセットする → それで自動ログオンがまた失効する。

やむを得ずリセットしたら、**同じ RDP セッションのうちに再設定する。**

```powershell
cd C:\illustrator-vm\scripts\setup_windows
.\setup_autologon.ps1
```

移送先の VM で自動ログオンは**働いている**。イメージから起こした直後、人が一度も
RDP せずに生成 API が 1 分ほどで `healthy` になった（REQ-0055）。**この状態を壊さないこと。**

## Terraform が管理しないもの

| もの | 誰がやるか | なぜ |
|---|---|---|
| state バケット | `scripts/bootstrap-state-bucket.sh` | 鶏卵 |
| Cloud Run のイメージタグ | デプロイ（CI / gcloud） | apply のたびに巻き戻るため |
| `terraform apply` そのもの | 作業者の手元 | CI に state と機密の読み取り権限を渡さないため（ADR-0031） |
| `sendgrid-api-key` の中身 | 人間（`gcloud secrets versions add`） | 値をリポジトリにも state にも置かない |
| 予算アラート | プロジェクト所有者 | 請求先アカウントの権限が要る |
| `default` VPC の削除 | 人間（プロジェクトごとに一度きり） | **compute API を有効にした瞬間に GCP が自動生成する。** Terraform の管理外なので、作られたことに気づいて消すしかない（下記） |

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
