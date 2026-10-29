"""다이 페이스 (드로잉 금형 면): 제품 + 어덴덤 + 바인더 를 자동으로 만들고 그 판 전체로 원스텝 해석.

제품 모양만으로 펼치면 (제품 원스텝) 트림선이 자유 가장자리가 되어, 실제로는 누르개 (바인더) 아래에서 끌려
들어오며 버티는 장력을 금형 저항 어림으로만 넣는다. 실제 드로잉 금형은 제품 트림선 바깥에 어덴덤 (제품과
바인더를 잇는 벽 · 다이 R) 과 평평한 바인더 면을 붙여, 블랭크가 바인더 위에 놓이고 펀치가 제품을 당긴다
(AutoForm·Dynaform 의 Die Face Design). 여기서는 그 면을 메시로 붙인다:

  트림선의 꼭짓점마다 바깥쪽 (프레스 방향에 수직인 평면에서 경계에 수직) 으로
    ① 어덴덤 벽: 바인더 높이까지 빼기 각 (프레스 방향에서 WALL_DEG) 으로 올라가고
    ② 다이 R: 반지름 r_d 로 눕고
    ③ 바인더: 폭 BINDER 만큼 평평하게.
  트림선이 이미 바인더 높이 (플랜지 끝) 이면 ③ 만.

그 위에서 원스텝 (소성 일 최소 + 금형 작용) — 이제 금형 저항은 바인더 바깥 끝 (진짜 끌려 들어오는 가장자리)
에 건다. 결과: 드로잉 블랭크 (바인더까지), 제품 부분의 변형 (트림 전), 끌려 들어감 (draw-in, 바인더 끝이
처음 놓인 자리에서 얼마나 들어왔나).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

WALL_DEG = 10.0       # 어덴덤 벽의 빼기 각 (프레스 방향에서)
BINDER = 25.0         # 바인더 폭 (mm): 원스텝의 바인더는 드로잉이 끝난 뒤 바인더 위에 남는 판 (트림 여유) —
                      # 넓게 잡으면 그만큼 남는 판이 끌려 들어오지 않고 버텨 벽이 지나치게 얇아진다
STEPS_WALL = 4        # 벽 높이 방향 칸 수 (최소)
STEPS_R = 4           # 다이 R 칸 수
SMOOTH = 20           # 바깥 방향 고르기 횟수 (들쭉날쭉한 트림선에서 고리가 엇갈리지 않게)
PRODUCT, ADDENDUM, BIND = 0, 1, 2
REGION_NAMES = ["제품", "어덴덤", "바인더"]
LAST_WHY = [""]        # build 가 None 을 돌려준 까닭
BINDER_TILT = 20.0     # 바인더 평면이 프레스 방향에서 기울어도 되는 각 (°)
MAX_FLIP = 0.1         # 바인더 띠의 뒤집힌 (겹친) 삼각형 비 한도 — 오목한 귀에서 조금 겹치는 것은 넘어감


@dataclass
class DieFace:
    V: np.ndarray
    F: np.ndarray
    region: np.ndarray          # 삼각형마다 0 제품 · 1 어덴덤 · 2 바인더
    z: np.ndarray               # 프레스 방향 (바인더가 + 쪽)
    h_binder: float
    r_die: float
    binder_w: float
    wall_deg: float
    n_product: int              # 앞쪽 n_product 개 삼각형이 제품
    notes: list = field(default_factory=list)
    U: np.ndarray | None = None
    major: np.ndarray | None = None
    minor: np.ndarray | None = None
    draw_in: np.ndarray | None = None     # 바인더 바깥 끝 꼭짓점마다 끌려 들어간 거리 (mm)
    outer: list = field(default_factory=list)   # 바인더 바깥 끝 꼭짓점 번호 (고리)
    correction: dict | None = None
    tilt: float = 0.0


def _press_dir(V, F):
    a = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]) * 0.5
    s = a.sum(0)
    if np.linalg.norm(s) < 0.08 * np.linalg.norm(a, axis=1).sum():
        return None
    return s / np.linalg.norm(s)


def _compact(V, F, region, outer):
    """가장 큰 이어진 덩어리만 남기고 안 쓰는 꼭짓점을 지운다 (삼각형 영역·바깥 고리 번호도 같이)."""
    n = len(V)
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in F:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    roots = np.array([find(a) for a in F[:, 0]])
    vals, counts = np.unique(roots, return_counts=True)
    sel = roots == vals[np.argmax(counts)]
    F, region = F[sel], region[sel]
    used = np.unique(F)
    remap = -np.ones(n, int)
    remap[used] = np.arange(len(used))
    outer = [int(remap[i]) for i in outer if remap[i] >= 0]
    # 제품 삼각형을 앞에 (n_product 개)
    order = np.argsort(region, kind="stable")
    return V[used], remap[F][order], region[order], outer


def split_long_boundary(V, F, factor=3.0, rounds=8):
    """경계 모서리 가운데 중앙값의 factor 배보다 긴 것을 반으로 (그 모서리를 가진 삼각형 하나를 둘로).
    CAD 메시의 바늘 삼각형이 경계에 긴 모서리를 남기면 바깥 고리가 엇갈린다."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    for _ in range(rounds):
        cnt = {}
        for ti, tri in enumerate(F):
            for k in range(3):
                a, b = int(tri[k]), int(tri[(k + 1) % 3])
                key = (min(a, b), max(a, b))
                cnt.setdefault(key, []).append((ti, k))
        bnd = [(key, v[0]) for key, v in cnt.items() if len(v) == 1]
        if not bnd:
            break
        L = np.array([np.linalg.norm(V[a] - V[b]) for (a, b), _ in bnd])
        lim = factor * float(np.median(L))
        long_ = [(bnd[i], L[i]) for i in np.nonzero(L > lim)[0]]
        if not long_:
            break
        newV = [V]
        nv = len(V)
        F = F.tolist()
        drop = set()
        add = []
        for ((a, b), (ti, k)), _ in long_:
            if ti in drop:
                continue
            tri = F[ti]
            A, B, C = tri[k], tri[(k + 1) % 3], tri[(k + 2) % 3]
            m = nv
            newV.append(((V[A] + V[B]) / 2)[None])
            nv += 1
            drop.add(ti)
            add += [[A, m, C], [m, B, C]]
        F = np.array([tri for i, tri in enumerate(F) if i not in drop] + add, int)
        V = np.vstack(newV)
    return V, F


