output "api_url" {
  description = "API の公開 URL"
  value       = module.api.uri
}

output "web_url" {
  description = "管理画面の公開 URL"
  value       = module.web.uri
}

output "next_public_api_url" {
  description = "web のイメージをビルドするときに渡す NEXT_PUBLIC_API_URL"
  value       = "${module.api.uri}/api/v1"
}

output "artifact_registry_url" {
  description = "docker push の宛先"
  value       = module.artifact_registry.repository_url
}

output "cloudsql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "gcs_bucket" {
  value = module.gcs.name
}
