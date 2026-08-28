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


variable "paused" {
  description = "true なら停止した状態で作る"
  type        = bool
  default     = false
}


