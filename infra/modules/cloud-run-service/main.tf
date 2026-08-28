resource "google_cloud_run_v2_service" "this" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  ingress             = var.ingress
  labels              = var.labels
  deletion_protection = var.deletion_protection

  # サービスレベルの scaling。**template 側の scaling とは別物である。**
  # こちらは「サービス全体の下限をリビジョン間で配分する」設定であり、
  # インスタンス数の制御は template 側で行う（var.min_instances / var.max_instances）。
  #
  # 使わないのに宣言しているのは、API が既定値を実体化して返すためである。
  # 宣言しないと毎回「このブロックを消す」差分が出続け、apply しても収束しない。
  # **var.min_instances を渡してはならない。** 同じ変数が 2 つの別の意味を持つ。
  scaling {
    min_instance_count = 0
    scaling_mode       = "AUTOMATIC"
  }

  template {
    service_account                  = var.service_account_email
    timeout                          = "${var.timeout_seconds}s"
    max_instance_request_concurrency = 80
    labels                           = var.labels

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    dynamic "volumes" {
      for_each = length(var.cloudsql_instances) == 0 ? [] : [1]
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = var.cloudsql_instances
        }
      }
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        # リクエストが無いあいだ CPU を割り当てない。Cloud Run Job と違い、
        # サービスはレスポンス後の処理を続けられない。非同期処理をここに載せない
        # 前提の設定である（REQ-0052）。
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = var.container_port
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = length(var.cloudsql_instances) == 0 ? [] : [1]
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }

      dynamic "startup_probe" {
        for_each = var.startup_probe_path == null ? [] : [1]
        content {
          initial_delay_seconds = 5
          period_seconds        = 5
          timeout_seconds       = 3
          failure_threshold     = 12
          http_get {
            path = var.startup_probe_path
            port = var.container_port
          }
        }
      }
    }
  }

  lifecycle {
    # イメージのタグはデプロイ（CI / gcloud run deploy）が動かす。
    # Terraform が持つと、apply のたびに最後にデプロイしたイメージへ巻き戻る。
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(var.invoker_members)

  project  = var.project_id
  location = google_cloud_run_v2_service.this.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = each.value
}
