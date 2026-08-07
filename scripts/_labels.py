#!/usr/bin/env python3
"""_labels.py — 顧客向け成果物で使う日本語ラベルの一元管理。

採否（priority）・実装状態（status）・分類（category）の日本語表記を定義する。
CSV（export-csv）と要件定義書（export-requirements）が同じ状態に同じ語を使うようにし、
成果物ごとに表記がぶれるのを防ぐ。

status と priority を種別ごとにネストしているのは、種別によって語彙も訳語も違うため。
status は要件と ADR でまったく違う値を取る。priority は値こそ共通だが、
**要件と不具合で意味が違うので訳語も変える**（要件の must は「対応」、不具合の must は「修正対応」）。
同じ「対応」という語を両方に使うと、顧客が不具合を新規要件と読み違える。
category は要件だけが持つのでフラットな 1 枚の表でよい。
"""
from __future__ import annotations

# 採否・約束の度合い。人間が PR のマージで決める軸。
# 要件の priority は「やると約束するか」、不具合の priority は「すでにした約束をいつ果たすか」。
PRIORITY_JA = {
    "REQ": {
        "must": "対応",
        "future": "次期フェーズ",
        "undecided": "検討中",
        "wont": "対象外",
    },
    "BUG": {
        "must": "修正対応",
        "future": "次期修正",
        "wont": "現状仕様",
    },
}

# 実装の進み具合。エージェントが進める軸。
STATUS_JA = {
    "REQ": {
        "not-started": "未着手",
        "in-progress": "実装中",
        "done": "完了",
        "on-hold": "保留",
    },
    "ADR": {
        "proposed": "検討中",
        "accepted": "決定",
        "superseded": "置き換え済み",
    },
    "BUG": {
        "not-started": "未着手",
        "in-progress": "修正中",
        "done": "修正済み",
        "on-hold": "保留",
    },
}

CATEGORY_JA = {
    "functional": "機能要件",
    "non-functional": "非機能要件",
    "constraint": "制約事項",
}


def priority_ja(kind: str, priority: str) -> str:
    """種別 kind の採否 priority を日本語にする。未知ならそのまま返す。"""
    return PRIORITY_JA.get(kind, {}).get(priority, priority)


def status_ja(kind: str, status: str) -> str:
    """種別 kind の実装状態 status を日本語にする。未知ならそのまま返す。"""
    return STATUS_JA.get(kind, {}).get(status, status)


def category_ja(category: str) -> str:
    """要件の分類 category を日本語にする。未知ならそのまま返す。"""
    return CATEGORY_JA.get(category, category)
