variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

variable "image" {
  description = <<-DESC
    初回作成時のイメージ。以後は無視される（lifecycle.ignore_changes）ので、
    実運用のイメージはデプロイ側が入れる。既定は Google 公開のサンプル。
  DESC
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "service_account_email" { type = string }

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  description = <<-DESC
    最大インスタンス数。**DB 接続数の上限を決める要素である。**
    max_instances × (DB_POOL_SIZE + DB_MAX_OVERFLOW) が Cloud SQL の
    max_connections に収まること。
  DESC
  type        = number
}

variable "timeout_seconds" {
  type    = number
  default = 300
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_ALL"
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "env_vars" {
  description = "平文の環境変数"
  type        = map(string)
  default     = {}
}

variable "secret_env_vars" {
  description = "Secret Manager から注入する環境変数（環境変数名 → secret_id）"
  type        = map(string)
  default     = {}
}

variable "cloudsql_instances" {
  description = "接続する Cloud SQL の connection_name。空なら Unix ソケットを張らない"
  type        = list(string)
  default     = []
}

variable "startup_probe_path" {
  description = "起動確認に使う HTTP パス。null ならプローブを付けない"
  type        = string
  default     = null
}

variable "invoker_members" {
  description = "呼び出しを許可する IAM メンバー。公開する場合は allUsers"
  type        = list(string)
  default     = []
}
