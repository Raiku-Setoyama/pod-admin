output "connection_name" {
  description = "<project>:<region>:<instance>。Cloud Run の Unix ソケット接続に使う"
  value       = google_sql_database_instance.this.connection_name
}

output "database_url" {
  description = <<-DESC
    Unix ソケット経由の接続文字列。asyncpg は `/` 始まりの host を
    ソケットディレクトリとして解釈する。
  DESC
  value       = "postgresql://${google_sql_user.this.name}:${random_password.user.result}@/${google_sql_database.this.name}?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
  sensitive   = true
}
