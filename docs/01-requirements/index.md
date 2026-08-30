# 要件一覧

このディレクトリが**要求・要件・バックログを兼ねます。** 打ち合わせで挙がった話も、
Slack で流れた話も、合意した要件も、見送ったものも、すべて `REQ-XXXX` として 1 か所に入ります。
ここに入っていない話は存在しなかったことになります。

**出どころは問いません。** 打ち合わせ由来なら `source` に議事録 ID が入り、
そうでなければ `source` は空のまま、出典は本文の `## 経緯` に残ります。

区別は 2 つのフィールドで行います。ディレクトリは分けません。

<!-- この表は起票スキルと /docs-audit が更新します -->

| ID | 領域 | タイトル | priority | status | マイルストーン |
|---|---|---|---|---|---|
| [REQ-0001](REQ-0001.md) | auth | 管理者アカウントで管理画面にログインしセッションを維持できる | must | done | v1.0 |
| [REQ-0002](REQ-0002.md) | auth | 製造委託先が専用ポータルにログインできる | must | done | v1.0 |
| [REQ-0003](REQ-0003.md) | auth | ロールとトークン種別で管理者・メーカーの権限を分離し保護する | must | done | v1.0 |
| [REQ-0004](REQ-0004.md) | auth | 外部連携APIキーと内部処理用シークレットで認証する | must | done | v1.0 |
| [REQ-0005](REQ-0005.md) | order | 受注一覧をステータス・商品種別・日付・キーワードで検索できる | must | done | v1.0 |
| [REQ-0006](REQ-0006.md) | order | 受注の顧客情報・商品明細・配送情報・製造データ状態を閲覧できる | must | done | v1.0 |
| [REQ-0007](REQ-0007.md) | order | 受注ステータスを単発・一括で更新し状態遷移の制約を守る | must | done | v1.0 |
| [REQ-0008](REQ-0008.md) | order | 注文〆切・営業日・自社休日をふまえ納品予定日・配送予定日を自動計算する | must | done | v1.0 |
| [REQ-0009](REQ-0009.md) | order | 選択した受注の配送CSV・デザイン画像ZIP・サムネイルZIPを出力できる | must | done | v1.0 |
| [REQ-0010](REQ-0010.md) | external-api | 外部販売サイトがAPIキー認証で完成デザイン付き受注を登録できる(v1) | must | done | v1.0 |
| [REQ-0011](REQ-0011.md) | external-api | 外部販売サイトが元データ付き受注を登録し製造データを生成する(v2) | must | done | v1.0 |
| [REQ-0012](REQ-0012.md) | external-api | 外部販売サイトが商品選択肢・価格計算・注文状況照会・キャンセルを行える | must | done | v1.0 |
| [REQ-0013](REQ-0013.md) | external-api | 受注元ごとにコード・APIキー・配送元情報を保持する | must | done | v1.0 |
| [REQ-0014](REQ-0014.md) | product | 商品をマスタとして登録・編集・一覧・削除できる | must | done | v1.0 |
| [REQ-0015](REQ-0015.md) | product | 同一仕様の有効な商品を二重登録できない | must | done | v1.0 |
| [REQ-0016](REQ-0016.md) | manufacturer | 製造委託先を連絡先・対応商品・単価等とともに登録・編集・一覧・削除できる | must | done | v1.0 |
| [REQ-0017](REQ-0017.md) | purchase-order | 発注中の受注明細をメーカー別に集計した発注サマリー・明細を確認できる | must | done | v1.0 |
| [REQ-0018](REQ-0018.md) | purchase-order | メーカー向け発注資料ZIPを生成できる | must | done | v1.0 |
| [REQ-0019](REQ-0019.md) | purchase-order | 発注ステータスを明細単位で一括更新し全納入で配送を自動起票する | must | done | v1.0 |
| [REQ-0020](REQ-0020.md) | purchase-order | 製造データを外部VMで生成し商品単位でキャッシュ再利用する | must | done | v1.0 |
| [REQ-0021](REQ-0021.md) | purchase-order | 製造データ完成までメーカー発注を不可にし発注準備中で表現する | must | done | v1.0 |
| [REQ-0022](REQ-0022.md) | purchase-order | 製造データを管理画面から再作成・元画像差し替えできる | must | done | v1.0 |
| [REQ-0023](REQ-0023.md) | manufacturer-portal | 製造委託先がポータルで自社情報・銀行口座を管理できる | must | done | v1.0 |
| [REQ-0024](REQ-0024.md) | manufacturer-portal | 製造委託先がポータルで自社の発注明細一覧を閲覧できる | must | done | v1.0 |
| [REQ-0025](REQ-0025.md) | manufacturer-portal | 製造委託先がポータルから発注資料をDLし発注中→製造中に自動遷移する | must | done | v1.0 |
| [REQ-0026](REQ-0026.md) | shipment | 配送一覧を実配送と準備中注文を統合して検索・絞り込みできる | must | done | v1.0 |
| [REQ-0027](REQ-0027.md) | shipment | 配送ステータスを個別・一括で更新し発送処理を行える | must | done | v1.0 |
| [REQ-0028](REQ-0028.md) | shipment | 配送業者向けCSV・梱包写真・サムネイル一括DLができる | must | done | v1.0 |
| [REQ-0029](REQ-0029.md) | shipment | 伝票番号を一括インポートして発送確定し発送通知メールを自動送信する | must | done | v1.0 |
| [REQ-0030](REQ-0030.md) | billing | 製造委託先向けの請求書PDFを管理画面とポータルから発行できる | must | done | v1.0 |
| [REQ-0031](REQ-0031.md) | chat | 管理者と製造委託先がテキスト・添付でチャットしダウンロードできる | must | done | v1.0 |
| [REQ-0032](REQ-0032.md) | dashboard | 管理者がダッシュボードで本日の受注・発送件数と内訳を把握できる | must | done | v1.0 |
| [REQ-0033](REQ-0033.md) | notification | 外部受注が入ったら社内担当者へ受注通知メールを自動送信する | must | done | v1.0 |
| [REQ-0034](REQ-0034.md) | notification | 通知ONの製造委託先へ新規発注分を日次ダイジェストメールで通知する | must | done | v1.0 |
| [REQ-0035](REQ-0035.md) | common | 発送準備日数・注文〆切・通知設定と自社休日、メーカー別通知宛先を管理できる | must | done | v1.0 |
| [REQ-0036](REQ-0036.md) | external-api | 受注元を管理画面から登録・APIキー発行・有効無効切替できる | future | not-started | |
| [REQ-0037](REQ-0037.md) | auth | メーカーポータルでトークンが自動更新され再ログインが不要になる | future | not-started | |
| [REQ-0038](REQ-0038.md) | order | 受注・発注のステータス変更履歴を記録し追跡できる | undecided | not-started | |
| [REQ-0039](REQ-0039.md) | chat | チャットの未読/既読管理と新着通知ができる | undecided | not-started | |
| [REQ-0040](REQ-0040.md) | auth | 本番のデバッグ資産（debug-token・トークンログ）を除去する | undecided | not-started | |
| [REQ-0041](REQ-0041.md) | common | 静的解析（ruff/eslint/mypy/tsc）を是正し品質ゲート・CIの必須チェックに組み込む | must | done | |
| [REQ-0042](REQ-0042.md) | common | 既存のテスト失敗（pytest 46件・vitest 9件）を解消しテストをCIの必須チェックにする | undecided | not-started | |
| [REQ-0043](REQ-0043.md) | common | openapi/schema.yaml を正本として復旧しフロントのAPI型を自動生成に戻す | undecided | not-started | |
| [REQ-0044](REQ-0044.md) | shipment | 何も検証していないテスト（同語反復のアサーション）を実装の検証に置き換える | undecided | not-started | |
| [REQ-0045](REQ-0045.md) | purchase-order | 全メーカー受注明細一覧で商品タイプ・発注日フィルタを操作するUIが無い | undecided | not-started | |
| [REQ-0047](REQ-0047.md) | common | データ出力タブから項目・条件・並び順を指定して任意のデータを出力できる | must | not-started | |
| [REQ-0048](REQ-0048.md) | shipment | 配送一覧の検索で注文番号も検索でき、検索欄の表記が実際の検索対象と一致する | must | done | |
| [REQ-0049](REQ-0049.md) | shipment | 配送一覧を作成日・配送予定日・ステータス・注文番号・宛先で昇順／降順に並び替えられる | must | done | |
| [REQ-0050](REQ-0050.md) | shipment | 配送一覧の 1 ページ表示件数と総件数を、実配送と準備中注文を通して正しくする | undecided | not-started | |
| [REQ-0051](REQ-0051.md) | shipment | 複数の注文を含む実配送で、一覧に出す配送予定日と並び替えの基準を揃える | undecided | not-started | |
| [REQ-0052](REQ-0052.md) | common | 非同期処理（製造データ生成・受注通知メール）をコンテナ実行基盤で完走する形に改める | must | done | |
| [REQ-0053](REQ-0053.md) | common | インフラを Terraform で管理し、ステージング環境を GCP に構築する | must | not-started | |
| [REQ-0054](REQ-0054.md) | common | 本番環境を Railway / Vercel から GCP へ移行する | must | not-started | |
| [REQ-0055](REQ-0055.md) | common | 製造データ生成VMを会社組織のGCPプロジェクトへ移し、認証なしでインターネットから到達できない状態にする | must | not-started | |
| [REQ-0056](REQ-0056.md) | common | SQLAlchemy のモデル定義と実際のDBスキーマのズレを解消する | undecided | not-started | |
| [REQ-0058](REQ-0058.md) | billing | 請求書PDFの支払期日ラベルの横に出る不要な文字「z」を消す | undecided | not-started | |

