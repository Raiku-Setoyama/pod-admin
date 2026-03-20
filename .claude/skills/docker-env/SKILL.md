---
name: docker-env
description: Docker環境のサービス検出・技術スタック判定・テスト実行コマンドのリファレンス
allowed-tools: Read, Grep, Glob
---

# Docker環境リファレンス

## コンテナ名特定

`docker-compose.yml` からサービス名を動的に特定する:

```bash
# フロントエンドサービス（優先順位: frontend > web > next > app）
FE_SERVICE=$(docker compose config --services 2>/dev/null | grep -E '^(frontend|web|next)$' | head -1)

# バックエンドサービス（優先順位: backend > api > server > fastapi > express > nest）
BE_SERVICE=$(docker compose config --services 2>/dev/null | grep -E '^(backend|api|server|fastapi|express|nest)$' | head -1)

# 単一サービスの場合は app を使用
if [ -z "$FE_SERVICE" ] && [ -z "$BE_SERVICE" ]; then
  APP_SERVICE=$(docker compose config --services 2>/dev/null | grep -E '^app$' | head -1)
fi
```

---

## 技術スタック判定

| 判定条件 | 種別 | テストランナー | ビルドコマンド | 静的検証 |
|----------|------|----------------|----------------|----------|
| `frontend/package.json` 存在 | フロントエンド | vitest | `npm run build` | tsc, eslint |
| `backend/pyproject.toml` or `requirements.txt` 存在 | Python BE | pytest | `python -m py_compile` | ruff, mypy |
| `backend/package.json` 存在 | TypeScript BE | vitest / jest | `npm run build` | tsc, eslint |
| ルートに `package.json` のみ | フルスタック TS | vitest | `npm run build` | tsc, eslint |

---

## テスト実行コマンド

### フロントエンド / TypeScript

```bash
# ユニットテスト
docker compose exec -T ${FE_SERVICE:-app} npm test -- --run tests/unit
# 統合テスト
docker compose exec -T ${FE_SERVICE:-app} npm test -- --run tests/integration
# カバレッジ確認
docker compose exec -T ${FE_SERVICE:-app} npm test -- --run --coverage
```

### Python バックエンド

```bash
# ユニットテスト
docker compose exec -T ${BE_SERVICE:-api} pytest tests/unit -v
# 統合テスト
docker compose exec -T ${BE_SERVICE:-api} pytest tests/integration -v
# カバレッジ確認
docker compose exec -T ${BE_SERVICE:-api} pytest --cov=app --cov-report=term-missing
```

### TypeScript バックエンド

```bash
# ユニットテスト
docker compose exec -T ${BE_SERVICE:-api} npm test -- --run tests/unit
# 統合テスト
docker compose exec -T ${BE_SERVICE:-api} npm test -- --run tests/integration
# カバレッジ確認
docker compose exec -T ${BE_SERVICE:-api} npm test -- --run --coverage
```
