"""カットラインのパス計算.

illustrator-vm の ExtendScript（`lib/path_smooth.jsx`、`acrylic_keychain_new.jsx`、
`acrylic_stand.jsx`）の計算を移したもの。**計算は Illustrator と同じ y 上向きの座標で行う。**
VectorCraft は y 下向き・アートボード左上原点なので、境界（``from_vc_anchors`` / ``to_vc_anchors``）
でだけ y を反転する。

アンカーは (A, LD, RD) = (アンカー, leftDirection, rightDirection) の 3 つ組で持つ。
VectorCraft の in / out がそれぞれ leftDirection / rightDirection に当たる。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from app.generator.errors import GenerationError

logger = logging.getLogger(__name__)

Pt = tuple[float, float]
# [left, top, right, bottom]（Illustrator の geometricBounds と同じ並び）
Bounds = tuple[float, float, float, float]


@dataclass
class SubPath:
    """1 本の連続したパス."""

    A: list[Pt]
    LD: list[Pt]
    RD: list[Pt]
    closed: bool = True

    def __len__(self) -> int:
        return len(self.A)


@dataclass(frozen=True)
class KeyholeCircle:
    """キー穴テンプレートの内円（本体の穴に置く）と、同心の外円の直径."""

    points: SubPath
    center_x: float
    center_y: float
    outer_diameter_pt: float


@dataclass(frozen=True)
class BaseEdge:
    """アクリルスタンドの土台の下辺（水平なセグメント）."""

    y: float
    left: float
    right: float


# --- VectorCraft の JSON <-> 上向き座標 -----------------------------------------


def from_vc_anchors(anchors: list[dict[str, Any]], closed: bool) -> SubPath:
    a_pts: list[Pt] = []
    l_pts: list[Pt] = []
    r_pts: list[Pt] = []
    for a in anchors:
        p = a["p"]
        i = a.get("in") or p
        o = a.get("out") or p
        a_pts.append((p[0], -p[1]))
        l_pts.append((i[0], -i[1]))
        r_pts.append((o[0], -o[1]))
    return SubPath(a_pts, l_pts, r_pts, closed)


def to_vc_anchors(sp: SubPath) -> list[dict[str, Any]]:
    return [
        {"x": a[0], "y": -a[1], "in": [left[0], -left[1]], "out": [right[0], -right[1]]}
        for a, left, right in zip(sp.A, sp.LD, sp.RD, strict=True)
    ]


def subpaths_of_node(node: dict[str, Any]) -> list[SubPath]:
    """``document.node`` の結果（パス・複合パス）からサブパスを取り出す."""
    k = node["kind"]
    if k.get("type") == "path":
        return [
            from_vc_anchors(s["anchors"], s.get("closed", True)) for s in k["path"]["subpaths"]
        ]
    if k.get("type") == "compound":
        out: list[SubPath] = []
        for ch in k["children"]:
            out.extend(subpaths_of_node(ch))
        return out
    raise GenerationError(f"not a path: {k.get('type')}")


# --- 外形 -----------------------------------------------------------------------


def _cubic_extrema(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """1 次元の 3 次ベジェが極値をとるパラメータ."""
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    ts: list[float] = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            ts.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            s = math.sqrt(disc)
            ts += [(-b + s) / (2 * a), (-b - s) / (2 * a)]
    return [t for t in ts if 0 < t < 1]


def _cubic_at(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1 - t
    return mt**3 * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t**3 * p3


def _segments(sp: SubPath) -> list[tuple[int, int]]:
    n = len(sp.A)
    count = n if sp.closed else n - 1
    return [(i, (i + 1) % n) for i in range(count)]


def bounds(sps: list[SubPath]) -> Bounds:
    """曲線の実際の外形（Illustrator の geometricBounds と同じ）."""
    xs: list[float] = []
    ys: list[float] = []
    for sp in sps:
        xs.extend(a[0] for a in sp.A)
        ys.extend(a[1] for a in sp.A)
        for i, j in _segments(sp):
            p0, p1, p2, p3 = sp.A[i], sp.RD[i], sp.LD[j], sp.A[j]
            for d, arr in ((0, xs), (1, ys)):
                for t in _cubic_extrema(p0[d], p1[d], p2[d], p3[d]):
                    arr.append(_cubic_at(p0[d], p1[d], p2[d], p3[d], t))
    return (min(xs), max(ys), max(xs), min(ys))


def union_bounds(bs: list[Bounds]) -> Bounds:
    return (
        min(b[0] for b in bs),
        max(b[1] for b in bs),
        max(b[2] for b in bs),
        min(b[3] for b in bs),
    )


def is_small(sp: SubPath) -> bool:
    """50pt 四方に収まるパス（キー穴など）."""
    b = bounds([sp])
    return (b[2] - b[0]) < 50 and (b[1] - b[3]) < 50


def _translate(sp: SubPath, dx: float, dy: float) -> SubPath:
    def move(p: Pt) -> Pt:
        return (p[0] + dx, p[1] + dy)

    return SubPath(
        [move(p) for p in sp.A], [move(p) for p in sp.LD], [move(p) for p in sp.RD], sp.closed
    )


# --- lib/path_smooth.jsx: smoothCutlinePath -------------------------------------


def smooth_cutline_path(
    sp: SubPath,
    min_spacing: float,
    *,
    preserve_bottom_edge: bool = False,
    preserve_above_y: float | None = None,
) -> SubPath:
    """アンカーを間引き、残したアンカーに Catmull-Rom 風の方向線を付ける."""
    a_pts = sp.A
    orig_n = len(a_pts)
    if orig_n < 10:
        return sp
    bottom_tol = 1.0
    bottom_y = min(a[1] for a in a_pts) if preserve_bottom_edge else None

    def pinned(p: Pt) -> bool:
        if preserve_above_y is not None and p[1] >= preserve_above_y:
            return True
        return bottom_y is not None and abs(p[1] - bottom_y) < bottom_tol

    keep = [False] * orig_n
    keep[0] = True
    last = 0
    for k in range(1, orig_n):
        if pinned(a_pts[k]) or math.dist(a_pts[k], a_pts[last]) >= min_spacing:
            keep[k] = True
            last = k
    keep_count = sum(keep)
    if keep_count < 8 or keep_count >= orig_n - 2:
        return sp

    idx = [i for i in range(orig_n) if keep[i]]
    out = SubPath([a_pts[i] for i in idx], [sp.LD[i] for i in idx], [sp.RD[i] for i in idx], sp.closed)
    m = len(out.A)
    for si in range(m):
        a = out.A[si]
        if pinned(a):
            continue
        prev = out.A[(si - 1) % m]
        nxt = out.A[(si + 1) % m]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        ln = math.hypot(dx, dy)
        if ln < 0.001:
            continue
        dx, dy = dx / ln, dy / ln
        dp = math.dist(a, prev)
        dn = math.dist(nxt, a)
        out.LD[si] = (a[0] - dx * dp / 3, a[1] - dy * dp / 3)
        out.RD[si] = (a[0] + dx * dn / 3, a[1] + dy * dn / 3)
    return out


# --- acrylic_keychain_new.jsx: キー穴 -------------------------------------------

# テンプレートの内円（直径 ≈5.03pt = 1.78mm）と外円（≈17.36pt = 6.12mm）
_INNER_DIA, _INNER_TOL = 5.03, 2.5
_OUTER_DIA, _OUTER_TOL = 17.36, 5.0
_PAIR_TOL = 8.0


def find_keyhole_pair(paths: list[SubPath]) -> KeyholeCircle | None:
    """テンプレートから、内円と同心の外円の組を探す（loadInnerCirclePoints）."""
    if len(paths) < 2:
        return None
    cx: list[float] = []
    cy: list[float] = []
    dia: list[float] = []
    for p in paths:
        b = bounds([p])
        cx.append((b[0] + b[2]) / 2)
        cy.append((b[1] + b[3]) / 2)
        dia.append(((b[2] - b[0]) + (b[1] - b[3])) / 2)
    best: tuple[float, int, int] | None = None
    for oi, od in enumerate(dia):
        if abs(od - _OUTER_DIA) > _OUTER_TOL:
            continue
        for ii, idia in enumerate(dia):
            if ii == oi or abs(idia - _INNER_DIA) > _INNER_TOL:
                continue
            cd = math.hypot(cx[ii] - cx[oi], cy[ii] - cy[oi])
            if cd > _PAIR_TOL:
                continue
            err = abs(od - _OUTER_DIA) + abs(idia - _INNER_DIA) + cd
            if best is None or err < best[0]:
                best = (err, ii, oi)
    if best is None:
        return None
    _, inner, outer = best
    return KeyholeCircle(paths[inner], cx[inner], cy[inner], dia[outer])


def replace_keyhole(paths: list[SubPath], circle: KeyholeCircle | None) -> list[SubPath]:
    """トレースしたキー穴（最初の小さなパス）を、テンプレートの内円に置き換える."""
    if circle is None:
        return paths
    for i, p in enumerate(paths):
        if is_small(p):
            b = bounds([p])
            hx, hy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            hole = _translate(circle.points, hx - circle.center_x, hy - circle.center_y)
            return [hole, *paths[:i], *paths[i + 1 :]]
    logger.info("replace_keyhole: no keyhole path found")
    return paths


def _circle_cross(pout: Pt, pin: Pt, cx: float, cy: float, r: float) -> Pt:
    dx, dy = pin[0] - pout[0], pin[1] - pout[1]
    fx, fy = pout[0] - cx, pout[1] - cy
    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = max(b * b - 4 * a * c, 0)
    t = min(max((-b - math.sqrt(disc)) / (2 * a), 0), 1)
    return (pout[0] + t * dx, pout[1] + t * dy)


def _arc_over_top(cx: float, cy: float, r: float, start: Pt, end: Pt, nseg: int) -> list[Pt]:
    a_s = math.atan2(start[1] - cy, start[0] - cx)
    a_e = math.atan2(end[1] - cy, end[0] - cx)
    if start[0] > cx:
        while a_e <= a_s:
            a_e += 2 * math.pi
    else:
        while a_e >= a_s:
            a_e -= 2 * math.pi
    return [
        (cx + r * math.cos(a_s + (a_e - a_s) * i / nseg), cy + r * math.sin(a_s + (a_e - a_s) * i / nseg))
        for i in range(nseg + 1)
    ]


def enlarge_keyhole_tab(paths: list[SubPath], outer_dia: float) -> list[SubPath]:
    """本体のキー穴まわりの外周を、テンプレートの外円まで広げる（enlargeKeyholeTab）."""
    if outer_dia <= 0:
        return paths
    r = outer_dia / 2
    center: Pt | None = None
    best = math.inf
    for p in paths:
        if not is_small(p):
            continue
        b = bounds([p])
        err = abs(((b[2] - b[0]) + (b[1] - b[3])) / 2 - 5.035)
        if err < best:
            best, center = err, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    if center is None:
        logger.info("enlarge_keyhole_tab: keyhole center not found")
        return paths
    cx, cy = center

    def area(p: SubPath) -> float:
        b = bounds([p])
        return (b[2] - b[0]) * (b[1] - b[3])

    body_idx = max(range(len(paths)), key=lambda i: area(paths[i]))
    body = paths[body_idx]
    n = len(body)
    if n < 8:
        return paths
    ob = bounds([body])
    orig_w, orig_h = ob[2] - ob[0], ob[1] - ob[3]
    dist = [math.hypot(a[0] - cx, a[1] - cy) for a in body.A]
    min_idx = min(range(n), key=lambda i: dist[i])
    if dist[min_idx] >= r:
        return paths
    s = min_idx
    while dist[(s - 1) % n] < r and (s - 1) % n != min_idx:
        s = (s - 1) % n
    e = min_idx
    while dist[(e + 1) % n] < r and (e + 1) % n != min_idx:
        e = (e + 1) % n
    run = (e - s) % n + 1
    if run > n - 3:
        return paths
    entry = _circle_cross(body.A[(s - 1) % n], body.A[s], cx, cy, r)
    exit_ = _circle_cross(body.A[(e + 1) % n], body.A[e], cx, cy, r)
    arc = _arc_over_top(cx, cy, r, entry, exit_, 64)
    new = SubPath([], [], [], True)
    i = (e + 1) % n
    while i != s:
        new.A.append(body.A[i])
        new.LD.append(body.LD[i])
        new.RD.append(body.RD[i])
        i = (i + 1) % n
    for pt in arc:
        new.A.append(pt)
        new.LD.append(pt)
        new.RD.append(pt)
    nb = bounds([new])
    if (nb[2] - nb[0]) < orig_w * 0.7 or (nb[1] - nb[3]) < orig_h * 0.7:
        logger.info("enlarge_keyhole_tab: new body is too small; keeping the original")
        return paths
    return [new, *paths[:body_idx], *paths[body_idx + 1 :]]


# --- acrylic_stand.jsx: 土台の延長（ADR-0038） ----------------------------------

_FLAT_TOL = 0.5
# 土台とみなす水平な辺の最短の長さ。VectorCraft のトレースは、丸い輪郭の上にも 1.1〜1.3mm 程度の
# 水平な直線を作ることがある（土台の無い円形の入力で実測）。Illustrator のトレースはこれを作らないので、
# illustrator-vm は長さを問わずに済んでいた。販売サイトの土台は 4.5mm 以上だった（検証した入力で 4.5〜12.6mm）。
MIN_BASE_LENGTH_PT = 3 * 72 / 25.4


def find_base_edge(sp: SubPath, search_band_pt: float) -> BaseEdge | None:
    """最下点から ``search_band_pt`` 以内にある水平なセグメントのうち、最も長いもの（findBaseEdge）.

    水平とは、両端のアンカーと、その間の方向線が同じ高さに並ぶこと（直線の辺）。
    ``MIN_BASE_LENGTH_PT`` より短いものは土台とみなさない。
    """
    lowest = bounds([sp])[3]
    best: BaseEdge | None = None
    for i, j in _segments(sp):
        a, b = sp.A[i], sp.A[j]
        y = (a[1] + b[1]) / 2
        if y - lowest > search_band_pt:
            continue
        if (
            abs(a[1] - b[1]) >= _FLAT_TOL
            or abs(sp.RD[i][1] - a[1]) >= _FLAT_TOL
            or abs(sp.LD[j][1] - b[1]) >= _FLAT_TOL
        ):
            continue
        left, right = min(a[0], b[0]), max(a[0], b[0])
        if right - left < MIN_BASE_LENGTH_PT:
            continue
        if best is None or right - left > best.right - best.left:
            best = BaseEdge(y, left, right)
    return best


def base_extension_rect(sp: SubPath, search_band_pt: float) -> Bounds | None:
    """土台を最下点まで延ばすための長方形（[left, top, right, bottom]）。延ばす必要が無ければ None.

    土台の下辺より下にはみ出している範囲（曲線上も含む）の左右端までを埋める。
    上端は本体と確実に重なるよう、土台の中へ 1pt 食い込ませる。

    Raises:
        GenerationError: 土台（水平な辺）が見つからない。ADR-0038 により生成を失敗させる。
    """
    lowest = bounds([sp])[3]
    base = find_base_edge(sp, search_band_pt)
    if base is None:
        raise GenerationError(
            "acrylic_stand: flat base edge not found within "
            f"{search_band_pt * 25.4 / 72:.1f}mm of the lowest point"
        )
    if base.y - lowest <= _FLAT_TOL:
        return None
    left, right = base.left, base.right
    for i, j in _segments(sp):
        p0, p1, p2, p3 = sp.A[i], sp.RD[i], sp.LD[j], sp.A[j]
        for k in range(17):
            t = k / 16
            x = _cubic_at(p0[0], p1[0], p2[0], p3[0], t)
            y = _cubic_at(p0[1], p1[1], p2[1], p3[1], t)
            if y < base.y - _FLAT_TOL:
                left, right = min(left, x), max(right, x)
    return (left, base.y + 1, right, lowest)


def bottom_anchor_count(sp: SubPath) -> int:
    """最下点の高さにあるアンカーの数（タブ合成の前提は 2 以上）."""
    lowest = min(a[1] for a in sp.A)
    return sum(1 for a in sp.A if abs(a[1] - lowest) < _FLAT_TOL)


# --- acrylic_stand.jsx: 台座タブ ------------------------------------------------


def find_joint_y(anchors: list[Pt], tol: float) -> float:
    """アンカーが最も多く並ぶ高さ（同数なら高いほう）。タブの肩ライン."""
    levels: list[list[float]] = []  # [y, count]
    for a in anchors:
        for lv in levels:
            if abs(lv[0] - a[1]) < tol:
                lv[1] += 1
                break
        else:
            levels.append([a[1], 1])
    best = levels[0]
    for lv in levels[1:]:
        if lv[1] > best[1] or (lv[1] == best[1] and lv[0] > best[0]):
            best = lv
    return best[0]


def merge_pedestal_tab(main: SubPath, tab: SubPath) -> SubPath:
    """本体カットラインの底辺を、テンプレートの差し込みタブ（ノッチ）で置き換える.

    タブはテンプレートの形と大きさのまま平行移動するだけで、変形しない（ADR-0038 の必須条件）。

    最下点の高さには、土台のほかに床に着いた脚などの辺が離れてあることがある（#154）。
    底の高さに続けて並ぶアンカーの列のうち、タブの中心（本体の中心）の下にあるものを土台とし、
    その列だけをノッチで置き換える。ほかの列は本体の輪郭としてそのまま残す。

    Raises:
        GenerationError: 底辺に平らな辺が無い・タブが土台に収まらない・テンプレートにノッチが無い、
            または合成の結果、本体の外形が変わった。
    """
    tab_a, tab_l, tab_r = tab.A, tab.LD, tab.RD
    n = len(tab_a)
    tb = bounds([tab])
    tab_top_y = find_joint_y(tab_a, 0.5)
    mb = bounds([main])
    cut_bottom = mb[3]
    cx = (mb[0] + mb[2]) / 2
    dx = cx - (tb[0] + tb[2]) / 2
    dy = cut_bottom - tab_top_y
    c_a, c_l, c_r = main.A, main.LD, main.RD
    cn = len(c_a)
    tol = _FLAT_TOL

    n_bottom = sum(1 for a in c_a if abs(a[1] - cut_bottom) < tol)
    if n_bottom < 2:
        raise GenerationError(
            f"acrylic_stand: need >=2 bottom points to merge the tab, found {n_bottom}"
        )
    # 土台の列 run（順にたどった並び）の両端。s から e へたどると土台の上を通る
    run = _bottom_run_under(c_a, cut_bottom, tol, cx)
    s, e = run[0], run[-1]
    # 右下から左下へたどる向きか
    fwd = c_a[s][0] > c_a[e][0]
    base_left, base_right = sorted((c_a[s][0], c_a[e][0]))

    top_idx = [i for i in range(n) if abs(tab_a[i][1] - tab_top_y) < 0.5]
    segs: list[list[int]] = []
    for k, start in enumerate(top_idx):
        end = top_idx[(k + 1) % len(top_idx)]
        seg: list[int] = []
        i = start
        for sw in range(n + 1):
            seg.append(i)
            if i == end and sw > 0:
                break
            i = (i + 1) % n
        if len(seg) > 2 and any(tab_a[j][1] < tab_top_y - 0.5 for j in seg):
            segs.append(seg)
    if not segs:
        raise GenerationError("acrylic_stand: no notch segments found in the tab template")
    l2r = tab_a[segs[0][-1]][0] >= tab_a[segs[0][0]][0]
    if len(segs) > 1:
        segs.sort(key=lambda s: tab_a[s[0]][0], reverse=not l2r)
    notch = [j for seg in segs for j in seg]
    rev = l2r == fwd
    pts = list(reversed(notch)) if rev else notch
    notch_xs = [tab_a[j][0] + dx for j in notch]
    if min(notch_xs) < base_left - tol or max(notch_xs) > base_right + tol:
        raise GenerationError(
            "acrylic_stand: the tab does not fit on the base "
            f"(tab {min(notch_xs):.1f}..{max(notch_xs):.1f}pt, base {base_left:.1f}..{base_right:.1f}pt)"
        )

    # 土台の列の外側（e の次から s まで）が本体の輪郭。土台の途中のアンカーは捨てる
    out = SubPath([], [], [], True)
    w = (e + 1) % cn
    for _ in range(cn):
        out.A.append(c_a[w])
        out.LD.append(c_l[w])
        out.RD.append(c_r[w])
        if w == s:
            break
        w = (w + 1) % cn
    last_body = len(out.A) - 1
    out.RD[last_body] = out.A[last_body]
    for j in pts:
        ld, rd = (tab_r[j], tab_l[j]) if rev else (tab_l[j], tab_r[j])
        out.A.append((tab_a[j][0] + dx, tab_a[j][1] + dy))
        out.LD.append((ld[0] + dx, ld[1] + dy))
        out.RD.append((rd[0] + dx, rd[1] + dy))
    out.LD[last_body + 1] = out.A[last_body + 1]
    out.RD[-1] = out.A[-1]
    out.A.append(c_a[e])
    out.LD.append(c_a[e])
    out.RD.append(c_r[e])

    # 合成で本体の外形が変わっていないこと（下へタブの深さだけ伸びるのは正しい）。
    # 壊れたカットラインを成功として納入しない（#154 は生成が成功扱いで製造委託先に届いた）
    ob = bounds([out])
    if any(abs(ob[k] - mb[k]) > tol for k in range(3)):
        raise GenerationError("acrylic_stand: merging the tab changed the outline of the body")
    return out


def _bottom_run_under(anchors: list[Pt], bottom_y: float, tol: float, x: float) -> list[int]:
    """高さ ``bottom_y`` に続けて並ぶアンカーの列（順にたどった添字）のうち、``x`` の真下にあるもの.

    Raises:
        GenerationError: ``x`` の下に、底の高さの辺が無い。
    """
    cn = len(anchors)
    on_bottom = [abs(a[1] - bottom_y) < tol for a in anchors]
    # 底でないアンカーから数え始めれば、0 番をまたぐ列も切れずに取れる
    start = next((i for i in range(cn) if not on_bottom[i]), None)
    if start is not None:
        run: list[int] = []
        for k in range(1, cn + 1):
            i = (start + k) % cn
            if on_bottom[i]:
                run.append(i)
                continue
            xs = [anchors[j][0] for j in run]
            if len(run) >= 2 and min(xs) <= x <= max(xs):
                return run
            run = []
    raise GenerationError("acrylic_stand: the tab does not fit on the base (no flat bottom under its center)")
