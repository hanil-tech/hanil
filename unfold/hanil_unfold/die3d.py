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

BOX, CYL, PRISM, PROF = "box", "cyl", "prism", "prof"   # prof: 옆 단면 (x, z) 을 y 로 민 것 (절곡 다이·펀치)
STRIP_K = 0.07        # 스트리핑 힘 / 절단력 (교재 2 ~ 20 %, 보통 5 ~ 10 %)
ENTRY = 1.0           # 닫힘에서 펀치가 다이 안으로 들어가는 깊이
RETRACT = 1.0         # 열림에서 펀치 끝이 스트리퍼 안으로 들어가 있는 깊이
REGRIND = 3.0         # 펀치·다이 재연마 여유 (스프링·스트리퍼 볼트 자리)
DENSITY = 7.85e-6     # kg/mm³ (강)
PUNCH_SIGMA = 1500.0  # 피어싱 펀치 허용 압축 응력 MPa (SKH51 어림)
# 파단까지 펀치가 들어가는 깊이 / t (전단 에너지 W = F · t · k) — 무를수록 깊게 (교재 어림: 연강 0.4~0.6, 경강 0.2~0.3)
PENETRATION = [(300, 0.55), (450, 0.45), (600, 0.38), (800, 0.30), (1200, 0.22), (1e9, 0.15)]


def penetration(mat):
    for ts, k in PENETRATION:
        if mat.tensile_mpa < ts:
            return k
    return 0.15
# STEP 안의 부품 이름 (영문 — 한글은 CAD 마다 STEP 문자 인코딩이 달라 깨짐)
EN = {"하형 다이 세트": "LOWER DIE SET", "다이 받침판": "DIE BACKING PLATE", "다이 플레이트": "DIE PLATE",
      "스트리퍼 플레이트": "STRIPPER PLATE", "펀치 플레이트": "PUNCH PLATE", "펀치 받침판": "PUNCH BACKING PLATE",
      "상형 다이 세트": "UPPER DIE SET", "가이드 포스트": "GUIDE POST", "가이드 부시": "GUIDE BUSH",
      "블랭킹 펀치": "BLANKING PUNCH", "피어싱 펀치": "PIERCE PUNCH", "이형 피어싱 펀치": "SHAPED PIERCE PUNCH",
      "스트리퍼 볼트": "STRIPPER BOLT", "다이 스프링": "DIE SPRING", "육각 구멍 붙이 볼트": "SOCKET HEAD BOLT",
      "다우얼 핀": "DOWEL PIN", "생크": "SHANK", "파일럿 핀": "PILOT PIN", "스트립 가이드": "STRIP GUIDE",
      "스톱 블록": "STOP BLOCK", "(펀치 고정)": "(PUNCH FIX)", "(스트립 가이드)": "(STRIP GUIDE)",
      "(스톱 블록)": "(STOP BLOCK)", "(하형)": "(LOWER)", "(상형)": "(UPPER)"}
PLATES = ("하형 다이 세트", "다이 받침판", "다이 플레이트", "스트리퍼 플레이트", "펀치 플레이트", "펀치 받침판", "상형 다이 세트")


def en_name(name):
    out = name
    for k in sorted(EN, key=len, reverse=True):
        out = out.replace(k, EN[k])
    # 표에 없는 한글이 남으면 STEP 에서 깨지므로 빼고 PART 로
    out = "".join(ch if ord(ch) < 128 else " " for ch in out)
    out = " ".join(out.split())
    return out or "PART"


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
    axis: str = "z"               # "z" 세로 (z0 · h) · "+y" "-y" "+x" "-x" 옆면에서 안으로 (x, y = 옆면 위 점, z0 = 높이, h = 깊이)


@dataclass
class Prim:
    kind: str
    p: tuple                      # box: (x0, y0, z0, dx, dy, dz) · cyl: (x, y, z0, r, h) · prism: (z0, h) · prof: (y0, 길이)
    poly: np.ndarray | None = None   # prism 의 2D 다각형 (x, y) · prof 의 옆 단면 (x, z)
    cuts: list = field(default_factory=list)   # 빼낼 프리즘 [(다각형, 넓힘[, z0, 깊이])] — z 없으면 관통
    holes: list = field(default_factory=list)  # 둥근 구멍 [Hole]
    # 둥근 표준품의 실제 모양 (cyl 만): 아래부터 [(z0, 높이, 아래 반지름, 위 반지름)] 을 돌려 만든 솔리드,
    # bore = 안 구멍 반지름 (스프링·부시), socket = 육각 구멍 (면 z, 깊이, 맞변 s, +1 위로 / −1 아래로 판다)
    stack: list = field(default_factory=list)
    bore: float = 0.0
    socket: tuple | None = None
    ax: str = "y"                 # prof 를 미는 방향: "y" (단면 x-z, p = (y0, 길이)) · "x" (단면 y-z, p = (x0, 길이))


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
    edges: list = field(default_factory=list)      # 날 치수표
    press: dict = field(default_factory=dict)      # 프레스 하중·에너지·고른 프레스
    usage: dict = field(default_factory=dict)      # 스트립 재료 이용
    stations: list = field(default_factory=list)   # [(이름, 가운데 x, 그 공정 부품 외곽)]
    spec: list = field(default_factory=list)       # 표지 사양 줄 [(이름, 값)] (절곡 금형 등 — 없으면 전단 금형 꼴)
    work: list = field(default_factory=list)       # 금형 안 제품 선 [(3D 꺾은선, "before"/"after")] (절곡 금형)

    def rows(self):
        return [[p.no, p.name, p.qty, p.material, p.size, "표준품" if p.std else "가공품",
                 round(p.weight, 2), p.order or p.note if p.std else p.note] for p in self.parts]

    def plate(self, name):
        return next(p for p in self.parts if p.name == name)


HEAD = ["번호", "품명", "수량", "재질", "크기 (mm)", "구분", "단중 (kg)", "비고 · 주문 규격"]
CHECK_HEAD = ["점검 항목", "값", "기준", "판정"]
EDGE_HEAD = ["날", "호칭 (mm)", "일반 공차", "마모 계수 x", "한쪽 옮김", "다이 날", "펀치", "한쪽 클리어런스"]


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


def _deep_point(P, n=30):
    """다각형 안 경계에서 가장 먼 점 (격자 찾기)."""
    P = np.asarray(P, float)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    best, bd = None, 0.0
    for x in np.linspace(x0, x1, n):
        for y in np.linspace(y0, y1, n):
            d = -_dist(P, (x, y))
            if d > bd:
                best, bd = (float(x), float(y)), d
    return best


def _inner_pair(P, inset, avoid, r, n=28):
    """다각형 안 (경계에서 inset 이상) 의 서로 먼 두 점, avoid [(x, y, r)] 와 r + 3 이상 떨어짐."""
    P = np.asarray(P, float)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    cand = []
    for x in np.linspace(x0, x1, n):
        for y in np.linspace(y0, y1, n):
            if -_dist(P, (x, y)) >= inset and all(math.hypot(x - ax, y - ay) >= ar + r + 3 for ax, ay, ar in avoid):
                cand.append((float(x), float(y)))
    if len(cand) < 2:
        return cand[:1]
    C = np.array(cand)
    D = np.linalg.norm(C[:, None] - C[None], axis=2)
    i, j = np.unravel_index(np.argmax(D), D.shape)
    return [cand[i], cand[j]]


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


def extent(pr: Prim):
    """(x0, y0, z0, dx, dy, dz) — 프리미티브를 둘러싼 상자."""
    if pr.kind == BOX:
        return tuple(pr.p)
    if pr.kind == CYL:
        x, y, z0, r, h = pr.p
        return x - r, y - r, z0, 2 * r, 2 * r, h
    P = np.asarray(pr.poly, float)
    if pr.kind == PROF:
        (a0, z0), (a1, z1) = P.min(0), P.max(0)
        if pr.ax == "x":
            return pr.p[0], a0, z0, pr.p[1], a1 - a0, z1 - z0
        return a0, pr.p[0], z0, a1 - a0, pr.p[1], z1 - z0
    (x0, y0), (x1, y1) = P.min(0), P.max(0)
    return x0, y0, pr.p[0], x1 - x0, y1 - y0, pr.p[1]


