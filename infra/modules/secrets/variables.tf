variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "managed_secrets" {
  description = "Terraform が値を持つシークレット（secret_id → 値）"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "external_secrets" {
  description = <<-DESC
    値を人間が入れるシークレット（secret_id → 初期プレースホルダ）。
    Terraform は初回バージョンだけ作り、以後の値の変更は追跡しない。
  DESC
  type        = map(string)
  default     = {}
}

variable "accessor_members" {
  description = "全シークレットの読み取りを許可する IAM メンバー"
  type        = list(string)
  default     = []
}
