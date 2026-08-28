# GitHub Actions を GCP に認証させるための連携（ADR-0028）。
# **サービスアカウントの鍵 JSON は作らない。** GitHub が実行のたびに発行する
# 短命なトークンを GCP 側で検証し、その場でサービスアカウントの権限を貸す。

resource "google_iam_workload_identity_pool" "this" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = var.pool_id
  description               = "GitHub Actions からの認証を受け付ける"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.this.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = var.provider_id
  description                        = "GitHub Actions OIDC"

  # principalSet でリポジトリ単位に絞れるようにするため、repository を属性として取り出す。
  # ref も写しておく。将来ブランチや環境で絞るときに、プロバイダを作り直さずに済む。
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # **この条件が無いと、任意の GitHub リポジトリから同じ権限を借りられる**（ADR-0028）。
  # GitHub の OIDC トークンは全世界共通の発行者から出るため、
  # 「誰が持ってきたトークンか」をここで絞らないと事実上の公開になる。
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# このリポジトリの Actions 実行だけが、指定したサービスアカウントを名乗れる。
resource "google_service_account_iam_member" "impersonators" {
  for_each = var.impersonating_service_account_ids

  service_account_id = each.value
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.this.name}/attribute.repository/${var.github_repository}"
}