def build(V, F, t, r_die=None, binder_w=BINDER, wall_deg=WALL_DEG):
    """제품 (두께 가운데 면) 메시 → DieFace (해석 전). 프레스 방향이 뚜렷하지 않으면 None."""
    from .forming import boundary_loops
    V, F = split_long_boundary(V, F)
    z = _press_dir(V, F)
    if z is None:
        return None
    loops = boundary_loops(F)
    if not loops:
        return None

    def length(lp):
        P = V[lp]
        return float(np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1).sum())
    outer = max(loops, key=length)
    h = V @ z
    if h[outer].mean() < h.mean():                       # 트림선 (다이 면) 쪽을 + 로
        z, h = -z, -h
    e1 = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(z, e1)
    P = V[outer]
    tz = np.roll(P, -1, axis=0) - P
    tl = np.linalg.norm(tz, axis=1)
    steep = np.abs(tz @ z) > 0.7 * np.maximum(tl, 1e-30)
    if tl[steep].sum() > 0.1 * tl.sum():
        LAST_WHY[0] = f"트림선의 {tl[steep].sum() / tl.sum():.0%} 가 벽을 따라 내려감"
        return None                                      # 트림선이 벽을 따라 내려감 (끝이 잘린 멤버) — 자동으로 못 만듦
    Q = np.column_stack([P @ e1, P @ e2])
    area2 = float(np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1]))
    tg = np.roll(Q, -1, axis=0) - np.roll(Q, 1, axis=0)
    out2 = np.column_stack([tg[:, 1], -tg[:, 0]]) * (1 if area2 > 0 else -1)   # 투영 다각형 바깥 법선
    for _ in range(SMOOTH):                              # 오목한 곳에서 고리가 엇갈리지 않게 고르기
        out2 = 0.5 * out2 + 0.25 * (np.roll(out2, 1, axis=0) + np.roll(out2, -1, axis=0))
    out2 /= np.maximum(np.linalg.norm(out2, axis=1), 1e-30)[:, None]
    out3 = out2[:, :1] * e1 + out2[:, 1:] * e2
    # 들쭉날쭉한 트림선 (메시 크기의 계단): 투영 위치를 고른 선을 따라 띠를 붙인다 (첫 고리가 그 선으로 옮겨 감)
    # Taubin (λ/μ) 고르기 — 계단만 지우고 볼록한 귀는 줄이지 않음 (단순 평균은 귀를 안으로 당겨 첫 고리가 제품 귀와 겹침)
    Qs = Q.copy()
    for _ in range(SMOOTH):
        for lam in (0.5, -0.53):
            Qs = Qs + lam * (0.5 * (np.roll(Qs, 1, axis=0) + np.roll(Qs, -1, axis=0)) - Qs)
    mv = Qs - Q
    inward = np.maximum(-np.einsum("ij,ij->i", mv, out2), 0.0)     # 안으로 옮긴 만큼은 첫 고리를 더 바깥에
    Ps = P + mv[:, :1] * e1 + mv[:, 1:] * e2 + (inward[:, None] * out2)[:, :1] * e1 + (inward[:, None] * out2)[:, 1:] * e2
    # 바인더 면: 트림선에 가장 잘 맞는 평면 (프레스 방향에서 BINDER_TILT 안으로 기울어도 됨 — 앞이 처진 후드처럼),
    # 트림선의 가장 높은 점을 지나게. 꼭짓점마다 프레스 방향으로 올라가야 할 높이 dh.
    c = P.mean(0)
    _, _, vh = np.linalg.svd(P - c)
    nb = vh[2] if vh[2] @ z > 0 else -vh[2]
    tilt = math.degrees(math.acos(min(1.0, abs(float(nb @ z)))))
    if tilt > BINDER_TILT:
        nb, tilt = z, 0.0
    hpl = P @ nb
    cb = P[int(np.argmax(hpl))]
    zn = float(z @ nb)
    hb = float(h[outer].max())
    rd = float(r_die) if r_die else max(5 * t, 3.0)
    tw = math.tan(math.radians(wall_deg))
    dh = np.maximum(((cb - P) @ nb) / zn, 0.0)
    seg = np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1)
    step = max(float(np.median(seg)), 0.5 * t)
    # 트림선에서 제품 면이 나가는 각 θ (바깥 수평 0, 위로 90°): 꼭짓점에 붙은 제품 삼각형의 가운데 → 그 꼭짓점 방향
    vt = {}
    for ti, tri in enumerate(F):
        for k in tri:
            vt.setdefault(int(k), []).append(ti)
    Cg = V[F].mean(1)
    theta = np.zeros(len(outer))
    for i, k in enumerate(outer):
        ts = vt.get(int(k), [])
        if ts:
            d = V[int(k)] - Cg[ts].mean(0)
            theta[i] = math.atan2(float(d @ z), max(float(d @ out3[i]), 1e-9))
    # 꼭짓점마다 단면 (바깥 s, 위 dz) 꺾은선:
    #  · 바인더가 위 (dh > t/2): 곧은 벽 (빼기 각) → 다이 R 자리 2차 베지어 → 바인더 높이
    #  · 제품 면이 위로 서서 끝남 (θ > 15°, 컵 위 끝처럼): 반지름 r_d 로 θ 에서 수평까지 눕힘 (다이 R)
    #  · 그 밖: 바로 바인더 (짧은 수평)
    M = 24
    profs = []
    for i in range(len(outer)):
        if dh[i] > 0.5 * t:
            r_ = min(rd, dh[i])
            wt = np.array([max(dh[i] - r_, 0.0) * tw, max(dh[i] - r_, 0.0)])
            co = np.array([dh[i] * tw, dh[i]])
            en = np.array([dh[i] * tw + r_, dh[i]])
            pts = [np.zeros(2)] + [wt * f for f in np.linspace(0, 1, M // 2)[1:]]
            pts += [(1 - u) ** 2 * wt + 2 * u * (1 - u) * co + u * u * en for u in np.linspace(0, 1, M // 2)[1:]]
        elif theta[i] > math.radians(15):
            th = min(theta[i], math.radians(100))
            ph = np.linspace(th, 0, M)
            pts = [np.array([rd * (math.sin(th) - math.sin(a)), rd * (math.cos(a) - math.cos(th))]) for a in ph]
        else:
            pts = [np.zeros(2), np.array([step, 0.0])]
        profs.append(np.array(pts))
    lens = [float(np.linalg.norm(np.diff(pr, axis=0), axis=1).sum()) for pr in profs]
    n_add = max(STEPS_WALL + STEPS_R, int(math.ceil(max(lens) / step)))
    n_bind = max(3, int(math.ceil(binder_w / step)))
    # 고리마다 같은 개수: 꼭짓점마다 자기 단면을 길이 비로 다시 나눔
    A = np.zeros((n_add, len(outer), 2))
    for i, pr in enumerate(profs):
        cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pr, axis=0), axis=1))])
        fr = np.linspace(0, cum[-1], n_add + 1)[1:]
        A[:, i, 0] = np.interp(fr, cum, pr[:, 0])
        A[:, i, 1] = np.interp(fr, cum, pr[:, 1])
    s_end, z_end = A[-1, :, 0], A[-1, :, 1]
    # 바인더 평면: 트림선에 맞춘 평면 (nb) 을 어덴덤 끝 높이가 가장 높은 쪽에 맞춰 올림
    rise = float(max(0.0, (z_end - dh).max()))
    cbp = cb + z * rise
    rings = []
    for k in range(n_add):
        rings.append((A[k, :, 0], A[k, :, 1], ADDENDUM))
    for k in range(1, n_bind + 1):
        rings.append((s_end + binder_w * k / n_bind, None, BIND))
    Vn = [V]
    ids = [np.asarray(outer, int)]
    nv = len(V)
    for (s_, dz, _) in rings:
        sv = np.asarray(s_, float)
        base = Ps + out3 * sv[:, None]
        target = ((cbp - base) @ nb) / zn                    # 이 자리에서 바인더 평면까지 높이
        if dz is None:
            dzf = target
        else:
            # 어덴덤 끝이 꼭 바인더 평면에 닿게 단면 높이를 늘이거나 (끝이 0 이면 길이 비로 올림)
            tend = ((cbp - (Ps + out3 * s_end[:, None])) @ nb) / zn
            f = np.where(z_end > 1e-6, tend / np.maximum(z_end, 1e-6), 0.0)
            ramp = np.where(s_end > 1e-9, sv / np.maximum(s_end, 1e-9), 1.0) * tend
            dzf = np.where(z_end > 1e-6, np.asarray(dz, float) * f, ramp)
        pts = base + z * dzf[:, None]
        Vn.append(pts)
        ids.append(nv + np.arange(len(outer)))
        nv += len(outer)
    dh = np.maximum(dh, z_end)
    Vc = np.vstack(Vn)
    # 고리 사이를 삼각형으로: 제품 경계의 방향 (제품 삼각형이 a→b 로 돌면 새 띠는 b→a)
    a, b = int(outer[0]), int(outer[1])
    same = False
    for tri in F:
        tl = list(tri)
        if a in tl and b in tl:
            i = tl.index(a)
            same = tl[(i + 1) % 3] == b
            break
    newF, reg = [], []
    m = len(outer)
    for k in range(len(rings)):
        r0, r1 = ids[k], ids[k + 1]
        rg = rings[k][2]
        for i in range(m):
            j = (i + 1) % m
            t1 = (r0[i], r0[j], r1[j])
            t2 = (r0[i], r1[j], r1[i])
            if same:
                t1, t2 = t1[::-1], t2[::-1]
            newF += [t1, t2]
            reg += [rg, rg]
    Fc = np.vstack([F, np.array(newF, int)])
    # 붙인 띠가 투영에서 뒤집히거나 (오목한 트림선에서 고리가 엇갈림) 넓이 0 이면 못 만든 것으로
    nf = np.array(newF, int)
    q = np.column_stack([Vc @ e1, Vc @ e2])
    sa = (q[nf[:, 1], 0] - q[nf[:, 0], 0]) * (q[nf[:, 2], 1] - q[nf[:, 0], 1]) - \
        (q[nf[:, 1], 1] - q[nf[:, 0], 1]) * (q[nf[:, 2], 0] - q[nf[:, 0], 0])
    bind_tri = np.array(reg) == BIND
    bad = (np.sign(sa[bind_tri]) != np.sign(np.median(sa[bind_tri]))).mean() if bind_tri.any() else 0.0
    if bad > MAX_FLIP:
        LAST_WHY[0] = f"바인더 띠의 {bad:.0%} 가 뒤집힘 (트림선이 들쭉날쭉하거나 많이 오목함)"
        return None
    region = np.concatenate([np.zeros(len(F), int), np.array(reg, int)])
    from .forming import _drop_degenerate
    keep = _drop_degenerate(Vc, Fc)
    if len(keep) != len(Fc):                             # 넓이 0 인 띠 삼각형 (겹친 고리) 은 뺌
        sel = np.zeros(len(Fc), bool)
        rows = {tuple(r) for r in keep.tolist()}
        sel = np.array([tuple(r) in rows for r in Fc.tolist()])
        Fc, region = Fc[sel], region[sel]
    Vc, Fc, region, outer_ids = _compact(Vc, Fc, region, ids[-1])
    df = DieFace(Vc, Fc, region, z, hb, rd, binder_w, wall_deg, int((region == PRODUCT).sum()))
    df.outer = list(outer_ids)
    df.tilt = tilt
    df.notes.append(f"다이 페이스: 트림선 바깥 어덴덤 벽 (빼기 {wall_deg:g}°, 높이 최대 {dh.max():.0f} mm) · 다이 R {rd:g} · "
                    f"바인더 폭 {binder_w:g} mm (트림선에 맞춘 평면, 프레스 방향에서 {tilt:.0f}° 기움, 트림선 가장 높은 곳을 지남)")
    return df