def _volume(pr: Prim):
    if pr.kind == BOX:
        v = pr.p[3] * pr.p[4] * pr.p[5]
        h_all = pr.p[5]
    elif pr.kind == CYL:
        if pr.stack:
            v = sum(math.pi * h_ / 3 * (r0 * r0 + r0 * r1 + r1 * r1) for _, h_, r0, r1 in pr.stack)
            if pr.socket:                                   # 육각 구멍 (맞변 s, 깊이)
                v -= math.sqrt(3) / 2 * pr.socket[2] ** 2 * pr.socket[1]
            return max(v - math.pi * pr.bore ** 2 * pr.p[4], 0.0)
        return math.pi * pr.p[3] ** 2 * pr.p[4]
    elif pr.kind == PROF:
        v = abs(_area(pr.poly)) * pr.p[1]
        h_all = float(np.ptp(np.asarray(pr.poly)[:, 1]))
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
        stations = []
        for i, s in enumerate(plan.stations):
            dx = (i - (n_st - 1) / 2) * P - cx
            for k in getattr(s, "holes", []) or []:
                ops.append((plan.holes[k] + np.array([dx, -cy]), "pierce"))
            stations.append((f"S{s.no} {s.title}", (i - (n_st - 1) / 2) * P, plan.outer + np.array([dx, -cy])))
        _layout.stations = stations
        return ops, pil, (n_st * P, plan.strip_width), (P, plan.strip_width), f"순차 ({n_st} 공정)", blank, holes
    W = float(np.ptp(blank[:, 1]))
    L = float(np.ptp(blank[:, 0]))
    Wst = W + 2 * side
    if not holes:
        P = L + max(1.5 * t, 1.5)
        _layout.stations = [("S1 블랭킹", 0.0, blank)]
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
    _layout.stations = [("S1 피어싱", -P / 2, blank + sh1), ("S2 블랭킹", P / 2, blank + sh2)]
    return ops, pil, (P + L, Wst), (P, Wst), "2 공정 (피어싱 → 블랭킹)", blank, holes


def build(result, settings: bc.BendSettings, kind=None, plan=None, tol="m", machines=None):
    """전개 결과 하나의 금형 조립. plan: 순차 금형 공정도 (process.ProcessPlan) — 있으면 스트립 길이·공정 자리로.
    tol: 일반 공차 등급 (ISO 2768 f / m / c) — 날 치수 (마모 여유) 에. machines: 프레스 목록 (costing 꼴, 없으면 예시)."""
    t = result.thickness
    ops, pilots, work, strip, kname, blank, holes = _layout(result, t, plan)
    # 압력 중심이 금형 가운데 (프레스 슬라이드 가운데) 에 오게 이송 방향으로 옮김
    sx = -_cop([P for P, _ in ops])[0]
    ops = [(P + np.array([sx, 0.0]), k_) for P, k_ in ops]
    stations = [(nm, x + sx, Q + np.array([sx, 0.0])) for nm, x, Q in _layout.stations]
    pilots = [(x + sx, y, d) for x, y, d in pilots]
    half = max(float(np.abs(np.vstack([P for P, _ in ops])[:, 0]).max()), work[0] / 2)
    work = (2 * half, work[1])
    for k in range(8):
        try:
            assy = _assemble(result, settings, kind or kname, plan, t, ops, pilots, work, strip, blank, holes,
                             extra=10.0 * k, tol=tol, machines=machines)
            assy.stations = stations
            return assy
        except _NoRoom:
            continue
    raise ValueError("표준 부품 자리를 못 찾았습니다 (여유 70 mm 넓혀도) — 손으로 배치하세요")


