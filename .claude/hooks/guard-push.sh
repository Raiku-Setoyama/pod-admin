#!/usr/bin/env bash
#
# guard-push.sh — PreToolUse フック。
# `git push` の実行前に品質検証が完了しているかを確認し、未完なら拒否する。
#
# stdin から Claude Code のフック入力（JSON）を受け取り、
# 拒否する場合は permissionDecision: deny を返す。
#
set -uo pipefail

input="$(cat)"

command="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_input", {}).get("command", ""))
except Exception:
    print("")
' 2>/dev/null)"

# git push 以外は素通し
case "$command" in
  *"git push"*) ;;
  *) exit 0 ;;
esac

# テンプレート本体（および contribute 目的のフォーク）は開発プロジェクトではないため、
# 品質ゲートの対象外にする。origin に repo 名が残っているかで判定する。
# 「Use this template」で作った案件は別名になるので、ここを素通りせず品質ゲートが効く。
origin="$(git remote get-url origin 2>/dev/null || echo "")"
case "$origin" in
  *ai-native-project-template*) exit 0 ;;
esac

# ドキュメントのみのブランチは品質ゲート対象外
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
case "$branch" in
  docs/*) exit 0 ;;
esac

deny() {
  python3 -c '
import json, sys
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": sys.argv[1]
  }
}, ensure_ascii=False))
' "$1"
  exit 0
}

if [ ! -x scripts/quality-gate.sh ]; then
  exit 0
fi

result="$(bash scripts/quality-gate.sh --verify 2>&1)" || deny \
  "push がブロックされました。$result / 先に /quality-gate を実行してください（静的チェック → /simplify max → 静的チェック再実行 → --seal の順）。"

exit 0
