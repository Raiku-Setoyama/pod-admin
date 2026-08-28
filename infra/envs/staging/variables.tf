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

variable "db_disk_autoresize_limit" {
  description = "ディスク自動拡張の上限（GB）。0 は無制限"
  type        = number
}

variable "db_max_connections" {
  description = <<-DESC
    Cloud SQL の max_connections。明示的に固定する。
    ティアごとの既定値はメモリ量から算出されるため、値を仮定して
    プールを設計すると本番で枯渇する。
  DESC
  type        = number

  validation {
    # 接続数の予算を人間の暗算に任せない。
    # api は max_instances 個まで並ぶ。worker と migrate は Job なので 1 実行ずつ。
    # 残りは管理接続（psql・Cloud SQL 自身）の予備として空けておく。
    condition = (
      (var.api_max_instances + 2) * (var.db_pool_size + var.db_max_overflow)
      <= var.db_max_connections - 5
    )
    error_message = "接続数が max_connections に収まりません。(api_max_instances + 2) × (db_pool_size + db_max_overflow) が db_max_connections - 5 を超えています。"
  }
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

variable "github_repository" {
  description = "デプロイを許可する GitHub リポジトリ（owner/repo）"
  type        = string
}
