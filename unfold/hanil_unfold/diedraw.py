"""금형 도면집: 표지 (사양·점검·도면 목록) · 조립도 (평면도 + 정면도, 풍선, 부품표) · 스트립 배치도 ·
부품도 (판·펀치·가이드·블록마다 평면도 + 정면도, 치수, 구멍 좌표표, 가공 주기) — 모두 표제란이 있는 A3 도면.

한 번 그린 도면 (Sheet: 종이 mm 좌표의 선·원·다각형·글) 을 DXF (시트를 옆으로 늘어놓음, 레이어·선 종류) 와
PDF (쪽마다 한 장) 로 똑같이 낸다. 투상은 3각법 (평면도 위, 정면도 아래). 척도는 KS/ISO 권장 척도에서 맞는 것.
가공 좌표는 판 왼쪽 아래 귀가 원점 (구멍표 X·Y), 실치수 가공 데이터는 die3d.save_dxf (1:1) 를 같이 쓴다.
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

import numpy as np

from . import die3d as d3

A3 = (420.0, 297.0)
MARGIN = 10.0
SCALES = [(1, 1), (1, 2), (1, 2.5), (1, 5), (1, 10), (1, 20)]
TB_W, TB_H = 180.0, 52.0          # 표제란
LAYERS = {"OUTLINE": 7, "HIDDEN": 8, "CENTER": 1, "DIM": 3, "TEXT": 7, "FRAME": 7, "THIN": 9, "WIRE": 1, "HATCH": 8,
          "PART": 6, "PART2": 6}
LTYPE = {"HIDDEN": "DASHED", "CENTER": "CENTER", "PART2": "PHANTOM"}   # PART 금형 안 제품 (공정 전), PART2 공정 뒤 (하사점)


def _work(sh, assy, T, which=("before", "after"), proj=None):
    """금형 안 제품 선 (절곡 금형): 공정 전 = PART 굵은 선, 공정 뒤 (하사점) = PART2 가상선. proj: 3D → 2D."""
    for P, tag in getattr(assy, "work", None) or []:
        if tag not in which:
            continue
        Q = [proj(q) for q in P] if proj else [(q[0], q[1]) for q in P]
        sh.poly([T(*q) for q in Q], False, "PART" if tag == "before" else "PART2", 0.5 if tag == "before" else 0.3)


@dataclass
class Sheet:
    """도면 한 장 (종이 mm, 원점 왼쪽 아래)."""
    title: str
    number: str = ""
    size: tuple = A3
    ents: list = field(default_factory=list)
    scale: str = "1:1"
    material: str = ""
    heat: str = ""
    qty: int = 1
    weight: float = 0.0

    def line(self, x1, y1, x2, y2, layer="OUTLINE", w=0.35):
        self.ents.append(("line", float(x1), float(y1), float(x2), float(y2), layer, w))

    def poly(self, pts, closed=True, layer="OUTLINE", w=0.35):
        P = [(float(x), float(y)) for x, y in pts]
        if len(P) >= 2:
            self.ents.append(("poly", P, closed, layer, w))

    def rect(self, x, y, wd, ht, layer="OUTLINE", w=0.35):
        self.poly([(x, y), (x + wd, y), (x + wd, y + ht), (x, y + ht)], True, layer, w)

    def circle(self, x, y, r, layer="OUTLINE", w=0.35):
        if r > 0:
            self.ents.append(("circle", float(x), float(y), float(r), layer, w))

    def text(self, x, y, s, h=2.5, align="L", layer="TEXT", bold=False):
        self.ents.append(("text", float(x), float(y), str(s), float(h), align, layer, bold))

    def center_mark(self, x, y, r):
        e = max(r + 1.5, 2.0)
        self.line(x - e, y, x + e, y, "CENTER", 0.18)
        self.line(x, y - e, x, y + e, "CENTER", 0.18)

    def arrow(self, x, y, ang, s=2.2):
        for da in (math.radians(17), -math.radians(17)):
            self.line(x, y, x + s * math.cos(ang + da), y + s * math.sin(ang + da), "DIM", 0.18)

    def dim_h(self, x1, x2, y_ref, y_dim, txt, h=2.5):
        """가로 치수: 기준점 y_ref 에서 y_dim 까지 치수 보조선, 화살표, 글."""
        for x in (x1, x2):
            self.line(x, y_ref, x, y_dim + (1.5 if y_dim > y_ref else -1.5), "DIM", 0.18)
        self.line(x1, y_dim, x2, y_dim, "DIM", 0.18)
        self.arrow(x1, y_dim, 0.0)
        self.arrow(x2, y_dim, math.pi)
        self.text((x1 + x2) / 2, y_dim + 0.8, txt, h, "C", "DIM")

    def dim_v(self, y1, y2, x_ref, x_dim, txt, h=2.5):
        for y in (y1, y2):
            self.line(x_ref, y, x_dim + (1.5 if x_dim > x_ref else -1.5), y, "DIM", 0.18)
        self.line(x_dim, y1, x_dim, y2, "DIM", 0.18)
        self.arrow(x_dim, y1, math.pi / 2)
        self.arrow(x_dim, y2, -math.pi / 2)
        self.text(x_dim - 0.8, (y1 + y2) / 2, txt, h, "VR", "DIM")


# ---------------------------------------------------------------- 틀 · 표제란

def _frame(sh: Sheet, info, idx, total):
    W, H = sh.size
    sh.rect(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN, "FRAME", 0.7)
    sh.rect(0, 0, W, H, "THIN", 0.18)
    # 가운데 표시 (중심 마크)
    for x, y, dx, dy in ((W / 2, 0, 0, MARGIN), (W / 2, H - MARGIN, 0, MARGIN), (0, H / 2, MARGIN, 0),
                         (W - MARGIN, H / 2, MARGIN, 0)):
        sh.line(x, y, x + dx, y + dy, "FRAME", 0.5)
    x0, y0 = W - MARGIN - TB_W, MARGIN
    sh.rect(x0, y0, TB_W, TB_H, "FRAME", 0.7)
    rows = [10.0, 8.0, 8.0, 8.0, 8.0, 10.0]          # 아래부터
    ys = [y0]
    for r in rows:
        ys.append(ys[-1] + r)
    for y in ys[1:-1]:
        sh.line(x0, y, x0 + TB_W, y, "FRAME", 0.35)
    c1, c2, c3 = x0 + 30, x0 + 105, x0 + 135
    for x in (c1, c2, c3):
        sh.line(x, y0, x, ys[-2], "FRAME", 0.35)
    # 맨 위 줄: 회사 · 도면 이름
    sh.line(c1, ys[-2], c1, ys[-1], "FRAME", 0.35)
    from .company import NAME
    sh.text(x0 + 2, ys[-2] + 3.2, NAME, 3.2, "L", bold=True)
    sh.text(c1 + 2, ys[-2] + 3.0, sh.title, 4.0, "L", bold=True)
    today = info.get("date") or _dt.date.today().isoformat()
    cells = [  # (줄, 칸 이름, 값 칸)
        (0, "도번", sh.number, "시트", f"{idx} / {total}"),
        (1, "금형", info.get("die", ""), "척도", sh.scale),
        (2, "재질", sh.material, "수량", f"{sh.qty}"),
        (3, "열처리", sh.heat, "무게", f"{sh.weight:.2f} kg" if sh.weight else "-"),
        (4, "부품", info.get("product", ""), "날짜", today),
    ]
    for r, k1, v1, k2, v2 in cells:
        y = ys[r] + 2.6
        sh.text(x0 + 2, y, k1, 2.5)
        sh.text(c1 + 2, y, v1, 2.8)
        sh.text(c2 + 2, y, k2, 2.5)
        sh.text(c3 + 2, y, v2, 2.8)
    # 설계·검도·승인 칸 (표제란 왼쪽)
    bx = x0 - 60
    sh.rect(bx, y0, 60, 24, "FRAME", 0.5)
    for i, k in enumerate(("설계", "검도", "승인")):
        sh.line(bx + 20 * i, y0, bx + 20 * i, y0 + 24, "FRAME", 0.35)
        sh.text(bx + 20 * i + 10, y0 + 19, k, 2.5, "C")
    sh.line(bx, y0 + 16, bx + 60, y0 + 16, "FRAME", 0.35)
    sh.text(bx + 10, y0 + 6, info.get("designer", ""), 2.5, "C")
    # 3각법 기호 · 단위 (설계 칸 위)
    sx, sy = bx + 2, y0 + 26
    sh.text(sx, sy + 15, "3각법 · 단위 mm", 2.2)
    sh.poly([(sx, sy + 4), (sx + 10, sy + 2), (sx + 10, sy + 10), (sx, sy + 8)], True, "OUTLINE", 0.25)
    sh.circle(sx + 18, sy + 6, 4, "OUTLINE", 0.25)
    sh.circle(sx + 18, sy + 6, 2, "OUTLINE", 0.25)
    return (x0, y0, TB_W, TB_H)


def _num(v, nd=3):
    """치수 글: 소수 nd 자리까지, 끝 0 지움."""
    t = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return t if t not in ("-0", "") else "0"


def _pick_scale(wd_mm, ht_mm, box_w, box_h):
    for a, b in SCALES:
        s = a / b
        if wd_mm * s <= box_w and ht_mm * s <= box_h:
            return s, (f"{a}:{b:g}" if b != 1 else "1:1")
    a, b = SCALES[-1]
    return a / b, f"{a}:{b:g}"


# ---------------------------------------------------------------- 부품도

def _part_extent(pr: d3.Prim):
    x0, y0, z0, dx, dy, dz = d3.extent(pr)
    return x0, y0, dx, dy, z0, dz


NOTES_BASE = ["일반 공차 ISO 2768-m (지시 없는 치수)", "모서리 C0.5 (날 끝은 날카롭게)",
              "탭 JIS B 0205 (보통 나사), 리머 구멍 H7", "구멍 좌표는 원점 (왼쪽 아래 귀, ⊕) 에서"]


def part_sheet(part: d3.DiePart, assy: d3.DieAssy, info, number, iso=True):
    pr = part.prims[0]
    lines3d = _part_lines(pr) if iso else []
    x0, y0, dx, dy, z0, dz = _part_extent(pr)
    sh = Sheet(f"{part.name}", number, A3, material=part.material.split(" HRC")[0].split(" (")[0],
               heat=_heat(part.material), qty=part.qty, weight=part.weight)
    W, H = sh.size
    # 그림 자리: 왼쪽 (표제란 위), 오른쪽 구멍표
    area_x, area_y = MARGIN + 12, MARGIN + TB_H + 16
    area_w, area_h = W * 0.58, H - area_y - MARGIN - 14
    s, sh.scale = _pick_scale(dx + dy + 40, dy + dz + 40, area_w, area_h - 24)   # 정면도 옆에 우측면도 (사이 띄움)
    # 평면도 (위) · 정면도 (아래, 3각법)
    fx = area_x + 10
    fy_front = area_y + 6
    fy_top = fy_front + dz * s + 28

    def T(x, y):
        return fx + (x - x0) * s, fy_top + (y - y0) * s
    # 평면도 외곽
    if pr.kind == d3.PRISM:
        sh.poly([T(*q) for q in d3._simplify(pr.poly, 0.02)], True, "OUTLINE", 0.5)
    else:
        sh.rect(*T(x0, y0), dx * s, dy * s, "OUTLINE", 0.5)
    # 날·홈 (관통 = 실선, 아래 빠짐·막힌 홈 = 숨은선)
    for c in pr.cuts:
        P = d3._offset(c[0], c[1]) if c[1] else np.asarray(c[0], float)
        P = np.clip(d3._simplify(P, 0.02), [x0, y0], [x0 + dx, y0 + dy])
        through = len(c) <= 2 or (c[2] <= z0 + 1e-6 and c[2] + c[3] >= z0 + dz - 1e-6)
        relief = len(c) > 2 and c[1]
        lay = "WIRE" if (through or (not relief and c[2] + c[3] >= z0 + dz - 1e-6)) else "HIDDEN"
        if len(c) > 4 and c[4] == "slot":
            lay = "OUTLINE"                              # 클램프 U 홈 (바깥 모양)
        sh.poly([T(*q) for q in P], True, lay, 0.35 if lay == "WIRE" else 0.25)
    # 날 (와이어 프로파일) 기호 W1 … — 관통 날만, 크기는 다이 날 치수표에서
    wires = []
    for c in pr.cuts:
        if len(c) > 2 and c[1] or (len(c) > 4 and c[4] == "slot"):
            continue
        through = len(c) <= 2 or (c[2] <= z0 + 1e-6 and c[2] + c[3] >= z0 + dz - 1e-6) or c[2] + c[3] >= z0 + dz - 1e-6
        P = np.asarray(d3._offset(c[0], c[1]) if c[1] else c[0], float)
        if not through or P[:, 0].min() < x0 - 1 or P[:, 0].max() > x0 + dx + 1:
            continue
        wires.append(P)
    for i, P in enumerate(wires, 1):
        q = d3._deep_point(P) or tuple(P.mean(0))
        cx, cy = T(q[0], q[1] + 0.25 * np.ptp(P[:, 1]))
        size = (f"Ø{d3._circle_d(P)[0]:.3f}" if d3._is_round(P)
                else f"{np.ptp(P[:, 0]):.3f} × {np.ptp(P[:, 1]):.3f}")
        sh.text(cx, cy, f"W{i}  {size}", 2.2, "C", "WIRE")
    tab = d3.hole_table(part)
    for sym, kind, cnt, pts, spec in tab:
        for i, (hx, hy, h) in enumerate(pts, 1):
            cx, cy = T(hx, hy)
            from_bottom = h.side == "밑면"
            lay = "HIDDEN" if from_bottom and h.h < dz - 1e-6 else "OUTLINE"
            if h.kind == "탭":
                major = {4.2: 5, 5.0: 6, 6.8: 8, 8.5: 10, 10.2: 12, 14.0: 16}.get(round(h.d, 1), h.d * 1.2)
                sh.circle(cx, cy, h.d / 2 * s, lay, 0.35)
                sh.circle(cx, cy, major / 2 * s, "THIN", 0.18)          # 나사 바깥 지름 (가는 선)
            else:
                sh.circle(cx, cy, h.d / 2 * s, lay, 0.35)
            if h.cb:
                sh.circle(cx, cy, h.cb[0] / 2 * s, "HIDDEN" if from_bottom else "OUTLINE", 0.25)
            sh.center_mark(cx, cy, max(h.d, h.cb[0] if h.cb else 0) / 2 * s)
            sh.text(cx + max(h.d / 2 * s, 1.0) + 0.6, cy + 0.6, f"{sym}{i}", 1.8, "L", "TEXT")
    # 원점 기호
    ox, oy = T(x0, y0)
    sh.circle(ox, oy, 1.6, "DIM", 0.25)
    sh.line(ox - 2.5, oy, ox + 2.5, oy, "DIM", 0.18)
    sh.line(ox, oy - 2.5, ox, oy + 2.5, "DIM", 0.18)
    # 바깥 치수
    sh.dim_h(*[T(x0, 0)[0], T(x0 + dx, 0)[0]], T(0, y0 + dy)[1], T(0, y0 + dy)[1] + 8, _num(dx))
    sh.dim_v(T(0, y0)[1], T(0, y0 + dy)[1], T(x0, 0)[0], T(x0, 0)[0] - 8, _num(dy))
    # 정면도 (앞에서, x–z): 외곽 + 구멍 숨은선 (깊이)
    def F(x, z):
        return fx + (x - x0) * s, fy_front + (z - z0) * s
    if pr.kind == d3.PROF and pr.ax == "y":             # 옆 단면 (절곡 다이·펀치: R · 경사 그대로)
        sh.poly([F(*q) for q in pr.poly], True, "OUTLINE", 0.5)
    else:
        sh.rect(*F(x0, z0), dx * s, dz * s, "OUTLINE", 0.5)
    seen = set()
    for h in pr.holes:
        if h.kind == "와이어 시작":
            continue
        key = (round(h.x, 1), round(h.d, 1), round(h.z0, 1))
        if key in seen:
            continue
        seen.add(key)
        za, zb = max(h.z0, z0), min(h.z0 + h.h, z0 + dz)
        for sx_ in (-1, 1):
            xa, ya = F(h.x + sx_ * h.d / 2, za)
            xb, yb = F(h.x + sx_ * h.d / 2, zb)
            sh.line(xa, ya, xb, yb, "HIDDEN", 0.25)
        if h.cb:
            D, zc, hc = h.cb
            for sx_ in (-1, 1):
                sh.line(*F(h.x + sx_ * D / 2, max(zc, z0)), *F(h.x + sx_ * D / 2, min(zc + hc, z0 + dz)), "HIDDEN", 0.25)
        c1 = F(h.x, za)
        c2 = F(h.x, zb)
        sh.line(c1[0], c1[1] - 1.5, c2[0], c2[1] + 1.5, "CENTER", 0.18)
    for c in pr.cuts:
        if len(c) > 2:
            P = d3._offset(c[0], c[1]) if c[1] else np.asarray(c[0], float)
            xa_, xb_ = max(P[:, 0].min(), x0), min(P[:, 0].max(), x0 + dx)
            za, zb = max(c[2], z0), min(c[2] + c[3], z0 + dz)
            sh.rect(*F(xa_, za), (xb_ - xa_) * s, (zb - za) * s, "HIDDEN", 0.25)
    # 우측면도 (정면도 오른쪽, 3각법): 오른쪽에서 본 y–z — 숨은선 지운 정투상 (구멍 = 파선)
    rx = F(x0 + dx, 0)[0] + 28
    try:
        from . import dieview
        vis, hid = dieview.hlr([d3._solid(pr)], view=dieview.RIGHT[0], hidden=True, up=dieview.RIGHT[1])
        for P in hid:
            sh.poly([(rx + (q[0] - y0) * s, fy_front + (q[1] - z0) * s) for q in P], False, "HIDDEN", 0.25)
        for P in vis:
            sh.poly([(rx + (q[0] - y0) * s, fy_front + (q[1] - z0) * s) for q in P], False, "OUTLINE", 0.5)
        sh.dim_h(rx, rx + dy * s, fy_front, fy_front - 6, _num(dy))
        sh.text(rx, fy_front + dz * s + 4, "우측면도", 3.0, "L", bold=True)
        side_ok = True
    except Exception:  # noqa: BLE001
        side_ok = False
    sh.dim_v(F(0, z0)[1], F(0, z0 + dz)[1], F(x0, 0)[0] if side_ok else F(x0 + dx, 0)[0],
             F(x0, 0)[0] - 8 if side_ok else F(x0 + dx, 0)[0] + 12, _num(dz))
    sh.text(fx, fy_top + dy * s + 16, "평면도", 3.0, "L", bold=True)
    sh.text(fx, fy_front + dz * s + 4, "정면도", 3.0, "L", bold=True)
    # 주기 (아래부터) · 입체도 (그 위) · 구멍 좌표표 (맨 위)
    notes = list(NOTES_BASE)
    if any(len(c) > 2 and c[1] for c in pr.cuts):
        notes.insert(0, "날: 와이어 — 위 랜드 곧게, 아래 한쪽 +0.5 빠짐 (숨은선), 프로파일은 가공 DXF 의 WIRE 레이어")
    if "SKD11" in part.material or "SKH" in part.material:
        notes.insert(0, f"열처리 {_heat(part.material)} 뒤 위·아래 면 연삭 (평행도 0.01), 날 면 Ra 0.4")
    elif part.name in d3.PLATES:
        notes.insert(0, "위·아래 면 연삭 (평행도 0.02), 날 안내 면 Ra 0.8, 그 밖 Ra 3.2")
    if pr.kind == d3.PRISM:
        notes.insert(0, "외곽: 와이어 (펀치 = 블랭크 − 2c, 날 치수표), 프로파일은 가공 DXF · 날 면 Ra 0.4")
    if part.weight > 25:
        notes.append(f"무게 {part.weight:.0f} kg — 옆면 아이볼트 탭 M12 × 2 (들어 올림)")
    if part.note:
        notes.append(part.note)
    ny = MARGIN + TB_H + 6 + 4.5 * len(notes)
    tx = MARGIN + W * 0.62
    ty = H - MARGIN - 10
    iso_top = ny + 10 + ISO_H
    if lines3d:
        _iso(sh, lines3d, tx, ny + 10, W - MARGIN - 4 - tx, ISO_H, "입체도")
    else:
        iso_top = ny + 6
    # 구멍 좌표표
    cols = [10, 8, 20, 20, 78]
    _table(sh, tx, ty, cols, ["기호", "번호", "X", "Y", "가공"],
           [[sym if i == 1 else "", i, f"{hx - x0:.2f}", f"{hy - y0:.2f}",
             (spec + (f" ({h.side})" if h.side != "윗면" else "")) if i == 1 else ""]
            for sym, kind, cnt, pts, spec in tab for i, (hx, hy, h) in enumerate(pts, 1)]
           + [[f"W{i}", "", f"{np.mean(P[:, 0]) - x0:.2f}", f"{np.mean(P[:, 1]) - y0:.2f}",
                "와이어 날 " + (f"Ø{d3._circle_d(P)[0]:.3f}" if d3._is_round(P)
                               else f"{np.ptp(P[:, 0]):.3f} × {np.ptp(P[:, 1]):.3f}") + " (가운데 좌표)"]
              for i, P in enumerate(wires, 1)],
           max_rows=max(int((ty - iso_top - 10) / 4.2) - 1, 3))
    sh.text(tx, ny + 4, "주기", 3.0, "L", bold=True)
    for k, n in enumerate(notes, 1):
        sh.text(tx, ny - 4.5 * (k - 1), f"{k}. {n}", 2.2)
    return sh


ISO_H = 62.0              # 부품도 오른쪽 입체도 칸 높이 (mm)


def _part_lines(pr: d3.Prim):
    """부품 솔리드 (구멍·날 판 것) 를 숨은선 지워 등각으로 — 화면 2D 꺾은선 (보이는 선)."""
    try:
        from . import dieview
        vis, _ = dieview.hlr([d3._solid(pr)])
        return vis
    except Exception:  # noqa: BLE001 — 입체도는 덤
        return []


def _fit2d(lines2d, x, y, w, h, top=5.0):
    """2D 선들을 칸 (x, y, w, h — 위 글 칸 top) 에 맞추는 변환 T(q) 와 배율."""
    allp = np.vstack(lines2d)
    lo, hi = allp.min(0), allp.max(0)
    s = min((w - 4) / max(hi[0] - lo[0], 1e-9), (h - 4 - top) / max(hi[1] - lo[1], 1e-9))
    mx, my = 0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1])
    cx, cy = x + w / 2, y + (h - top) / 2

    def T(q):
        return cx + (q[0] - mx) * s, cy + (q[1] - my) * s
    return T, s


def _iso(sh: Sheet, lines2d, x, y, w, h, title, layer="THIN", frame=True):
    """숨은선 지운 입체도 (dieview.hlr 의 화면 2D 선) 를 칸에 맞춰 넣음."""
    if not lines2d:
        return None
    T, s = _fit2d(lines2d, x, y, w, h)
    if frame:
        sh.rect(x, y, w, h, "THIN", 0.18)
    for P in lines2d:
        sh.poly([T(q) for q in P], False, layer, 0.25)
    sh.text(x + 1.5, y + h - 4.2, title, 2.6, "L", bold=True)
    return T


def _heat(material):
    if "HRC" in material:
        return "HRC " + material.split("HRC")[1].strip().split(" ")[0].strip(")")
    if "열처리" in material:
        return "열처리 (" + material.split("(")[-1].strip(")") + ")"
    return "-"


def _table(sh, x, ytop, cols, head, rows, h=4.2, max_rows=60):
    """위에서 아래로 표 (머리 굵게)."""
    W = sum(cols)
    y = ytop
    sh.rect(x, y - h, W, h, "OUTLINE", 0.35)
    cx = x
    for wd, t in zip(cols, head):
        sh.text(cx + 1, y - h + 1.2, t, 2.2, "L", bold=True)
        cx += wd
    shown = rows[:max_rows]
    for r in shown:
        y -= h
        sh.line(x, y - h, x + W, y - h, "THIN", 0.18)
        cx = x
        for wd, v in zip(cols, r):
            sh.text(cx + 1, y - h + 1.2, v, 2.0)
            cx += wd
    cx = x
    for wd in cols[:-1]:
        cx += wd
        sh.line(cx, ytop, cx, y - h, "THIN", 0.18)
    sh.rect(x, y - h, W, ytop - (y - h), "OUTLINE", 0.35)
    if len(rows) > max_rows:
        sh.text(x, y - h - 4, f"… {len(rows) - max_rows} 줄 더 — 엑셀 [가공 구멍표]", 2.0)
    return y - h


# ---------------------------------------------------------------- 조립도

def assembly_sheet(assy: d3.DieAssy, info, number):
    sh = Sheet("금형 조립도", number, A3, material="-", qty=1,
               weight=sum(p.weight * p.qty for p in assy.parts))
    W, H = sh.size
    zmax = assy.open_h
    # 왼쪽 평면도 (하형), 오른쪽 정면도, 아래 오른쪽 부품표
    box_w, box_h = W * 0.46, (H - 2 * MARGIN - 20) * 0.5
    s, sh.scale = _pick_scale(assy.L, max(assy.W, zmax), box_w, box_h)
    tx0, ty0 = MARGIN + 14, H - MARGIN - 14 - assy.W * s

    def T(x, y):
        return tx0 + (x + assy.L / 2) * s, ty0 + (y + assy.W / 2) * s
    fx0, fy0 = tx0, MARGIN + 18

    def F(x, z):
        return fx0 + (x + assy.L / 2) * s, fy0 + z * s
    balloons = []
    for part in assy.parts:
        for pr in part.prims:
            if pr.kind == d3.BOX:
                bx, by, bz, dx, dy, dz = pr.p
                if not part.upper:
                    sh.rect(*T(bx, by), dx * s, dy * s, "OUTLINE", 0.35)
                sh.rect(*F(bx, bz), dx * s, dz * s, "OUTLINE", 0.35)
            elif pr.kind == d3.CYL:
                x, y, z0, r, h = pr.p
                if not part.upper or "펀치" in part.name:
                    sh.circle(*T(x, y), r * s, "HIDDEN" if part.upper else "OUTLINE", 0.25)
                sh.rect(*F(x - r, z0), 2 * r * s, h * s, "OUTLINE", 0.25)
            elif pr.kind == d3.PROF:
                bx, by, bz, dx, dy, dz = d3.extent(pr)
                if not part.upper:
                    sh.rect(*T(bx, by), dx * s, dy * s, "OUTLINE", 0.35)
                if pr.ax == "y":
                    sh.poly([F(*q) for q in pr.poly], True, "OUTLINE", 0.35)
                else:
                    sh.rect(*F(bx, bz), dx * s, dz * s, "OUTLINE", 0.35)
            else:
                z0, h = pr.p
                P = d3._simplify(pr.poly, 0.05)
                sh.poly([T(*q) for q in P], True, "HIDDEN", 0.25)
                sh.rect(*F(P[:, 0].min(), z0), np.ptp(P[:, 0]) * s, h * s, "OUTLINE", 0.35)
        if part.name == "다이 플레이트":
            for c in part.prims[0].cuts:
                if len(c) > 2 and not c[1]:
                    sh.poly([T(*q) for q in d3._simplify(c[0], 0.05)], True, "WIRE", 0.35)
        if part.prims:
            # 부품마다 (x 범위, z 가운데) — 풍선 자리를 먼저 정하고 그 x 로 내려가게
            def xr(q):
                e = d3.extent(q)
                return e[0], e[0] + e[3], e[2] + e[5] / 2
            spans = [xr(q) for q in part.prims]
            narrow = min(spans, key=lambda r_: (r_[1] - r_[0], -r_[1]))
            balloons.append((part.no, spans, 0.5 * (narrow[0] + narrow[1])))
    # 풍선: 정면도 위 빈자리에 가로 두 줄 — 부품의 좁은 프리미티브 가운데 x 순으로 자리를 정하고, 그 자리 x 에서
    # 수직으로 내려가 부품에 닿게 (판처럼 넓은 부품은 아무 x 에나 닿음) — 지시선이 엇갈리지 않음
    balloons.sort(key=lambda b: (b[2], b[0]))
    xa, xb = F(-assy.L / 2, 0)[0], F(assy.L / 2, 0)[0]
    n_b = len(balloons)
    base = F(0, zmax)[1] + 12
    for k, (no, spans, _) in enumerate(balloons):
        bx_ = xa + (xb - xa) * (k + 0.5) / max(n_b, 1)
        by_ = base + (k % 2) * 7.0
        xm = (bx_ - fx0) / s - assy.L / 2                   # 풍선 자리의 모델 x
        best = min(spans, key=lambda r_: 0 if r_[0] <= xm <= r_[1] else min(abs(xm - r_[0]), abs(xm - r_[1])))
        ax = min(max(xm, best[0]), best[1])
        at = F(ax, best[2])
        sh.line(at[0], at[1], bx_, by_ - 2.6, "THIN", 0.18)
        sh.circle(at[0], at[1], 0.5, "THIN", 0.18)
        sh.circle(bx_, by_, 2.6, "OUTLINE", 0.25)
        sh.text(bx_, by_ - 0.9, str(no), 2.0, "C")
    _work(sh, assy, F, proj=lambda q: (q[0], q[2]))
    _work(sh, assy, T, ("before",))
    # 높이 치수
    xl = F(-assy.L / 2, 0)[0]
    sh.dim_v(F(0, 0)[1], F(0, zmax)[1], xl, xl - 8, f"열림 {zmax:.1f}")
    sh.line(xl - 12, F(0, assy.shut)[1], xl, F(0, assy.shut)[1], "DIM", 0.18)
    sh.text(xl - 9, F(0, assy.shut)[1] + 0.8, f"닫힘 {assy.shut:.1f}", 2.0, "R", "DIM")
    sh.dim_h(T(-assy.L / 2, 0)[0], T(assy.L / 2, 0)[0], T(0, assy.W / 2)[1], T(0, assy.W / 2)[1] + 6, f"{assy.L:g}")
    sh.text(tx0, ty0 + assy.W * s + 10, "평면도 (하형, 펀치는 숨은선)", 2.8, "L", bold=True)
    # 단면 표시 A-A (y = 0, 단면도 장)
    ya = T(0, 0)[1]
    xa0, xa1 = T(-assy.L / 2, 0)[0] - 6, T(assy.L / 2, 0)[0] + 6
    sh.line(xa0, ya, xa1, ya, "CENTER", 0.25)
    for xx in (xa0, xa1):
        sh.line(xx, ya, xx, ya - 5, "OUTLINE", 0.5)
        sh.arrow(xx, ya - 5, -math.pi / 2, 2.5)
        sh.text(xx, ya + 1.2, "A", 3.0, "C", bold=True)
    sh.text(fx0, F(0, zmax)[1] + 23, "정면도 (열린 상태)", 2.8, "L", bold=True)
    # 부품표 (표제란 위, 오른쪽)
    x = W - MARGIN - 190
    rows = [[p.no, p.name, p.qty, p.material.split(" HRC")[0], p.size, "표준" if p.std else "가공"]
            for p in assy.parts]
    cols = [8, 52, 8, 34, 66, 12]
    ytop = H - MARGIN - 6
    nrow = min(len(rows), int((ytop - MARGIN - TB_H - 10) / 3.9) - 1)
    y_bot = _table(sh, x + 2, ytop, cols, ["번호", "품명", "수량", "재질", "크기 · 규격", "구분"], rows, h=3.9,
                   max_rows=int((ytop - MARGIN - TB_H - 10) / 3.9) - 1)
    # 제품도 (조립도 옆): 정면도·풍선 오른쪽, 부품표 아래, 표제란 위
    bx0 = max(F(assy.L / 2, 0)[0] + 12, W * 0.45)
    by0 = MARGIN + TB_H + 30
    bw, bh = W - MARGIN - 4 - bx0, y_bot - 6 - by0
    if bw > 60 and bh > 40:
        _product_box(sh, assy, info, bx0, by0, bw, bh)
    del nrow
    return sh


def _flat_loops(assy, info):
    """제품 전개 (블랭크) 외곽·구멍 (다이 좌표가 아니라 전개도 좌표) 과 절곡선."""
    res = info.get("result")
    bends = []
    if res is not None:
        try:
            from .nesting import NestPart
            np_ = NestPart.from_result("p", res)
            outer = np.asarray(np_.outer, float)
            holes = [np.asarray(h, float) for h in np_.holes]
            bends = [np.asarray(b.line, float) for b in res.bends]
            return outer, holes, bends
        except Exception:  # noqa: BLE001
            pass
    return np.asarray(assy.blank, float), [np.asarray(h, float) for h in assy.holes], bends


def _flat_view(sh, outer, holes, bends, x, y, w, h, dims=True, title="전개도"):
    """전개도 (블랭크) 를 칸에 맞춰: 외곽·구멍 실선, 절곡선 중심선, 바깥 치수."""
    lo, hi = outer.min(0), outer.max(0)
    dx, dy = hi - lo
    s = min((w - 22) / max(dx, 1e-9), (h - 22) / max(dy, 1e-9))
    ox, oy = x + 14 + (w - 22 - dx * s) / 2, y + 10 + (h - 22 - dy * s) / 2

    def T(q):
        return ox + (q[0] - lo[0]) * s, oy + (q[1] - lo[1]) * s
    sh.rect(x, y, w, h, "THIN", 0.18)
    sh.poly([T(q) for q in d3._simplify(outer, 0.02)], True, "OUTLINE", 0.4)
    for hh in holes:
        sh.poly([T(q) for q in d3._simplify(hh, 0.01)], True, "OUTLINE", 0.3)
    for b in bends:
        sh.line(*T(b[0]), *T(b[1]), "CENTER", 0.25)
    if dims:
        sh.dim_h(T(lo)[0], T((hi[0], lo[1]))[0], T(lo)[1], T(lo)[1] - 6, _num(dx, 2))
        sh.dim_v(T(lo)[1], T((lo[0], hi[1]))[1], T(lo)[0], T(lo)[0] - 6, _num(dy, 2))
    sh.text(x + 1.5, y + h - 4.2, title + ("" if not bends else f" (절곡선 {len(bends)} — 중심선)"), 2.6, "L", bold=True)
    return s


def _product_box(sh, assy, info, x, y, w, h):
    """조립도 옆 제품도: 왼쪽 입체도 (3D 가 있으면), 오른쪽 전개도 (바깥 치수)."""
    solid = info.get("solid")
    outer, holes, bends = _flat_loops(assy, info)
    sh.text(x, y + h + 1.5, f"제품도 — {info.get('product', '')} · {info.get('material', '')}", 2.8, "L", bold=True)
    lines = _solid_lines(solid)
    if lines:
        _iso(sh, lines, x, y, w * 0.45, h, "제품 입체도", "OUTLINE")
        _flat_view(sh, outer, holes, bends, x + w * 0.47, y, w * 0.53, h)
    else:
        _flat_view(sh, outer, holes, bends, x, y, w, h)


def _solid_lines(solid):
    """제품 입체도: 숨은선 지운 등각 (안 되면 모서리 선을 등각 투영)."""
    if solid is None:
        return []
    try:
        from . import dieview
        vis, _ = dieview.hlr([solid])
        if vis:
            return vis
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import dieview
        from .drawing import solid_polylines
        return [np.array([dieview.project_point(q) for q in L]) for L in solid_polylines(solid, samples=24, iso=False)]
    except Exception:  # noqa: BLE001
        return []


def product_sheet(assy: d3.DieAssy, info, number):
    """제품도: 입체도 (3D 모델) + 전개도 (바깥 치수 · 절곡선) + 절곡표 · 사양."""
    res = info.get("result")
    sh = Sheet("제품도 · 전개도", number, A3, material=info.get("material", ""), qty=1,
               weight=float(assy.usage.get("part_kg", 0.0)) if assy.usage else 0.0)
    W, H = sh.size
    top = H - MARGIN - 8
    area_y = MARGIN + TB_H + 8
    lines = _solid_lines(info.get("solid"))
    outer, holes, bends = _flat_loops(assy, info)
    if lines:
        _iso(sh, lines, MARGIN + 6, area_y + 40, W * 0.42, top - area_y - 40, "제품 입체도 (3D 모델)", "OUTLINE")
        fx = MARGIN + 10 + W * 0.42
    else:
        fx = MARGIN + 6
    sc = _flat_view(sh, outer, holes, bends, fx, area_y + 40, W - MARGIN - 4 - fx, top - area_y - 40,
                    title="전개도 (블랭크)")
    sh.scale = "NTS"                                  # 그림 칸에 맞춰 그림 (치수가 실제 값)
    del sc
    # 절곡표 · 사양 (아래)
    rows = []
    if res is not None and res.bends:
        rows = [[f"B{b.number}", f"{b.angle_deg:.1f}°", f"R{b.inner_radius:g}", "UP" if b.direction == "UP" else "DOWN",
                 f"{b.length:.1f}", f"{b.allowance:.3f}", f"{b.k:.3f}"] for b in res.bends]
        _table(sh, MARGIN + 6, area_y + 34, [12, 16, 14, 14, 18, 20, 14],
               ["절곡", "각도", "안쪽 R", "방향", "길이", "펼친 폭 BA", "K"], rows, h=4.0, max_rows=6)
    u = assy.usage or {}
    lo, hi = outer.min(0), outer.max(0)
    spec = [f"전개 크기 {np.ptp(outer[:, 0]):.2f} × {np.ptp(outer[:, 1]):.2f} mm · 구멍 {len(holes)} 개 · 절곡 {len(bends)} 곳",
            f"제품 무게 {u.get('part_kg', 0):.3f} kg · 재질 {info.get('material', '')}",
            "전개도 실치수 가공 데이터는 전개 DXF (1:1) 를 쓰세요"]
    for k, ln in enumerate(spec):
        sh.text(W * 0.55, area_y + 30 - 5 * k, ln, 2.5)
    del lo, hi
    return sh


# ---------------------------------------------------------------- 스트립 배치도

def strip_sheet(assy: d3.DieAssy, info, number):
    """스트립 배치도: 공정마다 부품 외곽 (가는 선), 다이 날 (빨강), 앞 공정 구멍 (숨은선), 공정 이름 · 피치 · 폭."""
    sh = Sheet("스트립 배치도", number, A3, material=info.get("material", ""), qty=1)
    W, H = sh.size
    die = assy.plate("다이 플레이트").prims[0]
    opens = [d3._simplify(c[0], 0.05) for c in die.cuts if len(c) > 2 and not c[1]]
    pitch, Wst = assy.strip
    st = assy.stations or []
    if not opens and not st:
        return sh
    allx = np.vstack(opens + [Q for _, _, Q in st]) if (opens or st) else np.zeros((1, 2))
    x0, x1 = allx[:, 0].min() - 0.5 * pitch, allx[:, 0].max() + 0.4 * pitch
    s, sh.scale = _pick_scale(x1 - x0, Wst * 1.5, W - 2 * MARGIN - 40, H - 2 * MARGIN - TB_H - 60)
    ox, oy = MARGIN + 20, MARGIN + TB_H + 40 + Wst * s / 2

    def T(x, y):
        return ox + (x - x0) * s, oy + y * s
    sh.rect(*T(x0, -Wst / 2), (x1 - x0) * s, Wst * s, "OUTLINE", 0.5)
    for nm, xc, Q in st:
        sh.poly([T(*q) for q in d3._simplify(Q, 0.05)], True, "THIN", 0.25)
        sh.text(T(xc, 0)[0], T(0, -Wst / 2)[1] - 6, nm, 2.6, "C", bold=True)
        sh.line(*T(xc, -Wst / 2 - 2), *T(xc, Wst / 2 + 2), "CENTER", 0.18)
    # 앞 공정에서 뚫은 구멍은 다음 공정들에도 (숨은선)
    xs_st = sorted(xc for _, xc, _ in st)
    for Q in opens:
        sh.poly([T(*q) for q in Q], True, "WIRE", 0.5)
        if abs(d3._area(Q)) < 0.5 * max((abs(d3._area(q)) for _, _, q in st), default=1e9):
            for xc in xs_st:
                dxs = xc - float(Q[:, 0].mean())
                if dxs > 0.3 * pitch:
                    k_ = round(dxs / pitch)
                    sh.poly([T(q[0] + k_ * pitch, q[1]) for q in Q], True, "HIDDEN", 0.25)
    yt = T(0, Wst / 2)[1]
    if len(xs_st) >= 2:
        sh.dim_h(T(xs_st[0], 0)[0], T(xs_st[1], 0)[0], yt, yt + 10, f"피치 {pitch:.1f}")
    elif xs_st:
        sh.dim_h(T(xs_st[0] - pitch / 2, 0)[0], T(xs_st[0] + pitch / 2, 0)[0], yt, yt + 10, f"피치 {pitch:.1f}")
    sh.dim_v(T(0, -Wst / 2)[1], T(0, Wst / 2)[1], T(x0, 0)[0], T(x0, 0)[0] - 8, f"폭 {Wst:.1f}")
    sh.text(T(x1, 0)[0] - 30, yt + 4, "이송 →", 3.0, "L", bold=True)
    lines = d3.press_lines(assy) + ([getattr(assy, "layout_note")] if getattr(assy, "layout_note", "") else [])
    for k_, ln in enumerate(lines):
        sh.text(MARGIN + 12, MARGIN + TB_H + 24 - 5 * k_, ln, 2.5)
    return sh


# ---------------------------------------------------------------- 표지

def cover_sheet(assy: d3.DieAssy, info, number, index):
    sh = Sheet("금형 설계 도면집", number, A3, material=info.get("material", ""), qty=1,
               weight=sum(p.weight * p.qty for p in assy.parts))
    W, H = sh.size
    y = H - MARGIN - 18
    sh.text(MARGIN + 14, y, f"{info.get('product', '')} — {assy.kind} 금형", 7.0, "L", bold=True)
    y -= 14
    pr = assy.press or {}
    spec = [("금형 크기 (L × W)", f"{assy.L:g} × {assy.W:g} mm"),
            ("닫힌 높이 / 열린 높이", f"{assy.shut:.1f} / {assy.open_h:.1f} mm"),
            ("필요 행정", f"≥ {assy.stroke:.0f} mm"),
            ("절단력 / 스프링 / 합", f"{pr.get('cut_kn', 0):,.1f} / {pr.get('spring_kn', 0):,.1f} / {pr.get('total_kn', 0):,.1f} kN"),
            ("필요 프레스", f"{pr.get('need_tf', 0):,.0f} tf → {pr.get('machine', '') or '-'}"),
            ("전단 에너지", f"{pr.get('energy_j', 0):,.0f} J / 타"),
            ("스트립 피치 × 폭", f"{assy.strip[0]:.1f} × {assy.strip[1]:.1f} mm"),
            ("다이 스프링", assy.spring.label() + f" × {assy.spring.n}" if assy.spring else "-"),
            ("금형 무게 (어림)", f"{sum(p.weight * p.qty for p in assy.parts):,.0f} kg"),
            ("압력 중심", f"({assy.cop[0]:+.1f}, {assy.cop[1]:+.1f}) mm")]
    if getattr(assy, "spec", None):
        spec = [("금형 크기 (L × W)", f"{assy.L:g} × {assy.W:g} mm"),
                ("닫힌 높이 / 열린 높이", f"{assy.shut:.1f} / {assy.open_h:.1f} mm"),
                ("필요 행정", f"≥ {assy.stroke:.0f} mm")] + spec + [
                ("금형 무게 (어림)", f"{sum(p.weight * p.qty for p in assy.parts):,.0f} kg")]
    for k, v in spec:
        sh.text(MARGIN + 14, y, k, 3.0)
        sh.text(MARGIN + 74, y, v, 3.0)
        y -= 6
    y -= 4
    sh.text(MARGIN + 14, y, "점검", 3.4, "L", bold=True)
    rows = [[c[0], c[1], c[3]] for c in assy.checks]
    _table(sh, MARGIN + 14, y - 2, [92, 52, 14], ["항목", "값", "판정"], rows, h=4.0, max_rows=22)
    # 도면 목록
    x = W / 2 + 20
    sh.text(x, H - MARGIN - 32, "도면 목록", 3.4, "L", bold=True)
    _table(sh, x, H - MARGIN - 34, [10, 40, 80], ["장", "도번", "이름"],
           [[i, nb, nm] for i, (nb, nm) in enumerate(index, 1)], h=4.4, max_rows=40)
    return sh


# ---------------------------------------------------------------- 3D 도면: 입체 조립도 · 분해도 · 단면도

PLATE_ORDER = ["하형 다이 세트", "다이 받침판", "다이 플레이트", "스트리퍼 플레이트", "펀치 플레이트", "펀치 받침판", "상형 다이 세트"]


def _solids(assy, cache):
    """[(부품, 프리미티브, 솔리드)] — 한 번 만든 솔리드를 시트끼리 같이 씀."""
    out = []
    for part in assy.parts:
        for pr in part.prims:
            k = id(pr)
            if k not in cache:
                try:
                    cache[k] = d3._solid(pr)
                except Exception:  # noqa: BLE001
                    cache[k] = None
            if cache[k] is not None:
                out.append((part, pr, cache[k]))
    return out


def _zmid(pr):
    e = d3.extent(pr)
    return e[2] + e[5] / 2


def _center3(pr):
    x0, y0, z0, dx, dy, dz = d3.extent(pr)
    if pr.kind == d3.PRISM:
        c = np.asarray(pr.poly, float).mean(0)
        return np.array([c[0], c[1], z0 + dz / 2])
    return np.array([x0 + dx / 2, y0 + dy / 2, z0 + dz / 2])


def _plates(assy):
    """판 (쌓기 층): 전단 금형은 이름 차례, 그 밖 (절곡 금형) 은 가공품 상자·단면 중 넓은 것을 밑면 높이 순."""
    out = []
    for nm in PLATE_ORDER:
        try:
            pr = assy.plate(nm).prims[0]
            out.append((nm, pr.p[2], pr.p[2] + pr.p[5]))
        except StopIteration:
            pass
    if len(out) >= 3:
        return out
    out = []
    for p in assy.parts:
        if p.std or not p.prims or p.prims[0].kind not in (d3.BOX, d3.PROF):
            continue
        e = d3.extent(p.prims[0])
        if e[3] >= 0.25 * assy.L or len(p.prims) == 1 and e[3] * e[4] >= 0.05 * assy.L * assy.W:
            out.append((p.name, e[2], e[2] + e[5]))
    out.sort(key=lambda q: (q[1], q[2]))
    return out


def _explode_offsets(assy):
    """부품마다 분해 높이: 판 쌓기 차례 (가장 가까운 아래 판) × 간격."""
    plates = [(nm, z0) for nm, z0, _ in _plates(assy)]
    gap = max(assy.open_h / max(len(plates), 1), 30.0)
    off = {}
    for part in assy.parts:
        if not part.prims:
            continue
        if part.name in [n for n, _ in plates]:
            rank = [n for n, _ in plates].index(part.name)
        else:
            zc = _zmid(part.prims[0])
            below = [i for i, (_, z0) in enumerate(plates) if z0 <= zc + 1e-6]
            rank = below[-1] if below else 0
            if part.name.startswith("다이 스프링") or part.name.startswith("스트리퍼 볼트"):
                rank = [n for n, _ in plates].index("스트리퍼 플레이트") if "스트리퍼 플레이트" in [n for n, _ in plates] else rank
        off[part.no] = rank * gap
    return off


def _translated(shape, dz):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(0, 0, float(dz)))
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def _side_balloons(sh, items, x, y, w, h, r=2.6):
    """풍선을 칸 왼쪽 · 오른쪽 세로 줄에 — 닿는 점이 가운데보다 왼쪽이면 왼쪽 줄, 줄 안에서는 높이 순 (지시선이 엇갈리지 않게)."""
    if not items:
        return
    cx = x + w / 2
    top, bot = y + h - 12, y + 6
    for side, sel in ((-1, [it for it in items if it[1][0] < cx]), (1, [it for it in items if it[1][0] >= cx])):
        sel = sorted(sel, key=lambda it: -it[1][1])
        if not sel:
            continue
        step = (top - bot) / max(len(sel) - 1, 1)
        bx_ = x + 5 if side < 0 else x + w - 5
        for k, (no, at) in enumerate(sel):
            by_ = top - k * step if len(sel) > 1 else (top + bot) / 2
            sh.line(at[0], at[1], bx_ - side * r, by_, "THIN", 0.18)
            sh.circle(at[0], at[1], 0.45, "THIN", 0.18)
            sh.circle(bx_, by_, r, "OUTLINE", 0.25)
            sh.text(bx_, by_ - 0.9, str(no), 2.0, "C")


def iso3d_sheet(assy: d3.DieAssy, info, number, cache):
    """입체 조립도 (숨은선 지움, 열린 상태) · 분해도 (판 차례로 띄움, 풍선 = 부품표 번호)."""
    from . import dieview
    sh = Sheet("입체 조립도 · 분해도", number, A3, material="-", qty=1, weight=sum(p.weight * p.qty for p in assy.parts))
    sh.scale = "NTS"
    W, H = sh.size
    y0 = MARGIN + TB_H + 6
    hh = H - MARGIN - 6 - y0
    sol = _solids(assy, cache)
    vis, _ = dieview.hlr([s_ for _, _, s_ in sol])
    w1 = W * 0.44
    T1 = _iso(sh, vis, MARGIN + 4, y0, w1, hh, "입체 조립도 (숨은선 지움 · 열린 상태)", "OUTLINE")
    if T1 is not None:
        _work(sh, assy, lambda *q: T1(q), ("before",), proj=dieview.project_point)
    off = _explode_offsets(assy)
    moved = [(_translated(s_, off.get(part.no, 0.0)), part, pr) for part, pr, s_ in sol]
    vis2, _ = dieview.hlr([m for m, _, _ in moved])
    x2 = MARGIN + 8 + w1
    w2 = W - MARGIN - 4 - x2
    T = _iso(sh, vis2, x2 + 12, y0, w2 - 24, hh, "분해도 (풍선 = 부품표 번호)", "OUTLINE", frame=False)
    sh.rect(x2, y0, w2, hh, "THIN", 0.18)
    if T is not None:
        items, seen = [], set()
        for _, part, pr in moved:
            if part.no in seen:
                continue
            seen.add(part.no)
            c = _center3(pr) + np.array([0, 0, off.get(part.no, 0.0)])
            items.append((part.no, T(dieview.project_point(c))))
        _side_balloons(sh, items, x2, y0, w2, hh)
    return sh


def section_sheet(assy: d3.DieAssy, info, number, cache, y_cut=0.0):
    """단면도 A-A (y = y_cut 으로 자름, 열린 상태): 판·펀치는 빗금, 볼트·핀·포스트·스프링 (표준품) 은 빗금 없이 (제도
    관례), 판 두께 치수 사슬, 풍선."""
    from . import dieview
    sh = Sheet("단면도 A-A", number, A3, material="-", qty=1)
    W, H = sh.size
    area_x, area_y = MARGIN + 28, MARGIN + TB_H + 12
    area_w, area_h = W * 0.68, H - MARGIN - 14 - area_y
    s, sh.scale = _pick_scale(assy.L, assy.open_h, area_w, area_h)
    zmax = assy.open_h

    def F(x, z):
        return area_x + (x + assy.L / 2) * s, area_y + z * s
    sol = _solids(assy, cache)
    anchors = {}
    for k, (part, pr, solid) in enumerate(sol):
        secs = dieview.section(solid, y_cut)
        for outer, holes in secs:
            loops = [outer] + holes
            for L in loops:
                sh.poly([F(*q) for q in L], True, "OUTLINE", 0.35)
            if not part.std:
                ang = 45.0 if (PLATE_ORDER.index(part.name) if part.name in PLATE_ORDER else part.no) % 2 else 135.0
                for p_, q_ in dieview.hatch(loops, 2.2 / s, ang):
                    sh.line(*F(*p_), *F(*q_), "HATCH", 0.13)
            A = 0.5 * abs(np.sum(outer[:, 0] * np.roll(outer[:, 1], -1) - np.roll(outer[:, 0], -1) * outer[:, 1]))
            if part.no not in anchors or A > anchors[part.no][1]:
                c = outer.mean(0)
                anchors[part.no] = (F(*c), A)
    # 풍선: 오른쪽 세로 줄 (높이 순 — 지시선이 엇갈리지 않게)
    items = sorted(((no, at) for no, (at, _) in anchors.items()), key=lambda it: -it[1][1])
    bx = F(assy.L / 2, 0)[0] + 14
    top, bot = F(0, zmax)[1], F(0, 0)[1]
    step = (top - bot) / max(len(items) - 1, 1)
    for k, (no, at) in enumerate(items):
        by_ = top - k * step
        bxx = bx + (k % 2) * 7
        sh.line(at[0], at[1], bxx - 2.6, by_, "THIN", 0.18)
        sh.circle(at[0], at[1], 0.45, "THIN", 0.18)
        sh.circle(bxx, by_, 2.6, "OUTLINE", 0.25)
        sh.text(bxx, by_ - 0.9, str(no), 2.0, "C")
    # 판 두께 치수 사슬 (왼쪽) · 전체 높이
    xl = F(-assy.L / 2, 0)[0]
    zs = []
    for _, za, zb in _plates(assy):
        zs += [za, zb]
    zs = sorted(set(round(z, 3) for z in zs))
    for z_a, z_b in zip(zs[:-1], zs[1:]):
        sh.dim_v(F(0, z_a)[1], F(0, z_b)[1], xl, xl - 6, _num(z_b - z_a, 1), 2.0)
    sh.dim_v(F(0, 0)[1], F(0, zmax)[1], xl, xl - 16, f"열림 {zmax:.1f}", 2.2)
    _work(sh, assy, F, proj=lambda q: (q[0], q[2]))
    sh.text(area_x, top + 6, f"단면도 A-A (y = {y_cut:.0f}, 열린 상태) — 닫힌 높이 {assy.shut:.1f} · 열림 틈 "
            f"{assy.open_h - assy.shut:.1f}", 2.8, "L", bold=True)
    sh.text(area_x, MARGIN + TB_H + 4, "판·펀치 = 빗금, 볼트·핀·포스트·스프링 (표준품) = 빗금 없음 (제도 관례) · 풍선 = 부품표 번호"
            + (" · 제품: 굵은 자주 = 공정 전, 가상선 = 하사점 (공정 뒤)" if getattr(assy, "work", None) else ""), 2.2, "L")
    return sh


# ---------------------------------------------------------------- 3면도 (평면도 · 정면도 · 우측면도, 3각법)

def _bbox3(shapes):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    for s_ in shapes:
        try:
            BRepBndLib.AddOptimal_s(s_, b, False, False)        # 딱 맞는 상자 (B-스플라인 면도 부풀리지 않음)
        except Exception:  # noqa: BLE001
            BRepBndLib.Add_s(s_, b)
    p0, p1 = b.CornerMin(), b.CornerMax()
    return np.array([p0.X(), p0.Y(), p0.Z()]), np.array([p1.X(), p1.Y(), p1.Z()])


def _views3(sh, shapes, x0, y0, w, h, work=None, gap=34.0, dims=True, hidden=True):
    """3각법 세 그림을 칸 (x0, y0, w, h) 에: 정면도 왼쪽 아래, 평면도 그 위, 우측면도 그 오른쪽 — 숨은선 (HLR) 까지.
    축척은 표준 척도 (1:1, 1:2 …) 에서. 돌려줌: (척도 s, {이름: 변환}) — 변환 T(a, b) 는 그 그림의 2D 좌표 → 종이."""
    from . import dieview
    lo, hi = _bbox3(shapes)
    L, Wd, H = hi - lo
    g = gap
    s, label = SCALES[-1][0] / SCALES[-1][1], f"{SCALES[-1][0]}:{SCALES[-1][1]:g}"
    for a_, b_ in SCALES:                                  # 큰 척도부터: 세 그림 + 사이 + 치수 자리가 칸에 들어가면
        k = a_ / b_
        if (L + Wd) * k + g + 30 <= w and (Wd + H) * k + g + 30 <= h:
            s, label = k, (f"{a_}:{b_:g}" if b_ != 1 else "1:1")
            break
    sh.scale = label
    fx = x0 + 18 + max(0.0, (w - 30 - (L + Wd) * s - g) / 2)          # 가운데로
    fy = y0 + 14 + max(0.0, (h - 30 - (Wd + H) * s - g) / 2)
    ty = fy + H * s + g
    rx = fx + L * s + g
    T = {"정면도": lambda a, b: (fx + (a - lo[0]) * s, fy + (b - lo[2]) * s),
         "평면도": lambda a, b: (fx + (a - lo[0]) * s, ty + (b - lo[1]) * s),
         "우측면도": lambda a, b: (rx + (a - lo[1]) * s, fy + (b - lo[2]) * s)}
    views = {"정면도": dieview.FRONT, "평면도": dieview.TOP, "우측면도": dieview.RIGHT}
    for nm, (v, up) in views.items():
        vis, hid = dieview.hlr(shapes, view=v, hidden=hidden, up=up)
        for P in hid:
            sh.poly([T[nm](*q) for q in P], False, "HIDDEN", 0.18)
        for P in vis:
            sh.poly([T[nm](*q) for q in P], False, "OUTLINE", 0.35)
        if work:
            for P3, tag in work:
                Q = [dieview.project_point(q, v, up) for q in P3]
                sh.poly([T[nm](*q) for q in Q], False, "PART" if tag == "before" else "PART2", 0.5 if tag == "before" else 0.3)
    sh.text(fx, fy + H * s + 5, "정면도", 3.0, "L", bold=True)
    sh.text(fx, ty + Wd * s + 5, "평면도", 3.0, "L", bold=True)
    sh.text(rx, fy + H * s + 5, "우측면도", 3.0, "L", bold=True)
    if dims:
        sh.dim_h(T["정면도"](lo[0], 0)[0], T["정면도"](hi[0], 0)[0], fy, fy - 10, _num(L, 1))
        sh.dim_v(T["정면도"](0, lo[2])[1], T["정면도"](0, hi[2])[1], fx, fx - 10, _num(H, 1))
        sh.dim_v(T["평면도"](0, lo[1])[1], T["평면도"](0, hi[1])[1], fx, fx - 10, _num(Wd, 1))
        sh.dim_h(T["우측면도"](lo[1], 0)[0], T["우측면도"](hi[1], 0)[0], fy, fy - 10, _num(Wd, 1))
    return s, T, (lo, hi)


def ortho_sheet(assy: d3.DieAssy, info, number, cache):
    """금형 3면도: 평면도 · 정면도 · 우측면도 (열린 상태, 숨은선, 금형 안 제품) + 닫힌 높이 · 열린 높이."""
    sh = Sheet("금형 3면도 (평면 · 정면 · 우측면)", number, A3, material="-", qty=1,
               weight=sum(p.weight * p.qty for p in assy.parts))
    W, H = sh.size
    sol = [s_ for _, _, s_ in _solids(assy, cache)]
    y0 = MARGIN + TB_H + 6
    s, T, (lo, hi) = _views3(sh, sol, MARGIN + 6, y0, W - 2 * MARGIN - 12, H - MARGIN - 8 - y0,
                             work=getattr(assy, "work", None))
    xr = T["우측면도"](hi[1], 0)[0] + 10
    zs = T["우측면도"](0, assy.shut)[1]
    sh.line(xr - 8, zs, xr + 4, zs, "DIM", 0.18)
    sh.text(xr + 5, zs - 1.0, f"닫힌 높이 {assy.shut:.1f} (하사점)", 2.2, "L", "DIM")
    zo = T["우측면도"](0, hi[2])[1]
    sh.text(xr + 5, zo + (3.0 if abs(zo - zs) < 5 else -1.0), f"열린 높이 {assy.open_h:.1f}", 2.2, "L", "DIM")
    sh.text(MARGIN + 16, H - MARGIN - 6, "3각법 · 열린 상태 · 숨은선 = 파선"
            + (" · 제품: 자주 굵은 선 = 공정 전, 가상선 = 하사점" if getattr(assy, "work", None) else ""), 2.4, "L")
    return sh


def product_views_sheet(assy, info, number):
    """제품 3면도: 3D 모델의 평면도 · 정면도 · 우측면도 (숨은선) + 바깥 치수."""
    solid = info.get("solid")
    sh = Sheet("제품 3면도 (평면 · 정면 · 우측면)", number, A3, material=info.get("material", ""), qty=1,
               weight=float(assy.usage.get("part_kg", 0.0)) if assy.usage else 0.0)
    W, H = sh.size
    y0 = MARGIN + TB_H + 6
    _views3(sh, [solid], MARGIN + 6, y0, W - 2 * MARGIN - 12, H - MARGIN - 8 - y0)
    sh.text(MARGIN + 16, H - MARGIN - 6, f"{info.get('product', '')} · {info.get('material', '')} — 3각법 · 숨은선 = 파선 · "
            "치수 = 바깥 크기 (전개 치수는 제품도 · 전개도 장)", 2.4, "L")
    return sh


# ---------------------------------------------------------------- 묶음 · 출력



def build(assy: d3.DieAssy, info=None):
    """도면집 Sheet 목록 [표지, 조립도 (옆에 제품도), 스트립 배치도, 제품도, 부품도 (옆에 입체도) …].
    info: product · material · prefix · designer · solid (제품 3D) · result (전개 결과)."""
    info = dict(info or {})
    info.setdefault("die", assy.kind)
    pre = info.get("prefix") or "HD-" + _dt.date.today().strftime("%y%m%d")
    parts = [p for p in assy.parts if not p.std and p.prims and p.prims[0].kind in (d3.BOX, d3.PRISM, d3.PROF)]
    strip = any(p.name == "다이 플레이트" for p in assy.parts) and assy.strip[0] > 0
    product = info.get("product_sheet", True)
    index = [(f"{pre}-00", "표지 · 사양 · 점검"), (f"{pre}-01", "금형 조립도 (제품도 옆)")]
    if strip:
        index.append((f"{pre}-02", "스트립 배치도"))
    if product:
        index.append((f"{pre}-03", "제품도 · 전개도"))
    if product and info.get("solid") is not None:
        index.append((f"{pre}-06", "제품 3면도"))
    index += [(f"{pre}-07", "금형 3면도 (평면 · 정면 · 우측면)"), (f"{pre}-04", "입체 조립도 · 분해도"),
              (f"{pre}-05", "단면도 A-A")]
    index += [(f"{pre}-{p.no + 10:02d}", f"{p.no:02d} {p.name} (입체도 옆)") for p in parts]
    num = {nm: nb for nb, nm in index}
    cache = {}
    sheets = [cover_sheet(assy, info, index[0][0], index), assembly_sheet(assy, info, index[1][0])]
    if strip:
        sheets.append(strip_sheet(assy, info, num["스트립 배치도"]))
    if product:
        sheets.append(product_sheet(assy, info, num["제품도 · 전개도"]))
    if "제품 3면도" in num:
        try:
            sheets.append(product_views_sheet(assy, info, num["제품 3면도"]))
        except Exception:  # noqa: BLE001
            index = [q for q in index if q[1] != "제품 3면도"]
    for fn, nm in ((ortho_sheet, "금형 3면도 (평면 · 정면 · 우측면)"), (iso3d_sheet, "입체 조립도 · 분해도"),
                   (section_sheet, "단면도 A-A")):
        ix = [k for k, (_, n_) in enumerate(index) if n_ == nm][0]
        try:
            kw = {"y_cut": info["y_cut"]} if fn is section_sheet and "y_cut" in info else {}
            sheets.append(fn(assy, info, index[ix][0], cache, **kw))
        except Exception:  # noqa: BLE001 — 3D 도면은 덤 (목록에서 빼고 계속)
            index[ix] = (index[ix][0], index[ix][1] + " (못 만듦)")
    sheets += [part_sheet(p, assy, info, f"{pre}-{p.no + 10:02d}") for p in parts]
    for i, sh in enumerate(sheets, 1):
        _frame(sh, info, i, len(sheets))
    return sheets


def save_dxf(sheets, path):
    """도면집 DXF: 시트를 옆으로 (A3 틀 1:1 종이 크기, 그림은 시트 척도)."""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for nm, col in LAYERS.items():
        attrs = {"color": col}
        if nm in LTYPE:
            attrs["linetype"] = LTYPE[nm]
        doc.layers.add(nm, **attrs)
    doc.styles.add("KOR", font="malgun.ttf")
    msp = doc.modelspace()
    ox = 0.0
    for sh in sheets:
        for e in sh.ents:
            kind = e[0]
            if kind == "line":
                _, x1, y1, x2, y2, lay, w = e
                msp.add_line((ox + x1, y1), (ox + x2, y2), dxfattribs={"layer": lay, "lineweight": int(w * 100)})
            elif kind == "poly":
                _, P, closed, lay, w = e
                msp.add_lwpolyline([(ox + x, y) for x, y in P], close=closed,
                                   dxfattribs={"layer": lay, "lineweight": int(w * 100)})
            elif kind == "circle":
                _, x, y, r, lay, w = e
                msp.add_circle((ox + x, y), r, dxfattribs={"layer": lay, "lineweight": int(w * 100)})
            else:
                _, x, y, s_, h, align, lay, bold = e
                if not s_:
                    continue
                t = msp.add_text(s_, height=h * 0.85, dxfattribs={"layer": lay, "style": "KOR"})
                from ezdxf.enums import TextEntityAlignment as A
                al = {"L": A.BOTTOM_LEFT, "C": A.BOTTOM_CENTER, "R": A.BOTTOM_RIGHT, "VR": A.MIDDLE_RIGHT}[align]
                t.set_placement((ox + x, y), align=al)
        ox += sh.size[0] + 30
    doc.saveas(path)
    return path


def paint(p, sheet: Sheet, k, page_h):
    """QPainter (종이 mm × k = 장치 단위), y 뒤집음."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen, QPolygonF
    col = {"OUTLINE": QColor(0, 0, 0), "HIDDEN": QColor(60, 60, 60), "CENTER": QColor(180, 0, 0),
           "DIM": QColor(0, 110, 0), "TEXT": QColor(0, 0, 0), "FRAME": QColor(0, 0, 0), "THIN": QColor(90, 90, 90),
           "WIRE": QColor(200, 0, 0), "HATCH": QColor(120, 120, 120), "PART": QColor(190, 0, 160),
           "PART2": QColor(190, 0, 160)}

    def pt(x, y):
        return QPointF(x * k, (page_h - y) * k)

    def pen(lay, w):
        pn = QPen(col.get(lay, QColor(0, 0, 0)), max(w, 0.13) * k)
        if lay == "HIDDEN":
            pn.setStyle(Qt.DashLine)
        elif lay == "CENTER":
            pn.setStyle(Qt.DashDotLine)
        elif lay == "PART2":
            pn.setStyle(Qt.DashDotDotLine)
        return pn
    p.setBrush(Qt.NoBrush)
    f = QFont()
    for e in sheet.ents:
        kind = e[0]
        if kind == "line":
            _, x1, y1, x2, y2, lay, w = e
            p.setPen(pen(lay, w))
            p.drawLine(pt(x1, y1), pt(x2, y2))
        elif kind == "poly":
            _, P, closed, lay, w = e
            p.setPen(pen(lay, w))
            poly = QPolygonF([pt(x, y) for x, y in P])
            if closed:
                p.drawPolygon(poly)
            else:
                p.drawPolyline(poly)
        elif kind == "circle":
            _, x, y, r, lay, w = e
            p.setPen(pen(lay, w))
            p.drawEllipse(pt(x, y), r * k, r * k)
        else:
            _, x, y, s_, h, align, lay, bold = e
            if not s_:
                continue
            f.setPixelSize(max(int(h * k), 4))
            f.setBold(bold)
            p.setFont(f)
            p.setPen(col.get(lay, QColor(0, 0, 0)))
            wbox = 400 * k
            if align == "L":
                r = QRectF(x * k, (page_h - y) * k - h * 1.3 * k, wbox, h * 1.4 * k)
                p.drawText(r, Qt.AlignLeft | Qt.AlignBottom, s_)
            elif align == "C":
                r = QRectF(x * k - wbox / 2, (page_h - y) * k - h * 1.3 * k, wbox, h * 1.4 * k)
                p.drawText(r, Qt.AlignHCenter | Qt.AlignBottom, s_)
            elif align == "R":
                r = QRectF(x * k - wbox, (page_h - y) * k - h * 1.3 * k, wbox, h * 1.4 * k)
                p.drawText(r, Qt.AlignRight | Qt.AlignBottom, s_)
            else:   # VR: 세로 가운데, 오른쪽 맞춤
                r = QRectF(x * k - wbox, (page_h - y) * k - h * 0.7 * k, wbox, h * 1.4 * k)
                p.drawText(r, Qt.AlignRight | Qt.AlignVCenter, s_)


def save_pdf(sheets, path, title="금형 도면집"):
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

    from .report import ensure_gui, version_text
    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A3), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(title)
    pdf.setCreator(f"한일 판금 전개 {version_text()}")
    k = 300 / 25.4
    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    for i, sh in enumerate(sheets):
        if i:
            pdf.newPage()
        paint(p, sh, k, sh.size[1])
    p.end()
    return path


def render(sheet: Sheet, w=1680):
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    k = w / sheet.size[0]
    img = QImage(int(w), int(sheet.size[1] * k), QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint(p, sheet, k, sheet.size[1])
    p.end()
    return img
