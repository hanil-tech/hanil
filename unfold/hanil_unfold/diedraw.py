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
LAYERS = {"OUTLINE": 7, "HIDDEN": 8, "CENTER": 1, "DIM": 3, "TEXT": 7, "FRAME": 7, "THIN": 9, "WIRE": 1, "HATCH": 8}
LTYPE = {"HIDDEN": "DASHED", "CENTER": "CENTER"}


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
    if pr.kind == d3.BOX:
        x0, y0, z0, dx, dy, dz = pr.p
        return x0, y0, dx, dy, z0, dz
    if pr.kind == d3.PRISM:
        P = np.asarray(pr.poly, float)
        x0, y0 = P.min(0)
        dx, dy = np.ptp(P, 0)
        return x0, y0, dx, dy, pr.p[0], pr.p[1]
    x, y, z0, r, h = pr.p
    return x - r, y - r, 2 * r, 2 * r, z0, h


NOTES_BASE = ["일반 공차 ISO 2768-m (지시 없는 치수)", "모서리 C0.5 (날 끝은 날카롭게)",
              "탭 JIS B 0205 (보통 나사), 리머 구멍 H7", "구멍 좌표는 원점 (왼쪽 아래 귀, ⊕) 에서"]


def part_sheet(part: d3.DiePart, assy: d3.DieAssy, info, number):
    pr = part.prims[0]
    x0, y0, dx, dy, z0, dz = _part_extent(pr)
    sh = Sheet(f"{part.name}", number, A3, material=part.material.split(" HRC")[0].split(" (")[0],
               heat=_heat(part.material), qty=part.qty, weight=part.weight)
    W, H = sh.size
    # 그림 자리: 왼쪽 (표제란 위), 오른쪽 구멍표
    area_x, area_y = MARGIN + 12, MARGIN + TB_H + 16
    area_w, area_h = W * 0.58, H - area_y - MARGIN - 14
    s, sh.scale = _pick_scale(dx, dy + dz + 30 / 1.0, area_w, area_h - 24)
    # 평면도 (위) · 정면도 (아래, 3각법)
    fx = area_x + 10
    fy_front = area_y + 6
    fy_top = fy_front + dz * s + 22

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
        sh.poly([T(*q) for q in P], True, lay, 0.35 if lay == "WIRE" else 0.25)
    # 날 (와이어 프로파일) 기호 W1 … — 관통 날만, 크기는 다이 날 치수표에서
    wires = []
    for c in pr.cuts:
        if len(c) > 2 and c[1]:
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
    sh.dim_v(F(0, z0)[1], F(0, z0 + dz)[1], F(x0 + dx, 0)[0], F(x0 + dx, 0)[0] + 12, _num(dz))
    sh.text(fx, fy_top + dy * s + 16, "평면도", 3.0, "L", bold=True)
    sh.text(fx, fy_front + dz * s + 4, "정면도", 3.0, "L", bold=True)
    # 구멍 좌표표
    tx = MARGIN + W * 0.62
    ty = H - MARGIN - 10
    cols = [10, 8, 20, 20, 78]
    _table(sh, tx, ty, cols, ["기호", "번호", "X", "Y", "가공"],
           [[sym if i == 1 else "", i, f"{hx - x0:.2f}", f"{hy - y0:.2f}",
             (spec + (f" ({h.side})" if h.side != "윗면" else "")) if i == 1 else ""]
            for sym, kind, cnt, pts, spec in tab for i, (hx, hy, h) in enumerate(pts, 1)]
           + [[f"W{i}", "", f"{np.mean(P[:, 0]) - x0:.2f}", f"{np.mean(P[:, 1]) - y0:.2f}",
                "와이어 날 " + (f"Ø{d3._circle_d(P)[0]:.3f}" if d3._is_round(P)
                               else f"{np.ptp(P[:, 0]):.3f} × {np.ptp(P[:, 1]):.3f}") + " (가운데 좌표)"]
              for i, P in enumerate(wires, 1)],
           max_rows=int((H - MARGIN - TB_H - 70) / 4.2))
    # 주기
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
    sh.text(tx, ny + 4, "주기", 3.0, "L", bold=True)
    for k, n in enumerate(notes, 1):
        sh.text(tx, ny - 4.5 * (k - 1), f"{k}. {n}", 2.2)
    return sh


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
            pr = max(part.prims, key=lambda q: (q.p[0] + q.p[3]) if q.kind in (d3.BOX, d3.CYL) else q.poly[:, 0].max())
            if pr.kind == d3.BOX:
                at = F(pr.p[0] + pr.p[3], pr.p[2] + pr.p[5] / 2)
            elif pr.kind == d3.CYL:
                at = F(pr.p[0] + pr.p[3], pr.p[2] + pr.p[4] / 2)
            else:
                at = F(pr.poly[:, 0].max(), pr.p[0] + pr.p[1] / 2)
            balloons.append((part.no, at))
    # 풍선 (정면도 오른쪽 세로 줄, 위에서부터)
    bx = F(assy.L / 2, 0)[0] + 14
    balloons.sort(key=lambda b: -b[1][1])
    top, bot = F(0, zmax)[1] + 4, F(0, 0)[1]
    step = (top - bot) / max(len(balloons) - 1, 1)
    for k, (no, at) in enumerate(balloons):
        by_ = top - k * step
        bxx = bx + (k % 2) * 7
        sh.line(at[0], at[1], bxx - 2.6, by_, "THIN", 0.18)
        sh.circle(bxx, by_, 2.6, "OUTLINE", 0.25)
        sh.text(bxx, by_ - 0.9, str(no), 2.0, "C")
    # 높이 치수
    xl = F(-assy.L / 2, 0)[0]
    sh.dim_v(F(0, 0)[1], F(0, zmax)[1], xl, xl - 8, f"열림 {zmax:.1f}")
    sh.line(xl - 12, F(0, assy.shut)[1], xl, F(0, assy.shut)[1], "DIM", 0.18)
    sh.text(xl - 12, F(0, assy.shut)[1] + 0.8, f"닫힌 높이 {assy.shut:.1f} (하사점, 상형 세트 윗면)", 2.0, "L", "DIM")
    sh.dim_h(T(-assy.L / 2, 0)[0], T(assy.L / 2, 0)[0], T(0, assy.W / 2)[1], T(0, assy.W / 2)[1] + 6, f"{assy.L:g}")
    sh.text(tx0, ty0 + assy.W * s + 10, "평면도 (하형, 펀치는 숨은선)", 2.8, "L", bold=True)
    sh.text(fx0, F(0, zmax)[1] + 3, "정면도 (열린 상태)", 2.8, "L", bold=True)
    # 부품표 (표제란 위, 오른쪽)
    x = W - MARGIN - 190
    rows = [[p.no, p.name, p.qty, p.material.split(" HRC")[0], p.size, "표준" if p.std else "가공"]
            for p in assy.parts]
    cols = [8, 52, 8, 34, 66, 12]
    ytop = H - MARGIN - 6
    _table(sh, x + 2, ytop, cols, ["번호", "품명", "수량", "재질", "크기 · 규격", "구분"], rows, h=3.9,
           max_rows=int((ytop - MARGIN - TB_H - 10) / 3.9) - 1)
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
    for k_, ln in enumerate(d3.press_lines(assy)):
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


