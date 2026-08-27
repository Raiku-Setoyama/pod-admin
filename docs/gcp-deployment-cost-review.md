# GCP 本番デプロイ 構成・見積もり（確定版）

- 対象: POD Admin 本番デプロイ（GCP）＋ ステージング環境
- 初版: 2026-07-01 / 確定版更新: 2026-07-29
- リージョン: すべて **東京（asia-northeast1）** に統一
- 価格: list 価格（CUD なし）。**すべて料金計算ツールの実データ**（2026-07-29 再作成、下記共有リンク）
- **本番 ¥44,738/月（VM 2vCPU 24/7）** ＋ **ステージング ¥2,546/月** = **合計 ¥47,284/月**
- （元見積もり ¥59,684/月。VM を 4vCPU にすると本番 ~¥64,000/月）
- **見積もりは本番・ステージングで別プロジェクト運用のため、共有リンクも2本に分離（各プロジェクトの「用意リソース一覧」を兼ねる）:**
  - 本番: https://cloud.google.com/products/calculator/estimate-preview/CiQ4OTk5MGExYS1lZWVkLTQ2ZTQtOTgzNS0zN2JiODIyMmNkNDYQAQ%3D%3D
  - ステージング: https://cloud.google.com/products/calculator/estimate-preview/CiQwMmQ3ZTVmMC1jZDE0LTQ4ZWEtOTg1Yi0yMGNmMjI2ZjRmMmQQAQ%3D%3D

---

## 1. 確定した意思決定

| # | 決定 | 内容 |
| --- | --- | --- |
| 1 | DB エンジン | **PostgreSQL**（実体が asyncpg/JSONB/ARRAY。MySQL は誤りだった） |
| 2 | Cloud SQL 可用性 | **HA 無効（ゾーン構成）**。データは自動バックアップ＋PITR で保護。メンテ枠は夜間に設定 |
| 3 | Cloud SQL 割引 | **CUD は一旦適用しない**（将来 1年 CUD で vCPU+RAM 25%オフの余地あり） |
| 4 | 製造データ生成 | **Compute Engine の Windows VM** で実行（Adobe Illustrator はサーバーレス/Linux 不可のため VM 必須） |
| 5 | VM 稼働形態 | **24/7 常時起動**（オンデマンドより +~¥15,000/月だが、autologon トリガ・self-stop・起動レイテンシ対策が不要で運用が単純） |
| 6 | API / フロント | **Cloud Run（東京）** に集約。API は WeasyPrint 用に **2GiB** |
| 7 | ファイル保管 | **Cloud Storage**（GCS 実装済み）。入稿/成果物を 180日 ライフサイクルで自動削除 |
| 8 | ステージング | **最低スペックで別途用意**（別プロジェクト。Cloud Run ゼロスケール＋db-f1-micro＋illustrator-vm スタブ） |
| 9 | 削除済み | Cloud VPN / 常駐 Compute Engine(旧案) / Gemini Enterprise / Parameter Manager |

---

## 2. アーキテクチャ構成（本番）

```
[外部販売サイト] --APIキー/HTTPS--> ┌─────────────────────────────┐
                                    │ Cloud Run: API (FastAPI/東京)│  1vCPU/2GiB
[管理者ブラウザ] --> [Cloud Run:    │  ・注文受信 → manufacturing_ │  min-instances=0
                     フロント/Next] │    data(status=pending) 作成 │  (外部注文のコールド
                          │         │    → 即応答（重い処理はしない│   スタートが問題なら
                          └────────>│  ・請求書PDF(WeasyPrint) 等  │   =1 に。+~¥6k/月)
                                    └───────────┬─────────────────┘
                                                │ read/write
   ┌────────────────────────────────────────────┼───────────────────────┐
   │ Cloud SQL PostgreSQL (非HA, db-standard-1, 東京, 30GiB自動拡張)      │
   │ Cloud Storage (入稿/成果物, Standard, 180日ライフサイクル)          │
   └────────────────────────────────────────────┼───────────────────────┘
                                                │ poll pending / write result
                                    ┌───────────┴─────────────────┐
                                    │ Compute Engine: Windows VM   │ ← 24/7 常時起動
                                    │  ・Adobe Illustrator          │
                                    │  ・illustrator-vm (HTTPローカル)│
                                    │  ・Worker: pending を継続ポーリ │
                                    │    ング → Illustrator実行 →   │
                                    │    PNG → GCS保存 → status更新 │
                                    └──────────────────────────────┘
```

