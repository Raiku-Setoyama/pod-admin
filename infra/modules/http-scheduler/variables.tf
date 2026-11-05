variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

variable "description" {
  type    = string
  default = ""
}

variable "uri" {
  description = "POST する URL"
  type        = string
}

variable "headers" {
  description = "リクエストヘッダ（認証用の共有シークレットなど）"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "schedule" {
  description = "cron 形式（Asia/Tokyo）"
  type        = string
}

variable "paused" {
  description = "true なら停止した状態で作る"
  type        = bool
  default     = false
}
