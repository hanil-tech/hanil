"""원스텝 역해석 뒤 드로잉 보정: 금형을 지나며 생기는 얇아짐을 원스텝 막 (membrane) 변형률에 더한다.

원스텝 (전변형 이론, 막 요소) 은 블랭크 → 제품의 최종 모양만 보므로 두 가지를 못 본다.
 1) 굽힘: R 을 감거나 다이 R 을 지나며 굽혔다 펴지는 동안 장력이 걸려 있으면 판이 얇아진다
    (인장 아래 굽힘 · bending under tension). 강소성 평면 변형 모델에서 굽힘 한 번 (평판 → 반지름 ρ, 또는
    그 반대) 마다 중립면이 안쪽으로 a = (T/Ty)·t/2 옮겨 가 가운데 면이 a/ρ 만큼 늘어난다:
        Δε1 = −Δε_t = (T/Ty) · t / (2ρ)            (Marciniak·Duncan·Hu, Mechanics of Sheet Metal Forming,
                                                    "bending and unbending under tension")
    다이 R 을 지나 벽이 되는 재료는 굽힘 + 펴짐 = 2 번, 펀치 R 처럼 감긴 채 남는 곳은 1 번.
 2) 장력의 역사: 펀치 R 근처는 행정 내내 드로잉 장력을 버틴다. 장력이 그 자리의 항복 장력보다 크면
    평면 변형으로 더 늘어나 장력 = σ1(ε)·t(ε) 가 될 때까지 가고, 벽이 버틸 수 있는 가장 큰 장력 (평면 변형
    최대 하중) 을 넘으면 터진다 — 한계 드로잉비 (LDR) 에서 컵 바닥 R 이 터지는 까닭.
드로잉 장력 (폭 1 mm 당) 은 Siebel 식 T = t · 1.1 · k_f · ln(R/r) / η_F 를 행정마다 (플랜지 바깥 R(s) 이 줄며)
구한다 — diecalc.siebel_force · formsim.load_stroke 와 같은 식. 이 식의 최대 장력 / 벽 강도는 β = LDR 근처에서
1 이 된다 (SPCC 0.95, 시험 test_drawcorr). 끝으로 다이 틈새보다 두꺼워진 벽은 틈새로 훑인다 (아이어닝).
"""
from __future__ import annotations

import math

import numpy as np

ETA_F = 0.65          # Siebel 변형 효율 (diecalc.siebel_force 와 같음)
STEEP = 0.5           # |n·z| 가 이보다 작으면 벽 (60° 넘게 선 면)
FLAT = math.cos(math.radians(10))    # 펀치 면에 닿는 바닥
RHO_MIN = 1.0         # 감기는 반지름 하한 (× t) — 메시 꺾임에서 튀지 않게
MAX_BEND = 0.5        # 굽힘 몫 Δε 상한 (ρ = t 에서 t/2ρ)


def _hill(r):
    k = (1 + r) ** 2 / (1 + 2 * r)
    b = 2 * r / (1 + r)
    return k, b


def eq_strain(e1, e2, r):
    """Hill (1948) 수직 이방성 등가 변형률 (forming.plastic_work 와 같은 식)."""
    k, b = _hill(r)
    return np.sqrt(np.maximum(k * (e1 ** 2 + e2 ** 2 + b * e1 * e2), 0.0))


def stress_ratio(e1, e2, r):
    """변형률 비 α = ε2/ε1 에서 σ1 / σ̄ (Hill 수직 이방성, 흐름 법칙). 평면 변형 = (1+r)/√(1+2r)."""
    c = r / (1 + r)
    a = np.where(np.abs(e1) > 1e-9, e2 / np.where(np.abs(e1) > 1e-9, e1, 1.0), 0.0)
    bs = (a + c) / (1 + c * a)
    return 1 / np.sqrt(np.maximum(1 + bs ** 2 - 2 * c * bs, 1e-9))


