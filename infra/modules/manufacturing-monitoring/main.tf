# 製造データ生成の監視とアラート（2026-09-27〜10-02 の障害を受けて追加）。
#
# **何を防ぐか。** 当時は VM 上の生成 API が止まったまま 5 日間、誰も気づかなかった。
# ワーカーは注文が来たときしか生成に触れず、失敗は行に書かれるだけで、
# 人に届く経路が 1 つも無かったためである。生成をワーカーの中へ移した後（REQ-0067）も、
# 生成処理（VectorCraft）が壊れたときに同じことが起きうるので、同じ形で見張る。
#
# **見張り方は 2 通りある。**
# - 原因で見る: 生成処理の死活確認（ワーカーが 5 分ごとに VectorCraft を起動してみる）が NG 続き
# - 結果で見る: 生成待ちが動かない・生成が失敗した
# 結果で見る側は、原因を想定していない止まり方も拾う。両方を置く。
#
# **数えているのはワーカーのログの目印である**（app/worker.py の LOG_MARK_*、
# app/services/manufacturing_data_service.py の LOG_MARK_*）。
# **目印の文字列を変えたら、下のフィルタも同時に変える。** ずれても apply は通り、
# アラートが二度と鳴らなくなるという静かな形でしか表に出ない。
#
# **絞りが textPayload であることも同じ約束に含まれる。** ワーカーが構造化ログ（JSON）を
# 出すと中身は jsonPayload 側へ移り、下の指標は 1 件も当たらなくなる。ワーカーは
# Cloud Run Job で、書式を切り替える K_SERVICE が入らないためテキストのままになる
# （api/app/logging_config.py に同じことを書いてある）。
#
# **宛先は管理画面で設定する**（設定 → 製造データ生成のアラート）。アラートは Webhook で
# API の内部エンドポイントへ送り、API が app_settings の宛先へメールを送る。
# Terraform に宛先を書くと、宛先を変えるたびに apply が要るためである。
#
# **本番だけが呼ぶ。** ステージングの生成が止まっても人を呼ぶ必要は無い（ADR-0036 と同じ扱い）。

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
    generator_health_probe     = "generator_health status="
    generator_health_ng        = "generator_health status=ng"
    manufacturing_data_failed  = "manufacturing_data_failed"
    manufacturing_data_stalled = "manufacturing_data_stalled"
  }

  runbook = <<-EOT
    手順の正本は pod-admin の infra/README.md「製造データ生成が止まったとき」。

    1. ワーカー（Cloud Run Job）のログで `generator_health status=ng` の detail を確かめる
    2. 直前のデプロイで壊れたなら、ワーカーのイメージを 1 つ前のコミットに戻す
       （`gcloud run jobs update pod-admin-worker --image=.../worker:<前の SHA>`）
    3. 生成処理を起動できなかった生成は自動で再試行される（失敗にはならない）。
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

# 管理画面で設定した宛先へ送る経路。パスワードは API の INTERNAL_API_SECRET と同じ値で、
# API 側は Basic 認証のパスワードだけを照合する（ユーザー名は見ない）。
resource "google_monitoring_notification_channel" "webhook" {
  project      = var.project_id
  display_name = "製造データ生成アラート（管理画面で設定した宛先へ）"
  type         = "webhook_basicauth"
  labels = {
    url      = "${trimsuffix(var.api_url, "/")}/api/v1/internal/monitoring-alerts"
    username = "monitoring"
  }
  sensitive_labels {
    password = var.internal_api_secret
  }

  depends_on = [module.services]
}

resource "google_monitoring_notification_channel" "fallback_email" {
  for_each = toset(var.fallback_emails)

  project      = var.project_id
  display_name = "製造データ生成アラートの予備 (${each.value})"
  type         = "email"
  labels = {
    email_address = each.value
  }

  depends_on = [module.services]
}

locals {
  channels = [google_monitoring_notification_channel.webhook.id]

  # アラートのフィルタにはリソース種別の指定が必須である（無いと API が 400 を返す）。
  # ログベース指標は元ログのリソース種別の下に書かれ、ワーカーのログは cloud_run_job
  # （指標の記述子の monitoredResourceTypes で確認済み。2026-10-02）。
  # **ワーカーの実行基盤を変えたら、ここも変える。** ずれると鳴らなくなる。
  metric_resource_type = "cloud_run_job"

  # 指標の型。ログベース指標はこの名前で Monitoring に現れる。
  metric_type = { for k, m in google_logging_metric.this : k => "logging.googleapis.com/user/${m.name}" }
}

# ---- アラート ------------------------------------------------------------------
#
# 原因で見る: generator_down / worker_silent
# 結果で見る: generation_failed / generation_stalled（原因を問わず「発注できない」を拾う）
#
# worker_silent だけは「ログが途絶えた」を見るので condition_absent になる。
# 残りは「目印が閾値を超えた」なので同じ形で、下の map から作る。

locals {
  threshold_alerts = {
    # ワーカーは 5 分ごとに起動して生成処理を確かめる。15 分で 3 回 NG なら、
    # 一過性のものではなく壊れている。
    generator_down = {
      display_name   = "製造データの生成処理が動かない"
      condition_name = "generator_health が 15 分で 3 回 NG"
      metric         = "generator_health_ng"
      threshold      = 2
      window         = "900s"
      doc_prefix     = ""
    }
    # failed に確定した（入力の誤り、または生成処理を何度やっても起動できなかった）。
    # 管理画面では注文詳細の「要対応」にしか出ないので、ここで人に届ける。
    generation_failed = {
      display_name   = "製造データの生成が失敗した"
      condition_name = "manufacturing_data_failed が出た"
      metric         = "manufacturing_data_failed"
      threshold      = 0
      window         = "300s"
      doc_prefix     = "管理画面で「要対応」になった注文のエラー内容を確認し、元画像の差し替えか再生成を行う。"
    }
    # 生成待ちが長く動いていない（WORKER_STALL_ALERT_MINUTES、既定 60 分）。
    generation_stalled = {
      display_name   = "製造データが生成待ちのまま止まっている"
      condition_name = "manufacturing_data_stalled が出た"
      metric         = "manufacturing_data_stalled"
      threshold      = 0
      window         = "600s"
      doc_prefix     = ""
    }
  }
}

resource "google_monitoring_alert_policy" "threshold" {
  for_each = local.threshold_alerts

  project      = var.project_id
  display_name = each.value.display_name
  combiner     = "OR"

  conditions {
    display_name = each.value.condition_name
    condition_threshold {
      filter          = "metric.type=\"${local.metric_type[each.value.metric]}\" AND resource.type=\"${local.metric_resource_type}\""
      comparison      = "COMPARISON_GT"
      threshold_value = each.value.threshold
      duration        = "0s"
      aggregations {
        alignment_period     = each.value.window
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
    content   = trimspace("${each.value.doc_prefix}\n\n${local.runbook}")
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
    display_name = "generator_health のログが 30 分出ていない"
    condition_absent {
      filter   = "metric.type=\"${local.metric_type["generator_health_probe"]}\" AND resource.type=\"${local.metric_resource_type}\""
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

  # API・DB ごと止まっていると Webhook の先が受けられないので、予備の宛先にも直接送る。
  notification_channels = concat(
    local.channels,
    [for c in google_monitoring_notification_channel.fallback_email : c.id],
  )
}
