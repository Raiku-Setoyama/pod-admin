#!/usr/bin/env python3
"""_docmodel.py — docs/ の文書を読むための共有ヘルパ。

docs-lint.py / export-csv.py / export-requirements.py / migrate-to-unified.py が共通で使う。
frontmatter パーサ・コメント除去・値の文字列化・ID 種別ごとの読み込み・
領域（area）語彙の読み込み・**採否の語彙**を 1 箇所に集約する。これらが各スクリプトへ複製されると、
リンタと顧客向け成果物が同じ docs を別実装で解釈してしまい、内容が食い違う恐れがある。

依存パッケージなし。Python 3.9+ で動く。
`python3 scripts/<name>.py` で実行すると scripts/ が sys.path に入るため、
各スクリプトは `from _docmodel import ...` で読み込める。
"""
from __future__ import annotations

import re
from pathlib import Path

DOCS = Path("docs")

# 文書の種別はディレクトリで決まる。ID のプレフィックスでは決めない。
# 移行した案件では旧 ID の文書が残ることがあり、プレフィックスは種別を表さないため。
KINDS = {
    "01-requirements": "REQ",
    "02-decisions": "ADR",
    "03-meetings": "MTG",
    "05-defects": "BUG",
}

# 採否（priority）の語彙。「合意済みか」「理由が要るか」は、リンタ・顧客向け成果物・
# 移行ツールが同じ判定をしなければならない。だから定義はここ 1 か所だけに置く。
PRIORITIES = {"must", "future", "undecided", "wont"}
AGREED = {"must", "future"}          # 人間が採否を判断し、やると決めたもの
REQUIRES_REASON = {"future", "wont"}  # decision / decided_at が必須のもの

# 不具合に undecided は無い。要件の priority は「やると約束するか」だが、
# 不具合の priority は「すでにした約束をいつ果たすか」であり、採否を問う段階が存在しない。
# 起票は must から始まり、人間の判断が要るのは future / wont に下げるときだけになる。
DEFECT_PRIORITIES = PRIORITIES - {"undecided"}
PRIORITIES_BY_KIND = {"REQ": PRIORITIES, "BUG": DEFECT_PRIORITIES}

# 受入基準のチェックボックス。捕捉群は " "（未達）か "x"（達成）。
CHECKBOX = re.compile(r"^\s*-\s*\[([ x])\]", re.M)

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """ファイルから frontmatter を読む。返り値は parse_frontmatter_text と同じ。"""
    return parse_frontmatter_text(path.read_text(encoding="utf-8"))


def parse_frontmatter_text(text: str) -> tuple[dict, str]:
    """依存なしの簡易 YAML frontmatter パーサ。スカラーとフラットなリストのみ対応。

    返り値は (frontmatter dict, 本文)。frontmatter が無ければ ({}, 全文) を返す。
    全文を別の用途にも使う呼び出し側が、同じファイルを 2 回読まずに済むよう分けてある。
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    data: dict = {}
    for line in text[3:end].splitlines():
        line = line.split(" #")[0].rstrip()
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        else:
            data[key] = value.strip("\"'")
    return data, text[end + 4:]


def strip_comments(body: str) -> str:
    """HTML コメント（<!-- ... -->）を取り除く。"""
    return _HTML_COMMENT.sub("", body)


def as_text(value) -> str:
    """frontmatter の値を 1 つの文字列にする。リストは ", " で連結、None は空文字。"""
    if isinstance(value, list):
        return ", ".join(value)
    return str(value or "")


def as_list(value) -> list:
    """frontmatter の値をリストにする。単一値は 1 要素、空なら空リスト。"""
    if isinstance(value, list):
        return value
    return [value] if value else []


def section_body(text: str, heading: str) -> str:
    """`## <heading>` の直下から次の `##` までを返す。見つからなければ空文字。"""
    match = re.search(
        rf"^##\s*{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S
    )
    return match.group(1) if match else ""


def table_rows(path: Path, heading: str, header: str) -> list[list[str]]:
    """`## <heading>` の直下にある表の中身を、行ごとのセル配列として返す。

    見出し行・区切り行・空行は落とす。ファイルが無ければ空リスト。
    `00-charter/` の定義表（areas.md と id-migration.md）が同じ形なので、
    「表をどう読むか」の解釈をここ 1 か所に集約する。
    見出しで区切って読むのは、同じファイルの他の表を拾わないため。
    """
    if not path.exists():
        return []
    _, body = parse_frontmatter(path)

    rows: list[list[str]] = []
    for line in section_body(strip_comments(body), heading).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        key = cells[0].strip("`")
        # 見出し行と区切り行を落とす（空セルは区切り行の判定に含まれる）
        if key == header or set(key) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def load_areas(base: Path = DOCS) -> dict[str, dict]:
    """docs/00-charter/areas.md の「領域一覧」表から領域（area）の語彙を読む。

    返り値は {キー: {"label": 表示名, "state": active|retired}}。
    定義ファイルが無い、または表が空なら空 dict を返す。呼び出し側で扱いを決める。

    語彙は案件ごとに変わるため `_labels.py` ではなく docs 側を正本にしている。
    """
    areas: dict[str, dict] = {}
    for cells in table_rows(base / "00-charter" / "areas.md", "領域一覧", "キー"):
        if len(cells) < 4:
            continue
        key = cells[0].strip("`")
        areas[key] = {"label": cells[1] or key, "state": cells[3] or "active"}
    return areas


def load_id_aliases(base: Path = DOCS) -> set[str]:
    """docs/00-charter/id-migration.md の「対応表」から、廃止された旧 ID を読む。

    要求・要件・バックログの 3 層から統合モデルへ移行した案件では、RQ-XXXX / BL-XXXX が
    要件に畳み込まれて消える。議事録は追記のみで本文を書き換えられないため、旧 ID の
    参照だけが残る。それを参照切れにしないための表である。

    移行していないプロジェクトにはこのファイルが無い。その場合は空集合を返す。
    """
    return {
        cells[0].strip("`")
        for cells in table_rows(base / "00-charter" / "id-migration.md", "対応表", "旧 ID")
    }


def area_label(areas: dict, item: dict) -> str:
    """文書の area を顧客向けの表示名にする。未知のキーはそのまま返す。

    受け取るのはキーではなく frontmatter dict。顧客向け成果物はどれも
    「文書 → 表示名」しか必要としないので、呼び出し側で取り出し方がぶれないようにする。
    """
    key = as_text(item.get("area"))
    return (areas.get(key) or {}).get("label") or key


def load_docs(subdir: str, prefix: str | None = None, base: Path = DOCS) -> list[dict]:
    """base/subdir 配下の {prefix}-*.md を id 順に読み、id を持つものだけ返す。

    `prefix` を省略すると KINDS から決まる。明示するのは旧構造を読む移行ツールだけである。
    各要素は frontmatter dict に、本文を `_body`、パスを `_path` として添えたもの。
    """
    prefix = prefix or KINDS[subdir]
    items: list[dict] = []
    directory = base / subdir
    if not directory.exists():
        return items
    for path in sorted(directory.glob(f"{prefix}-*.md")):
        fm, body = parse_frontmatter(path)
        if fm.get("id"):
            fm["_body"] = body
            fm["_path"] = path
            items.append(fm)
    return items