def solve(df: DieFace, t, mat, mu=0.1, seconds=8.0):
    """다이 페이스 위 원스텝. df.U · major · minor · draw_in 을 채운다."""
    from . import forming
    from .diecalc import HOLDER_P, _family
    V, F = df.V, df.F
    U = forming.lscm(V, F)
    U = forming.arap(V, F, U, 60)
    tools = dict(thickness=t, tensile=mat.tensile_mpa, mu=mu, p_bh=HOLDER_P[_family(mat.code)], die_r=df.r_die)
    try:
        U, it = forming.one_step(V, F, U, mat.n, mat.r, seconds=seconds, tools=tools)
        df.notes.append(f"원스텝 (다이 페이스, {len(F):,} 삼각형) {it} 번 반복")
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as e:
        df.notes.append(f"원스텝을 못 해 ARAP 결과를 씀 ({e})")
    df.U = U
    df.major, df.minor, _ = forming.strains(V, F, U)
    # 끌려 들어감: 바인더 바깥 끝이 처음 (평평한 블랭크 위, 제품 투영에 맞춘) 자리에서 안쪽으로 온 거리
    z = df.z
    e1 = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(z, e1)
    proj = np.column_stack([V @ e1, V @ e2])
    bind = np.unique(F[df.region == BIND])
    from .formprocess import _kabsch2
    Ua, _ = _kabsch2(np.asarray(U, float)[bind], proj[bind]) if len(bind) >= 3 else (U[bind], None)
    Uall, _ = _kabsch2(np.asarray(U, float), proj) if len(bind) < 3 else (None, None)
    if Uall is None:
        # 바인더 점들로 맞춘 같은 변환을 전체에 (바인더는 거의 늘지 않음 → 맞춤이 정확)
        A = np.asarray(U, float)[bind]
        R, c_u, c_p = _fit(A, proj[bind])
        Uall = (np.asarray(U, float) - c_u) @ R.T + c_p
    o = np.asarray(df.outer, int)
    df.draw_in = np.linalg.norm(Uall[o] - proj[o], axis=1)
    df.U = Uall
    # 원스텝 (막) 이 못 보는 인장 아래 굽힘·장력·아이어닝 (제품만 볼 때와 같은 보정, drawcorr)
    from . import drawcorr
    try:
        m2, n2, corr = drawcorr.correct(V, F, Uall, df.major, df.minor, t, mat)
        if corr.get("applied"):
            df.major, df.minor = m2, n2
            df.correction = corr
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        pass
    return df


