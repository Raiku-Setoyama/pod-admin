# 製造データの元画像差し替え

## 概要

現状、製造データ（.ai/.pdf）の元画像（PNGレイヤー）は外部受注（v2 intake）から URL で受け取るだけで、
pod-admin 側から差し替える手段がない。元画像に不備があると外部サイト側で修正・再送してもらうしかなく、
製造データの生成失敗（`failed`）や意図しない仕上がりを管理画面から是正できない。

本機能では、管理画面から元画像 PNG をアップロードして差し替え、その元画像で製造データを再生成できるようにする。

## 現状の流れ

```
外部受注(v2) --source_images[{layer_type,url}]--> order_items
                                              --> manufacturing_data.source_images
                                                    --(URL を DL)--> illustrator-vm --> .ai/.pdf
```

`manufacturing_data` は「受注元 × 商品コード × サイズ × バリアント」単位のキャッシュで、
同一商品の複数注文が 1 行を共有する。生成の入力は `manufacturing_data.source_images` が正。

## 差し替え後の流れ

```
管理画面 --PNG アップロード--> FileStorage(source_images/)
                          --> manufacturing_data.source_images[i] = {layer_type, file_path, filename}
                                --(FileStorage から読む)--> illustrator-vm --> .ai/.pdf 再生成
```

- 差し替え対象は `manufacturing_data` 行（= 商品コード単位のデザイン）。同一商品コードの
  他注文にも同じ元画像が適用されるのはキャッシュの意味論として正しい。
- 差し替えは既存レイヤー種別の置き換えのみ許可する。レイヤー構成を変えると
  `build_vm_mapping` の導出バリアント（= キャッシュキー）が変わってしまうため。

## データモデル

### `manufacturing_data.source_images`（JSONB, 形式を拡張）

| 由来 | 形式 |
|------|------|
| 外部受注 | `{"layer_type": "color", "url": "https://..."}` |
| 差し替え | `{"layer_type": "color", "file_path": "source_images/2026...png", "filename": "color_fix.png"}` |

生成時は `file_path` があれば FileStorage から読み、無ければ従来どおり URL を SSRF ガード付きで取得する。

### `manufacturing_data` 追加カラム

| カラム | 型 | 説明 |
|--------|------|------|
| `source_images_replaced_at` | DateTime(tz), nullable | 最後に元画像を差し替えた時刻（未差し替えは NULL） |
| `source_images_replaced_by` | String(255), nullable | 差し替えた管理ユーザーのメール |

この2カラムは表示用の履歴（監査）のみ。差し替えの有無はレイヤー自身が `file_path` を持つかで
判定する。外部受注が同じキャッシュキーの `failed` 行を拾って `source_images` を更新する既存経路
では、レイヤー単位でマージする: 差し替え済み（`file_path`）レイヤーは維持し、それ以外は最新の
受注値へ更新する。

## API（管理者のみ）

| メソッド | パス | 説明 |
|----------|------|------|
| `GET` | `/manufacturing-data/{id}` | 製造データ詳細（元画像レイヤー一覧を含む） |
| `POST` | `/manufacturing-data/{id}/source-images` | 元画像を差し替えて再生成（multipart） |
| `GET` | `/manufacturing-data/{id}/source-images/{layer_type}` | 差し替え済み元画像の取得（プレビュー用） |

差し替えリクエストは「レイヤー種別と同名のファイル項目」（`color` / `cutline` / `white` / `design`）で
受け取る。レイヤー種別の語彙・重複はエンドポイントのシグネチャが保証するため、サービス側の検証は
行との突き合わせだけになる。1 リクエストで複数レイヤーを差し替えて再生成は 1 回だけ起動する。

### 拒否条件

| 条件 | 応答 |
|------|------|
| 行が存在しない | 404 |
| `status = generating`（VM ジョブ進行中） | 409 |
| 製造中/納入済みの注文と共有 | 409（完成データの保護。再作成と同じゲート） |
| 元画像が未登録の行 | 409 |
| 行に存在しないレイヤー（構成の変更） | 400 |
| PNG 以外（マジックバイト検査） | 400 |
| `SOURCE_IMAGE_MAX_BYTES` 超過 | 400 |

差し替え成功時は `regenerate` と同じ波及を行う: 行を `pending` に戻し、参照する「発注済み」明細を
「発注準備中」へ戻し（発注ゲートで保留）、バックグラウンド生成を起動する。生成完了で「発注済み」へ復帰する。

## フロントエンド

- `features/manufacturing-data/source-image-replace-dialog.tsx`（新規）
  レイヤーごとに現在の元画像（外部 URL はリンク、差し替え済みはプレビュー）と差し替えファイル選択を表示。
- `features/manufacturing-data/regenerate-controls.tsx`
  既存の「再作成」の隣に「元画像差し替え」ボタンを追加。製造着手前かつ生成中でない行のみ表示。
- 受注詳細（`orders/[id]`）とメーカー発注詳細（`purchase-orders/[id]`）の双方から操作できる。
