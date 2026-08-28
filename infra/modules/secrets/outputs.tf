output "secret_ids" {
  description = "作成したシークレットの secret_id"
  value       = [for s in google_secret_manager_secret.this : s.secret_id]
}