# ---------------------------------------------------------------- 묶음 · 출력

DRAWN = set(d3.PLATES) | {"블랭킹 펀치", "이형 피어싱 펀치", "스트립 가이드", "스톱 블록"}


def build(assy: d3.DieAssy, info=None):
    """도면집 Sheet 목록 [표지, 조립도, 스트립 배치도, 부품도 …]."""
    info = dict(info or {})
    info.setdefault("die", assy.kind)
    pre = info.get("prefix") or "HD-" + _dt.date.today().strftime("%y%m%d")
    parts = [p for p in assy.parts if p.name in DRAWN and p.prims and p.prims[0].kind in (d3.BOX, d3.PRISM)]
    index = [(f"{pre}-00", "표지 · 사양 · 점검"), (f"{pre}-01", "금형 조립도"), (f"{pre}-02", "스트립 배치도")]
    index += [(f"{pre}-{p.no + 10:02d}", f"{p.no:02d} {p.name}") for p in parts]
    sheets = [cover_sheet(assy, info, index[0][0], index), assembly_sheet(assy, info, index[1][0]),
              strip_sheet(assy, info, index[2][0])]
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
           "WIRE": QColor(200, 0, 0), "HATCH": QColor(120, 120, 120)}

    def pt(x, y):
        return QPointF(x * k, (page_h - y) * k)

    def pen(lay, w):
        pn = QPen(col.get(lay, QColor(0, 0, 0)), max(w, 0.13) * k)
        if lay == "HIDDEN":
            pn.setStyle(Qt.DashLine)
        elif lay == "CENTER":
            pn.setStyle(Qt.DashDotLine)
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
