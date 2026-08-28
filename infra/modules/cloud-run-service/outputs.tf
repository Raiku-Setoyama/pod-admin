output "uri" {
  description = "公開 URL"
  value       = google_cloud_run_v2_service.this.uri
}

output "urls" {
  description = <<-DESC
    Cloud Run がこのサービスに割り当てた **すべての** URL。
    1 サービスに 2 つ付く（`<service>-<hash>-<region>.a.run.app` と
    `<service>-<project number>.<region>.run.app`）。**uri はそのうち 1 つしか返さない。**
    CORS の許可元のように「利用者がどちらで来ても通す」必要があるものはこちらを使う。
  DESC
  value       = sort(google_cloud_run_v2_service.this.urls)
}
