仕様作成からPR作成まで全自動で実行します。
各フェーズは **Taskツールを使用してサブエージェントを起動** し、途中で止めず最後まで一気に実行します。

要望: $ARGUMENTS

## 引数の解釈

### 通常モード
`/ship <要望>` — 要望テキストから仕様を自動生成して実装

### 既存仕様モード
`/ship --spec <id>` — 過去の仕様ファイルから再実装
- 例: `/ship --spec FEAT-0001`
- `.claude/specs/<id>.yaml` を読み込み、Phase 1 をスキップして Phase 2 から開始

---

## 実行フロー

### Phase 1: 仕様構造化（--spec 指定時はスキップ）

**Taskツールで spec-writer を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/spec-writer.md を読み込み、その指示に従って動作してください。

  要望: <ここに要望テキストを埋め込む>

  対話なしで仕様を構造化し、.claude/specs/FEAT-XXXX.yaml に保存してください。
  """
)
```

### Phase 2: 設計

**Taskツールで architect を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/architect.md を読み込み、その指示に従って動作してください。

  Intent Spec: <Phase 1で生成した仕様ファイルのパス>

  変更対象・アーキテクチャ判断・実装順序を決定してください。
  """
)
```

### Phase 3: テスト生成（実装より先）

**Taskツールで tdd-writer を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/tdd-writer.md を読み込み、その指示に従って動作してください。

  Intent Spec: <仕様ファイルのパス>
  設計メモ: <Phase 2の出力>

  ユニットテスト + 統合テストを生成してください。
  E2Eテストは Intent Spec に test_type: e2e が含まれる場合のみ生成してください（オプション）。
  テストが全て失敗する（Red）ことを確認してください。
  """
)
```

### Phase 4: 実装

**Taskツールで implementer を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/implementer.md を読み込み、その指示に従って動作してください。

  テストをパスするコードを書いてください。
  全てのテスト（ユニット・統合、E2Eがある場合はE2Eも）がパスするまで実装を続けてください。
  """
)
```

### Phase 5: 品質ゲート

**Taskツールで quality-gate を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/quality-gate.md を読み込み、その指示に従って動作してください。

  9層検証を実行し、結果を報告してください。
  （E2Eテストは e2e/ ディレクトリが存在する場合のみ実行）
  """
)
```

**FAIL の場合:**
- Phase 4（implementer）に戻して修正（最大3回）
- それでもFAILなら人間に報告して終了

### Phase 6: PR作成（/ship 自身が実行）

品質ゲート PASS の場合、Taskツールは使わず直接実行:
1. `git add` で変更をステージング
2. `git commit` でコミット
3. `git push` でプッシュ
4. `gh pr create` でPR作成（`.github/PULL_REQUEST_TEMPLATE.md` を使用）

---

## 重要

- **各フェーズで必ずTaskツールを使用してサブエージェントを起動する**
- Phase 1→6 を途中で止めず最後まで一気に実行する
- サブエージェントには `.claude/agents/*.md` を読み込ませてその指示に従わせる
- Docker環境内で全てのコマンドを実行する

## 自動実行ルール

- **Phase 1〜6 の間、人間に承認を求めない**
- ファイルの読み書き、コマンド実行、Taskツール起動はすべて自動で進める
- 質問や確認は一切せず、最善の判断で進める
- 人間への報告が必要なのは以下の場合のみ:
  - 品質ゲートが3回連続でFAILした場合
  - 回復不能なエラーが発生した場合
