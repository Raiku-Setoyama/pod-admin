output "enabled" {
  description = "有効化した API。他のモジュールが depends_on で待つために使う"
  value       = [for s in google_project_service.this : s.service]
}
