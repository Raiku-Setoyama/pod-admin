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

# ブートディスクの日次スナップショット。
#
# **このディスクはシステムで唯一の再現不能資産である。** 上に Illustrator の
# インストールと Adobe CC のサインイン状態が乗っており、作り直すとハードウェア ID が
# 変わってライセンス認証をやり直すことになる。
#
# 既にある守り（`deletion_protection` と `ignore_changes`）が防ぐのは**消えること**
# だけで、**中身が壊れること**（Windows Update の失敗、ファイルシステムの破損、誤操作）は
# 防がない。復旧の拠り所は移送のために手で作ったイメージ 1 つしかなく、
# それ以後の変更は一切入っていない。
#
# **これは新しい要求ではない。** 移送元のディスクには
# `illustrator-vm-daily-snapshot`（日次・14 日保持・03:00 JST）が付いていた。
# イメージはディスクを運ぶが、ディスクに付いたリソースポリシーは運ばないため落ちた。
# 同じ設定をここで復元する（REQ-0062）。
resource "google_compute_resource_policy" "daily_snapshot" {
  project = var.project_id
  region  = var.region
  name    = "${local.instance_name}-daily-snapshot"

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        # **UTC で指定する。** 18:00 UTC = 03:00 JST（移送元と同じ時刻）。
        # 業務時間外に取ることで、生成中のディスクを掴む機会を減らす。
        start_time = "18:00"
      }
    }

    retention_policy {
      max_retention_days = 14

      # **ディスクを消してもスナップショットは残す。** 誤操作でディスクごと
      # 消えたときこそ、このスナップショットが唯一の復旧手段になる。
      # 一緒に消える設定にすると、最も要る場面で何も残らない。
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }

    snapshot_properties {
      labels            = local.labels
      storage_locations = [var.region]

      # **VSS（アプリ整合）は使わない。** Windows の VSS を要求すると、
      # ゲスト側のエージェントが応答しないときにスナップショットそのものが失敗する。
      # ここで守りたいのは「OS とライセンス認証の状態」であり、
      # 生成中のジョブの整合性ではない（生成はやり直せる）。
      # **取れないスナップショットより、整合が緩くても取れるスナップショットを選ぶ。**
      guest_flush = false
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "boot_disk_snapshot" {
  project = var.project_id
  zone    = local.zone
  name    = google_compute_resource_policy.daily_snapshot.name

  # **ディスクは Terraform の管理下に無い**（`boot_disk.initialize_params` で
  # 作られるため独立した実体を持たない）。独立した `google_compute_disk` へ
  # 移す案もあるが、その移行自体が置き換えを伴いかねず、この要件の目的に反する。
  #
  # ポリシーの貼り付けはディスクを作り直さない**その場の操作**なので、
  # 構造を変えずに守りだけを足せる。名前は instance の boot_disk から導く
  # （既定ではインスタンス名と同じだが、**その前提をここに書き写さない**）。
  disk = basename(google_compute_instance.this.boot_disk[0].source)
}
