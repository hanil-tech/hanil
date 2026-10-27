"""금형 3D 조립 (블랭킹 · 피어싱 → 블랭킹 2 공정 / 순차 금형): 판 쌓기 · 가이드 포스트·부시 · 펀치 · 파일럿 ·
스트리퍼 · 스프링 · 볼트 · 다우얼 핀 · 스트립 가이드 · 생크 를 솔리드로 만들고, STEP (부품 이름 붙임) · 2D 조립도
(평면도 + 정면도, 풍선 번호) · 판마다 가공도 (DXF · PDF, 구멍표) · 파트리스트 엑셀로.

VISI·PressCAD 의 3D 금형 설계 순서 (레이아웃 → 상·하 스틸 → 스트리퍼·펀치 → 홀더·표준 부품 → 조립도·부품도 → 파트리스트)
를 현장 첫 안으로 자동으로 한다.
  레이아웃      구멍이 있으면 피어싱 → 블랭킹 2 공정 (피치 = 길이 + 브리지 max(1.5 t, 1.5), 블랭킹 펀치에 파일럿)
  다이 플레이트 H ≈ ∛(0.1 F) (diecalc.die_plate_thickness), 5 mm 올림, 최소 20 — 날 랜드 max(3, t), 아래는 한쪽 0.5 넓힘
  여유          max(1.5 H, 30) mm 에서 시작, 볼트·스프링·스트리퍼 볼트가 자리를 못 찾으면 10 mm 씩 넓힘
  스트리핑 힘   절단력의 7 % — 펀치가 판에서 빠질 때 스프링 힘 ≥ 이 힘, 끝 휨 ≤ 오래 쓰기 한계 (diestd)
  행정          펀치는 열린 상태에서 스트리퍼 안 1 mm, 닫힘에서 다이 안 1 mm → 스트리퍼 움직임 = t + 2, 재연마 3 mm
  표준품        볼트·스트리퍼 볼트·다우얼 핀·스프링은 규격 길이 (diestd) 로, 카운터보어·탭·H7 구멍을 판에 판다
  생크          절단선 길이로 무게 중심 (압력 중심) 위에
설계 확정은 금형 설계자가 한다 (표준품 규격은 쓰는 업체 표로 확인).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc
from . import diestd as ds

BOX, CYL, PRISM = "box", "cyl", "prism"
STRIP_K = 0.07        # 스트리핑 힘 / 절단력 (교재 2 ~ 20 %, 보통 5 ~ 10 %)
ENTRY = 1.0           # 닫힘에서 펀치가 다이 안으로 들어가는 깊이
RETRACT = 1.0         # 열림에서 펀치 끝이 스트리퍼 안으로 들어가 있는 깊이
REGRIND = 3.0         # 펀치·다이 재연마 여유 (스프링·스트리퍼 볼트 자리)
DENSITY = 7.85e-6     # kg/mm³ (강)
PUNCH_SIGMA = 1500.0  # 피어싱 펀치 허용 압축 응력 MPa (SKH51 어림)
# STEP 안의 부품 이름 (영문 — 한글은 CAD 마다 STEP 문자 인코딩이 달라 깨짐)
EN = {"하형 다이 세트": "LOWER DIE SET", "다이 받침판": "DIE BACKING PLATE", "다이 플레이트": "DIE PLATE",
      "스트리퍼 플레이트": "STRIPPER PLATE", "펀치 플레이트": "PUNCH PLATE", "펀치 받침판": "PUNCH BACKING PLATE",
      "상형 다이 세트": "UPPER DIE SET", "가이드 포스트": "GUIDE POST", "가이드 부시": "GUIDE BUSH",
      "블랭킹 펀치": "BLANKING PUNCH", "피어싱 펀치": "PIERCE PUNCH", "이형 피어싱 펀치": "SHAPED PIERCE PUNCH",
      "스트리퍼 볼트": "STRIPPER BOLT", "다이 스프링": "DIE SPRING", "육각 구멍 붙이 볼트": "SOCKET HEAD BOLT",
      "다우얼 핀": "DOWEL PIN", "생크": "SHANK", "파일럿 핀": "PILOT PIN", "스트립 가이드": "STRIP GUIDE",
      "(하형)": "(LOWER)", "(상형)": "(UPPER)"}
PLATES = ("하형 다이 세트", "다이 받침판", "다이 플레이트", "스트리퍼 플레이트", "펀치 플레이트", "펀치 받침판", "상형 다이 세트")


def en_name(name):
    out = name
    for k in sorted(EN, key=len, reverse=True):
        out = out.replace(k, EN[k])
    return out


@dataclass
class Hole:
    """판에 파는 둥근 구멍 하나. z0·h 는 조립 좌표 (아래 끝 · 깊이), cb 는 카운터보어 (지름, z0, 깊이)."""
    x: float
    y: float
    d: float
    kind: str                     # "탭" · "통과" · "H7" · "압입" · "스프링 자리" ...
    z0: float
    h: float
    spec: str                     # 가공 지시 (예: "M8 탭 깊이 15")
    cb: tuple | None = None
    side: str = "윗면"            # 가공하는 면


@dataclass
class Prim:
    kind: str
    p: tuple                      # box: (x0, y0, z0, dx, dy, dz) · cyl: (x, y, z0, r, h) · prism: (z0, h)
    poly: np.ndarray | None = None   # prism 의 2D 다각형 (x, y)
    cuts: list = field(default_factory=list)   # 빼낼 프리즘 [(다각형, 넓힘[, z0, 깊이])] — z 없으면 관통
    holes: list = field(default_factory=list)  # 둥근 구멍 [Hole]


@dataclass
class DiePart:
    no: int
    name: str
    qty: int
    material: str
    size: str
    std: bool = False
    note: str = ""
    prims: list = field(default_factory=list)
    upper: bool = False           # 상형 쪽 (정면도에서 위)
    order: str = ""               # 표준품 주문 규격

    @property
    def weight(self):
        """한 개 무게 kg (구멍 뺌, 어림)."""
        v = _volume(self.prims[0]) if self.prims else 0.0
        return v * DENSITY


@dataclass
class DieAssy:
    kind: str
    parts: list
    L: float
    W: float
    shut: float                   # 닫힌 높이 (하형 세트 밑면 ↔ 상형 세트 윗면, 하사점)
    force_n: float
    notes: list = field(default_factory=list)
    blank: np.ndarray | None = None
    holes: list = field(default_factory=list)
    checks: list = field(default_factory=list)    # [(항목, 값, 기준, 판정)]
    cop: tuple = (0.0, 0.0)                       # 압력 중심
    open_h: float = 0.0                           # 열린 높이 (그림 상태)
    stroke: float = 0.0                           # 필요한 프레스 행정 (어림)
    strip: tuple = (0.0, 0.0)                     # (피치, 스트립 폭)
    spring: object = None

    def rows(self):
        return [[p.no, p.name, p.qty, p.material, p.size, "표준품" if p.std else "가공품",
                 round(p.weight, 2), p.order or p.note if p.std else p.note] for p in self.parts]

    def plate(self, name):
        return next(p for p in self.parts if p.name == name)


HEAD = ["번호", "품명", "수량", "재질", "크기 (mm)", "구분", "단중 (kg)", "비고 · 주문 규격"]
CHECK_HEAD = ["점검 항목", "값", "기준", "판정"]


class _NoRoom(Exception):
    pass


def _up5(x):
    return float(math.ceil(x / 5.0 - 1e-9) * 5)


def _outline(result):
    from .nesting import NestPart
    np_ = NestPart.from_result("p", result)
    if np_.outer is None:
        raise ValueError("전개 외곽이 닫혀 있지 않아 금형을 만들 수 없습니다")
    P = np.asarray(np_.outer, float)
    c = 0.5 * (P.min(0) + P.max(0))
    return P - c, [np.asarray(h, float) - c for h in np_.holes]


def _area(P):
    P = np.asarray(P, float)
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def _offset(poly, d):
    """다각형을 바깥으로 d 만큼 (꼭짓점 법선, 어림)."""
    P = np.asarray(poly, float)
    t = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    n = np.column_stack([t[:, 1], -t[:, 0]]) * (1 if _area(P) > 0 else -1)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    return P + d * n


def _per(P):
    return float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).sum())


def _circle_d(h):
    c = h.mean(0)
    return 2 * float(np.mean(np.linalg.norm(h - c, axis=1))), c


def _is_round(h):
    d, c = _circle_d(h)
    return np.std(np.linalg.norm(h - c, axis=1)) < 0.02 * d


def _inside(P, pt):
    x, y = pt
    xi, yi = P[:, 0], P[:, 1]
    xj, yj = np.roll(xi, 1), np.roll(yi, 1)
    c = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / np.where(yj - yi == 0, 1e-30, yj - yi) + xi)
    return bool(np.count_nonzero(c) % 2)


def _dist(P, pt):
    """점 ↔ 다각형 경계 거리 (안이면 음수)."""
    A = np.asarray(P, float)
    B = np.roll(A, -1, axis=0)
    q = np.asarray(pt, float)
    ab = B - A
    u = np.clip(np.einsum("ij,ij->i", q - A, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-30), 0, 1)
    d = float(np.min(np.linalg.norm(A + u[:, None] * ab - q, axis=1)))
    return -d if _inside(A, q) else d


def _poly_gap(P, Q):
    """두 다각형 사이 가장 짧은 거리 (경계 점들로)."""
    return min(min(_dist(Q, p) for p in P), min(_dist(P, q) for q in Q))


def _cop(polys):
    """절단선 길이로 무게 중심 = 압력 중심."""
    s, m = 0.0, np.zeros(2)
    for P in polys:
        A = np.asarray(P, float)
        B = np.roll(A, -1, axis=0)
        ln = np.linalg.norm(B - A, axis=1)
        s += ln.sum()
        m += ((A + B) / 2 * ln[:, None]).sum(0)
    return tuple(m / max(s, 1e-30))


def _volume(pr: Prim):
    if pr.kind == BOX:
        v = pr.p[3] * pr.p[4] * pr.p[5]
        h_all = pr.p[5]
    elif pr.kind == CYL:
        return math.pi * pr.p[3] ** 2 * pr.p[4]
    else:
        v = abs(_area(pr.poly)) * pr.p[1]
        h_all = pr.p[1]
    for c in pr.cuts:
        poly, grow = c[0], c[1]
        hh = c[3] if len(c) > 2 else h_all
        v -= abs(_area(_offset(poly, grow) if grow else poly)) * min(hh, h_all)
    for h in pr.holes:
        v -= math.pi * h.d ** 2 / 4 * h.h
        if h.cb:
            v -= math.pi * (h.cb[0] ** 2 - h.d ** 2) / 4 * h.cb[2]
    return max(v, 0.0)


class _Slots:
    """판 위 둥근 자리 고르기: 날 (다각형) 에서 띄우고, 판 끝에서 띄우고, 이미 잡은 자리와 겹치지 않게."""

    def __init__(self, a, b, polys, web):
        self.a, self.b, self.polys, self.web = a, b, polys, web
        self.taken = []

    def ok(self, x, y, r, e):
        if abs(x) > self.a - e + 1e-9 or abs(y) > self.b - e + 1e-9:
            return False
        if any(_dist(P, (x, y)) < r + self.web for P in self.polys):
            return False
        return all(math.hypot(x - qx, y - qy) >= r + qr + 3 for qx, qy, qr in self.taken)

    def place(self, target, r, e):
        """target 가까이 (판 끝에서 e 안쪽 둘레 위, 안 되면 더 안쪽) 빈 자리."""
        tx, ty = target
        for inset in (0, 5, 10, 15, 20):
            ee = e + inset
            a, b = self.a - ee, self.b - ee
            if a <= 0 or b <= 0:
                break
            per = 4 * (a + b)
            n = max(int(per / 1.0), 8)
            s = np.linspace(0, per, n, endpoint=False)
            pts = []
            for v in s:
                if v < 2 * a:
                    pts.append((-a + v, -b))
                elif v < 2 * a + 2 * b:
                    pts.append((a, -b + v - 2 * a))
                elif v < 4 * a + 2 * b:
                    pts.append((a - (v - 2 * a - 2 * b), b))
                else:
                    pts.append((-a, b - (v - 4 * a - 2 * b)))
            pts.sort(key=lambda p: math.hypot(p[0] - tx, p[1] - ty))
            for x, y in pts:
                if self.ok(x, y, r, ee):
                    self.taken.append((x, y, r))
                    return (x, y)
        raise _NoRoom


def _perimeter_targets(a, b, n, phase=0.5):
    per = 4 * (a + b)
    out = []
    for i in range(n):
        v = per * (i + phase) / n
        if v < 2 * a:
            out.append((-a + v, -b))
        elif v < 2 * a + 2 * b:
            out.append((a, -b + v - 2 * a))
        elif v < 4 * a + 2 * b:
            out.append((a - (v - 2 * a - 2 * b), b))
        else:
            out.append((-a, b - (v - 4 * a - 2 * b)))
    return out


def _layout(result, t, plan):
    """레이아웃: [(다각형, 종류)] (종류 "pierce" / "blank"), 블랭킹 위치의 파일럿 [(x, y, d)], 작업 영역 (L, W),
    피치·스트립 폭, 이름."""
    blank, holes = _outline(result)
    side = max(1.5 * t, 2.0)
    if plan is not None and getattr(plan, "pitch", 0):
        n_st = len(plan.stations)
        P = plan.pitch
        x0, y0, x1, y1 = plan.bbox
        tab_len = plan.tab[2]
        cx = 0.5 * (x0 + x1)
        cy = 0.5 * ((y0 - tab_len - plan.carrier) + (y1 + plan.side))     # 스트립 가운데
        ops = []
        pil = []
        if plan.pilot_d > 0:                                                # 캐리어 파일럿 구멍 (1 공정)
            yc = y0 - tab_len - plan.carrier / 2 - cy
            a_ = np.linspace(0, 2 * np.pi, 48, endpoint=False)
            circ = np.column_stack([np.cos(a_), np.sin(a_)]) * plan.pilot_d / 2
            ops.append((circ + np.array([(0 - (n_st - 1) / 2) * P, yc]), "pierce"))
        for i, s in enumerate(plan.stations):
            dx = (i - (n_st - 1) / 2) * P - cx
            for k in getattr(s, "holes", []) or []:
                ops.append((plan.holes[k] + np.array([dx, -cy]), "pierce"))
        return ops, pil, (n_st * P, plan.strip_width), (P, plan.strip_width), f"순차 ({n_st} 공정)", blank, holes
    W = float(np.ptp(blank[:, 1]))
    L = float(np.ptp(blank[:, 0]))
    Wst = W + 2 * side
    if not holes:
        P = L + max(1.5 * t, 1.5)
        return [(blank, "blank")], [], (L, Wst), (P, Wst), "단발 (블랭킹)", blank, holes
    P = math.ceil((L + max(1.5 * t, 1.5)) * 2) / 2
    sh1, sh2 = np.array([-P / 2, 0.0]), np.array([P / 2, 0.0])
    ops = [(h + sh1, "pierce") for h in holes] + [(blank + sh2, "blank")]
    rnd = [(h, *_circle_d(h)) for h in holes if _is_round(h) and _circle_d(h)[0] >= 3.0]
    pil = []
    if rnd:
        # 서로 가장 먼 둥근 구멍 둘 (하나면 하나)
        best = (rnd[0], rnd[0])
        for a_ in rnd:
            for b_ in rnd:
                if np.linalg.norm(a_[2] - b_[2]) > np.linalg.norm(best[0][2] - best[1][2]):
                    best = (a_, b_)
        for h, d, c in ({id(x): x for x in best}).values():
            pil.append((c[0] + P / 2, c[1], d))
    return ops, pil, (P + L, Wst), (P, Wst), "2 공정 (피어싱 → 블랭킹)", blank, holes


def build(result, settings: bc.BendSettings, kind=None, plan=None):
    """전개 결과 하나의 금형 조립. plan: 순차 금형 공정도 (process.ProcessPlan) — 있으면 스트립 길이·공정 자리로."""
    t = result.thickness
    ops, pilots, work, strip, kname, blank, holes = _layout(result, t, plan)
    # 압력 중심이 금형 가운데 (프레스 슬라이드 가운데) 에 오게 이송 방향으로 옮김
    sx = -_cop([P for P, _ in ops])[0]
    ops = [(P + np.array([sx, 0.0]), k_) for P, k_ in ops]
    pilots = [(x + sx, y, d) for x, y, d in pilots]
    half = max(float(np.abs(np.vstack([P for P, _ in ops])[:, 0]).max()), work[0] / 2)
    work = (2 * half, work[1])
    for k in range(8):
        try:
            return _assemble(result, settings, kind or kname, plan, t, ops, pilots, work, strip, blank, holes,
                             extra=10.0 * k)
        except _NoRoom:
            continue
    raise ValueError("표준 부품 자리를 못 찾았습니다 (여유 70 mm 넓혀도) — 손으로 배치하세요")


def _assemble(result, settings, kind, plan, t, ops, pilots, work, strip, blank, holes, extra=0.0):
    mat = settings.mat
    tau = dc.shear_strength(mat)
    polys = [P for P, _ in ops]
    if plan is not None and getattr(plan, "pitch", 0):
        F = float(sum(s.force_n for s in plan.stations)) or sum(_per(P) for P in polys) * t * tau
        L_cut = F / (t * tau)
    else:
        L_cut = sum(_per(P) for P in polys)
        F = L_cut * t * tau
    H = max(20.0, _up5(dc.die_plate_thickness(F)))
    clr = dc.clearance_pct(mat, t) / 100 * t
    land = max(3.0, t)
    work_L, work_W = work
    pitch, Wst = strip
    m = max(1.5 * H, 30.0) + extra
    Ld, Wd = _up5(work_L + 2 * m), _up5(work_W + 2 * m)
    a, b = Ld / 2, Wd / 2
    post_d = 25.0 if max(Ld, Wd) < 250 else 32.0 if max(Ld, Wd) < 450 else 38.0
    Ls, Ws = _up5(Ld + 2 * (post_d + 35)), _up5(Wd + 20)
    ts = max(40.0, _up5(0.08 * max(Ls, Ws)))
    tus = ts - 5
    bolt = ds.bolt_for(max(Ld, Wd))
    H = max(H, _up5(ds.ENGAGE * bolt + 6))               # 다이·펀치 플레이트에 볼트 탭 (물림 1.5 d + 3, 바닥 3)
    tb, tpp, tst = 10.0, max(20.0, _up5(0.8 * H), _up5(ds.ENGAGE * bolt + 6)), max(15.0, _up5(0.6 * H))
    gap = max(10.0, 4 * t)                       # 열림: 다이 윗면 ↔ 스트리퍼 아랫면
    s_w = RETRACT + t + ENTRY                    # 스트리퍼 움직임 (닿음 → 하사점)
    f_strip = STRIP_K * F
    spring = ds.pick_spring(f_strip, s_w + REGRIND, pocket_max=tpp, lag=RETRACT)
    gas = spring is None
    if gas:                                      # 코일 스프링으로 모자람 → 가장 센 것 8 개로 그리고 "검토"
        spring = ds.strongest_spring(s_w + REGRIND, tpp, 8)
        if spring is None:
            raise ValueError(f"스트리핑 힘 {f_strip / 1000:,.1f} kN — 다이 스프링 자리를 못 만듦, 가스 스프링으로 설계하세요")
    sgap = spring.installed - spring.pocket      # 스트리퍼 윗면 ↔ 펀치 플레이트 아랫면
    bk, bkh, bd1, bcb, bcbh, btap = ds.SHCS[bolt]
    n_sb = 4 if Ld <= 400 else 6
    sbd = ds.stripper_for(spring.f_max / n_sb)
    sb_m, sb_dk, sb_k, sb_thr = ds.STRIPPER[sbd]

    # 높이 (아래에서부터)
    z_ls = 0.0
    z_bk = ts
    z_die = ts + tb
    z_die_top = z_die + H
    z_st = z_die_top + gap
    z_pp = z_st + tst + sgap
    z_pb = z_pp + tpp
    z_us = z_pb + tb
    z_top = z_us + tus

    lower = Prim(BOX, (-Ls / 2, -Ws / 2, z_ls, Ls, Ws, ts))
    back = Prim(BOX, (-a, -b, z_bk, Ld, Wd, tb))
    die = Prim(BOX, (-a, -b, z_die, Ld, Wd, H))
    stripper = Prim(BOX, (-a, -b, z_st, Ld, Wd, tst))
    pp = Prim(BOX, (-a, -b, z_pp, Ld, Wd, tpp))
    pb = Prim(BOX, (-a, -b, z_pb, Ld, Wd, tb))
    upper_shoe = Prim(BOX, (-Ls / 2, -Ws / 2, z_us, Ls, Ws, tus))

    # 날: 다이는 클리어런스만큼 넓혀 랜드, 아래는 한쪽 0.5 더 (빠짐), 받침판·하형 세트는 떨어질 구멍
    for P, k in ops:
        Po = _offset(P, clr)
        die.cuts.append((Po, 0.0, z_die_top - land, land + 1))
        die.cuts.append((Po, 0.5, z_die - 1, H - land + 1))
        back.cuts.append((Po, 1.0))
        lower.cuts.append((Po, 2.0))
        stripper.cuts.append((P, 0.05))           # 펀치 안내 (블랭킹 펀치도)
        if not (k == "pierce" and _is_round(P)):
            pp.cuts.append((P, 0.0))              # 펀치 고정 (끼워 맞춤) — 둥근 펀치는 H7 구멍으로

    # 펀치 길이: 펀치 플레이트 윗면에서 스트리퍼 아랫면 RETRACT 위까지
    p_bot = z_st + RETRACT
    p_len = z_pb - p_bot
    parts = []

    def add(name, qty, material, size, prims, std=False, note="", upper=False, order=""):
        parts.append(DiePart(len(parts) + 1, name, qty, material, size, std, note, prims, upper, order))
        return parts[-1]

    # 자리 잡기: 상형 (펀치 플레이트를 지나는 것) · 하형 (다이 플레이트) 따로
    upolys = [_offset(P, 3.0 if not (k == 'pierce' and _is_round(P)) else 8.0) for P, k in ops]  # 펀치 머리·어깨까지
    web = max(5.0, float(bolt))
    up = _Slots(a, b, upolys, web)
    lo = _Slots(a, b, [_offset(P, clr + 0.5) for P in polys], web)
    e_sb = max(sb_dk / 2 + 4, 1.5 * sbd)
    r_sb = (sb_dk + 1) / 2                                # 상형 세트 머리 자리
    sb_xy = [up.place((sx * a, sy * b), r_sb, e_sb) for sx in (-1, 1) for sy in (-1, 1)]
    if n_sb == 6:
        sb_xy += [up.place((0, sy * b), r_sb, e_sb) for sy in (-1, 1)]
    e_b = max(1.5 * bolt, bcb / 2 + 4)
    b_t = [(sx * a, sy * b * 0.45) for sx in (-1, 1) for sy in (-1, 1)]
    ub_xy = [up.place(p, bcb / 2, e_b) for p in b_t]
    lb_xy = [lo.place(p, bcb / 2, e_b) for p in b_t]
    dwd = float(bolt)
    dw_t = [(-a, b), (a, -b)]
    ud_xy = [up.place(p, dwd / 2 + 0.5, max(1.5 * dwd, 12)) for p in dw_t]
    ld_xy = [lo.place(p, dwd / 2 + 0.5, max(1.5 * dwd, 12)) for p in dw_t]

    e_sp = spring.D / 2 + 5
    sp_xy = [up.place(p, spring.D / 2 + 0.5, e_sp)
             for p in _perimeter_targets(a - e_sp, b - e_sp, spring.n, 0.25)]

    # 하형: 다이 세트 · 받침판 · 다이 플레이트
    add("하형 다이 세트", 1, "SS400 (FC250)", f"{Ls:.0f} × {Ws:.0f} × {ts:.0f}", [lower], note="떨어질 구멍 (날 + 2)")
    add("다이 받침판", 1, "S50C (열처리 HRC 40~45)", f"{Ld:.0f} × {Wd:.0f} × {tb:.0f}", [back], note="떨어질 구멍 (날 + 1)")
    add("다이 플레이트", 1, "SKD11 HRC 58~62", f"{Ld:.0f} × {Wd:.0f} × {H:.0f}", [die],
        note=f"와이어: 한쪽 클리어런스 {clr:.3f} mm ({dc.clearance_pct(mat, t):g} % t), 랜드 {land:g} mm, 아래 한쪽 +0.5")
    add("스트리퍼 플레이트", 1, "S50C (HRC 40~45)", f"{Ld:.0f} × {Wd:.0f} × {tst:.0f}", [stripper],
        upper=True, note=f"펀치 안내 한쪽 +0.05 · 스트리핑 힘 {f_strip / 1000:,.1f} kN")
    add("펀치 플레이트", 1, "S50C", f"{Ld:.0f} × {Wd:.0f} × {tpp:.0f}", [pp], upper=True,
        note=f"펀치 끼워 맞춤 · 스프링 자리 Ø{spring.D + 1:g} 깊이 {spring.pocket:.1f}")
    add("펀치 받침판", 1, "SKD11 / S50C (열처리)", f"{Ld:.0f} × {Wd:.0f} × {tb:.0f}", [pb], upper=True)
    add("상형 다이 세트", 1, "SS400 (FC250)", f"{Ls:.0f} × {Ws:.0f} × {tus:.0f}", [upper_shoe], upper=True)

    # 가이드 포스트 · 부시 (다이 플레이트 바깥 네 귀) — 하형 세트 압입 구멍, 상형 세트 부시 구멍
    px, py = a + post_d / 2 + 15, b - post_d
    corners = [(sx * px, sy * py) for sx in (-1, 1) for sy in (-1, 1)]
    post_L = _up5(z_us - z_ls + 20)
    bush_o = post_d + 12
    for x, y in corners:
        lower.holes.append(Hole(x, y, post_d, "압입", z_ls, ts, f"Ø{post_d:g} H7 (포스트 압입) 관통"))
        upper_shoe.holes.append(Hole(x, y, bush_o, "압입", z_us, tus, f"Ø{bush_o:g} H7 (부시 압입) 관통"))
    add("가이드 포스트", 4, "SUJ2 HRC 60", f"Ø{post_d:g} × {post_L:.0f}",
        [Prim(CYL, (x, y, z_ls, post_d / 2, post_L)) for x, y in corners], std=True, note="압입",
        order=f"가이드 포스트 Ø{post_d:g} L{post_L:.0f} (압입형)")
    add("가이드 부시", 4, "SUJ2 / 동합금", f"Ø{post_d:g} 안 × Ø{bush_o:g} 밖 × {tus:.0f}",
        [Prim(CYL, (x, y, z_us, bush_o / 2, tus)) for x, y in corners], std=True, upper=True,
        order=f"가이드 부시 Ø{post_d:g} × Ø{bush_o:g} L{tus:.0f} (미끄럼 또는 볼)")

    # 펀치
    blank_ops = [P for P, k in ops if k == "blank"]
    pierce_ops = [P for P, k in ops if k == "pierce"]
    for P in blank_ops:
        pr = Prim(PRISM, (p_bot, p_len), poly=P)
        add("블랭킹 펀치", 1, "SKD11 HRC 58~62", f"{np.ptp(P[:, 0]):.1f} × {np.ptp(P[:, 1]):.1f} × {p_len:.1f}",
                 [pr], upper=True, note="외곽 = 블랭크 치수 (클리어런스는 다이 쪽) · 윗면 M 탭 2 로 받침판에 고정")
        for x, y, d in pilots:
            pd = round(d - 0.05, 2)
            pr.holes.append(Hole(x, y, pd, "H7", p_bot, p_len, f"Ø{pd:g} H7 관통 (파일럿)"))
    if pilots:
        pl = t + 1.5
        add("파일럿 핀", len(pilots), "SKH51 HRC 60~62", f"Ø{pilots[0][2] - 0.05:.2f} × {p_len + pl:.1f}",
            [Prim(CYL, (x, y, p_bot - pl, (d - 0.05) / 2, p_len + pl)) for x, y, d in pilots], std=True, upper=True,
            note=f"펀치 면에서 {pl:.1f} 나옴 (스트리퍼가 누르기 전에 구멍에 듦)",
            order=f"파일럿 핀 Ø{pilots[0][2] - 0.05:.2f} (구멍 −0.05)")
    groups = {}
    for P in pierce_ops:
        d, c = _circle_d(P)
        key = round(d, 2) if _is_round(P) else None
        groups.setdefault(key, []).append((P, c, d))
    lf = sgap + RETRACT                                   # 안내 없는 길이 (펀치 플레이트 ↔ 스트리퍼, 열림)
    tip_len = tst + RETRACT + s_w + REGRIND + 2           # 어깨 펀치 끝 (스트리퍼 안에서만 움직임)
    punch_sf = {}
    for key, hs in groups.items():
        if key is not None:
            f_p = math.pi * key * t * tau
            sf = math.pi ** 3 * 210000 * key ** 4 / 64 / (0.7 * lf) ** 2 / f_p
            body = key
            if sf < 3:                                    # 가는 펀치 → 어깨 펀치 (굵은 몸통)
                body = next(b_ for b_ in (6, 8, 10, 13, 16, 20, 25, 32) if b_ >= key + 2
                            and math.pi ** 3 * 210000 * b_ ** 4 / 64 / (0.7 * lf) ** 2 / f_p >= 3)
                sf = math.pi ** 3 * 210000 * body ** 4 / 64 / (0.7 * lf) ** 2 / f_p
            punch_sf[key] = (sf, body)
            dk = body + (3 if body < 10 else 4)
            kh = 5.0 if body < 13 else 8.0
            prims = []
            for _, c, d in hs:
                if body > key:
                    prims.append(Prim(CYL, (c[0], c[1], p_bot, d / 2, tip_len)))
                    prims.append(Prim(CYL, (c[0], c[1], p_bot + tip_len, body / 2, p_len - kh - tip_len)))
                else:
                    prims.append(Prim(CYL, (c[0], c[1], p_bot, d / 2, p_len - kh)))
                prims.append(Prim(CYL, (c[0], c[1], z_pb - kh, dk / 2, kh)))
                pp.holes.append(Hole(c[0], c[1], body, "H7", z_pp, tpp, f"Ø{body:g} H7 관통 (펀치)",
                                     cb=(dk + 0.5, z_pb - kh, kh)))
            std = key <= 32
            step = f", 어깨 Ø{body:g} · 끝 길이 {tip_len:.0f}" if body > key else ""
            add(f"피어싱 펀치 Ø{key:g}", len(hs), "SKH51 HRC 62~64",
                f"Ø{key:g} × {p_len:.1f} (머리 Ø{dk:g} × {kh:g}{step})",
                prims, std=std, upper=True, note="어깨 붙임 펀치 (좌굴)" if body > key else "머리 붙임 펀치",
                order=(f"{'어깨' if body > key else '머리'} 붙임 펀치 Ø{key:g} L{p_len:.1f} (길이 지정"
                       + (f", 몸통 Ø{body:g} 끝 {tip_len:.0f})" if body > key else ")")) if std else "")
        else:
            add("이형 피어싱 펀치", len(hs), "SKD11 HRC 58~62", f"구멍 모양 × {p_len:.1f}",
                [Prim(PRISM, (p_bot, p_len), poly=h) for h, _, _ in hs], upper=True, note="와이어 · 플랜지 붙여 고정")

    # 스트리퍼 볼트: 스트리퍼에 탭, 펀치 플레이트·받침판·상형 세트 통과, 머리는 상형 세트 윗면 카운터보어
    grip = sgap + tpp + tb + tus                          # 스트리퍼 윗면 ↔ 상형 세트 윗면
    need_cb = sb_k + s_w + REGRIND + 1                    # 머리 높이 + 움직임 + 재연마 + 여유
    sh_L = ds.down_std(grip - need_cb, ds.STRIPPER_L)
    cb_d = grip - sh_L                                    # 머리 자리 깊이 (머리 밑면 = 열림 때 자리 바닥)
    if cb_d > tus - 5:
        raise _NoRoom
    thr_through = sb_thr + 2 > tst
    for x, y in sb_xy:
        stripper.holes.append(Hole(x, y, ds.SHCS[sb_m][5], "탭", z_st + (0 if thr_through else tst - sb_thr - 2),
                                   tst if thr_through else sb_thr + 2,
                                   f"M{sb_m} 탭 " + ("관통" if thr_through else f"깊이 {sb_thr + 2:g}")))
        for pr_, z0, hh in ((pp, z_pp, tpp), (pb, z_pb, tb)):
            pr_.holes.append(Hole(x, y, sbd + 1, "통과", z0, hh, f"Ø{sbd + 1:g} 통과 (스트리퍼 볼트)"))
        upper_shoe.holes.append(Hole(x, y, sbd + 1, "통과", z_us, tus, f"Ø{sbd + 1:g} 통과, 자리 Ø{sb_dk + 1:g} 깊이 {cb_d:.1f}",
                                     cb=(sb_dk + 1, z_top - cb_d, cb_d)))
    add("스트리퍼 볼트", len(sb_xy), "SCM435", f"어깨 Ø{sbd:g} × {sh_L:.0f} (M{sb_m})",
        [Prim(CYL, (x, y, z_st + tst + sh_L, sb_dk / 2, sb_k)) for x, y in sb_xy]
        + [Prim(CYL, (x, y, z_st + tst, sbd / 2, sh_L)) for x, y in sb_xy]
        + [Prim(CYL, (x, y, z_st + tst - sb_thr, sb_m / 2, sb_thr)) for x, y in sb_xy],
        std=True, upper=True, order=f"스트리퍼 볼트 (ISO 7379) Ø{sbd:g} × {sh_L:.0f} M{sb_m}",
        note=f"머리 자리 깊이 {cb_d:.1f} (머리 {sb_k:g} + 움직임 {s_w:.1f} + 재연마 {REGRIND:g} + 1)")

    # 다이 스프링: 스트리퍼 윗면 ↔ 펀치 플레이트 자리 바닥
    sp_pr = []
    for x, y in sp_xy:
        pp.holes.append(Hole(x, y, spring.D + 1, "스프링 자리", z_pp, spring.pocket,
                             f"Ø{spring.D + 1:g} 깊이 {spring.pocket:.1f} (스프링 자리)", side="밑면"))
        sp_pr.append(Prim(CYL, (x, y, z_st + tst, spring.D / 2 - 0.5, spring.installed)))
    add("다이 스프링", spring.n, "SWOSC-V (ISO 10243)", f"{spring.label()}", sp_pr, std=True, upper=True,
        order=f"다이 스프링 ISO 10243 Ø{spring.D:g} × {spring.L:g} {spring.color}",
        note=f"끼움 눌림 {spring.preload:.1f} → 하사점 {spring.preload + s_w:.1f} (+재연마 {REGRIND:g}), "
             f"초기 {spring.f_pre / 1000:,.2f} kN · 최대 {spring.f_max / 1000:,.2f} kN")

    # 볼트: 하형 = 하형 세트 밑면 카운터보어 → 받침판 통과 → 다이 플레이트 탭, 상형 = 상형 세트 윗면 → 받침판 → 펀치 플레이트 탭
    def bolt_len(grip_, thick):
        want = grip_ + ds.ENGAGE * bolt
        L = ds.up_std(want, ds.SHCS_L)
        if L - grip_ > thick - 6:                          # 탭 깊이 (물림 + 3) 이 판을 뚫지 않게
            L = ds.down_std(grip_ + thick - 6, ds.SHCS_L)
        return L
    g_lo = ts - bcbh + tb
    L_lo = bolt_len(g_lo, H)
    g_up = tus - bcbh + tb
    L_up = bolt_len(g_up, tpp)
    for x, y in lb_xy:
        lower.holes.append(Hole(x, y, bd1, "통과", z_ls, ts, f"Ø{bd1:g} 통과, 자리 Ø{bcb:g} 깊이 {bcbh:g}",
                                cb=(bcb, z_ls, bcbh), side="밑면"))
        back.holes.append(Hole(x, y, bd1, "통과", z_bk, tb, f"Ø{bd1:g} 통과 (M{bolt})"))
        e = L_lo - g_lo
        die.holes.append(Hole(x, y, btap, "탭", z_die, e + 3, f"M{bolt} 탭 깊이 {e + 3:.0f} (드릴 Ø{btap:g})",
                              side="밑면"))
    for x, y in ub_xy:
        upper_shoe.holes.append(Hole(x, y, bd1, "통과", z_us, tus, f"Ø{bd1:g} 통과, 자리 Ø{bcb:g} 깊이 {bcbh:g}",
                                     cb=(bcb, z_top - bcbh, bcbh)))
        pb.holes.append(Hole(x, y, bd1, "통과", z_pb, tb, f"Ø{bd1:g} 통과 (M{bolt})"))
        e = L_up - g_up
        pp.holes.append(Hole(x, y, btap, "탭", z_pb - (e + 3), e + 3, f"M{bolt} 탭 깊이 {e + 3:.0f} (드릴 Ø{btap:g})"))
    add(f"육각 구멍 붙이 볼트 M{bolt} (하형)", len(lb_xy), "SCM435 (12.9)", f"M{bolt} × {L_lo:.0f}",
        [Prim(CYL, (x, y, z_ls + bcbh - bkh, bk / 2, bkh)) for x, y in lb_xy]
        + [Prim(CYL, (x, y, z_ls + bcbh, bolt / 2, L_lo)) for x, y in lb_xy], std=True,
        order=f"JIS B 1176 M{bolt} × {L_lo:.0f}", note=f"물림 {L_lo - g_lo:.0f} mm")
    add(f"육각 구멍 붙이 볼트 M{bolt} (상형)", len(ub_xy), "SCM435 (12.9)", f"M{bolt} × {L_up:.0f}",
        [Prim(CYL, (x, y, z_top - bcbh, bk / 2, bkh)) for x, y in ub_xy]
        + [Prim(CYL, (x, y, z_top - bcbh - L_up, bolt / 2, L_up)) for x, y in ub_xy], std=True, upper=True,
        order=f"JIS B 1176 M{bolt} × {L_up:.0f}", note=f"물림 {L_up - g_up:.0f} mm")

    # 다우얼 핀: H7 리머 — 하형 다이 플레이트·받침판 관통 + 하형 세트, 상형 펀치 플레이트·받침판 관통 + 상형 세트
    dl_lo = ds.up_std(H + tb + max(1.5 * dwd, 10), ds.DOWEL_L)
    dl_up = ds.up_std(tpp + tb + max(1.5 * dwd, 10), ds.DOWEL_L)
    for x, y in ld_xy:
        die.holes.append(Hole(x, y, dwd, "H7", z_die, H, f"Ø{dwd:g} H7 리머 관통 (다우얼)"))
        back.holes.append(Hole(x, y, dwd, "H7", z_bk, tb, f"Ø{dwd:g} H7 리머 관통 (다우얼)"))
        dd = dl_lo - H - tb + 2
        lower.holes.append(Hole(x, y, dwd, "H7", ts - dd, dd, f"Ø{dwd:g} H7 리머 깊이 {dd:.0f} (다우얼)"))
    for x, y in ud_xy:
        pp.holes.append(Hole(x, y, dwd, "H7", z_pp, tpp, f"Ø{dwd:g} H7 리머 관통 (다우얼)"))
        pb.holes.append(Hole(x, y, dwd, "H7", z_pb, tb, f"Ø{dwd:g} H7 리머 관통 (다우얼)"))
        dd = dl_up - tpp - tb + 2
        upper_shoe.holes.append(Hole(x, y, dwd, "H7", z_us, dd, f"Ø{dwd:g} H7 리머 깊이 {dd:.0f} (다우얼)",
                                     side="밑면"))
    add("다우얼 핀 (하형)", 2, "SUJ2 (m6)", f"Ø{dwd:g} × {dl_lo:.0f}",
        [Prim(CYL, (x, y, z_die_top - dl_lo, dwd / 2, dl_lo)) for x, y in ld_xy], std=True,
        order=f"평행 핀 ISO 8734 Ø{dwd:g} m6 × {dl_lo:.0f}")
    add("다우얼 핀 (상형)", 2, "SUJ2 (m6)", f"Ø{dwd:g} × {dl_up:.0f}",
        [Prim(CYL, (x, y, z_pp, dwd / 2, dl_up)) for x, y in ud_xy], std=True, upper=True,
        order=f"평행 핀 ISO 8734 Ø{dwd:g} m6 × {dl_up:.0f}")

    # 스트립 가이드 (다이 윗면, 스트립 양쪽) · 스트리퍼 밑면 홈
    gw, gh = 12.0, t + 1.0
    gd = gh - t + 1.0                                    # 스트리퍼 밑면 홈 깊이 (하사점에서 가이드가 1 들어옴)
    ys = Wst / 2 + 0.1
    rails = [Prim(BOX, (-a, s * ys + (0 if s > 0 else -gw), z_die_top, Ld, gw, gh)) for s in (-1, 1)]
    for s in (-1, 1):
        y0 = s * ys + (0 if s > 0 else -gw) - 0.5
        groove = np.array([[-a - 1, y0], [a + 1, y0], [a + 1, y0 + gw + 1], [-a - 1, y0 + gw + 1]])
        stripper.cuts.append((groove, 0.0, z_st - 1, gd + 1))
    add("스트립 가이드", 2, "S50C (HRC 40~45)", f"{Ld:.0f} × {gw:g} × {gh:g}", rails,
        note=f"스트립 폭 {Wst:.1f} + 0.2 · M5 볼트·Ø5 핀으로 다이에 · 스트리퍼 밑면 홈 {gw + 1:g} × {gd:g}")

    # 생크: 압력 중심
    cop = _cop(polys)
    cx_, cy_ = round(cop[0] * 2) / 2, round(cop[1] * 2) / 2
    if max(Ls, Ws) < 450:
        add("생크", 1, "S45C", "Ø38 × 60", [Prim(CYL, (cx_, cy_, z_top, 19.0, 60.0))], upper=True,
            note=f"압력 중심 ({cx_:+.1f}, {cy_:+.1f}) 위 · M16 탭 고정")
        upper_shoe.holes.append(Hole(cx_, cy_, 14.0, "탭", z_top - 24, 24, "M16 탭 깊이 24 (생크)"))

    # 하사점·높이
    travel = gap + RETRACT + ENTRY                       # 열림 → 하사점 상형 움직임
    shut = z_top - travel
    stroke = travel + t + 5                              # 스트립 들어 올림 · 이송 여유 5
    pierce_d = [k for k in groups if k is not None]
    checks = []

    def chk(item, val, crit, ok):
        checks.append([item, val, crit, "적합" if ok else "검토"])
    f_out = spring.n * spring.rate * (spring.preload + RETRACT)
    chk("스프링 힘 (펀치가 판에서 빠질 때) ≥ 스트리핑 힘", f"{f_out / 1000:,.2f} kN",
        f"≥ {f_strip / 1000:,.2f} kN ({STRIP_K * 100:g} % 절단력)"
        + (" — 모자람: 질소 가스 스프링 (ISO 11901) 으로" if gas else ""), f_out >= f_strip - 1e-6)
    chk("스프링 끝 휨 (재연마 포함)", f"{spring.defl_pct:.1f} %", f"≤ {spring.limit_pct:.1f} % (최대 × {ds.LIFE:g})",
        spring.defl_pct <= spring.limit_pct + 1e-6)
    chk("스트리퍼 ↔ 펀치 플레이트 틈 (하사점)", f"{sgap - s_w:.1f} mm", f"≥ {REGRIND:g} mm (재연마)", sgap - s_w >= REGRIND)
    chk("스트리퍼 볼트 머리 자리", f"깊이 {cb_d:.1f} mm", f"≥ {need_cb:.1f} (머리 + 움직임 + 재연마)", cb_d >= need_cb - 1e-6)
    for nm, L_, g_ in (("하형", L_lo, g_lo), ("상형", L_up, g_up)):
        chk(f"볼트 물림 ({nm} M{bolt} × {L_:.0f})", f"{L_ - g_:.1f} mm", f"≥ {ds.ENGAGE * bolt:.0f} (1.5 d)",
            L_ - g_ >= ds.ENGAGE * bolt - 1e-6)
    chk("펀치 진입 (하사점)", f"{ENTRY:g} mm", "0.5 ~ 1.5 mm", True)
    for d in pierce_d:
        sig = 4 * tau * t / d
        chk(f"피어싱 펀치 Ø{d:g} 압축 응력", f"{sig:,.0f} MPa", f"≤ {PUNCH_SIGMA:,.0f} (SKH51)", sig <= PUNCH_SIGMA)
        sf, body = punch_sf[d]
        chk(f"피어싱 펀치 Ø{d:g} 좌굴" + (f" (어깨 Ø{body:g})" if body > d else ""), f"안전율 {sf:,.1f}",
            f"≥ 3 (안내 없는 길이 {lf:.0f}, K 0.7)", sf >= 3)
    # 다이 벽: 날 사이 · 날 ↔ 다이 끝
    die_open = [_offset(P, clr) for P in polys]
    if len(die_open) > 1:
        w_min = max(1.5 * t, 2.0)
        g_min = min(_poly_gap(die_open[i], die_open[j])
                    for i in range(len(die_open)) for j in range(i + 1, len(die_open)))
        chk("다이 날 사이 벽 두께", f"{g_min:.1f} mm", f"≥ {w_min:.1f} (1.5 t, 최소 2) — 얇으면 빈 공정", g_min >= w_min)
    edge = min(min(a - abs(P[:, 0]).max(), b - abs(P[:, 1]).max()) for P in die_open)
    chk("날 ↔ 다이 끝 여유", f"{edge:.0f} mm", f"≥ {1.5 * H:.0f} (1.5 H)", edge >= 1.5 * H - 1e-6)
    off = math.hypot(*cop)
    chk("압력 중심 ↔ 금형 가운데", f"{off:.1f} mm", "생크를 압력 중심에 (옮김)" if max(Ls, Ws) < 450 else
        "큰 금형: 슬라이드 가운데와 맞춰 놓기", True)
    notes = [f"절단 길이 {L_cut:,.0f} mm × t {t:g} × τ {tau:.0f} MPa = 절단력 {F / 1000:,.1f} kN "
             f"(권장 프레스 {F * 1.3 / dc.TON:,.0f} tf)",
             f"다이 플레이트 두께 ∛(0.1 F) = {dc.die_plate_thickness(F):.1f} → {H:.0f} mm, 날 끝 여유 {m:.0f} mm",
             f"스트립 피치 {pitch:.1f} · 폭 {Wst:.1f} mm (이송 →)",
             f"높이: 열림 {z_top:.1f} · 하사점 (닫힌 높이) {shut:.1f} mm · 필요한 행정 ≥ {stroke:.0f} mm "
             f"(열림 {gap:.0f} + 스트리퍼 안 {RETRACT:g} + 진입 {ENTRY:g} + 들어 올림)",
             f"압력 중심 ({cop[0]:+.1f}, {cop[1]:+.1f}) mm (금형 가운데 기준)",
             "표준품 치수는 일반값 — 주문 전에 쓰는 업체 (MISUMI·Lesjöfors 등) 표로 확인, 스프링 상수는 Ø10 × 25 에서 닮은꼴 어림"]
    if plan is not None:
        notes.append("순차: 파일럿·피어싱 공정 구멍만 다이에 팠음 — 노칭·절곡·컷오프 인서트와 다음 공정 파일럿 핀은 "
                     "공정도를 보고 설계자가")
    return DieAssy(kind, parts, Ls, Ws, shut, F, notes, blank, holes, checks, cop, z_top, stroke, (pitch, Wst), spring)


# ---------------------------------------------------------------- 솔리드 · STEP

def _solid(pr: Prim):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakePrism,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    def prism(poly, z0, h, grow=0.0):
        P = _offset(poly, grow) if grow else np.asarray(poly, float)
        mk = BRepBuilderAPI_MakePolygon()
        for x, y in P:
            mk.Add(gp_Pnt(float(x), float(y), float(z0)))
        mk.Close()
        face = BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()
        return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(h))).Shape()

    def cyl(x, y, z0, r, h):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(float(x), float(y), float(z0)), gp_Dir(0, 0, 1)),
                                        float(r), float(h)).Shape()
    if pr.kind == BOX:
        x0, y0, z0, dx, dy, dz = pr.p
        s = BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), dx, dy, dz).Shape()
        z_lo, hh = z0, dz
    elif pr.kind == CYL:
        x, y, z0, r, h = pr.p
        s = cyl(x, y, z0, r, h)
        z_lo, hh = z0, h
    else:
        z0, h = pr.p
        s = prism(pr.poly, z0, h)
        z_lo, hh = z0, h
    tools = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(tools)
    n = 0
    for c in pr.cuts:
        poly, grow = c[0], c[1]
        zc, hc = (c[2], c[3]) if len(c) > 2 else (z_lo - 1, hh + 2)
        bld.Add(tools, prism(poly, zc, hc, grow))
        n += 1
    for h in pr.holes:
        # 막힌 구멍이 판 끝에 닿으면 조금 넘겨 깨끗이
        z0_, h_ = h.z0, h.h
        if abs(z0_ - z_lo) < 1e-6:
            z0_, h_ = z0_ - 0.5, h_ + 0.5
        if abs(h.z0 + h.h - (z_lo + hh)) < 1e-6:
            h_ += 0.5
        bld.Add(tools, cyl(h.x, h.y, z0_, h.d / 2, h_))
        n += 1
        if h.cb:
            D, zc, hc = h.cb
            if abs(zc - z_lo) < 1e-6:
                zc, hc = zc - 0.5, hc + 0.5
            if abs(zc + hc - (z_lo + hh)) < 1e-6:
                hc += 0.5
            bld.Add(tools, cyl(h.x, h.y, zc, D / 2, hc))
            n += 1
    if n:
        op = BRepAlgoAPI_Cut(s, tools)
        if op.IsDone():
            s = op.Shape()
    return s


def save_step(assy: DieAssy, path):
    """부품마다 이름 붙인 STEP (번호 · 품명)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for p in assy.parts:
        for k, pr in enumerate(p.prims, 1):
            lab = st.AddShape(_solid(pr), False)
            nm = f"{p.no:02d} {en_name(p.name)}" + (f" #{k}" if len(p.prims) > 1 else "")
            TDataStd_Name.Set_s(lab, TCollection_ExtendedString(nm))
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise ValueError("STEP 을 쓰지 못했습니다")
    return path


