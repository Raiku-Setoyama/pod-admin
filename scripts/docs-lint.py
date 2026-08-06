#!/usr/bin/env python3
"""docs-lint.py — docs/ 配下の ID 整合性を検査する。

検査する内容:
  1. frontmatter の必須フィールドが揃っているか
  2. ファイル名と frontmatter の id が一致しているか
  3. 参照している ID が実在するか（参照切れ）
  4. status / priority が定義された値か
  5. 採否と実装状態の整合（合意していないものを実装していないか、完了の申告が正しいか）
  6. 合意した要件に受入基準があるか
  7. 議事録 raw ファイルに対応する構造化議事録があるか
  8. area が areas.md に定義された領域か、判断ゲートまでに確定しているか

依存パッケージなし。Python 3.9+ で動く。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _docmodel import (
    AGREED,
    CHECKBOX,
    KINDS,
    PRIORITIES,
    REQUIRES_REASON,
    as_list,
    load_areas,
    load_id_aliases,
    parse_frontmatter,
    section_body,
)

DOCS = Path("docs")
AREAS_FILE = "docs/00-charter/areas.md"

# 実装の進み具合。エージェントが進める軸。
STATUSES = {
    "REQ": {"not-started", "in-progress", "done", "on-hold"},
    "ADR": {"proposed", "accepted", "superseded"},
    "MTG": {"draft", "confirmed"},
}

# 領域（area）が未確定（unassigned）のままでよい段階を、種別ごとに (フィールド, 値) で表す。
# 「まだ未確定でよい方」だけを挙げているので、ここに載っていない種別は既定で
# 「領域が必要」側に入る（fail closed）。判断ゲートを通ったあとの値を数え上げる書き方だと、
# 値を増やしたときに書き忘れて検査が素通りする。
AREA_PENDING = {
    "REQ": ("priority", {"undecided"}),   # 採否が決まるまでは未分類でよい
    "ADR": ("status", {"proposed"}),      # 論点のうちは未分類でよい
}

# 領域が必須になる種別。議事録は複数領域にまたがるイベントなので対象外。
AREA_REQUIRED = set(AREA_PENDING)

# 語彙に必ず存在すべきキー。common は「複数領域にまたがる」、unassigned は「まだ分からない」で
# 意味が異なり、docs-lint は 2 つを別々に扱う。だから areas.md 側の列にはできない。
RESERVED_AREAS = {"common", "unassigned"}
UNASSIGNED = "unassigned"

# 旧 3 層（RQ / BL）も認識する。移行した案件の議事録に旧 ID が残るため。
# 実在するかどうかは id-migration.md の対応表で解決する。
ID_PATTERN = re.compile(
    r"\b(RQ-\d{4}|REQ-\d{4}|BL-\d{4}|ADR-\d{4}|MTG-\d{4}-\d{2}-\d{2}(?:-[a-z])?)\b"
)

CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_noise(body: str) -> str:
    """コードブロック・HTML コメント・インラインコードを除去する。

    テンプレートの記入例やダイアグラムの例に書かれた ID を
    参照切れとして誤検出しないため。
    """
    for pattern in (CODE_BLOCK, HTML_COMMENT, INLINE_CODE):
        body = pattern.sub(" ", body)
    return body


errors: list[str] = []
warnings: list[str] = []


def collect() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for path in sorted(DOCS.rglob("*.md")):
        if "raw" in path.parts or path.name in {"index.md", "README.md"}:
            continue
        fm, body = parse_frontmatter(path)
        if not fm.get("id"):
            continue
        top = path.relative_to(DOCS).parts[0]
        index[fm["id"]] = {
            "path": path,
            "fm": fm,
            "body": body,
            "kind": KINDS.get(top),  # 憲章・用語集など採番対象外の文書は None
        }
    return index


def check_document(doc_id: str, entry: dict, index: dict, aliases: set) -> None:
    path, fm, body, kind = entry["path"], entry["fm"], entry["body"], entry["kind"]
    where = f"{path}"

    for field in ("id", "title", "status", "updated"):
        if not fm.get(field):
            errors.append(f"{where}: frontmatter に {field} がありません")

    # 憲章・用語集など、採番対象外の固定 ID 文書はファイル名一致を求めない
    if kind and path.stem != doc_id:
        errors.append(f"{where}: ファイル名と id ({doc_id}) が一致しません")

    status = fm.get("status")
    if status and kind and status not in STATUSES[kind]:
        errors.append(
            f"{where}: status '{status}' は不正です。使えるのは {sorted(STATUSES[kind])}"
        )

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm.get("updated", ""))):
        errors.append(f"{where}: updated は YYYY-MM-DD 形式で書いてください")

    # 参照切れ検査（frontmatter と本文の両方）
    referenced: set[str] = set()
    for key in ("source", "related", "depends_on", "supersedes"):
        referenced.update(as_list(fm.get(key)))
    referenced.update(ID_PATTERN.findall(strip_noise(body)))
    for ref in sorted(referenced):
        if ref != doc_id and ref not in index and ref not in aliases:
            errors.append(f"{where}: 参照先 {ref} が存在しません")

    for marker in re.findall(r"\[NEEDS-DECISION(?::\s*([^\]]*))?\]", body):
        target = (marker or "").strip()
        if not target:
            errors.append(
                f"{where}: [NEEDS-DECISION] は [NEEDS-DECISION: ADR-XXXX] の形式で"
                "論点の ID を書いてください"
            )
        elif target not in index and target not in aliases:
            errors.append(f"{where}: [NEEDS-DECISION: {target}] の参照先が存在しません")
        else:
            warnings.append(f"{where}: 未決事項 {target} が残っています")


def check_requirements(index: dict) -> None:
    """要件の 2 つの軸（採否 priority と実装 status）の整合を検査する。"""
    for entry in index.values():
        if entry["kind"] != "REQ":
            continue
        fm, path, body = entry["fm"], entry["path"], entry["body"]
        priority, status = fm.get("priority"), fm.get("status")

        if priority not in PRIORITIES:
            errors.append(
                f"{path}: priority '{priority}' は不正です。使えるのは {sorted(PRIORITIES)}"
            )
            continue

        # 判断済みなら理由が必須。理由のない判断は必ず蒸し返される。
        if priority in REQUIRES_REASON:
            if not fm.get("decision"):
                errors.append(f"{path}: priority が {priority} ですが decision（理由）が空です")
            if not fm.get("decided_at"):
                errors.append(f"{path}: priority が {priority} ですが decided_at が空です")

        # 合意していないものを実装している状態を検出する。
        if status in {"in-progress", "done"} and priority not in AGREED:
            errors.append(
                f"{path}: status が {status} ですが priority が {priority} です。"
                "採否が決まっていないもの・やらないと決めたものを実装しないでください"
            )

        # 「やると決めるなら、何をもって完了とするかも決める」の強制。
        # 旧モデルで ready 昇格の条件として人間が確認していたものを機械化した。
        criteria = CHECKBOX.findall(section_body(body, "受入基準"))
        if not criteria:
            if priority == "must":
                errors.append(
                    f"{path}: priority が must ですが受入基準がありません。"
                    "検証可能な形で「## 受入基準」に書いてください"
                )
            elif priority == "future":
                warnings.append(
                    f"{path}: priority が future ですが受入基準がありません。"
                    "着手する前までに確定させてください"
                )

        # 実装 PR が自分で status: done を書くため、完了の申告を機械的に検証する。
        if status == "done":
            unchecked = criteria.count(" ")
            if unchecked:
                errors.append(
                    f"{path}: status が done ですが、受入基準に未達の項目が {unchecked} 件残っています。"
                    "満たしたなら [x] にし、満たしていないなら status を in-progress にしてください"
                )


def check_areas(index: dict, areas: dict) -> None:
    """領域（area）に関する検査をまとめて行う。

    1 文書ごとの検査もここに置く。語彙が読めなければ全部が同じ理由で落ちるので、
    「areas が空かどうか」を各所で判定せず、この入口 1 か所で分岐させる。
    """
    if not areas:
        errors.append(
            f"{AREAS_FILE} に領域が定義されていません。"
            "「領域一覧」の表に少なくとも common と unassigned を書いてください"
        )
        return

    for key in sorted(RESERVED_AREAS - set(areas)):
        errors.append(f"{AREAS_FILE}: 予約キー '{key}' の行がありません。削除しないでください")

    project_areas = {k: v for k, v in areas.items() if k not in RESERVED_AREAS}
    if not project_areas:
        warnings.append(
            f"{AREAS_FILE}: 予約キー（{', '.join(sorted(RESERVED_AREAS))}）しか定義されていません。"
            "初回の /meeting-intake または /requirements-intake が、"
            "起票の材料から領域を提案します"
        )

    for entry in index.values():
        if entry["kind"] in AREA_REQUIRED:
            check_document_area(entry, areas)

    used = {entry["fm"].get("area") for entry in index.values()}
    for key, meta in project_areas.items():
        if meta["state"] != "retired" and key not in used:
            warnings.append(f"{AREAS_FILE}: 領域 '{key}' はどの文書からも使われていません")


def area_may_be_pending(entry: dict) -> bool:
    """領域が未確定（unassigned）のままでよい段階かどうかを AREA_PENDING から引く。"""
    field, values = AREA_PENDING.get(entry["kind"], (None, set()))
    return field is not None and entry["fm"].get(field) in values


def check_document_area(entry: dict, areas: dict) -> None:
    """1 文書の area が定義済みの語彙で、判断ゲートまでに確定しているかを見る。"""
    fm, where = entry["fm"], entry["path"]
    area = fm.get("area")

    if not area:
        errors.append(
            f"{where}: frontmatter に area がありません。"
            f"{AREAS_FILE} のキーから 1 つ選んでください（決まっていなければ {UNASSIGNED}）"
        )
        return
    if area not in areas:
        errors.append(
            f"{where}: area '{area}' は {AREAS_FILE} に定義されていません。"
            f"使えるのは {sorted(areas)}"
        )
        return

    if areas[area]["state"] == "retired":
        warnings.append(f"{where}: area '{area}' は廃止済み（retired）です")

    if area == UNASSIGNED:
        if area_may_be_pending(entry):
            warnings.append(f"{where}: area が未分類（{UNASSIGNED}）のままです")
        else:
            errors.append(
                f"{where}: 判断済みですが area が {UNASSIGNED} です。"
                "判断ゲートを通る前に領域を確定させてください"
            )


def check_meetings(index: dict) -> None:
    raw_dir = DOCS / "03-meetings" / "raw"
    if not raw_dir.exists():
        return
    for raw in sorted(raw_dir.iterdir()):
        if raw.name.startswith(".") or not raw.is_file():
            continue
        match = re.search(r"(\d{4}-\d{2}-\d{2})", raw.name)
        if not match:
            continue
        prefix = f"MTG-{match.group(1)}"
        if not any(mid.startswith(prefix) for mid in index):
            warnings.append(
                f"{raw}: 文字起こしはありますが、対応する議事録がまだ作られていません"
                "（/meeting-intake を実行してください）"
            )


def main() -> int:
    if not DOCS.exists():
        print("docs/ が見つかりません。リポジトリのルートで実行してください。", file=sys.stderr)
        return 1

    index = collect()
    aliases = load_id_aliases()
    for doc_id, entry in index.items():
        check_document(doc_id, entry, index, aliases)
    check_requirements(index)
    check_areas(index, load_areas())
    check_meetings(index)

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)

    print(f"\n{len(index)} 件の文書を検査しました。エラー {len(errors)} 件 / 警告 {len(warnings)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
