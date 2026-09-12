output "notification_channel_ids" {
  description = "作成した通知チャンネルの ID（他のアラートから使い回す用）"
  value       = local.channel_ids
}

output "alerting_active" {
  description = <<-EOT
    アラートが実際に作られているか。**false なら誰にも通知が届かない。**

    **入力からではなく、作られた実体から導く。** 入力（通知先の有無）から導くと、
    monitoring_enabled = false で通知先だけ設定されている環境で true を返し、
    **「監視してあるはず」を否定するための唯一の仕掛けが、それ自身で嘘をつく。**
  EOT
  value       = length(google_monitoring_alert_policy.vm_unreachable) > 0
}
