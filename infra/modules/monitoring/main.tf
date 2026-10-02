# API（Cloud Run サービス）の監視と通知。
#
# **製造データ生成の監視はここではない。** そちらは modules/manufacturing-monitoring が
# 持つ（ワーカーのログを数える指標・VM の死活・滞留・ワーカー不稼働）。このモジュールは
# **API が外から使えるか**だけを見る。2 つに分けてあるのは宛先の決まり方が違うからで、
# 製造データのほうは管理画面で宛先を変えられる（Webhook 経由）。
#
# **VM を直接叩く死活監視はどちらにも置けない。** REQ-0055 で外部 IP を外したので、
# Uptime Check の probe は公衆網から `10.20.0.10` に到達できない。VPC 内から VM を叩く
# 唯一の経路（ワーカー）のログを見るのが、manufacturing-monitoring 側の作りである。

locals {
  # 通知先が無ければアラートは作らない。**鳴らないアラートを置くほうが危険である。**
  # 「監視してあるはず」という思い込みだけが残るため。
  make_alerts = var.enabled && length(var.notification_emails) > 0 ? 1 : 0
  make_uptime = var.enabled && var.uptime_check_enabled ? 1 : 0

  channel_ids = [for c in google_monitoring_notification_channel.email : c.id]

  # Uptime Check はホスト名だけを取る（scheme とパスは別のフィールド）。
  # **ここは属性なので未確定でよい。** count と違い、apply の時点で埋まればよい。
  api_host = replace(replace(var.api_url, "https://", ""), "/", "")
}

resource "google_monitoring_notification_channel" "email" {
  for_each = var.enabled ? toset(var.notification_emails) : toset([])

  project      = var.project_id
  display_name = "POD Admin アラート (${each.value})"
  type         = "email"

  labels = {
    email_address = each.value
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
      # **REDUCE_COUNT_FALSE が数えるのは「失敗した probe 地域の数」である。**
      # したがって鳴らす条件は「失敗地域が 1 を超えた」= COMPARISON_GT / 1 になる。
      # LT / 1 にすると「失敗地域が 0」= **健全なときだけ鳴る**という真逆の条件になり、
      # しかも全地域が落ちた瞬間に黙る。
      comparison = "COMPARISON_GT"
      # **1 地域の失敗では鳴らさない。** probe は複数地域から来るので、
      # 1 地域の一過性の失敗を障害として扱わない。
      threshold_value = 1
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.host"]
      }

      # **地域数は threshold_value が見ている。** ここで数えるのは
      # 「条件を満たした時系列の本数」であり、host でまとめた後は 1 本しかない。
      # 2 を要求すると、どれだけ落ちても永久に満たされない。
      trigger {
        count = 1
      }
    }
  }

  notification_channels = local.channel_ids

  alert_strategy {
    auto_close = "3600s"
  }
}
