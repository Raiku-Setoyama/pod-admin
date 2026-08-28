locals {
  # 環境で変える理由がないもの。変える必要が出たら変数に引き上げる。
  backup_start_time_utc          = "18:00" # JST 03:00
  maintenance_day                = 7       # 日曜
  maintenance_hour_utc           = 18      # JST 03:00
  transaction_log_retention_days = 7
}

resource "google_sql_database_instance" "this" {
  project             = var.project_id
  name                = var.name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    edition           = "ENTERPRISE"
    availability_type = var.availability_type
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb

    # 自動拡張には必ず上限を付ける。**ディスクは拡張できても縮小できない。**
    # 暴走したログや誤ったインポートで一度膨らむと、インスタンスを作り直すまで
    # その容量の課金が続く（名前の再利用にも待ち時間がある）。
    disk_autoresize       = true
    disk_autoresize_limit = var.disk_autoresize_limit
    user_labels           = var.labels

    ip_configuration {
      # パブリック IP を有効にするが、authorized_networks は空のままにする。
      # 直接の TCP 接続はどこからもできず、到達経路は Cloud SQL Auth Proxy
      # （IAM 認証）だけになる。VPC を張らずに済ませるための構成（ADR-0026）。
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      start_time                     = local.backup_start_time_utc
      point_in_time_recovery_enabled = var.pitr_enabled
      transaction_log_retention_days = var.pitr_enabled ? local.transaction_log_retention_days : null
      backup_retention_settings {
        retained_backups = var.retained_backups
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = local.maintenance_day
      hour         = local.maintenance_hour_utc
      update_track = "stable"
    }

    dynamic "database_flags" {
      for_each = var.database_flags
      content {
        name  = database_flags.key
        value = database_flags.value
      }
    }
  }
}

resource "google_sql_database" "this" {
  project  = var.project_id
  instance = google_sql_database_instance.this.name
  name     = var.database_name
}

# パスワードに URL の予約文字を入れない。DATABASE_URL に素で埋め込むため、
# パーセントエンコードが要る文字が混ざると接続文字列が壊れる。
resource "random_password" "user" {
  length           = 32
  special          = true
  override_special = "-_.~"
}

resource "google_sql_user" "this" {
  project  = var.project_id
  instance = google_sql_database_instance.this.name
  name     = var.user_name
  password = random_password.user.result
}
