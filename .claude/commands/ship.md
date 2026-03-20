GitHub Issue の仕様を受け取り、全自動でPR作成まで実行します。
各フェーズは **Taskツールを使用してサブエージェントを起動** し、途中で止めず最後まで一気に実行します。

**参照スキル:** `.claude/skills/add-methodology/SKILL.md`（開発哲学・テスト戦略・Docker環境）

要望: $ARGUMENTS

## 引数の解釈

### Issue 指定モード（必須）
`/ship #<issue番号>` — GitHub Issue から仕様を読み込んで実装を開始

- 例: `/ship #42`
- `gh issue view 42` で仕様を取得し、Phase 0 から開始

### 引数なし・Issue番号以外の場合
引数なし、または `#` で始まらない引数が指定された場合:
- エラーメッセージを表示して終了:
  ```
  Issue番号が指定されていません。
  先に `/spec <要望>` で仕様を作成してから、`/ship #<issue番号>` で実行してください。
  ```

---

## 実行フロー

### Phase 0: Issue から仕様を取得

GitHub Issue から仕様と最新のコンテキストを取得する。

1. Issue の内容を取得:
   ```bash
   gh issue view <issue番号> --json number,title,body,comments,labels
   ```
2. Issue 本文から仕様（概要・スコープ・受け入れ基準・制約等）を読み取る
3. **Issue のコメントも全て確認する** — 仕様確定後に追加された補足・変更要望を把握する
   - コメントに仕様変更に関わる内容があれば、Issue 本文より **コメントの内容を優先** する
4. `spec` ラベルが付いていることを確認（付いていない場合は WARNING を出して続行）

### Worktree セットアップ

**全ての実装作業は独立した worktree で行う。** メインの作業ディレクトリを汚さないため、
最初に worktree を作成し、以降の全フェーズをその中で実行する。

1. フィーチャーブランチ名を決定: `feat/issue-<issue番号>`（例: `feat/issue-42`）
2. `EnterWorktree` ツールを使用して worktree に入る:
   ```
   EnterWorktree(branch: "feat/issue-<issue番号>")
   ```

**重要:**
- Phase 1〜3 の全作業は worktree 内で実行すること
- メインの作業ディレクトリには一切変更を加えないこと

### Phase 1: 設計＋テスト生成

**Taskツールで planner を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/planner.md を読み込み、その指示に従って動作してください。

  Intent Spec（GitHub Issue #<issue番号> の内容）:
  <Issue本文とコメントから取得した仕様をここに展開>

  1. 変更対象・アーキテクチャ判断・実装順序を決定してください。
  2. 決定した設計方針に基づいて、ユニットテスト + 統合テストを生成してください。
  """
)
```

### Phase 2: 実装＋品質確認

**Taskツールで builder を起動する:**
```
Task(
  subagent_type: "general-purpose",
  prompt: """
  .claude/agents/builder.md を読み込み、その指示に従って動作してください。

  Intent Spec（GitHub Issue #<issue番号> の内容）:
  <Issue本文とコメントから取得した仕様をここに展開>

  テストをパスするコードを書き、/simplify でコード品質を改善した後、
  Check 1〜5 の品質チェックを実行してください。
  チェック失敗時は自分で修正してください（最大3回）。
  3回失敗した場合、または環境エラーが発生した場合は、その旨を報告してください。
  """
)
```

#### Phase 2 の判定分岐

```
Phase 2: builder 実行
│
├─ 全チェック PASS
│   └─ → Phase 3（PR作成）へ進む
│
├─ ENVIRONMENT_ERROR
│   └─ → ユーザーに報告して終了
│       - 修復手順を提示
│       - `/ship #<issue番号>` での再実行方法を案内
│
└─ CODE_ERROR（3回失敗）
    └─ → ユーザーに報告して終了
        - これまでの試行履歴を提示
        - 推奨される次のアクションを提案
```

builder が ENVIRONMENT_ERROR または 3回失敗を報告した場合は、Cleanup → ExitWorktree してユーザーに報告する。

### Phase 3: PR作成

品質チェック PASS の場合、Taskツールは使わず直接実行:
1. `git add` で変更をステージング
2. UI変更ありの場合:
   - `.claude/screenshots/issue-<issue番号>/` のスクリーンショットを確認
   - `git add -f .claude/screenshots/issue-<issue番号>/` で強制ステージング（.gitignore 対象でも追加）
3. `git commit` でコミット
4. `git push` でプッシュ
5. `gh pr create` でPR作成（`.github/PULL_REQUEST_TEMPLATE.md` を使用）
   - PR description に `Closes #<issue番号>` を含める（マージ時に Issue を自動クローズ）
   - UI変更ありの場合、PR description にスクリーンショットのファイルパスを記載

### Cleanup: Docker環境の後片付け

**成功・失敗を問わず、Worktree 退出の前に必ず実行する。**

```bash
docker compose down --remove-orphans -v 2>/dev/null || true
```

- コンテナ・ネットワーク・匿名ボリュームを削除する
- イメージは削除しない（次回の `/ship` で再利用するため）
- コマンド自体が失敗しても（既に停止済み等）エラーにせず続行する

### Worktree 退出

Cleanup 完了後、worktree から退出する:
```
ExitWorktree()
```

---

## 重要

- **必ず worktree 内で作業する** — メインの作業ディレクトリを汚さない
- **各フェーズで必ずTaskツールを使用してサブエージェントを起動する**
- **Issue 番号（`#<番号>`）は必須** — 指定がなければエラーで終了
- **Phase 0 で Issue のコメントを確認する** — 仕様確定後の補足・変更を反映する
- 全フェーズを途中で止めず最後まで一気に実行する
- サブエージェントには `.claude/agents/*.md` を読み込ませてその指示に従わせる
- Docker環境内で全てのコマンドを実行する
- **Cleanup は必ず実行する** — 成功時・ENVIRONMENT_ERROR時・3回失敗時、いかなる終了パスでも ExitWorktree の前に `docker compose down --remove-orphans -v` を実行する

## 自動実行ルール

- **全フェーズの間、人間に承認を求めない**
- ファイルの読み書き、コマンド実行、Taskツール起動はすべて自動で進める
- 質問や確認は一切せず、最善の判断で進める
- 人間への報告が必要なのは以下の場合のみ:
  - **環境問題（ENVIRONMENT_ERROR）が検出された場合**
  - builder が3回連続でチェック失敗した場合
  - 回復不能なエラーが発生した場合

## 環境問題発生時の対応

環境問題が検出された場合、以下のフォーマットで報告:

```
## 環境問題が検出されました

品質チェックの実行中に環境問題が検出されたため、処理を中断しました。

### 検出された問題
<builder からの ENVIRONMENT_ERROR 内容を表示>

### 再開方法
環境を修復後、以下のコマンドで再実行してください:
/ship #<issue番号>
```
