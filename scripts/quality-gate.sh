#!/usr/bin/env bash
#
# quality-gate.sh — 実装 PR を出す前の静的チェックを一括実行し、
# 検証済みのツリー内容を .quality-gate/result.json に記録する。
#
# 使い方:
#   scripts/quality-gate.sh              静的チェックを実行して結果を記録
#   scripts/quality-gate.sh --seal       /simplify max 実行済みフラグを立てる
#   scripts/quality-gate.sh --verify     記録が現在のツリーと一致するか検証（フックが使う）
#
# 記録されるフィンガープリントは「追跡対象ファイルの内容」から計算するため、
# commit の前後で値が変わらない。つまり
#   実装 → 静的チェック → /simplify max → 静的チェック再実行 → --seal → commit → push
# の順で流しても、push 時点で検証が通る。
#
set -uo pipefail

GATE_DIR=".quality-gate"
RESULT="$GATE_DIR/result.json"

# ---------------------------------------------------------------------------
# プロジェクト固有の静的チェック
# ここを各プロジェクトで書き換える。存在しないコマンドは自動でスキップされる。
# ---------------------------------------------------------------------------
# cwd が漏れないよう bash -c で囲む（monorepo の api/ web/ 対策）。
PROJECT_CHECKS=(
  "bash -c 'cd api && uv run ruff check .'"
  "bash -c 'cd api && uv run mypy .'"
  "bash -c 'cd web && npm run lint'"
  "bash -c 'cd web && npx tsc --noEmit'"
  "bash scripts/terraform-check.sh"
  # テストは DB・インフラの準備が要るため対象外（REQ-0041 のスコープ外）。
  # "bash -c 'cd api && uv run pytest -q'"
  # "bash -c 'cd web && npm run test:run'"
)

# ドキュメント整合性チェックは常に実行する
DOCS_CHECK="python3 scripts/docs-lint.py"

# ---------------------------------------------------------------------------

sha() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | awk '{print $1}'
  else shasum -a 256 | awk '{print $1}'
  fi
}

fingerprint() {
  # 追跡対象 + 未追跡（gitignore 対象外）のファイル内容からハッシュを作る。
  # .quality-gate/ 自身は除外する。
  git ls-files -z --cached --others --exclude-standard \
    | tr '\0' '\n' \
    | grep -v '^\.quality-gate/' \
    | sort \
    | while IFS= read -r f; do
        [ -f "$f" ] || continue
        printf '%s ' "$f"
        sha < "$f"
      done \
    | sha
}

json_get() {
  # $1: key
  [ -f "$RESULT" ] || { echo ""; return; }
  python3 - "$RESULT" "$1" <<'PY' 2>/dev/null || echo ""
import json, sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))
except Exception:
    print("")
PY
}

write_result() {
  # $1: checks_passed(true/false)  $2: simplified(true/false)
  mkdir -p "$GATE_DIR"
  python3 - "$RESULT" "$(fingerprint)" "$1" "$2" <<'PY'
import json, sys, datetime
path, fp, checks, simplified = sys.argv[1:5]
json.dump({
    "fingerprint": fp,
    "checks_passed": checks == "true",
    "simplified": simplified == "true",
    "recorded_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
}, open(path, "w"), indent=2)
PY
}

# --- --verify -------------------------------------------------------------
if [ "${1:-}" = "--verify" ]; then
  [ -f "$RESULT" ] || { echo "GATE: 未実行（$RESULT がありません）"; exit 1; }
  want="$(json_get fingerprint)"
  have="$(fingerprint)"
  [ "$want" = "$have" ] || { echo "GATE: 検証後にコードが変更されています"; exit 1; }
  [ "$(json_get checks_passed)" = "True" ] || { echo "GATE: 静的チェックが未通過です"; exit 1; }
  [ "$(json_get simplified)" = "True" ] || { echo "GATE: /simplify max が未実行です"; exit 1; }
  echo "GATE: OK"
  exit 0
fi

# --- --seal ---------------------------------------------------------------
if [ "${1:-}" = "--seal" ]; then
  [ -f "$RESULT" ] || { echo "先に scripts/quality-gate.sh を実行してください" >&2; exit 1; }
  if [ "$(json_get checks_passed)" != "True" ]; then
    echo "静的チェックが通っていません。修正してから再実行してください" >&2; exit 1
  fi
  write_result true true
  echo "GATE: /simplify max 実行済みとして記録しました"
  exit 0
fi

# --- 通常実行 --------------------------------------------------------------
echo "=== quality gate ==="
failed=0

run_check() {
  local cmd="$1"
  local bin
  bin="$(echo "$cmd" | awk '{print $1}')"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "-- skip: $cmd （$bin が見つかりません）"
    return 0
  fi
  echo "-- run : $cmd"
  if eval "$cmd"; then
    echo "   ok"
  else
    echo "   FAILED: $cmd" >&2
    failed=1
  fi
}

run_check "$DOCS_CHECK"
# 空配列 + set -u で bash 3.2（macOS 既定）が unbound variable を出すのを避ける
for c in ${PROJECT_CHECKS[@]+"${PROJECT_CHECKS[@]}"}; do
  run_check "$c"
done

if [ "$failed" -ne 0 ]; then
  write_result false false
  echo ""
  echo "静的チェックに失敗しました。修正してから再実行してください。" >&2
  exit 1
fi

# 静的チェック通過。simplified はこの時点では false のまま。
write_result true "$( [ "$(json_get simplified)" = "True" ] && echo true || echo false )"
echo ""
echo "静的チェック通過。次に /simplify max を実行し、scripts/quality-gate.sh --seal を実行してください。"
