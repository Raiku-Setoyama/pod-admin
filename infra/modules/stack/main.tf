# POD Admin の 1 環境ぶんの構成。
#
# **modules/* が汎用の GCP ラッパーなのに対し、ここはアプリを知っている層である。**
# 「api と worker と migrate が同じイメージ・同じ設定で動く」「CORS_ORIGINS は
# JSON で渡す」「ワーカーの Job タイムアウトは実行上限から導出する」といった
# POD Admin 固有の知識はすべてここに集める。
#
# 環境の違いは呼び出し側（envs/<env>/main.tf）が渡す値だけにする。
# **ここを環境ごとに複製しない**（ADR-0027）。複製すると、ステージングで直した
# 修正が本番に伝わらなくなる。

locals {
  # 使い捨ててよい環境かどうかは gcs_force_destroy 1 つで表す。
  # **Cloud SQL と GCS だけ守って Cloud Run を守らない**理由が無いので、
  # 同じ表明から Cloud Run の削除保護も導く。
  deletion_protection = !var.gcs_force_destroy

  labels = {
    app        = "pod-admin"
    env        = var.env
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
  source = "../project-services"

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
  source = "../service-accounts"

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
    "pod-admin-deployer" = {
      display_name = "POD Admin deployer"
      description  = "GitHub Actions がデプロイに使う（鍵 JSON は作らない。ADR-0028）"
      # イメージの push はリポジトリ単位、実行 ID のなりすましは SA 単位で付ける。
      # プロジェクト全体に要るのは Cloud Run の更新権限だけ。
      project_roles = ["roles/run.admin"]
    }
  }

  depends_on = [module.services]
}

locals {
  api_member       = module.service_accounts.members["pod-admin-api"]
  worker_member    = module.service_accounts.members["pod-admin-worker"]
  scheduler_member = module.service_accounts.members["pod-admin-scheduler"]
  deployer_member  = module.service_accounts.members["pod-admin-deployer"]

  # DB とファイルとシークレットに触るのは api と worker だけ。
  data_plane_members = [local.api_member, local.worker_member]
}

module "artifact_registry" {
  source = "../artifact-registry"

  project_id  = var.project_id
  region      = var.region
  name        = "pod-admin"
  description = "POD Admin のコンテナイメージ"
  labels      = local.labels

  writer_members = [local.deployer_member]

  depends_on = [module.services]
}

module "github_oidc" {
  source = "../github-oidc"

  project_id        = var.project_id
  github_repository = var.github_repository

  impersonated_service_account_ids = {
    "pod-admin-deployer" = module.service_accounts.ids["pod-admin-deployer"]
  }

  depends_on = [module.services]
}

# Cloud Run のリビジョンを作るには、そのリビジョンが名乗る実行 ID に対する
# なりすまし権限が要る。**プロジェクト全体には付けない。**
# 全体に付けると、あとから増えた権限の強い SA まで自動的に名乗れてしまう。
#
# 対象を持つモジュールの *_members 入力に寄せられないのは循環するからである
# （デプロイ用 SA を作るのが service-accounts 自身で、その出力を同じモジュールの
# 入力には渡せない）。合成層が持つ配線としてここに置く。
resource "google_service_account_iam_member" "deployer_act_as" {
  for_each = toset(["pod-admin-api", "pod-admin-web", "pod-admin-worker"])

  service_account_id = module.service_accounts.ids[each.key]
  role               = "roles/iam.serviceAccountUser"
  member             = local.deployer_member
}

module "gcs" {
  source = "../gcs"

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
  source = "../cloud-sql"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin"
  tier                  = var.db_tier
  disk_size_gb          = var.db_disk_size_gb
  disk_autoresize_limit = var.db_disk_autoresize_limit
  availability_type     = "ZONAL"
  deletion_protection   = var.db_deletion_protection
  labels                = local.labels

  database_name = "pod_admin"
  user_name     = "pod_admin"

  pitr_enabled     = var.db_pitr_enabled
  retained_backups = var.db_retained_backups

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
  source = "../secrets"

  project_id = var.project_id
  region     = var.region
  labels     = local.labels

  managed_secrets = {
    "database-url"        = module.cloud_sql.database_url
    "app-secret-key"      = random_password.secret_key.result
    "internal-api-secret" = random_password.internal_api_secret.result
  }

  # SendGrid の鍵は人間が入れる（infra/README.md）。
  #
  # Secret Manager は空のペイロードを拒否するため、「未設定」をそのまま表せない。
  # プレースホルダのままだと EmailService は構築されるが、送信は SendGrid の
  # 認証エラーになる。**送信系はすべて例外を握って False を返す**ので
  # （api/app/services/email_service.py）、業務フローは壊れず、ログに残るだけになる。
  external_secrets = {
    "sendgrid-api-key" = "REPLACE_ME"
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
    GCS_PREFIX = var.env

    DB_POOL_SIZE    = tostring(var.db_pool_size)
    DB_MAX_OVERFLOW = tostring(var.db_max_overflow)

    ILLUSTRATOR_VM_BASE_URL = var.illustrator_vm_base_url

    SENDGRID_FROM_EMAIL = var.sendgrid_from_email
    CONTACT_EMAIL       = var.contact_email

    # **Cloud Run は 1 サービスに 2 つの URL を割り当てる**（旧形式の
    # `<service>-<hash>-<region>.a.run.app` と、新形式の
    # `<service>-<project number>.<region>.run.app`）。どちらも公開されていて等しく届くので、
    # 片方だけを許可すると、もう片方で開いた利用者はログインすら通らない
    # （プリフライトが 400 "Disallowed CORS origin" で落ち、画面には何も出ない）。
    # `uri` は 1 つしか返さないので `urls` を使う。
    #
    # CORS_ORIGINS は list[str] なので JSON で渡す（pydantic-settings の仕様）。
    CORS_ORIGINS = jsonencode(module.web.urls)

    # 一方こちらはメール本文に載る。**宛先は 1 つに定める**ので uri のままにする。
    ADMIN_BASE_URL         = module.web.uri
    MANUFACTURER_LOGIN_URL = "${module.web.uri}/manufacturer-login"
  }
}

module "api" {
  source = "../cloud-run-service"

  deletion_protection   = local.deletion_protection
  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-api"
  service_account_email = module.service_accounts.emails["pod-admin-api"]
  labels                = local.labels

  cpu             = "1"
  memory          = "2Gi"
  min_instances   = var.api_min_instances
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
  source = "../cloud-run-service"

  deletion_protection   = local.deletion_protection
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
  source = "../cloud-run-job"

  deletion_protection   = local.deletion_protection
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
  source = "../cloud-run-job"

  deletion_protection   = local.deletion_protection
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
  source = "../scheduler"

  project_id            = var.project_id
  region                = var.region
  name                  = "pod-admin-worker"
  description           = "製造データ生成ワーカーの定期起動"
  job_name              = module.worker_job.name
  service_account_email = module.service_accounts.emails["pod-admin-scheduler"]
  schedule              = var.worker_schedule

  # **VM が未設定なら必ず止める。** 空の URL のまま動かすと、
  # run_generation が IllustratorVmError を投げ、待ち行列の行が次々に
  # failed へ落ちる（api/app/services/manufacturing_data_service.py）。
  # 2 つの設定が並んでいるだけでは、片方だけ変えた事故を防げない。
  paused = var.worker_schedule_paused || var.illustrator_vm_base_url == ""

  depends_on = [module.worker_job]
}
