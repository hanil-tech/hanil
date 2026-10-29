"""주물 드로잉 금형 (OP10 드로우 다이, 주물 몸체): 다이 페이스 (dieface — 제품 + 어덴덤 + 바인더) 위에 세 몸체를 짠다.

  상형 다이 (FC300 주물)   — 형면 (제품 면 + t 오프셋) 이 오목하게 파인 윗형, 위에 리브 · 빈 곳, 가이드 부시
  펀치 (FCD550 주물)        — 형면이 볼록한 아랫형 가운데, 하형 베이스에 볼트 · 키, 바닥 리브, 에어 벤트
  누르개 (블랭크 홀더, FCD) — 펀치 둘레 고리, 윗면 = 바인더 평면, 쿠션 핀 (베이스 관통) 위에 뜸
  하형 베이스 (FC300 주물)  — 펀치 · 누르개를 받침, 가이드 포스트, 쿠션 핀 구멍, 밸런스 블록

형면은 프레스 방향을 z 로 한 높이장 (x, y → h) 을 격자로 떠서 B-스플라인 면 하나로 맞춘 것 (GeomAPI_PointsToBSplineSurface)
— 다이 R · 벽은 격자 간격으로 뭉뚱그려지니 NC 데이터는 CAD 형면으로, 여기 솔리드는 몸체 크기 · 무게 · 금형비 · 도면용.
하중: 드로잉력 F = 펀치 둘레 × t × 인장강도 × 0.7 (실무 어림, 원통 Siebel 식과 비슷한 자리), 누르개 힘 = 바인더 넓이 × 면압
(연강 2.5 MPa — 쿠션 능력 상한 어림, 실제는 드로우 비드 · 시타로). 주물 무게 = 솔리드 (리브 · 빈 곳 판 것) × 7.2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc
from . import diestd as ds
from .die3d import BOX, SHAPE, DieAssy, DiePart, Hole, Prim, _offset, _pin, _up5, _uslot, axi, screw

CAST = 7.2e-6             # 주철 kg/mm³
GRID = 90                 # 형면 격자 수 (긴 변)
PIN_KN = 40.0             # 쿠션 핀 하나가 받는 힘 (Ø40)
PIN_PITCH = 300.0         # 쿠션 핀 사이 거리 상한 (누르개 둘레 따라) — 큰 누르개가 휘지 않게 (실무 어림)
ETA_F = 0.65              # Siebel 변형 효율 η_F (마찰 · 굽힘-펴짐 몫, 0.5 ~ 0.7)
MU = 0.1                  # 누르개 ↔ 판 마찰 계수 (드로잉유)
OFFSET_CAP = 3.0          # 법선 오프셋의 수직 성분 t · √(1 + |∇h|²) 상한 (경사 70° 이상은 벽 — 윤곽 틈새로)
RIB, WALL, POCKET = 35.0, 45.0, 170.0   # 리브 두께 · 바깥 벽 · 빈 곳 피치


def _frame(df):
    z = np.asarray(df.z, float)
    z = z / np.linalg.norm(z)
    e1 = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(z, e1)
    return e1, e2, z


def _loops_between(F, region, a_set, b_set):
    """a 영역 삼각형과 b 영역 삼각형이 맞닿는 변들을 이어 닫힌 고리들 (꼭짓점 번호)."""
    from .forming import boundary_loops
    edges = {}
    for ti, tri in enumerate(F):
        ra = region[ti]
        for k in range(3):
            e = (int(tri[k]), int(tri[(k + 1) % 3]))
            key = (min(e), max(e))
            edges.setdefault(key, []).append(ra)
    sel = [k for k, rs in edges.items() if len(rs) == 2 and
           ((rs[0] in a_set and rs[1] in b_set) or (rs[1] in a_set and rs[0] in b_set))]
    if not sel:
        return []
    # 변들을 가짜 삼각형 (변 + 더미 점) 으로 만들어 boundary_loops 로 이음
    n = int(F.max()) + 1
    fake = np.array([[a, b, n + i] for i, (a, b) in enumerate(sel)])
    loops = []
    for lp in boundary_loops(fake):
        lp = [v for v in lp if v < n]
        if len(lp) >= 3:
            loops.append(lp)
    return loops


def _fit_surface(X, Y, Hz):
    """격자 높이장 → B-스플라인 면 (해석 곡면)."""
    from OCP.collections import Array2_double
    from OCP.GeomAbs import GeomAbs_C0
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    ny, nx = Hz.shape
    arr = Array2_double(1, nx, 1, ny)
    for i in range(nx):
        for j in range(ny):
            arr.SetValue(i + 1, j + 1, float(Hz[j, i]))
    # 1 차 (쌍선형) — 벽처럼 가파른 곳에서 고차 B-스플라인이 출렁이는 것 (깁스 현상) 을 피함, 격자 그대로 면
    api = GeomAPI_PointsToBSplineSurface(arr, float(X[0]), float(X[1] - X[0]), float(Y[0]), float(Y[1] - Y[0]),
                                         1, 1, GeomAbs_C0, 1e-3)
    return api.Surface()


def _half_space(surf, x0, x1, y0, y1, up, depth=3000.0):
    """면 위 (up) 또는 아래 솔리드: 면을 z 로 밀어낸 프리즘."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    face = BRepBuilderAPI_MakeFace(surf, 1e-4).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, depth if up else -depth)).Shape()


def offset_poly(poly, d, arc_step=6.0):
    """다각형을 d 만큼 바깥 (d < 0 안쪽) 으로 — OpenCASCADE 와이어 오프셋 (BRepOffsetAPI_MakeOffset, 모서리는 호).
    꼭짓점 법선 어림 (die3d._offset) 은 오목한 곳에서 선이 스스로 가로질러 (큰 후드의 누르개 안쪽) 프리즘 · 불리언이
    뒤집히므로 여기서는 진짜 오프셋을 쓴다. 호는 arc_step mm 쯤으로 잘게. 실패하면 어림으로."""
    from .die3d import _area, _simplify
    P = _simplify(np.asarray(poly, float), 0.5)
    if len(P) < 3 or abs(d) < 1e-9:
        return P
    if _area(P) < 0:
        P = P[::-1]
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
        from OCP.BRepTools import BRepTools_WireExplorer
        from OCP.GeomAbs import GeomAbs_Arc, GeomAbs_Line
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_REVERSED, TopAbs_WIRE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
        mk = BRepBuilderAPI_MakePolygon()
        for q in P:
            mk.Add(gp_Pnt(float(q[0]), float(q[1]), 0.0))
        mk.Close()
        face = BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()
        off = BRepOffsetAPI_MakeOffset(face, GeomAbs_Arc, False)
        off.Perform(float(d))
        if not off.IsDone():
            raise ValueError("offset")
        # 결과 와이어 중 가장 큰 것 (안쪽 오프셋이 여러 조각으로 갈라지면 큰 것)
        best = None
        exp = TopExp_Explorer(off.Shape(), TopAbs_WIRE)
        while exp.More():
            w = TopoDS.Wire(exp.Current())
            exp.Next()
            pts = []
            we = BRepTools_WireExplorer(w)
            while we.More():
                e = we.Current()
                we.Next()
                c = BRepAdaptor_Curve(e)
                a_, b_ = c.FirstParameter(), c.LastParameter()
                if c.GetType() == GeomAbs_Line:
                    n = 1
                else:
                    n = max(2, int(math.ceil(abs(b_ - a_) * max(c.Circle().Radius(), 1.0) / arc_step))
                             if c.GetType().name.endswith("Circle") else 8)
                rev = e.Orientation() == TopAbs_REVERSED
                for i in range(n):
                    u = a_ + (b_ - a_) * ((n - i) if rev else i) / n
                    q = c.Value(u)
                    pts.append((q.X(), q.Y()))
            if len(pts) >= 3:
                A = np.asarray(pts, float)
                if best is None or abs(_area(A)) > abs(_area(best)):
                    best = A
        if best is None:
            raise ValueError("no wire")
        if _area(best) < 0:
            best = best[::-1]
        return best
    except Exception:  # noqa: BLE001
        return _offset(P, d)


