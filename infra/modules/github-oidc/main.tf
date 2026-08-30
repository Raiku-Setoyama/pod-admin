locals {
  # GitHub の job_workflow_ref クレームと同じ形（owner/repo/パス@ref）。
  job_workflow_ref = "${var.github_repository}/${var.allowed_workflow}@${var.allowed_ref}"
}

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
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.job_workflow_ref" = "assertion.job_workflow_ref"
  }

  # **絞りは 2 段階とも必要である。**
  #
  # 1. リポジトリ — 無いと任意の GitHub リポジトリから借りられる（ADR-0028）
  # 2. **job_workflow_ref — どのワークフローの実行かまで絞る**
  #
  # 2 が ref ではなく job_workflow_ref なのには理由がある。**ref では防げない。**
  # issue_comment / issues を契機に動くワークフロー（.github/workflows/claude.yml は
  # id-token: write を持つ）では、GitHub が ref に**既定ブランチ**を入れる。
  # マージは起きていないのに `refs/heads/main` になるので、
  # `assertion.ref == 'refs/heads/main'` は素通しになる（ADR-0033）。
  #
  # job_workflow_ref は「owner/repo/パス@ref」の 1 つのクレームに
  # リポジトリ・ワークフローファイル・ref の 3 つが入る。再利用ワークフローを
  # uses: で呼んだジョブでは、**呼ばれた側**（deploy.yml）の値になる。
  attribute_condition = join(" && ", [
    "assertion.repository == '${var.github_repository}'",
    "assertion.job_workflow_ref == '${local.job_workflow_ref}'",
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
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.this.name}/attribute.job_workflow_ref/${local.job_workflow_ref}"
}
