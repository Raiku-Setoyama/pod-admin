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
  workload_identity_pool_provider_id = "github"
  display_name                       = "github"
  description                        = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # **絞りは 2 段階とも必要である。**
  #
  # 1. リポジトリ — これが無いと、任意の GitHub リポジトリから同じ権限を借りられる。
  #    GitHub の OIDC トークンは全世界共通の発行者から出るため、
  #    「誰が持ってきたトークンか」をここで絞らないと事実上の公開になる（ADR-0028）
  # 2. ref — **リポジトリ条件だけでは足りない。** 同じリポジトリの他のワークフローも
  #    同じ条件を満たす。実際 .github/workflows/claude.yml は issue コメントを契機に
  #    id-token: write で動くので、そこからデプロイ用 SA を名乗れてしまう。
  #    main に限れば、経路は「人間がマージする」1 本になる（ADR-0031）
  #
  # ワークフロー側の書き方（push の対象ブランチなど）では守れない。
  # **ブランチに push できる者がその定義ごと差し替えられる**からである。
  attribute_condition = join(" && ", [
    "assertion.repository == '${var.github_repository}'",
    "assertion.ref == '${var.allowed_ref}'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# このリポジトリの Actions 実行だけが、指定したサービスアカウントを名乗れる。
resource "google_service_account_iam_member" "impersonators" {
  for_each = var.impersonated_service_account_ids

  service_account_id = each.value
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.this.name}/attribute.repository/${var.github_repository}"
}
