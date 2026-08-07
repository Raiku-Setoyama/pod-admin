#!/usr/bin/env python3
"""export-wbs.py — 要件から WBS / スケジュールを生成する。

使い方:
    python3 scripts/export-wbs.py               # dist/wbs.md を生成
    python3 scripts/export-wbs.py --stdout      # 標準出力に出す（生成物は残さない）
    python3 scripts/export-wbs.py --actionable  # 着手可能な要件・不具合を 1 行ずつ出す

**未修正の不具合も載せる。** 不具合は要件のスケジュールではないので依存グラフと
マイルストーンの表には混ぜないが、**マイルストーンに残っている作業から外すと計画が嘘になる。**
`--actionable` は両方を出す。`/implement` が要件と不具合の両方を受けるためである。

**WBS は要件からの投影であり、正本ではない。** だから docs/ ではなく dist/ に出す。
顧客向け成果物（export-csv.py など）と同じ扱いである。理由は 2 つ。

1. 固有の情報を 1 つも持たない。表の列はすべて要件の frontmatter から出る。
   人間が入れる見積（estimate）とマイルストーン（milestone）も要件側に書く。
2. コミットすると、並行する起票 PR が同じファイルを書き換えて必ず衝突する。
   要件は別ファイルなので衝突しないのに、その投影だけが衝突源になる。

出力:
    dist/wbs.md
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from _docmodel import (
    AGREED,
    CHECKBOX,
    area_label,
    as_list,
    as_text,
    load_areas,
    load_docs,
    section_body,
    strip_comments,
)

OUT = Path("dist")
UNASSIGNED = "unassigned"
NO_MILESTONE = "マイルストーン未設定"

# docs-lint.py と同じ形を見る。ID の有無はリンタが検査するので、ここでは存在だけを判定する。
NEEDS_DECISION = re.compile(r"\[NEEDS-DECISION(?::\s*[^\]]*)?\]")


def blockers(item: dict, done_ids: set[str]) -> list[str]:
    """着手条件のうち満たしていないものを列挙する。空リストなら着手可能。

    **AGENTS.md「着手可能かどうかは保存しない」の機械判定はここが正本である。**
    フラグとして保存すると、立てたあとに前提が崩れても立ったままになる。
    導出ならその事故が起きない。

    **要件と不具合の両方に同じ条件が効く。** 不具合は priority の語彙が違う
    （undecided が無い）だけで、着手できるかどうかの条件は同一である。
    種別ごとに判定を分けると、片方だけ直された判定が 2 つ並ぶ。
    """
    reasons: list[str] = []
    if item.get("priority") not in AGREED:
        reasons.append(f"priority が {as_text(item.get('priority')) or '未設定'}")
    if item.get("status") != "not-started":
        reasons.append(f"status が {as_text(item.get('status')) or '未設定'}")

    body = strip_comments(as_text(item.get("_body")))
    if not CHECKBOX.findall(section_body(body, "受入基準")):
        reasons.append("受入基準が空")
    if NEEDS_DECISION.search(body):
        reasons.append("[NEEDS-DECISION] が残っている")
    if as_text(item.get("area")) in ("", UNASSIGNED):
        reasons.append("area が未確定")

    unmet = [d for d in as_list(item.get("depends_on")) if d not in done_ids]
    if unmet:
        reasons.append("依存が未完了（" + ", ".join(unmet) + "）")
    return reasons


def table(header: list[str], rows: list[list[str]]) -> str:
    """Markdown の表にする。行がなければ空表ではなく一行の説明を返す。"""
    if not rows:
        return "（該当なし）\n"
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def by_milestone(items: list[dict]) -> list[tuple[str, list[dict]]]:
    """マイルストーンごとにまとめる。未設定は必ず最後に置く。"""
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(as_text(item.get("milestone")) or NO_MILESTONE, []).append(item)
    return sorted(groups.items(), key=lambda kv: (kv[0] == NO_MILESTONE, kv[0]))


def dependency_graph(items: list[dict]) -> str:
    """depends_on から mermaid の有向グラフを作る。"""
    edges = [f"  {dep} --> {i['id']}"
             for i in items for dep in as_list(i.get("depends_on"))]
    if not edges:
        return "依存関係は登録されていません。\n"
    return "```mermaid\ngraph LR\n" + "\n".join(edges) + "\n```\n"


def parallel_groups(actionable: list[dict], areas: dict) -> str:
    """領域ごとに着手可能な要件をまとめる。

    領域が異なる要件はファイル競合が起きにくいので、並行して走らせる単位になる。
    """
    groups: dict[str, list[str]] = {}
    for item in actionable:
        groups.setdefault(area_label(areas, item), []).append(item["id"])
    if len(groups) < 2:
        return "並行して着手できる組み合わせはありません（着手可能な領域が 1 つ以下）。\n"
    lines = [f"- **{label}**: {', '.join(ids)}" for label, ids in sorted(groups.items())]
    return "\n".join(lines) + "\n"


def defect_section(open_defects: list[dict], done_ids: set[str], areas: dict) -> str:
    """未修正の不具合を、マイルストーンごとに出す。

    要件の表と依存グラフには混ぜない。**不具合はスケジュールへの約束ではなく、
    済んだ約束の履行漏れ**であり、混ぜると計画と瑕疵の区別が消える。
    それでも同じ節に出すのは、マイルストーンに残っている作業から外すと計画が嘘になるためである。
    """
    if not open_defects:
        return "（未修正の不具合はありません）\n"

    rows = []
    for milestone, items in by_milestone(open_defects):
        for item in items:
            reasons = blockers(item, done_ids)
            rows.append([
                item["id"], milestone, area_label(areas, item),
                as_text(item.get("title")), as_text(item.get("defect_of")),
                "着手可能" if not reasons else "／".join(reasons),
            ])
    return table(["ID", "マイルストーン", "領域", "現象", "対象", "状況"], rows)


def build(scheduled: list[dict], done_ids: set[str], areas: dict,
          open_defects: list[dict]) -> str:
    """WBS の本文を組み立てる。"""
    blocked = {i["id"]: blockers(i, done_ids) for i in scheduled}
    actionable = [i for i in scheduled if not blocked[i["id"]]]

    parts = [
        "# WBS / スケジュール",
        "",
        "<!-- scripts/export-wbs.py が docs/01-requirements/ と docs/05-defects/ から",
        "     生成しています。直接編集しないでください。 -->",
        f"<!-- 生成日: {date.today().isoformat()} -->",
        "",
        "対象は `priority` が `must` / `future` で、`status` が `done` でない要件と不具合です。",
        "**不具合はスケジュールへの約束ではないので、マイルストーンの表と依存グラフには含めません。**",
        "末尾の「未修正の不具合」に別途出します。",
        "",
        "## マイルストーン",
        "",
    ]

    for milestone, items in by_milestone(scheduled):
        parts.append(f"### {milestone}（{len(items)} 件）")
        parts.append("")
        parts.append(table(
            ["REQ-ID", "領域", "要件", "priority", "status", "見積", "依存", "着手"],
            [[
                i["id"],
                area_label(areas, i),
                as_text(i.get("title")),
                as_text(i.get("priority")),
                as_text(i.get("status")),
                as_text(i.get("estimate")) or "TBD",
                ", ".join(as_list(i.get("depends_on"))) or "—",
                "可" if not blocked[i["id"]] else "待ち",
            ] for i in items],
        ))
        parts.append("")

    parts += [
        "## 依存関係",
        "",
        dependency_graph(scheduled),
        "## 着手可能な要件",
        "",
        "条件は `AGENTS.md`「着手可能かどうかは保存しない」のとおりです。",
        "**フラグとして保存していないので、この一覧は生成した時点の判定です。**",
        "不具合も同じ条件で判定します（`--actionable` は両方を出します）。",
        "",
        table(["REQ-ID", "領域", "要件"],
              [[i["id"], area_label(areas, i), as_text(i.get("title"))] for i in actionable]),
        "",
        "## 並行して着手できる組み合わせ",
        "",
        parallel_groups(actionable, areas),
        "## 着手条件を満たさない要件",
        "",
        table(["REQ-ID", "不足しているもの"],
              [[i["id"], " / ".join(blocked[i["id"]])] for i in scheduled if blocked[i["id"]]]),
        "",
        "## 未修正の不具合",
        "",
        "**要件のスケジュールとは別枠です。** 要件は不具合が出ても `done` のまま戻さないので",
        "（`AGENTS.md`「元の要件は `done` のまま戻さない」）、**残っている作業はここに出ます。**",
        "",
        defect_section(open_defects, done_ids, areas),
        "",
        "## 見積もりが未入力の要件",
        "",
        "<!-- estimate は人間が入れます。エージェントは TBD のままにします -->",
        "",
    ]

    pending = [i["id"] for i in scheduled if (as_text(i.get("estimate")) or "TBD") == "TBD"]
    parts.append(", ".join(pending) if pending else "なし")
    parts.append("")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="要件から WBS を生成する")
    parser.add_argument("--stdout", action="store_true", help="ファイルに書かず標準出力に出す")
    parser.add_argument("--actionable", action="store_true",
                        help="着手可能な要件だけを 1 行ずつ出す")
    args = parser.parse_args()

    requirements = load_docs("01-requirements")
    defects = load_docs("05-defects")
    areas = load_areas()
    # 依存の解決には両方の done が要る。不具合が要件に依存することも、その逆もありうる。
    done_ids = {i["id"] for i in requirements + defects if i.get("status") == "done"}
    scheduled = [i for i in requirements
                 if i.get("priority") in AGREED and i.get("status") != "done"]
    open_defects = [i for i in defects
                    if i.get("priority") in AGREED and i.get("status") != "done"]

    if args.actionable:
        rows = [("要件", i) for i in scheduled] + [("不具合", i) for i in open_defects]
        found = False
        for kind, item in rows:
            if not blockers(item, done_ids):
                found = True
                print(f"{item['id']}\t{kind}\t{area_label(areas, item)}\t{as_text(item.get('title'))}")
        if not found:
            print("着手可能な要件・不具合はありません")
        return

    document = build(scheduled, done_ids, areas, open_defects)
    if args.stdout:
        print(document, end="")
        return

    OUT.mkdir(exist_ok=True)
    path = OUT / "wbs.md"
    path.write_text(document, encoding="utf-8")
    print(f"生成しました: {path}（対象 {len(scheduled)} 件）")


if __name__ == "__main__":
    main()
