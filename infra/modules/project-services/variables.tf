variable "project_id" {
  description = "対象の GCP プロジェクト ID"
  type        = string
}

variable "services" {
  description = "有効化する API のリスト（例: run.googleapis.com）"
  type        = list(string)
}
