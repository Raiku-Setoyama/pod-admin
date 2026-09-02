# 本番（tosyo-api-504104）。
# **値だけを持つ。** 構成の本体は modules/stack にある。
#
# アプリの設定値（SendGrid の差出人・連絡先・VM の URL）は
# **移行元の Railway から写したものである。** カットオーバーで挙動を変えないため、
# 移行の時点では値を変えない。

locals {
  project_id = "tosyo-api-504104"
  region     = "asia-northeast1"
}

provider "google" {
  project = local.project_id
  region  = local.region
}

module "stack" {
  source = "../../modules/stack"

  project_id        = local.project_id
  region            = local.region
  github_repository = "Raiku-Setoyama/pod-admin"

  # **GCS_PREFIX になる。** 移行元（Railway）の GCS_PREFIX も prod なので、
  # 旧バケットから複製したオブジェクトのパスがそのまま通る。ここを変えると、
  # DB に残った file_path が実体を指さなくなる。
  env = "prod"

  gcs_bucket_name = "tosyo-pod-admin-prod"

  # **本番は現行オブジェクトを消さない**（ADR-0032）。
  # 業務ファイル（製造データ・請求書・チャット添付）は参照期限が読めない。
  gcs_retention_days = null
  gcs_force_destroy  = false

  db_tier                  = "db-custom-1-3840"
  db_disk_size_gb          = 30
  db_disk_autoresize_limit = 200
  db_deletion_protection   = true

  # 日次バックアップだけでは障害の直前まで戻せない。本番は PITR を有効にする。
  db_pitr_enabled     = true
  db_retained_backups = 14

  # 既定値はメモリ量から算出されるので固定する。
  # 下のプール設定に収まるかは stack の validation が機械的に検証する。
  db_max_connections = 100

  # **既定値と同じだが、未決事項の目印として明示的に置いている。**
  # 外部販売サイト側のタイムアウト値の確認待ち（REQ-0054 の未決事項）。
  # 判断の根拠は modules/stack/variables.tf の description が正本。
  api_min_instances = 0

  api_max_instances = 5
  web_max_instances = 5
  db_pool_size      = 5
  db_max_overflow   = 5

  # **ステージングと同じ 5 分間隔にしてある**（設計書 5.3 は 1 分間隔と書いていた）。
  # Cloud Run Job は起動のたびにイメージ取得・Python 起動・Cloud SQL 接続まで
  # 課金される。**「空なら即降りる」実装で浮くのは、そのあとの数秒だけ**であり、
  # 起動そのものの費用は減らない。1 分間隔にすると月 43,000 回起動して
  # 月 ¥1,300〜2,100 上乗せになる。**買えるのは待ち時間 4 分の短縮だけ**で、
  # 生成 1 件に 30〜360 秒かかる処理では釣り合わない。
  worker_schedule = "*/5 * * * *"

  # 有効。**止めるときも、コンソールではなくここを true にする**
  # （コンソールで止めても次の apply が黙って動かし直す）。
  #
  # **止まる経路はもう 1 つある。** modules/stack の
  # `paused = worker_schedule_paused || illustrator_vm_base_url == ""` なので、
  # 下の URL を空にすると、この行が false のままでも Scheduler は止まる。
  # **戻すのを忘れても何もエラーにならない。** 製造データが黙って作られなく
  # なるだけである。REQ-0055 で URL を張り替えるときに踏みやすい。
  worker_schedule_paused = false

  # 個人プロジェクト（lively-transit-334610）にある VM を当面そのまま使う。
  # 内部 IP に張り替えるのは REQ-0055。
  illustrator_vm_base_url = "http://34.84.121.166:8000"

  sendgrid_from_email = "noreply@rksyo.com"
  contact_email       = "raiku.setoyama@ironiwa.co.jp"
}

# 製造データ生成 VM を迎えるためのネットワーク（REQ-0055 の 1 本目）。
#
# **この時点では誰も使っていない。** VM はまだ個人プロジェクト
# （lively-transit-334610）で動いており、Cloud Run も上の
# `illustrator_vm_base_url` が指す外部 IP を見ている。
#
# 追加しかしないので**切り戻す対象が無い。** REQ-0054 の PR 1 で
# 本番を空のまま先に作ったのと同じ理由で、当日その場で組み立てる作業を減らす。
#
# **envs が持つのは値だけ、という原則の唯一の例外である。**
# stack の中に入れてトグルで切り替えない理由は ADR-0036。
module "network" {
  source = "../../modules/network"

  project_id = local.project_id
  region     = local.region
}
