# modules/stack の出力の素通し。**説明は modules/stack/outputs.tf が正本。**

output "api_url" {
  value = module.stack.api_url
}

output "web_url" {
  value = module.stack.web_url
}

output "next_public_api_url" {
  value = module.stack.next_public_api_url
}

output "artifact_registry_url" {
  value = module.stack.artifact_registry_url
}

output "cloudsql_connection_name" {
  value = module.stack.cloudsql_connection_name
}

output "gcs_bucket" {
  value = module.stack.gcs_bucket
}

output "github_actions_workload_identity_provider" {
  value = module.stack.github_actions_workload_identity_provider
}

output "github_actions_service_account" {
  value = module.stack.github_actions_service_account
}
