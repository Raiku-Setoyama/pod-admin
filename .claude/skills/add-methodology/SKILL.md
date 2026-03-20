---
name: add-methodology
description: ADD（AI-Driven Development）方式の開発哲学・テスト戦略・Docker環境のリファレンス
allowed-tools: Read, Grep, Glob
---

# ADD方式 開発メソドロジー

`/ship`・`/spec` コマンド実行時に適用されるルールとガイドライン。

- `/spec`: 対話型で仕様を作成（GitHub Issue として登録）
- `/ship`: GitHub Issue の仕様から全自動実装→PR作成

---

## 開発哲学

**コードの行ではなく、意図・制約・成果で品質を担保する。**

| 原則 | 説明 |
|------|------|
| Intent-First | すべての実装は構造化された意図仕様（Intent Spec）から始める |
| Test-Proven | 正しさはテストで証明する（人間のコード読解に依存しない） |
| Docker-First | 開発・テスト環境はDockerコンテナで完結させ、ローカルを汚さない |
| Full-Auto Default | 仕様→設計→実装→テスト→PR作成は原則AIが全自動で行う |

---

## 自動化パイプライン概要

`/ship` 実行時、以下のフェーズを順に実行する:

| Phase | サブエージェント | 役割 |
|-------|------------------|------|
| 1 | planner | 設計判断 + テスト生成 |
| 2 | builder | 実装 → /simplify → 5段階の品質チェック（セルフリトライ最大3回） |
| 3 | /ship 自身 | コミット・プッシュ・PR作成 |

FAIL時: builder が自分で修正を試みる（最大3回）→ それでもFAILなら人間に報告

---

## テスト戦略

### 必須テスト

| 種別 | 場所 | 要件 |
|------|------|------|
| ユニットテスト | `tests/unit/` | カバレッジ80%以上 |
| 統合テスト | `tests/integration/` | DB操作はモック化 |

### ユニットテスト
- 単一モジュール・関数の振る舞いを検証
- 外部依存はモック・スタブで分離
- テストランナー: vitest（TypeScript）, pytest（Python）

### 統合テスト
- 複数モジュール間の連携・API入出力を検証
- DB操作はモック/スタブで分離（実DBには接続しない）
- テストランナー: vitest（TypeScript）, pytest（Python）

### テスト完遂ルール

**すべてのテスト（ユニット・統合）がパスするまで実装を続ける。**
テストが失敗している状態でのコミット・PR作成は禁止。

---

## Docker環境コマンド

Docker環境のコマンドは `.claude/skills/docker-env/SKILL.md` を参照。

---

## 品質チェック（5段階）

詳細は `.claude/agents/builder.md` を参照。
コード品質・可読性・再利用性のレビューは `/simplify` コマンドに委譲。
