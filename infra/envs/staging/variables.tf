variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-northeast1"
}

variable "gcs_bucket_name" {
  description = "業務ファイルの保管バケット（グローバルに一意）"
  type        = string
}

variable "db_tier" {
  type = string
}

variable "db_disk_size_gb" {
  type = number
}

variable "db_max_connections" {
  description = <<-DESC
    Cloud SQL の max_connections。明示的に固定する。
    ティアごとの既定値はメモリ量から算出されるため、値を仮定して
    プールを設計すると本番で枯渇する。
  DESC
  type        = number
}

variable "api_max_instances" {
  type = number
}

variable "web_max_instances" {
  type = number
}

variable "db_pool_size" {
  description = "1 インスタンスあたりの常設接続数"
  type        = number
}

variable "db_max_overflow" {
  description = "1 インスタンスあたりの追加接続数の上限"
  type        = number
}

variable "worker_max_runtime_seconds" {
  description = "ワーカーが 1 回の起動で処理を続ける上限秒数"
  type        = number
}

variable "worker_max_items" {
  type = number
}

variable "worker_schedule" {
  type = string
}

variable "worker_schedule_paused" {
  description = "true ならワーカーの定期起動を止めた状態で作る"
  type        = bool
}

variable "illustrator_vm_base_url" {
  description = "製造データ生成 VM の URL。空なら生成機能を無効にする"
  type        = string
  default     = ""
}

variable "sendgrid_from_email" {
  type    = string
  default = ""
}

variable "contact_email" {
  type    = string
  default = ""
}

variable "gcs_retention_days" {
  description = "アップロードしたファイルを保持する日数。null なら消さない"
  type        = number
  default     = null
}

variable "db_deletion_protection" {
  type = bool
}

variable "gcs_force_destroy" {
  type = bool
}
