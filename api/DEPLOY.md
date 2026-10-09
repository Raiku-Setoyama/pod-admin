# デプロイ

**本番・ステージングとも GCP である。** 手順の正本は
[`infra/README.md`](../infra/README.md) にあり、このファイルはその入口である。

> 2026-09-01 に Railway / Vercel から移行した（REQ-0054）。
> **旧 `railway up` の手順はもう使えない。** 誤って実行しても反映されない。

| 知りたいこと | 場所 |
|---|---|
| 反映のしかた | `infra/README.md`「デプロイ」 |
| **壊れたときに戻すしかた** | `infra/README.md`「切り戻す」 |
| インフラの変更 | `infra/README.md`「初回の手順」 |
| 製造データ生成を手で動かす | `infra/README.md`「製造データ生成を手動で動かす」 |
| VM に入る | `infra/README.md`「外部 IP を持たない VM に入る」 |

## 要点だけ

- 反映は GitHub Actions。**本番は `deploy-prod.yml` の手動実行のみ**で、
  確認のため `deploy-prod` と入力する必要がある（ADR-0028）
- 順序は **マイグレーション → API → 管理画面 → ワーカーのイメージを揃える**
- イメージのタグはコミット SHA（動いているリビジョンからコミットを一意に辿るため）
- **`terraform apply` は作業者の手元で実行する。** CI では動かさない（ADR-0031）

## 環境変数

実体は Terraform（`infra/modules/stack/main.tf`）が Cloud Run に渡している。
**手でコンソールから足さないこと。** 次の `apply` で消える。

秘匿値は Secret Manager 経由で渡る（`DATABASE_URL` / `SECRET_KEY` /
`INTERNAL_API_SECRET` / `SENDGRID_API_KEY`）。SendGrid の鍵だけは人間が入れる
（`infra/README.md`「SendGrid の鍵を入れる」）。

ローカル開発で使う値の一覧は [`.env.example`](.env.example) にある。
