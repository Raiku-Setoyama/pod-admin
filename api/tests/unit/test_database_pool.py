"""Unit tests for DB connection pool configuration (REQ-0052).

コンテナ実行基盤では「インスタンス数 × 1インスタンスあたりの接続数」が DB の
max_connections を超えると、増えたインスタンスが軒並み接続できなくなる。
小さい DB を使う環境ではプールを絞れる必要があるため、設定で変えられることを確認する。
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from app import database
from app.config import settings


def _engine_kwargs(**overrides: int) -> dict[str, object]:
    """設定を差し替えて get_engine を呼び、create_async_engine に渡った引数を返す."""
    database.get_engine.cache_clear()
    database.get_session_maker.cache_clear()
    try:
        with ExitStack() as stack:
            for name, value in overrides.items():
                stack.enter_context(patch.object(settings, name, value))
            create = stack.enter_context(
                patch.object(database, "create_async_engine", MagicMock())
            )
            database.get_engine()
        return dict(create.call_args.kwargs)
    finally:
        database.get_engine.cache_clear()
        database.get_session_maker.cache_clear()


class TestConnectionPoolSettings:
    def test_defaults_are_the_documented_values(self) -> None:
        # 既定値そのものを固定する。設定を参照して突き合わせると、実装と同じ変数を
        # 両辺に置くことになり、値がいくつでも通ってしまう。
        kwargs = _engine_kwargs()

        assert (kwargs["pool_size"], kwargs["max_overflow"]) == (5, 10)  # .env.example と一致

    def test_pool_can_be_narrowed_for_a_small_database(self) -> None:
        # 例: 同時接続の上限が小さいステージング用インスタンス
        kwargs = _engine_kwargs(DB_POOL_SIZE=2, DB_MAX_OVERFLOW=3)

        assert kwargs["pool_size"] == 2
        assert kwargs["max_overflow"] == 3
