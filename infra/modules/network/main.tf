# 製造データ生成 VM（illustrator-vm）を置くための閉じたネットワーク（REQ-0055）。
#
# **このモジュールは本番だけが呼ぶ。** 理由と、なぜ modules/stack の中ではなく
# envs/prod から直接呼ぶのかは ADR-0036。
#
# 既定の VPC を使わず custom mode の VPC を新設する理由は 2 つある。
#
# 1. **auto mode の VPC は全リージョンにサブネットを勝手に作る。** 使わない
#    リージョンにアドレス空間が生えるうえ、`default-allow-*`（0.0.0.0/0 からの
#    SSH・RDP）が最初から入っている。**それが個人プロジェクトで実際に起きたことである**
#    （`default-allow-rdp` / `default-allow-ssh` が送信元無制限で開いていた）
# 2. custom mode は**暗黙の deny だけが最初からある状態**で始まる。
#    到達できる経路は、以下で明示的に開けたものだけになる

# **値をここに置く。** 呼び出し側は project_id と region しか渡さない。
#
# modules/stack が `"pod-admin-api"` などを直書きしているのと同じ扱いである。
# 変数にしてよいのは**環境ごとに違う値**だけで（`infra/README.md`「構成」）、
# ここに並ぶ名前と CIDR は本番にしか存在しない。**呼び出し側が 2 つになった
# ときに変数へ格上げすればよく、先回りしてつまみを作らない。**
locals {
  network_name = "pod-admin-vpc"

  # VM を置く範囲。VM は 1 台だが、既定 VPC の自動割り当て（10.128.0.0/9）と
  # 重ならないことのほうが大事なので、切りのよい /24 を取る。
  illustrator_subnet_cidr = "10.20.0.0/24"

  # Cloud Run の Direct VPC egress が使う範囲。
  # **インスタンスごとに 1 アドレス使い、デプロイ中は新旧のリビジョンが同時に持つ。**
  # api 5 ＋ web 5 ＋ worker Job ＋ migrate Job = 12 の 4 倍を見込んで /24 にしてある。
  # **狭くすると、枯渇はデプロイ時の 503 という形で出る。**
  run_subnet_cidr = "10.20.1.0/24"

  # ファイアウォールの適用先になるネットワークタグ。
  # **VM 側に同じタグを付けないと、規則は 1 台にも効かない。**
  # PR 2 で VM を作るときは、この値を直書きせず `illustrator_target_tag` 出力から渡す。
  illustrator_target_tag = "illustrator-vm"
}

module "services" {
  source = "../project-services"

  project_id = var.project_id
  services = [
    "compute.googleapis.com",
    # 外部 IP を外すと RDP の入口が無くなる。IAP TCP forwarding で代替する。
    "iap.googleapis.com",
  ]
}

resource "google_compute_network" "this" {
  project = var.project_id
  name    = local.network_name

  # サブネットは下で明示的に作る。**ここを true にすると全リージョンに生える。**
  auto_create_subnetworks = false

  # 単一リージョンしか使わないので REGIONAL でよい。
  routing_mode = "REGIONAL"

  depends_on = [module.services]
}

# VM を置くサブネット。
resource "google_compute_subnetwork" "illustrator" {
  project       = var.project_id
  region        = var.region
  name          = "pod-admin-illustrator"
  network       = google_compute_network.this.id
  ip_cidr_range = local.illustrator_subnet_cidr

  # 外部 IP が無い VM から Google API（Logging / OS Config / Artifact Registry）へ
  # 出るために要る。**Cloud NAT を経由しない経路になるので、NAT のデータ処理料も減る。**
  # Ops Agent がログを送り続けるぶんが、この VM の下りの大半を占める。
  private_ip_google_access = true
}

