variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name" {
  description = <<-DESC
    インスタンス名。**削除した名前は一定期間再利用できない。**
    作り直しが要るときは名前を変える運用にする。
  DESC
  type        = string
}

variable "tier" {
  type = string
}

variable "availability_type" {
  description = "ZONAL（非HA）または REGIONAL（HA）"
  type        = string
  default     = "ZONAL"
}

variable "disk_size_gb" {
  type = number
}

variable "disk_autoresize_limit" {
  description = <<-DESC
    自動拡張の上限（GB）。**0 は無制限であり、事故のとき歯止めが無くなる。**
    ディスクは縮小できないため、一度膨らんだ容量の課金は戻らない。
  DESC
  type        = number
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "database_name" {
  type = string
}

variable "user_name" {
  type = string
}

variable "pitr_enabled" {
  description = "ポイントインタイムリカバリ。有効にすると WAL の保管料がかかる"
  type        = bool
  default     = false
}

variable "retained_backups" {
  type    = number
  default = 7
}

variable "database_flags" {
  description = "データベースフラグ（例: { max_connections = \"50\" }）"
  type        = map(string)
  default     = {}
}
