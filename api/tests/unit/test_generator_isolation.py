"""生成は API のプロセスでは行わない（REQ-0067 / ADR-0039）.

生成の依存（numpy / scipy / pypdf、VectorCraft）はワーカー用のイメージにだけ入る。
API が起動の途中でそれらを import すると、API のイメージでは起動できなくなる。
"""

import os
import subprocess
import sys

import pytest

from app import generator
from app.generator.errors import GeneratorUnavailableError
from app.generator.vectorcraft import check_available
from app.utils.mfg_product_mapping import build_generation_spec

# ワーカー用のイメージにだけ入っている依存
_WORKER_ONLY = ("numpy", "scipy", "pypdf")


# サブプロセスで、ワーカー専用の依存が入っていない環境（API のイメージ）を作ってから import する
_HIDE_WORKER_ONLY = f"""
import importlib.abc, sys
class _Hide(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {_WORKER_ONLY!r}:
            raise ModuleNotFoundError(name)
        return None
sys.meta_path.insert(0, _Hide())
"""


@pytest.mark.parametrize("entry", ["app.main", "app.worker"])
def test_entry_points_start_without_generator_dependencies(entry: str) -> None:
    """API（app.main）もワーカー（app.worker）も、生成の依存が無くても起動できる.

    ワーカーは生成するときに初めて読み込む（関数の中で import している）。
    （openpyxl のように、numpy があれば使うだけのライブラリは問題にならない。）
    """
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "test"),
    }
    result = subprocess.run(
        [sys.executable, "-c", _HIDE_WORKER_ONLY + f"import {entry}\n"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr


def test_health_check_does_not_load_generator_dependencies() -> None:
    """死活確認は起動のたびに走るので、重い依存を読み込まない（無くても NG を返せる）."""
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "test"),
        "GENERATOR_VECTORCRAFT_CLI": "/nonexistent/vectorcraft-cli",
    }
    code = (
        "from app.generator import check_available\n"
        "from app.generator.errors import GeneratorUnavailableError\n"
        "try:\n    check_available()\nexcept GeneratorUnavailableError:\n    pass\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", _HIDE_WORKER_ONLY + code], capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr


def test_missing_vectorcraft_is_reported_as_unavailable() -> None:
    """実行ファイルが無いのは入力の誤りではない（生成待ちへ戻して復旧を待つ）."""
    with pytest.raises(GeneratorUnavailableError):
        check_available(cli="/nonexistent/vectorcraft-cli", timeout_seconds=5)


def test_generate_without_dependencies_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """依存が無いプロセス（API のイメージ）で呼ばれても、行は失敗ではなく生成待ちに戻る."""
    # import すると ImportError になるようにする（読み込み済みの属性も外す）
    monkeypatch.setitem(sys.modules, "app.generator.runner", None)
    monkeypatch.delattr(generator, "runner", raising=False)
    spec = build_generation_spec("sticker", "50x50mm", {"color", "cutline"})
    with pytest.raises(GeneratorUnavailableError, match="dependencies are not installed"):
        generator.generate(spec, {"color": b"", "cutline": b""}, "md-1")
