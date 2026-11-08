# メーカー日次発注通知（デイリーダイジェスト）

登録したメールアドレスへ、**メーカーごとの「発注済み」内容を毎日定時に自動送信**する仕組みです。
メーカーは通知を受け取り、`manufacturer-login` からログインして内容を確認します。

- 送信対象は「まだメールに載せていない、発注済み以降（発注済み・製造中・納入済み）の明細」のみ
- 対象が 0 件のメーカーには送信しません
- 送信時刻は**全社共通・1 日 1 回**（運営ダッシュボードから変更可能）
- 宛先（To/CC・各複数可）と有効/無効は**メーカーごと**に設定

---

## 運営ダッシュボードでの設定

### 全社共通（設定画面）

`設定` 画面の「メーカー日次発注通知」カードで設定します。

| 項目 | 対応する app_settings キー | 説明 |
|---|---|---|
| 日次通知を有効にする（全体） | `manufacturer_daily_digest_enabled` | マスタスイッチ。OFF の間は誰にも送信されません |
| 送信時刻（JST・全社共通） | `manufacturer_daily_digest_send_time` | `HH:MM`。この時刻を過ぎた最初のトリガで 1 日 1 回送信。変更は翌日以降に反映（コード変更・再デプロイ不要） |

> `manufacturer_daily_digest_last_run_date` は日次ガード用に自動更新される内部値です（手動編集不要）。

### メーカー別（各メーカーの編集画面）

`メーカー編集` 画面の「発注通知メール（日次）」カードで設定します。

- **このメーカーへの日次通知を有効にする**（ON/OFF）
- **宛先（To）**: 複数可。**未登録の場合はメーカーのメールアドレスに送信**されます
- **CC**: 複数可

---

## メール仕様

- **件名**: `【TOSYO__API発注依頼】{メーカー名}様{YY/M/D}`
  - 日付は送信日・JST・2 桁年・月日はゼロ埋めなし（例: 2026/6/16 → `26/6/16`）
- **本文**:

  ```
  以下、発注済みの注文があります。

  発注中明細数　{件数} 件
  合計数量　{数量} 点

  https://pod-admin-beige.vercel.app/manufacturer-login
  からログインしてご確認ください。
  ```

ログイン URL は環境変数 `MANUFACTURER_LOGIN_URL` で変更できます（既定値は上記）。

---

## 定時実行（外部トリガ → 内部 API）

API 自体はスケジューラを持たないため、**外部トリガが内部エンドポイントを高頻度で叩く**方式です。
エンドポイントは「現在 JST ≥ 送信時刻 かつ 本日未実行」の場合のみ本処理を実行します。

### 内部エンドポイント

```
POST /api/v1/internal/manufacturer-daily-digest
Header: X-Internal-Secret: <INTERNAL_API_SECRET>
Query:  force=true|false   （任意。true で時刻・日次ガードを無視して即時送信＝手動テスト用）
```

- 認証は共有シークレット（環境変数 `INTERNAL_API_SECRET`）。未設定なら **403**（無効）。
- 高頻度（例: 5〜15 分毎）で叩いて問題ありません。**多重発火でも二重送信しません**
  （全社日次ガード `last_run_date` の原子的 claim ＋ 明細ごとの通知済み `order_items.manufacturer_notified_at`）。

レスポンス例:

```json
{
  "ran": true,
  "reason": "ok",
  "run_date": "2026-07-09",
  "sent_count": 2,
  "skipped_zero_count": 1,
  "failed_count": 0,
  "sent_manufacturer_ids": ["..."],
  "skipped_zero_manufacturer_ids": ["..."],
  "failed_manufacturer_ids": []
}
```

`ran: false` の `reason`: `disabled` / `send_time_not_set` / `before_send_time` / `already_ran_today`。

### 必要な環境変数（API 側）

| 変数 | 説明 |
|---|---|
| `INTERNAL_API_SECRET` | 内部エンドポイントの共有シークレット。例: `openssl rand -hex 32` |
| `MANUFACTURER_LOGIN_URL` | メール本文のログイン URL（任意。既定値あり） |

### トリガの設定例

#### A. Cloud Scheduler（本番で使用中）

本番は Cloud Scheduler `pod-admin-manufacturer-digest` が 5 分ごとに叩きます（Terraform 管理。
`infra/modules/stack/main.tf`、運用は `infra/README.md`）。ステージングは止めてあります。

> 以前は GitHub Actions の schedule（15 分ごと）で叩いていましたが、実際には 4〜7 時間おきにしか
> 動かず、送信時刻が日によって数時間ずれたため Cloud Scheduler に移しました（#162・#167）。

#### B. GitHub Actions（手動実行のみ: `.github/workflows/manufacturer-daily-digest.yml`）

`Run workflow` から手動で実行します。`force` を付けると時刻・日次ガードを無視して即時送信します
（未通知の明細があればメーカーへ実際に届くので、再送・テスト以外では使わない）。

リポジトリの `Settings → Secrets and variables → Actions` で設定:

- Variables: `API_BASE_URL` = API の URL
- Secrets: `INTERNAL_API_SECRET` = API と同じ値

#### 手動テスト（即時送信）

```bash
curl -sS -X POST \
  "<API の URL>/api/v1/internal/manufacturer-daily-digest?force=true" \
  -H "X-Internal-Secret: ${INTERNAL_API_SECRET}"
```

---

## 集計仕様（未通知分のみ）

メーカー `m` について:

- 対象明細 = `OrderItem` WHERE `Product.manufacturer_id = m.id`
  AND `manufacturer_notified_at IS NULL`
  AND `status IN (ordered, manufacturing, delivered)`
- **発注中明細数** = 対象明細の件数、**合計数量** = Σ `quantity`
- 送信**成功時のみ**、対象明細の `manufacturer_notified_at` を実行時刻にし、メーカーごとに確定する
  （失敗時は未通知のまま残り、次回の送信で載る）。`last_notified_at` は「最後に送った時刻」として更新する

> 送信処理の時点のステータスでは絞りません。送信処理より先に製造中へ進んだ明細（メーカーポータルで
> 発注資料をダウンロードすると自動で製造中になる）も、一度も通知していなければ載せます。
> 発注準備中（製造データ未準備）とキャンセル済みは載せず、発注済みになった後の回で載せます（#161）。
> 日時はすべて JST で扱います。

## 将来拡張（今回スコープ外）

- メーカーごとに異なる送信時刻（現状は全社共通）
- メーカーポータル側からの自己設定（現状は運営ダッシュボードのみ）
- 発注済み以外のステータス（製造中／納入済み等）の通知
