variable "project_id" {
  type = string
}

variable "github_repository" {
  description = "認証を許可するリポジトリ。owner/repo の形式で完全一致させる"
  type        = string

  validation {
    # 前方一致や部分一致にすると、似た名前のリポジトリから借りられてしまう。
    condition     = can(regex("^[^/[:space:]]+/[^/[:space:]]+$", var.github_repository))
    error_message = "github_repository は owner/repo の形式で指定してください。"
  }
}

variable "pool_id" {
  description = <<-DESC
    Workload Identity プール ID。
    **削除しても 30 日間は同じ ID を再作成できない**ため、使い回さない運用にする。
  DESC
  type        = string
  default     = "github"
}

variable "provider_id" {
  type    = string
  default = "github"
}

variable "impersonating_service_account_ids" {
  description = <<-DESC
    このリポジトリの Actions が名乗れるサービスアカウント。
    キーは表示用の名前、値は projects/<project>/serviceAccounts/<email> 形式の ID。
  DESC
  type        = map(string)
}
