# Cloud Run Job を定期起動する。Job 自体には呼び出し権限が要るため、
# cloud-run-job モジュールの invoker_members に、この SA を渡しておくこと。
resource "google_cloud_scheduler_job" "this" {
  project     = var.project_id
  region      = var.region
  name        = var.name
  description = var.description
  schedule    = var.schedule
  time_zone   = "Asia/Tokyo"
  paused      = var.paused

  # Job の完了ではなく **起動 API の応答** を待つ時間なので、Job の
  # タイムアウトと揃える必要はない。
  attempt_deadline = "60s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${var.job_name}:run"

    oauth_token {
      service_account_email = var.service_account_email
    }
  }
}
