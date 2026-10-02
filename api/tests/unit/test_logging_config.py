"""Unit tests for app.logging_config (Cloud Logging 向けのログ出力)."""

import json
import logging
import sys
from collections.abc import Iterator

import pytest

from app.logging_config import (
    CloudLoggingFormatter,
    configure_logging,
    quiet_noisy_dependencies,
)


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level


def _record(level: int, msg: str, exc_info: object = None) -> logging.LogRecord:
    return logging.LogRecord("app.x", level, __file__, 1, msg, None, exc_info)  # type: ignore[arg-type]


class TestCloudLoggingFormatter:
    def test_info_is_json_with_severity(self) -> None:
        line = CloudLoggingFormatter().format(_record(logging.INFO, "アラートを送った"))
        assert json.loads(line) == {
            "severity": "INFO",
            "message": "アラートを送った",
            "logger": "app.x",
        }

    def test_exception_includes_traceback_in_message(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            record = _record(logging.ERROR, "failed", sys.exc_info())
        payload = json.loads(CloudLoggingFormatter().format(record))
        assert payload["severity"] == "ERROR"
        assert payload["message"].startswith("failed\nTraceback")
        assert "ValueError: boom" in payload["message"]


class TestConfigureLogging:
    def test_json_to_stdout_on_cloud_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("K_SERVICE", "pod-admin-api")
        configure_logging()

        (handler,) = logging.getLogger().handlers
        assert isinstance(handler.formatter, CloudLoggingFormatter)
        assert getattr(handler, "stream", None) is sys.stdout
        assert logging.getLogger().level == logging.INFO

    def test_plain_text_locally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("K_SERVICE", raising=False)
        configure_logging()

        (handler,) = logging.getLogger().handlers
        assert not isinstance(handler.formatter, CloudLoggingFormatter)

    def test_info_from_app_loggers_is_emitted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """設定前に消えていた app.* の INFO が出ること（今回の不具合そのもの）."""
        monkeypatch.setenv("K_SERVICE", "pod-admin-api")
        configure_logging()

        logging.getLogger("app.services.monitoring_alert_notification").info("sent")

        assert json.loads(capsys.readouterr().out.strip())["message"] == "sent"


class TestNoisyDependencies:
    """**ルートに水準を与えた副作用で、依存ライブラリの INFO が一斉に出る。**

    httpx は 1 リクエスト 1 行で、製造データ 1 件の生成が VM の完了待ちだけで 70 行を
    超える（5 秒間隔・最大 360 秒）。読む人は居ないうえに取り込みは従量である。
    """

    def test_httpx_info_is_silenced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("K_SERVICE", raising=False)
        configure_logging()

        assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
        # 自分たちのログは落とさない
        assert logging.getLogger("app.worker").getEffectiveLevel() == logging.INFO

    def test_callable_without_configure_logging(self) -> None:
        """ワーカーは basicConfig を使い configure_logging を通らないので、単体で呼べること."""
        logging.getLogger("httpx").setLevel(logging.INFO)
        quiet_noisy_dependencies()

        assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING
