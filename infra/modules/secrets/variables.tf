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

  validation {
    # Secret Manager は空のペイロードを受け付けない
    # （API が「Field [payload] is required」で 400 を返す）。
    # 「値が無い」を空文字で表せないため、必ず何かを入れる。
    condition     = alltrue([for v in values(var.external_secrets) : length(v) > 0])
    error_message = "external_secrets のプレースホルダに空文字は使えません。Secret Manager が空のペイロードを拒否します。"
  }
}

variable "accessor_members" {
  description = "全シークレットの読み取りを許可する IAM メンバー"
  type        = list(string)
  default     = []
}
