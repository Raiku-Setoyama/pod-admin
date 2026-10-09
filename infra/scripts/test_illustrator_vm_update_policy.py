#!/usr/bin/env python3
"""illustrator-vm-update-policy.py のテスト.

実行: python3 infra/scripts/test_illustrator_vm_update_policy.py
（scripts/quality-gate.sh が毎回実行する。依存は git と PyYAML だけ）

VM と同じ手順（分割ファイルを名前順に結合）で bundle を復元し、git が読めることを確かめる。
なぜ名前順が問題になるかは illustrator-vm-update-policy.py の docstring を参照。
"""

from __future__ import annotations

import base64
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "update_policy", HERE / "illustrator-vm-update-policy.py"
)
assert _spec and _spec.loader
update_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_policy)
git = update_policy.git


def make_repo(root: Path, payload_bytes: int) -> tuple[Path, str]:
    """初期コミットの上に payload_bytes の更新を 1 コミット積んだ repo と、その起点を返す."""
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "README").write_text("base\n")
    git(repo, "add", "README")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    # 圧縮の効かない中身にして、bundle の大きさ（= 分割の数）を payload_bytes で決める
    (repo / "payload.bin").write_bytes(os.urandom(payload_bytes))
    git(repo, "add", "payload.bin")
    git(repo, "commit", "-q", "-m", "update")
    return repo, base


def chunk_files(policy: dict[str, Any]) -> list[tuple[str, str]]:
    """ポリシーに記載された順の (VM 上のパス, 中身)。分割ファイルだけを返す."""
    out = []
    for os_policy in policy["osPolicies"]:
        for group in os_policy["resourceGroups"]:
            for resource in group["resources"]:
                path = resource.get("file", {}).get("path", "")
                if path.endswith(".b64"):
                    out.append((path, resource["file"]["content"]))
    return out


def restore_like_vm(files: list[tuple[str, str]]) -> bytes:
    """VM の enforce と同じく、名前順に並べて結合し base64 を戻す."""
    # パスは同じ接頭辞（WORK_PREFIX + コミット）を持つので、パスの順＝ファイル名の順
    ordered = sorted(files)
    return base64.b64decode("".join(content.strip() for _, content in ordered))


class UpdatePolicyTest(unittest.TestCase):
    def assert_restorable(self, payload_bytes: int, min_chunks: int) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, base = make_repo(Path(tmp), payload_bytes)
            _, policy = update_policy.update_policy(repo, base, "main")

            files = chunk_files(policy)
            self.assertGreaterEqual(len(files), min_chunks)
            # 名前順に並べた結果が、分割した順序そのものであること
            names = [path for path, _ in files]
            self.assertEqual(names, sorted(names))

            bundle = Path(tmp) / "restored.bundle"
            bundle.write_bytes(restore_like_vm(files))
            git(repo, "bundle", "verify", str(bundle))

    def test_small_update_is_restorable(self) -> None:
        self.assert_restorable(payload_bytes=20_000, min_chunks=2)

    def test_update_over_100_chunks_is_restorable(self) -> None:
        # base64 で 1000 文字ずつ分割するので、約 110KB で 150 個前後になる
        self.assert_restorable(payload_bytes=110_000, min_chunks=101)


if __name__ == "__main__":
    unittest.main()