def bend_thinning(t_over_ty, t, rho, events=1):
    """인장 아래 굽힘의 가운데 면 늘어남 (= 두께 진변형률 감소) Δε1 = events · (T/Ty) · t / (2ρ)."""
    return events * np.clip(t_over_ty, 0.0, 1.0) * t / (2 * np.maximum(rho, 1e-9))


def wall_capacity(mat, t):
    """평면 변형 벽이 버틸 수 있는 가장 큰 장력 [N/mm] 과 그때의 ε1: max σ1(ε1) · t · e^(−ε1) (Swift 경화)."""
    from . import diecalc as dc
    hp = dc._hill_ps(mat.r)
    e1 = np.linspace(0.0, 1.0, 4001)
    T = hp * np.array([dc.flow_stress(mat, e / hp) for e in e1]) * t * np.exp(-e1)
    i = int(np.argmax(T))
    return float(T[i]), float(e1[i])


def draw_tension(mat, t, a_rem, a_open, a_blank, stroke, r_die):
    """플랜지가 a_rem 만큼 남았을 때 다이 입구의 드로잉 장력 [N/mm] (같은 넓이의 원으로 본 Siebel 식).
    펀치 R · 다이 R 을 감는 첫 행정 (r_die + 3t) 동안은 비례로 오른다 (formsim.load_stroke 와 같음)."""
    from . import diecalc as dc
    a_rem = np.maximum(a_rem, 0.0)
    ln_b = 0.5 * np.log1p(a_rem / a_open)                      # ln(R(s) / r)
    ln_0 = 0.5 * math.log(max(a_blank / a_open, 1.0))           # ln(R0 / r)
    flange = np.maximum(ln_0 - ln_b, 0.0)                       # 플랜지 끝의 둘레 줄어듦 (경화)
    kf = np.array([dc.flow_stress(mat, 0.5 * f) for f in np.atleast_1d(flange)])
    rise = np.minimum(np.asarray(stroke, float) / max(r_die + 3 * t, 1e-6), 1.0)
    return t * 1.1 * kf * ln_b / ETA_F * rise


def _curvature_along(V, F, N, D1):
    """삼각형마다 방향 D1 (3D 단위 벡터) 을 따른 법곡률 |κ| (꼭짓점 법선의 차이로 구한 모양 연산자)."""
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    ea = p1 - p0
    ea /= np.maximum(np.linalg.norm(ea, axis=1), 1e-30)[:, None]
    n = np.cross(p1 - p0, p2 - p0)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    eb = np.cross(n, ea)
    E = np.stack([ea, eb], axis=2)                                  # (m,3,2)
    X = np.stack([p1 - p0, p2 - p0], axis=2)                       # (m,3,2)
    Xl = np.transpose(E, (0, 2, 1)) @ X                             # (m,2,2)
    dN = np.stack([N[F[:, 1]] - N[F[:, 0]], N[F[:, 2]] - N[F[:, 0]]], axis=2)
    det = Xl[:, 0, 0] * Xl[:, 1, 1] - Xl[:, 0, 1] * Xl[:, 1, 0]
    ok = np.abs(det) > 1e-12
    inv = np.zeros_like(Xl)
    inv[ok, 0, 0], inv[ok, 1, 1] = Xl[ok, 1, 1] / det[ok], Xl[ok, 0, 0] / det[ok]
    inv[ok, 0, 1], inv[ok, 1, 0] = -Xl[ok, 0, 1] / det[ok], -Xl[ok, 1, 0] / det[ok]
    S = np.transpose(E, (0, 2, 1)) @ dN @ inv
    S = 0.5 * (S + np.transpose(S, (0, 2, 1)))
    d = np.einsum("mij,mi->mj", E, D1)                              # D1 의 국부 좌표
    d /= np.maximum(np.linalg.norm(d, axis=1), 1e-30)[:, None]
    return np.abs(np.einsum("mi,mij,mj->m", d, S, d))


