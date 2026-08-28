resource "google_service_account" "this" {
  for_each = var.accounts

  project      = var.project_id
  account_id   = each.key
  display_name = each.value.display_name
  description  = each.value.description
}

locals {
  # {SA キー}:{ロール} を一意キーにして展開する。for_each はフラットなマップしか
  # 取れないため、二重ループを merge で畳む。
  project_role_bindings = merge([
    for sa_key, sa in var.accounts : {
      for role in sa.project_roles :
      "${sa_key}:${role}" => { account = sa_key, role = role }
    }
  ]...)
}

# 追加的（authoritative でない）バインディングを使う。google_project_iam_binding だと
# 同じロールに付いている他のメンバーを消してしまう。
resource "google_project_iam_member" "this" {
  for_each = local.project_role_bindings

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.this[each.value.account].email}"
}
