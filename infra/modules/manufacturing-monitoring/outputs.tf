output "alert_policy_names" {
  description = "作成したアラートポリシー（動作確認でコンソールから辿る用）"
  value = [
    google_monitoring_alert_policy.vm_down.name,
    google_monitoring_alert_policy.worker_silent.name,
    google_monitoring_alert_policy.generation_failed.name,
    google_monitoring_alert_policy.generation_stalled.name,
  ]
}