def _assemble(result, settings, kind, plan, t, ops, pilots, work, strip, blank, holes, extra=0.0, tol="m",
              machines=None, nest=None, fit=None, outer=None, depth_below=0.0, up_h=0.0):
    """fit: 다이 쌓기 판 (다이·받침·스트리퍼·펀치 판) 크기 (L, W) 고정 — 후 피어싱 (접은 제품 안쪽에 들어가는 다이).
    outer: 금형 안 제품 바깥 크기 (L, W) — 가이드 포스트 · 스톱 블록을 그 밖으로. depth_below: 다이 윗면 아래로 내려간
    플랜지 깊이 (받침판을 그만큼 높임), up_h: 위로 선 높이 (점검)."""
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
    if fit is not None:
        Ld, Wd = float(fit[0]), float(fit[1])
    a, b = Ld / 2, Wd / 2
    oL, oW = (max(Ld, outer[0] + 30), max(Wd, outer[1] + 30)) if outer is not None else (Ld, Wd)
    a_out = oL / 2
    post_d = 25.0 if max(oL, oW) < 250 else 32.0 if max(oL, oW) < 450 else 38.0
    Ls, Ws = _up5(oL + 2 * (post_d + 35)), _up5(oW + 20)
    ts = max(40.0, _up5(0.08 * max(Ls, Ws)))
    tus = ts - 5
    bolt = ds.bolt_for(max(Ld, Wd))
    H = max(H, _up5(ds.ENGAGE * bolt + 6))               # 다이·펀치 플레이트에 볼트 탭 (물림 1.5 d + 3, 바닥 3)
    tb, tpp, tst = 10.0, max(20.0, _up5(0.8 * H), _up5(ds.ENGAGE * bolt + 6)), max(15.0, _up5(0.6 * H))
    if depth_below > 0:
        tb = max(tb, _up5(depth_below + 8 - H))             # 아래로 접힌 플랜지 끝이 하형 세트에 닿지 않게
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
    # 날 치수 (마모 여유): 블랭킹 — 다이 = 최대 − xΔ, 펀치 = 다이 − 2c / 피어싱 — 펀치 = 최소 + xΔ, 다이 = 펀치 + 2c
    edges = []
    punch_of = {}
    for i, (P, k) in enumerate(ops):
        blank_ = k == "blank"
        rnd = _is_round(P)
        nom = _circle_d(P)[0] if rnd and not blank_ else float(max(np.ptp(P[:, 0]), np.ptp(P[:, 1])))
        T, dl, x, sh = ds.size_edges(nom, t, tol, blank=blank_)
        Pd = _offset(P, sh + (0.0 if blank_ else clr))   # 다이 날
        Pp = _offset(P, sh - (clr if blank_ else 0.0))   # 펀치
        punch_of[i] = Pp
        def dims(Q, rnd=rnd, blank_=blank_):
            return f"Ø{_circle_d(Q)[0]:.3f}" if rnd and not blank_ else f"{np.ptp(Q[:, 0]):.3f} × {np.ptp(Q[:, 1]):.3f}"
        edges.append(["블랭킹 (외곽)" if blank_ else "피어싱", dims(P), f"±{T:g} ({tol})", f"{x:g}",
                      f"{sh:+.3f}", dims(Pd), dims(Pp), f"{clr:.3f}"])
        die.cuts.append((Pd, 0.0, z_die_top - land, land + 1))
        die.cuts.append((Pd, 0.5, z_die - 1, H - land + 1))
        back.cuts.append((Pd, 1.0))
        lower.cuts.append((Pd, 2.0))
        stripper.cuts.append((Pp, 0.05))          # 펀치 안내 (블랭킹 펀치도)
        if not (k == "pierce" and rnd):
            pp.cuts.append((Pp, 0.0))             # 펀치 고정 (끼워 맞춤) — 둥근 펀치는 H7 구멍으로

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
    # 볼트 개수: 상형 볼트가 스트리핑 힘을 되풀이 허용 응력 안에서 (4 → 6 → 8)
    n_b = 4
    while n_b < 8 and f_strip / (n_b * ds.STRESS_AREA[bolt]) > ds.BOLT_ALLOW:
        n_b += 2
    b_t = [(sx * a, sy * b * 0.45) for sx in (-1, 1) for sy in (-1, 1)]
    if n_b >= 6:
        b_t += [(0.0, sy * b) for sy in (-1, 1)]
    if n_b >= 8:
        b_t += [(sx * a, 0.0) for sx in (-1, 1)]
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
    px, py = a_out + post_d / 2 + 15, (b if outer is None else Ws / 2 - 10) - post_d
    corners = [(sx * px, sy * py) for sx in (-1, 1) for sy in (-1, 1)]
    post_L = _up5(z_us - z_ls + 20)
    bush_o = post_d + 12
    for x, y in corners:
        lower.holes.append(Hole(x, y, post_d, "압입", z_ls, ts, f"Ø{post_d:g} H7 (포스트 압입) 관통"))
        upper_shoe.holes.append(Hole(x, y, bush_o, "압입", z_us, tus, f"Ø{bush_o:g} H7 (부시 압입) 관통"))
    add("가이드 포스트", 4, "SUJ2 HRC 60", f"Ø{post_d:g} × {post_L:.0f}",
        [axi(x, y, [(z_ls, post_L - 2, post_d / 2, post_d / 2), (z_ls + post_L - 2, 2, post_d / 2, post_d / 2 - 1.5)])
         for x, y in corners], std=True, note="압입 · 끝 모따기",
        order=f"가이드 포스트 Ø{post_d:g} L{post_L:.0f} (압입형)")
    add("가이드 부시", 4, "SUJ2 / 동합금", f"Ø{post_d:g} 안 × Ø{bush_o:g} 밖 × {tus:.0f}",
        [axi(x, y, [(z_us, tus, bush_o / 2, bush_o / 2)], bore=post_d / 2) for x, y in corners], std=True, upper=True,
        order=f"가이드 부시 Ø{post_d:g} × Ø{bush_o:g} L{tus:.0f} (미끄럼 또는 볼)")

    # 펀치
    blank_ops = [punch_of[i] for i, (P, k) in enumerate(ops) if k == "blank"]
    pierce_ops = [(P, punch_of[i]) for i, (P, k) in enumerate(ops) if k == "pierce"]
    # 파일럿: 뚫린 구멍 = 피어싱 펀치 지름 → 파일럿 = 그 − 0.05
    pil_d = {}
    for (P, Pp) in pierce_ops:
        if _is_round(P):
            pil_d[round(_circle_d(P)[0], 2)] = _circle_d(Pp)[0]
    pilots = [(x, y, pil_d.get(round(d, 2), d)) for x, y, d in pilots]
    blank_punches = []
    for P in blank_ops:
        pr = Prim(PRISM, (p_bot, p_len), poly=P)
        blank_punches.append(add("블랭킹 펀치", 1, "SKD11 HRC 58~62",
                                 f"{np.ptp(P[:, 0]):.1f} × {np.ptp(P[:, 1]):.1f} × {p_len:.1f}", [pr], upper=True,
                                 note="외곽 = 블랭크 치수 − 2c (클리어런스는 다이 쪽) · 윗면 탭으로 상형 세트에 고정"))
        for x, y, d in pilots:
            pd = round(d - 0.05, 2)
            pr.holes.append(Hole(x, y, pd, "H7", p_bot, p_len, f"Ø{pd:g} H7 관통 (파일럿)"))
    if pilots:
        pl = t + 1.5
        add("파일럿 핀", len(pilots), "SKH51 HRC 60~62", f"Ø{pilots[0][2] - 0.05:.2f} × {p_len + pl:.1f}",
            [axi(x, y, [(p_bot - pl, min(pl, 0.8 * (d - 0.05)), 0.35 * (d - 0.05), (d - 0.05) / 2),
                        (p_bot - pl + min(pl, 0.8 * (d - 0.05)), p_len + pl - min(pl, 0.8 * (d - 0.05)),
                         (d - 0.05) / 2, (d - 0.05) / 2)]) for x, y, d in pilots], std=True, upper=True,
            note=f"펀치 면에서 {pl:.1f} 나옴 (스트리퍼가 누르기 전에 구멍에 듦)",
            order=f"파일럿 핀 Ø{pilots[0][2] - 0.05:.2f} (구멍 −0.05)")
    groups = {}
    for P0, P in pierce_ops:
        d, c = _circle_d(P)
        key = round(_circle_d(P0)[0], 2) if _is_round(P0) else None      # 구멍 호칭
        groups.setdefault(key, []).append((P, c, d))
    lf = sgap + RETRACT                                   # 안내 없는 길이 (펀치 플레이트 ↔ 스트리퍼, 열림)
    tip_len = tst + RETRACT + s_w + REGRIND + 2           # 어깨 펀치 끝 (스트리퍼 안에서만 움직임)
    punch_sf = {}
    for key, hs in groups.items():
        if key is not None:
            dp = round(hs[0][2], 3)                       # 펀치 지름 (마모 여유 넣음)
            f_p = math.pi * key * t * tau
            sf = math.pi ** 3 * 210000 * dp ** 4 / 64 / (0.7 * lf) ** 2 / f_p
            body = dp
            if sf < 3:                                    # 가는 펀치 → 어깨 펀치 (굵은 몸통)
                body = next(b_ for b_ in (6, 8, 10, 13, 16, 20, 25, 32) if b_ >= dp + 2
                            and math.pi ** 3 * 210000 * b_ ** 4 / 64 / (0.7 * lf) ** 2 / f_p >= 3)
                sf = math.pi ** 3 * 210000 * body ** 4 / 64 / (0.7 * lf) ** 2 / f_p
            punch_sf[key] = (sf, body, dp)
            dk = body + (3 if body < 10 else 4)
            kh = 5.0 if body < 13 else 8.0
            prims = []
            for _, c, d in hs:
                if body > dp:                             # 끝 · 어깨 (모따기 1) · 몸통 · 머리
                    st_ = [(p_bot, tip_len, d / 2, d / 2), (p_bot + tip_len, 1.0, d / 2, body / 2),
                           (p_bot + tip_len + 1.0, p_len - kh - tip_len - 1.0, body / 2, body / 2)]
                else:
                    st_ = [(p_bot, p_len - kh, d / 2, d / 2)]
                prims.append(axi(c[0], c[1], st_ + [(z_pb - kh, kh, dk / 2, dk / 2)]))
                pp.holes.append(Hole(c[0], c[1], body, "H7", z_pp, tpp, f"Ø{body:g} H7 관통 (펀치)",
                                     cb=(dk + 0.5, z_pb - kh, kh)))
            std = key <= 32
            step = f", 어깨 Ø{body:g} · 끝 길이 {tip_len:.0f}" if body > dp else ""
            add(f"피어싱 펀치 Ø{key:g}", len(hs), "SKH51 HRC 62~64",
                f"Ø{dp:g} × {p_len:.1f} (머리 Ø{dk:g} × {kh:g}{step})",
                prims, std=std, upper=True, note="어깨 붙임 펀치 (좌굴)" if body > dp else "머리 붙임 펀치",
                order=(f"{'어깨' if body > dp else '머리'} 붙임 펀치 P{dp:g} L{p_len:.1f} (길이 지정"
                       + (f", 몸통 Ø{body:g} 끝 {tip_len:.0f})" if body > dp else ")")) if std else "")
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
        [axi(x, y, [(z_st + tst - sb_thr, sb_thr, sb_m / 2, sb_m / 2), (z_st + tst, sh_L, sbd / 2, sbd / 2),
                    (z_st + tst + sh_L, sb_k, sb_dk / 2, sb_dk / 2)],
             socket=(z_st + tst + sh_L + sb_k, 0.6 * sb_k, HEX_KEY.get(sb_m, 0.8 * sb_m), -1)) for x, y in sb_xy],
        std=True, upper=True, order=f"스트리퍼 볼트 (ISO 7379) Ø{sbd:g} × {sh_L:.0f} M{sb_m}",
        note=f"머리 자리 깊이 {cb_d:.1f} (머리 {sb_k:g} + 움직임 {s_w:.1f} + 재연마 {REGRIND:g} + 1)")

    # 다이 스프링: 스트리퍼 윗면 ↔ 펀치 플레이트 자리 바닥
    sp_pr = []
    for x, y in sp_xy:
        pp.holes.append(Hole(x, y, spring.D + 1, "스프링 자리", z_pp, spring.pocket,
                             f"Ø{spring.D + 1:g} 깊이 {spring.pocket:.1f} (스프링 자리)", side="밑면"))
        sp_pr.append(axi(x, y, [(z_st + tst, spring.installed, spring.D / 2 - 0.5, spring.D / 2 - 0.5)],
                         bore=ds.SPRING_D[spring.D] / 2 + 0.3))          # 속이 빈 (로드 Ø 자리)
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
        [screw(x, y, z_ls + bcbh - bkh, bolt, bkh, bk, L_lo, True) for x, y in lb_xy], std=True,
        order=f"JIS B 1176 M{bolt} × {L_lo:.0f}", note=f"물림 {L_lo - g_lo:.0f} mm")
    add(f"육각 구멍 붙이 볼트 M{bolt} (상형)", len(ub_xy), "SCM435 (12.9)", f"M{bolt} × {L_up:.0f}",
        [screw(x, y, z_top - bcbh, bolt, bkh, bk, L_up, False) for x, y in ub_xy], std=True, upper=True,
        order=f"JIS B 1176 M{bolt} × {L_up:.0f}", note=f"물림 {L_up - g_up:.0f} mm")

    # 블랭킹 펀치 고정: 상형 세트 윗면 카운터보어 → 받침판 통과 → 펀치 윗면 탭 (2 개, 펀치 안쪽 1.5 d 이상)
    cop0 = _cop(polys)
    shank_on = max(Ls, Ws) < 450
    for bp in blank_punches:
        P = bp.prims[0].poly
        pd_ = 6 if min(np.ptp(P[:, 0]), np.ptp(P[:, 1])) < 60 else 8
        k6, kh6, d16, cb6, cbh6, tap6 = ds.SHCS[pd_]
        avoid = [(x, y, d / 2) for x, y, d in pilots]
        if shank_on:
            avoid.append((cop0[0], cop0[1], 19.0 + 2))
        avoid += [(x, y, bcb / 2) for x, y in ub_xy]
        pts = _inner_pair(P, max(1.5 * pd_, cb6 / 2 + 3), avoid, cb6 / 2 + 3)
        if not pts:
            bp.note += " · 고정 탭 자리 없음 (플랜지·키로 고정)"
            continue
        g = tus - cbh6 + tb
        Lp = ds.up_std(g + ds.ENGAGE * pd_, ds.SHCS_L)
        e = Lp - g
        for x, y in pts:
            upper_shoe.holes.append(Hole(x, y, d16, "통과", z_us, tus, f"Ø{d16:g} 통과, 자리 Ø{cb6:g} 깊이 {cbh6:g} (펀치 고정)",
                                         cb=(cb6, z_top - cbh6, cbh6)))
            pb.holes.append(Hole(x, y, d16, "통과", z_pb, tb, f"Ø{d16:g} 통과 (펀치 고정 M{pd_})"))
            bp.prims[0].holes.append(Hole(x, y, tap6, "탭", z_pb - (e + 3), e + 3,
                                          f"M{pd_} 탭 깊이 {e + 3:.0f} (윗면, 드릴 Ø{tap6:g})"))
        add(f"육각 구멍 붙이 볼트 M{pd_} (펀치 고정)", len(pts), "SCM435 (12.9)", f"M{pd_} × {Lp:.0f}",
            [screw(x, y, z_top - cbh6, pd_, kh6, k6, Lp, False) for x, y in pts], std=True, upper=True,
            order=f"JIS B 1176 M{pd_} × {Lp:.0f}", note=f"물림 {e:.0f} mm")

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
        [_pin(x, y, z_die_top - dl_lo, dwd, dl_lo) for x, y in ld_xy], std=True,
        order=f"평행 핀 ISO 8734 Ø{dwd:g} m6 × {dl_lo:.0f}")
    add("다우얼 핀 (상형)", 2, "SUJ2 (m6)", f"Ø{dwd:g} × {dl_up:.0f}",
        [_pin(x, y, z_pp, dwd, dl_up) for x, y in ud_xy], std=True, upper=True,
        order=f"평행 핀 ISO 8734 Ø{dwd:g} m6 × {dl_up:.0f}")

    if nest is not None:
        _nest_pins(add, nest, t, die, stripper, lo, z_die_top, H, tst, z_st)
    # 스트립 가이드 (다이 윗면, 스트립 양쪽): M5 카운터보어 볼트 + Ø5 다우얼 → 다이 플레이트 탭·H7, 스트리퍼 밑면 홈
    gw = 16.0
    gh = max(t + 2.0, 8.0)                               # M5 머리 자리 (5.4) + 바닥 2.6
    gd = gh - t + 1.0                                    # 스트리퍼 밑면 홈 깊이 (하사점에서 가이드가 1 들어옴)
    if gd > tst - 8:
        gh, gd = t + 1.0, 2.0                            # 스트리퍼가 얇으면 얇은 가이드 (밑면에서 핀·접착 — 주기)
    ys = Wst / 2 + 0.1
    rails = []
    kg6, kgh, gd1, gcb, gcbh, gtap = ds.SHCS[5]
    n_g = max(2, int(math.ceil(Ld / 120.0)))
    for sgn in ((-1, 1) if nest is None else ()):
        y0 = sgn * ys + (0 if sgn > 0 else -gw)
        rail = Prim(BOX, (-a, y0, z_die_top, Ld, gw, gh))
        rails.append(rail)
        groove = np.array([[-a - 1, y0 - 0.5], [a + 1, y0 - 0.5], [a + 1, y0 + gw + 0.5], [-a - 1, y0 + gw + 0.5]])
        stripper.cuts.append((groove, 0.0, z_st - 1, gd + 1))
        if gh >= 8.0:
            yc = y0 + gw / 2
            xs = np.linspace(-a + 15, a - 15, n_g + 2)
            used = [(q[0], q[1], q[2]) for q in lo.taken]
            screws, pins = [], []
            for i, x in enumerate(xs):
                is_pin = i in (0, len(xs) - 1)
                r_ = 2.5 if is_pin else gcb / 2
                for dx in (0, 6, -6, 12, -12, 18, -18):
                    if all(math.hypot(x + dx - qx, yc - qy) >= r_ + qr + 2 for qx, qy, qr in used):
                        (pins if is_pin else screws).append((x + dx, yc))
                        used.append((x + dx, yc, r_))
                        break
            for x, y in screws:
                rail.holes.append(Hole(x, y, gd1, "통과", z_die_top, gh, f"Ø{gd1:g} 통과, 자리 Ø{gcb:g} 깊이 {gcbh:g}",
                                       cb=(gcb, z_die_top + gh - gcbh, gcbh)))
                die.holes.append(Hole(x, y, gtap, "탭", z_die_top - 11, 11, f"M5 탭 깊이 11 (스트립 가이드, 드릴 Ø{gtap:g})"))
            for x, y in pins:
                rail.holes.append(Hole(x, y, 5.0, "H7", z_die_top, gh, "Ø5 H7 리머 관통 (다우얼)"))
                die.holes.append(Hole(x, y, 5.0, "H7", z_die_top - 10, 10, "Ø5 H7 리머 깊이 10 (스트립 가이드)"))
    if rails:
        add("스트립 가이드", 2, "S50C (HRC 40~45)", f"{Ld:.0f} × {gw:g} × {gh:g}", rails,
            note=f"스트립 폭 {Wst:.1f} + 0.2 · 스트리퍼 밑면 홈 {gw + 1:g} × {gd:g}"
            + ("" if gh >= 8.0 else " · 얇은 가이드: 밑면 핀 + 접착 (설계자 확인)"))
    if gh >= 8.0 and rails:
        g_scr = [(h.x, h.y) for r_ in rails for h in r_.holes if h.kind == "통과"]
        g_pin = [(h.x, h.y) for r_ in rails for h in r_.holes if h.kind == "H7"]
        z_hd = z_die_top + gh - gcbh                     # 머리 밑면
        Lg = ds.down_std(z_hd - (z_die_top - 11) - 1, ds.SHCS_L)
        add("육각 구멍 붙이 볼트 M5 (스트립 가이드)", len(g_scr), "SCM435 (12.9)", f"M5 × {Lg:.0f}",
            [screw(x, y, z_hd, 5, kgh, kg6, Lg, False) for x, y in g_scr], std=True, order=f"JIS B 1176 M5 × {Lg:.0f}")
        Lgp = ds.down_std(gh + 10, ds.DOWEL_L)
        add("다우얼 핀 (스트립 가이드)", len(g_pin), "SUJ2 (m6)", f"Ø5 × {Lgp:.0f}",
            [_pin(x, y, z_die_top - 10, 5.0, Lgp) for x, y in g_pin],
            std=True, order=f"평행 핀 ISO 8734 Ø5 m6 × {Lgp:.0f}")

    # 클램프 U 홈 (다이 세트를 볼스터·슬라이드에 클램프 볼트로): 양 끝 (x) 에 2 개씩, 가이드 포스트·스톱 블록 피함
    slot_w = 22.0 if max(Ls, Ws) < 800 else 26.0                   # M20 · M24 클램프 볼트
    slot_d = min(max(post_d + 35 - post_d / 2 - 8, 20.0), 40.0)
    sy_ = [sgn * 0.5 * (b - post_d) for sgn in (-1, 1)]
    for shoe in (lower, upper_shoe):
        for sxn in (-1, 1):
            for yy in sy_:
                shoe.cuts.append((_uslot(sxn * Ls / 2, yy, slot_w, slot_d, sxn), 0.0, shoe.p[2] - 1, shoe.p[5] + 2,
                                  "slot"))
    # 옆면 아이볼트 탭 (들어 올림): 다이 세트마다 앞·뒤 면에 2 개 (25 kg 넘는 판도) — JIS B 1168 어림 크기
    def eye_m(kg):
        return 12 if kg <= 200 else 16 if kg <= 400 else 20 if kg <= 600 else 24
    eye_done = []
    for shoe, nm in ((lower, "하형"), (upper_shoe, "상형"), (die, "다이")):
        kg = _volume(shoe) * DENSITY
        if nm == "다이" and kg <= 25:
            continue
        m_ = eye_m(2 * kg)
        tap = {12: 10.2, 16: 14.0, 20: 17.5, 24: 21.0}[m_]
        dep = 1.5 * m_ + 5
        x0_, y0_, z0_, dx_, dy_, dz_ = shoe.p
        if dz_ < m_ + 10:
            continue
        for sgn in (-1, 1):
            for xx in (-dx_ / 4, dx_ / 4):
                shoe.holes.append(Hole(xx, (y0_ + dy_) if sgn > 0 else y0_, tap, "탭", z0_ + dz_ / 2, dep,
                                       f"M{m_} 탭 깊이 {dep:.0f} (옆면 아이볼트, 드릴 Ø{tap:g})",
                                       side="앞면" if sgn < 0 else "뒷면", axis="-y" if sgn > 0 else "+y"))
        eye_done.append(f"{nm} M{m_} × 4")
    eye_note = ("옆면 아이볼트 탭: " + " · ".join(eye_done)) if eye_done else ""

    # 스톱 블록 (하사점 받침): 하형 세트 위, 가이드 포스트 사이 — 하사점에서 상형 세트 밑면과 0.5 틈 (심으로 맞춤)
    travel_ = gap + RETRACT + ENTRY
    sb_h = (z_us - travel_) - ts - 0.5
    sbw = 30.0 if Ws >= 160 else 20.0
    sxs = [sgn * (a_out + post_d / 2 + 15) for sgn in (-1, 1)]
    blocks = [Prim(BOX, (x - sbw / 2, -sbw / 2, ts, sbw, sbw, sb_h)) for x in sxs]
    for x, blk in zip(sxs, blocks):
        lower.holes.append(Hole(x, 0.0, 9.0, "통과", z_ls, ts, "Ø9 통과, 자리 Ø14 깊이 8.6 (스톱 블록)",
                                cb=(14.0, z_ls, 8.6), side="밑면"))
        blk.holes.append(Hole(x, 0.0, 6.8, "탭", ts, 15, "M8 탭 깊이 15 (밑면, 드릴 Ø6.8)", side="밑면"))
    add("스톱 블록", 2, "S50C", f"{sbw:g} × {sbw:g} × {sb_h:.1f}", blocks,
        note="하사점에서 상형 세트와 0.5 틈 — 보관할 때 사이에 받침, 재연마 뒤 같이 연삭")
    Lsb = ds.down_std(ts - 8.6 + 14, ds.SHCS_L)          # 블록 탭 물림 ≤ 14 (탭 깊이 15)
    add("육각 구멍 붙이 볼트 M8 (스톱 블록)", 2, "SCM435 (12.9)", f"M8 × {Lsb:.0f}",
        [screw(x, 0.0, z_ls + 8.6 - 8, 8, 8, 13, Lsb, True) for x in sxs], std=True, order=f"JIS B 1176 M8 × {Lsb:.0f}")

    # 와이어 시작 구멍 (날 안쪽 — 다이·스트리퍼·펀치 플레이트 이형 구멍)
    for i, (P, k) in enumerate(ops):
        if k == "pierce" and _is_round(P) and _circle_d(P)[0] < 30:
            continue                                     # 작은 둥근 구멍은 드릴 → 리머 / 지그 연삭
        q = _deep_point(P)
        if q is None:
            continue
        for pr_, z0 in ((die, z_die), (stripper, z_st)):
            pr_.holes.append(Hole(q[0], q[1], 2.0, "와이어 시작", z0 + 0.0, pr_.p[5], "Ø2 와이어 시작 구멍 (날 안)"))

    # 생크: 압력 중심
    cop = _cop(polys)
    cx_, cy_ = round(cop[0] * 2) / 2, round(cop[1] * 2) / 2
    if max(Ls, Ws) < 450:
        add("생크", 1, "S45C", "Ø38 × 60", [axi(cx_, cy_, [(z_top, 10, 25.0, 25.0), (z_top + 10, 48, 19.0, 19.0),
                                                        (z_top + 58, 2, 19.0, 17.0)])], upper=True,
            note=f"압력 중심 ({cx_:+.1f}, {cy_:+.1f}) 위 · M16 탭 고정")
        upper_shoe.holes.append(Hole(cx_, cy_, 14.0, "탭", z_top - 24, 24, "M16 탭 깊이 24 (생크)"))

    # 하사점·높이
    travel = gap + RETRACT + ENTRY                       # 열림 → 하사점 상형 움직임
    shut = z_top - travel
    stroke = travel + t + 5                              # 스트립 들어 올림 · 이송 여유 5
    pierce_d = [k for k in groups if k is not None]
    checks = []
    # 프레스: 절단력 + 하사점 스프링 힘, 에너지 = F · t · 파단 깊이 비
    f_spring = spring.n * spring.rate * (spring.preload + s_w)
    F_total = F + f_spring
    kp = penetration(mat)
    energy = F * t * kp / 1000.0                        # J
    from . import costing as cs
    mlist = machines if machines is not None else cs.DEFAULT_MACHINES
    need_t = F_total * cs.SAFETY / dc.TON
    mach, mach_ok = cs.pick(mlist, cs.PRESS, need_t, height=t + ENTRY)
    if mach is not None and mach_ok and float(mach.get("stroke") or cs.default_stroke(mach["capacity"])) < stroke:
        mach_ok = False
    press = {"cut_kn": F / 1000, "spring_kn": f_spring / 1000, "total_kn": F_total / 1000, "need_tf": need_t,
             "energy_j": energy, "penetration": kp, "machine": mach["name"] if mach else "", "ok": bool(mach_ok),
             "shear_h": t}
    # 전단각 (펀치·다이에 경사): 경사 높이 h ≥ k t 이면 최대 힘 ≈ F · k t / h (에너지는 같음)
    if not mach_ok:
        press["shear_note"] = (f"전단각: 경사 높이 h = t 면 최대 힘 ≈ {F * kp / 1000:,.0f} kN "
                               f"(블랭킹은 다이에, 피어싱은 펀치에 경사 — 제품이 휘지 않는 쪽)")

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
    sig_b = f_strip / (len(ub_xy) * ds.STRESS_AREA[bolt])
    chk(f"상형 볼트 인장 (스트리핑 힘 ÷ {len(ub_xy)})", f"{sig_b:,.0f} MPa", f"≤ {ds.BOLT_ALLOW:g} (12.9, 되풀이)",
        sig_b <= ds.BOLT_ALLOW)
    sig_sb = spring.f_max / (len(sb_xy) * ds.STRESS_AREA[sb_m])
    chk(f"스트리퍼 볼트 나사 인장 (스프링 최대 ÷ {len(sb_xy)})", f"{sig_sb:,.0f} MPa", f"≤ {ds.BOLT_ALLOW:g}",
        sig_sb <= ds.BOLT_ALLOW)
    chk("펀치 진입 (하사점)", f"{ENTRY:g} mm", "0.5 ~ 1.5 mm", True)
    for d in pierce_d:
        sig = 4 * tau * t / d
        chk(f"피어싱 펀치 Ø{d:g} 압축 응력", f"{sig:,.0f} MPa", f"≤ {PUNCH_SIGMA:,.0f} (SKH51)", sig <= PUNCH_SIGMA)
        sf, body, dp_ = punch_sf[d]
        chk(f"피어싱 펀치 Ø{d:g} 좌굴" + (f" (어깨 Ø{body:g})" if body > dp_ else ""), f"안전율 {sf:,.1f}",
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
    chk("프레스", f"{press['machine'] or '없음'} (필요 {need_t:,.0f} tf, 행정 ≥ {stroke:.0f})",
        f"(절단 {F / 1000:,.0f} + 스프링 {f_spring / 1000:,.0f} kN) × {cs.SAFETY:g}", mach_ok)
    # 가이드 포스트: 프레스 행정 끝 (상사점) 에서도 부시에 10 mm 넘게 물리고, 하사점에서 상형 세트 윗면 3 mm 아래
    p_stroke = float(mach.get("stroke") or cs.default_stroke(mach["capacity"])) if mach else stroke
    z_us_tdc = z_us - travel + p_stroke                   # 상사점의 상형 세트 밑면
    z_post_max = (z_top - travel) - 3                     # 하사점에서 포스트 끝이 넘으면 안 되는 높이
    need_post = z_us_tdc + 10 - z_ls
    post_part = next(q for q in parts if q.name == "가이드 포스트")
    post_L0 = post_part.prims[0].p[4]
    post_L_new = post_L0
    if need_post > post_L0:
        post_L_new = min(_up5(need_post), math.floor((z_post_max - z_ls) / 5) * 5)
    if post_L_new != post_L0:
        post_part.prims = [axi(q.p[0], q.p[1], [(z_ls, post_L_new - 2, post_d / 2, post_d / 2),
                                                (z_ls + post_L_new - 2, 2, post_d / 2, post_d / 2 - 1.5)])
                           for q in post_part.prims]
        post_part.size = f"Ø{post_d:g} × {post_L_new:.0f}"
        post_part.order = f"가이드 포스트 Ø{post_d:g} L{post_L_new:.0f} (압입형)"
    engage = z_ls + post_L_new - z_us_tdc
    # 선행 안내: 스트리퍼가 판에 닿을 때 (열림에서 gap − t 내려옴) 포스트가 부시에 물린 길이
    pre = z_ls + post_L_new - (z_us - (gap - t))
    chk("가이드 포스트 선행 안내 (스트리퍼가 판에 닿을 때)", f"{pre:.0f} mm", "≥ 10 mm (펀치보다 먼저 안내)",
        pre >= 10 - 1e-6)
    top_gap = z_post_max + 3 - (z_ls + post_L_new)
    chk("가이드 포스트 끝 ↔ 상형 세트 윗면 (하사점)", f"{top_gap:.0f} mm", "≥ 3 mm (램에 닿지 않게)", top_gap >= 3 - 1e-6)
    off = math.hypot(*cop)
    chk("압력 중심 ↔ 금형 가운데", f"{off:.1f} mm", "생크를 압력 중심에 (옮김)" if max(Ls, Ws) < 450 else
        "큰 금형: 슬라이드 가운데와 맞춰 놓기", True)
    # 스트립 재료 이용
    part_area = abs(_area(blank)) - sum(abs(_area(h)) for h in holes)
    usage = {"part_mm2": part_area, "pitch": pitch, "width": Wst,
             "ratio": part_area / (pitch * Wst) if pitch * Wst > 0 else 0.0,
             "part_kg": part_area * t * DENSITY, "strip_kg": pitch * Wst * t * DENSITY}
    notes = [f"절단 길이 {L_cut:,.0f} mm × t {t:g} × τ {tau:.0f} MPa = 절단력 {F / 1000:,.1f} kN, + 하사점 스프링 "
             f"{f_spring / 1000:,.1f} kN → 권장 프레스 {need_t:,.0f} tf ({cs.SAFETY:g} 배)"
             + (f" — {press['machine']}" if press["machine"] else ""),
             f"전단 에너지 W = F × t × {kp:g} (파단 깊이 비) = {energy:,.0f} J / 타",
             f"스트립 재료 이용률 {usage['ratio'] * 100:.1f} % (제품 {usage['part_kg']:.3f} kg / 피치 몫 "
             f"{usage['strip_kg']:.3f} kg)",
             f"날 치수: 일반 공차 ISO 2768-{tol} · 마모 계수 x 로 블랭킹 다이는 최대 − xΔ, 피어싱 펀치는 최소 + xΔ "
             "(도면 공차가 따로 있으면 그 값으로 고칠 것)",
             f"다이 플레이트 두께 ∛(0.1 F) = {dc.die_plate_thickness(F):.1f} → {H:.0f} mm, 날 끝 여유 {m:.0f} mm",
             f"스트립 피치 {pitch:.1f} · 폭 {Wst:.1f} mm (이송 →)",
             f"높이: 열림 {z_top:.1f} · 하사점 (닫힌 높이) {shut:.1f} mm · 필요한 행정 ≥ {stroke:.0f} mm "
             f"(열림 {gap:.0f} + 스트리퍼 안 {RETRACT:g} + 진입 {ENTRY:g} + 들어 올림)",
             f"압력 중심 ({cop[0]:+.1f}, {cop[1]:+.1f}) mm (금형 가운데 기준)",
             "표준품 치수는 일반값 — 주문 전에 쓰는 업체 (MISUMI·Lesjöfors 등) 표로 확인, 스프링 상수는 Ø10 × 25 에서 닮은꼴 어림"]
    if press.get("shear_note"):
        notes.append(press["shear_note"])
    if eye_note:
        notes.append(eye_note + " — 들어 올릴 때 두 개 이상, 45° 넘게 기울이지 않기")
    notes.append(f"클램프 U 홈 폭 {slot_w:g} × 깊이 {slot_d:.0f} (상·하형 세트 양 끝 2 개씩)")
    if engage < 10:
        notes.append(f"프레스 행정 {p_stroke:.0f} mm 상사점에서는 가이드 포스트가 부시에서 {-engage:.0f} mm 빠짐 "
                     f"(선행 안내 {pre:.0f} mm 는 됨) — 정밀 금형은 행정을 {max(10.0, p_stroke + engage - 10):.0f} mm 안으로 "
                     "조정하거나 볼 부시 (긴 것) 로")
    if nest is not None:
        notes[5] = "블랭크를 네스트 핀에 맞춰 넣음 (손 · 로봇) — 스트립 아님"
    if fit is not None:
        notes.append(f"후 피어싱: 다이를 접은 제품 안쪽에 맞춤 ({Ld:.0f} × {Wd:.0f}), 아래로 접힌 플랜지 깊이 {depth_below:.0f} "
                     f"→ 받침판 {tb:.0f}")
        chk("위로 선 부분 ↔ 상형 (하사점)", f"{up_h:.0f} mm", f"≤ {tst + sgap - s_w + tpp - 5:.0f} (스트리퍼 + 틈 + 펀치 판 − 5)",
            up_h <= tst + sgap - s_w + tpp - 5)
    if plan is not None:
        notes.append("순차: 파일럿·피어싱 공정 구멍만 다이에 팠음 — 노칭·절곡·컷오프 인서트와 다음 공정 파일럿 핀은 "
                     "공정도를 보고 설계자가")
    return DieAssy(kind, parts, Ls, Ws, shut, F, notes, blank, holes, checks, cop, z_top, stroke, (pitch, Wst), spring,
                   edges, press, usage)


def _nest_pins(add, blank, t, die, stripper, lo, z_die_top, H, tst, z_st):
    """블랭크 네스트 (3-2-1): 가장 긴 외곽 변에 핀 2 개, 그 옆 변에 1 개, 맞은편 끝에 1 개 (넣기 쉬운 쪽은 비움) —
    핀은 블랭크 바깥 0.1 띄움, 다이 플레이트 H7 압입, 판 위로 t + 3, 스트리퍼는 피함 구멍."""
    from scipy.spatial import ConvexHull
    P = np.asarray(blank, float)
    hull = P[ConvexHull(P).vertices]
    if _area(hull) < 0:
        hull = hull[::-1]
    d = 6.0 if max(np.ptp(P, 0)) < 120 else 8.0
    edges = [(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull))]
    lens = [float(np.linalg.norm(b - a)) for a, b in edges]
    i0 = int(np.argmax(lens))

    def out_pt(a, b, f):
        q = a + f * (b - a)
        tng = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        nrm = np.array([tng[1], -tng[0]])              # 반시계 외곽의 바깥 법선
        return q + nrm * (d / 2 + 0.1)
    want = [out_pt(*edges[i0], 0.2), out_pt(*edges[i0], 0.8)]
    # 옆 변: 긴 변과 가장 수직인 변 중 긴 것
    t0 = (edges[i0][1] - edges[i0][0]) / lens[i0]
    side = max((j for j in range(len(edges)) if j != i0 and lens[j] > 3 * d),
               key=lambda j: (abs(t0[0] * (edges[j][1] - edges[j][0])[1] - t0[1] * (edges[j][1] - edges[j][0])[0]) / lens[j],
                               lens[j]), default=None)
    if side is not None:
        want.append(out_pt(*edges[side], 0.5))
    pins = []
    for q in want:
        x, y = float(q[0]), float(q[1])
        if all(_dist(Q, (x, y)) >= d / 2 + 2 for Q in lo.polys) and all(
                math.hypot(x - qx, y - qy) >= d / 2 + qr + 2 for qx, qy, qr in lo.taken) and abs(x) < lo.a - d and abs(y) < lo.b - d:
            pins.append((x, y))
            lo.taken.append((x, y, d / 2))
    hp = t + 3.0
    L = ds.up_std(hp + 1.5 * d + 2, ds.DOWEL_L)
    dep = L - hp
    for x, y in pins:
        die.holes.append(Hole(x, y, d, "H7", z_die_top - dep, dep, f"Ø{d:g} H7 리머 깊이 {dep:.0f} (네스트 핀)"))
        stripper.holes.append(Hole(x, y, d + 2, "통과", z_st, tst, f"Ø{d + 2:g} 통과 (네스트 핀 피함)"))
    if pins:
        add("네스트 핀", len(pins), "SUJ2 (m6) HRC 58", f"Ø{d:g} × {L:.0f}", [_pin(x, y, z_die_top - dep, d, L) for x, y in pins],
            std=True, order=f"평행 핀 ISO 8734 Ø{d:g} m6 × {L:.0f} (윗면 모따기 크게)",
            note=f"블랭크 외곽 3-2-1 자리 — 판 위로 {hp:.0f} 나옴, 긴 변 2 · 옆 변 1 (반대쪽에서 밀어 넣음)")
    return pins


