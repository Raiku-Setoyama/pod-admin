"""Unit tests for the application logging configuration.

**この設定が無いと本番でアプリのログが出ない。** uvicorn はルートロガーを構成しないため、
``logger.info`` はハンドラのないルートへ伝播して捨てられる。ここで検証しているのは
「出ること」そのものであり、書式の好みではない。
"""

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    """テストがルートロガーを書き換えるので、元の構成へ戻す."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


class TestLogsActuallyReachTheOutput:
    def test_info_from_an_app_logger_is_emitted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """**これが本来の目的である。** 設定前は INFO がどこにも出ない."""
        configure_logging(level="INFO", log_format="text")
        logging.getLogger("app.services.some_service").info("generated md-1")

        assert "generated md-1" in capsys.readouterr().out

    def test_the_level_can_be_raised_to_drop_noise(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging(level="WARNING", log_format="text")
        log = logging.getLogger("app.noisy")
        log.info("chatter")
        log.warning("something is wrong")

        out = capsys.readouterr().out
        assert "chatter" not in out
        assert "something is wrong" in out


class TestStructuredOutput:
    """Cloud Logging が読む形（severity / message）で出ているか.

    ログベースのアラート（infra/modules/monitoring）がこの形に依存している。
    """

    def _emit(
        self, capsys: pytest.CaptureFixture[str], emit: Callable[[], None]
    ) -> dict[str, Any]:
        configure_logging(level="INFO", log_format="json")
        emit()
        entry: dict[str, Any] = json.loads(
            capsys.readouterr().out.strip().splitlines()[-1]
        )
        return entry

    def test_severity_and_message_are_top_level_keys(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        entry = self._emit(
            capsys,
            lambda: logging.getLogger("app.worker").warning("the VM is unreachable"),
        )

        assert entry["severity"] == "WARNING"
        assert entry["message"] == "the VM is unreachable"
        assert entry["logger"] == "app.worker"

    def test_format_arguments_are_interpolated(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """**素の %s のまま出さない。** 出すと検索もアラートも当たらない."""
        entry = self._emit(
            capsys,
            lambda: logging.getLogger("app").info("generated %s (%s)", "md-1", "a.ai"),
        )

        assert entry["message"] == "generated md-1 (a.ai)"

    def test_a_traceback_is_kept_with_the_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def boom() -> None:
            try:
                raise ValueError("boom")
            except ValueError:
                logging.getLogger("app").exception("generation crashed")

        entry = self._emit(capsys, boom)

        assert entry["severity"] == "ERROR"
        # 既定表示は message しか出さないので、追跡情報は message 側に畳む。
        assert "generation crashed" in entry["message"]
        assert "ValueError: boom" in entry["message"]

    def test_extra_fields_are_carried_through(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        entry = self._emit(
            capsys,
            lambda: logging.getLogger("app").info(
                "claimed", extra={"manufacturing_data_id": "md-1"}
            ),
        )

        assert entry["manufacturing_data_id"] == "md-1"


class TestItIsSafeToCallTwice:
    def test_handlers_do_not_pile_up(self, capsys: pytest.CaptureFixture[str]) -> None:
        """**入口が 2 つある**（API と worker）。重複して呼んでも二重に出さない."""
        configure_logging(level="INFO", log_format="text")
        configure_logging(level="INFO", log_format="text")
        logging.getLogger("app").info("once")

        assert capsys.readouterr().out.count("once") == 1
