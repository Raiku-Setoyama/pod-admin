output "emails" {
  description = "account_id → メールアドレス"
  value       = { for k, sa in google_service_account.this : k => sa.email }
}

output "members" {
  description = "account_id → IAM メンバー文字列（serviceAccount:...）"
  value       = { for k, sa in google_service_account.this : k => "serviceAccount:${sa.email}" }
}