# ---------------------------------------------------------------- 2D 조립도 (평면도 + 정면도, 풍선)

COLORS = {"다이": (90, 140, 200), "펀치": (210, 120, 60), "스트리퍼": (120, 170, 110), "세트": (170, 170, 175),
          "표준": (230, 190, 70)}


def _color(p: DiePart):
    if p.std:
        return COLORS["표준"]
    for k, c in COLORS.items():
        if k in p.name:
            return c
    return (150, 160, 175)


def paint(p, rect, assy: DieAssy, title=True):
    """왼쪽 평면도 (하형을 위에서), 오른쪽 정면도 (판 쌓기, 열린 상태). 풍선 = 파트리스트 번호."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
    x0, y0, W, H = rect.x(), rect.y(), rect.width(), rect.height()
    top_h = 34 if title else 0
    if title:
        f = QFont()
        f.setPixelSize(int(max(12, H * 0.028)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x0, y0, W, top_h), Qt.AlignLeft | Qt.AlignVCenter,
                   f"금형 조립도 — {assy.kind} · {assy.L:.0f} × {assy.W:.0f} · 닫힌 높이 약 {assy.shut:.0f} mm")
    half = W * 0.5
    zmax = max(pr.p[2] + pr.p[5] if pr.kind == BOX else (pr.p[2] + pr.p[4] if pr.kind == CYL else pr.p[0] + pr.p[1])
               for part in assy.parts for pr in part.prims)
    balloons = []
    f = QFont()
    f.setPixelSize(int(max(9, H * 0.018)))
    p.setFont(f)
    # 평면도: 하형 (upper 아닌 것) + 펀치 위치 점선
    sx = (half - 40) / assy.L
    sy = (H - top_h - 60) / assy.W
    s = min(sx, sy)
    cx, cy = x0 + half / 2, y0 + top_h + (H - top_h) / 2

    def T(x, y):
        return QPointF(cx + x * s, cy - y * s)
    for part in assy.parts:
        col = QColor(*_color(part))
        for pr in part.prims:
            if part.upper and "펀치" not in part.name:
                continue
            pen = QPen(col.darker(150), 1.2, Qt.DashLine if part.upper else Qt.SolidLine)
            p.setPen(pen)
            p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 40 if part.upper else 90)))
            if pr.kind == BOX:
                bx, by, _, dx, dy, _ = pr.p
                p.drawRect(QRectF(T(bx, by + dy), T(bx + dx, by)))
                p.setBrush(QBrush(QColor(255, 255, 255)))
                for c in pr.cuts:
                    if len(c) > 2:
                        continue                           # 막힌 홈·빠짐 (그림에서는 날만)
                    P = _offset(c[0], c[1]) if c[1] else c[0]
                    p.drawPolygon(QPolygonF([T(*q) for q in P]))
                if part.name == "다이 플레이트":
                    for c in pr.cuts:
                        if len(c) > 2 and not c[1]:
                            p.drawPolygon(QPolygonF([T(*q) for q in c[0]]))
                    for h in pr.holes:
                        p.drawEllipse(T(h.x, h.y), h.d / 2 * s, h.d / 2 * s)
            elif pr.kind == CYL:
                x, y, _, r, _ = pr.p
                c = T(x, y)
                p.drawEllipse(c, r * s, r * s)
            else:
                p.drawPolygon(QPolygonF([T(*q) for q in pr.poly]))
        pr = part.prims[0]
        if pr.kind == CYL:
            at = T(pr.p[0], pr.p[1])
        elif pr.kind == BOX:
            if part.name not in ("하형 다이 세트", "다이 플레이트"):
                continue                                   # 받침판은 다이 플레이트 밑에 가려 보이지 않음
            at = T(pr.p[0] + 0.03 * pr.p[3], pr.p[1] + 0.85 * pr.p[4])
        else:
            at = T(*pr.poly.mean(0))
        if not part.upper or "펀치" in part.name:
            balloons.append((part.no, at, "top"))
    # 정면도: x-z (앞에서), 판은 사각형, 원기둥은 세로 사각형
    fx0 = x0 + half + 20
    sz = min((half - 150) / assy.L, (H - top_h - 60) / max(zmax, 1.0))
    bz = y0 + H - 30

    def Tf(x, zz):
        return QPointF(fx0 + (x + assy.L / 2) * sz, bz - zz * sz)
    for part in assy.parts:
        col = QColor(*_color(part))
        p.setPen(QPen(col.darker(160), 1.0))
        p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 140)))
        for pr in part.prims:
            if pr.kind == BOX:
                bx, _, z0, dx, _, dz = pr.p
                p.drawRect(QRectF(Tf(bx, z0 + dz), Tf(bx + dx, z0)))
            elif pr.kind == CYL:
                x, _, z0, r, h = pr.p
                p.drawRect(QRectF(Tf(x - r, z0 + h), Tf(x + r, z0)))
            else:
                z0, h = pr.p
                xs = pr.poly[:, 0]
                p.drawRect(QRectF(Tf(xs.min(), z0 + h), Tf(xs.max(), z0)))
        # 지시선이 그림을 가로지르지 않게 오른쪽 끝 (x 가 가장 큰) 프리미티브에 붙임
        def right(pr):
            return pr.p[0] + pr.p[3] if pr.kind in (BOX, CYL) else float(pr.poly[:, 0].max())
        pr = max(part.prims, key=right)
        if pr.kind == BOX:
            at = Tf(pr.p[0] + pr.p[3], pr.p[2] + pr.p[5] / 2)
        elif pr.kind == CYL:
            at = Tf(pr.p[0] + pr.p[3], pr.p[2] + pr.p[4] / 2)
        else:
            at = Tf(pr.poly[:, 0].max(), pr.p[0] + pr.p[1] / 2)
        balloons.append((part.no, at, "front"))
    # 풍선: 정면도는 오른쪽에 세로로, 평면도는 위쪽 가장자리로 끌어냄
    r = max(9.0, H * 0.017)
    fr = [b for b in balloons if b[2] == "front"]
    fr.sort(key=lambda b: b[1].y())                     # 위에서부터 — 지시선이 엇갈리지 않게
    xs_ = min(fx0 + assy.L * sz + 30, x0 + W - 3 * r)
    step = (H - top_h - 40) / max(len(fr), 1)
    for k, (no, at, _) in enumerate(fr):
        bpos = QPointF(xs_ + (k % 2) * 2.4 * r, y0 + top_h + 20 + k * step)
        _balloon(p, at, bpos, no, r)
    tp = [b for b in balloons if b[2] == "top"]
    tp.sort(key=lambda b: b[1].x())
    for k, (no, at, _) in enumerate(tp):
        bpos = QPointF(x0 + 30 + k * (half - 60) / max(len(tp) - 1, 1), y0 + top_h + 14 + (k % 2) * 2.4 * r)
        _balloon(p, at, bpos, no, r)


def _balloon(p, at, pos, no, r):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QPen
    p.setPen(QPen(QColor(40, 40, 40), 0.8))
    p.drawLine(at, pos)
    p.setBrush(QBrush(QColor(255, 255, 255)))
    p.drawEllipse(pos, r, r)
    p.drawText(QRectF(pos.x() - r, pos.y() - r, 2 * r, 2 * r), Qt.AlignCenter, str(no))


def render(assy: DieAssy, w=1800, h=900):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint(p, QRectF(10, 10, w - 20, h - 20), assy)
    p.end()
    return img


def save_xlsx(assy: DieAssy, path, name=""):
    import os

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from .report import _add_image
    wb = Workbook()
    ws = wb.active
    ws.title = "파트리스트"
    ws["A1"] = f"금형 파트리스트 — {name} · {assy.kind}"
    ws["A1"].font = Font(bold=True, size=13)
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")
    for j, hd in enumerate(HEAD, 1):
        c = ws.cell(3, j, hd)
        c.font, c.fill = hf, hfill
    for i, row in enumerate(assy.rows(), 4):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for col, wd in zip("ABCDEFGH", (6, 30, 6, 22, 30, 9, 10, 56)):
        ws.column_dimensions[col].width = wd
    r = 5 + len(assy.parts)
    for n in assy.notes:
        ws.cell(r, 1, "• " + n)
        r += 1
    ws2 = wb.create_sheet("조립도")
    tmp = _add_image(ws2, render(assy, 1800, 900), "A1", 1100)
    ws3 = wb.create_sheet("점검")
    for j, hd in enumerate(CHECK_HEAD, 1):
        c = ws3.cell(1, j, hd)
        c.font, c.fill = hf, hfill
    for i, row in enumerate(assy.checks, 2):
        for j, v in enumerate(row, 1):
            c = ws3.cell(i, j, v)
            if j == 4 and v != "적합":
                c.font = Font(bold=True, color="C00000")
    for col, wd in zip("ABCD", (40, 18, 46, 8)):
        ws3.column_dimensions[col].width = wd
    ws4 = wb.create_sheet("가공 구멍표")
    r = 1
    for j, hd in enumerate(HOLE_HEAD, 1):
        c = ws4.cell(r, j, hd)
        c.font, c.fill = hf, hfill
    for pname, rows in hole_tables(assy):
        r += 1
        ws4.cell(r, 1, pname).font = Font(bold=True)
        for row in rows:
            r += 1
            for j, v in enumerate(row, 1):
                ws4.cell(r, j, v)
    for col, wd in zip("ABCDEF", (22, 8, 10, 10, 10, 50)):
        ws4.column_dimensions[col].width = wd
    from .company import stamp_workbook
    stamp_workbook(wb)
    wb.save(path)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return path


def save_pdf(assy: DieAssy, path, name=""):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont

    from .process import _open_pdf
    pdf, p, R, k, W, H, m = _open_pdf(path, f"금형 조립도 {name}")
    paint(p, R(m, m, W - 2 * m, H * 0.62), assy)
    f = QFont()
    f.setPointSizeF(8.5)
    p.setFont(f)
    y = m + H * 0.64
    cols = [12, 66, 12, 48, 56, 16, 18, 168]
    x = m
    for wd, hd in zip(cols, HEAD):
        p.fillRect(R(x, y, wd, 6), QColor(31, 78, 140))
        p.setPen(QColor(255, 255, 255))
        p.drawText(R(x + 1, y, wd - 2, 6), Qt.AlignVCenter | Qt.AlignLeft, hd)
        x += wd
    p.setPen(QColor(20, 20, 20))
    y += 6
    for row in assy.rows():
        if y > H - m - 5:
            pdf.newPage()
            y = m
        x = m
        for wd, v in zip(cols, row):
            p.drawText(R(x + 1, y, wd - 2, 5), Qt.AlignVCenter | Qt.AlignLeft, str(v))
            x += wd
        y += 5
    for n in assy.notes:
        if y > H - m - 5:
            pdf.newPage()
            y = m
        p.drawText(R(m, y + 1, W - 2 * m, 5), Qt.AlignVCenter | Qt.AlignLeft, "• " + n)
        y += 5
    # 점검표
    pdf.newPage()
    f.setPointSizeF(10)
    f.setBold(True)
    p.setFont(f)
    p.drawText(R(m, m, W - 2 * m, 8), Qt.AlignVCenter | Qt.AlignLeft, f"금형 점검 — {name} · {assy.kind}")
    f.setBold(False)
    f.setPointSizeF(8.5)
    p.setFont(f)
    y = m + 10
    cols = [120, 50, 140, 25]
    _row(p, R, m, y, cols, CHECK_HEAD, head=True)
    for row in assy.checks:
        y += 6
        _row(p, R, m, y, cols, row, bad=row[3] != "적합")
    # 판마다 가공도
    for part in assy.parts:
        if part.name in PLATES:
            pdf.newPage()
            _plate_page(p, R, k, W, H, m, assy, part, name)
    p.end()
    return path


def _row(p, R, x, y, cols, row, head=False, bad=False):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    for wd, v in zip(cols, row):
        if head:
            p.fillRect(R(x, y, wd, 6), QColor(31, 78, 140))
        p.setPen(QColor(255, 255, 255) if head else QColor(192, 0, 0) if bad and v == row[-1] else QColor(20, 20, 20))
        p.drawText(R(x + 1, y, wd - 2, 6), Qt.AlignVCenter | Qt.AlignLeft, str(v))
        x += wd


def _plate_page(p, R, k, W, H, m, assy, part, name):
    """판 하나의 가공도: 윗면에서 본 외곽·날·구멍 (기호), 원점 = 왼쪽 아래 귀, 오른쪽에 구멍표."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QFont, QPen, QPolygonF
    pr = part.prims[0]
    x0, y0, z0, dx, dy, dz = pr.p
    f = QFont()
    f.setPointSizeF(11)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(20, 20, 20))
    p.drawText(R(m, m, W - 2 * m, 8), Qt.AlignVCenter | Qt.AlignLeft,
               f"부품도 {part.no:02d} {part.name} — {part.size} · {part.material} · {name}")
    area_w, area_h = W * 0.58, H - 3 * m - 10
    s = min(area_w / dx, area_h / dy)
    ox, oy = m, m + 14 + dy * s      # 왼쪽 아래 (mm, 종이)

    def T(x, y):
        return QPointF((ox + (x - x0) * s) * k, (oy - (y - y0) * s) * k)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0), 0.35 * k))
    p.drawPolygon(QPolygonF([T(x0, y0), T(x0 + dx, y0), T(x0 + dx, y0 + dy), T(x0, y0 + dy)]))
    for c in pr.cuts:
        P = _offset(c[0], c[1]) if c[1] else c[0]
        blind = len(c) > 2 and (c[2] > z0 + 1e-6 or c[2] + c[3] < z0 + dz - 1e-6) and not (len(c) > 2 and c[1])
        relief = len(c) > 2 and c[1]
        p.setPen(QPen(QColor(200, 0, 0) if not blind else QColor(0, 120, 0), 0.3 * k,
                      Qt.DashLine if relief or blind else Qt.SolidLine))
        P2 = np.clip(P, [x0, y0], [x0 + dx, y0 + dy])
        p.drawPolygon(QPolygonF([T(*q) for q in P2]))
    f.setPointSizeF(6.5)
    f.setBold(False)
    p.setFont(f)
    tab = hole_table(part)
    for sym, kind, cnt, pts, spec in tab:
        for i, (hx, hy, h) in enumerate(pts, 1):
            c = T(hx, hy)
            col = QColor(0, 0, 200) if h.kind == "탭" else QColor(0, 120, 0) if h.kind == "H7" else QColor(0, 0, 0)
            p.setPen(QPen(col, 0.25 * k))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, h.d / 2 * s * k, h.d / 2 * s * k)
            if h.cb:
                p.setPen(QPen(col, 0.2 * k, Qt.DashLine))
                p.drawEllipse(c, h.cb[0] / 2 * s * k, h.cb[0] / 2 * s * k)
            p.setPen(QColor(20, 20, 20))
            p.drawText(QPointF(c.x() + (h.d / 2 * s + 0.8) * k, c.y() - 0.8 * k), f"{sym}{i}")
    # 원점 표시
    p.setPen(QPen(QColor(0, 0, 0), 0.3 * k))
    o = T(x0, y0)
    p.drawText(QPointF(o.x() - 2 * k, o.y() + 4 * k), "0,0")
    # 구멍표
    tx = m + area_w + 10
    ty = m + 14
    cols = [12, 10, 22, 22, 70]
    _row(p, R, tx, ty, cols, ["기호", "번호", "X", "Y", "가공"], head=True)
    for sym, kind, cnt, pts, spec in tab:
        for i, (hx, hy, h) in enumerate(pts, 1):
            ty += 4.2
            if ty > H - m - 5:
                break
            _row(p, R, tx, ty, cols, [sym if i == 1 else "", i, f"{hx - x0:.2f}", f"{hy - y0:.2f}",
                                      (spec + (f" ({h.side})" if h.side != "윗면" else "")) if i == 1 else ""])
    ty += 8
    for c in pr.cuts:
        if len(c) > 2 and c[1]:
            p.drawText(R(tx, ty, 140, 5), Qt.AlignLeft, "날: 와이어 — 위 랜드 곧게, 아래 한쪽 +0.5 빠짐 (점선)")
            ty += 5
            break
    p.drawText(R(tx, ty, 140, 5), Qt.AlignLeft, f"두께 {dz:g} · 위·아래 면 연삭 · 원점 = 왼쪽 아래 귀 (윗면에서 봄)")


