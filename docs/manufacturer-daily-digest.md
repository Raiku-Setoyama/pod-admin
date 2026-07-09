# メーカー日次発注通知（デイリーダイジェスト）

登録したメールアドレスへ、**メーカーごとの「発注済み」内容を毎日定時に自動送信**する仕組みです。
メーカーは通知を受け取り、`manufacturer-login` からログインして内容を確認します。

- 送信対象は「前回送信以降に新しく発注済みになった明細」のみ（新規分のみ）
- 新規の発注済みが 0 件のメーカーには送信しません
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

pod-admin にはスケジューラが無いため、**外部トリガが内部エンドポイントを高頻度で叩く**方式です。
エンドポイントは「現在 JST ≥ 送信時刻 かつ 本日未実行」の場合のみ本処理を実行します。

### 内部エンドポイント

```
POST /api/v1/internal/manufacturer-daily-digest
Header: X-Internal-Secret: <INTERNAL_API_SECRET>
Query:  force=true|false   （任意。true で時刻・日次ガードを無視して即時送信＝手動テスト用）
```

- 認証は共有シークレット（環境変数 `INTERNAL_API_SECRET`）。未設定なら **403**（無効）。
- 高頻度（例: 5〜15 分毎）で叩いて問題ありません。**多重発火でも二重送信しません**
  （全社日次ガード `last_run_date` の原子的 claim ＋ メーカー別ウォーターマーク `last_notified_at`）。

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

#### A. GitHub Actions（同梱: `.github/workflows/manufacturer-daily-digest.yml`）

リポジトリの `Settings → Secrets and variables → Actions` で設定:

- Variables: `API_BASE_URL` = `https://<your-app>.railway.app`
- Secrets: `INTERNAL_API_SECRET` = API と同じ値

15 分ごとに自動実行され、`Run workflow` から `force` 指定での手動送信も可能です。

> 注: GitHub Actions の cron は UTC 実行かつ高負荷時に遅延することがありますが、
> 送信可否は API 側が JST・日次ガードで判定するため運用上問題ありません。

#### B. 汎用 cron / ホスティングのスケジューラ

```bash
*/10 * * * * curl -sS -X POST \
  "https://<your-app>.railway.app/api/v1/internal/manufacturer-daily-digest" \
  -H "X-Internal-Secret: ${INTERNAL_API_SECRET}"
```

#### 手動テスト（即時送信）

```bash
curl -sS -X POST \
  "https://<your-app>.railway.app/api/v1/internal/manufacturer-daily-digest?force=true" \
  -H "X-Internal-Secret: ${INTERNAL_API_SECRET}"
```

---

## 集計仕様（新規分のみ）

メーカー `m` について:

- 対象明細 = `OrderItem` WHERE `Product.manufacturer_id = m.id`
  AND `status = ORDERED` AND `created_at > COALESCE(last_notified_at, '-infinity')`
- **発注中明細数** = 対象明細の件数、**合計数量** = Σ `quantity`
- 送信**成功時のみ** `last_notified_at` を実行時刻に更新（失敗時は次回再送対象として残す）

> `ORDERED` は発注時の初期ステータスのため、`OrderItem.created_at` を「発注済みになった時刻」とみなします。
> 日時はすべて JST で扱います。

## 将来拡張（今回スコープ外）

- メーカーごとに異なる送信時刻（現状は全社共通）
- メーカーポータル側からの自己設定（現状は運営ダッシュボードのみ）
- 発注済み以外のステータス（製造中／納入済み等）の通知
