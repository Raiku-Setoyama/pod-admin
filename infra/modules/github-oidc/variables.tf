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

variable "allowed_workflow" {
  description = <<-DESC
    トークンの発行を許可するワークフローファイルのパス。
    **同じリポジトリの別のワークフローを締め出すのがここの役目である。**
    再利用ワークフローを uses: で呼ぶ場合は、**呼ばれた側**を指定する。
  DESC
  type        = string
  default     = ".github/workflows/deploy.yml"
}

variable "allowed_ref" {
  description = <<-DESC
    トークンの発行を許可する git の ref。
    **これ単独では絞りにならない**（main.tf の attribute_condition を参照）。
    allowed_workflow と組にして job_workflow_ref を作るために持つ。
  DESC
  type        = string
  default     = "refs/heads/main"
}

variable "impersonated_service_account_ids" {
  description = <<-DESC
    このリポジトリの Actions が名乗れるサービスアカウント。
    キーは呼び出し側が静的に書ける名前、値は
    projects/<project>/serviceAccounts/<email> 形式の ID。

    **set ではなく map で受ける。** 値はサービスアカウントを作ってからでないと
    決まらないため、set にすると for_each のキーが plan の時点で確定しない。
    既に作り終えた環境では通ってしまい、**まだ何も無い環境（新しく作る本番）
    でだけ plan が落ちる。**
  DESC
  type        = map(string)
}
