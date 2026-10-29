"""금형 공정도 (초안).

판금 부품: 순차(프로그레시브) 금형 스트립 공정도
  피어싱(제품 구멍 + 파일럿) → 노칭(외곽, 캐리어 연결부만 남김) → [빈 공정] → 절곡(바깥 플랜지부터,
  100° 넘는 절곡·헤밍은 예비 굽힘 + 마무리 두 공정) → 분리(컷오프).
  공정마다 위에서 본 부품 모양: 구멍, 외곽, 접힌 플랜지는 위에서 본 길이(× cos 각도)로 줄여 그린다.
드로잉 성형품: 블랭킹 → 드로잉 1 … n → 트림 → 피어싱 (단면 그림, 단마다 높이는 넓이가 같다고 계산).

금형 설계자가 다듬을 출발점이다. 하중은 diecalc 와 같은 식.
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc

PIERCE, NOTCH, IDLE, BEND, CUTOFF = "피어싱", "노칭", "빈 공정", "절곡", "분리"
BLANK, DRAW, TRIM = "블랭킹", "드로잉", "트림"


@dataclass
class Station:
    no: int
    kind: str
    title: str
    detail: str
    force_n: float = 0.0
    bends: list = field(default_factory=list)     # [(번호, 이 공정까지 접은 각도)]
    holes: list = field(default_factory=list)     # 이 공정에서 뚫는 구멍 (plan.holes 의 번호)
    rules: list = field(default_factory=list)     # 근거 규칙 (procplan.RULES)


@dataclass
class FoldLine:
    number: int
    a: np.ndarray        # 선 위 한 점 (돌린 좌표)
    n: np.ndarray        # 플랜지 쪽 단위 법선
    angle: float         # 최종 각도
    half: float          # 절곡부 폭의 반 (BA/2)
    order: int           # 바깥(1) → 안쪽
    size: float = 0.0    # 플랜지 쪽 넓이 (격자 칸 수)
    up: bool = True      # UP (전개도를 보는 쪽으로 세움)


@dataclass
class ProcessPlan:
    kind: str                     # "progressive" / "draw"
    stations: list
    thickness: float
    material: str
    notes: list = field(default_factory=list)
    # 순차 금형
    polys: list = field(default_factory=list)      # 돌린 절단선 (외곽 + 구멍)
    outer: np.ndarray | None = None
    holes: list = field(default_factory=list)
    folds: list = field(default_factory=list)
    pitch: float = 0.0
    tab: tuple = (0.0, 0.0, 0.0)                    # (가운데 x, 폭, 길이)
    carrier: float = 0.0                            # 캐리어 폭
    pilot_d: float = 0.0
    side: float = 0.0
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)
    part_area: float = 0.0
    # 드로잉
    draw: object = None
    cup_r: float = 0.0
    final_h: float = 0.0

    @property
    def strip_width(self):
        x0, y0, x1, y1 = self.bbox
        return (y1 - y0) + self.tab[2] + self.carrier + self.side

    @property
    def utilization(self):
        return self.part_area / (self.pitch * self.strip_width) if self.pitch else 0.0

    @property
    def total_force(self):
        return sum(s.force_n for s in self.stations)

    @property
    def press_tonf(self):
        return self.total_force * 1.3 / dc.TON


# ---------------------------------------------------------------- 순차 금형

def _area(P):
    P = np.asarray(P, float)
    x, y = P[:, 0], P[:, 1]
    return abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2


def _rot(P, ang):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    P = np.asarray(P, float)
    return P @ np.array([[c, s], [-s, c]])


def _inside_points(part, angle, res):
    from .nesting import _rasterize
    m, (ox, oy) = _rasterize(part, angle, res, conservative=False)
    iy, ix = np.nonzero(m)
    return np.column_stack([ox + (ix + 0.5) * res, oy + (iy + 0.5) * res])


def _folds(result, angle, pts):
    """절곡선을 돌린 좌표로. 플랜지 = 선으로 나눈 두 쪽 중 넓이가 작은 쪽."""
    out = []
    for b in result.bends:
        a, c = _rot(np.array(b.line, float), angle)
        d = c - a
        L = float(np.linalg.norm(d)) or 1.0
        n = np.array([-d[1], d[0]]) / L
        side = (pts - a) @ n
        if (side > 0).sum() > (side < 0).sum():
            n = -n
        out.append(FoldLine(b.number, a, n, float(b.angle_deg), b.allowance / 2, 0, up=b.direction == "UP"))
    # 바깥 플랜지부터: 플랜지 쪽 넓이가 작은 순서
    for f in out:
        f.size = float(((pts - f.a) @ f.n > 0).sum())
    for rank, i in enumerate(np.argsort([f.size for f in out], kind="stable"), 1):
        out[i].order = rank
    return out


def fold_points(P, folds, done):
    """위에서 본 모양: 접은 플랜지 쪽 점을 선 쪽으로 cos(각도) 만큼 당긴다. done: {번호: 각도}."""
    P = np.array(P, float)
    for f in sorted(folds, key=lambda f: f.order):
        ang = done.get(f.number)
        if not ang:
            continue
        d = (P - f.a) @ f.n - f.half
        sel = d > 0
        P[sel] -= np.outer(d[sel] * (1 - math.cos(math.radians(min(ang, 180)))), f.n)
    return P


def progressive(result, settings: bc.BendSettings, idle=False):
    from .nesting import NestPart
    t = result.thickness
    mat = settings.mat
    tau = dc.shear_strength(mat)
    part = NestPart.from_result("p", result)
    if part.outer is None:
        raise ValueError("외곽이 닫혀 있지 않아 공정도를 그릴 수 없습니다.")
    w, h = result.size
    res = max(max(w, h) / 300.0, 0.1)
    notes = []

    # 방향: 절곡선이 이송 방향(X)과 나란하도록, 그리고 아래 변(캐리어 쪽)에 플랜지가 없도록
    if result.bends:
        angs = [math.degrees(math.atan2(b.line[1][1] - b.line[0][1], b.line[1][0] - b.line[0][0])) % 180
                for b in result.bends]
        # 가장 많은 절곡선 방향 (같으면 먼저 나온 것). 가운데값을 쓰면 0°·90° 가 섞인 부품이 45° 로 돌아간다.
        rounded = [round(a) % 180 for a in angs]
        base = float(max(dict.fromkeys(rounded), key=rounded.count))
    else:
        base = dc.strip_layout(result, part).angle
    best = None
    for k in range(4):
        ang = base + 90 * k
        pts = _inside_points(part, ang, res)
        folds = _folds(result, ang, pts)
        O = _rot(part.outer, ang)
        y0 = O[:, 1].min()
        # 변을 촘촘히 나눠 아래 변 위의 점을 고르게 (꼭짓점만 보면 가운데가 빠진다)
        Oc = np.vstack([O, O[:1]])
        dense = [O[:1]]
        for a_, b_ in zip(Oc[:-1], Oc[1:]):
            k_ = max(1, int(np.linalg.norm(b_ - a_) / res))
            dense.append(a_ + np.outer(np.arange(1, k_ + 1) / k_, b_ - a_))
        Od = np.vstack(dense)
        bottom = Od[Od[:, 1] < y0 + max(0.5, 0.2 * t)]
        free = bottom[np.all([((bottom - f.a) @ f.n) <= 0 for f in folds], axis=0)] if folds else bottom
        span = float(np.ptp(free[:, 0])) if len(free) > 1 else 0.0
        score = (span < 2 * t, -span)
        if best is None or score < best[0]:
            best = (score, ang, folds, O, free if len(free) > 1 else bottom)
    (score, ang, folds, O, contact) = best
    if score[0]:
        notes.append("모든 변에 플랜지가 있어 캐리어 연결부가 플랜지에 붙습니다 — 센터 캐리어나 "
                     "연결부를 절곡 전에 자르는 방식을 검토하세요.")
    polys = [_rot(c, ang) for c in part.cut]
    holes = [_rot(hh, ang) for hh in part.holes]
    P = np.vstack(polys)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    tab_w = min(max(4 * t, 6.0), max(float(np.ptp(contact[:, 0])) * 0.8, 2 * t))
    tab_x = float(contact[:, 0].mean())
    tab_len = max(3 * t, 5.0)
    pilot_d = math.ceil(max(4.0, 2 * t) * 2) / 2
    carrier = pilot_d + 2 * max(3.0, 2 * t)
    side = max(2 * t, 1.5)
    bridge = max(1.5 * t, 1.0)
    # 피치: 이웃과 닿지 않게 (접기 전 외곽 기준)
    pitch = (x1 - x0) + max(bridge, 2 * t)
    pitch = math.ceil(pitch * 2) / 2

    # 공정
    from . import procplan
    feat = procplan.features(result, settings)
    info = {h.index: h for h in feat.holes}
    st = []
    pilot_len = math.pi * pilot_d

    def hlen(ids):
        return sum(dc._perimeter(holes[i]) for i in ids)

    pre = [i for i in range(len(holes)) if not info[i].after_bend]
    groups = sorted({info[i].group for i in pre}) or [0]
    for g in groups:
        ids = [i for i in pre if info[i].group == g]
        names = ", ".join(info[i].label for i in ids)
        if g == 0:
            st.append(Station(0, PIERCE, "피어싱" if len(groups) == 1 else "피어싱 1",
                              f"파일럿 Ø{pilot_d:g}" + (f" + {names}" if names else ""),
                              (hlen(ids) + pilot_len) * t * tau, holes=ids, rules=["R1", "R2"]))
        else:
            st.append(Station(0, PIERCE, f"피어싱 {g + 1}", f"{names} (가까운 구멍 나눔)",
                              hlen(ids) * t * tau, holes=ids, rules=["R5"]))
    outer_len = dc._perimeter(O) - tab_w
    st.append(Station(0, NOTCH, "노칭 (외곽)", f"외곽 {outer_len:,.0f} mm 따내기, 연결부 {tab_w:.1f} 남김",
                      outer_len * t * tau, rules=["R6"]))
    if idle:
        st.append(Station(0, IDLE, "빈 공정", "금형 강도 · 다음 공정 여유"))
    v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)
    bmap = {b.number: b for b in result.bends}
    done = {}
    # 작은(바깥) 플랜지부터. 크기가 15 % 안으로 같은 플랜지는 한 공정에 (예: ㄷ 자 양쪽)
    batches = []
    for f in sorted(folds, key=lambda f: f.order):
        if batches and abs(f.size - batches[-1][0].size) <= 0.15 * max(f.size, batches[-1][0].size):
            batches[-1].append(f)
        else:
            batches.append([f])
    for grp in batches:
        big = [f for f in grp if f.angle > 100]
        if big:
            for f in big:
                done[f.number] = f.angle / 2
            st.append(Station(0, BEND, "예비 굽힘",
                              " · ".join(f"B{f.number} {f.angle / 2:.0f}°" for f in big),
                              sum(dc.bend_force(mat, bmap[f.number].length, t, v) for f in big),
                              [(f.number, done[f.number]) for f in grp if f.number in done], rules=["R8"]))
        for f in grp:
            done[f.number] = f.angle
        f_n = sum(dc.bend_force(mat, bmap[f.number].length, t, v, settings.process) for f in grp)
        st.append(Station(0, BEND, "절곡",
                          " · ".join(f"B{f.number} {f.angle:.0f}° {'UP' if bmap[f.number].direction == 'UP' else 'DOWN'}"
                                     for f in grp), f_n, [(f.number, f.angle) for f in grp], rules=["R7"]))
    post = [i for i in range(len(holes)) if info[i].after_bend]
    flat = [i for i in post if not info[i].cam]
    cam = [i for i in post if info[i].cam]
    if flat:
        st.append(Station(0, PIERCE, "후 피어싱", ", ".join(info[i].label for i in flat) + " (절곡선 가까움)",
                          hlen(flat) * t * tau, holes=flat, rules=["R3"]))
    if cam:
        st.append(Station(0, PIERCE, "캠 피어싱",
                          procplan.pair_names([info[i] for i in cam]),
                          hlen(cam) * t * tau, holes=cam, rules=sorted({info[i].reason for i in cam})))
    st.append(Station(0, CUTOFF, "분리 (컷오프)", f"연결부 {tab_w:.1f} × {t:g} 자르기", tab_w * t * tau,
                      rules=["R6"]))
    for i, s in enumerate(st, 1):
        s.no = i
    if any(f.angle > 150 for f in folds):
        notes.append("헤밍(150° 넘음): 예비 굽힘 뒤 눌러 접기 공정이 필요합니다.")
    plan = ProcessPlan("progressive", st, t, mat.code, notes, polys, O, holes, folds, pitch,
                       (tab_x, tab_w, tab_len), carrier, pilot_d, side, (x0, y0, x1, y1),
                       _area(O) - sum(_area(hh) for hh in holes))
    return plan


def section(plan, done):
    """절곡선이 모두 나란하면 옆에서 본 단면 (두께 가운데 선의 점들, 캐리어 쪽 판이 바닥), 아니면 None.
    모서리는 R 없이 꺾고 길이는 전개도의 절곡선 사이 거리 (공정 그림용 근사)."""
    if not plan.folds:
        return None
    u = plan.folds[0].n
    if any(abs(u[0] * f.n[1] - u[1] * f.n[0]) > 0.02 for f in plan.folds):
        return None
    proj = plan.outer @ u
    s0, s1 = float(proj.min()), float(proj.max())
    cuts = sorted((float(f.a @ u), f) for f in plan.folds)
    tab_s = float(np.array([plan.tab[0], plan.bbox[1]]) @ u)
    pos = [s0] + [c for c, _ in cuts] + [s1]
    k = int(np.clip(np.searchsorted(pos, tab_s) - 1, 0, len(cuts)))    # 바닥 판 번호
    a, b = pos[k], pos[k + 1]
    right = [(b - a) / 2, 0.0]
    pts_r = [np.array([-(b - a) / 2, 0.0]), np.array([(b - a) / 2, 0.0])]
    h = 0.0
    for i in range(k, len(cuts)):
        _, f = cuts[i]
        ang = math.radians(done.get(f.number, 0.0)) * (1 if f.up else -1)
        h += ang
        L = pos[i + 2] - pos[i + 1]
        pts_r.append(pts_r[-1] + L * np.array([math.cos(h), math.sin(h)]))
    pts_l = []
    h = math.pi
    cur = np.array([-(b - a) / 2, 0.0])
    for i in range(k - 1, -1, -1):
        _, f = cuts[i]
        ang = math.radians(done.get(f.number, 0.0)) * (1 if f.up else -1)
        h -= ang
        L = pos[i + 1] - pos[i]
        cur = cur + L * np.array([math.cos(h), math.sin(h)])
        pts_l.append(cur)
    del right
    return np.array(pts_l[::-1] + pts_r)


# ---------------------------------------------------------------- 드로잉

def drawing(result, settings: bc.BendSettings, draw_plan, r=None, final_h=None):
    t = result.thickness
    mat = settings.mat
    tau = dc.shear_strength(mat)
    st = [Station(1, BLANK, "블랭킹", f"원판 Ø{draw_plan.D:.1f}", math.pi * draw_plan.D * t * tau)]
    for s in draw_plan.stages:
        st.append(Station(len(st) + 1, DRAW, f"드로잉 {s.no}" if s.no == 1 else f"재드로잉 {s.no - 1}",
                          f"Ø{s.d:.1f}  (m = {s.m:.3f})", s.force_n))
    st.append(Station(len(st) + 1, TRIM, "트림", f"위 끝 {draw_plan.trim:.1f} 다듬기",
                      math.pi * draw_plan.stages[-1].d * t * tau))
    holes = 0
    try:
        from .nesting import NestPart
        holes = len(NestPart.from_result("p", result).holes)
    except ValueError:
        pass
    if holes:
        st.append(Station(len(st) + 1, PIERCE, "피어싱", f"구멍 {holes}개", 0.0))
    notes = []
    if draw_plan.holder_needed.startswith("필요"):
        notes.append(f"주름 누르개 필요 — 누르개 힘 약 {draw_plan.holder_n / 1000:,.0f} kN")
    notes += draw_plan.notes
    return ProcessPlan("draw", st, t, mat.code, notes, draw=draw_plan,
                       cup_r=r if r is not None else max(4 * t, 1.0), final_h=final_h or 0.0)


def cup_height(D, d, r):
    """블랭크 Ø D 를 지름 d, 바닥 R r 컵으로 당겼을 때 높이 (넓이 같음)."""
    A = math.pi * D * D / 4
    R = d / 2
    r = min(r, R)
    base = math.pi * (R - r) ** 2 + (math.pi * r / 2) * 2 * math.pi * (R - r + 2 * r / math.pi)
    return r + max(A - base, 0) / (math.pi * d)


# ---------------------------------------------------------------- 그리기

def paint(p, rect, plan, font_px=14.0):
    """rect(QRectF) 안에 공정도. 순차 금형은 스트립 평면도, 드로잉은 단면."""
    if plan.kind == "draw":
        return _paint_draw(p, rect, plan, font_px)
    return _paint_strip(p, rect, plan, font_px)


def _paint_strip(p, rect, plan, fp):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen, QPolygonF

    x0, y0, x1, y1 = plan.bbox
    n = len(plan.stations)
    # 단면 (나란한 절곡만): 아래 칸
    secs, d_ = [], {}
    for s_ in plan.stations:
        for num, ang in s_.bends:
            d_[num] = ang
        secs.append(section(plan, dict(d_)) if s_.kind != CUTOFF else None)
    if any(x is not None for x in secs):
        sec_h = rect.height() * 0.38
        sec_rect = QRectF(rect.left(), rect.bottom() - sec_h, rect.width(), sec_h)
        rect = QRectF(rect.left(), rect.top(), rect.width(), rect.height() - sec_h)
    else:
        sec_rect = None
    tab_x, tab_w, tab_len = plan.tab
    yc0 = y0 - tab_len - plan.carrier          # 스트립 아래 끝
    yc1 = y0 - tab_len                          # 캐리어 위 끝
    ytop = y1 + plan.side
    cx0 = x0 + (x1 - x0) / 2                    # 첫 공정의 부품 가운데
    left = cx0 - plan.pitch * 1.0
    right = cx0 + plan.pitch * (n - 0.5) + plan.pitch * 0.6
    head = fp * 3.2
    sc = min(rect.width() / (right - left), (rect.height() - head - fp * 1.5) / (ytop - yc0))
    ox = rect.left() + (rect.width() - (right - left) * sc) / 2 - left * sc
    oy = rect.top() + head + (ytop - yc0) * sc

    def pt(x, y):
        return QPointF(ox + x * sc, oy - y * sc)

    def poly(P, dx):
        return QPolygonF([pt(a + dx, b) for a, b in P])

    lw = max(1.0, fp / 10)
    strip_fill = QColor(232, 238, 248)
    edge = QPen(QColor(40, 70, 130), lw * 1.3)
    # 스트립 띠: 캐리어는 끝까지, 노칭 전 공정은 전체 폭
    notch_i = next((i for i, s in enumerate(plan.stations) if s.kind == NOTCH), 0)
    p.setPen(Qt.NoPen)
    p.setBrush(strip_fill)
    p.drawRect(QRectF(pt(left, yc1), pt(right, yc0)))
    full_end = cx0 + plan.pitch * (notch_i - 0.5)
    p.drawRect(QRectF(pt(left, ytop), pt(full_end, yc1)))
    p.setPen(QPen(QColor(120, 130, 150), lw))
    p.drawLine(pt(left, yc0), pt(right, yc0))
    p.drawLine(pt(left, ytop), pt(full_end, ytop))
    p.drawLine(pt(full_end, yc1), pt(right, yc1))

    done = {}
    for i, s in enumerate(plan.stations):
        cx = cx0 + i * plan.pitch
        dx = cx - cx0
        for num, ang in s.bends:
            done[num] = ang
        # 공정 가운데 선 · 제목
        p.setPen(QPen(QColor(170, 170, 170), lw * 0.8, Qt.DashDotLine))
        p.drawLine(pt(cx, yc0 - 2), pt(cx, ytop + 2))
        p.setPen(QColor(20, 20, 20))
        f = QFont(p.font())
        f.setPixelSize(int(fp))
        f.setBold(True)
        p.setFont(f)
        tx = pt(cx, ytop)
        p.drawText(QRectF(tx.x() - plan.pitch * sc / 2, rect.top(), plan.pitch * sc, fp * 1.4),
                   Qt.AlignCenter, f"S{s.no}")
        f.setBold(False)
        f.setPixelSize(int(fp * 0.85))
        p.setFont(f)
        p.drawText(QRectF(tx.x() - plan.pitch * sc / 2, rect.top() + fp * 1.4, plan.pitch * sc, fp * 1.3),
                   Qt.AlignCenter, s.title)
        # 파일럿
        p.setPen(QPen(QColor(40, 70, 130), lw))
        p.setBrush(QColor(255, 255, 255))
        r = plan.pilot_d / 2 * sc
        pc = pt(cx, (yc0 + yc1) / 2)
        if i >= 0:
            p.drawEllipse(pc, r, r)
        if s.kind == CUTOFF:
            # 떨어져 나간 부품: 연결부 자른 자리만
            p.setPen(QPen(QColor(200, 40, 40), lw * 1.5))
            a = pt(tab_x + dx - tab_w / 2, yc1)
            b = pt(tab_x + dx + tab_w / 2, yc1)
            p.drawLine(a, b)
            p.setPen(QPen(QColor(150, 150, 150), lw, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly(fold_points(plan.outer, plan.folds, done), dx))
            continue
        cut = i >= notch_i
        if cut:
            # 연결부 + 부품 (접힌 모양)
            p.setPen(Qt.NoPen)
            p.setBrush(strip_fill)
            p.drawRect(QRectF(pt(tab_x + dx - tab_w / 2, y0 + 0.5), pt(tab_x + dx + tab_w / 2, yc1)))
            p.setPen(edge)
            p.setBrush(QColor(200, 215, 240))
            p.drawPolygon(poly(fold_points(plan.outer, plan.folds, done), dx))
        else:
            p.setPen(QPen(QColor(90, 110, 160), lw, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(poly(plan.outer, dx))
        made = {h for st_ in plan.stations[:i + 1] for h in st_.holes}
        p.setPen(edge)
        p.setBrush(QColor(255, 255, 255))
        for k_, hh in enumerate(plan.holes):
            if k_ in made:
                p.drawPolygon(poly(fold_points(hh, plan.folds, done), dx))
        if s.holes:          # 이번 공정에서 뚫는 구멍은 빨간 테두리
            p.setPen(QPen(QColor(220, 50, 50), lw * 1.6))
            p.setBrush(Qt.NoBrush)
            for k_ in s.holes:
                p.drawPolygon(poly(fold_points(plan.holes[k_], plan.folds, done), dx))
        # 이번 공정의 절곡선
        for num, _ in s.bends:
            fl = next(f for f in plan.folds if f.number == num)
            d = np.array([fl.n[1], -fl.n[0]])
            O = fold_points(plan.outer, plan.folds, done)
            proj = (O - fl.a) @ d
            a = fl.a + d * proj.min()
            b = fl.a + d * proj.max()
            p.setPen(QPen(QColor(220, 50, 50), lw * 2.2))
            p.drawLine(pt(a[0] + dx, a[1]), pt(b[0] + dx, b[1]))
    # 피치 치수
    p.setPen(QPen(QColor(200, 40, 40), lw))
    f = QFont(p.font())
    f.setPixelSize(int(fp * 0.85))
    p.setFont(f)
    ya = yc0 - 4 / sc * fp / 3
    a, b = pt(cx0, yc0), pt(cx0 + plan.pitch, yc0)
    yy = a.y() + fp * 0.9
    p.drawLine(QPointF(a.x(), yy), QPointF(b.x(), yy))
    p.drawText(QRectF(a.x(), yy, b.x() - a.x(), fp * 1.3), Qt.AlignCenter, f"피치 {plan.pitch:g}")
    p.drawText(QRectF(pt(right, ytop).x() - 300 * fp / 14, yy, 300 * fp / 14, fp * 1.3),
               Qt.AlignRight | Qt.AlignVCenter,
               f"스트립 폭 {plan.strip_width:.1f} · 캐리어 {plan.carrier:.1f} · 이송 →")
    del ya
    if sec_rect is None:
        return
    # 단면: 모든 공정 같은 축척
    allp = np.vstack([x for x in secs if x is not None])
    span = np.ptp(allp, axis=0)
    cell = plan.pitch * sc
    ss = min(cell * 0.85 / max(span[0], 1e-6), (sec_rect.height() - fp * 2.5) / max(span[1], 1e-6), sc * 1.5)
    ybase = sec_rect.top() + fp * 1.6 + float(allp[:, 1].max()) * ss
    p.setPen(QColor(90, 90, 90))
    f.setPixelSize(int(fp * 0.85))
    p.setFont(f)
    p.drawText(QRectF(rect.left(), sec_rect.top(), 400 * fp / 14, fp * 1.3), Qt.AlignLeft | Qt.AlignVCenter,
               "단면 (옆에서 본 모양, 캐리어 쪽 판이 바닥)")
    for i, sx in enumerate(secs):
        if sx is None:
            continue
        cx = pt(cx0 + i * plan.pitch, 0).x()
        p.setPen(QPen(QColor(40, 70, 130), max(plan.thickness * ss, lw * 1.8)))
        p.drawPolyline(QPolygonF([QPointF(cx + a * ss, ybase - b * ss) for a, b in sx]))


def _paint_draw(p, rect, plan, fp):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen, QPolygonF

    dp = plan.draw
    t = plan.thickness
    D = dp.D
    shapes = []        # (지름, 높이) — 0 높이는 원판
    shapes.append((D, 0.0))
    for s in dp.stages:
        shapes.append((s.d, cup_height(D, s.d, plan.cup_r)))
    last_d, last_h = shapes[-1]
    shapes.append((last_d, plan.final_h or max(last_h - dp.trim, 0)))
    n = len(plan.stations)
    while len(shapes) < n:
        shapes.append(shapes[-1])
    cell = rect.width() / n
    hmax = max(h for _, h in shapes) or 1.0
    head = fp * 3.2
    sc = min((cell * 0.85) / D, (rect.height() - head - fp * 3) / (hmax + 5 * t + 1))
    lw = max(1.0, fp / 10)
    for i, s in enumerate(plan.stations):
        cx = rect.left() + cell * (i + 0.5)
        base = rect.bottom() - fp * 2.5
        f = QFont(p.font())
        f.setPixelSize(int(fp))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(20, 20, 20))
        p.drawText(QRectF(cx - cell / 2, rect.top(), cell, fp * 1.4), Qt.AlignCenter, f"S{s.no}")
        f.setBold(False)
        f.setPixelSize(int(fp * 0.85))
        p.setFont(f)
        p.drawText(QRectF(cx - cell / 2, rect.top() + fp * 1.4, cell, fp * 1.3), Qt.AlignCenter, s.title)
        d, h = shapes[i]
        p.setPen(QPen(QColor(40, 70, 130), lw * 1.5))
        p.setBrush(QColor(200, 215, 240))
        tt = max(t * sc, 2.0)
        if h <= 0:
            p.drawRect(QRectF(cx - d / 2 * sc, base - tt, d * sc, tt))
        else:
            R = d / 2 * sc
            H = h * sc
            pts = [QPointF(cx - R, base - H), QPointF(cx - R, base), QPointF(cx + R, base),
                   QPointF(cx + R, base - H), QPointF(cx + R - tt, base - H), QPointF(cx + R - tt, base - tt),
                   QPointF(cx - R + tt, base - tt), QPointF(cx - R + tt, base - H)]
            p.drawPolygon(QPolygonF(pts))
        if s.kind == PIERCE:
            p.setPen(QPen(QColor(220, 50, 50), lw * 2))
            p.drawLine(QPointF(cx - 3, base - tt / 2), QPointF(cx + 3, base - tt / 2))
        p.setPen(QColor(60, 60, 60))
        txt = f"Ø{d:.1f}" + (f"  H{h:.1f}" if h > 0 else "")
        p.drawText(QRectF(cx - cell / 2, base + fp * 0.3, cell, fp * 1.3), Qt.AlignCenter, txt)


def render(plan, w=1400, h=520):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint(p, QRectF(10, 6, w - 20, h - 12), plan, 15.0)
    p.end()
    return img


def station_rows(plan):
    return [[f"S{s.no}", s.title, s.detail + (f"  [{' '.join(s.rules)}]" if s.rules else ""),
             s.force_n / 1000, s.force_n / dc.TON] for s in plan.stations]


def summary_lines(plan):
    if plan.kind == "draw":
        dp = plan.draw
        out = [f"블랭크 Ø{dp.D:.1f} mm · 드로잉 {len(dp.stages)}회 · t/D {dp.rel_thickness:.2f} %"]
    else:
        out = [f"피치 {plan.pitch:g} mm · 스트립 폭 {plan.strip_width:.1f} mm · 캐리어 {plan.carrier:.1f} mm "
               f"(파일럿 Ø{plan.pilot_d:g}) · 연결부 {plan.tab[1]:.1f} × {plan.tab[2]:.1f}",
               f"재료 이용률 {plan.utilization:.1%} · 1 m 에 {1000 / plan.pitch:.2f} 개"]
    out.append(f"공정 {len(plan.stations)} · 하중 합계 {plan.total_force / 1000:,.1f} kN "
               f"({plan.total_force / dc.TON:.1f} tf) · 권장 프레스 {plan.press_tonf:.0f} tf (× 1.3)")
    return out + [f"⚠ {n}" for n in plan.notes]


def _open_pdf(path, title):
    from PySide6.QtCore import QMarginsF, QRectF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

    from .report import ensure_gui, version_text
    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A3), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(title)
    pdf.setCreator(f"한일 판금 전개 {version_text()}")
    k = 300 / 25.4

    def R(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    return pdf, p, R, k, 420.0, 297.0, 12.0


def save_pdf(plan, path, name="", route=None):
    pdf, p, R, k, W, H, m = _open_pdf(path, f"금형 공정도 - {name}")
    _plan_page(p, R, k, W, H, m, plan, name)
    if route is not None:
        pdf.newPage()
        _route_page(p, R, k, W, H, m, route, name)
    p.end()


def save_pdf_many(items, path, title=""):
    """여러 부품의 공정도를 한 권으로. items: [(이름, 공정도 plan 또는 None, 공정 설계 route 또는 None)].
    첫 쪽은 차례 (부품·금형 형식·공정수)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    from .report import _brand, _font
    pdf, p, R, k, W, H, m = _open_pdf(path, f"금형 공정도 - {title}")
    p.setPen(QColor(20, 20, 20))
    p.setFont(_font(18, True))
    p.drawText(R(m, m, W - 2 * m, 10), Qt.AlignLeft | Qt.AlignVCenter, f"금형 공정도 (초안) — {title}")
    p.setFont(_font(8))
    _brand(p, R(m, m + 2, W - 2 * m, 6))
    rows = []
    page = 2
    for name, plan, rt in items:
        n_pages = (1 if plan is not None else 0) + (1 if rt is not None else 0)
        ops = len(plan.stations) if plan is not None else (len(rt.steps) if rt else 0)
        rows.append([name[:30], rt.die_type if rt else "-", str(ops),
                     f"{plan.press_tonf:.0f}" if plan is not None else "-", f"{page}"])
        page += n_pages
    _table(p, R, k, m, m + 16, [("부품", 90), ("금형 형식 / 공정", 110), ("공정수", 22), ("프레스 tf", 26),
                                ("쪽", 16)], rows, 9, maxy=H - m - 10)
    for name, plan, rt in items:
        if plan is not None:
            pdf.newPage()
            _plan_page(p, R, k, W, H, m, plan, name)
        if rt is not None:
            pdf.newPage()
            _route_page(p, R, k, W, H, m, rt, name)
    p.end()


