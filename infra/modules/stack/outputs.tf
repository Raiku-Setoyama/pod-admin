# **ここに出力を足したら infra/envs/*/outputs.tf の全環境に同じものを足す。**
# env 側は module.stack.* をそのまま素通しするだけの手書きの写しであり、
# Terraform に取り込みの仕組みが無いので機械的には揃わない。
# 片方だけに足すと、infra/README.md が「どちらの環境でも実行できる」としている
# terraform output の手順が、その環境でだけ失敗する。

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

output "github_actions_workload_identity_provider" {
  description = "デプロイ用ワークフローの workload_identity_provider に指定する値"
  value       = module.github_oidc.provider_name
}

output "github_actions_service_account" {
  description = "デプロイ用ワークフローの service_account に指定する値"
  value       = module.service_accounts.emails["pod-admin-deployer"]
}
