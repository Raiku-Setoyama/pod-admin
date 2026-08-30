# modules/stack への切り出し（REQ-0054）に伴う state の移設。
#
# 切り出す前の state はリソースをルートモジュール直下に持っている。
# **この宣言が無いと、terraform は「全部消して作り直す」計画を出す。**
#
# 適用済みなので、いまは no-op である。**それでも残す理由は 1 つだけ：**
# state バケットはバージョニングが有効なので（ADR-0027）、切り出し前の
# バージョンに巻き戻せる。**巻き戻した state に対してこの宣言が無いと、
# 次の apply が 50 件超を作り直す。**
#
# 消してよいのは、切り出し前のバージョンを復元する見込みが無くなったとき
# （バケットの保持期間を過ぎたとき）である。

moved {
  from = module.services
  to   = module.stack.module.services
}

moved {
  from = module.service_accounts
  to   = module.stack.module.service_accounts
}

moved {
  from = module.artifact_registry
  to   = module.stack.module.artifact_registry
}

moved {
  from = module.github_oidc
  to   = module.stack.module.github_oidc
}

moved {
  from = module.gcs
  to   = module.stack.module.gcs
}

moved {
  from = module.cloud_sql
  to   = module.stack.module.cloud_sql
}

moved {
  from = module.secrets
  to   = module.stack.module.secrets
}

moved {
  from = module.api
  to   = module.stack.module.api
}

moved {
  from = module.web
  to   = module.stack.module.web
}

moved {
  from = module.migrate_job
  to   = module.stack.module.migrate_job
}

moved {
  from = module.worker_job
  to   = module.stack.module.worker_job
}

moved {
  from = module.worker_schedule
  to   = module.stack.module.worker_schedule
}

moved {
  from = random_password.secret_key
  to   = module.stack.random_password.secret_key
}

moved {
  from = random_password.internal_api_secret
  to   = module.stack.random_password.internal_api_secret
}

moved {
  from = google_service_account_iam_member.deployer_act_as
  to   = module.stack.google_service_account_iam_member.deployer_act_as
}

# github-oidc の for_each を set から map に変えたことによる添字の変更。
# **set のままだと、まだ何も無い環境で plan が通らない**（値が apply 時にしか
# 決まらないため、キーが確定しない）。ステージングは作成済みなので
# 気づけなかった。詳細は modules/github-oidc/variables.tf のコメント。
moved {
  from = module.stack.module.github_oidc.google_service_account_iam_member.impersonators["projects/tosyo-api-stg/serviceAccounts/pod-admin-deployer@tosyo-api-stg.iam.gserviceaccount.com"]
  to   = module.stack.module.github_oidc.google_service_account_iam_member.impersonators["pod-admin-deployer"]
}
