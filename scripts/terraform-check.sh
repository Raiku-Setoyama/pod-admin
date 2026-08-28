#!/usr/bin/env bash
#
# terraform-check.sh — infra/ の静的チェック（整形と構文・型の検証）。
#
# **terraform が無ければ失敗する。** quality-gate.sh のコマンド存在判定は
# 先頭の語（bash）しか見ないためここで自分で判定するが、「無ければ緑」に
# すると、ローカルのゲートは何も検証せずに封をして push を通してしまう。
# uv が無ければ赤くなるのと同じ扱いにして、ローカルと CI の「通過」を揃える。
#
set -uo pipefail

cd "$(dirname "$0")/.."

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform がインストールされていません（brew install terraform）" >&2
  exit 1
fi

# プロバイダを環境ディレクトリごとに落とし直さない。
# 1 環境で約 40MB あり、環境が増えるほど CI もローカルも無駄に膨らむ。
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"

failed=0

echo "--- terraform fmt ---"
terraform -chdir=infra fmt -check -recursive || failed=1

for env_dir in infra/envs/*/; do
  [ -d "$env_dir" ] || continue
  echo "--- terraform validate ($env_dir) ---"
  # -backend=false: state バケットへ触らずに検証する（認証を要求しない）。
  terraform -chdir="$env_dir" init -backend=false -input=false -no-color >/dev/null || { failed=1; continue; }
  terraform -chdir="$env_dir" validate -no-color || failed=1
done

exit $failed
