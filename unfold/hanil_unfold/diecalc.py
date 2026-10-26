"""금형 검토: 프레스 금형 설계 교재·핸드북의 계산을 전개 결과에 적용한다.

  · 하중      전단(블랭킹·피어싱)력, 스트리퍼력, 굽힘력, 권장 프레스 톤수
  · 클리어런스 재질 인장강도·두께에 따른 한쪽 클리어런스
  · 스프링백   굽힘 후 되돌아가는 각도와 금형 보정 각도
  · 설계 규칙  최소 구멍 지름, 구멍~외곽·구멍~구멍·구멍~절곡 거리, 최소 플랜지
  · 스트립     순차(프로그레시브) 금형 1열 배치: 피치·폭·재료 이용률
  · 드로잉     원통 컵 블랭크 지름, 드로잉 횟수·단별 지름, 드로잉력·주름 누르개 힘

값은 교재·핸드북의 대표값이다 (README '금형 검토' 의 출처). 금형 확정 전에는 회사 기준으로 맞춘다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc

G = 9.80665          # N → kgf
TON = 1000 * G       # N → tonf

# ---------------------------------------------------------------- 재질 상수 (대표값)

# 항복 강도 [MPa], 탄성 계수 [GPa] — 스프링백 계산용
YIELD_E = {
    "SPCC": (210, 205), "SPHC": (250, 205), "SECC": (210, 205), "SGCC": (250, 205),
    "SS275": (275, 205), "SAPH440": (305, 205), "SGARC440": (300, 205),
    "SPFC590": (380, 205), "SPFC980": (650, 205),
    "SUS304": (250, 193), "SUS430": (300, 200),
    "AL5052": (195, 70), "AL1050": (105, 69), "AL6061": (275, 69),
    "C1100": (200, 117), "C2600": (300, 103),
}

# 주름 누르개 면압 [MPa]: 강 2.5, 동합금 2.0~2.4, 알루미늄 1.2~1.5 (딥드로잉 교재),
# 스테인리스는 저탄소강의 페라이트계(430) 약 1.5 배, 오스테나이트계(304) 최대 3 배 (MetalForming 2017)
HOLDER_P = {"steel": 2.5, "sus": 3.75, "sus_aus": 6.0, "al": 1.35, "cu": 2.2}
# 전단 저항 / 인장강도: 강·스테인리스 0.8, 알루미늄 0.55~0.65 (권장 0.6), 동 0.7
SHEAR_RATIO = {"steel": 0.8, "sus": 0.8, "sus_aus": 0.8, "al": 0.6, "cu": 0.7}


def _family(code):
    if code.startswith("SUS3"):
        return "sus_aus"            # 300 계 오스테나이트
    if code.startswith("SUS"):
        return "sus"
    if code.startswith("AL"):
        return "al"
    if code.startswith("C"):
        return "cu"
    return "steel"


def shear_strength(mat: bc.Material) -> float:
    """전단 저항 τ [MPa] = 인장강도 × 재질별 비 (강 0.8, 알루미늄 0.6, 동 0.7)."""
    return SHEAR_RATIO[_family(mat.code)] * mat.tensile_mpa


def clearance_pct(mat: bc.Material, t: float) -> float:
    """한쪽 클리어런스 [두께의 %] (표준 등급). 단단할수록, 두꺼울수록 크게."""
    ts = mat.tensile_mpa
    pct = 5.0 if ts < 300 else 7.0 if ts < 500 else 9.0 if ts < 800 else 11.0
    if t > 3.0:
        pct += 1.0
    return pct


def vdi_clearance(mat: bc.Material, t: float, c: float = 0.01) -> float:
    """VDI 3368 한쪽 클리어런스 u = c · s · √(0.1 · τB) [mm] (τB N/mm²).
    c = 0.005~0.01 버(burr) 없는 깨끗한 절단, 0.01~0.035 버 허용. (Hanser 「Formelsammlung Fertigungstechnik」)"""
    return c * t * math.sqrt(0.1 * shear_strength(mat))


def die_plate_thickness(force_n: float) -> float:
    """다이(Schneidplatte) 두께 어림 H ≈ ∛(0.1 · F) [mm], F 절단력 N (독일 교재 어림식), 최소 15 mm."""
    return max(15.0, (0.1 * max(force_n, 0.0)) ** (1 / 3))


def ldr(mat: bc.Material, eta: float = 0.74) -> float:
    """한계 드로잉비 β_max (LDR) = exp(η · √((1 + r) / 2)) — Whiteley (1960) 의 수직 이방성 식에
    변형 효율 η 를 곱한 꼴 (Hosford·Caddell). η = 1 이면 마찰 없는 이상값 (r = 1 에서 2.72),
    η 0.74 는 r = 1 에서 2.1 (연강 실험값 2.0~2.2) 이 되게 맞춘 값."""
    return math.exp(eta * math.sqrt((1 + max(mat.r, 0.1)) / 2))


def mean_flow_stress(mat: bc.Material, phi: float) -> float:
    """0 ~ φ 의 평균 유동 응력 k_fm = K · φⁿ / (n + 1),  K = σb · (e/n)ⁿ (홀로몬, 인장강도·n 에서)."""
    n = max(mat.n, 0.02)
    k = mat.tensile_mpa * (math.e / n) ** n
    return k * max(phi, 1e-6) ** n / (n + 1)


def siebel_force(d, D, t, mat: bc.Material, eta_f: float = 0.65) -> float:
    """Siebel 드로잉력: 이상 변형력 π · d_m · s · 1.1 · k_fm · ln(D/d) 을 변형 효율 η_F 로 나눔
    (마찰·굽힘-펴짐 몫을 η_F 0.5~0.7 로). d_m = d (두께 가운데)."""
    phi = math.log(max(D / max(d, 1e-9), 1.0))
    return math.pi * d * t * 1.1 * mean_flow_stress(mat, phi) * phi / eta_f


def min_hole_factor(mat: bc.Material) -> float:
    """피어싱 최소 구멍 지름 = 계수 × 두께 (연질·연강 1.0, 단단한 재질 1.5)."""
    return 1.5 if mat.tensile_mpa >= 500 else 1.0


# ---------------------------------------------------------------- 하중

@dataclass
class Load:
    name: str
    length: float        # 전단·굽힘 길이 mm
    force_n: float
    note: str = ""

    @property
    def tonf(self):
        return self.force_n / TON


def bend_force(mat, length, t, v, process=bc.AIR):
    """V 다이 굽힘력 F = C · σb · L · t² / V,  C = 1 + 4 t / V (Schuler 「Metal Forming Handbook」·DIN 식 —
    V = 12 t 에서 1.33, V = 8 t 에서 1.5, 상수 1.33 만 쓰면 V 가 좁을 때 작게 나온다). 바텀 ×2, 코이닝 ×5 (최소)."""
    v = max(v, 1e-6)
    f = (1 + 4 * t / v) * mat.tensile_mpa * length * t * t / v
    return f * {bc.AIR: 1.0, bc.BOTTOM: 2.0, bc.COIN: 5.0}.get(process, 1.0)


def yield_strength(mat: bc.Material) -> float:
    """항복 강도 [MPa] — 밀시트 값, 없으면 대표값 표."""
    return mat.yield_mpa if mat.yield_mpa > 0 else YIELD_E.get(mat.code, (250, 205))[0]


def modulus_gpa(mat: bc.Material) -> float:
    return mat.e_gpa if mat.e_gpa > 0 else YIELD_E.get(mat.code, (250, 205))[1]


def swift(mat: bc.Material):
    """Swift 가공 경화 σ̄ = K (ε0 + ε̄)ⁿ 를 항복 강도 · 인장 강도 · n 에 맞춘 (K, ε0).
    σy = K ε0ⁿ,  인장 강도 (공칭) = K nⁿ exp(−(n − ε0)) (최대 하중 = 균일 연신 끝 ε̄ = n − ε0).
    (홀로몬 K εⁿ 은 처음 항복을 0 으로 보아 굽힘 R 이 클 때 유동 응력을 작게 낸다.)"""
    n = max(mat.n, 0.02)
    ys, ts = yield_strength(mat), mat.tensile_mpa
    lo, hi = 1e-7, n * 0.999
    f = lambda e0: ys * (n / e0) ** n * math.exp(-(n - e0)) - ts  # noqa: E731  (e0 가 크면 감소)
    if f(hi) > 0:                                  # 항복비가 아주 높음 → ε0 ≈ n
        e0 = hi
    elif f(lo) < 0:
        e0 = lo
    else:
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
        e0 = (lo + hi) / 2
    return ys / e0 ** n, e0


def flow_stress(mat: bc.Material, strain: float) -> float:
    """유동 응력 [MPa] σ̄ = K (ε0 + ε̄)ⁿ (Swift, 항복·인장 강도·n 에 맞춤)."""
    k, e0 = swift(mat)
    return k * (e0 + max(strain, 0.0)) ** max(mat.n, 0.02)


# 하중을 뺄 때 탄성 계수가 줄어드는 것 (Yoshida·Uemori 2002): E = E0 − (E0 − Ea)(1 − exp(−ξ ε̄))
# DP600 t1.62: E0 206, Ea 152 GPa, ξ 61 (JSTAMP Yoshida-Uemori 스프링백 논문). 고장력강 (590 이상) 에만 쓰고,
# 980 급 공개값을 못 찾아 같은 값을 쓴다 (보수적 아님 — 실측 권장). 연강·스테인리스·알루미늄은 E0 그대로.
MODULUS_DROP = {"SPFC590": (152 / 206, 61.0), "SPFC980": (152 / 206, 61.0)}
POISSON = 0.3


def chord_modulus(mat: bc.Material, strain: float) -> float:
    """소성 변형 ε̄ 뒤 하중 뺄 때 탄성 계수 [GPa]."""
    e0 = modulus_gpa(mat)
    if mat.code not in MODULUS_DROP:
        return e0
    ratio, xi = MODULUS_DROP[mat.code]
    return e0 - (e0 - ratio * e0) * (1 - math.exp(-xi * max(strain, 0.0)))


def _hill_ps(r):
    """평면 변형 (굽힘) 에서 σ1 / σ̄ = ε̄ / ε1 = (1 + r) / √(1 + 2r) (Hill 1948 수직 이방성, r = 1 → 1.155 = 2/√3)."""
    r = max(r, 0.1)
    return (1 + r) / math.sqrt(1 + 2 * r)


def bend_moment(mat: bc.Material, r, t, npts=400):
    """단위 폭 굽힘 모멘트 [N·mm/mm] 와 두께 평균 등가 소성 변형률 — 두께 가운데 반지름 ρ = R + t/2 의 순수 굽힘,
    탄성 코어 + Swift 가공 경화, 평면 변형 (Marciniak·Duncan·Hu 「Mechanics of Sheet Metal Forming」 6 장)."""
    k, e0 = swift(mat)
    n = max(mat.n, 0.02)
    h = _hill_ps(mat.r)
    ep = modulus_gpa(mat) * 1000 / (1 - POISSON ** 2)        # 평면 변형 탄성 계수 E'
    rho = r + t / 2
    s_y = h * k * e0 ** n                                     # 평면 변형 첫 항복
    e_y = s_y / ep
    m, pe = 0.0, 0.0
    dy = (t / 2) / npts
    for i in range(npts):
        y = (i + 0.5) * dy
        eps = math.log(1 + y / rho)                           # 섬유 변형률 (진)
        if eps <= e_y:
            sig = ep * eps
        else:
            p_ = h * (eps - e_y)                              # 등가 소성 변형률
            sig = h * k * (e0 + p_) ** n
            pe += p_ * dy
        m += 2 * sig * y * dy
    return m, pe / (t / 2)


def springback(mat: bc.Material, r, t, angle_deg):
    """(되돌아간 뒤 각도, 금형에서 접어야 할 각도, 계수 Ks). 모멘트 법 (Marciniak·Duncan·Hu):
    하중을 빼면 곡률이 Δκ = M / (E' t³/12) 만큼 줄고 두께 가운데 길이는 그대로 → Ks = κ'/κ = 되돌아간 각 / 접은 각.
    M 은 탄성 코어 + Swift 가공 경화 + Hill 평면 변형 (r 값), E' = E/(1 − ν²) 에 고장력강은 Yoshida·Uemori 탄성
    계수 감소. (예전: 탄성-완전 소성 Ri/Rf = 4x³ − 3x + 1, Kalpakjian)"""
    r = max(r, 0.1 * t)
    m, pe = bend_moment(mat, r, t)
    e_un = chord_modulus(mat, pe) * 1000 / (1 - POISSON ** 2)
    kappa = 1 / (r + t / 2)
    d_kappa = 12 * m / (e_un * t ** 3)
    ks = (kappa - d_kappa) / kappa
    from . import calibration
    k_cal, _ = calibration.factor("springback", mat.code)      # 실적 보정 (되돌아가는 양에 곱함)
    ks = 1 - k_cal * (1 - ks)
    if ks <= 0.05:                                 # R/t 가 아주 커서 거의 탄성으로 다 돌아옴
        return 0.0, float("inf"), 0.0
    return angle_deg * ks, angle_deg / ks, ks


def springback_classic(mat: bc.Material, r, t, angle_deg):
    """견줌용: 탄성-완전 소성 식 Ri/Rf = 4x³ − 3x + 1, x = Ri·σ/(E·t) (Gardiner 1957, Kalpakjian)."""
    r = max(r, 0.1 * t)
    sig = flow_stress(mat, t / (2 * r + t))
    x = r * sig / (modulus_gpa(mat) * 1000 * t)
    ratio = 4 * x ** 3 - 3 * x + 1
    if ratio <= 0.05:
        return 0.0, float("inf"), 0.0
    ks = (r + t / 2) / (r / ratio + t / 2)
    return angle_deg * ks, angle_deg / ks, ks


# ---------------------------------------------------------------- 설계 규칙 검사

OK, WARN, NG = "적합", "주의", "부적합"


@dataclass
class Check:
    rule: str
    target: str
    value: float
    limit: float
    verdict: str
    note: str = ""


def _seg_dist(p, a, b):
    """점들 p (n,2) 에서 선분 ab 까지 거리."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    L2 = float(ab @ ab) or 1e-30
    s = np.clip(((p - a) @ ab) / L2, 0, 1)
    return np.linalg.norm(p - (a + s[:, None] * ab), axis=1)


def _poly_dist(P, Q):
    """두 닫힌 점 목록 사이 가장 가까운 거리 (꼭짓점 ↔ 변)."""
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    best = math.inf
    for A, B in ((P, Q), (Q, P)):
        for i in range(len(B)):
            best = min(best, float(_seg_dist(A, B[i], B[(i + 1) % len(B)]).min()))
    return best


def _hole_size(h):
    h = np.asarray(h, float)
    c = h.mean(0)
    w, ht = np.ptp(h, axis=0)
    rs = np.linalg.norm(h - c, axis=1)
    round_ = rs.mean() > 0 and (rs.max() - rs.min()) < 0.02 * rs.mean() + 0.01
    return c, (2 * rs.mean() if round_ else None), float(min(w, ht))


def design_checks(result, settings: bc.BendSettings, part=None):
    """전개 결과의 설계 규칙 검사 목록."""
    from .nesting import NestPart
    t = result.thickness
    mat = settings.mat
    out = []
    if part is None:
        part = NestPart.from_result("p", result)
    holes = [np.asarray(h, float) for h in part.holes]
    labels = {}
    # 구멍 번호는 dims 와 같은 순서 (아래→위, 왼쪽→오른쪽)
    order = sorted(range(len(holes)), key=lambda i: (round(holes[i][:, 1].mean() - result.bbox[1], 1),
                                                     round(holes[i][:, 0].mean() - result.bbox[0], 1)))
    for n, i in enumerate(order, 1):
        labels[i] = f"H{n}"

    kmin = min_hole_factor(mat)
    for i, h in enumerate(holes):
        c, dia, small = _hole_size(h)
        size = dia if dia is not None else small
        lim = kmin * t
        out.append(Check("최소 구멍 지름 (피어싱)", labels[i], size, lim,
                         OK if size >= lim else NG,
                         f"{kmin:g}t 이상 — 작으면 펀치가 부러짐 (레이저·드릴 가공은 가능)"))
    if part.outer is not None:
        outer = np.asarray(part.outer, float)
        for i, h in enumerate(holes):
            d = _poly_dist(h, outer)
            v = OK if d >= 2 * t else WARN if d >= t else NG
            out.append(Check("구멍 ~ 외곽 거리", labels[i], d, 2 * t, v,
                             "프레스 피어싱 2t 권장, 1t 미만은 찢어짐·변형"))
    for a in range(len(holes)):
        for b in range(a + 1, len(holes)):
            if np.linalg.norm(holes[a].mean(0) - holes[b].mean(0)) > 50 * t + np.ptp(holes[a], 0).max() \
                    + np.ptp(holes[b], 0).max():
                continue
            d = _poly_dist(holes[a], holes[b])
            if d < 2 * t:
                out.append(Check("구멍 ~ 구멍 거리", f"{labels[a]}-{labels[b]}", d, 2 * t,
                                 WARN if d >= t else NG, "2t 권장"))
    for bnd in result.bends:
        half = bnd.allowance / 2
        for i, h in enumerate(holes):
            d = float(_seg_dist(h, *bnd.line).min()) - half
            if d > 10 * t:
                continue
            lim = 2 * t
            out.append(Check("구멍 ~ 절곡 시작선", f"{labels[i]}·B{bnd.number}", d, lim,
                             OK if d >= lim else NG if d < 0 else WARN,
                             "2t 미만이면 구멍이 늘어남 (3D 로 구멍 가장자리 ~ 플랜지 안쪽 면 2t+R)"))
    # 플랜지 길이: 가로·세로 절곡의 끝 쪽 간격 (dims 의 연속 치수)
    from . import dims as dm
    bends = {f"B{b.number}": b for b in result.bends}
    v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)
    for ch in dm.compute(result).chains:
        n = len(ch.positions)
        for k in range(n - 1):
            a, b = ch.labels[k], ch.labels[k + 1]
            if (a == "끝") == (b == "끝"):
                continue
            bnd = bends[b if a == "끝" else a]
            straight = ch.positions[k + 1] - ch.positions[k] - bnd.allowance / 2
            outer_len = straight + bnd.inner_radius + t
            lim = max(4 * t, v / 2 + t)
            verdict = OK if outer_len >= lim else WARN if outer_len >= 3 * t else NG
            out.append(Check("최소 플랜지 (바깥 치수)", f"B{bnd.number} {'왼쪽' if k == 0 else '오른쪽'}"
                             if ch.axis == "x" else f"B{bnd.number} {'아래' if k == 0 else '위'}",
                             outer_len, lim, verdict,
                             f"V{v:g} 위에 걸쳐야 함 (4t 또는 V/2+t, 3t 미만 불가)"))
    return out


