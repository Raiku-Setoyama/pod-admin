locals {
  env = "staging"

  labels = {
    app        = "pod-admin"
    env        = local.env
    managed-by = "terraform"
  }

  # 1 件の製造データ生成にかかりうる最大秒数。
  # **正本は api/app/config.py の Settings.generation_worst_case_seconds** であり、
  # ここはその値を写したもの。ILLUSTRATOR_VM_* の設定を変えたら両方を直す。
  generation_worst_case_seconds = 921

  # ワーカーは自分で降りる設計なので、Job のタイムアウトは
  # 「降りる判断をしてから、最後の 1 件を処理し終えるまで」を賄えばよい。
  # 直接指定せず導出することで、両者の関係が崩れないようにする。
  worker_job_timeout_seconds = var.worker_max_runtime_seconds + local.generation_worst_case_seconds
}

module "services" {
  source = "../../modules/project-services"

  project_id = var.project_id
  services = [
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "storage.googleapis.com",
  ]
}

module "service_accounts" {
  source = "../../modules/service-accounts"

  project_id = var.project_id

  accounts = {
    "pod-admin-api" = {
      display_name  = "POD Admin API"
      description   = "Cloud Run api サービスと migrate Job が使う"
      project_roles = ["roles/cloudsql.client"]
    }
    "pod-admin-worker" = {
      display_name  = "POD Admin worker"
      description   = "製造データ生成ワーカー（Cloud Run Job）が使う"
      project_roles = ["roles/cloudsql.client"]
    }
    "pod-admin-web" = {
      display_name  = "POD Admin web"
      description   = "Cloud Run web サービスが使う（GCP リソースへは触らない）"
      project_roles = []
    }
    "pod-admin-scheduler" = {
      display_name  = "POD Admin scheduler"
      description   = "Cloud Scheduler がワーカー Job を起動するのに使う"
      project_roles = []
    }
  }

  depends_on = [module.services]
}

locals {
  api_member       = module.service_accounts.members["pod-admin-api"]
  worker_member    = module.service_accounts.members["pod-admin-worker"]
  scheduler_member = module.service_accounts.members["pod-admin-scheduler"]

  # DB とファイルとシークレットに触るのは api と worker だけ。
  data_plane_members = [local.api_member, local.worker_member]
}

module "artifact_registry" {
  source = "../../modules/artifact-registry"

  project_id = var.project_id
  region     = var.region
  name       = "pod-admin"
  labels     = local.labels

  depends_on = [module.services]
}

module "gcs" {
  source = "../../modules/gcs"

  project_id                = var.project_id
  name                      = var.gcs_bucket_name
  location                  = var.region
  labels                    = local.labels
  versioning                = true
  retention_days            = var.gcs_retention_days
  noncurrent_retention_days = 7
  force_destroy             = var.gcs_force_destroy
  object_admin_members      = local.data_plane_members

  depends_on = [module.services]
}

module "cloud_sql" {
  source = "../../modules/cloud-sql"

  project_id          = var.project_id
  region              = var.region
  name                = "pod-admin"
  tier                = var.db_tier
  disk_size_gb        = var.db_disk_size_gb
  availability_type   = "ZONAL"
  deletion_protection = var.db_deletion_protection
  labels              = local.labels

  database_name = "pod_admin"
  user_name     = "pod_admin"

  # ステージングは PITR まではやらない。日次バックアップだけ持つ。
  pitr_enabled     = false
  retained_backups = 7

  database_flags = {
    max_connections = tostring(var.db_max_connections)
  }

  depends_on = [module.services]
}

resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "random_password" "internal_api_secret" {
  length  = 48
  special = false
}

module "secrets" {
  source = "../../modules/secrets"

  project_id = var.project_id
  region     = var.region
  labels     = local.labels

  managed_secrets = {
    "database-url"        = module.cloud_sql.database_url
    "app-secret-key"      = random_password.secret_key.result
    "internal-api-secret" = random_password.internal_api_secret.result
  }

  # SendGrid の鍵は人間が入れる。空のままでもアプリは起動し、
  # メール送信だけが無効になる（api/app/dependencies.py）。
  external_secrets = {
    "sendgrid-api-key" = ""
  }

  accessor_members = local.data_plane_members

  depends_on = [module.services]
}

