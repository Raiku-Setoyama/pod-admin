output "network_name" {
  description = "Cloud Run の Direct VPC egress は network と subnetwork の両方を要る（省略すると default 網を指す）"
  value       = google_compute_network.this.name
}

output "illustrator_subnet_id" {
  description = "VM を置くサブネット。PR 2 で google_compute_instance に渡す"
  value       = google_compute_subnetwork.illustrator.id
}

output "run_subnet_id" {
  description = "Cloud Run の vpc_access に渡すサブネット。PR 2 で stack へ繋ぐまでは誰も使わない"
  value       = google_compute_subnetwork.run.id
}

output "illustrator_target_tag" {
  description = <<-DESC
    VM に付けるネットワークタグ。**PR 2 では値を直書きせず、必ずここから渡す。**
    付け忘れても apply は通り、到達できないという静かな形でしか表に出ない。
  DESC
  value       = local.illustrator_target_tag
}
