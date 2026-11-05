# URL を定期的に POST する。Cloud Run Job の起動は ../scheduler を使う。
#
# 認証はヘッダで渡す（API の内部エンドポイントの共有シークレットなど）。
# **ヘッダの値は Terraform の state に平文で残る**（監視の Webhook のパスワードと同じ扱い）。
resource "google_cloud_scheduler_job" "this" {
  project     = var.project_id
  region      = var.region
  name        = var.name
  description = var.description
  schedule    = var.schedule
  time_zone   = "Asia/Tokyo"
  paused      = var.paused

  attempt_deadline = "60s"

  # 定期実行そのものが再試行の役目を果たすので、ここでは再試行しない。
  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = var.uri
    headers     = var.headers
  }
}
