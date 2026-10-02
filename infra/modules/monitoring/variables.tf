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

variable "api_url" {
  description = "API の公開 URL。外形監視（Uptime Check）の宛先になる"
  type        = string
  default     = ""
}

variable "uptime_check_enabled" {
  description = <<-EOT
    外形監視を作るか。

    **`api_url` の中身では判断しない。** その値は Cloud Run サービスの属性なので、
    環境をゼロから作るとき（DR の再構築・別リージョン）には plan の時点で未確定であり、
    `count` に使うと `Invalid count argument` で plan ごと止まる。
    **最も必要なとき — 作り直しのとき — にだけ止まる**という壊れ方になる。
  EOT
  type        = bool
  default     = true
}

variable "enabled" {
  description = <<-EOT
    false なら何も作らない。**ステージングで通知を鳴らさないための逃げ道である。**
    本番では true にすること。
  EOT
  type        = bool
  default     = true
}
