variable "project_id" { type = string }

variable "notification_emails" {
  description = <<-EOT
    アラートの宛先メールアドレス。**空にすると通知先のないアラートになる。**
    条件は評価され、コンソールには出るが、誰の手元にも届かない。
  EOT
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for e in var.notification_emails : can(regex("@", e))])
    error_message = "notification_emails にはメールアドレスを指定してください。"
  }
}

variable "api_service_name" {
  description = "監視対象の Cloud Run サービス名（API）"
  type        = string
}

variable "worker_job_name" {
  description = "監視対象の Cloud Run Job 名（製造データ生成ワーカー）"
  type        = string
}

variable "api_url" {
  description = <<-EOT
    API の公開 URL。外形監視（Uptime Check）の宛先になる。
    空なら外形監視を作らない。
  EOT
  type        = string
  default     = ""
}

variable "enabled" {
  description = <<-EOT
    false なら何も作らない。**ステージングで通知を鳴らさないための逃げ道である。**
    本番では true にすること。
  EOT
  type        = bool
  default     = true
}
