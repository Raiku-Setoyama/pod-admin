project_id = "tosyo-api-stg"
region     = "asia-northeast1"

gcs_bucket_name    = "tosyo-pod-admin-stg"
gcs_retention_days = 30
gcs_force_destroy  = true

db_tier                  = "db-f1-micro"
db_disk_size_gb          = 10
db_disk_autoresize_limit = 50
db_deletion_protection   = false

# db-f1-micro（共有コア）の既定値と同じ。共有コアで既定より上げるのは
# 不安定の元なので上げない。予算に収まるかは variables.tf の validation が検証する。
db_max_connections = 25

api_max_instances = 1
web_max_instances = 2
db_pool_size      = 3
db_max_overflow   = 2

# ワーカーは Cloud Run Job のタイムアウトより先に自分で降りる。
# Job 側のタイムアウトはこの値から導出する（main.tf の locals を参照）。
worker_max_runtime_seconds = 600
worker_max_items           = 20

# 製造データ生成は当面ステージングでは動かさない。
# 本番と同じ VM を共有すると本番のジョブ待ち行列に混ざるため（REQ-0055 で繋ぎ直す）。
illustrator_vm_base_url = ""
worker_schedule         = "*/5 * * * *"
worker_schedule_paused  = true

github_repository = "Raiku-Setoyama/pod-admin"