def _plan_page(p, R, k, W, H, m, plan, name):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPen

    from .report import _brand, _font, version_text
    p.setPen(QColor(20, 20, 20))
    p.setFont(_font(16, True))
    kind = "순차 금형 스트립 공정도" if plan.kind == "progressive" else "드로잉 공정도"
    p.drawText(R(m, m, W - 2 * m, 9), Qt.AlignLeft | Qt.AlignVCenter, f"금형 공정도 (초안) — {name}  ·  {kind}")
    p.setFont(_font(8))
    bw = _brand(p, R(m, m + 1.5, W - 2 * m, 6)) / k
    p.setFont(_font(8))
    p.setPen(QColor(110, 110, 110))
    p.drawText(R(m, m, W - 2 * m - bw - 4, 9), Qt.AlignRight | Qt.AlignVCenter,
               f"{plan.material} · t {plan.thickness:g} · {_dt.datetime.now():%Y-%m-%d} · 한일 판금 전개 {version_text()}")
    p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
    p.drawLine(QPointF(m * k, (m + 10) * k), QPointF((W - m) * k, (m + 10) * k))
    # 그림
    box = R(m, m + 14, W - 2 * m, 150)
    p.setPen(QPen(QColor(180, 180, 180), 0.2 * k))
    p.setBrush(Qt.NoBrush)
    p.drawRect(box)
    p.setFont(_font(9))
    paint(p, box.adjusted(3 * k, 2 * k, -3 * k, -2 * k), plan, 3.6 * k)
    # 공정표
    y = m + 14 + 150 + 6
    cols = [("공정", 16), ("작업", 40), ("내용", 190), ("하중 kN", 30), ("tf", 24)]
    x = m
    p.setFont(_font(9, True))
    p.setBrush(QColor(31, 78, 140))
    p.setPen(Qt.NoPen)
    p.drawRect(R(m, y, sum(c[1] for c in cols), 6.5))
    p.setPen(QColor(255, 255, 255))
    for title, cw in cols:
        p.drawText(R(x + 1.5, y, cw - 3, 6.5), Qt.AlignVCenter | Qt.AlignLeft, title)
        x += cw
    y += 6.5
    p.setFont(_font(9))
    for i, row in enumerate(station_rows(plan)):
        if y > H - m - 30:
            break
        if i % 2:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(240, 244, 250))
            p.drawRect(R(m, y, sum(c[1] for c in cols), 6))
        p.setPen(QColor(20, 20, 20))
        x = m
        for (title, cw), v in zip(cols, row):
            txt = v if isinstance(v, str) else f"{v:,.1f}"
            al = Qt.AlignLeft if isinstance(v, str) else Qt.AlignRight
            p.drawText(R(x + 1.5, y, cw - 3, 6), Qt.AlignVCenter | al, txt)
            x += cw
        y += 6
    # 요약 · 주의
    sx = m + sum(c[1] for c in cols) + 8
    yy = m + 14 + 150 + 6
    p.setFont(_font(9))
    for line in summary_lines(plan):
        p.setPen(QColor(200, 100, 0) if line.startswith("⚠") else QColor(20, 20, 20))
        rr = R(sx, yy, W - m - sx, 18)
        br = p.boundingRect(rr, Qt.TextWordWrap, line)
        p.drawText(rr, Qt.TextWordWrap, line)
        yy += br.height() / k + 2
    p.setPen(QColor(120, 120, 120))
    p.setFont(_font(8))
    p.drawText(R(m, H - m - 6, W - 2 * m, 6), Qt.AlignLeft | Qt.AlignVCenter,
               "자동으로 만든 초안입니다. 공정 순서·캐리어·파일럿·빈 공정·하중은 금형 설계자가 확정하세요. "
               "하중: 전단 τ = 인장강도 × 0.8, 굽힘 F = 1.33·σb·L·t²/V.")



