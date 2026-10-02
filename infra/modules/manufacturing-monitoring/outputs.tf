output "alert_policy_names" {
  description = "作成したアラートポリシー（動作確認でコンソールから辿る用）"
  value = concat(
    [for p in google_monitoring_alert_policy.threshold : p.name],
    [google_monitoring_alert_policy.worker_silent.name],
  )
}
