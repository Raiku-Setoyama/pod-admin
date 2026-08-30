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

variable "allowed_ref" {
  description = <<-DESC
    トークンの発行を許可する git の ref。**リポジトリ条件だけでは足りない。**
    同じリポジトリの別のワークフロー（例: .github/workflows/claude.yml は
    issue コメントを契機に id-token: write で動く）も同じ条件を満たすため、
    ここで実行の出どころまで絞る。
  DESC
  type        = string
  default     = "refs/heads/main"
}

variable "impersonated_service_account_ids" {
  description = <<-DESC
    このリポジトリの Actions が名乗れるサービスアカウント。
    projects/<project>/serviceAccounts/<email> 形式の ID を入れる。
  DESC
  type        = set(string)
}