def _table(p, R, k, x, y, cols, rows, size=9, maxy=280.0):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    from .report import _font
    p.setFont(_font(size, True))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(31, 78, 140))
    tw = sum(c[1] for c in cols)
    p.drawRect(R(x, y, tw, 6.5))
    p.setPen(QColor(255, 255, 255))
    cx = x
    for title, cw in cols:
        p.drawText(R(cx + 1.5, y, cw - 3, 6.5), Qt.AlignVCenter | Qt.AlignLeft, title)
        cx += cw
    y += 6.5
    p.setFont(_font(size))
    for i, row in enumerate(rows):
        if y > maxy:
            break
        if i % 2:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(240, 244, 250))
            p.drawRect(R(x, y, tw, 6))
        p.setPen(QColor(20, 20, 20))
        cx = x
        for (title, cw), v in zip(cols, row):
            p.drawText(R(cx + 1.5, y, cw - 3, 6), Qt.AlignVCenter | Qt.AlignLeft, str(v))
            cx += cw
        y += 6
    return y


def _route_page(p, R, k, W, H, m, rt, name):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPen

    from . import procplan as pp
    from .report import _brand, _font
    p.setPen(QColor(20, 20, 20))
    p.setFont(_font(16, True))
    p.drawText(R(m, m, W - 2 * m, 9), Qt.AlignLeft | Qt.AlignVCenter, f"자동 공정 설계 — {name}")
    p.setFont(_font(8))
    _brand(p, R(m, m + 1.5, W - 2 * m, 6))
    p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
    p.drawLine(QPointF(m * k, (m + 10) * k), QPointF((W - m) * k, (m + 10) * k))
    y = m + 15
    p.setFont(_font(12, True))
    p.setPen(QColor(31, 78, 140))
    p.drawText(R(m, y, W - 2 * m, 7), Qt.AlignLeft | Qt.AlignVCenter, f"추천 금형: {rt.die_type}")
    y += 8
    p.setFont(_font(9))
    p.setPen(QColor(40, 40, 40))
    p.drawText(R(m, y, W - 2 * m, 6), Qt.AlignLeft | Qt.AlignVCenter, rt.die_reason)
    y += 9
    left_w = 250
    y1 = _table(p, R, k, m, y, [("순서", 14), ("공정", 40), ("내용", 166), ("근거", 30)], pp.route_rows(rt))
    if rt.features.holes:
        y1 = _table(p, R, k, m, y1 + 6, [("구멍", 14), ("크기", 18), ("있는 판", 32), ("가까운 절곡", 30),
                                         ("동축", 16), ("뚫는 때", 40), ("근거", 22)], pp.hole_rows(rt), 8)
    # 오른쪽: AI 검토 · 주의 · 규칙
    x = m + left_w + 8
    yy = y
    cw = W - m - x

    def para(text, color=QColor(30, 30, 30), size=9, bold=False):
        nonlocal yy
        p.setFont(_font(size, bold))
        p.setPen(color)
        rr = R(x, yy, cw, 60)
        br = p.boundingRect(rr, Qt.TextWordWrap, text)
        p.drawText(rr, Qt.TextWordWrap, text)
        yy += br.height() / k + 1.5

    for n in rt.notes:
        para("⚠ " + n, QColor(200, 100, 0))
    if rt.ai:
        a = rt.ai
        para(f"AI 도면 검토: {a['die_type']}", QColor(31, 78, 140), 11, True)
        para(a["die_reason"])
        for i, s_ in enumerate(a["steps"], 1):
            para(f"{i}. {s_['op']} — {s_['detail']}  ({s_['reason']})", size=8)
        for n in a["drawing_notes"]:
            para("· 도면: " + n, size=8)
        for n in a["warnings"]:
            para("⚠ " + n, QColor(200, 100, 0), 8)
        yy += 2
    para("근거 규칙", QColor(31, 78, 140), 10, True)
    for kk, v in pp.RULES.items():
        para(f"{kk}  {v}", QColor(70, 70, 70), 8)
    p.setFont(_font(8))
    p.setPen(QColor(120, 120, 120))
    p.drawText(R(m, H - m - 6, W - 2 * m, 6), Qt.AlignLeft | Qt.AlignVCenter,
               "규칙 출처: Naranje & Kumar 2013 (순차 금형 KBS), Vosniakos 외 2005, Qattawi 외 2014 (조사), "
               "MetalForming·절곡 실무 지침, 자동차 패널 금형 라인 (DR-TR/PI-FL-RST-CAM). 생산량 기준은 어림값.")