**要点:** 30〜360秒かかる生成処理を Cloud Run（リクエスト処理中のみ CPU 割当）に載せず、**常時起動の VM ワーカー**が DB を継続ポーリングして処理する。これで Cloud Run のタイムアウト/CPU スロットリング問題が消える。24/7 なので起動トリガ（Cloud Scheduler）や self-stop は不要。既存の `run_generation` + `recover_stranded_generations` をワーカーのループにするだけで、**Cloud Tasks/Pub/Sub は不要**。

---

## 3. 月額見積もり（本番・確定・料金計算ツール実データ）

| コンポーネント | 構成 | ¥/月 |
| --- | --- | --- |
| Cloud Run（API） | 1vCPU/2GiB, min-instances=0, 東京 | 3,433 |
| Cloud Run（フロント） | 1vCPU/512MiB, min-instances=0, 東京 | 3,056 |
| **Cloud SQL PostgreSQL** | **非HA**, db-standard-1(1vCPU/3.75GB), 30GiB SSD, 東京 | **11,434** |
| Cloud Storage | 1TB Standard, 東京（※実使用量課金） | 3,717 |
| Secret Manager / Cloud Build | 無料枠内 | 0 |
| **マネージド小計** | | **21,640** |
| **＋ Compute Engine（Windows/Illustrator VM, 24/7）** | e2-standard-2(2vCPU/8GB)+100GBディスク | **23,099** |
| **本番 合計** | | **44,739** |

### Illustrator VM の内訳感（東京・Windows・24/7 = 730h）

| サイズ | compute | Windowsライセンス | ディスク100GB | **月合計** |
| --- | --- | --- | --- | --- |
| e2-standard-2 (2vCPU/8GB) | ¥10,143 | ¥10,855 | ~¥2,100 | **¥23,099**（実データ） |
| e2-standard-4 (4vCPU/16GB) | ~¥20,000 | ~¥22,000 | ~¥2,100 | **~¥44,000** |

- 既定は **e2-standard-2**。Illustrator で開く .ai が大きい/重い場合は e2-standard-4 へ（本番合計 ~¥64,000/月）
- **Adobe Illustrator ライセンス（Adobe CC）は GCP 請求外** — 別途予算化
- Cloud Storage 1TB は上限想定。実保持量（注文量×平均入稿サイズ×180日）が例: 100〜200GB なら ~¥400〜800/月に下がる

---

## 4. ステージング環境（最低スペック）

**方針:** 本番と同じアーキテクチャを**別 GCP プロジェクト**（`pod-admin-staging`）で最小構成再現。**ステージング専用の Illustrator VM は持たず、一旦は本番の VM に接続**（`ILLUSTRATOR_VM_BASE_URL` を本番 VM に向ける／ユーザー決定）。見積もり（下記共有リンク）は料金計算ツール実データ。

| コンポーネント | 構成 | ¥/月 |
| --- | --- | --- |
| Cloud Run（API） | 1vCPU/2GiB, min=0, 東京, 10万req/月 | 187 |
| Cloud Run（フロント） | 1vCPU/512MiB, min=0, 東京, 10万req/月 | 163 |
| **Cloud SQL** | **db-f1-micro**(共有コア,1vCPU/0.6GB), 10GiB SSD, 非HA, 東京 | 2,009 |
| Cloud Storage | 50GiB Standard, 東京（専用バケット・短ライフサイクル） | 186 |
| Secret Manager / Cloud Build | 無料枠内 | 0 |
| **ステージング 合計** | | **2,546** |

補足:
- **Cloud Run のゼロスケール（min=0）**＋低リクエスト想定（10万req/月）でほぼ無料枠内。使う時だけ課金。
- **db-f1-micro** は共有コアで HA/SLA/CUD 非対応だが、ステージングには十分。さらに削るなら夜間・週末は Cloud SQL を **停止**（停止中はストレージのみ課金）で ~半額に。
- **Illustrator は一旦 本番 VM を共有**（ステージング専用 VM 無し）。将来分離するなら小さな Windows VM を追加（+~¥21,000/月 or オンデマンドで数千円）。本番データとの混在に注意。

---

## 5. 総額

