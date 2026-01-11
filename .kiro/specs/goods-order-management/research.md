# Research Log: goods-order-management

## Summary

本調査では、PODグッズ受発注管理システムの技術設計に必要な以下の領域を調査した：

**フロントエンド**:
- Next.js 15 App Router のベストプラクティス
- データフェッチングライブラリの比較（SWR vs TanStack Query）
- OpenAPI 型生成戦略
- Excel ファイル生成ライブラリの選定
- 大容量ファイルアップロードの実装パターン

**バックエンド**:
- FastAPI + SQLAlchemy 2.0 非同期パターン
- FastAPI ファイルアップロードのベストプラクティス
- レイヤードアーキテクチャの適用

---

## Research Log

### Topic 1: Next.js 15 App Router ベストプラクティス

**調査日**: 2025-12-27

**ソース**:
- [Next.js Docs: App Router](https://nextjs.org/docs/app)
- [Next.js 15 in 2025: Features, Best Practices](https://javascript.plainenglish.io/next-js-15-in-2025-features-best-practices-and-why-its-still-the-framework-to-beat-a535c7338ca8)
- [Building APIs with Next.js](https://nextjs.org/blog/building-apis-with-nextjs)

**主要な発見**:

1. **Server Components がデフォルト**
   - サーバー上でレンダリング、クライアント JS なし
   - DB/API に直接アクセス可能
   - useState, useEffect, DOM API は使用不可
   - インタラクティブな部分は "use client" で Client Component として分離

2. **Route Handlers vs Server Actions**
   - Route Handlers: 公開 API、Webhook、大容量アップロード、ストリーミングに使用
   - Server Actions: ミューテーション操作（作成・更新・削除）用の自動生成 POST API

3. **キャッシング（Next.js 15 の変更点）**
   - staleTime のデフォルトが 0 に変更
   - ナビゲーション時に常に最新データを反映

4. **セキュリティ**
   - NEXT_PUBLIC_ 以外の環境変数はサーバーのみ
   - アクション/ハンドラでの入力検証必須
   - ミューテーションでの認証強制

**設計への影響**:
- フロントエンドは FastAPI バックエンドを呼び出す
- 管理画面のデータ取得は Server Components + SWR

---

### Topic 2: データフェッチングライブラリ比較

**調査日**: 2025-12-27

**ソース**:
- [React Query vs TanStack Query vs SWR: A 2025 Comparison](https://refine.dev/blog/react-query-vs-tanstack-query-vs-swr-2025/)
- [TanStack Query vs SWR: A Comprehensive Guide for Next.js 15](https://corner.buka.sh/tanstack-query-vs-swr-a-comprehensive-guide-for-next-js-15-projects/)

**比較結果**:

| 項目 | SWR | TanStack Query |
|------|-----|----------------|
| バンドルサイズ | 小さい | 大きい |
| DevTools | なし（コミュニティ版あり） | 公式サポート |
| ページネーション | 手動実装 | 組み込みサポート |
| ミューテーション | 基本的 | 楽観的更新・ロールバック |
| ガベージコレクション | なし | あり |
| Next.js 統合 | Vercel 公式、シームレス | Hydration サポート |

**決定**: SWR を採用
- steering で既に SWR が指定されている
- 基本的なデータフェッチが中心
- Vercel/Next.js エコシステムとの親和性

---

### Topic 3: OpenAPI 型生成戦略

**調査日**: 2025-12-27

**ソース**:
- [Type-Safe Fetch with Next.js, Strapi, and OpenAPI](https://strapi.io/blog/type-safe-fetch-with-next-js-strapi-and-open-api)
- [Automating the Generation of Code from OpenAPI](https://plainenglish.io/blog/automating-the-generation-of-code-from-openapi-in-your-next-js-application)

**ベストプラクティス**:

1. **自動再生成**
   - package.json にスクリプト追加: `"generate:api": "npx openapi-typescript ..."`
   - CI/CD パイプラインに統合

2. **型の使い分け**
   - `types/api/generated.ts`: 自動生成（編集禁止）
   - `types/index.ts`: エイリアスと re-export
   - `features/*/types/`: フロントエンド固有の型

3. **スキーマ検証**
   - Zod と組み合わせて入力データを検証

**設計への影響**:
- FastAPI の自動スキーマ生成を openapi/schema.yaml にエクスポート
- フロントエンドは openapi-typescript で型を生成
- スキーマ変更時の再生成を CI に組み込み

---

### Topic 4: Excel ファイル生成ライブラリ

**調査日**: 2025-12-27

**ソース**:
- [SheetJS Community Edition](https://docs.sheetjs.com/)
- [ExcelJS GitHub](https://github.com/exceljs/exceljs)
- [xlsx vs exceljs comparison](https://npm-compare.com/excel4node,exceljs,xlsx,xlsx-populate)

**比較結果**:

| 項目 | SheetJS (xlsx) | ExcelJS |
|------|---------------|---------|
| ライセンス | Apache 2.0 | MIT |
| スタイリング | Pro版（有料） | 無料 |
| ストリーミング書き込み | Pro版（有料） | 無料 |
| セキュリティ履歴 | 脆弱性報告あり | 良好 |
| 大容量ファイル | 対応 | 最適化済み |

**決定**: バックエンド（Python）で openpyxl を採用
- Python エコシステムでの標準的な選択
- スタイリング機能が充実
- FastAPI と相性が良い

---

### Topic 5: 大容量ファイルアップロード（フロントエンド）

**調査日**: 2025-12-27

**ソース**:
- [Next.js File Uploads: Server-Side Solutions](https://www.pronextjs.dev/next-js-file-uploads-server-side-solutions)
- [How to handle Large Files as Streams in Next.js 13+](https://dev.to/grimshinigami/how-to-handle-large-filefiles-streams-in-nextjs-13-using-busboymulter-25gb)

**主要なパターン**:

1. **file.stream() の使用**
   - `arrayBuffer()` は全体をメモリに読み込むため大容量ファイルには不適
   - `stream()` でチャンク単位で処理

2. **busboy によるストリーム処理**
   - NextRequest は Web Fetch API の Request を拡張
   - busboy でストリームベースの処理が可能

**設計への影響**:
- フロントエンドからは FormData で FastAPI に送信
- 大容量ファイルは FastAPI 側でストリーミング処理

---

### Topic 6: FastAPI + SQLAlchemy 2.0 非同期パターン

**調査日**: 2025-12-27

**ソース**:
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)
- [Setting up a FastAPI App with Async SQLALchemy 2.0 & Pydantic V2](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
- [Async APIs with FastAPI: Patterns, Pitfalls & Best Practices](https://shiladityamajumder.medium.com/async-apis-with-fastapi-patterns-pitfalls-best-practices-2d72b2b66f25)

**主要な発見**:

1. **非同期 DB アクセス**
   - SQLAlchemy 2.0 は非同期をファーストクラスでサポート
   - asyncpg ドライバを使用（PostgreSQL）
   - `create_async_engine` と `async_sessionmaker` を使用

2. **セッション管理**
   - FastAPI の依存性注入でセッションを管理
   - `async with` でセッションのライフサイクルを制御

3. **注意点**
   - asyncpg 0.29.0 以上で互換性問題あり
   - 同期的な操作が必要な場合は `run_in_threadpool` を使用

**設計への影響**:
- 非同期 SQLAlchemy を採用
- PostgreSQL + asyncpg を使用
- 依存性注入でセッション管理

---

### Topic 7: FastAPI ファイルアップロードのベストプラクティス

**調査日**: 2025-12-27

**ソース**:
- [How to Handle File Uploads in FastAPI](https://davidmuraya.com/blog/fastapi-file-uploads/)
- [Async File Uploads in FastAPI: Handling Gigabyte-Scale Data Smoothly](https://medium.com/@connect.hashblock/async-file-uploads-in-fastapi-handling-gigabyte-scale-data-smoothly-aec421335680)
- [Handling File Uploads in FastAPI: From Basics to S3 Integration](https://mahdijafaridev.medium.com/handling-file-uploads-in-fastapi-from-basics-to-s3-integration-fc7e64f87d65)

**主要なパターン**:

1. **UploadFile の使用**
   - `bytes` ではなく `UploadFile` を使用
   - ストリーミングでメモリ使用量を削減

2. **チャンク読み取り**
   - `await file.read()` は大容量ファイルに不適
   - チャンク単位で読み取り・書き込み

3. **セキュリティ対策**
   - ファイルサイズ制限の設定
   - MIME タイプの検証
   - ファイル名のサニタイズ

4. **S3 連携（オプション）**
   - 非常に大きなファイルは Presigned URL パターン
   - クライアントから直接 S3 にアップロード

**設計への影響**:
- 製造データは UploadFile + チャンク読み取り
- ファイルサイズ制限（100MB 推奨）
- 将来的な S3 連携を考慮した抽象化

---

## Architecture Decisions

### ADR-001: データフェッチングライブラリ（フロントエンド）

**決定**: SWR を採用

**理由**:
1. steering で既に指定されている
2. Next.js/Vercel エコシステムとの親和性
3. 本システムの要件（基本的な CRUD、一覧表示）に十分

**代替案**: TanStack Query
- 却下理由: バンドルサイズ増加、追加機能は不要

### ADR-002: Excel 生成ライブラリ（バックエンド）

**決定**: openpyxl を採用

**理由**:
1. Python エコシステムでの標準的な選択
2. スタイリング機能が無料で利用可能
3. FastAPI との相性が良い

**代替案**: xlsxwriter
- 却下理由: 読み取り機能がない（書き込み専用）

### ADR-003: ファイルアップロード実装

**決定**: FastAPI の UploadFile + チャンク処理

**理由**:
1. メモリ効率が良い
2. FastAPI の標準機能で実装可能
3. 将来的な S3 連携にも対応しやすい

### ADR-004: データベースアクセス

**決定**: 非同期 SQLAlchemy 2.0 + asyncpg

**理由**:
1. FastAPI の非同期特性を活かせる
2. 高パフォーマンス
3. SQLAlchemy 2.0 のファーストクラス非同期サポート

**注意点**:
- asyncpg < 0.29.0 を使用

### ADR-005: モノレポ構成

**決定**: api/ と web/ を分離したモノレポ構成

**理由**:
1. フロントエンドとバックエンドを独立して開発可能
2. OpenAPI スキーマを共有リソースとして管理
3. CI/CD パイプラインを統一管理

---

## Risks & Mitigations

### Risk 1: 製造データの大容量対応

**リスク**: 製造データが大容量の場合、メモリ不足やタイムアウトが発生する可能性

**軽減策**:
- FastAPI でチャンク読み取りを実装
- ファイルサイズ上限の設定（100MB）
- アップロード進捗表示の実装

### Risk 2: TOSYO DRIVE 連携

**リスク**: TOSYO DRIVE の API 仕様が不明確

**軽減策**:
- 抽象化レイヤーを設計し、実装時に詳細を確定
- モックによる開発進行

### Risk 3: 外部販売サイト API の認証

**リスク**: 外部販売サイトからの API 認証方式が未定義

**軽減策**:
- API Key 認証を基本設計
- JWT 対応も視野に入れた柔軟な設計

### Risk 4: フロントエンド・バックエンド間の型の乖離

**リスク**: OpenAPI スキーマと実装の不整合

**軽減策**:
- FastAPI の自動スキーマ生成を活用
- CI/CD でスキーマ生成と型生成を自動化
- E2E テストで型の整合性を検証

---

## Parallelization Considerations

以下のタスクは並列実行可能：

1. **バックエンド基盤**
   - プロジェクトセットアップ
   - DB モデル定義
   - 共通ユーティリティ

2. **フロントエンド基盤**
   - プロジェクトセットアップ
   - 共通コンポーネント実装
   - レイアウト実装

3. **ドメイン別実装（独立して実装可能）**
   - orders（受注管理）
   - manufacturers（メーカー管理）
   - shipments（配送管理）
   - products（商品マスタ）

**依存関係**:
- OpenAPI スキーマは DB モデル定義後に生成
- フロントエンド型生成は OpenAPI スキーマ完成後
- Feature 実装は共通基盤完成後

---

*Last Updated: 2025-12-27*