def save_dxf(plan, path, name=""):
    """순차 금형 스트립 공정도 DXF (1:1 mm). 레이어: STRIP, PART, PILOT, BEND, STATION, TEXT."""
    import ezdxf
    if plan.kind != "progressive":
        raise ValueError("DXF 는 순차 금형 스트립 공정도만 됩니다.")
    doc = ezdxf.new("R2010", setup=True)
    for lay, col in (("STRIP", 8), ("PART", 5), ("PILOT", 3), ("BEND", 1), ("STATION", 9), ("TEXT", 7)):
        doc.layers.add(lay, color=col)
    msp = doc.modelspace()
    x0, y0, x1, y1 = plan.bbox
    tab_x, tab_w, tab_len = plan.tab
    yc0, yc1, ytop = y0 - tab_len - plan.carrier, y0 - tab_len, y1 + plan.side
    cx0 = (x0 + x1) / 2
    n = len(plan.stations)
    left, right = cx0 - plan.pitch, cx0 + plan.pitch * (n + 0.1)
    msp.add_lwpolyline([(left, yc0), (right, yc0)], dxfattribs={"layer": "STRIP"})
    msp.add_lwpolyline([(left, yc1), (left, ytop)], dxfattribs={"layer": "STRIP"})
    notch_i = next((i for i, s in enumerate(plan.stations) if s.kind == NOTCH), 0)
    full_end = cx0 + plan.pitch * (notch_i - 0.5)
    msp.add_lwpolyline([(left, ytop), (full_end, ytop)], dxfattribs={"layer": "STRIP"})
    msp.add_lwpolyline([(full_end, yc1), (right, yc1)], dxfattribs={"layer": "STRIP"})
    h_txt = max(plan.pitch / 25, 2.5)
    done = {}
    for i, s in enumerate(plan.stations):
        cx = cx0 + i * plan.pitch
        dx = cx - cx0
        for num, ang in s.bends:
            done[num] = ang
        msp.add_line((cx, yc0 - 3), (cx, ytop + 3), dxfattribs={"layer": "STATION", "linetype": "DASHDOT"})
        msp.add_text(f"S{s.no} {s.title}", height=h_txt,
                     dxfattribs={"layer": "TEXT"}).set_placement((cx, ytop + 3 + h_txt), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
        msp.add_circle((cx, (yc0 + yc1) / 2), plan.pilot_d / 2, dxfattribs={"layer": "PILOT"})
        if s.kind == CUTOFF:
            continue
        O = fold_points(plan.outer, plan.folds, done) + (dx, 0)
        msp.add_lwpolyline([tuple(q) for q in O], close=True,
                           dxfattribs={"layer": "PART", "linetype": "DASHED" if i < notch_i else "CONTINUOUS"})
        if i >= notch_i:
            msp.add_lwpolyline([(tab_x + dx - tab_w / 2, yc1), (tab_x + dx - tab_w / 2, y0),
                                (tab_x + dx + tab_w / 2, y0), (tab_x + dx + tab_w / 2, yc1)],
                               dxfattribs={"layer": "PART"})
        made = {h for st_ in plan.stations[:i + 1] for h in st_.holes}
        for k_, hh in enumerate(plan.holes):
            if k_ in made:
                msp.add_lwpolyline([tuple(q) for q in fold_points(hh, plan.folds, done) + (dx, 0)], close=True,
                                   dxfattribs={"layer": "PART"})
        for num, _ in s.bends:
            fl = next(f for f in plan.folds if f.number == num)
            d = np.array([fl.n[1], -fl.n[0]])
            proj = (O - (dx, 0) - fl.a) @ d
            a, b = fl.a + d * proj.min(), fl.a + d * proj.max()
            msp.add_line((a[0] + dx, a[1]), (b[0] + dx, b[1]), dxfattribs={"layer": "BEND"})
    y = yc0 - 3 * h_txt
    for line in [f"금형 공정도 (초안) {name}  {plan.material} t{plan.thickness:g}"] + summary_lines(plan):
        msp.add_text(line, height=h_txt * 0.8, dxfattribs={"layer": "TEXT"}).set_placement((left, y))
        y -= h_txt * 1.4
    for row in station_rows(plan):
        msp.add_text(f"{row[0]}  {row[1]}  {row[2]}  {row[3]:,.1f} kN", height=h_txt * 0.7,
                     dxfattribs={"layer": "TEXT"}).set_placement((left, y))
        y -= h_txt * 1.2
    doc.saveas(path)
