# 製造データ生成の監視とアラート（2026-09-27〜10-02 の障害を受けて追加）。
#
# **何を防ぐか。** VM 上の生成 API が止まったまま 5 日間、誰も気づかなかった。
# ワーカーは注文が来たときしか VM に触れず、失敗は行に書かれるだけで、
# 人に届く経路が 1 つも無かったためである。
#
# **見張り方は 2 通りある。**
# - 原因で見る: VM の死活確認（ワーカーが 5 分ごとに /health を叩く）が NG 続き
# - 結果で見る: 生成待ちが動かない・生成が失敗した
# 結果で見る側は、原因を想定していない止まり方も拾う。両方を置く。
#
# **数えているのはワーカーのログの目印である**（app/worker.py の LOG_MARK_*、
# app/services/manufacturing_data_service.py の LOG_MARK_*）。
# **目印の文字列を変えたら、下のフィルタも同時に変える。** ずれても apply は通り、
# アラートが二度と鳴らなくなるという静かな形でしか表に出ない。
#
# **本番だけが呼ぶ。** 製造データ生成 VM は本番にしか無い（ADR-0036 と同じ扱い）。

module "services" {
  source = "../project-services"

  project_id = var.project_id
  services   = ["monitoring.googleapis.com"]
}

locals {
  worker_logs = join(" AND ", [
    "resource.type=\"cloud_run_job\"",
    "resource.labels.job_name=\"${var.worker_job_name}\"",
  ])

  # 指標名 => 数える目印
  log_metrics = {
    illustrator_vm_health_probe = "illustrator_vm_health status="
    illustrator_vm_health_ng    = "illustrator_vm_health status=ng"
    manufacturing_data_failed   = "manufacturing_data_failed"
    manufacturing_data_stalled  = "manufacturing_data_stalled"
  }

  runbook = <<-EOT
    手順の正本は pod-admin の infra/README.md「製造データ生成が止まったとき」。

    1. 生成 API の生死を確かめる（IAP トンネル越しに /health）
    2. 応答しなければ VM の中の監視タスク（IllustratorAPIWatchdog）が数分で起動し直す。
       10 分以上戻らなければ `gcloud compute instances reset illustrator-vm` で VM を再起動する
    3. VM に届かなかった生成は自動で再試行される（失敗にはならない）。
       「要対応」になったものだけ、管理画面から再生成する
  EOT
}

resource "google_logging_metric" "this" {
  for_each = local.log_metrics

  project = var.project_id
  name    = each.key
  filter  = "${local.worker_logs} AND textPayload:\"${each.value}\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_notification_channel" "email" {
  for_each = toset(var.alert_emails)

  project      = var.project_id
  display_name = "製造データ生成アラート (${each.value})"
  type         = "email"
  labels = {
    email_address = each.value
  }

  depends_on = [module.services]
}

locals {
  channels = [for c in google_monitoring_notification_channel.email : c.id]

  # **リソース種別では絞らない。** ログベース指標がどの監視対象リソースの下に
  # 書かれるかは元ログの種別に依存し、保証されていない。絞り込みがずれると
  # 「失敗しても鳴らない／ワーカーが動いていないと鳴り続ける」になる。
  # ワーカーのログへの絞り込みは指標の側（google_logging_metric の filter）で済ませている。

  # 指標の型。ログベース指標はこの名前で Monitoring に現れる。
  metric_type = { for k, m in google_logging_metric.this : k => "logging.googleapis.com/user/${m.name}" }
}

# ---- 原因で見る ---------------------------------------------------------------

# ワーカーは 5 分ごとに起動して /health を叩く。15 分で 3 回 NG なら、
# 一過性の瞬断ではなく止まっている。
resource "google_monitoring_alert_policy" "vm_down" {
  project      = var.project_id
  display_name = "製造データ生成 VM が応答しない"
  combiner     = "OR"

  conditions {
    display_name = "illustrator_vm_health が 15 分で 3 回 NG"
    condition_threshold {
      filter          = "metric.type=\"${local.metric_type["illustrator_vm_health_ng"]}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2
      duration        = "0s"
      aggregations {
        alignment_period     = "900s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = local.runbook
  }

  notification_channels = local.channels
}

# 死活確認のログそのものが途絶えた＝ワーカーが動いていない。
# **Scheduler を止めたまま戻し忘れた場合もここで鳴る**（保守のために止めるのは正しいが、
# 戻し忘れると生成が黙って止まる。infra/README.md の手順はその間 30 分以内に戻す前提）。
resource "google_monitoring_alert_policy" "worker_silent" {
  project      = var.project_id
  display_name = "製造データ生成ワーカーが動いていない"
  combiner     = "OR"

  conditions {
    display_name = "illustrator_vm_health のログが 30 分出ていない"
    condition_absent {
      filter   = "metric.type=\"${local.metric_type["illustrator_vm_health_probe"]}\""
      duration = "1800s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Cloud Scheduler `${var.worker_job_name}` が ENABLED か、Cloud Run Job の実行が失敗していないかを確認する。\n\n${local.runbook}"
  }

  notification_channels = local.channels
}

# ---- 結果で見る ---------------------------------------------------------------

# 生成が failed に確定した（入力の誤り、または VM に何度やっても届かなかった）。
# 管理画面では注文詳細の「要対応」にしか出ないので、ここで人に届ける。
resource "google_monitoring_alert_policy" "generation_failed" {
  project      = var.project_id
  display_name = "製造データの生成が失敗した"
  combiner     = "OR"

  conditions {
    display_name = "manufacturing_data_failed が出た"
    condition_threshold {
      filter          = "metric.type=\"${local.metric_type["manufacturing_data_failed"]}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "管理画面で「要対応」になった注文のエラー内容を確認し、元画像の差し替えか再生成を行う。\n\n${local.runbook}"
  }

  notification_channels = local.channels
}

# 生成待ちが長く動いていない（WORKER_STALL_ALERT_MINUTES、既定 60 分）。
# 原因を問わず「発注できない状態が続いている」ことを拾う最後の網。
resource "google_monitoring_alert_policy" "generation_stalled" {
  project      = var.project_id
  display_name = "製造データが生成待ちのまま止まっている"
  combiner     = "OR"

  conditions {
    display_name = "manufacturing_data_stalled が出た"
    condition_threshold {
      filter          = "metric.type=\"${local.metric_type["manufacturing_data_stalled"]}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "600s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = local.runbook
  }

  notification_channels = local.channels
}