locals {
  # api / worker / migrate は同じイメージ・同じ設定で動く。差は起動コマンドだけ。
  app_secret_env_vars = {
    DATABASE_URL        = "database-url"
    SECRET_KEY          = "app-secret-key"
    INTERNAL_API_SECRET = "internal-api-secret"
    SENDGRID_API_KEY    = "sendgrid-api-key"
  }

  app_env_vars = {
    DEBUG = "false"

    GCS_BUCKET = module.gcs.name
    GCS_PREFIX = local.env

    DB_POOL_SIZE    = tostring(var.db_pool_size)
    DB_MAX_OVERFLOW = tostring(var.db_max_overflow)

    ILLUSTRATOR_VM_BASE_URL = var.illustrator_vm_base_url

    SENDGRID_FROM_EMAIL = var.sendgrid_from_email
    CONTACT_EMAIL       = var.contact_email

    # CORS_ORIGINS は list[str] なので JSON で渡す（pydantic-settings の仕様）。
    CORS_ORIGINS           = jsonencode([module.web.uri])
    ADMIN_BASE_URL         = module.web.uri
    MANUFACTURER_LOGIN_URL = "${module.web.uri}/manufacturer-login"
  }
}

module "api" {
  source = "../../modules/cloud-run-service"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-api"
  service_account_email = module.service_accounts.emails["pod-admin-api"]
  labels                = local.labels

  cpu             = "1"
  memory          = "2Gi"
  min_instances   = 0
  max_instances   = var.api_max_instances
  timeout_seconds = 300
  container_port  = 8000

  startup_probe_path = "/health"

  env_vars           = local.app_env_vars
  secret_env_vars    = local.app_secret_env_vars
  cloudsql_instances = [module.cloud_sql.connection_name]

  # 管理画面と外部の販売サイトから叩かれるため公開する。
  # 認証はアプリ側（JWT / API キー）が持つ。
  invoker_members = ["allUsers"]

  depends_on = [module.secrets]
}

module "web" {
  source = "../../modules/cloud-run-service"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-web"
  service_account_email = module.service_accounts.emails["pod-admin-web"]
  labels                = local.labels

  cpu             = "1"
  memory          = "512Mi"
  min_instances   = 0
  max_instances   = var.web_max_instances
  timeout_seconds = 300
  container_port  = 3000

  # API の向き先はビルド時にバンドルへ焼き込まれるため、実行時の環境変数は要らない。
  env_vars = {}

  invoker_members = ["allUsers"]

  depends_on = [module.services]
}

module "migrate_job" {
  source = "../../modules/cloud-run-job"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-migrate"
  service_account_email = module.service_accounts.emails["pod-admin-api"]
  labels                = local.labels

  command = ["uv", "run", "alembic", "upgrade", "head"]

  cpu             = "1"
  memory          = "512Mi"
  timeout_seconds = 900
  max_retries     = 0

  env_vars           = local.app_env_vars
  secret_env_vars    = local.app_secret_env_vars
  cloudsql_instances = [module.cloud_sql.connection_name]

  depends_on = [module.secrets]
}

module "worker_job" {
  source = "../../modules/cloud-run-job"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-worker"
  service_account_email = module.service_accounts.emails["pod-admin-worker"]
  labels                = local.labels

  command = ["uv", "run", "python", "-m", "app.worker"]

  cpu             = "1"
  memory          = "1Gi"
  timeout_seconds = local.worker_job_timeout_seconds
  max_retries     = 0

  env_vars = merge(local.app_env_vars, {
    WORKER_MAX_RUNTIME_SECONDS = tostring(var.worker_max_runtime_seconds)
    WORKER_MAX_ITEMS           = tostring(var.worker_max_items)
  })
  secret_env_vars    = local.app_secret_env_vars
  cloudsql_instances = [module.cloud_sql.connection_name]

  invoker_members = [local.scheduler_member]

  depends_on = [module.secrets]
}

module "worker_schedule" {
  source = "../../modules/scheduler"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-worker"
  description           = "製造データ生成ワーカーの定期起動"
  job_name              = module.worker_job.name
  service_account_email = module.service_accounts.emails["pod-admin-scheduler"]
  schedule              = var.worker_schedule
  paused                = var.worker_schedule_paused

  depends_on = [module.worker_job]
}
