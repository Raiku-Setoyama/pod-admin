#!/usr/bin/env python3
"""_exports.py — 顧客向け成果物の列定義（要件・検討事項・決定事項・不具合）を集約する。

export-csv.py（CSV）と export-xlsx.py（Excel 4 タブ）が同じ builder を使うことで、
CSV と Excel で列や絞り込みがぶれないようにする。列を足すときはここだけ直せばよい。

**要件と検討事項は同じ `docs/01-requirements/` から出る。** 違いは priority だけで、
合意済み（must / future）が「要件」、未判断・見送り（undecided / wont）が「検討事項」になる。
顧客に見せる単位が違うだけで、正本は 1 つである。

**不具合は `docs/05-defects/` から出る。別の層なので絞り込みが要らない。**
要件の一覧に混ざらないことがディレクトリの分離によって保証されている。

4 種すべての先頭に「領域」列を置いている。顧客がこの列で絞り込めることが目的なので、
列の位置は ID の直後から動かさない。

各 builder は `(header, rows)` を返す。`client=True` なら顧客向け（日本語ラベル・
内部項目を落とす）、`client=False` なら内部管理用（frontmatter をそのまま出す）。
"""
from __future__ import annotations

import re
from functools import lru_cache

from _docmodel import (
    AGREED,
    area_label,
    as_list,
    as_text,
    load_areas,
    load_docs,
    section_body,
    strip_comments,
)
from _labels import category_ja, priority_ja, status_ja


def first_section(text: str, heading: str, limit: int = 200) -> str:
    """本文から指定した見出しの直下を 1 行に畳んで返す。"""
    body = strip_comments(section_body(text, heading))
    body = re.sub(r"\s+", " ", body).strip()
    return body[:limit] + ("…" if len(body) > limit else "")


@lru_cache(maxsize=1)
def load_requirements() -> tuple[dict, ...]:
    """要件を 1 度だけ読む。要件タブと検討事項タブが同じディレクトリを見るため。"""
    return tuple(load_docs("01-requirements"))


@lru_cache(maxsize=1)
def load_defects() -> tuple[dict, ...]:
    """不具合を 1 度だけ読む。不具合タブと、要件タブの「未修正の不具合」列が使う。"""
    return tuple(load_docs("05-defects"))


@lru_cache(maxsize=1)
def open_defect_counts() -> dict[str, int]:
    """未修正の不具合を、それが指す文書 ID ごとに数える。

    「未修正」は「直すと決めていて（must / future）まだ done でないもの」。
    wont は「直さないと決めた」ので数えない。

    要件は不具合が出ても done のまま戻さない（done はマージ時点の履歴であって、
    今も満たしている保証ではない）。そのぶん **今この瞬間の健全性を要件の一覧に
    出すのはこの列の役目になる。** 保存はせず、ここで毎回導出する。
    """
    counts: dict[str, int] = {}
    for defect in load_defects():
        if defect.get("priority") not in AGREED or defect.get("status") == "done":
            continue
        for target in as_list(defect.get("defect_of")):
            counts[target] = counts.get(target, 0) + 1
    return counts


def build_requirements(client: bool) -> tuple[list[str], list[list[str]]]:
    """合意済みの要件。顧客の「何を作るか」の一覧。"""
    items = [i for i in load_requirements() if i.get("priority") in AGREED]
    areas = load_areas()
    open_defects = open_defect_counts()
    if client:
        header = ["ID", "領域", "要件", "種別", "対応区分", "実装状況", "未修正の不具合",
                  "対象リリース", "根拠（打合せ）", "最終更新"]
        rows = [[
            i["id"], area_label(areas, i), as_text(i.get("title")),
            category_ja(as_text(i.get("category"))),
            priority_ja("REQ", as_text(i.get("priority"))),
            status_ja("REQ", as_text(i.get("status"))),
            str(open_defects.get(i["id"], "") or ""),
            as_text(i.get("milestone")),
            as_text(i.get("source")), as_text(i.get("updated")),
        ] for i in items]
    else:
        header = ["ID", "area", "title", "priority", "status", "category", "milestone",
                  "depends_on", "estimate", "requester", "source", "related", "updated"]
        rows = [[
            i["id"], as_text(i.get("area")), as_text(i.get("title")),
            as_text(i.get("priority")), as_text(i.get("status")),
            as_text(i.get("category")), as_text(i.get("milestone")),
            as_text(i.get("depends_on")), as_text(i.get("estimate")),
            as_text(i.get("requester")), as_text(i.get("source")),
            as_text(i.get("related")), as_text(i.get("updated")),
        ] for i in items]
    return header, rows


