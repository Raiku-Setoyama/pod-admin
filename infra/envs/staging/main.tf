# ステージング（tosyo-api-stg）。
# **値だけを持つ。** 構成の本体は modules/stack にある。

locals {
  project_id = "tosyo-api-stg"
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
  env               = "staging"
  github_repository = "Raiku-Setoyama/pod-admin"

  # 使い捨て環境なので、現行オブジェクトも 30 日で消す。バケットごと壊してよい。
  gcs_bucket_name    = "tosyo-pod-admin-stg"
  gcs_retention_days = 30
  gcs_force_destroy  = true

  db_tier                  = "db-f1-micro"
  db_disk_size_gb          = 10
  db_disk_autoresize_limit = 50
  db_deletion_protection   = false

  # ステージングは PITR まではやらない。日次バックアップだけ持つ。
  db_pitr_enabled     = false
  db_retained_backups = 7

  # db-f1-micro（共有コア）の既定値と同じ。共有コアで既定より上げるのは
  # 不安定の元なので上げない。予算に収まるかは stack の validation が検証する。
  db_max_connections = 25

  api_max_instances = 1
  web_max_instances = 2
  db_pool_size      = 3
  db_max_overflow   = 2

  # 製造データ生成は当面ステージングでは動かさない。
  # 本番と同じ VM を共有すると本番のジョブ待ち行列に混ざるため（REQ-0055 で繋ぎ直す）。
  illustrator_vm_base_url = ""
  worker_schedule         = "*/5 * * * *"
  worker_schedule_paused  = true
}
