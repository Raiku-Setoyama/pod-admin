# 必要な API を有効化する。
#
# `disable_on_destroy = false` は意図的である。true にすると、この構成を destroy した
# ときにプロジェクト全体の API が止まり、Terraform の管理外で動いているものまで壊れる。
resource "google_project_service" "this" {
  for_each = toset(var.services)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}