## priority — 採否・約束の度合い

**「やると決まっているか」**の軸です。**人間が PR のマージで決めます。**

| priority | 意味 | 顧客向け表記 | 誰が遷移させるか |
|---|---|---|---|
| `undecided` | 実装するかは未定。判断待ち | 検討中 | エージェント（根拠が引用できないときの既定値） |
| `must` | 必ず必要。今回のスコープ | 対応 | **人間（PR マージ）** |
| `future` | 将来的に必ず必要。今回はやらない | 次期フェーズ | **人間（PR マージ）** |
| `wont` | やらないと決めた | 対象外 | **人間（PR マージ）** |

`future` / `wont` にするときは、**`decision` に理由を、`decided_at` に判断日を必ず書きます。**
理由のない判断は後で必ず蒸し返されます。

**受託開発では「やらないと決めた記録」が資産になります。** 後から「あの時お願いしましたよね」と
なった際に、いつ・どういう理由で見送ったかを提示できます。

## status — 実装の進み具合

**「どこまで作ったか」**の軸です。エージェントが進めます。

| status | 意味 | 誰が遷移させるか |
|---|---|---|
| `not-started` | 未着手 | エージェント |
| `in-progress` | 着手中。受入基準の一部が未達 | エージェント |
| `done` | 実装済み | **人間（実装 PR のマージ）** |
| `on-hold` | 保留。着手したが止めている | エージェント（理由を本文に書く） |