| 環境 | ¥/月 | 共有見積もりリンク |
| --- | --- | --- |
| 本番（VM 2vCPU 24/7） | 44,738 | [estimate-preview/CiQ4OTk5...](https://cloud.google.com/products/calculator/estimate-preview/CiQ4OTk5MGExYS1lZWVkLTQ2ZTQtOTgzNS0zN2JiODIyMmNkNDYQAQ%3D%3D) |
| ステージング（最小構成） | 2,546 | [estimate-preview/CiQwMmQ3...](https://cloud.google.com/products/calculator/estimate-preview/CiQwMmQ3ZTVmMC1jZDE0LTQ4ZWEtOTg1Yi0yMGNmMjI2ZjRmMmQQAQ%3D%3D) |
| **合計** | **47,284** | |

（本番 VM を 4vCPU にする場合は本番 ~64,000 → 合計 ~66,000）

> **本番とステージングで見積もりURLを分離**（別プロジェクト運用のため、各URLがそのプロジェクトの「用意すべきリソース一覧」を兼ねる）。いずれもユーザーのGoogleアカウントに保存済み。既存見積もりを Duplicate→編集して作成。

---

## 6. デプロイ前チェックリスト

### インフラ（本番）
- [ ] Cloud SQL: **HA 無効**・db-standard-1・30GiB 自動拡張・**メンテナンス枠を夜間**に設定
- [ ] Cloud SQL: **自動バックアップ＋PITR 有効**（HA を外す分、復旧はここに依存）
- [ ] Cloud SQL 接続: **Cloud SQL Auth Proxy（public IP + IAM）**なら VPC connector 追加費用なし。private IP にするなら Serverless VPC Connector（~¥0〜3,000/月）を計上
- [ ] `max_connections` を確認し、**Cloud Run の max-instances に上限**を設定（`pool_size=5 + overflow=10 = 15接続/インスタンス` × インスタンス数 が超過しないよう）。VM ワーカー側のプールは小さめ（2〜4）に
- [ ] Cloud Run（API）**メモリ 2GiB**（WeasyPrint 請求書の OOM 回避）
- [ ] 外部注文のコールドスタートが問題なら Cloud Run（API）を **min-instances=1**（+~¥6,000/月）。外部側が 5xx でリトライ or タイムアウト >10s なら min=0 で可

### コード改修
- [ ] `enqueue_generation`：`background_tasks.add_task` を外し、**`manufacturing_data` を status=pending で作るだけ**にする
- [ ] `run_generation` / `recover_stranded_generations` を **VM ワーカーの継続ループ**として起動できるエントリポイント追加（同一コードベース・別 CMD）
- [ ] 通知メール（SendGrid）：現状 `background_tasks` 送信 → **同期送信**へ（Cloud Run では応答後タスクが不安定なため）
- [ ] マイグレーション（`alembic upgrade head`）を**起動 CMD から分離**し、デプロイ前の単独ステップ（Cloud Build ステップ / Cloud Run Job）で実行
- [ ] `GCS_BUCKET` / `GCS_CREDENTIALS_JSON`(or ADC) / `GCS_PREFIX` を本番設定

### Windows / Illustrator VM 固有（重要）
- [ ] **無人でも Illustrator が動く構成**：Illustrator は対話セッションが必要 → **自動ログオン（autologon）＋ログオン時スケジュールタスク**で Illustrator・illustrator-vm・Worker を起動。24/7 でも **Windows Update 再起動後に自動復帰**させるため必須
- [ ] メンテナンス時も **stop/start で運用（delete/recreate しない）**：永続ディスク上の Illustrator インストールと **Adobe CC サインイン状態**を保持するため
- [ ] Worker のクラッシュ時自動再起動（Windows サービス化 or タスクの再試行設定）

### ステージング
- [ ] **別プロジェクト** `pod-admin-staging` を作成（IAM/課金/クォータ隔離）
- [ ] Cloud SQL は **db-f1-micro**・非HA・最小ストレージ。必要なら夜間停止
- [ ] `ILLUSTRATOR_VM_BASE_URL` を**スタブ**に向ける（実 VM は E2E 時のみ手動起動）
- [ ] 本番と別の GCS バケット・別 Secret・別 DB（データ隔離）

### 運用
- [ ] Artifact Registry / Cloud Logging は少額（低トラフィックなら概ね無料枠内）だが監視対象に
- [ ] IAM: Cloud Run SA に GCS 権限、VM SA に GCS 権限

---

## 7. 変更履歴・補足

- 2026-07-01 初版（改定版レビュー）: MySQL→PostgreSQL 訂正、Cloud VPN/常駐 Compute Engine/Gemini 削除、東京統一。当時は HA 有効・約 ¥27,000〜39,000/月 想定。
- 2026-07-29 確定版: 実コード突合の結果 **GCS は実装済み**を確認。**HA 無効**・**CUD 見送り**を決定。製造データ生成は **Windows VM** で実行、async 処理を VM ワーカーへ寄せる設計を確定。**VM は 24/7**（運用簡素化のため on-demand から変更）。**最低スペックのステージング環境**（別プロジェクト・ゼロスケール・db-f1-micro・スタブ）を追加。
- ライブ見積もり（HA 有・CUD なし・VM 抜きの旧構成）は 2026-07-29 時点で ¥32,822/月。
