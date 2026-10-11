"""生成は API のプロセスでは行わない（REQ-0067 / ADR-0039）.

生成の依存（numpy / scipy / pypdf、VectorCraft）はワーカー用のイメージにだけ入る。
API が起動の途中でそれらを import すると、API のイメージでは起動できなくなる。
"""

import os
import subprocess
import sys

import pytest

from app.generator.errors import GeneratorUnavailableError
from app.generator.runner import check_available

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


def test_missing_vectorcraft_is_reported_as_unavailable() -> None:
    """実行ファイルが無いのは入力の誤りではない（生成待ちへ戻して復旧を待つ）."""
    with pytest.raises(GeneratorUnavailableError):
        check_available(cli="/nonexistent/vectorcraft-cli", timeout_seconds=5)