def _fit(A, B):
    """A 를 B 에 맞추는 회전 (뒤집기 허용) · 두 무게 중심."""
    ca, cb = A.mean(0), B.mean(0)
    H = (A - ca).T @ (B - cb)
    u, _, vt = np.linalg.svd(H)
    R = (u @ vt).T
    return R, ca, cb


def as_result(df: DieFace, t, mat):
    """해석한 다이 페이스를 UnfoldResult (성형품) 로 — 성형 해석 (formsim.analyze) 을 그대로 쓰기 위해."""
    from .forming import boundary_loops, quality
    from .unfolder import FORMING, FormingInfo, Polyline, UnfoldResult, _tri_areas2, _tri_areas3
    V, F, U = df.V, df.F, df.U
    ratio = np.exp(df.major + df.minor)
    fi = FormingInfo(U=U, F=F, ratio=ratio, major=df.major, minor=df.minor,
                     product_area=float(_tri_areas3(V, F).sum()), blank_area=float(_tri_areas2(U, F).sum()),
                     reliable=quality(V, F) > 5.0, method="원스텝 (다이 페이스)", flc0=mat.flc0_for(t),
                     material=mat.code, V=V)
    fi.region = df.region
    fi.correction = df.correction
    ents = []
    for lp in boundary_loops(F):
        pts = [tuple(float(x) for x in U[i]) for i in lp]
        ents.append(Polyline(pts + [pts[0]]))
    return UnfoldResult(thickness=t, k_factor=0.5, entities=ents, bends=[], warnings=list(df.notes),
                        settings_text="다이 페이스 원스텝", mode=FORMING, forming=fi)