HOLE_HEAD = ["판 / 기호", "번호", "X", "Y", "지름", "가공"]
SYMS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def hole_table(part):
    """판의 구멍을 같은 가공끼리 묶어 기호 (A, B, …) — [(기호, 종류, 개수, [(x, y, Hole)], 가공 지시)]."""
    pr = part.prims[0]
    groups = {}
    for h in pr.holes:
        groups.setdefault((h.spec, h.side), []).append(h)
    out = []
    for i, ((spec, _side), hs) in enumerate(sorted(groups.items(), key=lambda kv: -kv[1][0].d)):
        hs = sorted(hs, key=lambda h: (round(h.y, 1), h.x))
        out.append((SYMS[i % len(SYMS)], hs[0].kind, len(hs), [(h.x, h.y, h) for h in hs], spec))
    return out


def hole_tables(assy):
    """엑셀용: 판마다 [기호, 번호, X, Y, 지름, 가공] (원점 = 판 왼쪽 아래 귀)."""
    out = []
    for part in assy.parts:
        if part.name not in PLATES:
            continue
        x0, y0 = part.prims[0].p[0], part.prims[0].p[1]
        rows = []
        for sym, kind, cnt, pts, spec in hole_table(part):
            for i, (hx, hy, h) in enumerate(pts, 1):
                rows.append([sym, i, round(hx - x0, 2), round(hy - y0, 2), h.d,
                             spec + (f" ({h.side})" if h.side != "윗면" else "") if i == 1 else ""])
        out.append((f"{part.no:02d} {part.name}", rows))
    return out


