variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name" {
  description = <<-DESC
    インスタンス名。**削除した名前は一定期間再利用できない。**
    作り直しが要るときは名前を変える運用にする。
  DESC
  type        = string
}

variable "database_version" {
  type    = string
  default = "POSTGRES_16"
}

variable "tier" {
  type = string
}

variable "availability_type" {
  description = "ZONAL（非HA）または REGIONAL（HA）"
  type        = string
  default     = "ZONAL"
}

variable "disk_size_gb" {
  type = number
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "database_name" {
  type = string
}

variable "user_name" {
  type = string
}

variable "pitr_enabled" {
  description = "ポイントインタイムリカバリ。有効にすると WAL の保管料がかかる"
  type        = bool
  default     = false
}

variable "transaction_log_retention_days" {
  type    = number
  default = 7
}

variable "retained_backups" {
  type    = number
  default = 7
}

variable "backup_start_time_utc" {
  description = "自動バックアップの開始時刻（UTC, HH:MM）"
  type        = string
  default     = "18:00"
}

variable "maintenance_day" {
  description = "メンテナンス枠の曜日（1=月 ... 7=日）"
  type        = number
  default     = 7
}

variable "maintenance_hour_utc" {
  description = "メンテナンス枠の時刻（UTC）。18 は JST 03:00"
  type        = number
  default     = 18
}

variable "database_flags" {
  description = "データベースフラグ（例: { max_connections = \"50\" }）"
  type        = map(string)
  default     = {}
}