def _prism(poly, z0, h):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    from .die3d import _area, _simplify
    P = _simplify(np.asarray(poly, float), 1.0)          # 곧은 변만 (B-스플라인 변은 형면과의 불리언이 아주 느림)
    if _area(P) < 0:
        P = P[::-1]                                      # 반시계 — 시계 방향 와이어는 면이 뒤집혀 교집합이 빔
    mk = BRepBuilderAPI_MakePolygon()
    for q in P:
        mk.Add(gp_Pnt(float(q[0]), float(q[1]), float(z0)))
    mk.Close()
    face = BRepBuilderAPI_MakeFace(mk.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, float(h))).Shape()


def _box(x0, y0, z0, dx, dy, dz):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeBox(gp_Pnt(float(x0), float(y0), float(z0)), float(dx), float(dy), float(dz)).Shape()


def _common(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    op = BRepAlgoAPI_Common(a, b)
    if not op.IsDone():
        raise ValueError("솔리드 교집합 실패")
    return op.Shape()


def _cut(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    op = BRepAlgoAPI_Cut(a, b)
    return op.Shape() if op.IsDone() else a


def _nsolids(s):
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    ex = TopExp_Explorer(s, TopAbs_SOLID)
    n = 0
    while ex.More():
        n += 1
        ex.Next()
    return n


def _bbox(s):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(s, b, False, False)
    p0, p1 = b.CornerMin(), b.CornerMax()
    return (p0.X(), p0.Y(), p0.Z(), p1.X() - p0.X(), p1.Y() - p0.Y(), p1.Z() - p0.Z())


def _pockets(x0, x1, y0, y1, z0, depth, wall=WALL, rib=RIB, pitch=POCKET, avoid=()):
    """리브 사이 빈 곳 (네모) — [(poly, 0, z0, depth)] 꼴의 cuts. avoid: [(x, y, r)] 구멍 (쿠션 핀 · 가이드 포스트 · 볼트)
    둘레는 네모 보스로 남긴다 (주물 보스) — 구멍이 리브 벽에 스치면 불리언이 깨져 솔리드가 여러 조각이 되므로."""
    out = []
    nx = max(1, int((x1 - x0 - 2 * wall + rib) // (pitch + rib)))
    ny = max(1, int((y1 - y0 - 2 * wall + rib) // (pitch + rib)))
    px = (x1 - x0 - 2 * wall - (nx - 1) * rib) / nx
    py = (y1 - y0 - 2 * wall - (ny - 1) * rib) / ny
    if px < 40 or py < 40 or depth < 25:
        return out
    rects = []
    for i in range(nx):
        for j in range(ny):
            ax = x0 + wall + i * (px + rib)
            ay = y0 + wall + j * (py + rib)
            rects.append((ax, ay, ax + px, ay + py))
    for cx, cy, r in avoid:
        bx0, by0, bx1, by1 = cx - r, cy - r, cx + r, cy + r
        nxt = []
        for (ax0, ay0, ax1, ay1) in rects:
            if bx1 <= ax0 or bx0 >= ax1 or by1 <= ay0 or by0 >= ay1:
                nxt.append((ax0, ay0, ax1, ay1))
                continue
            # 네모에서 보스 네모를 뺀 네 조각 (왼 · 오른 세로 띠, 가운데 아래 · 위)
            mx0, mx1 = max(ax0, bx0), min(ax1, bx1)
            for cand in ((ax0, ay0, bx0, ay1), (bx1, ay0, ax1, ay1), (mx0, ay0, mx1, by0), (mx0, by1, mx1, ay1)):
                if cand[2] - cand[0] >= 40 and cand[3] - cand[1] >= 40:
                    nxt.append(cand)
        rects = nxt
    for ax0, ay0, ax1, ay1 in rects:
        poly = np.array([[ax0, ay0], [ax1, ay0], [ax1, ay1], [ax0, ay1]])
        out.append((poly, 0.0, z0, depth))
    return out


def _edge_slope(H, gx, gy):
    """격자점마다 경사 |∇h| — 앞 · 뒤 차분 중 작은 쪽 (평탄부 가장자리는 평탄부 쪽 법선이 수직이라 오프셋이 t 그대로)."""
    dx = float(gx[1] - gx[0])
    dy = float(gy[1] - gy[0])
    fx = np.diff(H, axis=1) / dx
    fy = np.diff(H, axis=0) / dy
    inf = np.full((H.shape[0], 1), np.inf)
    gxm = np.minimum(np.abs(np.hstack([inf, fx])), np.abs(np.hstack([fx, inf])))
    inf = np.full((1, H.shape[1]), np.inf)
    gym = np.minimum(np.abs(np.vstack([inf, fy])), np.abs(np.vstack([fy, inf])))
    return np.hypot(np.where(np.isfinite(gxm), gxm, 0.0), np.where(np.isfinite(gym), gym, 0.0))


@dataclass
class DrawLoads:
    """드로잉 하중 — 같은 둘레 원통으로 본 Siebel 식 (formsim.load_stroke 와 같은 틀) + 교재 표 식 중 큰 값."""
    d_eq: float            # 펀치 둘레 / π
    D0: float              # 블랭크 지름 (넓이 같은 원: 다이 페이스 겉넓이 = 블랭크 넓이)
    beta: float            # 드로잉비 D0 / d
    ldr: float             # 한계 드로잉비 (Whiteley · Hosford)
    f_tab: float           # π d t σb n(m)
    f_sie: float           # Siebel: π d t · 1.1 k_fm ln β / η_F + 2 μ F_N
    f_draw: float          # 둘 중 큰 값 (N)
    p_sie: float           # Siebel 누르개 면압 MPa (원통 컵 식 — 큰 패널은 d / 200 s 항이 커서 표 값으로 자름)
    p_tab: float           # 교재 표 면압 (쿠션 능력 상한) — 쓰는 값은 p_use = min(p_sie, p_tab)
    bhf: float             # 누르개 힘 N = p_sie × 누르개 고리 넓이
    r_die_rec: float       # 다이 어깨 R 권장 (Oehler · Kaiser)
    h: np.ndarray          # 펀치 깊이 축 (하중-행정 곡선)
    fd: np.ndarray         # 깊이마다 드로잉력 N
    fn: np.ndarray         # 깊이마다 누르개 힘 N
    i_peak: int            # 전체 하중이 가장 큰 곳
    cap: np.ndarray | None = None   # 고른 프레스의 깊이마다 능력 N
    press: dict | None = None
    ok: bool = False
    need_tf: float = 0.0   # 가장 빠듯한 깊이에서 필요한 정격 톤수 (하중 × 안전율 ÷ 톤수 곡선)

    @property
    def p_use(self):
        return min(self.p_sie, self.p_tab)


def draw_loads(per, A_blank, A_holder, t, mat, depth, r_die, machines=None, n=60):
    """주물 드로우 다이의 하중. per: 펀치 윤곽 둘레, A_blank: 블랭크 (다이 페이스 겉) 넓이, A_holder: 누르개가 누르는
    고리 넓이 (처음), depth: 드로잉 깊이, r_die: 다이 R.
    - 드로잉력: 교재 표 F = π d t σb n(m) (m = d / D0) 와 Siebel F = π d t · 1.1 k_fm ln β / η_F + 2 μ F_N (누르개 마찰 양면)
      중 큰 값 (diecalc.draw_plan 과 같은 두 식). 4ming 「Umformtechnik — Tiefziehen」 · Lange 「Handbook of Metal Forming」.
    - 누르개 면압: Siebel p = [(β − 1)^k + d / (200 s)] · Rm / 400, 교재 표 (연강 2.5 MPa …) 는 쿠션 능력 상한으로.
    - 하중-행정: 깊이 h 에서 플랜지 바깥 D(h) = √(D0² − 4 d h) (넓이 일정), F_N(h) = p × 남은 고리 넓이,
      F_d(h) = (이상 변형력 ln(D(h)/d) + 마찰) × (R 을 감는 동안 오르는 몫) — 꼭대기가 처음 ~ 중간 깊이에 옴.
    - 프레스: 모든 깊이에서 능력 (크랭크 곡선 costing.press_factor) ≥ (F_d + F_N) × 안전율, 행정 ≥ 2 × 깊이."""
    from . import costing as cs
    d = max(per / math.pi, 1e-6)
    D0 = max(math.sqrt(4 * A_blank / math.pi), d * 1.001)
    beta = D0 / d
    m = 1 / beta
    f_tab = math.pi * d * t * mat.tensile_mpa * dc.force_k(max(m, 0.55))
    p_sie = dc.siebel_holder_pressure(beta, d, t, mat)
    p_tab = dc.HOLDER_P[dc._family(mat.code)]
    bhf = min(p_sie, p_tab) * A_holder
    phi = math.log(beta)
    kfm = dc.mean_flow_stress(mat, phi)
    f_sie = math.pi * d * t * 1.1 * kfm * phi / ETA_F + 2 * MU * bhf
    f_draw = max(f_tab, f_sie)
    # 하중 - 행정
    h = np.linspace(0.0, depth, n)
    h_full = (D0 ** 2 - d ** 2) / (4 * d)
    D = np.sqrt(np.maximum(D0 ** 2 - 4 * d * np.minimum(h, h_full), d ** 2))
    ring0 = max(D0 ** 2 - (d + 2 * r_die) ** 2, 1e-9)
    fn = bhf * np.maximum(D ** 2 - (d + 2 * r_die) ** 2, 0.0) / ring0           # 남은 고리 넓이에 비례
    ideal = math.pi * d * t * 1.1 * kfm * np.log(np.maximum(D / d, 1.0)) / ETA_F
    rise = np.minimum(h / max(r_die + 3 * t, 1e-6), 1.0)
    fd = (ideal + 2 * MU * fn) * rise
    if fd.max() > 0:
        fd = fd * (f_draw / fd.max())                                             # 꼭대기를 두 식 중 큰 값에 맞춤
    total = fd + fn
    i_peak = int(np.argmax(total))
    mlist = machines if machines is not None else cs.DEFAULT_MACHINES
    presses = sorted([m_ for m_ in mlist if m_["kind"] == cs.PRESS], key=lambda m_: m_["capacity"])
    chosen, cap, ok = None, None, False
    need_tf = 0.0
    for m_ in presses:
        c = np.array([m_["capacity"] * dc.TON * cs.press_factor(m_, depth - hh) for hh in h])
        stroke = float(m_.get("stroke") or cs.default_stroke(m_["capacity"]))
        if np.all(c >= total * cs.SAFETY) and stroke >= 2 * depth:
            chosen, cap, ok = m_, c, True
            break
    if chosen is None and presses:
        chosen = presses[-1]
        cap = np.array([chosen["capacity"] * dc.TON * cs.press_factor(chosen, depth - hh) for hh in h])
    if chosen is not None:
        fac = np.array([max(cs.press_factor(chosen, depth - hh), 1e-3) for hh in h])
        need_tf = float(np.max(total * cs.SAFETY / fac)) / dc.TON
    else:
        need_tf = float(total[i_peak]) * cs.SAFETY / dc.TON
    return DrawLoads(d, D0, beta, dc.ldr(mat), f_tab, f_sie, f_draw, p_sie, p_tab, bhf, dc.die_radius(D0, d, t),
                     h, fd, fn, i_peak, cap, chosen, ok, need_tf)


def design(df, result, settings: bc.BendSettings, machines=None, rates=None):
    """다이 페이스 → 주물 드로잉 금형 (DieAssy)."""
    from . import costing as cs
    from . import dieface as dfm
    from .die3d import DENSITY
    t = float(result.thickness)
    mat = settings.mat
    uts = mat.tensile_mpa
    e1, e2, z = _frame(df)
    V = np.asarray(df.V, float)
    X = V @ e1
    Y = V @ e2
    Hh = -(V @ z)                                        # 위 = 펀치 쪽: 바인더가 가장 낮고 제품 바닥이 가장 높음 (쿠션식)
    F = np.asarray(df.F)
    region = np.asarray(df.region)
    hb = float(Hh[df.outer].min())
    # 바인더 바깥 고리 · 펀치 개구 (어덴덤 ↔ 바인더 경계)
    outer = np.column_stack([X[df.outer], Y[df.outer]])
    lps = _loops_between(F, region, {dfm.PRODUCT, dfm.ADDENDUM}, {dfm.BIND})
    if not lps:
        raise ValueError("펀치 개구 (어덴덤 ↔ 바인더 경계) 를 못 찾음")
    lp = max(lps, key=len)
    binder_start = np.column_stack([X[lp], Y[lp]])
    if _area2(binder_start) < 0:
        binder_start = binder_start[::-1]                # 반시계로 (offset 의 안 · 밖이 방향에 달림)
    if _area2(outer) < 0:
        outer = outer[::-1]
    r_d = float(df.r_die)
    cell = float(np.ptp(outer, 0).max()) / GRID * 1.4
    punch_poly = offset_poly(binder_start, -r_d)                        # 펀치 윤곽: 다이 R 안쪽
    holder_in = offset_poly(binder_start, t + 1.0)
    # 치수
    depth = float(Hh.max()) - hb
    bx0, by0 = outer.min(0)
    bx1, by1 = outer.max(0)
    Lb, Wb = bx1 - bx0, by1 - by0
    m_h = 40.0                                           # 누르개 바깥 = 바인더 끝 + 40
    hx0, hx1, hy0, hy1 = bx0 - m_h, bx1 + m_h, by0 - m_h, by1 + m_h
    post_d = 50.0 if max(Lb, Wb) < 900 else 63.0 if max(Lb, Wb) < 1500 else 80.0
    m_d = post_d + 70.0                                  # 다이 · 베이스 바깥 = 누르개 + 가이드 자리
    dx0, dx1, dy0, dy1 = hx0 - m_d, hx1 + m_d, hy0 - m_d, hy1 + m_d
    L, W = dx1 - dx0, dy1 - dy0
    Th = _up5(max(80.0, 0.08 * max(Lb, Wb)))            # 누르개 두께
    g_bdc = 10.0
    z_base_top = hb - Th - g_bdc                         # 하사점에서 누르개 밑면이 베이스 위 10
    Tb = _up5(max(150.0, 0.12 * max(L, W)))              # 베이스 두께 (리브)
    z_base0 = z_base_top - Tb
    Hd = 150.0                                           # 상형 몸체 (형면 위)
    z_top_bdc = hb + depth + t + Hd
    g_load = max(60.0, 0.5 * depth)                     # 열림: 블랭크 넣는 틈
    travel = depth + g_load
    # 형면 격자 → B-스플라인
    from scipy.interpolate import LinearNDInterpolator
    n = GRID
    gx = np.linspace(dx0 - 10, dx1 + 10, n if L >= W else max(int(n * L / W), 12))
    gy = np.linspace(dy0 - 10, dy1 + 10, n if W > L else max(int(n * W / L), 12))
    GX, GY = np.meshgrid(gx, gy)
    interp = LinearNDInterpolator(np.column_stack([X, Y]), Hh, fill_value=hb)
    Hz = interp(GX, GY)
    Hz = np.where(np.isnan(Hz), hb, Hz)
    from .die3d import _inside
    # 바인더 밖은 평면
    xs_, ys_ = GX.ravel(), GY.ravel()
    inb = np.array([_inside(outer, (x_, y_)) for x_, y_ in zip(xs_, ys_)]).reshape(GX.shape)
    Hz = np.where(inb, Hz, hb)
    Hz = np.maximum(Hz, hb)
    # 벽이 수직 (컵처럼) 이면 쌍선형 면 조각이 각기둥 옆면과 나란해 불리언이 실패 — 3 × 3 평균으로 두 칸 경사로 (등고선은 원래 격자)
    from scipy.ndimage import uniform_filter
    Hs = np.maximum(uniform_filter(Hz, size=3, mode="nearest"), hb)
    # 상형 형면 = 펀치 형면의 법선 오프셋 t. 높이장 h(x, y) 의 법선 오프셋을 같은 (x, y) 에서 재면 수직 거리
    # t · √(1 + |∇h|²) (= t / cos θ, 평면 조각마다 정확). 벽 (70° 넘는 경사) 은 상한 — 거기는 윤곽 틈새가 맡음.
    gy_, gx_ = np.gradient(Hs, gy, gx)
    slope = np.hypot(gx_, gy_)
    Hd = Hs + t * np.minimum(np.sqrt(1.0 + _edge_slope(Hs, gx, gy) ** 2), OFFSET_CAP)
    Hz_d = Hz + t * np.minimum(np.sqrt(1.0 + _edge_slope(Hz, gx, gy) ** 2), OFFSET_CAP)      # 등고선용 (원래 격자)
    surf_p = _fit_surface(gx, gy, Hs)
    surf_d = _fit_surface(gx, gy, Hd)
    # 솔리드
    # 몸체 = 각기둥에서 형면 위 (또는 아래) 반공간을 뺌 — 교집합 (Common) 은 둥근 윤곽에서 빈 결과를 내기도 함
    above_p = _half_space(surf_p, gx[0], gx[-1], gy[0], gy[-1], up=True)
    below_d = _half_space(surf_d, gx[0], gx[-1], gy[0], gy[-1], up=False)
    steep = float(np.nanmax(slope)) > math.tan(math.radians(60))
    if steep:
        # 수직 벽 (컵): 각기둥 옆면이 형면 경사로와 겹쳐 불리언이 실패 — 윤곽 각기둥을 제품 바닥 높이까지 세우고,
        # 안쪽 (경사로 안) 만 형면으로 깎음 (펀치 R 은 CAD 에서)
        inner = offset_poly(punch_poly, -(3.0 * cell + 2.0))
        cap = _common(above_p, _prism(inner, z_base_top, 2000.0))
        punch = _cut(_prism(punch_poly, z_base_top, hb + depth - z_base_top), cap)
    else:
        punch = _cut(_prism(punch_poly, z_base_top, 2000.0), above_p)
    # 누르개: 윗면 = 바인더 평면 (평평) — 고리 상자에서 안쪽만 뺌
    holder = _cut(_box(hx0, hy0, hb - Th, hx1 - hx0, hy1 - hy0, Th), _prism(holder_in, hb - Th - 1, Th + 2))
    # 상형: 밑면 = 바인더 + t 평면, 형면 오목부 (바인더 시작 + 다이 R 안) 만 형면 반공간으로 파냄 — 작은 공구가 불리언에 안전
    cav = _common(below_d, _prism(offset_poly(binder_start, r_d + 2 * cell + 2), hb - 1, depth + t + 60))
    die = _cut(_box(dx0, dy0, hb + t, L, W, z_top_bdc - hb - t), cav)
    for nm_, sh_ in (("펀치", punch), ("누르개", holder), ("상형", die)):
        if _nsolids(sh_) != 1:
            raise ValueError(f"{nm_} 몸체를 못 만듦 (형면과의 불리언 결과 {_nsolids(sh_)} 조각)")
    base = _box(dx0, dy0, z_base0, L, W, Tb)
    # 열린 상태: 상형은 travel 만큼 위로
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(0, 0, float(travel)))
    die_open = BRepBuilderAPI_Transform(die, tr, True).Shape()
    # 누르개 열린 자리: 쿠션 핀이 올려 depth 만큼 위 (윗면 = 바인더 + depth → 펀치 끝보다 위)
    tr2 = gp_Trsf()
    tr2.SetTranslation(gp_Vec(0, 0, float(depth)))
    holder_open = BRepBuilderAPI_Transform(holder, tr2, True).Shape()
    parts = []

    def add(name, qty, material, size, prims, std=False, note="", upper=False, order=""):
        parts.append(DiePart(len(parts) + 1, name, qty, material, size, std, note, prims, upper, order))
        return parts[-1]
    p_base = Prim(SHAPE, _bbox(base), shape=base, density=CAST)       # 리브 · 빈 곳은 구멍 자리를 다 정한 뒤 (맨 아래)
    p_punch = Prim(SHAPE, _bbox(punch), shape=punch, density=CAST)
    p_punch.grid = {"gx": gx, "gy": gy, "hz": Hz, "poly": punch_poly, "dz": 0.0}
    px0, py0 = punch_poly.min(0)
    px1, py1 = punch_poly.max(0)
    inner_p = offset_poly(punch_poly, -70.0)
    if len(inner_p) >= 3 and np.ptp(inner_p[:, 0]) > 80 and np.ptp(inner_p[:, 1]) > 80:
        z_pk = min(hb + depth - 60, hb - 10)                 # 빈 곳 꼭대기: 형면 아래 60, 바인더 높이 아래 10 (벽 빼기 안쪽)
        punch_pockets = (inner_p[:, 0].min(), inner_p[:, 0].max(), inner_p[:, 1].min(), inner_p[:, 1].max(),
                         z_base_top - 1, z_pk - z_base_top + 1)
    else:
        punch_pockets = None
    p_hold = Prim(SHAPE, _bbox(holder_open), shape=holder_open, density=CAST)
    p_die = Prim(SHAPE, _bbox(die_open), shape=die_open, density=CAST)
    p_die.grid = {"gx": gx, "gy": gy, "hz": Hz_d, "poly": np.array([[dx0, dy0], [dx1, dy0], [dx1, dy1], [dx0, dy1]]),
                  "dz": travel}
    z_die_top_open = z_top_bdc + travel
    p_die.cuts += _pockets(dx0, dx1, dy0, dy1, hb + depth + t + 60 + travel, z_die_top_open - (hb + depth + t + 60 + travel) + 1)
    add("하형 베이스", 1, "FC300 (주물)", f"{L:.0f} × {W:.0f} × {Tb:.0f}", [p_base],
        note="펀치 · 누르개 받침, 쿠션 핀 관통, 가이드 포스트 압입 · 바닥 리브")
    pp = add("드로우 펀치", 1, "FCD550 (주물)", f"{px1 - px0:.0f} × {py1 - py0:.0f} × {hb + depth - z_base_top:.0f}", [p_punch],
             note=f"형면 (제품 안쪽 면) · 펀치 R · 벽 빼기 {df.wall_deg:g}° · 바닥 리브 · 에어 벤트")
    ph = add("누르개 (블랭크 홀더)", 1, "FCD550 (주물)", f"{hx1 - hx0:.0f} × {hy1 - hy0:.0f} × {Th:.0f}", [p_hold],
             note=f"윗면 = 바인더 평면 (화염 경화), 안쪽 = 펀치 + {t + 1:.1f} · 쿠션 핀 위에 뜸 · 드로우 비드는 시타 뒤")
    pd = add("상형 다이", 1, "FC300 (주물)", f"{L:.0f} × {W:.0f} × {z_top_bdc - hb:.0f}", [p_die], upper=True,
             note=f"형면 = 펀치 형면의 법선 오프셋 t {t:g} (수직 성분 t·√(1+|∇h|²)), 다이 R{r_d:g} 화염 경화 · 위 리브")
    # 형면 넓이 (NC 시간)
    from .unfolder import _tri_areas3
    A_face_m2 = float(_tri_areas3(V, F).sum()) * 1e-6
    A_bind = (float(abs(_area2(outer))) - float(abs(_area2(binder_start)))) * 1e-6
    pp.face_m2 = A_face_m2 * 1.1
    pd.face_m2 = A_face_m2 * 1.1 + A_bind
    ph.face_m2 = A_bind
    # 가이드 포스트 · 부시 (네 귀)
    cx, cy = 0.5 * (dx0 + dx1), 0.5 * (dy0 + dy1)
    gpx, gpy = (L / 2 - post_d / 2 - 25), (W / 2 - post_d / 2 - 25)
    corners = [(cx + sx * gpx, cy + sy * gpy) for sx in (-1, 1) for sy in (-1, 1)]
    post_L = _up5(max(z_top_bdc - 30 - z_base0, hb + travel + 30 - z_base0))   # 열린 상태에서도 물림 ≥ 30 (깊은 제품)
    bush_o = post_d + 20
    for x, y in corners:
        p_base.holes.append(Hole(x, y, post_d, "압입", z_base0, Tb, f"Ø{post_d:g} H7 (포스트 압입) 관통"))
        p_die.holes.append(Hole(x, y, bush_o, "압입", hb + travel, z_die_top_open - (hb + travel), f"Ø{bush_o:g} H7 (부시 압입) 관통"))
        p_hold.holes.append(Hole(x, y, post_d + 6, "통과", hb - Th + depth, Th, f"Ø{post_d + 6:g} 통과 (포스트 피함)")) \
            if hx0 < x < hx1 and hy0 < y < hy1 else None
    add("가이드 포스트", 4, "SUJ2 HRC 60", f"Ø{post_d:g} × {post_L:.0f}",
        [axi(x, y, [(z_base0, post_L - 3, post_d / 2, post_d / 2), (z_base0 + post_L - 3, 3, post_d / 2, post_d / 2 - 2)])
         for x, y in corners], std=True, order=f"가이드 포스트 Ø{post_d:g} L{post_L:.0f} (대형 압입형)")
    Lbush = _up5(z_top_bdc - hb)
    add("가이드 부시", 4, "FC250 + 동합금", f"Ø{post_d:g} 안 × Ø{bush_o:g} 밖 × {Lbush:.0f}",
        [axi(x, y, [(z_die_top_open - Lbush, Lbush, bush_o / 2, bush_o / 2)], bore=post_d / 2) for x, y in corners],
        std=True, upper=True, order=f"가이드 부시 Ø{post_d:g} × Ø{bush_o:g} L{Lbush:.0f}")
    eng_open = (z_base0 + post_L) - (hb + travel)
    # 하중
    per = float(np.linalg.norm(np.roll(punch_poly, -1, 0) - punch_poly, axis=1).sum())
    A_b = float(abs(_area2(outer)) - abs(_area2(holder_in)))
    from .unfolder import _tri_areas3
    A_face = float(_tri_areas3(V, F).sum())                           # 다이 페이스 겉넓이 = 블랭크 넓이 (두께 일정)
    mlist = machines if machines is not None else cs.DEFAULT_MACHINES
    ld = draw_loads(per, A_face, A_b, t, mat, depth, r_d, mlist)
    F_draw, BHF = ld.f_draw, ld.bhf
    ring_len = float(np.linalg.norm(np.roll(holder_in, -1, 0) - holder_in, axis=1).sum())
    n_pin = max(4, int(math.ceil(BHF / (PIN_KN * 1000))), int(math.ceil(ring_len / PIN_PITCH)))   # 큰 누르개는 간격으로도
    # 쿠션 핀: 누르개 고리 안에 고르게 (둘레 따라)
    ring_pts = _ring_points(hx0, hx1, hy0, hy1, holder_in, n_pin, inset=35.0)
    pin_d = 40.0
    pins = []
    for x, y in ring_pts:
        p_base.holes.append(Hole(x, y, pin_d + 2, "통과", z_base0, Tb, f"Ø{pin_d + 2:g} 통과 (쿠션 핀)"))
        pins.append(axi(x, y, [(z_base0 - 40, Tb + 40 + (hb - Th + depth - z_base_top), pin_d / 2, pin_d / 2)]))
    add("쿠션 핀", len(pins), "S45C 조질", f"Ø{pin_d:g} × {Tb + 40 + (hb - Th + depth - z_base_top):.0f}", pins, std=True,
        order=f"쿠션 핀 Ø{pin_d:g} (프레스 쿠션 핀 배열에 맞춤) × {len(pins)}",
        note=f"누르개 힘 {BHF / 1000:,.0f} kN ÷ {PIN_KN:g} kN = {n_pin} 개 — 프레스 쿠션 능력 확인")
    # 밸런스 블록 (누르개 네 귀 아래, 하사점 받침) · 마모판 (누르개 옆 안내)
    bal = []
    for x, y in ((hx0 + 60, hy0 + 60), (hx1 - 60, hy0 + 60), (hx0 + 60, hy1 - 60), (hx1 - 60, hy1 - 60)):
        bal.append(Prim(BOX, (x - 40, y - 40, z_base_top, 80, 80, g_bdc - 0.5)))
    add("밸런스 블록 (스토퍼)", 4, "S50C", f"80 × 80 × {g_bdc - 0.5:.1f}", bal, std=True,
        note="하사점에서 누르개를 받침 (심으로 높이 맞춤) · 상형과 0.5 틈")
    wear = []
    for (x, y, dx_, dy_) in ((hx0 - 12, hy0 + 40, 12, hy1 - hy0 - 80), (hx1, hy0 + 40, 12, hy1 - hy0 - 80),
                             (hx0 + 40, hy0 - 12, hx1 - hx0 - 80, 12), (hx0 + 40, hy1, hx1 - hx0 - 80, 12)):
        wear.append(Prim(BOX, (x, y, hb - Th - 20 + depth, dx_, dy_, Th + 20)))
    add("마모판 (누르개 안내)", 4, "SKD11 + 흑연 (무급유)", f"{Th + 20:.0f} × 12", wear, std=True, upper=False,
        note="누르개 옆면 안내 — 베이스 벽에 볼트, 흑연 매립 무급유")
    # 펀치 고정 볼트 (베이스 밑에서 펀치 탭) · 키
    M = 20 if max(px1 - px0, py1 - py0) > 500 else 16
    k, kh, d1, cb, cbh, tap = ds.SHCS.get(M, ds.SHCS[16])
    bolts = []
    inner = offset_poly(punch_poly, -(2.5 * M))
    per_in = float(np.linalg.norm(np.roll(inner, -1, 0) - inner, axis=1).sum()) if len(inner) >= 3 else 0.0
    n_bolt = max(2, min(max(6, int(per // 250)), int(per_in // (3.0 * M))))      # 작은 펀치: 볼트끼리 3 d 띄움
    bxy = []
    if len(inner) >= 3 and min(np.ptp(inner, 0)) >= 2.0 * M:
        bxy = _ring_points(inner.min(0)[0], inner.max(0)[0], inner.min(0)[1], inner.max(0)[1], None,
                           n_bolt, inset=0.0, poly=inner)[:n_bolt]
    if len(bxy) < 2 or min(math.hypot(a_[0] - b_[0], a_[1] - b_[1]) for i_, a_ in enumerate(bxy)
                           for b_ in bxy[i_ + 1:]) < 3.0 * M:
        # 작은 펀치: 긴 방향 양 끝 두 개 (3 d 띄움), 그것도 안 되면 가운데 하나
        bxy = [(px0 + 2.5 * M, cy), (px1 - 2.5 * M, cy)]
        if px1 - px0 - 5.0 * M < 3.0 * M:
            bxy = [(0.5 * (px0 + px1), cy)]
    for x, y in bxy:
        p_base.holes.append(Hole(x, y, d1, "통과", z_base0, Tb, f"Ø{d1:g} 통과, 자리 Ø{cb:g} 깊이 {cbh:g} (펀치 볼트)",
                                 cb=(cb, z_base0, cbh), side="밑면"))
        p_punch.holes.append(Hole(x, y, tap, "탭", z_base_top, 2 * M, f"M{M} 탭 깊이 {2 * M:g} (밑면, 드릴 Ø{tap:g})", side="밑면"))
        Lb_ = ds.up_std(Tb - cbh + 1.5 * M, ds.SHCS_L + (160, 180, 200, 220, 250))
        bolts.append(screw(x, y, z_base0 + cbh - kh, M, kh, k, Lb_, True))
    add(f"육각 구멍 붙이 볼트 M{M} (펀치)", len(bolts), "SCM435 (12.9)", f"M{M} × {Lb_:.0f}", bolts, std=True,
        order=f"JIS B 1176 M{M} × {Lb_:.0f}")
    kx = min(60.0, 0.25 * (px1 - px0))
    key_xy = [(px0 + kx, cy), (px1 - kx, cy)]
    if any(math.hypot(x - a_, y - b_) < 25.0 for x, y in key_xy for a_, b_ in bxy):      # 볼트와 겹치면 옆으로
        key_xy = [(px0 + kx, cy + 0.25 * (py1 - py0)), (px1 - kx, cy - 0.25 * (py1 - py0))]
    keys = [_pin(x, y, z_base_top - 40, 25.0, 80.0) for x, y in key_xy]
    add("위치 키 (다우얼)", 2, "SUJ2 (m6)", "Ø25 × 80", keys, std=True, order="평행 핀 Ø25 m6 × 80 (펀치 ↔ 베이스)")
    # 에어 벤트 (펀치 형면 낮은 곳)
    low = np.column_stack([X, Y])[np.argsort(-Hh)[:200]]              # 펀치 꼭대기 (제품 바닥) — 공기가 갇히는 곳
    vents = []
    taken = list(bxy) + list(key_xy)
    for q in low[::40]:
        if _inside(punch_poly, (q[0], q[1])) and all(math.hypot(q[0] - a, q[1] - b) > 60 for a, b in vents) \
                and all(math.hypot(q[0] - a, q[1] - b) > 30 for a, b in taken):          # 볼트 · 키와 안 겹치게
            vents.append((float(q[0]), float(q[1])))
    for x, y in vents[:6]:
        p_punch.holes.append(Hole(x, y, 6.0, "에어 벤트", z_base_top, hb + depth - z_base_top, "Ø6 에어 벤트 (형면 → 바닥 빈 곳)"))
    # 클램프 홈 · 아이볼트
    slot_w = 26.0 if max(L, W) < 1200 else 32.0
    for shoe, z0_, h_ in ((p_base, z_base0, Tb), (p_die, hb + travel, z_die_top_open - (hb + travel))):
        for sxn in (-1, 1):
            for yy in (cy - 0.3 * W, cy + 0.3 * W):
                shoe.cuts.append((_uslot(cx + sxn * L / 2, yy, slot_w, 45.0, sxn), 0.0, z0_ - 1, h_ + 2, "slot"))
        for sg in (-1, 1):
            for xx in (cx - L / 4, cx + L / 4):
                shoe.holes.append(Hole(xx, (dy1 if sg > 0 else dy0), 21.0, "탭", z0_ + h_ / 2, 41,
                                       "M24 탭 깊이 41 (옆면 아이볼트, 드릴 Ø21)", side="앞면" if sg < 0 else "뒷면",
                                       axis="-y" if sg > 0 else "+y"))
    # 프레스 · 점검
    F_total = F_draw + BHF
    need_t = ld.need_tf
    stroke = 2 * depth + g_load
    mach, ok = ld.press, ld.ok
    h_pk = float(ld.h[ld.i_peak])
    checks = []

    def chk(item, val, crit, good):
        checks.append([item, val, crit, "적합" if good else "검토"])
    chk("프레스 (쿠션 포함)", f"{mach['name'] if mach else '없음'} (필요 {need_t:,.0f} tf, 행정 ≥ {stroke:.0f})",
        f"모든 깊이에서 (드로잉 + 누르개) × {cs.SAFETY:g} ≤ 톤수 곡선 — 꼭대기 "
        f"{(ld.fd[ld.i_peak] + ld.fn[ld.i_peak]) / 1000:,.0f} kN 이 깊이 {h_pk:.0f} (하사점 위 {depth - h_pk:.0f})", bool(ok))
    chk("드로잉비 β", f"{ld.beta:.2f} (d {ld.d_eq:.0f} ← D₀ {ld.D0:.0f})", f"≤ LDR {ld.ldr:.2f} (Whiteley · Hosford, r̄ {mat.r:g})",
        ld.beta <= ld.ldr)
    rr = r_d / t
    chk("다이 R", f"R{r_d:g} = {rr:.1f} t", f"5 ~ 10 t (4ming) · Oehler 권장 R{ld.r_die_rec:.1f}", 5.0 <= rr <= 10.0)
    chk("쿠션 핀 수", f"{len(pins)} 개", f"≥ max({BHF / 1000:,.0f} kN ÷ {PIN_KN:g}, 둘레 {ring_len:,.0f} ÷ {PIN_PITCH:g}) = {n_pin}",
        len(pins) >= n_pin)
    chk("가이드 물림 (열림)", f"{eng_open:.0f} mm", "≥ 30 mm (블랭크 넣을 때도 안내)", eng_open >= 30)
    chk("누르개 면압", f"{ld.p_use:.2f} MPa" + (f" (Siebel {ld.p_sie:.1f} 는 원통 식이라 표 값으로 자름)" if ld.p_sie > ld.p_tab else " (Siebel)"),
        f"≤ 표 값 {ld.p_tab:g} MPa (쿠션 능력 상한)", True)
    chk("에어 벤트", f"{min(len(vents), 6)} 개", "≥ 1 (형면 낮은 곳)", len(vents) >= 1)
    chk("누르개 밑 ↔ 베이스 (하사점)", f"{g_bdc:g} mm", "≥ 10 (밸런스 블록 위)", True)
    kg = sum(p.weight * p.qty for p in parts)
    notes = [f"OP10 드로잉 (주물 금형): 깊이 {depth:.0f} mm · 바인더 {Lb:.0f} × {Wb:.0f} · 다이 R{r_d:g} · 벽 {df.wall_deg:g}°",
             f"드로잉력: 같은 둘레 원통 d = {per:,.0f} / π = {ld.d_eq:.0f}, 블랭크 D₀ = √(4 × {A_face * 1e-6:.3f} m² / π) = {ld.D0:.0f} "
             f"(β {ld.beta:.2f}) — 교재 표 π d t σb n(m) {ld.f_tab / 1000:,.0f} kN / Siebel π d t · 1.1 k_fm ln β / η_F {ETA_F:g} "
             f"+ 2 μ F_N {ld.f_sie / 1000:,.0f} kN 중 큰 값 {F_draw / 1000:,.0f} kN (UTS {uts:.0f} · n {mat.n:g})",
             f"누르개 힘 = 면압 {ld.p_use:.2f} MPa (Siebel [(β − 1)^k + d / 200 s] Rm / 400 = {ld.p_sie:.2f}, 표 값 {ld.p_tab:g} 중 작은 값) "
             f"× 고리 {A_b * 1e-6:.3f} m² = {BHF / 1000:,.0f} kN → 프레스 {need_t:,.0f} tf"
             + (f" — {mach['name']}" if mach else "") + f", 하중 꼭대기는 깊이 {h_pk:.0f} mm (하중 - 행정 곡선은 부품표 엑셀)",
             f"높이: 닫힌 {z_top_bdc - z_base0:.0f} · 열린 {z_die_top_open - z_base0:.0f} mm · 행정 ≥ {stroke:.0f} (깊이 × 2 + 틈 {g_load:.0f})",
             f"주물 무게 어림 {kg:,.0f} kg (리브 · 빈 곳 판 솔리드 × 7.2) — 베이스 {parts[0].weight:,.0f} · 펀치 {pp.weight:,.0f} · "
             f"누르개 {ph.weight:,.0f} · 상형 {pd.weight:,.0f}",
             f"형면은 격자 {gx[1] - gx[0]:.0f} mm 의 쌍선형 면 근사 (다이 R · 벽은 뭉뚱그려짐) — NC 데이터는 CAD 형면으로, "
             f"상형 형면 = 펀치 형면의 법선 오프셋 t (수직 성분 t·√(1+|∇h|²), 경사 70° 넘는 벽은 × {OFFSET_CAP:g} 상한)" + (" · 벽이 수직이라 펀치 옆면은 윤곽 그대로, 펀치 R 은 CAD 에서" if steep else ""),
             "드로우 비드 · 누르개 면압 · 스프링백 보정은 시타 (트라이아웃) 로 — 비드 자리는 성형 해석 draw-in 이 큰 변",
             "표준품 (가이드 · 쿠션 핀 · 마모판) 치수는 일반값 — MISUMI · 후타바 대형 금형 표로 확인"]
    a = DieAssy("OP10 드로우 (주물)", parts, L, W, z_top_bdc - z_base0, F_draw, notes, None, [], checks, (0.0, 0.0),
                z_die_top_open - z_base0, stroke, (0.0, 0.0), None, [],
                {"draw_kn": F_draw / 1000, "bhf_kn": BHF / 1000, "need_tf": need_t, "machine": mach["name"] if mach else "",
                 "ok": bool(ok), "beta": ld.beta, "ldr": ld.ldr, "p_sie": ld.p_sie, "f_tab_kn": ld.f_tab / 1000,
                 "f_sie_kn": ld.f_sie / 1000, "r_die_rec": ld.r_die_rec, "h_peak": h_pk})
    a.loads = ld
    a.cast = True
    a.spec = [("공정", "OP10 드로우 (주물 금형)"), ("드로잉력 / 누르개", f"{F_draw / 1000:,.0f} / {BHF / 1000:,.0f} kN (β {ld.beta:.2f})"),
              ("필요 프레스", f"{need_t:,.0f} tf → {mach['name'] if mach else '-'}"), ("드로잉 깊이", f"{depth:.0f} mm"),
              ("쿠션 핀", f"Ø{pin_d:g} × {len(pins)}"), ("주물 무게", f"{kg:,.0f} kg")]
    a.y_cut = float(cy)
    # 리브 · 빈 곳 — 구멍 (쿠션 핀 · 가이드 포스트 · 볼트 · 벤트) 둘레는 보스로 남김
    p_base.cuts += _pockets(dx0, dx1, dy0, dy1, z_base0 - 1, Tb - 60 + 1,
                            avoid=[(h.x, h.y, h.d / 2 + RIB / 2 + 2) for h in p_base.holes if h.axis == "z"])
    if punch_pockets is not None:
        p_punch.cuts += _pockets(*punch_pockets, wall=0.0,
                                 avoid=[(h.x, h.y, h.d / 2 + RIB / 2 + 2) for h in p_punch.holes if h.axis == "z"])
    # 금형 좌표를 베이스 밑면 0 · 가운데 0 으로
    from .bendie import shift_prim
    for p in parts:
        for pr in p.prims:
            _shift_shape(pr, -cx, -cy, -z_base0)
            shift_prim(pr, -cx, -cy, -z_base0) if pr.kind != SHAPE else None
    a.y_cut = 0.0
    # 제품 선 (성형 뒤, 열린 상태의 펀치 위) — 트림선 · 바인더 끝
    from .forming import boundary_loops
    work = []
    for lp_ in boundary_loops(F):
        Q = np.column_stack([X[lp_] - cx, Y[lp_] - cy, Hh[lp_] - z_base0 + depth + t / 2])   # 열린 상태 (누르개 올라옴)
        work.append((np.vstack([Q, Q[:1]]), "after"))
    a.work = work
    return a


def _shift_shape(pr, dx, dy, dz):
    if pr.kind != SHAPE:
        return
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    tr = gp_Trsf()
    tr.SetTranslation(gp_Vec(float(dx), float(dy), float(dz)))
    pr.shape = BRepBuilderAPI_Transform(pr.shape, tr, True).Shape()
    g = getattr(pr, "grid", None)
    if g:
        pr.grid = dict(g, gx=np.asarray(g["gx"]) + dx, gy=np.asarray(g["gy"]) + dy, hz=np.asarray(g["hz"]) + dz,
                       poly=np.asarray(g["poly"], float) + (dx, dy))
    x0, y0, z0, a, b, c = pr.p
    pr.p = (x0 + dx, y0 + dy, z0 + dz, a, b, c)
    pr.cuts = [tuple([np.asarray(cc[0], float) + (dx, dy), cc[1]] + ([cc[2] + dz, cc[3]] if len(cc) > 2 else [])
                     + list(cc[4:])) for cc in pr.cuts]
    for h in pr.holes:
        h.x += dx
        h.y += dy
        h.z0 += dz
        if h.cb:
            h.cb = (h.cb[0], h.cb[1] + dz, h.cb[2])


def _area2(P):
    P = np.asarray(P, float)
    return 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))


def _ring_points(x0, x1, y0, y1, inner, n, inset=35.0, poly=None):
    """상자 (x0..x1, y0..y1) 안쪽 inset 둘레 (또는 poly 안쪽 둘레) 를 따라 n 개 고르게 — inner 다각형 안은 피함."""
    from .die3d import _inside
    if poly is not None:
        P = np.asarray(poly, float)
        seg = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        per = seg.sum()
        pts = []
        for s_ in np.linspace(0, per, n, endpoint=False) + per / (2 * n):
            acc = 0.0
            for i in range(len(P)):
                if acc + seg[i] >= s_:
                    u = (s_ - acc) / max(seg[i], 1e-9)
                    pts.append(tuple(P[i] + u * (P[(i + 1) % len(P)] - P[i])))
                    break
                acc += seg[i]
        return pts
    a, b = x1 - x0 - 2 * inset, y1 - y0 - 2 * inset
    per = 2 * (a + b)
    pts = []
    for s_ in np.linspace(0, per, n, endpoint=False) + per / (2 * n):
        if s_ < a:
            q = (x0 + inset + s_, y0 + inset)
        elif s_ < a + b:
            q = (x1 - inset, y0 + inset + s_ - a)
        elif s_ < 2 * a + b:
            q = (x1 - inset - (s_ - a - b), y1 - inset)
        else:
            q = (x0 + inset, y1 - inset - (s_ - 2 * a - b))
        if inner is None or not _inside(np.asarray(inner, float), q):
            pts.append(q)
    return pts


# ---------------------------------------------------------------- 형면 선 (도면용): 등고선 · 실루엣

def grid_lines(pr, view, up=(0.0, 0.0, 1.0), step=None):
    """형면 격자 (pr.grid) 의 등고선 (평면 · 입체도) 과 실루엣 (정면 · 우측면도) 을 보는 방향으로 투영한 2D 꺾은선.
    정확 HLR 이 쌍선형 B-스플라인 면의 윤곽을 못 그리는 것을 보탬."""
    g = getattr(pr, "grid", None)
    if not g:
        return []
    from . import dieview
    from .die3d import _inside
    gx, gy, hz = np.asarray(g["gx"]), np.asarray(g["gy"]), np.asarray(g["hz"], float) + g.get("dz", 0.0)
    poly = np.asarray(g["poly"], float)
    GX, GY = np.meshgrid(gx, gy)
    inside = np.array([_inside(poly, (x_, y_)) for x_, y_ in zip(GX.ravel(), GY.ravel())]).reshape(GX.shape)
    H = np.where(inside, hz, np.nan)
    if not np.isfinite(H).any():
        return []
    lo, hi = float(np.nanmin(H)), float(np.nanmax(H))
    v = np.asarray(view, float)
    out = []
    if hi - lo > 0.5:
        try:
            import contourpy
            st = step or max(5.0, (hi - lo) / 8.0)
            levels = np.arange(lo + st, hi - 0.1, st)
            gen = contourpy.contour_generator(GX, GY, np.ma.masked_invalid(H))
            for lv in levels:
                for seg in gen.lines(float(lv)):
                    if len(seg) >= 2:
                        out.append(np.array([dieview.project_point((q[0], q[1], lv), view, up) for q in seg]))
        except Exception:  # noqa: BLE001
            pass
    if abs(v[2]) < 0.5:                                   # 옆에서 봄: 실루엣 (보는 방향으로 가장 높은 곳)
        Hf = np.where(np.isfinite(H), H, -np.inf)
        if abs(v[1]) > abs(v[0]):                         # 정면 (y 방향으로 봄): x 마다 최대
            zmax = Hf.max(axis=0)
            pts = [(float(x_), float(gy[0]), float(z_)) for x_, z_ in zip(gx, zmax) if np.isfinite(z_)]
        else:
            zmax = Hf.max(axis=1)
            pts = [(float(gx[0]), float(y_), float(z_)) for y_, z_ in zip(gy, zmax) if np.isfinite(z_)]
        if len(pts) >= 2:
            out.append(np.array([dieview.project_point(q, view, up) for q in pts]))
    return out


def save_all(assy, stem, info, rates=None, dwg_converter=""):
    """STEP · 도면집 PDF · DXF (· DWG) · 부품표 엑셀 (금형비 시트)."""
    from . import die3d as d3
    from . import diedraw as dd
    from . import drawfmt
    out = [d3.save_step(assy, stem + ".step")]
    sheets = dd.build(assy, dict(info, die=assy.kind, y_cut=0.0))
    out.append(dd.save_pdf(sheets, stem + "_도면집.pdf", title="주물 드로잉 금형 도면집"))
    dxf = dd.save_dxf(sheets, stem + "_도면집.dxf")
    out.append(dxf)
    try:
        out.append(drawfmt.dxf_to_dwg(dxf, stem + "_도면집.dwg", dwg_converter))
    except Exception:  # noqa: BLE001
        pass
    out.append(save_xlsx(assy, stem + "_부품표.xlsx", info.get("product", ""), rates))
    return out


def save_xlsx(assy, path, name="", rates=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from . import die3d as d3
    from . import diecost
    wb = Workbook()
    ws = wb.active
    ws.title = "부품표"
    ws["A1"] = f"주물 드로잉 금형 부품표 — {name} · {assy.kind}"
    ws["A1"].font = Font(bold=True, size=13)
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")
    for j, hd in enumerate(d3.HEAD, 1):
        c = ws.cell(3, j, hd)
        c.font, c.fill = hf, hfill
    for i, row in enumerate(assy.rows(), 4):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, v).alignment = Alignment(wrap_text=True, vertical="top")
    r = 5 + len(assy.parts)
    ws.cell(r, 1, "점검").font = Font(bold=True)
    for c_ in assy.checks:
        r += 1
        for j, v in enumerate(c_, 1):
            ws.cell(r, j, v)
    r += 2
    for n in assy.notes:
        ws.cell(r, 1, "• " + n)
        r += 1
    for col, wd in zip("ABCDEFGH", (6, 30, 6, 22, 30, 9, 10, 56)):
        ws.column_dimensions[col].width = wd
    wc = wb.create_sheet("금형비")
    wc["A1"] = f"금형비 어림 — {name} (예시 단가, [견적 단가] 창에서 고침)"
    wc["A1"].font = Font(bold=True, size=12)
    for j, h in enumerate(("항목", "근거", "원"), 1):
        c = wc.cell(3, j, h)
        c.font, c.fill = hf, hfill
    lines, tot = diecost.estimate(assy, rates)
    rr = 4
    for nm_, why_, v_ in lines:
        wc.cell(rr, 1, nm_)
        wc.cell(rr, 2, why_)
        wc.cell(rr, 3, round(v_))
        rr += 1
    wc.cell(rr, 1, "합계").font = Font(bold=True)
    wc.cell(rr, 3, round(tot)).font = Font(bold=True)
    for col, wd in zip("ABC", (30, 70, 16)):
        wc.column_dimensions[col].width = wd
    ld = getattr(assy, "loads", None)
    if ld is not None:
        wl = wb.create_sheet("하중-행정")
        wl["A1"] = (f"드로잉 하중 - 행정 곡선 (같은 둘레 원통 Siebel) — d {ld.d_eq:.0f} · D₀ {ld.D0:.0f} · β {ld.beta:.2f} · "
                    f"면압 {ld.p_sie:.2f} MPa · 프레스 {ld.press['name'] if ld.press else '-'}")
        wl["A1"].font = Font(bold=True, size=12)
        for j, h in enumerate(("펀치 깊이 mm", "드로잉력 kN", "누르개 kN", "합 kN", "× 안전율 kN", "프레스 능력 kN"), 1):
            c = wl.cell(3, j, h)
            c.font, c.fill = hf, hfill
        from . import costing as cs_
        for i, hh in enumerate(ld.h):
            tot_ = ld.fd[i] + ld.fn[i]
            vals = (round(float(hh), 1), round(float(ld.fd[i]) / 1000, 1), round(float(ld.fn[i]) / 1000, 1),
                    round(float(tot_) / 1000, 1), round(float(tot_) * cs_.SAFETY / 1000, 1),
                    round(float(ld.cap[i]) / 1000, 1) if ld.cap is not None else "")
            for j, v in enumerate(vals, 1):
                wl.cell(4 + i, j, v)
        for col in "ABCDEF":
            wl.column_dimensions[col].width = 16
    wb.save(path)
    return path
