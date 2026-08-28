variable "project_id" {
  type = string
}

variable "name" {
  description = "バケット名（グローバルに一意）"
  type        = string
}

variable "location" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "versioning" {
  description = "オブジェクトのバージョニング。誤削除・誤上書きからの復旧に要る"
  type        = bool
  default     = true
}

variable "retention_days" {
  description = <<-DESC
    現行オブジェクトを保持する日数。null ならルールを作らない。
    **使い捨て環境専用。** 本番で設定すると業務ファイルの実体が消え、
    DB に残った file_path が参照切れになる。
  DESC
  type        = number
  default     = null
}

variable "noncurrent_retention_days" {
  description = "旧バージョンを保持する日数。null ならルールを作らない"
  type        = number
  default     = null
}

variable "force_destroy" {
  description = "true にすると中身ごと destroy できる。本番では false のままにする"
  type        = bool
  default     = false
}

variable "object_admin_members" {
  description = "オブジェクトの読み書きを許可する IAM メンバー"
  type        = list(string)
  default     = []
}
