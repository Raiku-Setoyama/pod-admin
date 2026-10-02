#!/usr/bin/env python3
"""illustrator-vm の更新を、RDP を使わずに VM Manager（OS Config）で VM へ届ける OS ポリシーを作る.

手順の正本は infra/README.md「RDP を使わずに更新する（VM Manager）」。

なぜ git pull ではなく git bundle なのか:
    VM の作業ツリーは admin の対話セッションの資格情報で GitHub に入っており、
    対話なしでは `git pull` が認証で止まる（2026-10-02 に実測）。更新分の bundle を
    OS ポリシーのファイルとして届け、VM の上で fetch → fast-forward すれば、
    資格情報も権限の追加も要らず、VM の git の履歴は GitHub と同じになる。

OS ポリシーの上限に合わせて分割する:
    - スクリプト・ファイルの中身は 1 つ 1024 文字まで → base64 を 1000 文字ずつに分ける
    - 1 つのポリシーのリソースは 10 個まで → ポリシーを複数に分ける（記載順に適用される）
    分割したファイル名にはコミットを含める。前回の残りが混ざると復元が壊れるため。

VM の上では次の順に動く（SYSTEM が admin の対話セッションのタスクを起動する。
admin で動かすのは、作業ツリーの持ち主が admin で、install_service.ps1 が実行ユーザーで
タスクを登録するため）:
    分割を結合して bundle を復元 → git fetch → git merge --ff-only <commit>
    → scripts/setup_windows/deploy_update.ps1（スクリプトの再導入・生成 API の起動し直し）
    進み具合は Application ログ（PodAdminDeploy 902/903、IllustratorDeploy 2000〜2011）に残り、
    Ops Agent が Cloud Logging へ送る。

使い方:
    python3 infra/scripts/illustrator-vm-update-policy.py \\
        --repo ../illustrator-vm --base <VM の今の HEAD> --ref origin/main --out /tmp/policy.yaml
    python3 infra/scripts/illustrator-vm-update-policy.py --cleanup --out /tmp/cleanup.yaml
"""

from __future__ import annotations

import argparse
import base64
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT = "tosyo-api-504104"
ZONE = "asia-northeast1-a"
CHUNK_CHARS = 1000
MAX_RESOURCES = 10
SCRIPT_LIMIT = 1024

# VM 上の一時ファイル。**すべてこの接頭辞で始める**（片付けはこれで消す）。
WORK_PREFIX = "C:\\ProgramData\\pod-admin-deploy-"
TASK_NAME = "PodAdminDeploy"
CLEANUP_ASSIGNMENT = "illustrator-vm-deploy-cleanup"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def check_limit(name: str, script: str) -> None:
    if len(script) > SCRIPT_LIMIT:
        sys.exit(f"{name} is {len(script)} chars (OS Config allows {SCRIPT_LIMIT})")


