output "notification_channel_ids" {
  description = "作成した通知チャンネルの ID（他のアラートから使い回す用）"
  value       = local.channel_ids
}

output "has_notification_channel" {
  description = <<-EOT
    通知先があるか。**false ならアラートは 1 本も作られていない。**
    呼び出し側がこれを出力に出して、気づけるようにすること。
  EOT
  value       = local.has_channel
}
