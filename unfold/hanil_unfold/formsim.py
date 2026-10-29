"""제품 성형 해석 (원스텝): 전개 결과로 제품 위의 성형성 판정 · 두께 · 절곡부 균열 · 프레스 하중.

성형품 (자유곡면): 원스텝 역해석의 삼각형별 변형률로 성형성 존을 나눈다 (AutoForm 의 Formability 판정과
같은 구분 — 파단 / 파단 위험 / 과도 얇아짐 / 안전 / 늘림 부족 / 주름 경향 / 주름).
판금 (절곡): 절곡마다 바깥 면 변형률 ln((R+t)/(R+t/2)) 을 평면 변형 성형 한계 FLC0 와 견주고
(굽힘은 평면 변형), 최소 R · 스프링백 · 굽힘력을 낸다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc

OK, WARN, NG = dc.OK, dc.WARN, dc.NG

# 성형성 존: (이름, 색 RGB, 판정)
ZONES = [
    ("파단", (220, 30, 30), NG, "파단"),
    ("파단 위험 (한계 80 % 이상)", (245, 160, 0), WARN, "파단 위험"),
    ("과도 얇아짐", (240, 220, 40), WARN, "과도 얇아짐"),
    ("안전", (60, 170, 80), OK, "안전"),
    ("늘림 부족 (변형 3 % 미만)", (150, 150, 150), OK, "늘림 부족"),
    ("압축 (두꺼워짐 2~5 %)", (110, 160, 230), OK, "압축"),
    ("두꺼워짐 · 주름 경향 (5 % 넘음)", (140, 70, 200), WARN, "두꺼워짐·주름"),
]
# 균열 없는 최소 안쪽 R / t (압연 방향과 직각으로 접을 때). 바깥 면 변형률 1/(2R/t+1) 은 접은 각과 상관없이
# R/t 로 정해지므로 180° 굽힘 시험값을 그대로 쓴다 (보수적).
# - SPCC·SECC·SGCC: JIS G 3141 굽힘 시험 180° 밀착 (표준·소둔 질별)
# - SPFC590: JIS G 3135 180° 안쪽 R 1.0 t (SPFC980Y 는 4.0 t)
# - SPFC980: Baosteel DP980 냉연 90° 시험 Rmin/t ≈ 2.0 (용융아연 2.2) — 180° 규격값 4.0 t 보다 실제 90° 절곡에 가까움
# - SPFC440 0.5 t · SPFC780 1.5 t · SPFC1180 3.0 t: AHSS 대표 90° 굽힘 R/t (DP780 1~1.5, 1180 급 2.5~3.5 의 보수 쪽)
# - AL5052-H32: 0~1 t (The Fabricator, 3.2 mm), AL6061-T6: 2~4 t (FAA AC 43.13 0.375", 현장 자료) → 2.5 t
# - 그 밖: 재질 굽힘 시험 대표값 (SPHC·SAPH 0.5 t, SS275 1.0 t (JIS G 3101 180° 1.5 t 의 90° 쪽), SUS304 0.5 t …)
MIN_BEND_RT = {"SPCC": 0.0, "SECC": 0.0, "SGCC": 0.0, "SPHC": 0.5, "SS275": 1.0, "SAPH440": 0.5,
               "SGARC440": 0.5, "SPFC440": 0.5, "SPFC590": 1.0, "SPFC780": 1.5, "SPFC980": 2.0, "SPFC1180": 3.0,
               "SUS304": 0.5, "SUS430": 1.0,
               "AL5052": 1.0, "AL1050": 0.0, "AL6061": 2.5, "C1100": 0.0, "C2600": 0.5}
# 가장자리 늘림 한계 = 구멍 확장률 HER (ISO 16630, 펀칭한 10 mm 구멍을 60° 원뿔로 넓혀 균열까지):
# 연강·일반 고장력강 100 % 넘음, AHSS (DP·TRIP 등) 약 50 % (AHSS Insights · The Fabricator 「edge cracking
# in hole flanging of AHSS」). 그 밖 재질은 공개값을 못 찾아 판정하지 않음 (None).
HER = {"SPCC": 1.0, "SECC": 1.0, "SGCC": 1.0, "SPHC": 1.0, "SS275": 1.0, "SAPH440": 1.0, "SGARC440": 1.0,
       "SPFC440": 1.0, "SPFC590": 0.5, "SPFC780": 0.2, "SPFC980": 0.5}
# SPFC780 0.2: DP780 펀칭 구멍 약 14 %, 밀링·워터젯 약 38 % (MIT, Engineering Fracture Mechanics 2014) — 펀칭 기준의 보수 쪽.
# SPFC1180 은 공개값을 못 찾아 판정하지 않음 (소재 업체 값 권장).
THIN_MAX = 0.25        # 과도 얇아짐 기준 (문헌 관례 25 % 또는 30 %)
STRETCH_MIN = 0.03     # 늘림 부족: 얇아짐·주 변형률 3 % 미만 (스프링백·면 결함 기준 3~5 %)
MARGIN = 0.20          # 파단 위험 = FLC 아래 20 % 안 (LS-DYNA 기본 안전 여유 20 %, 문헌 10~20 %)


@dataclass
class BendCheck:
    no: int
    angle: float
    radius: float          # 계산에 쓴 안쪽 R
    t: float
    strain: float          # 바깥 면 진변형률
    limit: float           # FLC0 (평면 변형)
    r_min: float           # 터지지 않는 가장 작은 안쪽 R
    after: float           # 보정 없이 접으면 돌아간 뒤 각
    die_angle: float       # 금형에서 접어야 할 각
    force_n: float
    verdict: str
    note: str = ""

    @property
    def risk(self):
        return self.strain / self.limit if self.limit > 0 else 0.0


@dataclass
class FormAnalysis:
    mode: str                       # "forming" / "sheet"
    material: str
    thickness: float
    n: float
    r: float
    flc0: float
    zone: np.ndarray | None = None  # 삼각형별 존 번호
    zone_frac: list = field(default_factory=list)   # 존별 넓이 비
    thin_lo: float = 0.0            # 가장 많이 두꺼워짐 (−)
    thin_hi: float = 0.0            # 가장 많이 얇아짐 (+)
    risk_top: float = 0.0
    loads: list = field(default_factory=list)       # (이름, N, 설명)
    press_tonf: float = 0.0
    bends: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    verdict: str = OK
    fi: object = None
    fields: tuple = ()               # 고른 (ε1, ε2, 두께 감소율, 한계 비)
    ldr: tuple = ()                  # (이 제품 드로잉비 β, 한계 드로잉비 LDR)
    edge: tuple = ()                 # (가장자리 늘림 최대, 어디, HER 한계 또는 None)
    box: tuple = ()                  # 사각 드로잉 (귀 R, 깊이, 깊이/R)
    box_ng: bool = False
    corner_floor: float = 0.0        # 사각 드로잉 귀에 깐 경험식 한계 비 (0 = 없음)
    edge_verdict: str = OK
    edge_pt: object = None           # 가장자리 늘림이 가장 큰 점 (제품 3D)
    draw_geom: dict = field(default_factory=dict)   # 드로잉: 둘레·깊이 (하중-행정 곡선용)
    explain: object = None           # formexplain.Explanation (문제 부위별 설명)

    @property
    def t_min(self):
        return self.thickness * (1 - self.thin_hi)

    @property
    def t_max(self):
        return self.thickness * (1 - self.thin_lo)


def smooth(fi, values, passes=2):
    """삼각형 값 → 꼭짓점 (넓이 가중 평균) → 삼각형 (세 꼭짓점 평균). 유한요소 후처리의 절점 평균:
    CAD 메시의 길쭉한 삼각형에서 이웃끼리 번갈아 튀는 값 (체커보드) 을 고른다."""
    V = fi.V if fi.V is not None else np.column_stack([fi.U, np.zeros(len(fi.U))])
    F = fi.F
    a = np.linalg.norm(_vector_area(V, F), axis=1)
    if fi.reliable is not None and fi.reliable.any():
        a = a * np.where(fi.reliable, 1.0, 0.05)
    out = np.asarray(values, float)
    nv = len(V)
    for _ in range(passes):
        num = np.zeros(nv)
        den = np.zeros(nv)
        for k in range(3):
            np.add.at(num, F[:, k], a * out)
            np.add.at(den, F[:, k], a)
        vv = num / np.maximum(den, 1e-30)
        out = vv[F].mean(1)
    return out


def fields(fi):
    """고른 (주 변형률, 부 변형률, 두께 감소율, 한계 비)."""
    from .forming import flc_risk
    e1, e2 = smooth(fi, fi.major), smooth(fi, fi.minor)
    th = 1 - np.exp(-(e1 + e2))              # 체적 일정: t/t0 = exp(ε3), ε3 = −(ε1 + ε2)
    from . import calibration
    k_th, _ = calibration.factor("thinning", getattr(fi, "material", "") or None)
    if k_th != 1.0:                          # 실적 보정: 얇아지는 쪽만 (원스텝은 R 부 얇아짐을 작게 봄)
        th = np.where(th > 0, th * k_th, th)
    rk = flc_risk(e1, e2, fi.flc0, getattr(fi, "material", None)) if fi.flc0 > 0 else np.zeros(len(e1))
    return e1, e2, th, rk


def zones(fi, f=None) -> np.ndarray:
    """삼각형별 성형성 존 번호 (ZONES 의 순서)."""
    e1, e2, th, rk = f if f is not None else fields(fi)
    thick = -(e1 + e2)                       # 두께 진변형률
    z = np.full(len(fi.F), 3)
    z[(e1 < STRETCH_MIN) & (th < STRETCH_MIN)] = 4
    z[(thick > 0.02) & (e2 < 0)] = 5
    z[(thick > 0.05) & (e2 < 0)] = 6
    z[th > THIN_MAX] = 2
    if fi.flc0 > 0:
        z[(rk >= 1 - MARGIN) & (rk < 1)] = 1
        z[rk >= 1] = 0
    return z


def _wq(x, w, q):
    """넓이 가중 분위수 (튀는 조각 삼각형 빼고)."""
    order = np.argsort(x)
    cw = np.cumsum(w[order])
    return float(x[order][min(np.searchsorted(cw, q * cw[-1]), len(x) - 1)]) if len(x) else 0.0


def _vector_area(V, F):
    a = V[F[:, 1]] - V[F[:, 0]]
    b = V[F[:, 2]] - V[F[:, 0]]
    return 0.5 * np.cross(a, b)


def _loop_length(P, loop):
    Q = P[loop]
    return float(np.linalg.norm(np.roll(Q, -1, axis=0) - Q, axis=1).sum())


def press_direction(V, F):
    """투영 넓이가 가장 큰 방향 (프레스 방향)과 그 투영 넓이. 뚜렷하지 않으면 (None, 0)."""
    va = _vector_area(V, F)
    s = va.sum(0)
    area = float(np.linalg.norm(va, axis=1).sum())
    if np.linalg.norm(s) < 0.08 * area:            # 관·닫힌 꼴 (깊은 상자·컵은 0.1~0.3 이라 받아들임)
        return None, 0.0
    return s / np.linalg.norm(s), float(np.linalg.norm(s))


def _forming(fa: FormAnalysis, fi, mat: bc.Material):
    from .forming import boundary_loops
    fa.fields = fields(fi)
    fa.zone = zones(fi, fa.fields)
    w = fi._weights()
    fa.zone_frac = [float(w[fa.zone == i].sum()) for i in range(len(ZONES))]
    th, rk = fa.fields[2], fa.fields[3]
    fa.thin_lo, fa.thin_hi = _wq(th, w, 0.005), _wq(th, w, 0.995)
    fa.risk_top = _wq(rk, w, 0.995)
    t = fa.thickness
    # 하중: 드로잉력 F = L·t·σb·n(m) (m = 제품 둘레 / 블랭크 둘레, 원통 컵 드로잉 식을 둘레로 넓힘)
    #       주름 누르개 힘 = 면압 × (블랭크 넓이 − 펀치 투영 넓이)
    if fi.V is not None:
        loops = boundary_loops(fi.F)
        if loops:
            outer = max(loops, key=lambda lp: _loop_length(fi.U, lp))
            L_prod = _loop_length(fi.V, outer)
            L_blank = _loop_length(fi.U, outer)
            m = min(1.0, L_prod / max(L_blank, 1e-9))
            z, proj = press_direction(fi.V, fi.F)
            depth = float(np.ptp(fi.V @ z)) if z is not None else 0.0
            if m < 0.97 and depth > 3 * t:
                f_tab = L_prod * t * mat.tensile_mpa * dc.force_k(max(m, 0.55))
                # Siebel: 둘레 L = π·d 로 보고 π·d·s·1.1·k_fm·ln β ÷ η_F
                phi = math.log(1 / m)
                f_sie = L_prod * t * 1.1 * dc.mean_flow_stress(mat, phi) * phi / 0.65
                f_draw = max(f_tab, f_sie)
                fa.loads.append(("드로잉 (펀치) 힘", f_draw, f"둘레 {L_prod:,.0f} mm · 드로잉률 m {m:.2f} · "
                                                        f"교재 식 {f_tab / 1000:,.0f} kN / Siebel {f_sie / 1000:,.0f} kN 중 큰 값"))
                lim = dc.ldr(mat)
                beta = 1 / m
                fa.ldr = (beta, lim)
                fa.draw_geom = dict(L_prod=L_prod, L_blank=L_blank, depth=depth, m=m, f_draw=f_draw)
                _box_corners(fa, fi, z, depth, t)
                if beta > lim:
                    fa.messages.append(f"드로잉비 β = {beta:.2f} 가 한계 드로잉비 LDR {lim:.2f} (Whiteley·Hosford, r {mat.r:g}) "
                                       "를 넘음 — 다단 드로잉 (재드로잉) 으로 나누세요.")
                else:
                    fa.messages.append(f"드로잉비 β = {beta:.2f} ≤ LDR {lim:.2f} (Whiteley·Hosford, r {mat.r:g}) — 한 번에 드로잉 가능 범위")
            else:                                    # 얕은 성형 (스트레치): 둘레 벽 장력 L·t·σf
                sig = dc.flow_stress(mat, max(float(np.average(np.maximum(fi.major, 0), weights=w)), 0.002))
                f_draw = L_prod * t * sig
                fa.loads.append(("성형 (펀치) 힘", f_draw, f"둘레 {L_prod:,.0f} mm × t × 유동 응력 {sig:.0f} MPa "
                                                       "(스트레치 성형)"))
            if z is not None:
                p_tab = dc.HOLDER_P[dc._family(mat.code)]
                if fa.ldr:                           # 드로잉: Siebel 면압 (β = 1/m, d = 둘레 / π)
                    p_bh = dc.siebel_holder_pressure(fa.ldr[0], L_prod / math.pi, t, mat)
                    how = f"Siebel 면압 {p_bh:.2f} MPa (β {fa.ldr[0]:.2f}; 표 값 {p_tab:g} MPa 는 쿠션 능력 상한)"
                else:                                # 스트레치: 누르개로 잡아 둠 → 표 값
                    p_bh, how = p_tab, f"면압 {p_tab:g} MPa (스트레치 성형, 교재 표)"
                bh = max(fi.blank_area - proj, 0.0)
                if bh > 0.02 * fi.blank_area:
                    fa.loads.append(("주름 누르개 힘", p_bh * bh, f"{how} × {bh:,.0f} mm² (블랭크 − 펀치 투영)"))
                fa.messages.append(f"성형 깊이 {depth:.1f} mm · 펀치 투영 넓이 {proj:,.0f} mm² · "
                                   f"블랭크 {fi.blank_area:,.0f} mm²")
    _edge_stretch(fa, fi, mat)
    from . import drawcorr
    note = drawcorr.summary(getattr(fi, "correction", None), fa.thickness)
    if note:
        fa.messages.append(note)
    fr = dict(zip(range(len(ZONES)), fa.zone_frac))
    if fr[0] > 0.001:
        fa.messages.append(f"파단 {fr[0]:.1%}: 성형 한계를 넘습니다 — R 을 키우거나, 깊이를 나누거나 (다단 드로잉), "
                           "n 값 큰 재질 (SPCE·DC04 급) 로 바꾸세요.")
    if fr[1] > 0.001:
        fa.messages.append(f"파단 위험 {fr[1]:.1%}: 한계의 80 % 이상 — 소재 편차·윤활에 따라 터질 수 있습니다.")
    if fr[2] > 0.001:
        fa.messages.append(f"과도 얇아짐 {fr[2]:.1%}: 두께 {THIN_MAX:.0%} 넘게 얇아집니다 (최소 {fa.t_min:.2f} mm).")
    if fr[6] > 0.02:
        fa.messages.append(f"두꺼워짐 {fr[6]:.1%} (최대 {-fa.thin_lo:.0%}): 압축으로 두꺼워지는 곳 — 다이 벽에 눌리는 "
                           f"드로잉 벽이면 정상 (다이 틈새를 두께 + 10 % 이상 = {fa.thickness * (1.1 - fa.thin_lo):.2f} mm "
                           "근처로), 받쳐 주는 면이 없는 곳이면 주름 — 주름 누르개 힘·드로잉 비드를 늘리세요.")
    if fr[4] > 0.5:
        fa.messages.append(f"늘림 부족 {fr[4]:.0%}: 변형이 3 % 안 되는 넓은 곳 — 외판이면 강성 부족·오일 캔·"
                           "스프링백이 생길 수 있습니다 (비드로 더 늘리기).")
    worst = [ZONES[i][2] for i in range(len(ZONES)) if fr[i] > (0.001 if i < 3 else 0.02)]
    fa.verdict = NG if NG in worst else WARN if WARN in worst else OK
    if ((fa.ldr and fa.ldr[0] > fa.ldr[1]) or fa.box_ng) and fa.verdict == OK:   # 한 번에 못 당김 → 다단 (주의)
        fa.verdict = WARN
    order = [OK, WARN, NG]
    if order.index(fa.edge_verdict) > order.index(fa.verdict):
        fa.verdict = fa.edge_verdict


BOX_HR = 6.0     # 사각 드로잉 한 번에 깊이 ≤ 6 × 귀 R (MetalForming 2017, 보수적 — 2014 판은 7~12 배)


def box_corner(fi, z=None, depth=None):
    """(귀 R, 깊이, 깊이/귀 R) 또는 None — 프레스 방향과 나란한 세로 원통 면이 2 개 이상일 때 (사각 드로잉)."""
    if fi is None or fi.V is None or not getattr(fi, "cylinders", None):
        return None
    if z is None:
        z, _ = press_direction(fi.V, fi.F)
        if z is None:
            return None
        depth = float(np.ptp(fi.V @ z))
    rc = [r for r, ax in fi.cylinders if abs(float(np.dot(ax, z))) > 0.95 and r < depth]
    if len(rc) < 2:
        return None
    r = min(rc)
    return r, depth, depth / max(r, 1e-9)


def _box_corners(fa, fi, z, depth, t):
    """사각 드로잉 (상자·오일 팬): 프레스 방향과 나란한 세로 원통 면 (귀 R) 이 2 개 이상이면, 귀가 원통 컵처럼
    가장 어렵다 — 한 번에 깊이 ≤ 6 × 귀 R (MetalForming), 귀 R ≥ 5 t. 넘으면 다단 드로잉."""
    b = box_corner(fi, z, depth)
    if b is None:
        return
    r, depth, hr = b
    fa.box = b
    if hr > BOX_HR:
        n = max(2, math.ceil(hr / BOX_HR))
        fa.messages.append(f"사각 드로잉 깊이 {depth:.0f} mm = 귀 R {r:g} 의 {hr:.1f} 배 > {BOX_HR:g} 배 — 한 번에 못 당김: "
                           f"약 {n} 번 드로잉 (재드로잉) 이나 귀 R 을 {depth / BOX_HR:.0f} mm 이상으로 (MetalForming 경험식)")
        fa.box_ng = True
    else:
        fa.messages.append(f"사각 드로잉 깊이 / 귀 R = {hr:.1f} ≤ {BOX_HR:g} — 한 번 드로잉 범위 (MetalForming 경험식)")
    _corner_risk(fa, fi, z, r, hr)
    if r < 5 * t:
        fa.messages.append(f"귀 R {r:g} < 5 t ({5 * t:g} mm) — 귀가 터지기 쉬움, R 을 키우세요")


CORNER_RISK = True     # 사각 드로잉 귀의 한계 비에 경험식 (깊이/귀 R ÷ BOX_HR) 을 바닥 삼각형으로 깐다


def _corner_risk(fa, fi, z, r, hr):
    """원스텝 (전변형) 은 깊은 사각 드로잉의 귀 터짐을 작게 본다 (귀로 몰리는 플랜지 압축·장력의 역사를 못 봄 —
    H/R 10 의 오일 팬도 한계 비 0.8 안팎). 그래서 귀 벽 아래 절반 (터지는 곳: 펀치 R 위 벽) 의 한계 비를
    경험식 이용률 (깊이 / 귀 R) / BOX_HR 아래로 내려가지 않게 한다 — 판정 (한 번에 못 당김) 과 3D 그림이 같은 말을 하게."""
    if not CORNER_RISK or fa.fields is None or fi.V is None:
        return
    from .drawcorr import _curvature_along
    V, F = fi.V, fi.F
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    from .forming import boundary_loops
    hv = V @ z
    loops = boundary_loops(F)
    if loops:                                           # 트림선 (바깥 경계) 이 있는 쪽이 다이 면 — 바닥은 반대쪽
        outer = max(loops, key=len)
        if hv[outer].mean() < hv.mean():
            hv = -hv
    h = hv[F].mean(1)
    lo, hi = float(hv.min()), float(hv.max())
    hoop = np.cross(z, n)                               # 벽 위의 수평 방향
    ln = np.linalg.norm(hoop, axis=1)
    wall = (ln > 0.85)                                  # 거의 선 벽
    hoop[wall] /= ln[wall, None]
    kap = np.zeros(len(F))
    kap[wall] = _curvature_along(V, F[wall], forming_normals(V, F), hoop[wall]) if wall.any() else 0
    corner = wall & (kap > 1 / (1.6 * r)) & (kap < 1 / (0.6 * r)) & (h < lo + 0.5 * (hi - lo))
    if not corner.any():
        return
    u = hr / BOX_HR
    e1, e2, th, rk = fa.fields
    rk = np.where(corner, np.maximum(rk, u), rk)
    fa.fields = (e1, e2, th, rk)
    fa.zone = zones(fi, fa.fields)
    w = fi._weights()
    fa.zone_frac = [float(w[fa.zone == i].sum()) for i in range(len(ZONES))]
    fa.risk_top = max(fa.risk_top, _wq(rk, w, 0.995))
    fa.corner_floor = u
    fa.messages.append(f"사각 드로잉 귀 벽 아래 (펀치 R 위) 한계 비를 경험식 이용률 {u:.2f} (깊이/귀 R {hr:.1f} ÷ {BOX_HR:g}) "
                       "아래로 내리지 않음 — 원스텝은 깊은 귀의 터짐을 작게 봄")


def forming_normals(V, F):
    from .forming import vertex_normals
    return vertex_normals(V, F)


def _edge_stretch(fa, fi, mat):
    """잘린 가장자리 (메시 경계: 외곽 트림선·구멍) 의 둘레 방향 늘림 = 제품 길이 / 블랭크 길이 − 1.
    둘레 10 mm (또는 10 t) 창의 평균 최대를 구멍 확장률 HER 과 견준다 — 구멍 버링·스트레치 플랜지 균열."""
    from .forming import boundary_loops
    if fi.V is None:
        return
    worst, where = 0.0, ""
    for k, loop in enumerate(boundary_loops(fi.F)):
        if len(loop) < 6:
            continue
        P3, P2 = fi.V[loop], fi.U[loop]
        l3 = np.linalg.norm(np.roll(P3, -1, axis=0) - P3, axis=1)
        l2 = np.linalg.norm(np.roll(P2, -1, axis=0) - P2, axis=1)
        # 둘레 길이로 잰 창 (max(10 mm, 10 t)) 안의 길이 비 — 절곡 R 을 가로지르는 짧은 경계 모서리의 메시 흔들림을 없앤다
        win = max(10.0, 10 * fa.thickness)
        c3 = np.concatenate([[0.0], np.cumsum(np.concatenate([l3, l3, l3]))])
        c2 = np.concatenate([[0.0], np.cumsum(np.concatenate([l2, l2, l2]))])
        n = len(l3)
        start = c3[n:2 * n]
        lo = np.clip(np.searchsorted(c3, start - win / 2), 0, len(c3) - 1)
        hi = np.clip(np.searchsorted(c3, start + win / 2), 0, len(c3) - 1)
        e = (c3[hi] - c3[lo]) / np.maximum(c2[hi] - c2[lo], 1e-12) - 1
        if e.max() > worst:
            worst = float(e.max())
            fa.edge_pt = P3[int(e.argmax())].copy()
            where = "바깥 트림선" if l2.sum() == max(np.linalg.norm(np.roll(fi.U[lp], -1, axis=0) - fi.U[lp], axis=1).sum()
                                                 for lp in boundary_loops(fi.F)) else "구멍 가장자리"
    fa.edge = (worst, where, HER.get(mat.code))
    lim = HER.get(mat.code)
    if worst <= 0.02:
        return
    if lim is None:
        fa.messages.append(f"가장자리 늘림 최대 {worst:.0%} ({where}) — {mat.code} 의 구멍 확장률 (HER) 값이 없어 판정하지 않음")
    elif worst >= lim:
        fa.messages.append(f"가장자리 늘림 {worst:.0%} ({where}) ≥ 구멍 확장률 HER {lim:.0%} — 가장자리 균열 (버링·스트레치 "
                           "플랜지): 펀칭 대신 레이저·리밍, 버를 안쪽으로, 플랜지 높이 줄이기")
        fa.edge_verdict = NG
    elif worst >= 0.8 * lim:
        fa.messages.append(f"가장자리 늘림 {worst:.0%} ({where}) — HER {lim:.0%} 의 80 % 이상 (가장자리 균열 주의)")
        fa.edge_verdict = WARN
    elif worst > 0.05:
        fa.messages.append(f"가장자리 늘림 {worst:.0%} ({where}) < 구멍 확장률 HER {lim:.0%} — 여유 있음")


def _sheet(fa: FormAnalysis, result, settings: bc.BendSettings, mat: bc.Material):
    """절곡 균열: 바깥 면 공칭 변형률 e = 1/(2R/t + 1) 을 그 재질의 최소 R/t 에서의 e 와 견준다.
    (굽힘은 두께 방향 변형률 기울기가 있어 성형 한계 FLC0 보다 훨씬 더 늘어나도 터지지 않는다 —
    Datsko·Yang R/t = 50/RA − 1, Kalpakjian.) 최소 R/t 는 MIN_BEND_RT (90°, 압연 방향과 직각)."""
    t = fa.thickness
    rt = MIN_BEND_RT.get(mat.code, 1.0)
    r_min = rt * t
    e_lim = 1 / (2 * rt + 1)
    v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)
    for b in result.bends:
        R = max(b.inner_radius, 0.0)              # 실제 접히는 안쪽 R (자연 R·상형 R 반영)
        e = 1 / (2 * R / t + 1)
        strain = math.log(1 + e)
        after, die, _ = dc.springback(mat, max(R, 0.1 * t), t, b.angle_deg)
        f = dc.bend_force(mat, b.length, t, v, settings.process)
        # 덜 접힌 절곡은 같은 R 이라도 바깥 면 변형이 같다 (R 이 정해지면) — 각도는 스프링백·힘에만
        risk = e / e_lim
        verdict = NG if risk > 1.0 + 1e-9 else WARN if risk >= 0.8 else OK
        note = ""
        if b.model_radius <= 0:
            note = f"도면 R 0 — 계산 R {R:.2f}"
        if verdict == NG:
            note = (note + " · " if note else "") + f"안쪽 R {r_min:.2f} 이상으로 (압연 방향과 나란히 접으면 더 크게)"
        elif verdict == WARN:
            note = (note + " · " if note else "") + "한계 근처 — 압연 방향과 나란한 절곡은 균열 주의"
        fa.bends.append(BendCheck(b.number, b.angle_deg, R, t, strain, math.log(1 + e_lim), r_min, after,
                                  die if math.isfinite(die) else float("nan"), f, verdict, note))
    if fa.bends:
        fa.risk_top = max(c.risk for c in fa.bends)
        bad = [c for c in fa.bends if c.verdict == NG]
        warn = [c for c in fa.bends if c.verdict == WARN]
        if bad:
            fa.messages.append(f"절곡 {', '.join(f'B{c.no}' for c in bad)}: 안쪽 R 이 {mat.code} 최소 R "
                               f"{r_min:.2f} mm ({rt:g} t) 보다 작습니다 — 바깥 면 균열 위험.")
        if warn:
            fa.messages.append(f"절곡 {', '.join(f'B{c.no}' for c in warn)}: 최소 R 근처 (균열 주의).")
        fa.loads.append(("굽힘 힘 (가장 큰 절곡)", max(c.force_n for c in fa.bends),
                         f"F = 1.33·σb·L·t²/V (V {v:g})"))
        fa.verdict = NG if bad else WARN if warn else OK
        fa.messages.append(f"{mat.code} 90° 절곡 최소 안쪽 R {r_min:.2f} mm = {rt:g} t (압연 방향과 직각, 대표값) · "
                           f"바깥 면 늘어남 e = 1/(2R/t + 1)")
    else:
        fa.messages.append("절곡이 없는 평판 부품입니다 (성형 판정할 곳 없음).")


def analyze(result, settings: bc.BendSettings) -> FormAnalysis:
    """전개 결과 하나의 성형 해석."""
    mat = settings.mat
    t = result.thickness
    fi = result.forming
    fa = FormAnalysis(mode="forming" if fi is not None else "sheet", material=mat.code, thickness=t,
                      n=mat.n, r=mat.r, flc0=fi.flc0 if fi is not None and fi.flc0 > 0 else mat.flc0_for(t), fi=fi)
    from . import forming as _fm
    if mat.code in _fm.MEASURED_FLC:                 # 실측 FLC: ε2 = 0 값을 FLC0 로 보임
        fa.flc0 = _fm.flc0_of(mat.code, fa.flc0)
    if fi is not None:
        _forming(fa, fi, mat)
    else:
        _sheet(fa, result, settings, mat)
    if fi is not None and fi.flc0 > 0:
        fa.messages.append(f"성형 한계 (FLC): " + (f"{mat.code} 실측 FLC ({len(_fm.MEASURED_FLC[mat.code])} 점, ISO 12004-2)"
                                                 if mat.code in _fm.MEASURED_FLC else
                                                 f"Keeler 식 (t {round(t, 2):g}, n {mat.n:g}) — 소재 업체 실측 FLC 를 넣으면 더 정확"))
    fa.messages.append(f"재질값: {mat.source} — TS {mat.tensile_mpa:g} MPa · YS {dc.yield_strength(mat):g} MPa · "
                       f"n {mat.n:g} · r̄ {mat.r:.2f}" + (f" · Δr {mat.dr:+.2f}" if mat.dr else "")
                       + ("" if mat.source != "대표값" else " (밀시트 값을 넣으면 더 정확: 절곡 조건 → [밀시트 실측값])"))
    peak = max((f for _, f, _ in fa.loads), default=0.0)
    total = sum(f for name, f, _ in fa.loads if not name.startswith("굽힘")) if fi is not None else peak
    from . import calibration
    k_ton, note_t = calibration.factor("tonnage", ("드로잉" if fa.ldr else "성형") if fi is not None else "전단·굽힘")
    fa.press_tonf = total * 1.3 * k_ton / dc.TON
    k_th, note_th = calibration.factor("thinning", mat.code) if fi is not None else (1.0, "")
    k_sb, note_sb = calibration.factor("springback", mat.code) if fi is None and fa.bends else (1.0, "")
    for note, what in ((note_t, "권장 프레스"), (note_th, "얇아짐"), (note_sb, "스프링백")):
        if note:
            fa.messages.append(f"{what}: {note} — 현장 실측으로 맞춘 계수 ([기록] → [실적 보정])")
    from . import formexplain
    try:
        fa.explain = formexplain.explain(fa)
    except Exception:                         # 설명은 덤 — 해석 결과는 그대로 쓴다
        import traceback
        traceback.print_exc()
    return fa


def summary_html(fa: FormAnalysis) -> str:
    """정보 칸 한 줄."""
    col = {OK: "#60c060", WARN: "#e0a040", NG: "#e05050"}[fa.verdict]
    if fa.mode == "forming":
        fr = fa.zone_frac
        body = (f"파단 {fr[0]:.1%} · 위험 {fr[1]:.1%} · 얇아짐 최대 {max(fa.thin_hi, 0):.0%} · 두꺼워짐 {fr[6]:.1%}")
    elif fa.bends:
        body = (f"절곡 균열 위험도 {fa.risk_top:.0%} (100 % = 최소 R) · 최소 R {fa.bends[0].r_min:.2f} · "
                f"스프링백 보정 최대 {max(c.die_angle - c.angle for c in fa.bends if math.isfinite(c.die_angle)) if any(math.isfinite(c.die_angle) for c in fa.bends) else 0:.1f}°")
    else:
        body = "평판"
    fld = " · <a href='fld'>성형 한계도</a>" if fa.mode == "forming" and fa.flc0 > 0 else ""
    return (f"<b>성형 해석</b> <span style='color:{col}'>{fa.verdict}</span> · {body} · "
            f"<a href='sim'>성형 해석 보기</a>{fld}")


def zone_rows(fa: FormAnalysis):
    return [[z_[0], frac, z_[2] if frac > 0.001 else "—"] for z_, frac in zip(ZONES, fa.zone_frac)]


def bend_rows(fa: FormAnalysis):
    return [[f"B{c.no}", c.angle, c.radius, c.radius / c.t, c.strain, c.risk, c.r_min, c.after,
             c.die_angle, c.force_n / 1000, c.verdict, c.note] for c in fa.bends]


BEND_HEAD = ["절곡", "각도 °", "안쪽 R", "R/t", "바깥 면 진변형률", "최소 R 대비", "최소 R", "보정 없이 (°)",
             "금형 보정 각 (°)", "굽힘력 kN", "판정", "비고"]


def load_rows(fa: FormAnalysis):
    rows = [[name, f / 1000, f / dc.TON, note] for name, f, note in fa.loads]
    rows.append(["권장 프레스 (× 1.3)", fa.press_tonf * dc.TON / 1000, fa.press_tonf, "여유 30 %"])
    return rows


# ---------------------------------------------------------------- 3D 그림

VIEWS = ["성형성 존", "두께 변화 %", "두께 mm", "주 변형률", "성형 한계 비"]


FILLED_RGB = (225, 225, 228)


def tri_colors(fa: FormAnalysis, view: str):
    """삼각형별 색 (m, 3) 과 범례 [(글, RGB)]. 막은 피어싱 구멍 자리는 옅은 회색."""
    cols, leg = _tri_colors(fa, view)
    region = getattr(fa.fi, "region", None) if fa.fi is not None else None
    if region is not None and (region > 0).any():          # 다이 페이스: 어덴덤·바인더는 옅게 (제품이 보이게)
        cols = np.array(cols, float)
        cols[region > 0] = 0.45 * cols[region > 0] + 0.55 * 255
        leg = list(leg) + [("어덴덤·바인더 (옅게)", (225, 232, 240))]
    filled = getattr(fa.fi, "filled", None) if fa.fi is not None else None
    if filled is not None and filled.any():
        cols = np.array(cols, float)
        cols[filled] = FILLED_RGB
        leg = list(leg) + [("피어싱 구멍 (막고 해석)", FILLED_RGB)]
    return cols, leg


def _tri_colors(fa: FormAnalysis, view: str):
    from .drawing import THIN_LIMIT, thinning_color
    from .formrobust import ROBUST_VIEWS
    if view in ROBUST_VIEWS and getattr(fa, "robust", None) is not None:
        from .formrobust import colors
        return colors(fa.robust, view)
    fi = fa.fi
    if view == VIEWS[0]:
        pal = np.array([z_[1] for z_ in ZONES], float)
        return pal[fa.zone], [(z_[3], z_[1]) for z_ in ZONES]
    e1, _, th, rk = fa.fields
    if view in VIEWS[1:3]:
        cols = np.array([thinning_color(float(x)).getRgb()[:3] for x in np.clip(th, -1, 1)], float)
        if view == VIEWS[1]:
            leg = [((f"{-x:+.0%}" + (" 두꺼워짐" if x < 0 else " 얇아짐")) if abs(x) > 1e-9 else "0 %",
                    thinning_color(x).getRgb()[:3])
                   for x in np.linspace(-THIN_LIMIT, THIN_LIMIT, 5)]
        else:
            leg = [(f"{fa.thickness * (1 - x):.2f}", thinning_color(x).getRgb()[:3])
                   for x in np.linspace(-THIN_LIMIT, THIN_LIMIT, 5)]
        return cols, leg
    if view == VIEWS[3]:
        v = np.clip(e1 / max(fa.flc0, 0.05), 0, 1.2) / 1.2
    else:
        v = np.clip(rk, 0, 1.2) / 1.2
    stops = np.array([(40, 90, 220), (60, 170, 90), (240, 220, 40), (220, 30, 30)], float)
    pos = v * 3
    i = np.minimum(pos.astype(int), 2)
    f = (pos - i)[:, None]
    cols = stops[i] * (1 - f) + stops[i + 1] * f
    top = 1.2 * (max(fa.flc0, 0.05) if view == VIEWS[3] else 1.0)
    leg = [(f"{top * k / 3:.2f}" if view == VIEWS[3] else f"{top * k / 3:.0%}", tuple(stops[k])) for k in range(4)]
    return cols, leg


def paint_product(p, rect, fa: FormAnalysis, view=VIEWS[0], az=-35.0, el=30.0, title=True, marks=True, fast=False,
                  sphere=False, zoom=1.0, pan=(0.0, 0.0)):
    """제품 3D 메시를 색 지도로 (화가 알고리즘 + 평면 음영). fast: 줄인 메시로 (자동 회전 중),
    sphere: 감싸는 공으로 크기를 정함 (돌려도 크기가 그대로). zoom · pan: 확대 배율과 화면 이동 (픽셀) — 제목 · 범례는
    그대로 두고 그림 자리 안에서만 (넘치는 것은 잘림)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    from .report import _font
    fi = fa.fi
    if fi is None or fi.V is None:
        return
    mesh = None
    if fast:
        if getattr(fa, "_fast_mesh", None) is None:
            inv, Fc, keep = cluster_mesh(fi.V, fi.F)
            fa._fast_mesh = (cluster_points(inv, fi.V), Fc, keep)
        mesh = fa._fast_mesh
    V = (mesh[0] if mesh else fi.V) - fi.V.mean(0)
    z0, _ = press_direction(fi.V, fi.F)
    if z0 is not None:                    # 바깥 법선 합의 반대 = 열린 쪽을 위로 (컵은 바닥이 아래)
        zz = -z0
        xx = np.cross([0, 1.0, 0] if abs(zz[1]) < 0.9 else [1.0, 0, 0], zz)
        xx /= np.linalg.norm(xx)
        yy = np.cross(zz, xx)
        V = V @ np.column_stack([xx, yy, zz])
    a, e = math.radians(az), -math.radians(el)       # el > 0 = 위에서 내려다봄
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]])
    # 보는 좌표: x 오른쪽, y 위, z 앞 (화면 쪽)
    W = V @ Rz.T
    W = np.column_stack([W[:, 0], W[:, 2], -W[:, 1]]) @ Rx.T
    W[:, 2] *= -1
    _, leg0 = tri_colors(fa, view)
    per_row = max(1, int((rect.width() - 20) // 125))
    rows_ = math.ceil(len(leg0) / per_row)
    legend_h = (8 + 22 * rows_) if title else 0
    area = QRectF(rect.left() + 10, rect.top() + (30 if title else 6), rect.width() - 20,
                  rect.height() - (30 if title else 6) - legend_h - 10)
    if sphere:
        rad = float(np.linalg.norm(fi.V - fi.V.mean(0), axis=1).max())
        lo, hi = np.array([-rad, -rad]), np.array([rad, rad])
    else:
        lo, hi = W[:, :2].min(0), W[:, :2].max(0)
    s = min(area.width() / max(hi[0] - lo[0], 1e-9), area.height() / max(hi[1] - lo[1], 1e-9)) * 0.94 * zoom
    cx, cy = area.center().x() + pan[0], area.center().y() + pan[1]
    mid = (lo + hi) / 2
    X = cx + (W[:, 0] - mid[0]) * s
    Y = cy - (W[:, 1] - mid[1]) * s
    cols, leg = tri_colors(fa, view)
    F = fi.F
    if mesh:
        F, cols = mesh[1], cols[mesh[2]]
    nrm = np.cross(W[F[:, 1]] - W[F[:, 0]], W[F[:, 2]] - W[F[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    light = np.array([0.3, 0.5, 0.81])
    shade = 0.45 + 0.55 * np.abs(nrm @ light)
    order = np.argsort(W[F].mean(1)[:, 2])          # 먼 것부터
    p.save()
    if zoom != 1.0 or pan != (0.0, 0.0):
        p.setClipRect(area)
    p.setPen(Qt.NoPen)
    for i in order:
        c = cols[i] * shade[i]
        q = QColor(int(min(c[0], 255)), int(min(c[1], 255)), int(min(c[2], 255)))
        p.setBrush(q)
        p.setPen(QPen(q, 0.6))
        tri = F[i]
        p.drawPolygon(QPolygonF([QPointF(X[tri[0]], Y[tri[0]]), QPointF(X[tri[1]], Y[tri[1]]),
                                 QPointF(X[tri[2]], Y[tri[2]])]))
    if marks and fa.explain is not None and not mesh:  # 문제 부위 번호 (설명 표와 같은 번호)
        from . import formexplain
        r_ = max(9.0, min(16.0, rect.width() / 70))
        p.setFont(_font(max(7.0, r_ * 0.75), True))
        placed = []
        for txt, P, rgb in formexplain.marks(fa.explain):
            Pm = (P - fi.V.mean(0))
            if z0 is not None:
                Pm = Pm @ np.column_stack([xx, yy, zz])
            w_ = Pm @ Rz.T
            w_ = np.array([w_[0], w_[2], -w_[1]]) @ Rx.T
            px, py = cx + (w_[0] - mid[0]) * s, cy - (w_[1] - mid[1]) * s
            while any(math.hypot(px - qx, py - qy) < 2.1 * r_ for qx, qy in placed):   # 겹치면 옆으로
                px += 2.2 * r_
            placed.append((px, py))
            p.setPen(QPen(QColor(20, 20, 20), 1.6))
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawEllipse(QPointF(px, py), r_, r_)
            p.setPen(QColor(*[int(v * 0.8) for v in rgb]))
            p.drawText(QRectF(px - r_, py - r_, 2 * r_, 2 * r_), Qt.AlignCenter, txt)
    if title:
        p.setClipping(False)
        p.setPen(QColor(30, 30, 30))
        p.setFont(_font(12, True))
        p.drawText(QRectF(rect.left(), rect.top() + 4, rect.width(), 24), Qt.AlignCenter,
                   f"제품 성형 해석 — {view}  ({fa.material}, t {round(fa.thickness, 2):g}, 판정 {fa.verdict})")
        p.setFont(_font(9))
        n = min(len(leg), per_row)
        bw = min(170.0, (rect.width() - 20) / max(n, 1))
        x0 = rect.left() + (rect.width() - bw * n) / 2
        for k, (txt, rgb) in enumerate(leg):
            col_, row_ = k % per_row, k // per_row
            xb, yb = x0 + col_ * bw, rect.bottom() - legend_h + 22 * row_
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*[int(v) for v in rgb]))
            p.drawRect(QRectF(xb + 2, yb + 4, 14, 14))
            p.setPen(QColor(40, 40, 40))
            p.drawText(QRectF(xb + 20, yb, bw - 22, 22), Qt.AlignLeft | Qt.AlignVCenter, txt)
    p.restore()


def render_product(fa: FormAnalysis, view=VIEWS[0], w=1000, h=760, az=-35.0, el=30.0, dpr=1.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import new_image
    img, p = new_image(w, h, dpr)
    paint_product(p, QRectF(0, 0, w, h), fa, view, az, el)
    p.end()
    return img


# ---------------------------------------------------------------- 저장

def add_sheets(wb, fa: FormAnalysis, name="", first=False):
    """통합 문서에 [성형 해석] (+ 성형품이면 [제품 그림] [성형 한계도]) 시트. 지울 임시 그림 파일 목록을 돌려준다."""
    from openpyxl.styles import Font, PatternFill

    from . import company
    from .report import _add_image, render_fld

    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")

    def table(ws, r0, head, rows, pct=()):
        for j, h in enumerate(head, 1):
            c = ws.cell(r0, j, h)
            c.font, c.fill = hf, hfill
            ws.column_dimensions[c.column_letter].width = max(ws.column_dimensions[c.column_letter].width or 0,
                                                              12, len(h) * 2 + 2)
        for i, row in enumerate(rows, r0 + 1):
            for j, v in enumerate(row, 1):
                c = ws.cell(i, j, v)
                if isinstance(v, float):
                    c.number_format = "0.0%" if j - 1 in pct else "#,##0.000"
        return r0 + len(rows) + 2

    if first:
        ws = wb.active
        ws.title = "성형 해석"
    else:
        ws = wb.create_sheet("성형 해석")
    ws["A1"] = f"제품 성형 해석 — {name}  ({fa.material}, t {round(fa.thickness, 2):g}, n {fa.n:g}, r {fa.r:g})"
    ws["A1"].font = Font(bold=True, size=13)
    ws.cell(1, 8, company.MAKER)
    ws["A2"] = f"판정: {fa.verdict} · FLC0 {fa.flc0:.3f} · 권장 프레스 {fa.press_tonf:.1f} tf"
    r = 4
    if fa.mode == "forming":
        r = table(ws, r, ["성형성 존", "넓이 비", "판정"], zone_rows(fa), pct=(1,))
        for k, v in (("최소 두께 mm", fa.t_min), ("최대 두께 mm", fa.t_max), ("가장 많이 얇아짐", fa.thin_hi),
                     ("가장 많이 두꺼워짐", -fa.thin_lo), ("가장 큰 한계 비", fa.risk_top)):
            ws.cell(r, 1, k)
            ws.cell(r, 2, float(v)).number_format = "0.000" if "mm" in k else "0.0%"
            r += 1
        r += 1
    elif fa.bends:
        r = table(ws, r, BEND_HEAD, bend_rows(fa), pct=(5,))
    r = table(ws, r, ["하중", "kN", "tf", "설명"], load_rows(fa))
    ws.cell(r, 1, "알림")
    for i, msg in enumerate(fa.messages, 1):
        ws.cell(r + i, 1, msg)
    r += len(fa.messages) + 2
    for i, line in enumerate(NOTES, 0):
        ws.cell(r + i, 1, line)
    _explain_sheet(wb, fa, name)
    tmps = []
    if fa.mode == "forming":
        pic = wb.create_sheet("제품 그림")
        for k, view in enumerate(VIEWS[:2] + VIEWS[4:] + VIEWS[3:4]):
            tmps.append(_add_image(pic, render_product(fa, view, 900, 680), f"{'AK'[k % 2]}{1 + 36 * (k // 2)}", 640))
        if not any(ws_.title == "두께 변화" for ws_ in wb.worksheets):
            tmps.append(_add_image(wb.create_sheet("성형 한계도"), render_fld(fa.fi, 900, 700), "A1", 700))
        try:
            from . import formprocess as fp
            pr = fp.build(fa)
        except Exception:
            pr = None
        if pr is not None:
            ws_p = wb.create_sheet("성형 과정")
            for i, line in enumerate(fp.summary(pr), 1):
                ws_p.cell(i, 1, line).font = Font(bold="시작" in line, color="C00000" if "터지기" in line else "000000")
            for k, sv in enumerate((0.25, 0.5, 0.75, 1.0)):
                tmps.append(_add_image(ws_p, fp.render_stage(pr, sv, 800, 600), f"{'AK'[k % 2]}{5 + 32 * (k // 2)}", 560))
        secs = default_sections(fa)
        if secs:
            ws_s = wb.create_sheet("단면 두께")
            r = 1
            for sec in secs:
                ws_s.cell(r, 1, section_note(sec)).font = Font(bold=True)
                tmps.append(_add_image(ws_s, render_section(sec, 1000, 620), f"K{r}", 620))
                r += 1
                for j, h_ in enumerate(SECTION_HEAD, 1):
                    c = ws_s.cell(r, j, h_)
                    c.font, c.fill = hf, hfill
                for row in sec.rows()[::max(1, len(sec.s) // 120)]:
                    r += 1
                    for j, v in enumerate(row, 1):
                        ws_s.cell(r, j, round(v, 4))
                r = max(r + 3, r + 2)
                r = max(r, (r // 34 + 1) * 34)
        ls = load_stroke(fa)
        if ls is not None:
            ws_l = wb.create_sheet("하중-행정")
            ws_l["A1"] = ls.note
            ws_l["A1"].font = Font(bold=True)
            for j, h_ in enumerate(["깊이 mm", "드로잉력 tf", "누르개 tf", "합 tf", f"{ls.press} 능력 tf"], 1):
                c = ws_l.cell(3, j, h_)
                c.font, c.fill = hf, hfill
            for i, hh in enumerate(ls.h):
                for j, v in enumerate([hh, ls.draw[i] / dc.TON, ls.holder[i] / dc.TON, ls.total[i] / dc.TON,
                                       ls.cap[i] / dc.TON], 1):
                    ws_l.cell(4 + i, j, round(float(v), 3))
            tmps.append(_add_image(ws_l, render_load_stroke(ls, 1000, 600), "H3", 640))
    return tmps


def _explain_sheet(wb, fa: FormAnalysis, name=""):
    """[해석 설명] 시트: 판정 이유 · 문제 부위 표 (위치·값·뜻·원인·대책) · 위치별 두께 · 두께 분포 · 그림 읽는 법."""
    from openpyxl.styles import Alignment, Font, PatternFill

    from . import formexplain as fx
    ex = fa.explain
    if ex is None:
        return
    ws = wb.create_sheet("해석 설명")
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")
    wrap = Alignment(wrap_text=True, vertical="top")
    for col, wd in zip("ABCDEFGHI", (7, 14, 34, 9, 34, 8, 50, 55, 60)):
        ws.column_dimensions[col].width = wd
    ws["A1"] = f"성형 해석 설명 — {name}  ({fa.material}, t {round(fa.thickness, 2):g})"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = ex.headline
    ws["A2"].font = Font(bold=True, color={OK: "2A8C3C", WARN: "C87F00", NG: "D22828"}[ex.verdict])
    r = 4
    ws.cell(r, 1, "판정 이유").font = Font(bold=True)
    for t_ in ex.reasons:
        r += 1
        ws.cell(r, 1, "• " + t_)
    if ex.advice:
        r += 2
        ws.cell(r, 1, "먼저 해 볼 대책").font = Font(bold=True)
        for k, a in enumerate(ex.advice, 1):
            r += 1
            ws.cell(r, 1, f"{k}. {a}")
    if ex.issues:
        r += 2
        head = fx.ISSUE_HEAD + ["뜻", "원인", "대책"]
        for j, h in enumerate(head, 1):
            c = ws.cell(r, j, h)
            c.font, c.fill = hf, hfill
        for i in ex.issues:
            r += 1
            row = [i.no, i.zone_name, i.region, i.frac if i.frac else "—", i.value, i.verdict, i.meaning, i.cause,
                   "\n".join(f"- {a}" for a in i.actions)]
            for j, v in enumerate(row, 1):
                c = ws.cell(r, j, v)
                c.alignment = wrap
                if j == 4 and isinstance(v, float):
                    c.number_format = "0.0%"
            rgb = ZONES[i.zone][1]
            ws.cell(r, 2).fill = PatternFill("solid", fgColor="%02X%02X%02X" % rgb)
            ws.cell(r, 2).font = Font(bold=True, color="FFFFFF" if i.zone in (0, 6) else "000000")
            ws.row_dimensions[r].height = max(60, 15 * (len(i.actions) + 1), 15 * (len(i.cause) // 45 + 1))
    if ex.regions:
        r += 2
        for j, h in enumerate(fx.REGION_HEAD, 1):
            c = ws.cell(r, j, h)
            c.font, c.fill = hf, hfill
        for row in ex.regions:
            r += 1
            for j, v in enumerate(row, 1):
                c = ws.cell(r, j, v)
                if isinstance(v, float):
                    c.number_format = "0.0%" if j in (2, 3, 6) else "0.000"
    if ex.thickness:
        r += 2
        for j, h in enumerate(["두께 변화 구간", "넓이 비"], 1):
            c = ws.cell(r, j, h)
            c.font, c.fill = hf, hfill
        for nm, f in ex.thickness:
            r += 1
            ws.cell(r, 1, nm)
            ws.cell(r, 2, f).number_format = "0.0%"
    if ex.process:
        r += 2
        for j, h in enumerate(["공정 · 하중", "값", "설명"], 1):
            c = ws.cell(r, j, h)
            c.font, c.fill = hf, hfill
        for row in ex.process:
            r += 1
            for j, v in enumerate(row, 1):
                ws.cell(r, j, v).alignment = wrap
    if fa.mode == "forming":
        r += 2
        ws.cell(r, 1, "그림 읽는 법").font = Font(bold=True)
        for v in fx.VIEW_HELP.values():
            r += 1
            ws.cell(r, 1, v)


def save_xlsx(fa: FormAnalysis, path, name=""):
    import os

    from openpyxl import Workbook
    wb = Workbook()
    tmps = add_sheets(wb, fa, name, first=True)
    if getattr(fa, "ops", None) is not None:          # [공정별 해석] 을 돌렸으면 그 시트도
        from . import formops
        formops.add_sheet(wb, fa.ops, name)
        tl = getattr(fa.ops, "trim", None)
        if tl is not None:
            ws = wb.create_sheet("트림선 전개")
            ws.append([f"트림선 전개 · 스프링백 보정 — {name}"])
            for line in tl.summary():
                ws.append(["• " + line])
            ws.append([])
            ws.append(["고리", "번호", "X (평면)", "Y (평면)", "Z", "펼친 플랜지 mm", "트림 각 °", "꺾는 각 °", "보정 각 °"])
            for li, (P2, P3, L, S, B, C) in enumerate(zip(tl.loops2d, tl.loops3d, tl.flange_len, tl.slope,
                                                          tl.bend or [None] * len(tl.loops2d),
                                                          tl.comp or [None] * len(tl.loops2d)), 1):
                step = max(1, len(P2) // 400)
                for i in range(0, len(P2), step):
                    b_ = None if B is None or not np.isfinite(B[i]) else round(float(B[i]), 1)
                    c_ = None if C is None or not np.isfinite(C[i]) else round(float(C[i]), 2)
                    ws.append([li, i + 1, round(float(P2[i, 0]), 2), round(float(P2[i, 1]), 2),
                               round(float(P3[i] @ tl.z), 2), round(float(L[i]), 2), round(float(S[i]), 1), b_, c_])
    rob = getattr(fa, "robust", None)
    if rob is not None:
        ws = wb.create_sheet("강건성")
        ws.append([f"강건성 해석 (Sigma) — {name} · 판정 {rob.verdict}"])
        for line in rob.summary():
            ws.append(["• " + line])
        ws.append([])
        ws.append(rob.head())
        for r in rob.rows():
            ws.append(r)
    from .company import stamp_workbook
    stamp_workbook(wb)
    wb.save(path)
    for t_ in tmps:
        try:
            os.remove(t_)
        except OSError:
            pass


NOTES = ["원스텝 (한 번에 성형) 해석입니다: 다단 공정 이력·드로잉 비드·실제 금형 형상은 들어가지 않습니다.",
         "성형성 존: 파단 = 성형 한계(FLC) 넘음, 파단 위험 = 80 % 이상, 과도 얇아짐 > 25 %, 늘림 부족 = 변형 3 % 미만, "
         "주름 경향 = 압축으로 두꺼워짐 2~5 %, 주름 = 5 % 넘음 (AutoForm Formability 판정과 같은 구분).",
         "FLC: 강판 Keeler-Brazier 식, 그 밖은 재질 대표값. 금형 확정 전에는 성형 해석 프로그램·시험으로 확인하세요.",
         "원스텝 (막) 이 못 보는 인장 아래 굽힘·드로잉 장력·아이어닝은 드로잉 보정으로 더한다 (1.42.0) — 원통 컵 펀치 R 쪽 "
         "얇아짐 14 % (연강 컵 시험 15~18 %). [공정별 해석] 은 바인더·어덴덤을 붙인 다이 페이스 위에서 다시 푼다.",
         "절곡: 바깥 면 공칭 변형률 1/(2R/t+1) 을 재질의 최소 굽힘 R/t (90°, 압연 방향과 직각) 에서의 값과 비교 "
         "(Datsko·Yang, Kalpakjian). 스프링백은 가공 경화 유동 응력의 탄성-소성 식."]


def _explain_pages(p, pdf, R, k, W, H, m, header, fa, name):
    """설명 쪽: 왼쪽 번호 붙은 성형성 존 그림, 오른쪽·다음 쪽에 글 (줄 바꿈)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor

    from . import formexplain as fx
    from .report import _font
    lines = fx.text_lines(fa)
    if not lines:
        return
    pdf.newPage()
    y = header(f"해석 설명 (어디서 · 얼마나 · 왜 · 대책) — {name}")
    x0 = m
    if fa.mode == "forming":
        p.drawImage(R(m, y, 150, 114), render_product(fa, VIEWS[0], 1200, 912))
        x0 = m + 156
    top = y
    col_w = W - m - x0
    flags = Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap
    for kind, txt in lines:
        size, bold, gap = {"h": (11, True, 3.0), "i": (9.5, True, 2.0)}.get(kind, (8.5, False, 0.6))
        p.setFont(_font(size, bold))
        br = p.boundingRect(QRectF(0, 0, col_w * k, 2000 * k), flags, txt)
        h = br.height() / k
        if y + gap + h > H - m:
            pdf.newPage()
            y = header(f"해석 설명 (이어서) — {name}")
            x0, col_w = m, W - 2 * m
            top = y
            br = p.boundingRect(QRectF(0, 0, col_w * k, 2000 * k), flags, txt)
            h = br.height() / k
        y += gap if y > top else 0
        if kind == "i":
            p.fillRect(R(x0, y - 0.5, col_w, h + 1), QColor(236, 240, 247))
        p.setPen(QColor(31, 78, 140) if kind == "h" else QColor(25, 25, 25))
        p.drawText(R(x0 + (1 if kind == "i" else 0), y, col_w - 1, h + 1), flags, txt)
        y += h
        if x0 > m and y > top + 118:              # 그림 아래부터는 넓게
            x0, col_w = m, W - 2 * m


def save_pdf(fa: FormAnalysis, path, name=""):
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

    from . import process as pr
    from .report import _brand, _font, ensure_gui, render_fld, version_text
    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A3), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(f"성형 해석 - {name}")
    pdf.setCreator(f"한일 판금 전개 {version_text()}")
    k = 300 / 25.4
    W, H, m = 420.0, 297.0, 12.0

    def R(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)

    def header(title):
        p.setPen(QColor(20, 20, 20))
        p.setFont(_font(16, True))
        p.drawText(R(m, m, W - 2 * m, 9), Qt.AlignLeft | Qt.AlignVCenter, title)
        p.setFont(_font(8))
        _brand(p, R(m, m + 1.5, W - 2 * m, 6))
        p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
        p.drawLine(QPointF(m * k, (m + 10) * k), QPointF((W - m) * k, (m + 10) * k))
        return m + 15

    def fmt(rows, pct=()):
        return [[v if isinstance(v, str) else f"{v:.1%}" if j in pct else f"{v:,.2f}" for j, v in enumerate(r)]
                for r in rows]

    y = header(f"제품 성형 해석 — {name}  ({fa.material}, t {round(fa.thickness, 2):g}) · 판정 {fa.verdict}")
    if fa.mode == "forming":
        p.drawImage(R(m, y, 250, 190), render_product(fa, VIEWS[0], 1500, 1140))
        x2 = m + 256
        yy = pr._table(p, R, k, x2, y, [("성형성 존", 70), ("넓이 비", 30), ("판정", 26)],
                       fmt(zone_rows(fa), (1,)))
        yy = pr._table(p, R, k, x2, yy + 4, [("항목", 70), ("값", 56)],
                       [["최소 두께", f"{fa.t_min:.3f} mm"], ["최대 두께", f"{fa.t_max:.3f} mm"],
                        ["가장 많이 얇아짐", f"{fa.thin_hi:.1%}"], ["가장 많이 두꺼워짐", f"{-fa.thin_lo:.1%}"],
                        ["가장 큰 한계 비", f"{fa.risk_top:.0%}"], ["FLC0", f"{fa.flc0:.3f}"]])
        yy = pr._table(p, R, k, x2, yy + 4, [("하중", 42), ("kN", 20), ("tf", 16), ("설명", 62)],
                       fmt(load_rows(fa)), 8)
        y = max(y + 194, yy + 2)
    else:
        y = pr._table(p, R, k, m, y, [(h_, 30 if i in (0, 10) else 26) for i, h_ in enumerate(BEND_HEAD[:11])] +
                      [("비고", 100)], fmt(bend_rows(fa), (5,)), 8, maxy=H - 60)
        y = pr._table(p, R, k, m, y + 4, [("하중", 60), ("kN", 26), ("tf", 22), ("설명", 120)],
                      fmt(load_rows(fa)))
    p.setFont(_font(9))
    p.setPen(QColor(30, 30, 30))
    for line in fa.messages + [""] + NOTES:
        if y > H - m - 5:
            break
        p.drawText(R(m, y, W - 2 * m, 5), Qt.AlignLeft | Qt.AlignVCenter, line)
        y += 5
    if fa.mode == "forming":
        pdf.newPage()
        y = header(f"두께 · 성형 한계 — {name}")
        p.drawImage(R(m, y, 196, 148), render_product(fa, VIEWS[1], 1200, 900))
        p.drawImage(R(m + 200, y, 196, 148), render_product(fa, VIEWS[4], 1200, 900))
        p.drawImage(R(m + 60, y + 150, 140, 109), render_fld(fa.fi, 900, 700))
    if fa.mode == "forming":
        try:
            from . import formprocess as fp
            pr = fp.build(fa)
        except Exception:
            pr = None
        if pr is not None:
            pdf.newPage()
            y = header(f"성형 과정 (행정마다) — {name}")
            for k, sv in enumerate((0.25, 0.5, 0.75, 1.0)):
                p.drawImage(R(m + k * 99, y, 97, 73), fp.render_stage(pr, sv, 970, 730))
            yy = y + 78
            p.setFont(_font(10))
            for line in fp.summary(pr):
                p.setPen(QColor(200, 20, 20) if "터지기" in line else QColor(130, 60, 190) if "주름 시작" in line
                         else QColor(30, 30, 30))
                p.drawText(R(m, yy, W - 2 * m, 7), Qt.AlignLeft | Qt.AlignVCenter, ("⚠ " if "시작" in line else "✔ ") + line)
                yy += 7
            p.setPen(QColor(110, 110, 110))
            p.setFont(_font(8.5))
            p.drawText(R(m, yy + 2, W - 2 * m, 12), Qt.AlignLeft | Qt.TextWordWrap,
                       "원스텝 해석의 처음 (블랭크) 과 끝 (제품) 사이를 비례 변형 (행정 s 에서 변형 = s × 끝 변형) 과 펀치 깊이로 "
                       "이어 그린 그림 — 실제 금형 접촉 순서·다단 공정은 아님.")
        secs = default_sections(fa)
        ls = load_stroke(fa)
        if secs or ls is not None:
            pdf.newPage()
            y = header(f"단면 두께 · 하중 - 행정 — {name}")
            x = m
            for sec in secs[:2]:
                p.drawImage(R(x, y, 196, 124), render_section(sec, 1300, 820))
                x += 200
            if ls is not None:
                p.drawImage(R(m + 60, y + 130, 200, 120), render_load_stroke(ls, 1300, 780))
                p.setFont(_font(9))
                p.setPen(QColor(30, 30, 30))
                p.drawText(R(m, y + 252, W - 2 * m, 10), Qt.AlignLeft | Qt.TextWordWrap, ls.note)
    ops = getattr(fa, "ops", None)
    if ops is not None and ops.ops:                       # 공정별 해석 · 트림선 전개 · 스프링백 보정
        from . import formops as fo
        from . import process as proc
        pdf.newPage()
        y = header(f"공정별 해석 (OP10 ~ OP40) — {name}")
        rows = [[r[0], r[1], r[2], f"{r[3]:,.0f}", f"{r[4]:,.1f}", r[5][:150]] for r in ops.rows()]
        y = proc._table(p, R, k, m, y, [(fo.HEAD[0], 16), (fo.HEAD[1], 40), (fo.HEAD[2], 16), (fo.HEAD[3], 22),
                                      (fo.HEAD[4], 26), (fo.HEAD[5], 276)], rows, 7.5)
        if ops.fa_die is not None:
            p.drawImage(R(m, y + 4, 196, 148), render_product(ops.fa_die, VIEWS[0], 1200, 900))
        tl = getattr(ops, "trim", None)
        if tl is not None:
            from . import formtrim
            p.drawImage(R(m + 200, y + 4, 196, 130), formtrim.render(tl, 1200, 800))
            p.setFont(_font(9))
            p.setPen(QColor(30, 30, 30))
            yy = y + 138
            for line in tl.summary():
                p.drawText(R(m + 200, yy, 196, 5), Qt.AlignLeft | Qt.AlignVCenter, "• " + line)
                yy += 5
    rob = getattr(fa, "robust", None)
    if rob is not None:
        from . import formrobust as fr
        pdf.newPage()
        y = header(f"강건성 해석 (Sigma) — {name} · 판정 {rob.verdict}")
        p.drawImage(R(m, y, 196, 148), render_product(fa, fr.ROBUST_VIEWS[0], 1200, 900))
        p.drawImage(R(m + 200, y, 196, 148), render_product(fa, fr.ROBUST_VIEWS[2], 1200, 900))
        p.setFont(_font(10))
        p.setPen(QColor(30, 30, 30))
        yy = y + 152
        for line in rob.summary():
            p.drawText(R(m, yy, W - 2 * m, 6), Qt.AlignLeft | Qt.AlignVCenter, "• " + line)
            yy += 6
        heads = rob.head()
        cols = [(h_, 14 if i == 0 else 30) for i, h_ in enumerate(heads)]
        from . import process as proc
        proc._table(p, R, k, m, yy + 2, cols, [[str(v) for v in r] for r in rob.rows()[:14]], 7.5)
    _explain_pages(p, pdf, R, k, W, H, m, header, fa, name)
    p.end()


# ---------------------------------------------------------------- 단면 (자른 면을 따라 두께 · 변형률)

@dataclass
class Section:
    axis: str                  # "X" / "Y" / "Z" — 이 축에 수직인 평면
    pos: float                 # 평면 위치 (모델 좌표 mm)
    pts: np.ndarray            # (n, 3) 단면 선 위 점 (두께 가운데 면)
    s: np.ndarray              # 선 따라 거리 mm
    thin: np.ndarray           # 얇아짐 (+) / 두꺼워짐 (−) 비
    e1: np.ndarray
    e2: np.ndarray
    risk: np.ndarray
    t0: float

    @property
    def thickness(self):
        return self.t0 * (1 - self.thin)

    def rows(self):
        return [[float(a), float(p[0]), float(p[1]), float(p[2]), float(self.t0 * (1 - b)), float(b), float(c), float(d),
                 float(e)] for a, p, b, c, d, e in zip(self.s, self.pts, self.thin, self.e1, self.e2, self.risk)]


SECTION_HEAD = ["선 따라 mm", "X", "Y", "Z", "두께 mm", "두께 변화 (+ 얇아짐)", "주 변형률", "부 변형률", "한계 비"]
AXES = {"X": 0, "Y": 1, "Z": 2}


def _vertex_values(fi, vals):
    V, F = fi.V, fi.F
    a = np.linalg.norm(_vector_area(V, F), axis=1)
    num, den = np.zeros(len(V)), np.zeros(len(V))
    for k in range(3):
        np.add.at(num, F[:, k], a * vals)
        np.add.at(den, F[:, k], a)
    return num / np.maximum(den, 1e-30)


def section(fa: FormAnalysis, axis="X", pos=None):
    """제품 메시를 axis 에 수직인 평면 (axis = pos, 없으면 가운데) 으로 잘라 가장 긴 단면 선을 따라 값.
    잘리는 삼각형 모서리마다 꼭짓점 값을 선형 보간 (시험품을 잘라 재는 것과 같은 자리). 단면이 없으면 None."""
    fi = fa.fi
    if fi is None or fi.V is None or not fa.fields:
        return None
    ax = AXES[axis]
    V, F = fi.V, fi.F
    if pos is None:
        pos = float((V[:, ax].min() + V[:, ax].max()) / 2)
    e1, e2, th, rk = fa.fields
    vals = np.column_stack([_vertex_values(fi, v) for v in (th, e1, e2, rk)])
    d = V[:, ax] - pos
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)                # 꼭짓점이 평면 위면 살짝 비켜
    sd = d[F]
    cut = (sd.min(1) < 0) & (sd.max(1) > 0)
    edge_pt, segs = {}, []
    for ti in np.nonzero(cut)[0]:
        ends = []
        for k in range(3):
            i, j = int(F[ti, k]), int(F[ti, (k + 1) % 3])
            if (d[i] < 0) != (d[j] < 0):
                key = (min(i, j), max(i, j))
                if key not in edge_pt:
                    w = d[i] / (d[i] - d[j])
                    edge_pt[key] = (V[i] + w * (V[j] - V[i]), vals[i] + w * (vals[j] - vals[i]))
                ends.append(key)
        if len(ends) == 2:
            segs.append(tuple(ends))
    if not segs:
        return None
    adj = {}
    for si, (a, b) in enumerate(segs):
        adj.setdefault(a, []).append(si)
        adj.setdefault(b, []).append(si)
    used = [False] * len(segs)
    lines = []
    for s0 in range(len(segs)):
        if used[s0]:
            continue
        used[s0] = True
        chain = [segs[s0][0], segs[s0][1]]
        for direction in (1, 0):                         # 양쪽으로 늘리기
            while True:
                end = chain[-1] if direction else chain[0]
                nxt = [si for si in adj.get(end, []) if not used[si]]
                if not nxt:
                    break
                si = nxt[0]
                used[si] = True
                a, b = segs[si]
                new = b if a == end else a
                if direction:
                    chain.append(new)
                else:
                    chain.insert(0, new)
        lines.append(chain)
    best = None
    for ch in lines:
        P = np.array([edge_pt[k][0] for k in ch])
        L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
        if best is None or L > best[0]:
            best = (L, ch, P)
    _, ch, P = best
    Q = np.array([edge_pt[k][1] for k in ch])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    h0 = [k for k in range(3) if k != ax][0]               # 단면 그림의 가로축 — 왼쪽 끝에서 시작 (그래프와 같은 방향)
    if P[0, h0] > P[-1, h0] + 1e-6:
        P, Q = P[::-1], Q[::-1]
        s = s[-1] - s[::-1]
    return Section(axis, pos, P, s, Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3], fa.thickness)


def section_note(sec: Section):
    i = int(np.argmax(sec.thin))
    j = int(np.argmin(sec.thin))
    return (f"{sec.axis} = {sec.pos:.1f} 단면 · 길이 {sec.s[-1]:.0f} mm · 가장 얇은 곳 {sec.thickness[i]:.3f} mm "
            f"(얇아짐 {max(sec.thin[i], 0):.1%}, {sec.s[i]:.0f} mm 지점) · 가장 두꺼운 곳 {sec.thickness[j]:.3f} mm "
            f"(두꺼워짐 {max(-sec.thin[j], 0):.1%})")


def paint_section(p, rect, sec: Section, title=True):
    """위: 단면 모양 (얇아짐 색), 아래: 선 따라 두께 변화 % 그래프 (기준선: 0, −25 % 얇아짐, +5 % 두꺼워짐)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    from .drawing import thinning_color
    from .report import _font
    p.save()
    p.fillRect(rect, QColor(255, 255, 255))
    y0 = rect.top() + (26 if title else 4)
    if title:
        p.setPen(QColor(30, 30, 30))
        p.setFont(_font(11, True))
        p.drawText(QRectF(rect.left(), rect.top() + 2, rect.width(), 22), Qt.AlignCenter, section_note(sec))
    # 단면 모양
    h_shape = (rect.height() - (y0 - rect.top())) * 0.38
    others = [k for k in range(3) if k != AXES[sec.axis]]
    A = sec.pts[:, others]
    if sec.axis != "Z":
        A = np.column_stack([A[:, 0], A[:, 1]])
    lo, hi = A.min(0), A.max(0)
    sc = min((rect.width() - 40) / max(hi[0] - lo[0], 1e-9), (h_shape - 16) / max(hi[1] - lo[1], 1e-9))
    cx = rect.left() + rect.width() / 2 - (lo[0] + hi[0]) / 2 * sc
    cy = y0 + h_shape / 2 + (lo[1] + hi[1]) / 2 * sc
    for k in range(len(A) - 1):
        c = thinning_color(float((sec.thin[k] + sec.thin[k + 1]) / 2))
        p.setPen(QPen(c, 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx + A[k, 0] * sc, cy - A[k, 1] * sc), QPointF(cx + A[k + 1, 0] * sc, cy - A[k + 1, 1] * sc))
    i = int(np.argmax(sec.thin))
    p.setPen(QPen(QColor(200, 0, 0), 2))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(cx + A[i, 0] * sc, cy - A[i, 1] * sc), 7, 7)
    # 그래프
    g = QRectF(rect.left() + 70, y0 + h_shape + 10, rect.width() - 100, rect.height() - (y0 - rect.top()) - h_shape - 50)
    ys = -sec.thin * 100                                   # + 두꺼워짐, − 얇아짐 (현장 단면 측정 꼴)
    ymin = min(-30.0, float(ys.min()) - 3)
    ymax = max(10.0, float(ys.max()) + 3)
    L = float(sec.s[-1]) or 1.0

    def q(sv, yv):
        return QPointF(g.left() + sv / L * g.width(), g.bottom() - (yv - ymin) / (ymax - ymin) * g.height())
    p.setFont(_font(8.5))
    for yv in range(int(math.ceil(ymin / 10) * 10), int(ymax) + 1, 10):
        p.setPen(QPen(QColor(220, 220, 220), 1))
        p.drawLine(q(0, yv), q(L, yv))
        p.setPen(QColor(90, 90, 90))
        p.drawText(QRectF(g.left() - 66, q(0, yv).y() - 9, 60, 18), Qt.AlignRight | Qt.AlignVCenter, f"{yv:+d} %")
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        p.drawText(QRectF(q(L * frac, ymin).x() - 30, g.bottom() + 2, 60, 16), Qt.AlignCenter, f"{L * frac:.0f}")
    p.drawText(QRectF(g.left(), g.bottom() + 16, g.width(), 16), Qt.AlignCenter, "단면 선 따라 거리 mm  (세로: 두께 변화, − 얇아짐)")
    for yv, col, lab in ((0, QColor(60, 60, 60), "처음 두께"), (-THIN_MAX * 100, QColor(220, 30, 30), f"얇아짐 한계 −{THIN_MAX:.0%}"),
                         (5, QColor(140, 70, 200), "두꺼워짐 +5 % (주름 경향)")):
        p.setPen(QPen(col, 1.2, Qt.DashLine))
        p.drawLine(q(0, yv), q(L, yv))
        p.drawText(QRectF(g.right() - 200, q(0, yv).y() - 16, 200, 14), Qt.AlignRight, lab)
    p.setPen(QPen(QColor(31, 78, 140), 2))
    p.drawPolyline(QPolygonF([q(float(a), float(b)) for a, b in zip(sec.s, ys)]))
    p.setPen(QPen(QColor(200, 0, 0), 2))
    p.drawEllipse(q(float(sec.s[i]), float(ys[i])), 5, 5)
    p.restore()


def render_section(sec: Section, w=1100, h=700, dpr=1.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import new_image
    img, p = new_image(w, h, dpr)
    paint_section(p, QRectF(0, 0, w, h), sec)
    p.end()
    return img


def default_sections(fa: FormAnalysis):
    """보고서용: 가운데를 지나는 X · Y 단면 (있는 것만)."""
    out = []
    for ax in ("X", "Y"):
        try:
            s = section(fa, ax)
        except Exception:
            s = None
        if s is not None and len(s.s) > 3:
            out.append(s)
    return out


# ---------------------------------------------------------------- 하중 - 행정 (드로잉)

@dataclass
class LoadStroke:
    h: np.ndarray              # 펀치가 들어간 깊이 mm (0 = 닿음)
    draw: np.ndarray           # 드로잉력 N
    holder: np.ndarray         # 누르개 (쿠션) 힘 N
    cap: np.ndarray            # 고른 프레스가 그 높이에서 낼 수 있는 힘 N
    press: str
    ok: bool
    depth: float
    note: str = ""

    @property
    def total(self):
        return self.draw + self.holder

    @property
    def margin(self):
        """프레스 능력 / 하중 의 가장 작은 값과 그 깊이."""
        r = self.cap / np.maximum(self.total, 1.0)
        i = int(np.argmin(r))
        return float(r[i]), float(self.h[i])


def load_stroke(fa: FormAnalysis, mat=None, machines=None, n=80, mu=0.1):
    """드로잉 하중 - 행정 곡선과 크랭크 프레스 능력 곡선 (같은 둘레의 원통 컵으로 본 어림).
    같은 둘레 원통: d = 제품 둘레 / π, D0 = 블랭크 둘레 / π. 펀치 깊이 h 에서 플랜지 바깥 지름 D(h) = √(D0² − 4 d h)
    (넓이 일정: 벽으로 들어간 π d h = 플랜지에서 줄어든 π (D0² − D²)/4).
    드로잉력 F(h) = π d t · 1.1 k_fm ln(D(h)/d) / η_F + 2 μ F_N(h)  (Siebel, 홀더 마찰 양면),
    누르개 F_N(h) = Siebel 면압 × 남은 플랜지 넓이. 곡선의 가장 큰 드로잉력은 해석의 드로잉력에 맞춘다.
    프레스: costing 기계 표에서 모든 깊이에서 능력 ≥ 하중 (크랭크 곡선 F = P sin30°/sin α) 이고 행정 ≥ 2 × 깊이인
    가장 작은 것."""
    g = fa.draw_geom
    if not g or not fa.ldr:
        return None
    from . import bendcalc as bc
    from . import costing as cs
    mat = mat or bc.MATERIAL_BY_CODE.get(fa.material, bc.MATERIALS[0])
    t = fa.thickness
    d = g["L_prod"] / math.pi
    D0 = g["L_blank"] / math.pi
    depth = g["depth"]
    h_full = (D0 ** 2 - d ** 2) / (4 * d)                  # 플랜지가 다 들어가는 깊이 (같은 둘레 원통)
    h = np.linspace(0, depth, n)
    D = np.sqrt(np.maximum(D0 ** 2 - 4 * d * np.minimum(h, h_full), d ** 2))
    phi = math.log(max(D0 / d, 1.0))
    kfm = dc.mean_flow_stress(mat, phi)
    rd = dc.die_radius(D0, d, t)
    p_bh = dc.siebel_holder_pressure(D0 / d, d, t, mat)
    FN = p_bh * np.pi / 4 * np.maximum(D ** 2 - (d + 2 * rd) ** 2, 0.0)
    ideal = np.pi * d * t * 1.1 * kfm * np.log(D / d) / 0.65
    rise = np.minimum(h / max(rd + 3 * t, 1e-6), 1.0)      # 펀치 R·다이 R 을 감는 동안 오르는 몫
    Fd = (ideal + 2 * mu * FN) * rise
    if Fd.max() > 0 and g.get("f_draw"):
        Fd = Fd * (g["f_draw"] / Fd.max())
    machines = machines or cs.default_costing()["machines"]
    presses = sorted([m for m in machines if m["kind"] == cs.PRESS], key=lambda m: m["capacity"])
    total = Fd + FN
    chosen, cap = None, None
    for m in presses:
        c = np.array([m["capacity"] * dc.TON * cs.press_factor(m, depth - hh) for hh in h])
        stroke = float(m.get("stroke") or cs.default_stroke(m["capacity"]))
        if np.all(c >= total) and stroke >= 2 * depth:
            chosen, cap = m, c
            break
    ok = chosen is not None
    if chosen is None and presses:
        chosen = presses[-1]
        cap = np.array([chosen["capacity"] * dc.TON * cs.press_factor(chosen, depth - hh) for hh in h])
    ls = LoadStroke(h, Fd, FN, cap if cap is not None else np.zeros(n), chosen["name"] if chosen else "-", ok, depth)
    r, at = ls.margin
    i = int(np.argmax(total))
    ls.note = (f"최대 하중 {total[i] / dc.TON:,.1f} tf (드로잉 {Fd[i] / dc.TON:,.1f} + 누르개 {FN[i] / dc.TON:,.1f}) — 깊이 "
               f"{h[i]:.0f} mm (하사점 위 {depth - h[i]:.0f} mm). {ls.press}: 가장 빠듯한 곳 깊이 {at:.0f} mm 에서 능력 / 하중 "
               f"{r:.2f}" + ("" if ok else " — 표의 프레스로 모자람 (행정 또는 능력)"))
    return ls


def paint_load_stroke(p, rect, ls: LoadStroke, title=True):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    from .report import _font
    p.save()
    p.fillRect(rect, QColor(255, 255, 255))
    top = rect.top() + (28 if title else 6)
    if title:
        p.setPen(QColor(30, 30, 30))
        p.setFont(_font(11, True))
        p.drawText(QRectF(rect.left(), rect.top() + 2, rect.width(), 22), Qt.AlignCenter,
                   f"하중 - 행정 · {ls.press} {'적합' if ls.ok else '모자람'}")
    g = QRectF(rect.left() + 70, top + 8, rect.width() - 100, rect.bottom() - top - 60)
    tf = dc.TON
    ymax = max(float(ls.total.max()), float(np.max(ls.cap)) if len(ls.cap) else 0) / tf * 1.1 or 1.0

    def q(hh, f):
        return QPointF(g.left() + hh / max(ls.depth, 1e-9) * g.width(), g.bottom() - f / tf / ymax * g.height())
    p.setFont(_font(8.5))
    for k in range(6):
        yv = ymax * k / 5
        p.setPen(QPen(QColor(220, 220, 220), 1))
        p.drawLine(q(0, yv * tf), q(ls.depth, yv * tf))
        p.setPen(QColor(90, 90, 90))
        p.drawText(QRectF(g.left() - 66, q(0, yv * tf).y() - 9, 60, 18), Qt.AlignRight | Qt.AlignVCenter, f"{yv:,.0f} tf")
    for frac in (0, 0.25, 0.5, 0.75, 1):
        p.drawText(QRectF(q(ls.depth * frac, 0).x() - 30, g.bottom() + 2, 60, 16), Qt.AlignCenter, f"{ls.depth * frac:.0f}")
    p.drawText(QRectF(g.left(), g.bottom() + 18, g.width(), 16), Qt.AlignCenter,
               "펀치가 들어간 깊이 mm (오른쪽 끝 = 하사점)")
    for arr, col, lab, dash in ((ls.cap, QColor(220, 30, 30), f"{ls.press} 능력 (크랭크 곡선)", Qt.DashLine),
                                (ls.total, QColor(31, 78, 140), "하중 합 (드로잉 + 누르개)", Qt.SolidLine),
                                (ls.draw, QColor(60, 170, 80), "드로잉력", Qt.SolidLine),
                                (ls.holder, QColor(240, 160, 0), "누르개 (쿠션) 힘", Qt.SolidLine)):
        p.setPen(QPen(col, 2, dash))
        p.drawPolyline(QPolygonF([q(float(a), float(b)) for a, b in zip(ls.h, arr)]))
    y = g.top() + 4
    for col, lab in ((QColor(220, 30, 30), f"{ls.press} 능력"), (QColor(31, 78, 140), "하중 합"),
                     (QColor(60, 170, 80), "드로잉력"), (QColor(240, 160, 0), "누르개 힘")):
        p.setPen(QPen(col, 3))
        p.drawLine(QPointF(g.left() + 10, y + 7), QPointF(g.left() + 34, y + 7))
        p.setPen(QColor(40, 40, 40))
        p.drawText(QRectF(g.left() + 40, y, 220, 16), Qt.AlignLeft | Qt.AlignVCenter, lab)
        y += 17
    p.restore()


def render_load_stroke(ls: LoadStroke, w=1000, h=600, dpr=1.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import new_image
    img, p = new_image(w, h, dpr)
    paint_load_stroke(p, QRectF(0, 0, w, h), ls)
    p.end()
    return img


# ---------------------------------------------------------------- 재질 · 두께 바꿔 보기

COMPARE_HEAD = ["재질", "두께 mm", "판정", "파단 %", "파단 위험 %", "가장 많이 얇아짐", "최소 두께 mm", "가장 큰 한계 비",
                "드로잉비 / LDR", "권장 프레스 tf", "블랭크 넓이 mm²", "재질값"]


def compare(solid, settings, candidates, mode=None, progress=None):
    """같은 제품을 다른 재질·두께로 다시 펼쳐 성형 해석 → [행]. candidates: [(재질 코드, 두께 또는 None)].
    두께를 바꾸면 3D 의 두께 가운데 면을 그대로 두고 판만 바꾼다 (같은 제품 모양, 다른 판)."""
    import dataclasses

    from .unfolder import FORMING, unfold
    rows = []
    for k, (code, t) in enumerate(candidates):
        if progress:
            progress(k, len(candidates), code, t)
        st = dataclasses.replace(settings, material=code,
                                 mill=settings.mill if code == settings.material else {})
        try:
            r = unfold(solid, thickness=t, settings=st, mode=mode or FORMING)
            fa = analyze(r, st)
        except Exception as e:
            rows.append([code, t or 0.0, f"실패: {str(e).splitlines()[0][:40]}"] + [""] * (len(COMPARE_HEAD) - 3))
            continue
        fr = fa.zone_frac if fa.zone_frac else [0.0] * len(ZONES)
        rows.append([code, r.thickness, fa.verdict, fr[0], fr[1], max(fa.thin_hi, 0.0), fa.t_min, fa.risk_top,
                     f"{fa.ldr[0]:.2f} / {fa.ldr[1]:.2f}" if fa.ldr else "-", fa.press_tonf,
                     r.forming.blank_area if r.forming is not None else 0.0, st.mat.source])
    return rows


def best_row(rows):
    """적합 > 주의 > 부적합, 같으면 한계 비가 작은 것."""
    order = {OK: 0, WARN: 1, NG: 2}
    ok = [r for r in rows if r[2] in order]
    return min(ok, key=lambda r: (order[r[2]], r[7])) if ok else None


# ---------------------------------------------------------------- 재생·회전용 가벼운 메시

def cluster_mesh(V, F, target=7000):
    """꼭짓점 모으기 (격자 칸마다 한 점) 로 삼각형을 줄인 메시 → (칸 번호 (n,), 새 삼각형 (k,3), 원래 삼각형 번호 (k,)).
    재생·자동 회전 동안만 쓰고, 멈추면 원래 메시로 다시 그린다."""
    F = np.asarray(F)
    if len(F) <= target:
        return np.arange(len(V)), F, np.arange(len(F))
    area = float(np.linalg.norm(_vector_area(V, F), axis=1).sum())
    cell = math.sqrt(area / (target / 2.0))
    key = np.floor((V - V.min(0)) / cell).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    G = inv[F]
    ok = (G[:, 0] != G[:, 1]) & (G[:, 1] != G[:, 2]) & (G[:, 0] != G[:, 2])
    idx = np.nonzero(ok)[0]
    srt = np.sort(G[idx], axis=1)
    _, first = np.unique(srt, axis=0, return_index=True)
    keep = idx[np.sort(first)]
    return inv, G[keep], keep


def cluster_points(inv, P):
    """칸마다 평균 점."""
    n = int(inv.max()) + 1
    out = np.zeros((n, P.shape[1]))
    np.add.at(out, inv, P)
    cnt = np.bincount(inv, minlength=n).astype(float)
    return out / np.maximum(cnt, 1)[:, None]