# ---------------------------------------------------------------- 둥근 표준품 모양

HEX_KEY = {4: 3, 5: 4, 6: 5, 8: 6, 10: 8, 12: 10, 16: 14, 20: 17}   # 육각 구멍 붙이 볼트 맞변 (JIS B 1176)


def axi(x, y, stack, bore=0.0, socket=None):
    """축대칭 부품 (아래부터 [(z0, 높이, r 아래, r 위)]) — 바깥 꼴은 cyl (x, y, z0, r 최대, 높이) 로 보임."""
    z0 = min(a for a, _, _, _ in stack)
    z1 = max(a + h for a, h, _, _ in stack)
    r = max(max(r0, r1) for _, _, r0, r1 in stack)
    return Prim(CYL, (float(x), float(y), float(z0), float(r), float(z1 - z0)), stack=list(stack), bore=float(bore),
                socket=socket)


def _uslot(x_edge, yc, w, depth, sgn, n=10):
    """판 끝 (x = x_edge, sgn: +1 오른쪽 끝) 에서 안으로 depth 들어간 U 홈 (끝 반원)."""
    xi = x_edge - sgn * (depth - w / 2)                   # 반원 가운데
    pts = [(x_edge + sgn * 1.0, yc - w / 2), (xi, yc - w / 2)]
    for i in range(1, n):
        a = -math.pi / 2 - sgn * math.pi * i / n if sgn > 0 else -math.pi / 2 + math.pi * i / n
        pts.append((xi + (w / 2) * math.cos(a) * (1 if sgn < 0 else 1), yc + (w / 2) * math.sin(a)))
    pts += [(xi, yc + w / 2), (x_edge + sgn * 1.0, yc + w / 2)]
    P = np.array(pts)
    return P if _area(P) > 0 else P[::-1]