`done` は実装 PR 自身が書き込みます。未達の受入基準を残したまま `done` にすると
`scripts/docs-lint.py` が落ちます。

**`undecided`（やるか決まっていない）と `on-hold`（やると決めたが止めている）は別物です。**
前者は採否の話、後者は実行の話。軸が分かれているのでこの 2 つは混ざりません。

## 着手可能かどうかは保存しません

次の条件をすべて満たすものが着手可能です。フラグとして持たず、
`scripts/docs-lint.py` と `/implement` がその場で判定します。

- `priority` が `must` または `future`
- `status` が `not-started`
- 受入基準が 1 件以上、検証可能な形で書かれている
- `[NEEDS-DECISION]` が残っていない
- `area` が確定している（`unassigned` のままにしない）
- `depends_on` がすべて `done`

保存されたフラグは、立てたあとに前提が崩れても立ったままになります。導出ならその事故が起きません。

## 不具合は別の層に置きます

**完了した機能が期待どおり動かない、という話は要件ではありません。**
要件は「これから何を作るか」の合意で、不具合は「した合意が果たされていない」状態です。

> **既存の受入基準（憲章の `NFR` / `CONSTRAINTS` を含む）に違反しているか。**
>
> - **違反している → 不具合。** `../05-defects/` に `BUG-XXXX` を `priority: must` で起票します
> - **違反していない → 要件。** ここに `priority: undecided` で起票します
> - **判定がつかない → 要件に倒します**

不具合を要件として起票すると、要件定義書に不具合が載り、
不具合を見つけるほど要件の総数が増えて消化率が意味を失います。

**完了した要件は、不具合が出ても `done` のまま戻しません。** `done` はマージ時点の履歴であり、
今も満たしている保証ではありません。今の健全性は「未修正の不具合があるか」で表します
（→ `../05-defects/index.md`）。

## 論点は ADR に置きます

「承認は 2 段階か 3 段階か」のような**決める必要がある論点**は、要件ではありません。
`../02-decisions/` に ADR を `status: proposed` で起票し、選択肢と推奨を書きます。
決まったら同じファイルが `accepted` になります。

要件の本文からは `[NEEDS-DECISION: ADR-XXXX]` で参照します。
**ID のない `[NEEDS-DECISION]` は CI エラーになります。論点には必ず住所を与えてください。**

## 領域（area）

「どの機能まわりの話か」を表す別の軸です。語彙は `../00-charter/areas.md` に定義します。

まだ決まっていないものは `unassigned` にします。**`priority` を `undecided` から動かすときは
必ず確定させてください**（`unassigned` のままだと `scripts/docs-lint.py` が落ちます）。

## 作業 ID

**`REQ-XXXX` がそのまま作業 ID です。** GitHub Issue は作りません。
実装ブランチは `feat/REQ-XXXX-slug`、PR 本文の `Refs: REQ-XXXX` で対応を辿ります。

1 要件 = 1 実装 PR が原則です。実装の都合で分ける場合は `## 実装メモ` に計画を書きます
（→ `AGENTS.md`「作業の単位」）。**1 つの PR が 2 件以上の作業項目を実装することは禁じます**
（要件と不具合を混ぜることもできません。合計 1 件です）。
