.PHONY: help up down build rebuild logs api-shell db-shell migrate makemigrations test clean ps restart seed seed-reset

# デフォルトターゲット
help:
	@echo "利用可能なコマンド:"
	@echo "  make up              - コンテナをバックグラウンドで起動"
	@echo "  make down            - コンテナを停止"
	@echo "  make build           - コンテナをビルド"
	@echo "  make rebuild         - コンテナを再ビルドして起動"
	@echo "  make restart         - コンテナを再起動"
	@echo "  make logs            - 全コンテナのログを表示"
	@echo "  make logs-api        - APIコンテナのログを表示"
	@echo "  make ps              - コンテナの状態を表示"
	@echo "  make api-shell       - APIコンテナに入る"
	@echo "  make db-shell        - DBコンテナに入る（psql）"
	@echo "  make migrate         - マイグレーションを実行"
	@echo "  make makemigrations  - マイグレーションファイルを作成 (MSG=メッセージ)"
	@echo "  make seed            - シードデータを挿入"
	@echo "  make seed-reset      - データをリセットしてシードデータを再挿入"
	@echo "  make test            - テストを実行"
	@echo "  make clean           - コンテナとボリュームを削除"

# コンテナ操作
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

ps:
	docker compose ps

# シェルアクセス
api-shell:
	docker compose exec api bash

db-shell:
	docker compose exec db psql -U postgres -d pod_admin

# マイグレーション
migrate:
	docker compose exec api uv run alembic upgrade head

makemigrations:
ifndef MSG
	$(error MSG is required. Usage: make makemigrations MSG="your migration message")
endif
	docker compose exec api uv run alembic revision --autogenerate -m "$(MSG)"

# シードデータ
seed:
	docker compose exec api uv run python scripts/seed.py

seed-reset:
	docker compose exec api uv run python scripts/seed.py --reset

# テスト
test:
	docker compose exec api uv run pytest

# クリーンアップ
clean:
	docker compose down -v --remove-orphans
