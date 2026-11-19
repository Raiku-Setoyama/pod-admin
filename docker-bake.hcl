# デプロイで push する 3 つのイメージ（.github/workflows/deploy.yml が使う）。
#
# 1 回の bake でまとめてビルドする。**順に build-push すると、互いに依存しない
# 3 つのビルドを待ち合わせることになる**（以前はこれが直列で、デプロイの半分近くを占めた）。
# api と worker が共有する層（base / runtime）は、同じビルドの中で 1 度だけ作られる。
#
# 値は環境変数から入る。空のままだとタグが不正になり、ビルドが失敗する。

variable "IMAGE_BASE" {
  default = ""
}

# イメージのタグ。deploy.yml ではコミット SHA を入れる。
variable "TAG" {
  default = ""
}

# NEXT_PUBLIC_* はビルド時にバンドルへ焼き込まれる（web/Dockerfile）。
variable "NEXT_PUBLIC_API_URL" {
  default = ""
}

group "default" {
  targets = ["api", "worker", "web"]
}

target "api" {
  context    = "api"
  target     = "production"
  tags       = ["${IMAGE_BASE}/api:${TAG}"]
  cache-from = ["type=gha,scope=api"]
  cache-to   = ["type=gha,scope=api,mode=max"]
}

# 製造データ生成ワーカー（REQ-0067 / ADR-0039）。OS のパッケージの層は API と同じなので、
# API のキャッシュも読む。
target "worker" {
  context    = "api"
  target     = "worker"
  tags       = ["${IMAGE_BASE}/worker:${TAG}"]
  cache-from = ["type=gha,scope=api", "type=gha,scope=worker"]
  cache-to   = ["type=gha,scope=worker,mode=max"]
}

target "web" {
  context    = "web"
  target     = "production"
  tags       = ["${IMAGE_BASE}/web:${TAG}"]
  args       = { NEXT_PUBLIC_API_URL = NEXT_PUBLIC_API_URL }
  cache-from = ["type=gha,scope=web"]
  cache-to   = ["type=gha,scope=web,mode=max"]
}