# Cloud Run の Direct VPC egress が使うサブネット。
#
# **VM と分けてある。** Cloud Run はインスタンスごとにこのサブネットの IP を
# 1 つ取るので、VM と同居させると VM 側のアドレスを食い合う。分けておけば
# ファイアウォールの送信元も「Cloud Run だけ」と書けて、規則が実態を表す。
resource "google_compute_subnetwork" "run" {
  project       = var.project_id
  region        = var.region
  name          = "pod-admin-run"
  network       = google_compute_network.this.id
  ip_cidr_range = local.run_subnet_cidr

  # **今日は効かない。** egress を PRIVATE_RANGES_ONLY にする限り、
  # Google API 宛ての通信はこのサブネットを通らない。
  # egress を広げたときに Google API だけ黙って落ちるのを防ぐための保険であり、
  # 有効にしても費用は増えない。
  private_ip_google_access = true
}

# Cloud Run（api / worker）から VM の生成 API へ。**開けるのはこれだけ。**
resource "google_compute_firewall" "run_to_illustrator" {
  project     = var.project_id
  name        = "pod-admin-allow-run-to-illustrator"
  network     = google_compute_network.this.id
  description = "Cloud Run の Direct VPC egress から illustrator-vm の生成 API へ（REQ-0055）"

  # **サブネットの実体から引く。** local を両方から参照すると、
  # 範囲を広げたときに規則が付いてこない事故が起きうる。
  source_ranges = [google_compute_subnetwork.run.ip_cidr_range]

  # **適用先をタグで絞る。** ここを空にすると VPC 内の全インスタンスに効く。
  # 個人プロジェクトの `allow-tshirt-api` がまさにそれで、
  # 0.0.0.0/0 から tcp:8000 が全台に開いていた。
  target_tags = [local.illustrator_target_tag]

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }
}

# 運用のための入口。**外部 IP を持たない VM に入る唯一の経路である。**
#
# 35.235.240.0/20 は IAP TCP forwarding の固定レンジで、ここからのパケットは
# Google 側で認証・認可を通ったものだけになる（`roles/iap.tunnelResourceAccessor`）。
# 到達できること自体が権限になる 0.0.0.0/0 の RDP とは、そこが違う。
resource "google_compute_firewall" "iap_to_illustrator" {
  project     = var.project_id
  name        = "pod-admin-allow-iap-to-illustrator"
  network     = google_compute_network.this.id
  description = "IAP TCP forwarding から RDP と生成 API へ（運用・疎通確認用。REQ-0055）"

  source_ranges = ["35.235.240.0/20"]
  target_tags   = [local.illustrator_target_tag]

  allow {
    protocol = "tcp"
    # 3389 は RDP。8000 は Cloud Run を経由せずに生成 API の生死を確かめるため
    # （切替前に VM 単体を検証できる。REQ-0055 の段階 3）。
    ports = ["3389", "8000"]
  }
}

# 外部 IP を持たない VM の下り経路。
#
# **これが無いと Adobe のライセンス確認・Windows Update・Ops Agent が出られない。**
# 設計書のフェーズ 5 はここに触れていないが、外部 IP を外す以上は必須である
# （Illustrator は定期的にライセンスをオンラインで確認する）。
#
# **PR 1 では作らなかった。** ゲートウェイは VM が 1 台も無くても課金されるので、
# 使う相手と同じ PR で作る。
resource "google_compute_router" "this" {
  project = var.project_id
  region  = var.region
  name    = "pod-admin-router"
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  project = var.project_id
  region  = var.region
  name    = "pod-admin-nat"
  router  = google_compute_router.this.name

  nat_ip_allocate_option = "AUTO_ONLY"

  # **VM のサブネットだけを NAT する。** 全サブネットを対象にすると、
  # Cloud Run の Direct VPC egress（PRIVATE_RANGES_ONLY で公衆網には出ない想定）が
  # 設定ミスで ALL_TRAFFIC になったときに、黙って NAT 経由で外へ出てしまう。
  # 対象を絞っておけば、その事故は疎通しないという形で表に出る。
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.illustrator.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
