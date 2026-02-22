.PHONY: help up down build rebuild logs ps restart clean \
        api-shell db-shell web-shell \
        migrate makemigrations seed seed-reset \
        test test-unit test-integration test-web test-e2e test-all \
        lint lint-api lint-web typecheck

# デフォルトターゲット
help:
	@echo "===== 開発環境 ====="
	@echo "  make up              - 全コンテナをバックグラウンドで起動"
	@echo "  make down            - 全コンテナを停止"
	@echo "  make build           - コンテナをビルド"
	@echo "  make rebuild         - コンテナを再ビルドして起動"
	@echo "  make restart         - コンテナを再起動"
	@echo "  make logs            - 全コンテナのログを表示"
	@echo "  make ps              - コンテナの状態を表示"
	@echo "  make clean           - コンテナとボリュームを削除"
	@echo ""
	@echo "===== シェルアクセス ====="
	@echo "  make api-shell       - APIコンテナに入る"
	@echo "  make web-shell       - Webコンテナに入る"
	@echo "  make db-shell        - DBコンテナに入る（psql）"
	@echo ""
	@echo "===== データベース ====="
	@echo "  make migrate         - マイグレーションを実行"
	@echo "  make makemigrations  - マイグレーションファイルを作成 (MSG=メッセージ)"
	@echo "  make seed            - シードデータを挿入"
	@echo "  make seed-reset      - データをリセットしてシードデータを再挿入"
	@echo ""
	@echo "===== テスト ====="
	@echo "  make test            - バックエンド全テスト"
	@echo "  make test-unit       - バックエンドユニットテスト"
	@echo "  make test-integration - バックエンド統合テスト"
	@echo "  make test-web        - フロントエンドテスト（vitest）"
	@echo "  make test-e2e        - E2Eテスト（Playwright）"
	@echo "  make test-all        - 全テスト実行"
	@echo ""
	@echo "===== コード品質 ====="
	@echo "  make lint            - 全体のリント"
	@echo "  make lint-api        - APIのリント（ruff）"
	@echo "  make lint-web        - Webのリント（eslint）"
	@echo "  make typecheck       - 型チェック"

# ===== 開発環境 =====
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v --remove-orphans

# ===== シェルアクセス =====
api-shell:
	docker compose exec api bash

web-shell:
	docker compose exec web sh

db-shell:
	docker compose exec db psql -U postgres -d pod_admin

# ===== データベース =====
migrate:
	docker compose exec api uv run alembic upgrade head

makemigrations:
ifndef MSG
	$(error MSG is required. Usage: make makemigrations MSG="your migration message")
endif
	docker compose exec api uv run alembic revision --autogenerate -m "$(MSG)"

seed:
	docker compose exec api uv run python scripts/seed.py

seed-reset:
	docker compose exec api uv run python scripts/seed.py --reset

# ===== テスト =====
test:
	docker compose exec api uv run pytest

test-unit:
	docker compose exec api uv run pytest tests/unit -v

test-integration:
	docker compose exec api uv run pytest tests/integration -v

test-web:
	docker compose exec web npm test

test-e2e:
	docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm e2e

test-all: test test-web test-e2e

# ===== コード品質 =====
lint: lint-api lint-web

lint-api:
	docker compose exec api uv run ruff check .
	docker compose exec api uv run ruff format --check .

lint-web:
	docker compose exec web npm run lint

typecheck:
	docker compose exec api uv run mypy app
