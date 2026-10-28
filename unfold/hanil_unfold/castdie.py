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

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc
from . import diestd as ds
from .die3d import BOX, SHAPE, DieAssy, DiePart, Hole, Prim, _offset, _pin, _up5, _uslot, axi, screw

CAST = 7.2e-6             # 주철 kg/mm³
GRID = 90                 # 형면 격자 수 (긴 변)
K_DRAW = 0.7              # 드로잉력 계수 (둘레 × t × UTS × k)
P_HOLDER = 2.5            # 누르개 면압 MPa (연강)
PIN_KN = 40.0             # 쿠션 핀 하나가 받는 힘 (Ø40)
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


def _prism(poly, z0, h):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    from .die3d import _simplify
    P = _simplify(np.asarray(poly, float), 1.0)          # 곧은 변만 (B-스플라인 변은 형면과의 불리언이 아주 느림)
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


def _bbox(s):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(s, b, False, False)
    p0, p1 = b.CornerMin(), b.CornerMax()
    return (p0.X(), p0.Y(), p0.Z(), p1.X() - p0.X(), p1.Y() - p0.Y(), p1.Z() - p0.Z())


def _pockets(x0, x1, y0, y1, z0, depth, wall=WALL, rib=RIB, pitch=POCKET):
    """리브 사이 빈 곳 (네모) — [(poly, 0, z0, depth)] 꼴의 cuts."""
    out = []
    nx = max(1, int((x1 - x0 - 2 * wall + rib) // (pitch + rib)))
    ny = max(1, int((y1 - y0 - 2 * wall + rib) // (pitch + rib)))
    px = (x1 - x0 - 2 * wall - (nx - 1) * rib) / nx
    py = (y1 - y0 - 2 * wall - (ny - 1) * rib) / ny
    if px < 40 or py < 40 or depth < 25:
        return out
    for i in range(nx):
        for j in range(ny):
            ax = x0 + wall + i * (px + rib)
            ay = y0 + wall + j * (py + rib)
            poly = np.array([[ax, ay], [ax + px, ay], [ax + px, ay + py], [ax, ay + py]])
            out.append((poly, 0.0, z0, depth))
    return out


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
    r_d = float(df.r_die)
    punch_poly = _offset(binder_start, -r_d)
    holder_in = _offset(binder_start, t + 1.0)
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
    surf_p = _fit_surface(gx, gy, Hz)
    surf_d = _fit_surface(gx, gy, Hz + t)
    # 솔리드
    below = _half_space(surf_p, gx[0], gx[-1], gy[0], gy[-1], up=False)
    above = _half_space(surf_d, gx[0], gx[-1], gy[0], gy[-1], up=True)
    punch = _common(below, _prism(punch_poly, z_base_top, 5000.0))
    holder = _common(below, _box(hx0, hy0, hb - Th, hx1 - hx0, hy1 - hy0, 5000.0))
    holder = _cut(holder, _prism(holder_in, hb - Th - 1, Th + 5000.0))
    die = _common(above, _box(dx0, dy0, hb, L, W, z_top_bdc - hb))
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
    p_base = Prim(SHAPE, _bbox(base), shape=base, density=CAST)
    p_base.cuts += _pockets(dx0, dx1, dy0, dy1, z_base0 - 1, Tb - 60 + 1)
    p_punch = Prim(SHAPE, _bbox(punch), shape=punch, density=CAST)
    p_punch.grid = {"gx": gx, "gy": gy, "hz": Hz, "poly": punch_poly, "dz": 0.0}
    px0, py0 = punch_poly.min(0)
    px1, py1 = punch_poly.max(0)
    inner_p = _offset(punch_poly, -70.0)
    if len(inner_p) >= 3 and np.ptp(inner_p[:, 0]) > 80 and np.ptp(inner_p[:, 1]) > 80:
        z_pk = min(hb + depth - 60, hb - 10)                 # 빈 곳 꼭대기: 형면 아래 60, 바인더 높이 아래 10 (벽 빼기 안쪽)
        p_punch.cuts += _pockets(inner_p[:, 0].min(), inner_p[:, 0].max(), inner_p[:, 1].min(), inner_p[:, 1].max(),
                                 z_base_top - 1, z_pk - z_base_top + 1, wall=0.0)
    p_hold = Prim(SHAPE, _bbox(holder_open), shape=holder_open, density=CAST)
    p_die = Prim(SHAPE, _bbox(die_open), shape=die_open, density=CAST)
    p_die.grid = {"gx": gx, "gy": gy, "hz": Hz + t, "poly": np.array([[dx0, dy0], [dx1, dy0], [dx1, dy1], [dx0, dy1]]),
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
             note=f"형면 = 제품 면 + t {t:g} 오프셋 (수직 오프셋 어림), 다이 R{r_d:g} 화염 경화 · 위 리브")
    # 형면 넓이 (NC 시간)
    from .unfolder import _tri_areas3
    A_face = float(_tri_areas3(V, F).sum()) * 1e-6
    A_bind = (float(abs(_area2(outer))) - float(abs(_area2(binder_start)))) * 1e-6
    pp.face_m2 = A_face * 1.1
    pd.face_m2 = A_face * 1.1 + A_bind
    ph.face_m2 = A_bind
    # 가이드 포스트 · 부시 (네 귀)
    cx, cy = 0.5 * (dx0 + dx1), 0.5 * (dy0 + dy1)
    gpx, gpy = (L / 2 - post_d / 2 - 25), (W / 2 - post_d / 2 - 25)
    corners = [(cx + sx * gpx, cy + sy * gpy) for sx in (-1, 1) for sy in (-1, 1)]
    post_L = _up5(z_top_bdc - 30 - z_base0)
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
    F_draw = K_DRAW * per * t * uts
    A_b = float(abs(_area2(outer)) - abs(_area2(holder_in)))
    BHF = P_HOLDER * A_b
    n_pin = max(4, int(math.ceil(BHF / (PIN_KN * 1000))))
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
    inner = _offset(punch_poly, -(2.5 * M))
    for x, y in _ring_points(inner.min(0)[0], inner.max(0)[0], inner.min(0)[1], inner.max(0)[1], None,
                             max(6, int(per // 250)), inset=0.0, poly=inner):
        p_base.holes.append(Hole(x, y, d1, "통과", z_base0, Tb, f"Ø{d1:g} 통과, 자리 Ø{cb:g} 깊이 {cbh:g} (펀치 볼트)",
                                 cb=(cb, z_base0, cbh), side="밑면"))
        p_punch.holes.append(Hole(x, y, tap, "탭", z_base_top, 2 * M, f"M{M} 탭 깊이 {2 * M:g} (밑면, 드릴 Ø{tap:g})", side="밑면"))
        Lb_ = ds.up_std(Tb - cbh + 1.5 * M, ds.SHCS_L + (160, 180, 200, 220, 250))
        bolts.append(screw(x, y, z_base0 + cbh - kh, M, kh, k, Lb_, True))
    add(f"육각 구멍 붙이 볼트 M{M} (펀치)", len(bolts), "SCM435 (12.9)", f"M{M} × {Lb_:.0f}", bolts, std=True,
        order=f"JIS B 1176 M{M} × {Lb_:.0f}")
    keys = [_pin(x, y, z_base_top - 40, 25.0, 80.0) for x, y in ((px0 + 60, cy), (px1 - 60, cy))]
    add("위치 키 (다우얼)", 2, "SUJ2 (m6)", "Ø25 × 80", keys, std=True, order="평행 핀 Ø25 m6 × 80 (펀치 ↔ 베이스)")
    # 에어 벤트 (펀치 형면 낮은 곳)
    low = np.column_stack([X, Y])[np.argsort(-Hh)[:200]]              # 펀치 꼭대기 (제품 바닥) — 공기가 갇히는 곳
    vents = []
    for q in low[::40]:
        if _inside(punch_poly, (q[0], q[1])) and all(math.hypot(q[0] - a, q[1] - b) > 60 for a, b in vents):
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
    mlist = machines if machines is not None else cs.DEFAULT_MACHINES
    F_total = F_draw + BHF
    need_t = F_total * cs.SAFETY / dc.TON
    stroke = 2 * depth + g_load
    mach, ok = cs.pick(mlist, cs.PRESS, need_t, height=depth, depth=depth)
    checks = []

    def chk(item, val, crit, good):
        checks.append([item, val, crit, "적합" if good else "검토"])
    chk("프레스 (쿠션 포함)", f"{mach['name'] if mach else '없음'} (필요 {need_t:,.0f} tf, 행정 ≥ {stroke:.0f})",
        f"(드로잉 {F_draw / 1000:,.0f} + 누르개 {BHF / 1000:,.0f} kN) × {cs.SAFETY:g}, 깊이 {depth:.0f} 위에서", bool(ok))
    chk("쿠션 핀 수", f"{len(pins)} 개", f"≥ {BHF / 1000:,.0f} kN ÷ {PIN_KN:g} = {n_pin}", len(pins) >= n_pin)
    chk("가이드 물림 (열림)", f"{eng_open:.0f} mm", "≥ 30 mm (블랭크 넣을 때도 안내)", eng_open >= 30)
    chk("누르개 면압", f"{P_HOLDER:g} MPa", "1 ~ 3 MPa (연강)", 1.0 <= P_HOLDER <= 3.0)
    chk("에어 벤트", f"{min(len(vents), 6)} 개", "≥ 1 (형면 낮은 곳)", len(vents) >= 1)
    chk("누르개 밑 ↔ 베이스 (하사점)", f"{g_bdc:g} mm", "≥ 10 (밸런스 블록 위)", True)
    kg = sum(p.weight * p.qty for p in parts)
    notes = [f"OP10 드로잉 (주물 금형): 깊이 {depth:.0f} mm · 바인더 {Lb:.0f} × {Wb:.0f} · 다이 R{r_d:g} · 벽 {df.wall_deg:g}°",
             f"드로잉력 F = 펀치 둘레 {per:,.0f} × t {t:g} × UTS {uts:.0f} × {K_DRAW:g} = {F_draw / 1000:,.0f} kN, "
             f"누르개 힘 = 바인더 {A_b * 1e-6:.3f} m² × {P_HOLDER:g} MPa = {BHF / 1000:,.0f} kN → 프레스 {need_t:,.0f} tf"
             + (f" — {mach['name']}" if mach else ""),
             f"높이: 닫힌 {z_top_bdc - z_base0:.0f} · 열린 {z_die_top_open - z_base0:.0f} mm · 행정 ≥ {stroke:.0f} (깊이 × 2 + 틈 {g_load:.0f})",
             f"주물 무게 어림 {kg:,.0f} kg (리브 · 빈 곳 판 솔리드 × 7.2) — 베이스 {parts[0].weight:,.0f} · 펀치 {pp.weight:,.0f} · "
             f"누르개 {ph.weight:,.0f} · 상형 {pd.weight:,.0f}",
             f"형면은 격자 {gx[1] - gx[0]:.0f} mm 의 B-스플라인 근사 (다이 R · 벽은 뭉뚱그려짐) — NC 데이터는 CAD 형면으로, "
             "상형 형면 오프셋은 수직 t (법선 오프셋 아님)",
             "드로우 비드 · 누르개 면압 · 스프링백 보정은 시타 (트라이아웃) 로 — 비드 자리는 성형 해석 draw-in 이 큰 변",
             "표준품 (가이드 · 쿠션 핀 · 마모판) 치수는 일반값 — MISUMI · 후타바 대형 금형 표로 확인"]
    a = DieAssy("OP10 드로우 (주물)", parts, L, W, z_top_bdc - z_base0, F_draw, notes, None, [], checks, (0.0, 0.0),
                z_die_top_open - z_base0, stroke, (0.0, 0.0), None, [],
                {"draw_kn": F_draw / 1000, "bhf_kn": BHF / 1000, "need_tf": need_t, "machine": mach["name"] if mach else "",
                 "ok": bool(ok)})
    a.cast = True
    a.spec = [("공정", "OP10 드로우 (주물 금형)"), ("드로잉력 / 누르개", f"{F_draw / 1000:,.0f} / {BHF / 1000:,.0f} kN"),
              ("필요 프레스", f"{need_t:,.0f} tf → {mach['name'] if mach else '-'}"), ("드로잉 깊이", f"{depth:.0f} mm"),
              ("쿠션 핀", f"Ø{pin_d:g} × {len(pins)}"), ("주물 무게", f"{kg:,.0f} kg")]
    a.y_cut = float(cy)
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
        if abs(v[1]) > abs(v[0]):                         # 정면 (y 방향으로 봄): x 마다 최대
            zmax = np.nanmax(H, axis=0)
            pts = [(float(x_), float(gy[0]), float(z_)) for x_, z_ in zip(gx, zmax) if np.isfinite(z_)]
        else:
            zmax = np.nanmax(H, axis=1)
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
    wb.save(path)
    return path