# ---------------------------------------------------------------- 스트립 레이아웃

@dataclass
class Strip:
    angle: float          # 부품을 돌린 각도 (이송 방향 = X)
    pitch: float
    width: float
    bridge: float
    side: float
    part_area: float
    utilization: float
    mask: np.ndarray | None = None
    res: float = 0.0
    origin: tuple = (0.0, 0.0)

    @property
    def per_meter(self):
        return 1000.0 / self.pitch


def strip_layout(result, part=None, bridge=None, side=None, step=5.0):
    """1열 순차 배치. 잔폭(부품 사이) 기본 max(1.5t, 1 mm), 옆 잔폭 max(2t, 1.5 mm).
    피치는 바운딩 박스가 아니라 실제 모양으로 맞물리는 최소 간격 (격자 상관)."""
    from scipy import ndimage

    from .nesting import NestPart, _rasterize
    t = result.thickness
    if part is None:
        part = NestPart.from_result("p", result)
    bridge = max(1.5 * t, 1.0) if bridge is None else bridge
    side = max(2.0 * t, 1.5) if side is None else side
    w, h = result.size
    res = max(max(w, h) / 400.0, 0.05)
    gap = max(1, int(math.ceil(bridge / res)))
    yy, xx = np.mgrid[-gap:gap + 1, -gap:gap + 1]
    disk = xx ** 2 + yy ** 2 <= gap * gap

    def evaluate(angle):
        m, org = _rasterize(part, angle, res)
        rows = np.nonzero(m.any(1))[0]
        cols = np.nonzero(m.any(0))[0]
        m = m[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
        grown = ndimage.binary_dilation(np.pad(m, gap), structure=disk)
        H, W = grown.shape
        # 같은 줄에서 오른쪽으로 s 칸 옮긴 부품과 겹치는지: 줄마다 상관 (FFT)
        n = 2 * W
        A = np.fft.rfft(grown.astype(float), n, axis=1)
        B = np.fft.rfft(np.pad(m, gap).astype(float), n, axis=1)
        corr = np.fft.irfft(np.conj(B) * A, n, axis=1).sum(0)[:W + 1]
        free = np.nonzero(corr[1:] < 0.5)[0]
        s = (free[0] + 1) if len(free) else W
        pitch = s * res
        width = m.shape[0] * res + 2 * side
        return pitch, width, m, (org[0] + cols[0] * res, org[1] + rows[0] * res)

    best = None
    angles = list(np.arange(0, 180, step))
    for a in angles:
        p, wd, m, org = evaluate(a)
        u = part.area / (p * wd)
        if best is None or u > best[0] + 1e-9:
            best = (u, a, p, wd, m, org)
    a0 = best[1]
    for a in np.arange(a0 - step + 1, a0 + step, 1.0):
        p, wd, m, org = evaluate(a % 180)
        u = part.area / (p * wd)
        if u > best[0] + 1e-9:
            best = (u, a % 180, p, wd, m, org)
    u, a, p, wd, m, org = best
    # 격자는 보수적이라 피치·폭이 칸 하나둘만큼 크다: 닫힌 외곽이 있으면 정확한 거리로 다듬는다
    if part.outer is not None:
        from .nesting import _rot_poly
        O = np.asarray(_rot_poly(part.outer, a), float)
        wd = float(np.ptp(O[:, 1])) + 2 * side
        lo, hi = max(p - 4 * res, 1e-3), p
        if _poly_dist(O, O + (lo, 0)) < bridge:
            for _ in range(14):
                mid = 0.5 * (lo + hi)
                if _poly_dist(O, O + (mid, 0)) >= bridge:
                    hi = mid
                else:
                    lo = mid
            p = hi
        else:
            p = lo
        u = part.area / (p * wd)
    return Strip(float(a), float(p), float(wd), bridge, side, part.area, float(u), m, res, org)


# ---------------------------------------------------------------- 원통 드로잉

# 한계 드로잉률 m (주름 누르개 사용, 플랜지 없는 원통). 행: 상대 두께 t/D×100 구간 아래 끝.
# 열: m1(첫 드로잉), m2, m3, m4, m5. 값은 구간의 가운데.
DRAW_TABLE = [
    (1.5, (0.49, 0.74, 0.77, 0.79, 0.81)),
    (1.0, (0.515, 0.755, 0.785, 0.805, 0.83)),
    (0.6, (0.54, 0.77, 0.795, 0.815, 0.845)),
    (0.3, (0.565, 0.785, 0.805, 0.825, 0.855)),
    (0.15, (0.59, 0.795, 0.815, 0.84, 0.865)),
    (0.0, (0.615, 0.81, 0.83, 0.855, 0.875)),
]

# 드로잉력 계수 n:  F = π · d · t · σb · n  (드로잉률 m 에 따라)
FORCE_K = [(0.55, 1.00), (0.575, 0.93), (0.60, 0.86), (0.625, 0.79), (0.65, 0.72), (0.675, 0.66),
           (0.70, 0.60), (0.725, 0.55), (0.75, 0.50), (0.775, 0.45), (0.80, 0.40)]


def siebel_holder_pressure(beta, d1, t, mat: bc.Material):
    """Siebel 누르개 면압 p = [(β − 1)^k + d1 / (200 s)] · Rm / 400 [MPa] (강-강, 드로잉유, 혼합 윤활).
    지수 k 는 자료마다 2 (Aufgabensammlung Fertigungstechnik) · 3 (Siebel·Beisswanger 인용) 이 달라 둘 중 큰 값.
    확인: β 2 · d1 100 · s 1 · Rm 310 → 1.16 MPa (4ming Forming Handbook 예제와 같음)."""
    b = max(beta - 1, 0.0)
    return (max(b ** 2, b ** 3) + d1 / (200 * max(t, 1e-9))) * mat.tensile_mpa / 400


def die_radius(D, d, t, flange=False):
    """다이 어깨 R r_M = 0.035 · [50 + (D − d)] · √s (Oehler·Kaiser 「Schnitt-, Stanz- und Ziehwerkzeuge」).
    플랜지가 남거나 β < 1.4 면 20 % 줄여도 된다. 확인: D 200 · d 100 · s 1 → 5.25 mm (4ming 예제).
    너무 작으면 바닥 R 쪽 터짐, 너무 크면 주름 — 5 ≤ r_M / s ≤ 10 (4ming)."""
    r = 0.035 * (50 + (D - d)) * math.sqrt(t)
    if flange or D / max(d, 1e-9) < 1.4:
        r *= 0.8
    return r


def draw_gap(t, beta_total, mat: bc.Material):
    """(권장, 최대) 한쪽 틈새. 플랜지 바깥 끝이 둘레로 줄며 두꺼워져 t·β^(1/(1+r)) 이 된다 (단축 압축, 수직 이방성 r:
    ε_t = −ε_θ / (1 + r); r = 1 이면 t√β — 4ming 「Ziehspalt」 t 1 · β 2 → 최대 1.41). 권장은 판 두께의 1.0~1.1 배
    (MISUMI 「円筒絞りのクリアランス」) — 그보다 위 끝이 두꺼우면 끝이 조금 훑인다 (아이어닝)."""
    rim = t * max(beta_total, 1.0) ** (1 / (1 + max(mat.r, 0.1)))
    return min(1.1 * t, rim) if rim > t else t, rim


def holder_misumi(t, d, D):
    """MISUMI: t/d ≥ K (D/d − 1) 이면 누르개 없이 드로잉 (K 0.09~0.17, 큰 K 가 안전)."""
    lhs, k = t / max(d, 1e-9), (D / max(d, 1e-9) - 1)
    if lhs >= 0.17 * k:
        return "없이도 가능 (t/d ≥ 0.17 (D/d − 1))"
    if lhs < 0.09 * k:
        return "필요 (t/d < 0.09 (D/d − 1))"
    return "경우에 따라 (K 0.09~0.17 사이)"


def draw_ratios(t, D):
    rel = 100.0 * t / D
    for lo, ms in DRAW_TABLE:
        if rel >= lo:
            return ms
    return DRAW_TABLE[-1][1]


def force_k(m):
    xs = [a for a, _ in FORCE_K]
    ys = [b for _, b in FORCE_K]
    return float(np.interp(m, xs, ys))


def cup_area(d, h, r, flange_d=0.0, rf=0.0):
    """두께 가운데 면 넓이. d 지름, h 바닥~위 끝 높이 (플랜지 면까지), r 바닥 모서리 R,
    flange_d 플랜지 바깥 지름 (0 = 없음), rf 플랜지 쪽 R. 파푸스 정리로 정확히."""
    R = d / 2
    r = min(r, R, h)
    a = math.pi * (R - r) ** 2                                     # 바닥
    a += (math.pi * r / 2) * 2 * math.pi * (R - r + 2 * r / math.pi)   # 바닥 모서리 1/4 원환
    wall = h - r - (rf if flange_d else 0.0)
    a += math.pi * d * max(wall, 0.0)
    if flange_d:
        a += (math.pi * rf / 2) * 2 * math.pi * (R + rf - 2 * rf / math.pi)   # 플랜지 R
        a += math.pi / 4 * (flange_d ** 2 - (d + 2 * rf) ** 2)
    return a


@dataclass
class DrawStage:
    no: int
    m: float
    d: float
    force_n: float            # 두 식 중 큰 값 (프레스 고르기)
    table_n: float = 0.0      # π·d·t·σb·n (교재 표)
    siebel_n: float = 0.0     # Siebel (독일)
    die_r: float = 0.0        # 다이 어깨 R 권장 (Oehler·Kaiser)
    gap: float = 0.0          # 한쪽 드로잉 틈새 권장
    gap_max: float = 0.0      # 한쪽 틈새 최대 (위 끝 두께 = t · β^(1/(1+r)))


@dataclass
class DrawPlan:
    D: float
    trim: float
    rel_thickness: float       # t/D × 100
    ratio_total: float         # d / D
    stages: list = field(default_factory=list)
    holder_n: float = 0.0          # 누르개 힘 (Siebel 면압 × 누르개 넓이)
    holder_needed: str = ""
    notes: list = field(default_factory=list)
    holder_p: float = 0.0          # Siebel 면압 MPa
    holder_tab_n: float = 0.0      # 교재 표 면압 (강 2.5 MPa …) 으로 — 다이 쿠션 능력 고를 때 상한
    holder_misumi: str = ""        # t/d ≥ K (D/d − 1) 판정 (MISUMI, K 0.09~0.17)


def draw_plan(d, h, r, t, mat: bc.Material, flange_d=0.0, rf=0.0, trim=None):
    """원통 컵 공정. 치수는 두께 가운데 기준 (도면이 바깥·안쪽 치수면 t/2 만큼 맞춰 넣는다).
    trim: 위 끝 다듬기 여유 (mm, None 이면 높이의 3 % 와 1 mm 중 큰 값)."""
    if trim is None:
        trim = max(1.0, 0.03 * h)
    hh = h + (trim if not flange_d else 0.0)
    fd = flange_d + (2 * trim if flange_d else 0.0)
    D = math.sqrt(4 * cup_area(d, hh, r, fd, rf) / math.pi)
    rel = 100 * t / D
    ms = list(draw_ratios(t, D))
    # 드로잉률 표는 연강 (r ≈ 1) 기준 — 재질의 r 로 첫 드로잉률을 고친다: m1 × LDR(r=1) / LDR(r)
    lim = ldr(mat)
    k_r = min(max(math.exp(0.74) / lim, 0.9), 1.1)          # LDR(r = 1) / LDR(r)
    ms[0] = ms[0] * k_r
    if flange_d:
        notes = ["플랜지 붙은 컵: 첫 드로잉률은 플랜지 비 df/d 에 따라 더 작아질 수 있습니다 (표는 플랜지 없는 원통)"]
    else:
        notes = []
    stages, cur = [], D
    for i in range(12):
        m = ms[min(i, len(ms) - 1)]
        nxt = cur * m
        if nxt <= d + 1e-9:
            m = d / cur
            nxt = d
        f_tab = math.pi * nxt * t * mat.tensile_mpa * force_k(m)
        f_sie = siebel_force(nxt, cur, t, mat)
        gap, gap_max = draw_gap(t, D / nxt, mat)
        rd = die_radius(cur, nxt, t, bool(flange_d) and nxt <= d + 1e-9)
        if i:                                        # 재드로잉: Oehler 식은 첫 드로잉용 → 5~10 t 안으로
            rd = min(max(rd, 5 * t), 10 * t)
        stages.append(DrawStage(i + 1, m, nxt, max(f_tab, f_sie), f_tab, f_sie, rd, gap, gap_max))
        cur = nxt
        if nxt <= d + 1e-9:
            break
    if rel >= 2.0:
        need = "없이도 가능 (t/D ≥ 2 %)"
    elif rel >= 1.5:
        need = "경우에 따라 (t/D 1.5~2 %)"
    else:
        need = "필요 (t/D < 1.5 %)"
        if rel < 0.5:
            notes.append("t/D < 0.5 %: 주름 누르개가 있어도 주름 위험이 큼")
    if abs(k_r - 1) > 0.005:
        notes.append(f"첫 드로잉률을 r = {mat.r:g} 로 고침 (× {k_r:.3f}): 한계 드로잉비 LDR = {lim:.2f} "
                     "(Whiteley·Hosford, η 0.74)")
    if D / d > lim and len(stages) == 1:
        notes.append(f"D/d = {D / d:.2f} 이 LDR {lim:.2f} 보다 큼 — 다단 드로잉 필요")
    d1 = stages[0].d
    area = math.pi / 4 * max(D ** 2 - (d1 + 2 * stages[0].die_r) ** 2, 0)
    p_sie = siebel_holder_pressure(D / d1, d1, t, mat)
    p_tab = HOLDER_P[_family(mat.code)]
    rr = stages[0].die_r / t
    if rr < 5 or rr > 10:
        notes.append(f"1차 다이 R {stages[0].die_r:.1f} = {rr:.1f} t — 5~10 t 밖 (4ming): "
                     + ("작으면 바닥 R 터짐" if rr < 5 else "크면 주름") + " 쪽, 시험 타발로 확인")
    if len(stages) > 1:
        notes.append("재드로잉 다이 R: Oehler 식은 첫 드로잉용이라 5~10 t 범위로 둠")
    notes.append(f"누르개 면압 Siebel {p_sie:.2f} MPa (표 값 {p_tab:g} MPa 는 다이 쿠션 능력 고를 때 상한으로)")
    if abs(mat.dr) > 0.1:
        notes.append(f"면내 이방성 Δr {mat.dr:+.2f} (밀시트): 귀 (earing) 4 곳 — " +
                     ("0°·90° 방향" if mat.dr > 0 else "45° 방향") + " 이 높아짐, 다듬기 여유를 넉넉히")
    if mat.source != "대표값":
        notes.append(f"재질값: {mat.source} (TS {mat.tensile_mpa:g} · n {mat.n:g} · r̄ {mat.r:.2f})")
    return DrawPlan(D, trim, rel, d / D, stages, area * p_sie, need, notes, p_sie, area * p_tab,
                    holder_misumi(t, d1, D))


# ---------------------------------------------------------------- 한 부품 정리

@dataclass
class DieReport:
    thickness: float
    material: str
    clearance_pct: float
    clearance_mm: float
    shear_mpa: float
    loads: list
    bends: list               # (번호, 길이, 힘 N, 되돌아간 각, 금형 각, Ks)
    total_n: float
    press_tonf: float
    checks: list
    strip: Strip | None
    blank_d: float | None = None   # 성형품: 같은 넓이 원판 지름
    vdi_clearance_mm: float = 0.0  # VDI 3368 (c = 0.01) 한쪽 클리어런스
    die_plate_mm: float = 0.0      # 다이 두께 어림 ∛(0.1 F)


def review(result, settings: bc.BendSettings, strip=True):
    from . import metrics as mt
    from .nesting import NestPart
    t = result.thickness
    mat = settings.mat
    part = NestPart.from_result("p", result)
    tau = shear_strength(mat)
    hole_len = sum(_perimeter(h) for h in part.holes)
    m = mt.compute(result, mat.density)
    outer_len = max(m.cut_length - hole_len, 0.0)
    blank = Load("블랭킹 (외곽 전단)", outer_len, outer_len * t * tau)
    pierce = Load(f"피어싱 (구멍 {len(part.holes)}개)", hole_len, hole_len * t * tau)
    strip_f = Load("스트리퍼 (전단력의 10 %)", 0.0, 0.10 * (blank.force_n + pierce.force_n),
                   "문헌 범위 5~20 %")
    loads = [blank, pierce, strip_f]
    v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)
    bends = []
    for b in result.bends:
        f = bend_force(mat, b.length, t, v, settings.process)
        if b.kind == "날카로운 모서리" or b.angle_deg < 1:
            sb = (b.angle_deg, b.angle_deg, 1.0)
        else:
            # 에어 벤딩은 상형 R 이 작아도 판이 V 폭에 맞는 자연 R 로 휜다
            r = b.inner_radius
            if settings.process == bc.AIR:
                r = max(r, mat.air_ratio * v)
            sb = springback(mat, r, t, b.angle_deg)
        bends.append((b.number, b.length, f) + sb)
    if bends:
        loads.append(Load(f"굽힘 (가장 큰 것, V{v:g} {bc.PROCESS_NAMES[settings.process]})",
                          max(b[1] for b in bends), max(b[2] for b in bends)))
    total = blank.force_n + pierce.force_n + strip_f.force_n
    checks = design_checks(result, settings, part)
    st = None
    if strip:
        try:
            st = strip_layout(result, part)
        except Exception:
            st = None
    cl = clearance_pct(mat, t)
    from . import calibration
    k_ton, _ = calibration.factor("tonnage", "전단·굽힘")
    rep = DieReport(t, mat.code, cl, cl / 100 * t, tau, loads, bends, total,
                    max(total, max((b[2] for b in bends), default=0)) * 1.3 * k_ton / TON, checks, st)
    if result.forming is not None:
        rep.blank_d = math.sqrt(4 * m.blank_area / math.pi)
    rep.vdi_clearance_mm = vdi_clearance(mat, t)
    rep.die_plate_mm = die_plate_thickness(total)
    return rep


def _perimeter(poly):
    P = np.asarray(poly, float)
    return float(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1).sum())
