variable "project_id" { type = string }

variable "worker_job_name" {
  description = "製造データ生成ワーカーの Cloud Run Job 名。ログの絞り込みに使う"
  type        = string
}

variable "api_url" {
  description = "API の公開 URL。アラートの Webhook（/api/v1/internal/monitoring-alerts）の宛先になる"
  type        = string
}

variable "internal_api_secret" {
  description = "API の内部エンドポイントの共有シークレット（INTERNAL_API_SECRET）。Webhook の Basic 認証のパスワードに使う"
  type        = string
  sensitive   = true
}

variable "fallback_emails" {
  description = <<-EOT
    「ワーカーが動いていない」アラートだけを、API を経由せず Monitoring から直接送る宛先。
    通常の宛先は管理画面で設定する（API が送る）。API や DB ごと止まっているときは
    API が送れないので、この 1 本だけは経路を分けておく。
  EOT
  type        = list(string)

  validation {
    condition     = length(var.fallback_emails) > 0
    error_message = "API ごと止まったときに誰にも届かなくなる。予備の宛先を少なくとも 1 つ指定する。"
  }
}
