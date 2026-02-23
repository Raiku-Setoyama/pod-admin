.PHONY: help up down build rebuild logs ps restart clean \
        api-shell web-shell db-shell \
        migrate makemigrations seed seed-reset \
        test test-api test-web test-coverage e2e

# デフォルトターゲット
help:
	@echo "============================================"
	@echo "POD Admin - 開発コマンド一覧"
	@echo "============================================"
	@echo ""
	@echo "■ コンテナ操作"
	@echo "  make up              - 全サービス起動（api + web + db）"
	@echo "  make down            - 全サービス停止"
	@echo "  make build           - コンテナビルド"
	@echo "  make rebuild         - コンテナ再ビルド（キャッシュなし）"
	@echo "  make restart         - コンテナ再起動"
	@echo "  make logs            - 全コンテナのログ表示"
	@echo "  make ps              - コンテナ状態表示"
	@echo "  make clean           - コンテナ・ボリューム削除"
	@echo ""
	@echo "■ シェルアクセス"
	@echo "  make api-shell       - APIコンテナに入る"
	@echo "  make web-shell       - Webコンテナに入る"
	@echo "  make db-shell        - DBコンテナに入る（psql）"
	@echo ""
	@echo "■ マイグレーション"
	@echo "  make migrate         - マイグレーション実行"
	@echo "  make makemigrations  - マイグレーション作成（MSG=メッセージ）"
	@echo "  make seed            - シードデータ挿入"
	@echo "  make seed-reset      - データリセット＆シード再挿入"
	@echo ""
	@echo "■ テスト"
	@echo "  make test            - 全テスト実行（API + Web）"
	@echo "  make test-api        - APIテスト実行（pytest）"
	@echo "  make test-web        - Webテスト実行（vitest）"
	@echo "  make test-coverage   - 全テスト＋カバレッジ"
	@echo "  make e2e             - E2Eテスト実行（Playwright）"

# ============================================
# コンテナ操作
# ============================================
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

logs-api:
	docker compose logs -f api

logs-web:
	docker compose logs -f web

ps:
	docker compose ps

# ============================================
# シェルアクセス
# ============================================
api-shell:
	docker compose exec api bash

web-shell:
	docker compose exec web sh

db-shell:
	docker compose exec db psql -U postgres -d pod_admin

# ============================================
# マイグレーション
# ============================================
migrate:
	docker compose exec api uv run alembic upgrade head

makemigrations:
ifndef MSG
	$(error MSG is required. Usage: make makemigrations MSG="your migration message")
endif
	docker compose exec api uv run alembic revision --autogenerate -m "$(MSG)"

# ============================================
# シードデータ
# ============================================
seed:
	docker compose exec api uv run python scripts/seed.py

seed-reset:
	docker compose exec api uv run python scripts/seed.py --reset

# ============================================
# テスト
# ============================================
test: test-api test-web

test-api:
	docker compose exec api uv run pytest

test-api-unit:
	docker compose exec api uv run pytest tests/unit

test-api-integration:
	docker compose exec api uv run pytest tests/integration

test-web:
	docker compose exec web npm run test:run

test-web-unit:
	docker compose exec web npm run test:run -- tests/unit

test-coverage:
	docker compose exec api uv run pytest --cov=app --cov-report=term --cov-report=html
	docker compose exec web npm run test:coverage

e2e:
	docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm e2e

# ============================================
# クリーンアップ
# ============================================
clean:
	docker compose down -v --remove-orphans
