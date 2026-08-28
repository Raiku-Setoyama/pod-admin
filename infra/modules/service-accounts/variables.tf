variable "project_id" {
  description = "対象の GCP プロジェクト ID"
  type        = string
}

variable "accounts" {
  description = <<-DESC
    作成するサービスアカウント。キーが account_id になる。
    project_roles にはプロジェクト全体に付けるロールだけを書く。
    バケット単位・シークレット単位の権限は、それぞれのモジュール側で付ける。
  DESC
  type = map(object({
    display_name  = string
    description   = string
    project_roles = list(string)
  }))
}
