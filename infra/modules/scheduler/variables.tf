variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

variable "description" {
  type    = string
  default = ""
}

variable "job_name" {
  description = "起動する Cloud Run Job の名前"
  type        = string
}

variable "service_account_email" {
  description = "起動に使う SA。対象の Job に roles/run.invoker が要る"
  type        = string
}

variable "schedule" {
  description = "cron 形式"
  type        = string
}

variable "time_zone" {
  type    = string
  default = "Asia/Tokyo"
}

variable "paused" {
  description = "true なら停止した状態で作る"
  type        = bool
  default     = false
}

variable "attempt_deadline_seconds" {
  description = <<-DESC
    1 回の起動リクエストの締め切り。Job の実行完了ではなく **起動 API の応答** を
    待つ時間なので、Job のタイムアウトと合わせる必要はない。
  DESC
  type        = number
  default     = 60
}

variable "retry_count" {
  description = "起動 API が失敗したときの再試行回数"
  type        = number
  default     = 1
}