def build_pending(client: bool) -> tuple[list[str], list[list[str]]]:
    """未判断（undecided）と見送り（wont）。顧客が判断する対象の一覧。

    見送りを落とさないのは意図的である。受託開発では「言われたが、やらないと決めた」
    記録そのものが資産になる。決めた理由と日付を列に出す。
    """
    items = [i for i in load_requirements() if i.get("priority") not in AGREED]
    areas = load_areas()
    if client:
        header = ["ID", "領域", "内容", "ご要望元", "状況",
                  "判断内容", "判断日", "最終更新"]
        rows = [[
            i["id"], area_label(areas, i), as_text(i.get("title")),
            as_text(i.get("requester")),
            priority_ja("REQ", as_text(i.get("priority"))),
            as_text(i.get("decision")), as_text(i.get("decided_at")),
            as_text(i.get("updated")),
        ] for i in items]
    else:
        header = ["ID", "area", "title", "priority", "category", "requester",
                  "source", "related", "decision", "decided_at", "背景", "updated"]
        rows = [[
            i["id"], as_text(i.get("area")), as_text(i.get("title")),
            as_text(i.get("priority")), as_text(i.get("category")),
            as_text(i.get("requester")), as_text(i.get("source")),
            as_text(i.get("related")),
            as_text(i.get("decision")), as_text(i.get("decided_at")),
            first_section(i["_body"], "背景・理由"),
            as_text(i.get("updated")),
        ] for i in items]
    return header, rows


def build_decisions(client: bool) -> tuple[list[str], list[list[str]]]:
    # 決定事項は検討中(proposed)・置き換え済み(superseded)も含めて全件出す。
    # proposed は「まだ決まっていない論点」であり、顧客の判断対象そのものである。
    items = load_docs("02-decisions")
    areas = load_areas()
    if client:
        header = ["ID", "領域", "決定内容・論点", "状況", "決定日",
                  "関連（要件）", "最終更新"]
        rows = [[
            i["id"], area_label(areas, i), as_text(i.get("title")),
            status_ja("ADR", as_text(i.get("status"))),
            as_text(i.get("date")), as_text(i.get("related")),
            as_text(i.get("updated")),
        ] for i in items]
    else:
        header = ["ID", "area", "title", "status", "date", "supersedes", "related",
                  "決定", "updated"]
        rows = [[
            i["id"], as_text(i.get("area")), as_text(i.get("title")),
            as_text(i.get("status")),
            as_text(i.get("date")), as_text(i.get("supersedes")),
            as_text(i.get("related")),
            first_section(i["_body"], "決定"),
            as_text(i.get("updated")),
        ] for i in items]
    return header, rows


def build_defects(client: bool) -> tuple[list[str], list[list[str]]]:
    """不具合。約束したものが満たされていない状態の一覧。

    絞り込まずに全件出す。「直さないと決めた（wont）」も残すのは検討事項と同じ理由で、
    受託開発では「不具合として報告を受けたが、仕様の範囲内と判断した」記録が資産になる。
    """
    items = load_defects()
    areas = load_areas()
    if client:
        header = ["ID", "領域", "不具合", "対象要件", "対応区分", "修正状況",
                  "対象リリース", "判断内容", "判断日", "最終更新"]
        rows = [[
            i["id"], area_label(areas, i), as_text(i.get("title")),
            as_text(i.get("defect_of")),
            priority_ja("BUG", as_text(i.get("priority"))),
            status_ja("BUG", as_text(i.get("status"))),
            as_text(i.get("milestone")),
            as_text(i.get("decision")), as_text(i.get("decided_at")),
            as_text(i.get("updated")),
        ] for i in items]
    else:
        header = ["ID", "area", "title", "priority", "status", "defect_of", "milestone",
                  "depends_on", "estimate", "requester", "source", "related",
                  "decision", "decided_at", "現象", "updated"]
        rows = [[
            i["id"], as_text(i.get("area")), as_text(i.get("title")),
            as_text(i.get("priority")), as_text(i.get("status")),
            as_text(i.get("defect_of")), as_text(i.get("milestone")),
            as_text(i.get("depends_on")), as_text(i.get("estimate")),
            as_text(i.get("requester")), as_text(i.get("source")),
            as_text(i.get("related")),
            as_text(i.get("decision")), as_text(i.get("decided_at")),
            first_section(i["_body"], "現象"),
            as_text(i.get("updated")),
        ] for i in items]
    return header, rows


# kind -> (CSV ファイル名で使うラベル, Excel のシート名, builder)
# 並び順が Excel のタブ順（要件 → 検討事項 → 決定事項 → 不具合）になる。
BUILDERS = {
    "requirements": ("要件一覧", "要件", build_requirements),
    "pending": ("検討事項一覧", "検討事項", build_pending),
    "decisions": ("決定事項", "決定事項", build_decisions),
    "defects": ("不具合一覧", "不具合", build_defects),
}
