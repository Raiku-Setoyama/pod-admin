variable "project_id" { type = string }

variable "worker_job_name" {
  description = "製造データ生成ワーカーの Cloud Run Job 名。ログの絞り込みに使う"
  type        = string
}

variable "alert_emails" {
  description = "アラートを受け取るメールアドレス"
  type        = list(string)

  validation {
    condition     = length(var.alert_emails) > 0
    error_message = "宛先が空だとアラートはどこにも届かない。少なくとも 1 つ指定する。"
  }
}