def _major_dirs(V, F, U):
    """삼각형마다 주 변형률 ε1 방향 (제품 위 3D 단위 벡터)."""
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    ea = p1 - p0
    ea /= np.maximum(np.linalg.norm(ea, axis=1), 1e-30)[:, None]
    n = np.cross(p1 - p0, p2 - p0)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]
    eb = np.cross(n, ea)
    E = np.stack([ea, eb], axis=2)
    Q = np.transpose(E, (0, 2, 1)) @ np.stack([p1 - p0, p2 - p0], axis=2)
    P = U[F]
    D = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]], axis=2)
    Fd = Q @ np.linalg.inv(D)
    Uu, _, _ = np.linalg.svd(Fd)
    return np.einsum("mij,mj->mi", E, Uu[:, :, 0])


def correct(V, F, U, major, minor, t, mat, die_r=None, N=None):
    """(보정한 major, minor, 설명 dict). 프레스 방향이 뚜렷하지 않거나 깊이 3 t 미만이면 그대로.
    N: 꼭짓점의 CAD 곡면 법선 (없으면 메시 법선 — 면 경계에서 곡률이 뭉개진다)."""
    from . import diecalc as dc
    from .forming import boundary_loops, vertex_normals

    major = np.asarray(major, float).copy()
    minor = np.asarray(minor, float).copy()
    info = dict(applied=False)
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    A3 = 0.5 * np.linalg.norm(nrm, axis=1)
    nrm /= np.maximum(2 * A3, 1e-30)[:, None]
    P = U[F]
    A2 = 0.5 * np.abs((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
                      - (P[:, 1, 1] - P[:, 0, 1]) * (P[:, 2, 0] - P[:, 0, 0]))
    zs = (A3[:, None] * nrm).sum(0)
    if np.linalg.norm(zs) < 0.08 * A3.sum():
        info["why"] = "프레스 방향이 뚜렷하지 않음"
        return major, minor, info
    z = zs / np.linalg.norm(zs)
    loops = boundary_loops(F)
    if not loops:
        info["why"] = "가장자리 없음"
        return major, minor, info

    def length(X, lp):
        Q = X[lp]
        return float(np.linalg.norm(Q - np.roll(Q, -1, axis=0), axis=1).sum())
    outer = max(loops, key=lambda lp: length(V, lp))
    h = V @ z
    if h[outer].mean() < h.mean():                  # 다이 면 (트림선·플랜지) 이 위로
        z, h = -z, -h
    hc = h[F].mean(1)
    h_top, h_min = float(h[outer].max()), float(h.min())
    depth = h_top - h_min
    if depth < 3 * t:
        info["why"] = f"얕음 (깊이 {depth:.1f} mm < 3 t)"
        return major, minor, info
    cz = np.abs(nrm @ z)
    m_ratio = length(V, outer) / max(length(U, outer), 1e-9)
    drawn = m_ratio < 0.97
    a_blank = float(A2.sum())

    e1, e2 = major, minor
    r = max(mat.r, 0.1)
    hp = dc._hill_ps(r)
    eq = eq_strain(e1, e2, r)
    te = t * np.exp(-(e1 + e2))
    sig = np.array([dc.flow_stress(mat, float(x)) for x in eq])
    Ty = hp * sig * te                                # 그 자리의 평면 변형 항복 장력 [N/mm]

    # 주 변형률 방향의 곡률 → 감긴 반지름 (가운데 면)
    Nm = vertex_normals(V, F)
    D1 = _major_dirs(V, F, U)
    kap = _curvature_along(V, F, Nm, D1)
    if N is not None and len(N) == len(V) and np.all(np.isfinite(N)):
        # CAD 법선은 면마다 방향이 뒤집혀 저장되기도 하고 (B-스플라인 판·후드), 날카로운 모서리의 꼭짓점은
        # 한쪽 면의 법선만 가진다: 메시 법선 쪽으로 맞추고, 세 꼭짓점이 모두 삼각형 면과 30° 안일 때만 쓴다
        N = N * np.where(np.einsum("ij,ij->i", N, Nm) < 0, -1.0, 1.0)[:, None]
        ok = np.min(np.einsum("mkj,mj->mk", N[F], nrm), axis=1) > math.cos(math.radians(30))
        kap = np.where(ok, _curvature_along(V, F, N, D1), kap)
    rho = np.maximum(1 / np.maximum(kap, 1e-9), RHO_MIN * t)

    d_eq = np.zeros(len(F))
    d_wrap = np.zeros(len(F))
    d_die = np.zeros(len(F))
    d_iron = np.zeros(len(F))
    necked = np.zeros(len(F), bool)
    # 장력이 없는 곳 (늘어나지 않는 곳) 은 굽혀도 얇아지지 않는다: 늘어나는 (항복한) 곳만 흐름 법칙의 σ1/σ̄
    # 원스텝의 잔 변형 (1 % 안팎, 메시 흔들림) 을 장력으로 보지 않게 ε1 1 → 3 % 에서 0 → 1 로 올린다
    ramp = np.clip((e1 - 0.01) / 0.02, 0.0, 1.0)
    local = np.where((eq > 0.002) & (e1 > 0), stress_ratio(e1, e2, r) / hp * ramp, 0.0)
    t_ratio = local.copy()
    r_die = None
    if drawn:
        cav = (hc < h_top - 0.5 * t) | (cz < STEEP)      # 다이 면 아래 (선 벽은 맨 위 줄까지)
        a_open = float(abs((A3[cav] * (nrm[cav] @ z)).sum()))
        if a_open <= 0.05 * a_blank:
            drawn = False
    if drawn:
        r_eq, R0 = math.sqrt(a_open / math.pi), math.sqrt(a_blank / math.pi)
        r_die = float(die_r) if die_r else dc.die_radius(2 * R0, 2 * r_eq, t)
        rho_d = r_die + t / 2
        order = np.argsort(hc)
        below = np.empty(len(F))
        below[order] = np.cumsum(A2[order]) - 0.5 * A2[order]       # 이 삼각형보다 아래 (먼저 들어간) 블랭크 넓이
        stroke = np.maximum(hc - h_min, 0.0)
        passed = (below > a_open) & cav                             # 다이 R 을 지나 들어온 재료
        # 행정마다 장력 (남은 플랜지 넓이로) — 지난 뒤로 겪는 가장 큰 장력 = 그 뒤 행정의 최대
        grid = np.linspace(0.0, 1.0, 121)
        a_in = a_open + grid * max(a_blank - a_open, 0.0)               # 다이 안으로 들어간 블랭크 넓이
        s_grid = np.interp(a_in, below[order], stroke[order], left=0.0, right=float(stroke.max()))
        T_grid = draw_tension(mat, t, a_blank - a_in, a_open, a_blank, s_grid, r_die)
        T_after = np.maximum.accumulate(T_grid[::-1])[::-1]
        T_peak = float(T_grid.max())
        T_cap, e_cap = wall_capacity(mat, t)
        frac = np.clip((below - a_open) / max(a_blank - a_open, 1e-9), 0.0, 1.0)
        T_pass = np.interp(frac, grid, T_grid)
        T_carry = np.where(passed, np.interp(frac, grid, T_after), T_peak)
        load = cav & (passed | (cz < FLAT))               # 장력이 지나가는 길 (펀치 바닥 면은 마찰로 잡힘)
        t_ratio = np.where(load, T_carry / np.maximum(Ty, 1e-9), local)
        # 장력 평형: 항복 장력보다 큰 장력이 걸리면 평면 변형으로 더 늘어난다
        for i in np.nonzero(load & (T_carry > Ty))[0]:
            Tc = T_carry[i]
            de = np.linspace(0.0, 0.6, 601)
            g = hp * np.array([dc.flow_stress(mat, eq[i] + x / hp) for x in de]) * te[i] * np.exp(-de)
            j = int(np.argmax(g))
            if Tc >= g[j]:
                necked[i] = True
                d_eq[i] = de[j]
            else:
                d_eq[i] = float(np.interp(Tc, g[:j + 1], de[:j + 1]))
        d_die = np.where(passed, bend_thinning(T_pass / np.maximum(Ty, 1e-9), te, rho_d, events=2), 0.0)
        info.update(T_peak=T_peak, T_cap=T_cap, e_cap=e_cap, util=T_peak / max(T_cap, 1e-9), r_die=r_die,
                    passed=float(A3[passed].sum() / A3.sum()), beta=math.sqrt(a_blank / a_open))
    d_wrap = bend_thinning(t_ratio, te, rho, events=1)
    d_wrap[rho > 200 * t] = 0.0
    # 한 삼각형에 더하는 굽힘 몫의 상한: 강소성 식은 ρ → t 에서 t/2ρ = 0.5 (그보다 작은 R 은 굽힘 균열 판정 몫)
    d_wrap = np.minimum(d_wrap, MAX_BEND)
    d_die = np.minimum(d_die, MAX_BEND)
    total = d_eq + d_wrap + d_die
    major = major + total
    if drawn:
        gap = dc.draw_gap(t, info["beta"], mat)[0]
        wall = passed & (cz < STEEP)
        t_new = t * np.exp(-(major + minor))
        d_iron = np.where(wall & (t_new > gap), np.log(np.maximum(t_new, 1e-9) / gap), 0.0)
        major = major + d_iron
        info.update(gap=gap, ironed=float(A3[d_iron > 0].sum() / A3.sum()))
    # 터짐 (벽 강도를 넘는 장력): 그 자리 FLC 를 넘긴 것으로 — 평면 변형 최대 하중 뒤는 국부 넥킹
    if necked.any():
        from .forming import flc_limit, keeler_flc0
        lim = flc_limit(minor, mat.flc0_for(t) if hasattr(mat, "flc0_for") else keeler_flc0(t, mat.n), mat.code)
        major = np.where(necked, np.maximum(major, 1.001 * lim), major)
    info.update(applied=True, drawn=drawn, depth=depth, d_eq=d_eq, d_wrap=d_wrap, d_die=d_die, d_iron=d_iron,
                necked=float(A3[necked].sum() / A3.sum()), rho=rho, area=A3)
    return major, minor, info


def summary(info, t):
    """보정 설명 한 줄 (해석 메시지·보고서)."""
    if not info or not info.get("applied"):
        return ""
    parts = []
    if info.get("drawn"):
        parts.append(f"드로잉 장력 최대 {info['T_peak']:.0f} N/mm = 벽 강도의 {info['util']:.0%} "
                     f"(Siebel, β {info['beta']:.2f})")
        parts.append(f"다이 R {info['r_die']:.1f} 굽힘-펴짐")
    a = info.get("area")

    def top(x):
        """넓이 기준 위 0.5 % 를 뺀 가장 큰 값 (메시 조각·CAD 의 작은 주름 하나가 요약을 흔들지 않게)."""
        if a is None or not x.size:
            return float(x.max()) if x.size else 0.0
        o = np.argsort(x)
        cw = np.cumsum(a[o]) / a.sum()
        return float(x[o][min(np.searchsorted(cw, 0.995), len(x) - 1)])
    w = top(info["d_wrap"])
    if w > 0.005:
        parts.append(f"R 감김 (인장 아래 굽힘) 최대 +{w:.1%} 얇아짐")
    if info.get("drawn") and top(info["d_die"]) > 0.005:
        parts.append(f"다이 R 지남 최대 +{top(info['d_die']):.1%}")
    if info.get("drawn") and info.get("ironed", 0) > 0.001:
        parts.append(f"틈새 {info['gap']:.2f} mm 아이어닝 {info['ironed']:.0%}")
    if info.get("necked", 0) > 0:
        parts.append(f"벽 강도 넘음 (터짐) {info['necked']:.1%}")
    if not parts:
        return ""
    return "드로잉 보정 (원스텝 + 인장 굽힘·장력 평형, Marciniak·Siebel): " + " · ".join(parts)
