variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name" {
  description = "リポジトリ ID"
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "keep_recent_versions" {
  description = "経過日数にかかわらず残す直近バージョン数"
  type        = number
  default     = 10
}

variable "delete_older_than_days" {
  description = "この日数を過ぎたバージョンを削除する（keep_recent_versions が優先）"
  type        = number
  default     = 30
}
