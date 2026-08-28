resource "google_sql_database_instance" "this" {
  project             = var.project_id
  name                = var.name
  region              = var.region
  database_version    = var.database_version
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.tier
    edition           = "ENTERPRISE"
    availability_type = var.availability_type
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb
    disk_autoresize   = true
    user_labels       = var.labels

    ip_configuration {
      # パブリック IP を有効にするが、authorized_networks は空のままにする。
      # 直接の TCP 接続はどこからもできず、到達経路は Cloud SQL Auth Proxy
      # （IAM 認証）だけになる。VPC を張らずに済ませるための構成（ADR-0026）。
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      start_time                     = var.backup_start_time_utc
      point_in_time_recovery_enabled = var.pitr_enabled
      transaction_log_retention_days = var.pitr_enabled ? var.transaction_log_retention_days : null
      backup_retention_settings {
        retained_backups = var.retained_backups
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = var.maintenance_day
      hour         = var.maintenance_hour_utc
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