def _pin(x, y, z0, d, L):
    """평행 핀 (양 끝 모따기 0.1 d)."""
    c = max(0.3, 0.1 * d)
    return axi(x, y, [(z0, c, d / 2 - c, d / 2), (z0 + c, L - 2 * c, d / 2, d / 2), (z0 + L - c, c, d / 2, d / 2 - c)])


def screw(x, y, z_head, d, k, dk, L, shank_up):
    """육각 구멍 붙이 볼트: 머리 (z_head ~ z_head + k), 몸통 L (shank_up 이면 머리 위로, 아니면 아래로),
    머리 바깥 면에 육각 구멍 (깊이 0.6 k), 끝 모따기 0.5 · 머리 모따기."""
    c = min(0.5, 0.1 * d)
    s = HEX_KEY.get(int(round(d)), 0.8 * d)
    if shank_up:
        st = [(z_head, 0.4, dk / 2 - 0.4, dk / 2), (z_head + 0.4, k - 0.4, dk / 2, dk / 2),
              (z_head + k, L - c, d / 2, d / 2), (z_head + k + L - c, c, d / 2, d / 2 - c)]
        sock = (z_head, 0.6 * k, s, +1)
    else:
        st = [(z_head - L, c, d / 2 - c, d / 2), (z_head - L + c, L - c, d / 2, d / 2),
              (z_head, k - 0.4, dk / 2, dk / 2), (z_head + k - 0.4, 0.4, dk / 2, dk / 2 - 0.4)]
        sock = (z_head + k, 0.6 * k, s, -1)
    return axi(x, y, st, socket=sock)


