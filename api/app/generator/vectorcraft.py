"""VectorCraft をヘッドレスで操作する最小のクライアント.

`vectorcraft-cli mcp --headless` を子プロセスで起動し、標準入出力の JSON-RPC（MCP）で
``run_command``（全コマンドの入口）を呼ぶ。条件分岐や座標計算は Python 側で行い、
結果をコマンドで書き戻す。illustrator-vm の ExtendScript が担っていた役割である。

1 件の生成ごとに 1 プロセスを起動して使い捨てる。前の生成の文書や設定を持ち越さない。
時間の上限はセッション全体にかける（コマンドごとではない）。1 件の生成にかかる時間をこの値で押さえ、
Terraform がワーカー Job のタイムアウトを同じ値から導出する（``Settings.GENERATOR_TIMEOUT_SECONDS``）。
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from types import TracebackType
from typing import IO, Any

from app.generator.errors import (
    GenerationError,
    GenerationTimeoutError,
    GeneratorUnavailableError,
)

_PROTOCOL_VERSION = "2025-06-18"


class VectorCraftError(GenerationError):
    """VectorCraft がコマンドをエラーで返した（この入力では作れない）.

    時間内に終わらなかったときは ``GenerationTimeoutError`` にする（入口の ``generate`` が 1 回だけやり直す）。
    """


class VectorCraftCrashedError(GeneratorUnavailableError):
    """VectorCraft が途中で落ちた・応答が壊れた（入力ではなく生成処理の不調）.

    生成待ちへ戻して再試行する（``manufacturing_data_service._defer_or_fail``）。
    """


class VectorCraft:
    """1 プロセス分の VectorCraft セッション."""

    def __init__(self, cli: str, *, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds
        self._deadline = time.monotonic() + timeout_seconds
        try:
            self._proc = subprocess.Popen(
                [cli, "mcp", "--headless"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                # 壊れたバイトで読み取りのスレッドが止まると、応答が来ないまま時間切れまで待つことになる。
                # 置き換えて読めば、その行は壊れた応答として即座に扱える
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise GeneratorUnavailableError(f"cannot start {cli}: {exc}") from exc
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._stdin: IO[str] = self._proc.stdin
        # 読み出しは別スレッドで行い、待つ側はキューにタイムアウト付きで並ぶ。
        # readline() を直接待つと、VectorCraft が固まったときに永久に戻らない。
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._pump, args=(self._proc.stdout,), daemon=True).start()
        self._id = 0
        # 起動の途中で失敗したら必ず閉じる。コンストラクタが例外で抜けると with の __exit__ は
        # 呼ばれないので、ここで閉じないと子プロセスと読み取りのスレッドが残り続ける
        try:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "pod-admin-worker", "version": "1"},
                },
            )
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except BaseException as exc:
            self.close()
            if isinstance(exc, Exception):
                raise GeneratorUnavailableError(f"{cli} did not start: {exc}") from exc
            raise

    def _pump(self, stdout: IO[str]) -> None:
        for line in stdout:
            self._lines.put(line)
        self._lines.put(None)  # プロセスが終了した

    def _send(self, msg: dict[str, Any]) -> None:
        try:
            self._stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self._stdin.flush()
        except OSError as exc:
            raise VectorCraftCrashedError(f"vectorcraft-cli is not accepting input: {exc}") from exc

    def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        while True:
            try:
                line = self._lines.get(timeout=max(self._deadline - time.monotonic(), 0))
            except queue.Empty:
                self._proc.kill()
                raise GenerationTimeoutError(
                    f"generation did not finish within {self._timeout:.0f}s (at {method})"
                ) from None
            if line is None:
                raise VectorCraftCrashedError(f"vectorcraft-cli exited during {method}")
            try:
                msg = json.loads(line)
            except ValueError as exc:
                raise VectorCraftCrashedError(f"vectorcraft-cli wrote a broken reply: {exc}") from exc
            if not isinstance(msg, dict):
                raise VectorCraftCrashedError(f"vectorcraft-cli wrote a broken reply: {line[:200]}")
            if "method" in msg:
                continue  # VectorCraft からの通知・要求（応答ではない）
            if msg.get("id") is None and "error" in msg:
                # こちらの要求を読めなかった（id が付かない）。待っても応答は来ない
                raise VectorCraftError(f"{method}: {msg['error']}")
            if msg.get("id") != rid:
                continue
            if "error" in msg:
                raise VectorCraftError(f"{method}: {msg['error']}")
            if "result" not in msg:
                raise VectorCraftCrashedError(f"vectorcraft-cli wrote a broken reply: {line[:200]}")
            return msg["result"]

    def tool(self, name: str, args: dict[str, Any]) -> Any:
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        content = res.get("content", []) if isinstance(res, dict) else None
        if not isinstance(content, list) or not all(isinstance(c, dict) for c in content):
            raise VectorCraftCrashedError(f"vectorcraft-cli wrote a broken reply to {name}: {res!r:.200}")
        text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        if res.get("isError"):
            raise VectorCraftError(f"{name} {json.dumps(args, ensure_ascii=False)[:300]}: {text}")
        try:
            return json.loads(text)
        except ValueError:
            return text

    def cmd(self, command: str, **params: Any) -> Any:
        """コマンドを 1 つ実行する（`commands.list` に並ぶ ID と、その引数）."""
        return self.tool("run_command", {"command": command, "params": params})

    def inspect(self) -> Any:
        """開いている文書のレイヤー構成とアートボード."""
        return self.tool("inspect_document", {})

    def node(self, node_id: int) -> Any:
        """1 つのオブジェクトの中身（パスならアンカー）."""
        return self.cmd("document.node", id=node_id, summary=False)

    def close(self) -> None:
        try:
            self._stdin.close()
            self._proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self._proc.kill()
            self._proc.wait()  # 刈り取らないとゾンビが残る

    def __enter__(self) -> VectorCraft:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def check_available(*, cli: str, timeout_seconds: float) -> None:
    """VectorCraft を起動してコマンドが通ることを確かめる（ワーカーの死活確認）.

    起動しない・落ちたものは ``VectorCraft`` が ``GeneratorUnavailableError`` にする。
    ここでは、起動したがコマンドが通らない（エラー・時間切れ）ものも動かないとみなす。
    """
    try:
        with VectorCraft(cli, timeout_seconds=timeout_seconds) as vc:
            vc.cmd("edit.colorSettings")
    except GenerationError as exc:
        raise GeneratorUnavailableError(str(exc)) from exc
