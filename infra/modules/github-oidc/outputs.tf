output "provider_name" {
  description = "ワークフローの workload_identity_provider に渡す完全修飾名"
  value       = google_iam_workload_identity_pool_provider.github.name
}