def _revolve(pr: Prim):
    """stack 을 원통·원뿔 (해석 곡면 — CAD 가 구멍·원통으로 알아봄) 으로 이어 붙이고 같은 면을 합침, 안 구멍 bore ·
    육각 구멍 socket 을 판다."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    x, y = float(pr.p[0]), float(pr.p[1])
    s = None
    for z0, h, r0, r1 in sorted(pr.stack, key=lambda q: q[0]):
        if h <= 1e-6:
            continue
        ax = gp_Ax2(gp_Pnt(x, y, float(z0)), gp_Dir(0, 0, 1))
        seg = (BRepPrimAPI_MakeCylinder(ax, float(r0), float(h)).Shape() if abs(r0 - r1) < 1e-9
               else BRepPrimAPI_MakeCone(ax, float(r0), float(r1), float(h)).Shape())
        s = seg if s is None else BRepAlgoAPI_Fuse(s, seg).Shape()
    if pr.bore > 0:
        z0, h = pr.p[2], pr.p[4]
        s = BRepAlgoAPI_Cut(s, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, float(z0 - 1)), gp_Dir(0, 0, 1)),
                                                       float(pr.bore), float(h + 2)).Shape()).Shape()
    if pr.socket:
        zf, dep, sz, sgn = pr.socket
        R = sz / math.sqrt(3)                      # 맞변 s 의 육각형 꼭짓점 반지름
        mk = BRepBuilderAPI_MakePolygon()
        z_start = zf if sgn > 0 else zf - dep
        for i in range(6):
            a = math.pi / 6 + i * math.pi / 3
            mk.Add(gp_Pnt(x + R * math.cos(a), y + R * math.sin(a), float(z_start - 0.01)))
        mk.Close()
        hexf = BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()
        try:
            s = BRepAlgoAPI_Cut(s, BRepPrimAPI_MakePrism(hexf, gp_Vec(0, 0, float(dep + 0.01))).Shape()).Shape()
        except Exception:  # noqa: BLE001
            pass
    try:
        u = ShapeUpgrade_UnifySameDomain(s, True, True, False)
        u.Build()
        s = u.Shape()
    except Exception:  # noqa: BLE001
        pass
    return s


# ---------------------------------------------------------------- 솔리드 · STEP

SIMPLIFY_TOL = 0.005      # STEP 외곽 점 줄이기 (mm) — 클리어런스 (0.05 ~) 보다 훨씬 작게


CORNER_DEG = 20.0         # 이보다 크게 꺾이면 귀 (곧은 선·곡선 끊음)


def _wire(P, z0):
    """닫힌 외곽 선: 귀에서 끊고, 점이 많은 매끈한 구간은 B-스플라인 (벗어남 ≤ 0.005) 하나로 — STEP 면 수가 적고
    와이어 CAM 에도 매끈한 곡선. 짧은 구간은 곧은 선."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeWire
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.GeomAbs import GeomAbs_C2
    from OCP.gp import gp_Pnt
    from OCP.collections import Array1_gp_Pnt as TColgp_Array1OfPnt
    P = np.asarray(P, float)
    n = len(P)

    def pnt(q):
        return gp_Pnt(float(q[0]), float(q[1]), float(z0))
    if n < 12:
        mk = BRepBuilderAPI_MakePolygon()
        for q in P:
            mk.Add(pnt(q))
        mk.Close()
        return mk.Wire()
    d1 = P - np.roll(P, 1, axis=0)
    d2 = np.roll(P, -1, axis=0) - P
    ang = np.degrees(np.abs(np.arctan2(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0], (d1 * d2).sum(1))))
    corners = list(np.nonzero(ang > CORNER_DEG)[0])
    if not corners:
        corners = [0, n // 3, 2 * n // 3]                 # 둥근 외곽: 세 조각
    wm = BRepBuilderAPI_MakeWire()
    for k, a in enumerate(corners):
        b = corners[(k + 1) % len(corners)]
        idx = list(range(a, b + 1)) if b > a else list(range(a, n)) + list(range(0, b + 1))
        seg = P[idx]
        if len(seg) >= 5:
            arr = TColgp_Array1OfPnt(1, len(seg))
            for i, q in enumerate(seg, 1):
                arr.SetValue(i, pnt(q))
            try:
                c = GeomAPI_PointsToBSpline(arr, 3, 8, GeomAbs_C2, SIMPLIFY_TOL).Curve()
                wm.Add(BRepBuilderAPI_MakeEdge(c, pnt(seg[0]), pnt(seg[-1])).Edge())
                continue
            except Exception:  # noqa: BLE001 — 맞추기 못하면 곧은 선으로
                pass
        for q0, q1 in zip(seg[:-1], seg[1:]):
            if np.linalg.norm(q1 - q0) > 1e-7:
                wm.Add(BRepBuilderAPI_MakeEdge(pnt(q0), pnt(q1)).Edge())
    return wm.Wire()


def _simplify(P, tol=SIMPLIFY_TOL):
    """닫힌 다각형 점 줄이기 (Douglas–Peucker, 벗어남 ≤ tol). 곡선 외곽의 STEP 면 수를 줄임."""
    P = np.asarray(P, float)
    n = len(P)
    if n <= 24:
        return P
    # 서로 가장 먼 두 점으로 둘로 나눠 열린 선 두 개
    i0 = 0
    i1 = int(np.argmax(np.linalg.norm(P - P[0], axis=1)))
    keep = np.zeros(n, bool)
    keep[[i0, i1]] = True
    stack = [(i0, i1), (i1, n)]
    while stack:
        a, b = stack.pop()
        idx = np.arange(a + 1, b)
        if len(idx) == 0:
            continue
        A, B = P[a], P[b % n]
        d = B - A
        L = np.linalg.norm(d)
        Q = P[idx]
        if L < 1e-12:
            dist = np.linalg.norm(Q - A, axis=1)
        else:
            dist = np.abs(d[0] * (Q[:, 1] - A[1]) - d[1] * (Q[:, 0] - A[0])) / L
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = int(idx[k])
            keep[m] = True
            stack += [(a, m), (m, b)]
    return P[keep]

def _solid(pr: Prim):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakePrism,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    def prism(poly, z0, h, grow=0.0):
        P = _simplify(_offset(poly, grow) if grow else np.asarray(poly, float))
        face = BRepBuilderAPI_MakeFace(_wire(P, z0), True).Face()
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
        s = _revolve(pr) if pr.stack else cyl(x, y, z0, r, h)
        z_lo, hh = z0, h
    elif pr.kind == PROF:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
        c0, L = pr.p
        Q = np.asarray(pr.poly, float)
        mk = BRepBuilderAPI_MakePolygon()
        for q in Q:
            mk.Add(gp_Pnt(float(c0), float(q[0]), float(q[1])) if pr.ax == "x"
                   else gp_Pnt(float(q[0]), float(c0), float(q[1])))
        mk.Close()
        face = BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()
        s = BRepPrimAPI_MakePrism(face, gp_Vec(float(L), 0, 0) if pr.ax == "x" else gp_Vec(0, float(L), 0)).Shape()
        z_lo, hh = float(Q[:, 1].min()), float(np.ptp(Q[:, 1]))
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
        if h.kind == "와이어 시작":
            continue                                     # 날 안 (이미 빠진 곳) — 솔리드에는 없음, 도면에만
        if h.axis != "z":                                # 옆면 구멍 (아이볼트 탭): 면 밖 0.5 에서 안으로
            sgn = 1.0 if h.axis[0] == "+" else -1.0
            dv = (sgn, 0.0, 0.0) if h.axis[1] == "x" else (0.0, sgn, 0.0)
            o = gp_Pnt(float(h.x - 0.5 * dv[0]), float(h.y - 0.5 * dv[1]), float(h.z0))
            bld.Add(tools, BRepPrimAPI_MakeCylinder(gp_Ax2(o, gp_Dir(*dv)), float(h.d / 2), float(h.h + 0.5)).Shape())
            n += 1
            continue
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


STEP_COLORS = {"SKD11": (0.45, 0.55, 0.70), "SKH51": (0.85, 0.50, 0.20), "S50C": (0.72, 0.74, 0.76),
               "SS400": (0.45, 0.47, 0.50), "SCM435": (0.12, 0.12, 0.12), "SUJ2": (0.85, 0.85, 0.88),
               "S45C": (0.60, 0.62, 0.64)}
SPRING_RGB = {"녹색": (0.20, 0.65, 0.30), "청색": (0.20, 0.40, 0.85), "적색": (0.85, 0.20, 0.20),
              "황색": (0.95, 0.80, 0.15)}


def part_rgb(p: DiePart, spring=None):
    """STEP·그림 색 (0~1): 스프링은 ISO 10243 색, 그 밖은 재질."""
    if p.name == "다이 스프링" and spring is not None:
        return SPRING_RGB.get(spring.color, (0.6, 0.6, 0.6))
    for k, c in STEP_COLORS.items():
        if k in p.material:
            return c
    return (0.65, 0.65, 0.68)


def save_step(assy: DieAssy, path):
    """금형 STEP: 조립 구조 (DIE → UPPER DIE · LOWER DIE → 부품) 와 부품 이름 (번호 · 품명, 영문) · 색 (재질별,
    다이 스프링은 ISO 색) — CAD 에서 열면 상형·하형이 묶여 보임."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(lab, nm):
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(nm))
    root = st.NewShape()
    name(root, "DIE ASSEMBLY")
    subs = {}
    for key, nm in ((False, "LOWER DIE"), (True, "UPPER DIE")):
        lab = st.NewShape()
        name(lab, nm)
        subs[key] = lab
    for p in assy.parts:
        r, g, b = part_rgb(p, assy.spring)
        col = Quantity_Color(r, g, b, Quantity_TOC_RGB)
        for k, pr in enumerate(p.prims, 1):
            lab = st.AddShape(_solid(pr), False)
            nm = f"{p.no:02d} {en_name(p.name)}" + (f" #{k}" if len(p.prims) > 1 else "")
            name(lab, nm)
            ct.SetColor(lab, col, XCAFDoc_ColorGen)
            comp = st.AddComponent(subs[p.upper], lab, TopLoc_Location())
            name(comp, nm)
    for key in (False, True):
        c = st.AddComponent(root, subs[key], TopLoc_Location())
        name(c, "UPPER DIE" if key else "LOWER DIE")
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.SetColorMode(True)
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
    zmax = max(extent(pr)[2] + extent(pr)[5] for part in assy.parts for pr in part.prims)
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
            elif pr.kind == PROF:
                bx, by, _, dx, dy, _ = extent(pr)
                p.drawRect(QRectF(T(bx, by + dy), T(bx + dx, by)))
            else:
                p.drawPolygon(QPolygonF([T(*q) for q in pr.poly]))
        pr = part.prims[0]
        if pr.kind == CYL:
            at = T(pr.p[0], pr.p[1])
        elif pr.kind == PROF:
            bx, by, _, dx, dy, _ = extent(pr)
            at = T(bx + dx / 2, by + 0.8 * dy)
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
            elif pr.kind == PROF:
                if pr.ax == "y":
                    p.drawPolygon(QPolygonF([Tf(*q) for q in pr.poly]))
                else:
                    e = extent(pr)
                    p.drawRect(QRectF(Tf(e[0], e[2] + e[5]), Tf(e[0] + e[3], e[2])))
            else:
                z0, h = pr.p
                xs = pr.poly[:, 0]
                p.drawRect(QRectF(Tf(xs.min(), z0 + h), Tf(xs.max(), z0)))
        # 지시선이 그림을 가로지르지 않게 오른쪽 끝 (x 가 가장 큰) 프리미티브에 붙임
        def right(pr):
            e = extent(pr)
            return e[0] + e[3]
        pr = max(part.prims, key=right)
        if pr.kind == PROF:
            e = extent(pr)
            at = Tf(e[0] + e[3], e[2] + e[5] / 2)
        elif pr.kind == BOX:
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
    ws5 = wb.create_sheet("날 치수 · 프레스")
    for j, hd in enumerate(EDGE_HEAD, 1):
        c = ws5.cell(1, j, hd)
        c.font, c.fill = hf, hfill
    for i, row in enumerate(assy.edges, 2):
        for j, v in enumerate(row, 1):
            ws5.cell(i, j, v)
    rr = len(assy.edges) + 3
    for line in press_lines(assy):
        ws5.cell(rr, 1, "• " + line)
        rr += 1
    for col, wd in zip("ABCDEFGH", (16, 22, 12, 12, 11, 22, 22, 16)):
        ws5.column_dimensions[col].width = wd
    tmp2 = _add_image(ws5, render_strip(assy), f"A{rr + 1}", 1000)
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
    for f_ in (tmp, tmp2):
        try:
            os.remove(f_)
        except OSError:
            pass
    return path


def press_lines(assy: DieAssy):
    pr, u = assy.press, assy.usage
    if not pr:
        return []
    out = [f"프레스 하중: 절단 {pr['cut_kn']:,.1f} kN + 하사점 스프링 {pr['spring_kn']:,.1f} kN = {pr['total_kn']:,.1f} kN "
           f"→ 필요 {pr['need_tf']:,.0f} tf · 고른 프레스: {pr['machine'] or '없음'}" + ("" if pr["ok"] else " (모자람 — 검토)"),
           f"전단 에너지 {pr['energy_j']:,.0f} J / 타 (파단 깊이 비 {pr['penetration']:g} t) · 닫힌 높이 {assy.shut:.1f} mm · "
           f"행정 ≥ {assy.stroke:.0f} mm"]
    if pr.get("shear_note"):
        out.append(pr["shear_note"])
    if u:
        out.append(f"스트립: 피치 {u['pitch']:.1f} × 폭 {u['width']:.1f} mm · 재료 이용률 {u['ratio'] * 100:.1f} % · "
                   f"제품 {u['part_kg']:.3f} kg / 피치 몫 {u['strip_kg']:.3f} kg")
    return out


def paint_strip(p, rect, assy: DieAssy):
    """스트립 배치 (위에서): 다이 플레이트 날 (다이 쪽) 을 공정 자리대로, 스트립 폭·피치, 이송 →."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
    die = assy.plate("다이 플레이트").prims[0]
    pitch, Wst = assy.strip
    opens = [c[0] for c in die.cuts if len(c) > 2 and not c[1]]
    if not opens:
        return
    P = np.vstack(opens)
    x0, x1 = P[:, 0].min() - 0.6 * pitch, P[:, 0].max() + 0.3 * pitch
    s = min(rect.width() / (x1 - x0), rect.height() / (Wst * 1.6))
    cx, cy = rect.x(), rect.y() + rect.height() / 2

    def T(x, y):
        return QPointF(cx + (x - x0) * s, cy - y * s)
    p.setPen(QPen(QColor(90, 90, 90), max(1.0, 0.002 * rect.width())))
    p.setBrush(QBrush(QColor(225, 232, 240)))
    p.drawRect(QRectF(T(x0, Wst / 2), T(x1, -Wst / 2)))
    # 앞 공정에서 뚫린 구멍은 피치마다 앞으로 (이송), 블랭크는 뒤 공정에 남은 모양 (회색 점선)
    big = max(opens, key=lambda Q: abs(_area(Q)))
    has_blank = any("블랭킹 펀치" == q.name for q in assy.parts)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(130, 130, 130), max(1.0, 0.0015 * rect.width()), Qt.DashLine))
    if has_blank:
        p.drawPolygon(QPolygonF([T(q[0] - pitch, q[1]) for q in big]))
    p.setBrush(QBrush(QColor(255, 255, 255)))
    for Q in opens:
        if has_blank and Q is big:
            continue
        for j in (1,):
            Qj = Q + np.array([j * pitch, 0.0])
            if Qj[:, 0].max() < x1:
                p.drawPolygon(QPolygonF([T(*q) for q in Qj]))
    p.setPen(QPen(QColor(200, 0, 0), max(1.0, 0.002 * rect.width())))
    p.setBrush(Qt.NoBrush)
    for Q in opens:
        p.drawPolygon(QPolygonF([T(*q) for q in Q]))
    p.setPen(QColor(20, 20, 20))
    p.drawText(QRectF(T(x0, Wst / 2 + 0.25 * Wst), T(x1, Wst / 2)), Qt.AlignLeft | Qt.AlignBottom,
               f"스트립 배치 — 피치 {pitch:.1f} · 폭 {Wst:.1f} mm · 이송 →  (빨강 = 다이 날)")


def render_strip(assy: DieAssy, w=1600, h=500):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint_strip(p, QRectF(10, 10, w - 20, h - 20), assy)
    p.end()
    return img


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
    # 날 치수표 · 프레스 · 스트립 배치
    y += 12
    cols = [34, 52, 26, 22, 22, 52, 52, 30]
    _row(p, R, m, y, cols, EDGE_HEAD, head=True)
    for row in assy.edges[:12]:
        y += 6
        _row(p, R, m, y, cols, row)
    y += 10
    for line in press_lines(assy):
        p.drawText(R(m, y, W - 2 * m, 5), Qt.AlignVCenter | Qt.AlignLeft, "• " + line)
        y += 5.5
    paint_strip(p, R(m, y + 4, W - 2 * m, H - m - y - 6), assy)
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
            if len(c) > 4 and c[4] == "slot":
                lay = "CONTOUR"                                  # 클램프 U 홈 (밀링) — 바깥 모양과 같이
            elif len(c) > 2 and c[1]:
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
