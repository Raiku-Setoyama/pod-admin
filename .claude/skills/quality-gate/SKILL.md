---
name: quality-gate
description: 品質検証を行う。テスト実行、カバレッジ確認、Playwright E2E、仕様適合チェック。
allowed-tools: Read, Grep, Glob, Bash(docker:*), Bash(npm:*), Bash(npx:*), Bash(git:*)
---
# 品質ゲートスキル
quality-gate エージェントに委譲して6層検証を実行する。
（静的検証→ユニットテスト→統合テスト→E2E→仕様適合→AI意味レビュー）
