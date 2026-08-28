resource "google_storage_bucket" "this" {
  project  = var.project_id
  name     = var.name
  location = var.location
  labels   = var.labels

  # UBLA。オブジェクト単位の ACL を禁止し、権限を IAM に一本化する。
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # 誤削除に備える。中身のあるバケットは destroy で消せない。
  force_destroy = var.force_destroy

  versioning {
    enabled = var.versioning
  }

  # 現行オブジェクトの削除。**使い捨て環境でしか有効にしてはならない。**
  # 業務ファイル（製造データ・請求書・チャット添付）は参照期限が読めないため、
  # 本番でこれを有効にすると DB に残った file_path が実体を失う。
  dynamic "lifecycle_rule" {
    for_each = var.retention_days == null ? [] : [1]
    content {
      action {
        type = "Delete"
      }
      condition {
        age = var.retention_days
      }
    }
  }

  # 上書き・削除で退いた旧バージョンの掃除。現行オブジェクトには当たらない。
  dynamic "lifecycle_rule" {
    for_each = var.noncurrent_retention_days == null ? [] : [1]
    content {
      action {
        type = "Delete"
      }
      condition {
        days_since_noncurrent_time = var.noncurrent_retention_days
        with_state                 = "ARCHIVED"
      }
    }
  }
}

resource "google_storage_bucket_iam_member" "object_admins" {
  for_each = toset(var.object_admin_members)

  bucket = google_storage_bucket.this.name
  role   = "roles/storage.objectAdmin"
  member = each.value
}
