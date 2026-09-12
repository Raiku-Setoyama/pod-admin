# 監視と通知。
#
# **これが無い間、本番は「静かに壊れる」構成だった。** 製造データ生成 VM が止まっても、
# ワーカーが失敗し続けても、API が 5xx を返し続けても、画面にエラーは出ない。
# 気づく手段は「発注できないという問い合わせ」しかなかった（REQ-0063）。
#
# 監視の対象は 3 層ある。**どれか 1 つでは足りない。**
#
# | 層 | 何を見るか | これだけでは足りない理由 |
# |---|---|---|
# | 外形 | API が外から応答するか | 製造データ生成は API を通らない |
# | ジョブ | ワーカーが完走しているか | 完走しても中身が全部失敗していることがある |
# | ログ | 生成が失敗・再試行しているか | 受注が無ければログも出ない |
#
# **VM を直接叩く死活監視は置いていない。** REQ-0055 で外部 IP を外したので、
# Uptime Check の probe は公衆網から `10.20.0.10` に到達できない。代わりに、
# VPC 内から VM を叩く唯一の経路（ワーカー）が残すログを見る。
# ワーカーが到達不能を報告した時点で、VM が落ちていることは確定している。

locals {
  enabled = var.enabled

  # 通知先が無ければアラートは作らない。**鳴らないアラートを置くほうが危険である。**
  # 「監視してあるはず」という思い込みだけが残るため。
  has_channel = length(var.notification_emails) > 0

  make_alerts = local.enabled && local.has_channel ? 1 : 0
  make_uptime = local.enabled && var.api_url != "" ? 1 : 0

  channel_ids = [for c in google_monitoring_notification_channel.email : c.id]

  # Uptime Check はホスト名だけを取る（scheme とパスは別のフィールド）。
  api_host = local.make_uptime == 1 ? replace(replace(var.api_url, "https://", ""), "/", "") : ""
}

resource "google_monitoring_notification_channel" "email" {
  for_each = local.enabled ? toset(var.notification_emails) : toset([])

  project      = var.project_id
  display_name = "POD Admin アラート (${each.value})"
  type         = "email"

  labels = {
    email_address = each.value
  }
}

# --- ログベースの指標 -------------------------------------------------------
#
# **ワーカーが JSON 構造化ログを出していることに依存している**
# （api/app/logging_config.py）。素の stderr のままだと severity が付かず、
# 下の filter は当たらない。片方だけ直すと静かに効かなくなる。

resource "google_logging_metric" "vm_unreachable" {
  count = local.enabled ? 1 : 0

  project = var.project_id
  name    = "pod_admin/mfg_vm_unreachable"
  description = join("", [
    "製造データ生成 VM に届かなかった回数。",
    "ワーカーが再試行を予定した（= VM が落ちている疑い）ときに 1 増える。",
  ])

  # 文言は api/app/services/manufacturing_data_service.py の _handle_failure が出すもの。
  # **両方を同時に直すこと。** 片方だけ変えても apply は通り、アラートだけが黙る。
  filter = join(" AND ", [
    "resource.type=\"cloud_run_job\"",
    "jsonPayload.logger=\"app.services.manufacturing_data_service\"",
    "jsonPayload.message=~\"could not reach the VM\"",
  ])

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "generation_failed" {
  count = local.enabled ? 1 : 0

  project     = var.project_id
  name        = "pod_admin/mfg_generation_failed"
  description = "製造データ生成が failed で終わった回数（入力の誤り、または再試行の上限）。"

  filter = join(" AND ", [
    "resource.type=\"cloud_run_job\"",
    "jsonPayload.logger=\"app.services.manufacturing_data_service\"",
    "jsonPayload.message=~\"manufacturing data generation failed\"",
  ])

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# --- アラート ---------------------------------------------------------------

# **これが最優先である。** 製造データが作れなければ発注が止まり、業務が止まる。
resource "google_monitoring_alert_policy" "vm_unreachable" {
  count = local.make_alerts

  project      = var.project_id
  display_name = "製造データ生成VMに届いていない"
  combiner     = "OR"

  documentation {
    content = join("\n", [
      "製造データ生成 VM（illustrator-vm）に到達できていません。",
      "",
      "**受注は止まりません。** 生成待ちの行は `pending` のまま残り、VM が戻れば",
      "ワーカーが自動で作り直します（再試行の上限に達した分は `failed` になります）。",
      "",
      "確認の手順:",
      "1. 管理画面の「製造データ」で、生成待ち・生成失敗の件数を見る",
      "2. VM が動いているかを確認する（`infra/README.md`「外部 IP を持たない VM に入る」）",
      "3. VM を戻したあと、`failed` に落ちた行を「失敗した全件を戻す」でまとめて戻す",
    ])
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "5 分間に 1 回以上、到達に失敗している"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_job\"",
        "metric.type=\"logging.googleapis.com/user/${google_logging_metric.vm_unreachable[0].name}\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    # 5 分間隔のワーカーが 1 度も報告しなければ、VM は戻っている。
    auto_close = "3600s"
  }
}

resource "google_monitoring_alert_policy" "generation_failed" {
  count = local.make_alerts

  project      = var.project_id
  display_name = "製造データ生成が失敗している"
  combiner     = "OR"

  documentation {
    content = join("\n", [
      "製造データの生成が `failed` で終わっています。",
      "",
      "到達不能の再試行とは別です。**入力の誤り（未対応の商品種別・サイズ、",
      "必須レイヤーの欠落）か、再試行の上限に達したもの**です。",
      "",
      "管理画面の「製造データ」→「生成失敗」で、行ごとの理由を確認してください。",
      "元データの差し替えが要る場合は、受注詳細から差し替えると再生成されます。",
    ])
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "1 時間に 3 回以上失敗している"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_job\"",
        "metric.type=\"logging.googleapis.com/user/${google_logging_metric.generation_failed[0].name}\"",
      ])
      comparison = "COMPARISON_GT"
      # **1 件では鳴らさない。** 個別の入力ミスは日常的に起きるうえ、
      # 管理画面の一覧に出る。鳴らす価値があるのは「続けて落ちている」ときである。
      threshold_value = 2
      duration        = "0s"

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    auto_close = "86400s"
  }
}

