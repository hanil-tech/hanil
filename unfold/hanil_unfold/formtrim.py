"""트림선 전개 (AutoForm Trim 비슷하게): 트림 뒤 꺾어 세우는 플랜지를 드로잉 형면 위로 펼쳐 OP20 트림선을 구한다.

1. 플랜지 (formops.flange_mask) 를 떼어 낸 드로잉 모양의 가장자리 (플랜지 뿌리) 꼭짓점마다,
   원스텝 블랭크 (U) 에서 그 점부터 플랜지 끝 (제품 가장자리) 까지 거리 = 펼친 플랜지 길이 L
   (원스텝이 플랜지의 늘림·줄임을 이미 셈 — 3D 가운데 면 길이도 같이 보임).
2. 그 점에서 드로잉 형면의 접평면으로 바깥으로 (가장자리에 수직) L 만큼 = 트림선 점 (어덴덤을 플랜지 길이만큼
   접선으로 늘리는 설계 관례). 플랜지 뿌리는 삼각형 단위라 호 길이 2 mm 로 다시 나누고 가우스 (σ 8 mm, 줄어듦 보정) 로
   고른다. 다이 페이스가 있으면 펼친 트림선이 자동 어덴덤 면에서 얼마나 뜨는지 알려 준다.
3. 트림 각: 트림선 자리의 면이 프레스 방향에 수직인 면과 이루는 각 — 15° 안 위에서 바로 (수직 트림),
   15 ~ 30° 주의 (트림 날을 비스듬히·전단각), 30° 넘으면 캠 트림.
플랜지가 없는 곳은 제품 가장자리가 그대로 트림선.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SLOPE_WARN, SLOPE_CAM = 15.0, 30.0


@dataclass
class TrimLine:
    loops3d: list                      # [(n, 3)] 드로잉 형면 위 트림선 고리
    loops2d: list                      # [(n, 2)] 프레스 방향으로 내려다본 평면 (트림 날 윤곽)
    flange_len: list                   # 고리마다 (n,) 펼친 플랜지 길이 (0 = 플랜지 없음)
    flange_len3d: list                 # 고리마다 (n,) 3D 가운데 면 플랜지 길이 (견줌)
    slope: list                        # 고리마다 (n,) 트림 각 °
    z: np.ndarray
    basis: tuple                       # (e1, e2) 평면 좌표축
    on_die: bool = False               # 다이 페이스 위로 걸었나
    notes: list = field(default_factory=list)
    bend: list = field(default_factory=list)     # 고리마다 (n,) 플랜지 꺾는 각 ° (플랜지 없음 = nan)
    comp: list = field(default_factory=list)     # 고리마다 (n,) 스프링백 보정 각 ° (금형에서 더 꺾을 각)
    r_in: float = 0.0                            # 보정 계산에 쓴 플랜지 안쪽 R

    @property
    def length(self):
        return sum(float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).sum()) for P in self.loops3d)

    def _seg_weights(self, i):
        P = self.loops3d[i]
        return 0.5 * (np.linalg.norm(P - np.roll(P, 1, axis=0), axis=1) + np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1))

    def frac(self, lo, hi=1e9):
        num = den = 0.0
        for i, s in enumerate(self.slope):
            w = self._seg_weights(i)
            num += float(w[(s > lo) & (s <= hi)].sum())
            den += float(w.sum())
        return num / max(den, 1e-12)

    def summary(self):
        Ls = np.concatenate(self.flange_len) if self.flange_len else np.zeros(0)
        L3 = np.concatenate(self.flange_len3d) if self.flange_len3d else np.zeros(0)
        on = Ls > 0
        lines = [f"트림선 {self.length:,.0f} mm ({len(self.loops3d)} 고리)"
                 + (" — 플랜지를 드로잉 형면 접평면으로 펼침" if any(np.any(x > 0) for x in self.flange_len) else "")]
        if on.any():
            lines.append(f"펼친 플랜지 길이 평균 {Ls[on].mean():.1f} · 최대 {Ls[on].max():.1f} mm "
                         f"(3D 가운데 면 {L3[on].mean():.1f} mm — 원스텝 블랭크 기준)")
        B = np.concatenate(self.bend) if self.bend else np.zeros(0)
        C = np.concatenate(self.comp) if self.comp else np.zeros(0)
        okb = np.isfinite(B) & (B > 5)
        if okb.any():
            okc = okb & np.isfinite(C)
            lines.append(f"플랜지 꺾는 각 평균 {np.nanmean(B[okb]):.0f}° (범위 {np.nanmin(B[okb]):.0f}~{np.nanmax(B[okb]):.0f}°)"
                         + (f" · 스프링백 보정 (안쪽 R {self.r_in:g}) +{np.nanmean(C[okc]):.1f}° "
                            f"(최대 +{np.nanmax(C[okc]):.1f}°) 더 꺾음" if okc.any() else ""))
        lines.append(f"트림 각: 15° 안 {self.frac(-1, SLOPE_WARN):.0%} · 15~30° {self.frac(SLOPE_WARN, SLOPE_CAM):.0%} · "
                     f"30° 넘음 (캠 트림) {self.frac(SLOPE_CAM):.0%}")
        return lines + self.notes

    @property
    def cam_frac(self):
        return self.frac(SLOPE_CAM)


def _basis(z):
    a = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = a - (a @ z) * z
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(z, e1)


def _tri_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]


def _vertex_tris(F, nv):
    vt = [[] for _ in range(nv)]
    for ti, tri in enumerate(F):
        for k in tri:
            vt[int(k)].append(ti)
    return vt


def _seg_dist(P, A, B):
    """점들 P (n, d) 에서 선분들 (A, B) (m, d) 까지 가장 짧은 거리 (n,)."""
    out = np.full(len(P), np.inf)
    ab = B - A
    L2 = np.maximum((ab * ab).sum(1), 1e-30)
    for i0 in range(0, len(P), 512):
        Q = P[i0:i0 + 512][:, None, :]
        u = np.clip(((Q - A[None]) * ab[None]).sum(2) / L2[None], 0, 1)
        d = np.linalg.norm(A[None] + u[..., None] * ab[None] - Q, axis=2)
        out[i0:i0 + 512] = d.min(1)
    return out


def develop(V, F, U, fmask, z, df=None, t=None, mat=None, r_in=None) -> TrimLine:
    """제품 메시 (V, F, 블랭크 U) 와 플랜지 삼각형 표시 fmask, 프레스 방향 z (트림선 쪽 +) 로 트림선.
    df: 드로잉 모양의 다이 페이스 (dieface.DieFace) — 있으면 그 면 위로 펼침."""
    from scipy.spatial import cKDTree

    from .forming import boundary_loops
    z = np.asarray(z, float) / np.linalg.norm(z)
    e1, e2 = _basis(z)
    fmask = np.asarray(fmask, bool) if fmask is not None and len(fmask) == len(F) else np.zeros(len(F), bool)
    loops = boundary_loops(F)
    if not loops:
        raise ValueError("제품 가장자리가 없습니다")
    outer = max(loops, key=lambda lp: float(np.linalg.norm(np.roll(V[lp], -1, axis=0) - V[lp], axis=1).sum()))
    nv = len(V)
    vt = _vertex_tris(F, nv)
    nrm = _tri_normals(V, F)
    keep = ~fmask
    on_die = False
    notes = []
    # 플랜지 끝 (제품 가장자리 중 플랜지에 속한 선분) — U 에서
    fl_v = np.zeros(nv, bool)
    fl_v[np.unique(F[fmask])] = True
    ring = np.asarray(outer)
    seg_a, seg_b = ring, np.roll(ring, -1)
    free = fl_v[seg_a] & fl_v[seg_b]
    A2, B2 = U[seg_a[free]], U[seg_b[free]]
    A3, B3 = V[seg_a[free]], V[seg_b[free]]
    # 드로잉 모양 가장자리 (플랜지를 떼면 생기는 고리, 플랜지 없으면 제품 가장자리 그대로)
    if keep.any() and fmask.any():
        # 플랜지를 뗀 드로잉 모양 (한 점에서만 맞닿는 꼭짓점을 정리한 것) 의 가장자리를 원래 꼭짓점 번호로
        from .formops import _draw_shape
        dsh = _draw_shape(V, F, fmask)
        if dsh is not None:
            V2, F2 = dsh
            idx = cKDTree(V).query(V2)[1]
            keep = np.zeros(len(F), bool)
            fset = {tuple(sorted(tri)) for tri in idx[F2]}
            keep = np.array([tuple(sorted(tri)) in fset for tri in F])
            dloops = [list(idx[np.asarray(lp)]) for lp in boundary_loops(F2)]
        else:
            dloops = boundary_loops(F[keep])
    else:
        dloops = [outer]
    dloops = [lp for lp in dloops if len(lp) >= 8]
    if fmask.any() and dloops:
        # 가장 긴 고리 (드로잉 모양 바깥) 와, 그 30 % 넘는 긴 고리 중 플랜지에 닿는 것만 (작은 구멍·조각 빼고)
        def _len(lp):
            Q = V[np.asarray(lp)]
            return float(np.linalg.norm(np.roll(Q, -1, axis=0) - Q, axis=1).sum())
        Lmax = max(_len(lp) for lp in dloops)
        dloops = [lp for lp in dloops if _len(lp) >= 0.999 * Lmax
                  or (_len(lp) > 0.3 * Lmax and fl_v[np.asarray(lp)].mean() > 0.2)]
    tri_tree = None
    if df is not None and getattr(df, "V", None) is not None:
        DV, DF = df.V, df.F
        cen = DV[DF].mean(1)
        tri_tree = cKDTree(cen)
        dn = _tri_normals(DV, DF)
        on_die = True
    out3, out2, outL, outL3, outS, bends, comps = [], [], [], [], [], [], []
    # 플랜지 삼각형 (가운데 · 법선) — 꺾는 각
    fl_tree = None
    if fmask.any():
        fl_c = V[F[fmask]].mean(1)
        fl_n = nrm[fmask]
        fl_tree = cKDTree(fl_c)
    t_ = float(t) if t else 1.0
    r_in = float(r_in) if r_in else max(2 * t_, 3.0)
    for lp in dloops:
        lp = np.asarray(lp)
        P = V[lp].copy()
        n = len(lp)
        # 꼭짓점 법선 (드로잉 쪽 삼각형) · 바깥 방향 (가장자리에 수직, 면을 따라)
        Nv = np.zeros((n, 3))
        cin = np.zeros((n, 3))
        for i, k in enumerate(lp):
            ts = [ti for ti in vt[int(k)] if keep[ti]] or vt[int(k)]
            Nv[i] = nrm[ts].sum(0)
            cin[i] = V[F[ts]].mean((0, 1))
        Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-30)[:, None]
        # 펼친 플랜지 길이 (원래 꼭짓점에서)
        root = fl_v[lp]
        L = np.zeros(n)
        L3 = np.zeros(n)
        if root.any() and len(A2):
            L[root] = _seg_dist(U[lp[root]], A2, B2)
            L3[root] = _seg_dist(V[lp[root]], A3, B3)
        if root.any():
            # 플랜지 뿌리는 삼각형 단위라 계단 (지그재그) — 호 길이 2 mm 로 다시 나누고 가우스로 고른 뿌리선에서 시작,
            # 플랜지 길이·법선도 그 선을 따라 고름
            P, idx = _gauss_loop(P, sigma=GAUSS_MM)
            n = len(P)
            ds_ = GAUSS_MM / max(float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).mean()), 1e-9)
            step_mm = float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).mean())
            rr = root[idx]
            L = _gsmooth(_fill_gaps(L[idx], rr, int(GAP_MM / max(step_mm, 1e-9))), ds_)
            L3 = _gsmooth(_fill_gaps(L3[idx], rr, int(GAP_MM / max(step_mm, 1e-9))), ds_)
            Nv = _gsmooth(Nv[idx], ds_)
            Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-30)[:, None]
            cin = cin[idx]
            root = _fill_gaps(rr.astype(float), rr, int(GAP_MM / max(step_mm, 1e-9))) > 0.5
        T = np.roll(P, -2, axis=0) - np.roll(P, 2, axis=0)
        d = np.cross(T, Nv)
        d -= (d * Nv).sum(1)[:, None] * Nv
        d /= np.maximum(np.linalg.norm(d, axis=1), 1e-30)[:, None]
        sgn = np.sign(((P - cin) * d).sum(1))
        sgn[sgn == 0] = 1
        d *= sgn[:, None]
        # 플랜지 뿌리의 형면 접평면으로 곧게 펼침 (어덴덤을 플랜지 길이만큼 접선으로 늘리는 설계 관례) —
        # 자동 어덴덤 (선 벽 + 다이 R) 위로 걸으면 삼각형 단위 뿌리선 때문에 트림선이 튐
        Q = P + d * L[:, None]
        # 트림 날 윤곽 (평면) 이 고르게 — 형면에 다시 붙이면 선 벽에서 평면 위치가 흔들려 붙이지 않음 (면에서 벗어남 ≪ 1 mm)
        if root.any():
            Q = _gsmooth(Q, GAUSS_MM / max(float(np.linalg.norm(np.roll(Q, -1, axis=0) - Q, axis=1).mean()), 1e-9))
        # 트림 각: 펼친 면 (뿌리 접평면) 의 기울기
        ns = Nv
        slope = np.degrees(np.arccos(np.clip(np.abs(ns @ z), 0, 1)))
        if root.any() and tri_tree is not None:
            # 자동 어덴덤이 뿌리에서 바로 꺾여 내려가면 (선 벽) 펼친 트림선이 그 벽 밖에 뜸 — 어덴덤을 접선으로 늘려야
            _, j = tri_tree.query(Q[root])
            off = np.abs(((Q[root] - cen[j]) * dn[j]).sum(1))
            if np.median(off) > 2.0:
                notes.append(f"펼친 트림선이 자동 어덴덤 면에서 {np.median(off):.0f} mm 뜸 — 어덴덤을 플랜지 길이 "
                             f"(최대 {L.max():.0f} mm + 5) 만큼 형면 접선으로 늘려 설계하세요")
        if not root.any() and (slope > SLOPE_CAM).mean() > 0.5:
            notes.append("트림선이 선 벽 위 (플랜지 없는 컵 위 끝 등) — 벽 트림: 캠 트림 또는 핀치 트림")
        # 플랜지 꺾는 각 (뿌리 면 ↔ 플랜지 끝 쪽 면) 과 스프링백 보정 (플랜지 굽힘, 모멘트 법)
        bend = np.full(n, np.nan)
        comp = np.full(n, np.nan)
        if root.any() and fl_tree is not None:
            for i in np.nonzero(root & (L > 2 * t_))[0]:
                js = fl_tree.query_ball_point(P[i], float(L[i]) + 1.0)
                if not js:
                    continue
                js = np.asarray(js)
                dd = np.linalg.norm(fl_c[js] - P[i], axis=1)
                far = js[dd >= 0.5 * L[i]]
                if not len(far):
                    continue
                nf = fl_n[far].sum(0)
                nf /= max(np.linalg.norm(nf), 1e-30)
                bend[i] = float(np.degrees(np.arccos(np.clip(nf @ Nv[i], -1, 1))))
            ok = np.isfinite(bend) & (bend > 5)
            if ok.any() and mat is not None:
                from . import diecalc as dc
                for b_ in np.unique(np.round(bend[ok])):
                    after, die_a, _ = dc.springback(mat, r_in, t_, float(b_))
                    m_ = ok & (np.round(bend) == b_)
                    comp[m_] = (die_a - b_) if np.isfinite(die_a) else np.nan
        bends.append(bend)
        comps.append(comp)
        out3.append(Q)
        out2.append(np.column_stack([Q @ e1, Q @ e2]))
        outL.append(L)
        outL3.append(L3)
        outS.append(slope)
    return TrimLine(out3, out2, outL, outL3, outS, z, (e1, e2), on_die, list(dict.fromkeys(notes)), bends, comps,
                    r_in if fmask.any() else 0.0)


GAUSS_MM = 8.0            # 트림선 고르기 (가우스 σ, mm) — 이보다 작은 귀 R 은 둥글어짐


def _gauss_loop(P, sigma=GAUSS_MM, ds=2.0):
    """닫힌 선을 호 길이 ds 로 다시 나누고 가우스 (σ mm) 로 고름. (새 점들, 새 점마다 가까운 원래 점 번호)."""
    P = np.asarray(P, float)
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = s[-1]
    if L < 4 * ds:
        return P, np.arange(len(P))
    m = max(int(L / ds), 16)
    u = np.linspace(0, L, m, endpoint=False)
    Pc = np.vstack([P, P[:1]])
    R = np.column_stack([np.interp(u, s, Pc[:, k]) for k in range(P.shape[1])])
    w = int(3 * sigma / (L / m)) + 1
    ker = np.exp(-0.5 * ((np.arange(-w, w + 1) * L / m) / sigma) ** 2)
    ker /= ker.sum()
    def g(X):
        Y = np.zeros_like(X)
        for k, c in zip(range(-w, w + 1), ker):
            Y += c * np.roll(X, k, axis=0)
        return Y
    G1 = g(R)
    Rs = 2 * G1 - g(G1)                              # 줄어듦 보정 (굽은 곳이 안쪽으로 당겨지는 것을 되돌림)
    near = np.searchsorted(s[:-1], u, side="right") - 1
    return Rs, np.clip(near, 0, len(P) - 1)


GAP_MM = 40.0             # 플랜지 뿌리 사이 이 길이보다 짧은 빈틈은 이어 붙임 (삼각형 단위 플랜지 경계)


def _fill_gaps(X, mask, max_gap):
    """닫힌 배열에서 mask 가 False 인 짧은 구간 (≤ max_gap 점, 양쪽이 True) 을 양 끝 값으로 선형 보간."""
    X = np.asarray(X, float).copy()
    n = len(X)
    if mask.all() or not mask.any():
        return X
    start = int(np.argmax(mask))                 # True 에서 시작해 돎
    i = 0
    while i < n:
        k = (start + i) % n
        if not mask[k]:
            j = i
            while j < n and not mask[(start + j) % n]:
                j += 1
            gap = j - i
            if gap <= max_gap:
                a, b = X[(start + i - 1) % n], X[(start + j) % n]
                for g in range(gap):
                    X[(start + i + g) % n] = a + (b - a) * (g + 1) / (gap + 1)
                    mask = mask.copy()
                    mask[(start + i + g) % n] = True
            i = j
        else:
            i += 1
    return X


def _gsmooth(X, sigma_pts):
    """고른 간격 닫힌 배열 (n,) 또는 (n, d) 의 가우스 고르기 (줄어듦 보정), σ 는 점 수."""
    X = np.asarray(X, float)
    w = int(3 * sigma_pts) + 1
    if w < 1 or len(X) < 3:
        return X
    w = min(w, len(X) // 2)
    ker = np.exp(-0.5 * (np.arange(-w, w + 1) / max(sigma_pts, 1e-9)) ** 2)
    ker /= ker.sum()

    def g(Y):
        Z = np.zeros_like(Y)
        for k, c in zip(range(-w, w + 1), ker):
            Z += c * np.roll(Y, k, axis=0)
        return Z
    G1 = g(X)
    return 2 * G1 - g(G1)


def save_dxf(tl: TrimLine, path, name=""):
    """트림선 DXF: TRIM_2D (프레스 방향으로 내려다본 트림 날 윤곽, 1:1), TRIM_3D (형면 위 3D 폴리선),
    CAM (트림 각 30° 넘는 구간), TEXT."""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for nm, col in (("TRIM_2D", 1), ("TRIM_3D", 5), ("CAM", 6), ("WARN", 2), ("TEXT", 7)):
        doc.layers.add(nm, color=col)
    doc.styles.add("KOR", font="malgun.ttf")
    msp = doc.modelspace()
    for P2, P3, S in zip(tl.loops2d, tl.loops3d, tl.slope):
        msp.add_lwpolyline([tuple(map(float, q)) for q in P2], close=True, dxfattribs={"layer": "TRIM_2D"})
        msp.add_polyline3d([tuple(map(float, q)) for q in P3], close=True, dxfattribs={"layer": "TRIM_3D"})
        n = len(P2)
        for lay, lo, hi in (("WARN", SLOPE_WARN, SLOPE_CAM), ("CAM", SLOPE_CAM, 1e9)):
            m = (S > lo) & (S <= hi)
            i = 0
            while i < n:
                if m[i]:
                    j = i
                    while j + 1 < n and m[j + 1]:
                        j += 1
                    pts = [tuple(map(float, P2[k])) for k in range(i, j + 1)]
                    if len(pts) >= 2:
                        msp.add_lwpolyline(pts, dxfattribs={"layer": lay, "lineweight": 50})
                    i = j + 1
                else:
                    i += 1
    allp = np.vstack(tl.loops2d)
    y = float(allp[:, 1].min()) - 10
    for k, ln in enumerate([f"트림선 전개 {name}"] + tl.summary()):
        msp.add_text(ln, height=3.0, dxfattribs={"layer": "TEXT", "style": "KOR"}).set_placement(
            (float(allp[:, 0].min()), y - 5 * k))
    doc.saveas(path)
    return path


def paint(p, rect, tl: TrimLine, title=True):
    """평면 (프레스 방향으로 내려다봄) 트림선 — 트림 각으로 색 (초록 15° 안 · 노랑 15~30° · 빨강 캠)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen
    allp = np.vstack(tl.loops2d)
    lo, hi = allp.min(0), allp.max(0)
    top = 26 if title else 0
    s = min((rect.width() - 20) / max(hi[0] - lo[0], 1e-9), (rect.height() - top - 20) / max(hi[1] - lo[1], 1e-9))
    cx = rect.x() + 10 + (rect.width() - 20 - (hi[0] - lo[0]) * s) / 2
    cy = rect.y() + top + 10 + (rect.height() - top - 20 + (hi[1] - lo[1]) * s) / 2

    def T(q):
        return QPointF(cx + (q[0] - lo[0]) * s, cy - (q[1] - lo[1]) * s)
    for P2, S in zip(tl.loops2d, tl.slope):
        n = len(P2)
        for i in range(n):
            a, b = P2[i], P2[(i + 1) % n]
            sl = max(S[i], S[(i + 1) % n])
            col = QColor(40, 160, 70) if sl <= SLOPE_WARN else QColor(230, 170, 30) if sl <= SLOPE_CAM else QColor(210, 40, 40)
            p.setPen(QPen(col, 2.2))
            p.drawLine(T(a), T(b))
    if title:
        p.setPen(QColor(20, 20, 20))
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), top), Qt.AlignLeft | Qt.AlignVCenter,
                   f"트림선 (평면) — 초록 15° 안 · 노랑 15~30° · 빨강 캠 트림 · 길이 {tl.length:,.0f} mm")


def render(tl: TrimLine, w=900, h=600, dpr=1.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import new_image
    img, p = new_image(w, h, dpr)
    paint(p, QRectF(0, 0, w, h), tl)
    p.end()
    return img
