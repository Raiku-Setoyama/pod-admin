resource "google_cloud_run_v2_job" "this" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  labels              = var.labels
  deletion_protection = var.deletion_protection

  template {
    task_count = 1
    labels     = var.labels

    template {
      service_account = var.service_account_email
      timeout         = "${var.timeout_seconds}s"
      max_retries     = var.max_retries

      # Direct VPC egress。**VPC の中にしか居ないものを呼ぶときだけ設定する。**
      #
      # egress は PRIVATE_RANGES_ONLY にする。ALL_TRAFFIC にすると
      # SendGrid や Cloud SQL（パブリック IP）まで VPC 経由になり、
      # そちら側に NAT が要る。private だけ通せば公衆網は今までの経路のままである。
      dynamic "vpc_access" {
        for_each = var.vpc_egress == null ? [] : [1]
        content {
          egress = "PRIVATE_RANGES_ONLY"
          network_interfaces {
            network    = var.vpc_egress.network
            subnetwork = var.vpc_egress.subnetwork
          }
        }
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
        image   = var.image
        command = var.command

        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
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
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

resource "google_cloud_run_v2_job_iam_member" "invokers" {
  for_each = toset(var.invoker_members)

  project  = var.project_id
  location = google_cloud_run_v2_job.this.location
  name     = google_cloud_run_v2_job.this.name
  role     = "roles/run.invoker"
  member   = each.value
}
