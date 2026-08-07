#!/usr/bin/env python3
"""export-requirements.py — 分割された要件を 1 つの要件定義書に結合する。

使い方:
    python3 scripts/export-requirements.py                    # レビュー版（undecided 含む）
    python3 scripts/export-requirements.py --agreed-only      # 合意版（must / future のみ）
    python3 scripts/export-requirements.py --docx             # Word も出す（要 pandoc）

出力:
    dist/要件定義書.md    常に生成
    dist/要件定義書.docx  --docx かつ pandoc がある場合

合意版を作るときは、生成後に Git タグを打って版を確定させてください。
    git tag -a v1.0-requirements -m "要件定義 合意版 v1.0"
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

from _docmodel import (
    AGREED,
    area_label,
    as_text,
    load_areas,
    load_docs,
    parse_frontmatter,
    strip_comments,
)
from _labels import category_ja, priority_ja, status_ja

DOCS = Path("docs")
OUT = Path("dist")

CATEGORY_ORDER = ["functional", "non-functional", "constraint"]
PRIORITY_ORDER = {"must": 0, "future": 1, "undecided": 2, "wont": 3, "": 9}


def demote(body: str, levels: int = 2) -> str:
    """本文中の見出しを levels 段下げる。0 なら無変換。"""
    if levels <= 0:
        return body
    out = []
    in_code = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^#{1,5} ", line):
            line = "#" * levels + line
        out.append(line)
    return "\n".join(out)


def load_charter() -> dict:
    result = {}
    for name in ("charter", "nfr", "constraints"):
        path = DOCS / "00-charter" / f"{name}.md"
        if path.exists():
            _, body = parse_frontmatter(path)
            result[name] = strip_comments(body).strip()
    return result


@lru_cache(maxsize=1)
def all_requirements() -> tuple[dict, ...]:
    """要件を 1 度だけ読む。本文・未決事項の章の両方が同じディレクトリを見るため。"""
    return tuple(load_docs("01-requirements"))


def load_requirements(agreed_only: bool, areas: dict) -> list[tuple[dict, str]]:
    # 見送り（wont）は本文に載せない。判断の記録は管理表（検討事項タブ）が担う。
    allowed = AGREED if agreed_only else AGREED | {"undecided"}
    items = [
        (fm, strip_comments(fm["_body"]))
        for fm in all_requirements()
        if fm.get("priority") in allowed
    ]
    # 領域は areas.md に書かれた順に並べる。章立ての順序を人間が決められるようにするため。
    area_order = {key: index for index, key in enumerate(areas)}
    items.sort(key=lambda x: (
        CATEGORY_ORDER.index(x[0].get("category", "functional"))
        if x[0].get("category") in CATEGORY_ORDER else 9,
        area_order.get(x[0].get("area", ""), 999),
        PRIORITY_ORDER.get(x[0].get("priority", ""), 9),
        x[0]["id"],
    ))
    return items


def load_undecided() -> list[dict]:
    """まだ採否が決まっていない要件。"""
    return [fm for fm in all_requirements() if fm.get("priority") == "undecided"]


def load_open_decisions() -> list[dict]:
    """まだ決まっていない論点（proposed の ADR）。"""
    return [fm for fm in load_docs("02-decisions") if fm.get("status") == "proposed"]


def load_glossary() -> str:
    path = DOCS / "90-glossary.md"
    if not path.exists():
        return ""
    _, body = parse_frontmatter(path)
    return strip_comments(body).strip()


def git_version() -> str:
    try:
        tag = subprocess.run(
            ["git", "describe", "--tags", "--match", "v*-requirements", "--abbrev=0"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        return tag or f"draft ({sha})" if sha else "draft"
    except Exception:
        return "draft"


def history() -> list[str]:
    result = subprocess.run(
        ["git", "log", "--date=short", "--format=%ad|%s", "--", "docs/01-requirements/"],
        capture_output=True, text=True, check=False,
    )
    lines = [l for l in result.stdout.splitlines() if "|" in l][:30]
    return lines


def build(agreed_only: bool) -> str:
    charter = load_charter()
    areas = load_areas()
    reqs = load_requirements(agreed_only, areas)
    version = git_version()
    today = date.today().isoformat()
    label = "合意版" if agreed_only else "レビュー版"

    parts: list[str] = []
    parts.append("---")
    parts.append(f'title: "要件定義書"')
    parts.append(f'subtitle: "{label} / {version}"')
    parts.append(f"date: {today}")
    parts.append("---\n")

    parts.append("# 要件定義書\n")
    parts.append(f"| | |\n|---|---|\n| 版 | {version} |\n| 区分 | {label} |\n| 発行日 | {today} |\n")

    if not agreed_only:
        parts.append(
            "> この文書はレビュー版です。**【検討中】** と記載された要件は採否が未確定のため、"
            "やる / やらないのご判断をお願いします。\n"
        )

    parts.append("\\newpage\n")

    if charter.get("charter"):
        parts.append("# 1. プロジェクト概要\n")
        parts.append(demote(charter["charter"], 0).strip() + "\n")
        parts.append("\\newpage\n")

    # 要件本体
    parts.append("# 2. 要件一覧\n")
    parts.append("| ID | 領域 | 要件 | 対応区分 | 実装状況 |\n|---|---|---|---|---|")
    for fm, _ in reqs:
        parts.append(
            f"| {fm['id']} | {area_label(areas, fm)} | {fm.get('title','')} | "
            f"{priority_ja('REQ', fm.get('priority',''))} | {status_ja('REQ', fm.get('status',''))} |"
        )
    parts.append("\n\\newpage\n")

    # 分類（機能要件 / 非機能要件 / 制約事項）で章を、領域で節を切る。
    # reqs はこの順に並んでいるので、値が変わった時点が区切りになる。
    current_category = None
    current_area = None
    section = 2
    subsection = 0
    for fm, body in reqs:
        category = fm.get("category", "functional")
        if category != current_category:
            section += 1
            subsection = 0
            current_area = None
            parts.append(f"# {section}. {category_ja(category)}\n")
            current_category = category
        area = fm.get("area", "")
        if area != current_area:
            subsection += 1
            parts.append(f"## {section}-{subsection}. {area_label(areas, fm)}\n")
            current_area = area
        marker = "" if fm.get("priority") in AGREED else "【検討中】"
        parts.append(f"### {marker}{fm['id']} {fm.get('title','')}\n")
        meta = [
            f"対応区分: {priority_ja('REQ', fm.get('priority',''))}",
            f"実装状況: {status_ja('REQ', fm.get('status',''))}",
        ]
        if fm.get("milestone"):
            meta.append(f"対象リリース: {fm['milestone']}")
        if fm.get("source"):
            meta.append(f"根拠: {as_text(fm['source'])}")
        parts.append("*" + " / ".join(meta) + "*\n")
        parts.append(demote(body, 2).strip() + "\n")

    parts.append("\\newpage\n")

    if charter.get("nfr"):
        section += 1
        parts.append(f"# {section}. 非機能要件（全体）\n")
        parts.append(demote(charter["nfr"], 0).strip() + "\n")

    if charter.get("constraints"):
        section += 1
        parts.append(f"# {section}. 技術制約・前提\n")
        parts.append(demote(charter["constraints"], 0).strip() + "\n")

    glossary = load_glossary()
    if glossary:
        section += 1
        parts.append(f"# {section}. 用語集\n")
        parts.append(demote(glossary, 0).strip() + "\n")

    # 未決事項（採否が未確定の要件と、決まっていない論点）
    undecided = load_undecided()
    open_decisions = load_open_decisions()
    section += 1
    parts.append(f"# {section}. 未決事項\n")
    if undecided or open_decisions:
        parts.append(
            "本書の発行時点で未決の事項です。詳細は検討事項一覧をご参照ください。\n"
        )
        parts.append("| ID | 領域 | 内容 | 区分 |\n|---|---|---|---|")
        for fm in undecided:
            parts.append(
                f"| {fm['id']} | {area_label(areas, fm)} | "
                f"{fm.get('title','')} | 採否のご判断待ち |"
            )
        for fm in open_decisions:
            parts.append(
                f"| {fm['id']} | {area_label(areas, fm)} | "
                f"{fm.get('title','')} | 論点（選択肢のご判断待ち） |"
            )
        parts.append("")
    else:
        parts.append("現時点で未決の事項はありません。\n")

    # 改訂履歴
    section += 1
    parts.append(f"# {section}. 改訂履歴\n")
    lines = history()
    if lines:
        parts.append("| 日付 | 変更内容 |\n|---|---|")
        for line in lines:
            when, _, subject = line.partition("|")
            parts.append(f"| {when} | {subject} |")
    else:
        parts.append("（履歴なし）")
    parts.append("")

    return "\n".join(parts)


def to_docx(md_path: Path, docx_path: Path) -> bool:
    if not shutil.which("pandoc"):
        print("pandoc が見つからないため .docx はスキップしました。", file=sys.stderr)
        print("  macOS: brew install pandoc / Ubuntu: apt install pandoc", file=sys.stderr)
        return False
    cmd = [
        "pandoc", str(md_path), "-o", str(docx_path),
        "--from", "markdown+raw_tex", "--to", "docx",
        # 章（分類）・節（領域）・要件の 3 階層を目次に出す
        "--standalone", "--toc", "--toc-depth=3",
    ]
    reference = Path("_templates/reference.docx")
    if reference.exists():
        cmd += ["--reference-doc", str(reference)]
    lua = Path("_templates/pagebreak.lua")
    if lua.exists():
        cmd += ["--lua-filter", str(lua)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agreed-only", action="store_true",
        help="採否が確定した要件（must / future）のみ収録する",
    )
    parser.add_argument("--docx", action="store_true", help="Word 形式も生成する")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    if not DOCS.exists():
        print("docs/ が見つかりません。リポジトリのルートで実行してください。", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "要件定義書.md"
    md_path.write_text(build(args.agreed_only), encoding="utf-8")
    print(f"生成: {md_path}")

    if args.docx:
        docx_path = out_dir / "要件定義書.docx"
        if to_docx(md_path, docx_path):
            print(f"生成: {docx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
