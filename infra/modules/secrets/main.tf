locals {
  # 値だけが機密であり、secret_id は機密ではない。for_each のキーは
  # リソースアドレスになるため、ここで明示的にマークを外す。
  managed_secret_ids = nonsensitive(keys(var.managed_secrets))
  all_secret_ids     = concat(local.managed_secret_ids, keys(var.external_secrets))
}

resource "google_secret_manager_secret" "this" {
  for_each = toset(local.all_secret_ids)

  project   = var.project_id
  secret_id = each.value
  labels    = var.labels

  # 保管先をリージョンに固定する。自動レプリケーションだと配置が読めない。
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

# Terraform が値を持つシークレット。値が変われば新しいバージョンが作られる。
resource "google_secret_manager_secret_version" "managed" {
  for_each = toset(local.managed_secret_ids)

  secret      = google_secret_manager_secret.this[each.value].id
  secret_data = var.managed_secrets[each.value]
}

# 値を人間が入れるシークレット。Terraform は入れ物と初期のプレースホルダだけ作る。
#
# ignore_changes を付ける理由: 実際の値は `gcloud secrets versions add` で
# 追加される。Cloud Run は `latest` を参照するのでそれが使われるが、
# ここを無視しないと Terraform が毎回「プレースホルダに戻す」差分を出す。
resource "google_secret_manager_secret_version" "external" {
  for_each = var.external_secrets

  secret      = google_secret_manager_secret.this[each.key].id
  secret_data = each.value

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each = {
    for pair in setproduct(local.all_secret_ids, var.accessor_members) :
    "${pair[0]}:${pair[1]}" => { secret = pair[0], member = pair[1] }
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}
