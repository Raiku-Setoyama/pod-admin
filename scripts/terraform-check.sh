#!/usr/bin/env bash
#
# terraform-check.sh — infra/ の静的チェック（整形と構文・型の検証）。
#
# terraform が入っていない環境ではスキップする。quality-gate.sh の
# コマンド存在判定は先頭の語しか見ないため、ここで自分で判定する。
#
set -uo pipefail

cd "$(dirname "$0")/.."

if [ ! -d infra ]; then
  echo "infra/ が無いためスキップ"
  exit 0
fi

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform 未インストールのためスキップ"
  exit 0
fi

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
