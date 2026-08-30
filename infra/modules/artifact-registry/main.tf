resource "google_artifact_registry_repository" "this" {
  project       = var.project_id
  location      = var.region
  repository_id = var.name
  format        = "DOCKER"

  # **docker_config は宣言しない。** immutable_tags の既定は false で、
  # GCP の API は既定のときこのブロックを返さない。宣言すると、
  # **作りたての環境でだけ**「1 件 change」が出て 2 回 apply が要る
  # （state に入るまで差分が消えない）。タグはコミット SHA で使い回さないので、
  # immutable_tags を true にする実益も無い。
  description = var.description
  labels      = var.labels

  # 古いイメージを溜め込まない。keep が delete より優先されるので、直近 10 個は
  # 経過日数にかかわらず残る。
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.keep_recent_versions
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "${var.delete_older_than_days * 24}h"
    }
  }
}

# push できるのは CI だけにする。リポジトリ単位で付けるので、プロジェクト内の
# 他のリポジトリには届かない。
resource "google_artifact_registry_repository_iam_member" "writers" {
  for_each = toset(var.writer_members)

  project    = var.project_id
  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.name
  role       = "roles/artifactregistry.writer"
  member     = each.value
}