# ワーカーそのものが落ちている場合。**上の 2 つは、ワーカーが動いて初めて鳴る。**
resource "google_monitoring_alert_policy" "worker_job_failed" {
  count = local.make_alerts

  project      = var.project_id
  display_name = "製造データ生成ワーカーが異常終了している"
  combiner     = "OR"

  documentation {
    content = join("\n", [
      "ワーカー（Cloud Run Job `${var.worker_job_name}`）が異常終了しています。",
      "",
      "**ログベースのアラートはワーカーが動いて初めて鳴ります。** ワーカー自身が",
      "起動できていないときは、この 1 本だけが鳴ります。",
      "",
      "Cloud Run Job の実行ログを確認してください（DB への接続、マイグレーション、",
      "Secret Manager の参照など、生成に入る前の失敗が多い）。",
    ])
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "実行が失敗している"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_job\"",
        "resource.label.job_name=\"${var.worker_job_name}\"",
        "metric.type=\"run.googleapis.com/job/completed_task_attempt_count\"",
        "metric.label.result=\"failed\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    auto_close = "3600s"
  }
}

resource "google_monitoring_alert_policy" "api_server_errors" {
  count = local.make_alerts

  project      = var.project_id
  display_name = "API が 5xx を返している"
  combiner     = "OR"

  documentation {
    content = join("\n", [
      "API（Cloud Run `${var.api_service_name}`）が 5xx を返しています。",
      "",
      "外部販売サイトからの受注が失敗している可能性があります。**受注の取りこぼしは",
      "あとから復旧できません**（相手側が再送しない限り DB に何も残らない）ので、",
      "まず受注が通っているかを確認してください。",
      "",
      "Cloud Run のログを `severity>=ERROR` で絞ると、アプリ側の例外が読めます。",
    ])
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "5 分間に 5 回以上の 5xx"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_revision\"",
        "resource.label.service_name=\"${var.api_service_name}\"",
        "metric.type=\"run.googleapis.com/request_count\"",
        "metric.label.response_code_class=\"5xx\"",
      ])
      comparison = "COMPARISON_GT"
      # 単発の 5xx では鳴らさない（コールドスタート時の取りこぼし等）。
      threshold_value = 4
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    auto_close = "3600s"
  }
}

# --- 外形監視 ---------------------------------------------------------------
#
# 上のアラートはすべて「メトリクスが届くこと」を前提にしている。
# **サービスごと落ちているときは、その前提が崩れる。** 外から叩く 1 本を別に持つ。

resource "google_monitoring_uptime_check_config" "api" {
  count = local.make_uptime

  project      = var.project_id
  display_name = "POD Admin API"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.api_host
    }
  }
}

resource "google_monitoring_alert_policy" "api_down" {
  count = local.make_alerts * local.make_uptime

  project      = var.project_id
  display_name = "API が応答していない"
  combiner     = "OR"

  documentation {
    content = join("\n", [
      "API（${var.api_url}）の /health が応答していません。",
      "",
      "管理画面と、外部販売サイトからの受注の両方が止まっています。",
      "Cloud Run のリビジョンの状態を確認し、直前のデプロイが原因なら",
      "**前のリビジョンへ戻してください**（`infra/README.md`「切り戻す」）。",
    ])
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "外形監視が失敗している"

    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"uptime_url\"",
        "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\"",
        "metric.label.check_id=\"${google_monitoring_uptime_check_config.api[0].uptime_check_id}\"",
      ])
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      # **1 回の失敗では鳴らさない。** probe は複数地域から来るので、
      # 1 地域の一過性の失敗を障害として扱わない。
      duration = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.host"]
      }

      trigger {
        count = 2
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    auto_close = "3600s"
  }
}
