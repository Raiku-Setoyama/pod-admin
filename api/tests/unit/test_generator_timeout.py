"""生成の時間切れ（REQ-0069）.

時間切れは 1 回だけやり直し、やり直しを含めて 1 件の上限（GENERATOR_TIMEOUT_SECONDS）を超えない。
VectorCraft の代わりに、応答しない偽の実行ファイルを使う。
"""

import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from app import generator
from app.config import settings
from app.generator import GeneratedFile, GenerationError, GenerationTimeoutError
from app.generator import runner as generator_runner
from app.generator.errors import GeneratorUnavailableError
from app.generator.vectorcraft import VectorCraft
from app.utils.mfg_product_mapping import build_generation_spec

SPEC = build_generation_spec("sticker", "50x50mm", {"color", "cutline"})


def _fake_cli(tmp_path: Path, *, answer_initialize: bool) -> str:
    """MCP の initialize にだけ答えて、そのあとは何も返さない偽の VectorCraft."""
    reply = (
        'print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {}}), flush=True)'
        if answer_initialize
        else "pass"
    )
    script = tmp_path / "vectorcraft-cli"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, sys, time\n"
        "for line in sys.stdin:\n"
        "    msg = json.loads(line)\n"
        "    if msg.get('method') == 'initialize':\n"
        f"        {reply}\n"
        "    elif 'id' in msg:\n"
        "        time.sleep(60)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _scripted_cli(tmp_path: Path, initialize_reply: str) -> str:
    """initialize に ``initialize_reply``（1 行そのまま）を返し、あとは何も返さない偽の VectorCraft."""
    script = tmp_path / "vectorcraft-cli"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "for line in sys.stdin:\n"
        f"    print({initialize_reply!r}, flush=True)\n"
        "    break\n"
        "for line in sys.stdin:\n"
        "    pass\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param("[1, 2]", id="オブジェクトでない"),
        pytest.param('{"jsonrpc": "2.0", "id": 1}', id="結果もエラーも無い"),
        pytest.param('{"jsonrpc": "2.0", "id": null, "error": {"code": -32700}}', id="要求を読めない"),
    ],
)
def test_broken_reply_while_starting_is_unavailable_and_closes(
    tmp_path: Path, reply: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """壊れた応答でも、時間切れまで待たずに「起動できない」になり、子プロセスを残さない."""
    started: list[subprocess.Popen[str]] = []
    popen = subprocess.Popen

    def recording_popen(*args: Any, **kwargs: Any) -> subprocess.Popen[str]:
        proc = popen(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    began = time.monotonic()
    with pytest.raises(GeneratorUnavailableError, match="did not start"):
        VectorCraft(_scripted_cli(tmp_path, reply), timeout_seconds=30)

    assert time.monotonic() - began < 15  # 時間切れ（30 秒）まで待っていない
    (proc,) = started
    assert proc.returncode is not None  # 閉じて刈り取ってある


def test_vectorcraft_that_stops_answering_times_out(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, answer_initialize=True)
    with VectorCraft(cli, timeout_seconds=1) as vc, pytest.raises(GenerationTimeoutError):
        vc.cmd("doc.new")


def test_timeout_while_starting_is_reported_as_unavailable(tmp_path: Path) -> None:
    """起動の応答が無いのは生成処理の不調であって、入力の誤りではない（生成待ちへ戻す）."""
    cli = _fake_cli(tmp_path, answer_initialize=False)
    with pytest.raises(GeneratorUnavailableError, match="did not start"):
        VectorCraft(cli, timeout_seconds=1)


class _Runner:
    """runner.generate の代役。``results`` を順に返す（例外なら投げる）."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.timeouts: list[float] = []

    def __call__(self, *args: Any, timeout_seconds: float, **kwargs: Any) -> GeneratedFile:
        self.timeouts.append(timeout_seconds)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, GeneratedFile)
        return result


def test_timeout_is_retried_once_within_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    done = GeneratedFile("out.ai", b"AI")
    fake = _Runner(GenerationTimeoutError("slow"), done)
    monkeypatch.setattr(generator_runner, "generate", fake)

    assert generator.generate(SPEC, {}, "md-1") == done

    # 上限を半分ずつに分ける（やり直しを含めて上限を超えない）
    assert fake.timeouts == [settings.GENERATOR_TIMEOUT_SECONDS / 2] * 2


def test_second_timeout_fails_the_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _Runner(GenerationTimeoutError("slow"), GenerationTimeoutError("slow again"))
    monkeypatch.setattr(generator_runner, "generate", fake)

    # 入力の誤りと同じ扱い（failed）になる
    with pytest.raises(GenerationError, match="slow again"):
        generator.generate(SPEC, {}, "md-1")
    assert len(fake.timeouts) == 2


def test_other_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _Runner(GenerationError("flat base edge not found"))
    monkeypatch.setattr(generator_runner, "generate", fake)

    with pytest.raises(GenerationError, match="flat base"):
        generator.generate(SPEC, {}, "md-1")
    assert len(fake.timeouts) == 1
