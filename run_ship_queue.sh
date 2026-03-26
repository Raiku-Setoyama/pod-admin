#!/usr/bin/env bash
# Sequential /ship queue: #28 → #29 → #27 → #25 → #30 → #26
set -e

REPO_DIR="/Users/raiku_setoyama/github/tosyo/pod-admin"
cd "$REPO_DIR"

notify() {
  openclaw system event --text "$1" --mode now 2>/dev/null || true
}

run_ship() {
  local issue_num="$1"
  local prompt="$2"
  echo ""
  echo "=========================================="
  echo "▶ 着手: issue #${issue_num}"
  echo "=========================================="
  claude --dangerously-skip-permissions -p "/ship ${prompt}"
  local exit_code=$?
  if [ $exit_code -eq 0 ]; then
    notify "✅ issue #${issue_num} 完了: ${prompt:0:40}..."
  else
    notify "❌ issue #${issue_num} 失敗 (exit=${exit_code}): ${prompt:0:40}..."
    echo "エラー: issue #${issue_num} が失敗しました (exit=${exit_code})"
    exit $exit_code
  fi
}

notify "🚀 /ship キュー開始: #28 → #29 → #27 → #25 → #30 → #26 の順で実行します"

# 1. #28 バグ修正: 商品マスター一覧のメーカーが反映されない
run_ship 28 "issue #28: 【バグ】商品マスター一覧の「メーカー」が反映されていない。商品マスター一覧画面においてメーカーフィールドが正しく表示・反映されていない。APIレスポンスにメーカーフィールドが含まれているか確認し、フロントエンドの表示カラムにメーカーを追加、DBのリレーション（商品↔メーカー）が正しくJOINされているか修正してください。"

# 2. #29 商品マスター一覧にフィルター追加
run_ship 29 "issue #29: 【機能】商品マスター一覧に「種類」「メーカー」「ステータス」のフィルター機能を追加してほしい。APIにクエリパラメーター(category, maker, status)を追加し、フロントエンドにフィルターUIコンポーネントを追加。URLパラメーターでフィルター状態を保持してください。"

# 3. #27 受注CSVに「商品名（処理用）」列追加
run_ship 27 "issue #27: 【機能】受注CSVの出力項目に「商品名（処理用）」列を追加し、値として「注文番号_商品番号」の形式（例: ORD-0001_ITEM-001）で出力してほしい。受注CSV出力のエクスポートロジックに新列を追加してください。"

# 4. #25 全メーカーへの発注一覧ページ
run_ship 25 "issue #25: 【機能】メーカごとの発注一覧はそのままに、「すべての発注」として全メーカー分を一覧で確認できるページを作成してほしい。発注一覧にメーカー未選択時に全件返すAPIエンドポイントの拡張と、「全メーカー」ビューのフロントエンド追加をしてください。"

# 5. #30 伝票番号インポートCSV/XLSX
run_ship 30 "issue #30: 【機能】注文番号・伝票番号・運送会社名をCSVまたはXLSX形式でインポートできる機能を追加してほしい。バックエンドにCSV/XLSXを解析するエンドポイント(POST /api/shipments/import)を実装し、フロントエンドにインポートボタンを追加。バリデーション・エラーハンドリングも実装してください。"

# 6. #26 受注CSV対応イメージ画像ダウンロード（ZIP）
run_ship 26 "issue #26: 【機能】受注CSVのデータに対応する商品イメージ画像だけをまとめてZIPダウンロードできる機能を追加してほしい。受注一覧にイメージ画像をダウンロードボタンを追加し、選択された受注に紐づく商品の画像URLを収集してZIP化してダウンロードするAPIエンドポイントを実装してください。"

notify "🎉 全タスク完了! #28→#29→#27→#25→#30→#26 すべてPR作成済み"
echo ""
echo "=========================================="
echo "✅ 全6タスク完了!"
echo "=========================================="
