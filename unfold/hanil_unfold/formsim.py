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
# - AL5052-H32: 0~1 t (The Fabricator, 3.2 mm), AL6061-T6: 2~4 t (FAA AC 43.13 0.375", 현장 자료) → 2.5 t
# - 그 밖: 재질 굽힘 시험 대표값 (SPHC·SAPH 0.5 t, SS275 1.0 t (JIS G 3101 180° 1.5 t 의 90° 쪽), SUS304 0.5 t …)
MIN_BEND_RT = {"SPCC": 0.0, "SECC": 0.0, "SGCC": 0.0, "SPHC": 0.5, "SS275": 1.0, "SAPH440": 0.5,
               "SGARC440": 0.5, "SPFC590": 1.0, "SPFC980": 2.0, "SUS304": 0.5, "SUS430": 1.0,
               "AL5052": 1.0, "AL1050": 0.0, "AL6061": 2.5, "C1100": 0.0, "C2600": 0.5}
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
    rk = flc_risk(e1, e2, fi.flc0) if fi.flc0 > 0 else np.zeros(len(e1))
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
    if np.linalg.norm(s) < 0.3 * area:
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
                p_bh = dc.HOLDER_P[dc._family(mat.code)]
                bh = max(fi.blank_area - proj, 0.0)
                if bh > 0.02 * fi.blank_area:
                    fa.loads.append(("주름 누르개 힘", p_bh * bh, f"면압 {p_bh:g} MPa × {bh:,.0f} mm² "
                                                              "(블랭크 − 펀치 투영)"))
                fa.messages.append(f"성형 깊이 {depth:.1f} mm · 펀치 투영 넓이 {proj:,.0f} mm² · "
                                   f"블랭크 {fi.blank_area:,.0f} mm²")
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
    if fa.ldr and fa.ldr[0] > fa.ldr[1] and fa.verdict == OK:     # 한 번에 못 당김 → 다단 (주의)
        fa.verdict = WARN


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
    if fi is not None:
        _forming(fa, fi, mat)
    else:
        _sheet(fa, result, settings, mat)
    peak = max((f for _, f, _ in fa.loads), default=0.0)
    total = sum(f for name, f, _ in fa.loads if not name.startswith("굽힘")) if fi is not None else peak
    fa.press_tonf = total * 1.3 / dc.TON
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


def tri_colors(fa: FormAnalysis, view: str):
    """삼각형별 색 (m, 3) 과 범례 [(글, RGB)]."""
    from .drawing import THIN_LIMIT, thinning_color
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


def paint_product(p, rect, fa: FormAnalysis, view=VIEWS[0], az=-35.0, el=30.0, title=True):
    """제품 3D 메시를 색 지도로 (화가 알고리즘 + 평면 음영)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    from .report import _font
    fi = fa.fi
    if fi is None or fi.V is None:
        return
    V = fi.V - fi.V.mean(0)
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
    lo, hi = W[:, :2].min(0), W[:, :2].max(0)
    s = min(area.width() / max(hi[0] - lo[0], 1e-9), area.height() / max(hi[1] - lo[1], 1e-9)) * 0.94
    cx, cy = area.center().x(), area.center().y()
    mid = (lo + hi) / 2
    X = cx + (W[:, 0] - mid[0]) * s
    Y = cy - (W[:, 1] - mid[1]) * s
    cols, leg = tri_colors(fa, view)
    F = fi.F
    nrm = np.cross(W[F[:, 1]] - W[F[:, 0]], W[F[:, 2]] - W[F[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    light = np.array([0.3, 0.5, 0.81])
    shade = 0.45 + 0.55 * np.abs(nrm @ light)
    order = np.argsort(W[F].mean(1)[:, 2])          # 먼 것부터
    p.save()
    p.setPen(Qt.NoPen)
    for i in order:
        c = cols[i] * shade[i]
        q = QColor(int(min(c[0], 255)), int(min(c[1], 255)), int(min(c[2], 255)))
        p.setBrush(q)
        p.setPen(QPen(q, 0.6))
        tri = F[i]
        p.drawPolygon(QPolygonF([QPointF(X[tri[0]], Y[tri[0]]), QPointF(X[tri[1]], Y[tri[1]]),
                                 QPointF(X[tri[2]], Y[tri[2]])]))
    if title:
        p.setPen(QColor(30, 30, 30))
        p.setFont(_font(12, True))
        p.drawText(QRectF(rect.left(), rect.top() + 4, rect.width(), 24), Qt.AlignCenter,
                   f"제품 성형 해석 — {view}  ({fa.material}, t {fa.thickness:g}, 판정 {fa.verdict})")
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


def render_product(fa: FormAnalysis, view=VIEWS[0], w=1000, h=760, az=-35.0, el=30.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
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
    ws["A1"] = f"제품 성형 해석 — {name}  ({fa.material}, t {fa.thickness:g}, n {fa.n:g}, r {fa.r:g})"
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
    tmps = []
    if fa.mode == "forming":
        pic = wb.create_sheet("제품 그림")
        for k, view in enumerate(VIEWS[:2] + VIEWS[4:] + VIEWS[3:4]):
            tmps.append(_add_image(pic, render_product(fa, view, 900, 680), f"{'AK'[k % 2]}{1 + 36 * (k // 2)}", 640))
        if not any(ws_.title == "두께 변화" for ws_ in wb.worksheets):
            tmps.append(_add_image(wb.create_sheet("성형 한계도"), render_fld(fa.fi, 900, 700), "A1", 700))
    return tmps


def save_xlsx(fa: FormAnalysis, path, name=""):
    import os

    from openpyxl import Workbook
    wb = Workbook()
    tmps = add_sheets(wb, fa, name, first=True)
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
         "원스텝은 펀치 R 근처 얇아짐을 작게 본다 (굽힘-펴짐·마찰 이력 없음): 실험 컵은 펀치 R 에서 15~18 % 얇아지고 "
         "위 끝이 약 10 % 두꺼워진다 — 두꺼워짐은 맞고 얇아짐은 실험보다 작다.",
         "절곡: 바깥 면 공칭 변형률 1/(2R/t+1) 을 재질의 최소 굽힘 R/t (90°, 압연 방향과 직각) 에서의 값과 비교 "
         "(Datsko·Yang, Kalpakjian). 스프링백은 가공 경화 유동 응력의 탄성-소성 식."]


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

    y = header(f"제품 성형 해석 — {name}  ({fa.material}, t {fa.thickness:g}) · 판정 {fa.verdict}")
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
    p.end()
