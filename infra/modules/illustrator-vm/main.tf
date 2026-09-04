# 製造データ生成 VM（illustrator-vm）。REQ-0055 で個人プロジェクトから移送した。
#
# **Windows の VM である。** Adobe Illustrator は Linux でもサーバーレスでも動かないので、
# 生成だけがこの 1 台に載っている（`docs/gcp-deployment-cost-review.md`）。
#
# **stop/start で運用し、delete/recreate しない。** 永続ディスクの上に
# Illustrator のインストールと **Adobe CC のサインイン状態**が乗っており、
# 作り直すとハードウェア ID が変わってライセンス認証をやり直すことになる。
# **これがこの移送で唯一読めなかったリスクであり、二度は引きたくない。**
#
# **このモジュールは本番だけが呼ぶ**（ADR-0036・ADR-0037）。

# **値をここに置く。** 呼び出し側が渡すのは配線（プロジェクト・ネットワーク・イメージ）だけである。
# 姉妹モジュール `modules/network` と同じ扱いで、**呼び出し側が 2 つになったときに
# 変数へ格上げすればよく、先回りしてつまみを作らない。**
locals {
  instance_name = "illustrator-vm"

  # **VM 名とは別に持つ。** 同じ値を使い回すと、VM の改名が
  # サービスアカウントの作り直しを巻き添えにする。
  # このモジュールの前提は「この 1 台を作り直さない」ことなので、
  # 巻き添えの経路自体を持たない。
  service_account_id = "illustrator-vm"

  # 移送元と同じ。重い .ai を開くようになったら e2-standard-4
  # （`docs/gcp-deployment-cost-review.md`）。
  machine_type = "e2-standard-2"

  # 移送元と同じ。**この 2 つを変えるとインスタンスごと作り直しになる**
  # （plan には「変更」と出るが、実体は置き換えである）。
  # pd-balanced にすれば月 ¥1,500 ほど安くなるが、Adobe の再認証と引き換えになる。
  boot_disk_size_gb = 100
  boot_disk_type    = "pd-ssd"

  zone = "${var.region}-a"

  labels = {
    app        = "pod-admin"
    env        = var.env
    managed-by = "terraform"
  }
}

# 生成 API の宛先を、plan の時点で確定した文字列にするために予約する。
#
# **インスタンスの network_ip をそのまま参照しない。** apply 前に値が決まらないので、
# `illustrator_vm_base_url` が computed になり、それを読む Cloud Run のリソースまで
# 巻き込んで「apply してみないと分からない」差分になる。
resource "google_compute_address" "internal" {
  project      = var.project_id
  region       = var.region
  name         = "${local.instance_name}-internal"
  subnetwork   = var.subnetwork_id
  address_type = "INTERNAL"
  address      = var.internal_ip
}

# VM 専用のサービスアカウント。
#
# **移送元は既定の Compute サービスアカウントを使っていた。** それはプロジェクトの
# 既定権限を持ち、用途も追えない。この VM が要るのは Ops Agent の書き込みだけである
# （生成 API は HTTP で完結し、GCS にも DB にも触らない）。
module "service_account" {
  source = "../service-accounts"

  project_id = var.project_id

  accounts = {
    (local.service_account_id) = {
      display_name  = "POD Admin illustrator-vm"
      description   = "製造データ生成 VM が使う（Ops Agent の書き込みのみ）"
      project_roles = ["roles/logging.logWriter", "roles/monitoring.metricWriter"]
    }
  }
}

resource "google_compute_instance" "this" {
  project      = var.project_id
  zone         = local.zone
  name         = local.instance_name
  machine_type = local.machine_type
  labels       = local.labels

  # **作り直しを止める最後の砦である。** ファイル冒頭の理由による。
  deletion_protection = true

  boot_disk {
    initialize_params {
      image = var.source_image
      size  = local.boot_disk_size_gb
      type  = local.boot_disk_type
    }
  }

  network_interface {
    subnetwork = var.subnetwork_id
    network_ip = google_compute_address.internal.address

    # **access_config を書かない。これが「外部 IP を付けない」の実体である。**
    # 書かないことでしか表せないので、消したことに気づける形にならない。
    # 付いていないことは受入基準として機械的に確認する。
  }

  # ファイアウォールの適用先。**呼び出し側が network モジュールの出力から渡す。**
  # ここに文字列を書くと、規則の側とずれても apply は通り、
  # 「到達できない」という静かな形でしか表に出ない。
  tags = [var.network_tag]

  service_account {
    email = module.service_account.emails[local.service_account_id]

    # ロールで絞る前提で cloud-platform を渡す（Google の推奨）。
    # 上のとおり、付いているロールは Ops Agent の 2 つだけである。
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = {
    # 移送元と同じ。Ops Agent のポリシーがこれを見る。
    enable-osconfig = "TRUE"
  }

  allow_stopping_for_update = true

  lifecycle {
    ignore_changes = [
      # **イメージはブートディスクの作成にしか使われない。**
      # 次のイメージを作ったときに VM ごと作り直されると、
      # Adobe の認証をやり直すことになる。
      # **裏返すと、ここを書き換えても何も起きない。** 起動中のイメージを
      # 入れ替えるには VM を作り直すしかなく、それは冒頭の理由で行わない。
      boot_disk[0].initialize_params[0].image,

      # Windows のログイン鍵は `gcloud compute reset-windows-password` が書き込む。
      metadata["windows-keys"],
    ]
  }
}
