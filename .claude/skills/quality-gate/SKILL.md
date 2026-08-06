---
name: quality-gate
description: 実装した変更に対して、静的チェックと /simplify max による品質検証を行い、push 可能な状態にする。コードを変更したあと、コミットする前、PR を出す前、push する前には必ずこのスキルを使うこと。「品質チェック」「静的チェック」「simplify」「PR を出したい」「push したい」「コミットしたい」と言われたとき、および実装作業を終えたときには常にこのスキルを実行する。
allowed-tools: Bash(bash scripts/quality-gate.sh:*) Bash(python3 scripts/docs-lint.py:*) Bash(git diff:*) Bash(git status:*)
effort: high
---

# 品質検証ゲート

実装 PR には必ずこの検証を通す。この手順を飛ばして `git push` すると PreToolUse フックに拒否される。

## 手順

必ずこの順序で実行する。順序に意味がある。

### 1. 静的チェック

```bash
bash scripts/quality-gate.sh
```

失敗したら**修正してから 1 に戻る**。失敗を無視して先へ進まない。
チェック内容がプロジェクトに合っていない場合は `scripts/quality-gate.sh` の `PROJECT_CHECKS` を直す（その修正自体も今回の PR に含める）。

### 2. `/simplify max`

Skill ツールで bundled skill `simplify` を引数 `max` で実行する（`/simplify max` と同じ）。

`/simplify` は変更されたコードを並列エージェントで走査し、再利用可能な箇所、冗長な実装、非効率な処理、`CLAUDE.md` / `AGENTS.md` の規約違反を洗い出して修正する。`max` で最も深く検証する。

出力を読み、次を確認する。

- 修正内容が意図した振る舞いを壊していないか
- 「false positive としてスキップした」と報告された項目に、本当は対応すべきものが混じっていないか

**振る舞いを変える修正が入った場合は、その旨を後で PR 本文に書くためにメモしておく。**

### 3. 静的チェック再実行

`/simplify max` はコードを書き換える。**必ずもう一度**実行する。

```bash
bash scripts/quality-gate.sh
```

ここで失敗したら `/simplify` の修正が壊した箇所である。修正して再度 2 から実行する。

### 4. 封をする

```bash
bash scripts/quality-gate.sh --seal
```

これで push が許可される。

## 封をしたあとにコードを触ったら

`--seal` はそのときのファイル内容のハッシュを記録している。あとから 1 行でも変更すると検証は無効になり、push は再び拒否される。その場合は **1 からやり直す**。ハッシュだけを再記録して回避しようとしてはいけない。

## PR 本文に書く内容

品質検証の結果を必ずこの形式で記載する。

```markdown
## 品質検証

- [x] 静的チェック: `scripts/quality-gate.sh` 通過
- [x] `/simplify max` 実行済み
  - 指摘: <件数>件 / 修正: <件数>件
  - 主な修正: <1〜3行で要約。指摘ゼロなら「指摘なし」>
- [x] 静的チェック再実行: 通過
```

## やってはいけないこと

- 静的チェックの失敗を「既存の問題なので無関係」として無視する。無関係だと判断した場合は、その根拠を PR 本文に書く。
- `/simplify max` を省略する。指摘が出ない小さな変更でも実行する。
- `.quality-gate/result.json` を手で編集する。
- `--seal` を静的チェックの前に実行する。