def assemble(name: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    groups = [resources[i : i + MAX_RESOURCES] for i in range(0, len(resources), MAX_RESOURCES)]
    return {
        "osPolicies": [
            {
                "id": f"{name}-{i + 1}",
                "description": f"{name}（{i + 1}/{len(groups)}。完了後に削除する）",
                "mode": "ENFORCEMENT",
                "resourceGroups": [{"resources": group}],
            }
            for i, group in enumerate(groups)
        ],
        "instanceFilter": {"all": True},
        "rollout": {"disruptionBudget": {"fixed": 1}, "minWaitDuration": "0s"},
    }


def update_policy(repo: Path, base: str, ref: str) -> tuple[str, dict[str, Any]]:
    """更新の OS ポリシーを作り、(割り当て名, ポリシー) を返す."""
    refname = git(repo, "rev-parse", "--symbolic-full-name", ref)
    if not refname:
        sys.exit(f"--ref には参照名を指定する（コミット ID は bundle に入れられない）: {ref}")
    target = git(repo, "rev-parse", refname)
    rev = target[:7]
    git(repo, "merge-base", "--is-ancestor", base, target)  # fast-forward できること

    bundle = subprocess.run(
        ["git", "-C", str(repo), "bundle", "create", "-", f"{base}..{refname}"],
        check=True,
        capture_output=True,
    ).stdout
    encoded = base64.b64encode(bundle).decode()
    chunks = [encoded[i : i + CHUNK_CHARS] for i in range(0, len(encoded), CHUNK_CHARS)]

    chunk_glob = f"{WORK_PREFIX}{rev}-*.b64"
    bundle_path = f"{WORK_PREFIX}{rev}.bundle"
    bootstrap_path = f"{WORK_PREFIX}{rev}-bootstrap.ps1"
    marker = f"{WORK_PREFIX}{rev}-started"

    resources: list[dict[str, Any]] = [
        {
            "id": f"bundle-{i:02d}",
            "file": {"path": f"{WORK_PREFIX}{rev}-{i:02d}.b64", "state": "PRESENT", "content": chunk},
        }
        for i, chunk in enumerate(chunks)
    ]

    log = "eventcreate /L APPLICATION /T ERROR /SO PodAdminDeploy"
    bootstrap = f"""$ErrorActionPreference='Continue'
Set-Location C:\\illustrator-vm
$o=((git fetch '{bundle_path}' {refname} 2>&1|Out-String).Trim()) -replace '"',"'"
if($LASTEXITCODE){{{log} /ID 902 /D "git fetch failed: $o"|Out-Null;exit 1}}
$o=((git merge --ff-only {target} 2>&1|Out-String).Trim()) -replace '"',"'"
if($LASTEXITCODE){{{log} /ID 903 /D "git merge failed: $o"|Out-Null;exit 1}}
& .\\scripts\\setup_windows\\deploy_update.ps1
exit $LASTEXITCODE
"""
    enforce = f"""$f=Get-ChildItem '{chunk_glob}'|Sort-Object Name|ForEach-Object{{(Get-Content $_.FullName -Raw).Trim()}}
[IO.File]::WriteAllBytes('{bundle_path}',[Convert]::FromBase64String(($f -join '')))
$a=New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File {bootstrap_path}'
$p=New-ScheduledTaskPrincipal -UserId admin -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName {TASK_NAME} -Action $a -Principal $p -Force|Out-Null
Start-ScheduledTask -TaskName {TASK_NAME}
New-Item '{marker}' -ItemType File -Force|Out-Null
exit 100
"""
    validate = f"if (Test-Path '{marker}') {{ exit 100 }}\nexit 101\n"
    for name, script in (("bootstrap", bootstrap), ("enforce", enforce), ("validate", validate)):
        check_limit(name, script)

    resources.append(
        {"id": "bootstrap-file", "file": {"path": bootstrap_path, "state": "PRESENT", "content": bootstrap}}
    )
    resources.append(
        {
            "id": "start-deploy",
            "exec": {
                "validate": {"interpreter": "POWERSHELL", "script": validate},
                "enforce": {"interpreter": "POWERSHELL", "script": enforce},
            },
        }
    )
    name = f"illustrator-vm-deploy-{rev}"
    return name, assemble(name, resources)


def cleanup_policy() -> dict[str, Any]:
    """更新で残った一時ファイル（WORK_PREFIX*）と一時タスクを消す OS ポリシー."""
    validate = (
        f"if ((Get-ChildItem '{WORK_PREFIX}*' -ErrorAction SilentlyContinue) -or "
        f"(Get-ScheduledTask -TaskName {TASK_NAME} -ErrorAction SilentlyContinue)) {{ exit 101 }}\n"
        "exit 100\n"
    )
    enforce = (
        f"Unregister-ScheduledTask -TaskName {TASK_NAME} -Confirm:$false -ErrorAction SilentlyContinue\n"
        f"Remove-Item '{WORK_PREFIX}*' -Force -ErrorAction SilentlyContinue\n"
        "exit 100\n"
    )
    return assemble(
        CLEANUP_ASSIGNMENT,
        [
            {
                "id": "cleanup",
                "exec": {
                    "validate": {"interpreter": "POWERSHELL", "script": validate},
                    "enforce": {"interpreter": "POWERSHELL", "script": enforce},
                },
            }
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--repo", type=Path, help="illustrator-vm のローカルの clone")
    parser.add_argument("--base", help="VM の今の HEAD（bundle の起点）")
    parser.add_argument("--ref", default="origin/main", help="更新先の参照名（既定: origin/main）")
    parser.add_argument("--cleanup", action="store_true", help="片付けの OS ポリシーを作る")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    loc = f"--location={ZONE} --project={PROJECT}"
    if args.cleanup:
        name, policy = CLEANUP_ASSIGNMENT, cleanup_policy()
    else:
        if not (args.repo and args.base):
            parser.error("--repo と --base が要る（--cleanup 以外）")
        name, policy = update_policy(args.repo, args.base, args.ref)

    args.out.write_text(
        yaml.safe_dump(policy, allow_unicode=True, sort_keys=False, width=100000), encoding="utf-8"
    )
    print(f"# {args.out}: {len(policy['osPolicies'])} policies")
    print(f"gcloud compute os-config os-policy-assignments create {name} {loc} --file={args.out}")
    print(f"gcloud compute os-config os-policy-assignments delete {name} {loc} --quiet")


if __name__ == "__main__":
    main()