def save_dxf(assy: DieAssy, path):
    """판마다 가공도 DXF — 판을 옆으로 늘어놓고, 판마다 원점 = 왼쪽 아래 귀.
    레이어: CONTOUR (외곽) · WIRE (날·이형 펀치 자리 — 와이어) · RELIEF (빠짐) · POCKET (막힌 홈) · DRILL (통과·드릴) ·
    TAP · REAM (H7) · CBORE (카운터보어) · TEXT."""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for nm, col in (("CONTOUR", 7), ("WIRE", 1), ("RELIEF", 6), ("POCKET", 3), ("DRILL", 7), ("TAP", 5),
                    ("REAM", 3), ("CBORE", 4), ("TEXT", 2)):
        doc.layers.add(nm, color=col)
    msp = doc.modelspace()
    ox = 0.0
    for part in assy.parts:
        if part.name not in PLATES:
            continue
        pr = part.prims[0]
        x0, y0, z0, dx, dy, dz = pr.p

        def T(x, y, ox=ox, x0=x0, y0=y0):
            return (ox + x - x0, y - y0)
        msp.add_lwpolyline([T(x0, y0), T(x0 + dx, y0), T(x0 + dx, y0 + dy), T(x0, y0 + dy)], close=True,
                           dxfattribs={"layer": "CONTOUR"})
        for c in pr.cuts:
            P = _offset(c[0], c[1]) if c[1] else np.asarray(c[0], float)
            P = np.clip(P, [x0, y0], [x0 + dx, y0 + dy])
            if len(c) > 2 and c[1]:
                lay = "RELIEF"
            elif len(c) > 2 and (c[2] > z0 + 1e-6 or c[2] + c[3] < z0 + dz - 1e-6):
                lay = "POCKET"
            else:
                lay = "WIRE"
            msp.add_lwpolyline([T(*q) for q in P], close=True, dxfattribs={"layer": lay})
        ty = -12.0
        for sym, kind, cnt, pts, spec in hole_table(part):
            lay = "TAP" if kind == "탭" else "REAM" if kind == "H7" else "DRILL"
            for i, (hx, hy, h) in enumerate(pts, 1):
                msp.add_circle(T(hx, hy), h.d / 2, dxfattribs={"layer": lay})
                if h.cb:
                    msp.add_circle(T(hx, hy), h.cb[0] / 2, dxfattribs={"layer": "CBORE"})
                msp.add_text(f"{sym}{i}", height=2.5, dxfattribs={"layer": "TEXT"}).set_placement(
                    (T(hx, hy)[0] + h.d / 2 + 1, T(hx, hy)[1] + 1))
            side = f" ({pts[0][2].side})" if pts[0][2].side != "윗면" else ""
            msp.add_text(f"{sym} x{cnt}: {spec}{side}", height=3.0, dxfattribs={"layer": "TEXT"}).set_placement(
                (ox, ty))
            ty -= 5.0
        msp.add_text(f"{part.no:02d} {part.name}  {part.size}  {part.material}", height=5.0,
                     dxfattribs={"layer": "TEXT"}).set_placement((ox, dy + 6))
        ox += dx + 60
    doc.saveas(path)
    return path