def summary(df: DieFace, fa_die=None):
    """표 줄 [(항목, 값)]."""
    rows = []
    if df.U is not None:
        from .unfolder import _tri_areas2
        x0, y0 = df.U.min(0)
        x1, y1 = df.U.max(0)
        rows.append(("드로잉 블랭크 (바인더까지)", f"{x1 - x0:,.0f} × {y1 - y0:,.0f} mm · 넓이 "
                                             f"{_tri_areas2(df.U, df.F).sum():,.0f} mm²"))
    if df.draw_in is not None and len(df.draw_in):
        rows.append(("끌려 들어감 (바인더 끝)", f"최대 {df.draw_in.max():.1f} · 평균 {df.draw_in.mean():.1f} mm"))
    rows.append(("바인더 기울기 · 폭 · 다이 R", f"{df.tilt:.0f}° · {df.binder_w:g} mm · R{df.r_die:.1f}"))
    if fa_die is not None:
        prod = df.region == PRODUCT
        e1, e2, th, rk = fa_die.fields
        w = fa_die.fi._weights()
        for name, sel in (("제품", prod), ("어덴덤·바인더", ~prod)):
            if sel.any() and w[sel].sum() > 0:
                from .formsim import _wq
                rows.append((f"{name}: 얇아짐 최대 · 한계 비", f"{_wq(th[sel], w[sel], 0.995):.1%} · "
                                                           f"{_wq(rk[sel], w[sel], 0.995):.2f}"))
    return rows
