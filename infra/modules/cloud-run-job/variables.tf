variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

variable "image" {
  description = "初回作成時のイメージ。以後はデプロイ側が入れる（ignore_changes）"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/job"
}

variable "service_account_email" { type = string }

variable "command" {
  description = "ENTRYPOINT の上書き。null ならイメージの既定を使う"
  type        = list(string)
  default     = null
}

variable "args" {
  type    = list(string)
  default = null
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

variable "timeout_seconds" {
  description = <<-DESC
    タスクのタイムアウト。**ワーカーの WORKER_MAX_RUNTIME_SECONDS より長くすること。**
    先に殺されると、生成中の行がリース期限まで宙吊りになる。
  DESC
  type        = number
}

variable "max_retries" {
  description = <<-DESC
    失敗時の再実行回数。ワーカーは次回起動が取りこぼしを拾うので 0 でよい。
    マイグレーションは冪等だが、失敗の原因が一過性とは限らないので 0 にする。
  DESC
  type        = number
  default     = 0
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
  type    = map(string)
  default = {}
}

variable "secret_env_vars" {
  description = "Secret Manager から注入する環境変数（環境変数名 → secret_id）"
  type        = map(string)
  default     = {}
}

variable "cloudsql_instances" {
  type    = list(string)
  default = []
}

variable "invoker_members" {
  description = "実行を許可する IAM メンバー（Cloud Scheduler の SA など）"
  type        = list(string)
  default     = []
}
