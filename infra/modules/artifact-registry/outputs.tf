output "repository_url" {
  description = "docker push の宛先（<region>-docker.pkg.dev/<project>/<repo>）"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.this.repository_id}"
}
