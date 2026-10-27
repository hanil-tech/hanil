"""성형품(자동차 부품처럼 곡면이 있는 제품)의 블랭크 근사 전개.

판금처럼 평면·원통·원뿔로만 된 부품은 정확히 펼칠 수 있지만, 프레스로 당겨 만든
자유곡면은 펼 수 있는 면이 아니다(구면을 종이로 쌀 수 없는 것과 같다).
그래서 성형 해석 프로그램의 "원스텝(역해석) 블랭크 추정" 과 같은 생각으로 근사한다.

1. 제품 겉면(스킨)을 잘게 삼각형으로 나누고, 두께 가운데 면으로 t/2 만큼 옮긴다.
2. 등각 사상(LSCM)으로 처음 펼친 모양을 만든다.
3. ARAP(As-Rigid-As-Possible) 반복으로 각 삼각형이 될 수 있는 한 늘거나 줄지 않게 다듬는다.
   → 블랭크에서 제품으로 갈 때 생기는 변형이 가장 작은 펼친 모양.
4. 삼각형마다 블랭크 → 제품 넓이 비를 구해 두께 변화(체적 일정)를 어림한다.
       제품 두께 ≈ 원래 두께 × (블랭크 넓이 / 제품 넓이)

결과는 설계 초기의 블랭크 크기·재료비 추정용이다. 실제 금형 블랭크는
금형 시험(트라이아웃)이나 성형 해석으로 확정해야 한다.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.sparse import coo_matrix, csc_matrix, identity
from scipy.sparse.linalg import factorized, spsolve

from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location


class FormingError(Exception):
    pass


# ---------------------------------------------------------------- 메시

# 평평한 판의 구멍은 성형 뒤 피어싱으로 보고 막아서 해석 (fill_pierced_holes)
FILL_PIERCED = True
# 성형품 근사의 메시: 면마다 고른 크기 (facemesh) — CAD 메시보다 모양이 좋을 때 씀
UNIFORM_MESH = True
MAX_MESH_TRIS = 40_000    # CAD 메시가 이보다 많으면 성글게 다시 (큰 외판·촘촘한 B-스플라인에서 수십만 개가 나옴)


def _count_tris(faces):
    n = 0
    for face in faces:
        tri = BRep_Tool.Triangulation_s(face, TopLoc_Location())
        if tri is not None:
            n += tri.NbTriangles()
    return n


def mesh_faces(solid, faces, size_hint):
    """faces 를 삼각형으로 나눠 (꼭짓점, 삼각형) 을 돌려준다. 공유 모서리 점은 하나로 합친다.
    삼각형이 MAX_MESH_TRIS 를 넘으면 처짐 허용값을 키워 다시 나눈다 (자동차 외판 1.5 m 급에서 56 만 개 → 수 만 개)."""
    from OCP.BRepTools import BRepTools
    # 성근 메시에서 시작해 목표 (처짐 size/600 · 각 0.15) 까지 촘촘하게 — 다음 단계가 MAX 를 넘을 것 같으면 멈춤.
    # (목표 값으로 바로 나누면 촘촘한 B-스플라인 외판에서 56 만 개 · 1 분이 걸렸다)
    lin_goal, ang_goal = max(size_hint / 600.0, 0.02), 0.15
    lin, ang = lin_goal * 8, 0.6
    BRepTools.Clean_s(solid)
    BRepMesh_IncrementalMesh(solid, lin, False, ang, True)
    while lin > lin_goal * 1.01 or ang > ang_goal + 1e-9:
        n = _count_tris(faces)
        if n * 3.5 > MAX_MESH_TRIS:
            break
        lin, ang = max(lin / 2, lin_goal), max(ang / 2, ang_goal)
        BRepTools.Clean_s(solid)
        BRepMesh_IncrementalMesh(solid, lin, False, ang, True)

    verts, tris, normals = [], [], []
    keymap = {}
    tol = max(size_hint * 1e-7, 1e-7)

    def vid(p):
        key = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        i = keymap.get(key)
        if i is None:
            i = len(verts)
            verts.append(p)
            normals.append(np.zeros(3))
            keymap[key] = i
        return i

    for face in faces:
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            raise FormingError("면을 삼각형으로 나누지 못했습니다.")
        trsf = loc.Transformation()
        ids = []
        has_uv = tri.HasUVNodes()
        for i in range(1, tri.NbNodes() + 1):
            p = tri.Node(i).Transformed(trsf)
            k = vid((p.X(), p.Y(), p.Z()))
            ids.append(k)
            if has_uv:
                # 메시 평균이 아니라 실제 곡면의 바깥 법선 (절곡 R 처럼 휜 곳에서 정확)
                uv = tri.UVNode(i)
                n = _face_normal(face, uv.X(), uv.Y())
                if n is not None:
                    normals[k] = normals[k] + n
        flip = face.Orientation() == TopAbs_REVERSED
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(i).Get()
            t = (ids[a - 1], ids[b - 1], ids[c - 1])
            if len(set(t)) < 3:
                continue
            tris.append((t[0], t[2], t[1]) if flip else t)
    N = np.array(normals)
    L = np.linalg.norm(N, axis=1)
    N[L > 0] /= L[L > 0, None]
    return np.array(verts, float), np.array(tris, int), N


def _face_normal(face, u, v):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.gp import gp_Pnt, gp_Vec
    s = BRepAdaptor_Surface(face)
    p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    s.D1(u, v, p, du, dv)
    n = du.Crossed(dv)
    m = n.Magnitude()
    if m < 1e-12:
        return None
    n = np.array([n.X(), n.Y(), n.Z()]) / m
    return -n if face.Orientation() == TopAbs_REVERSED else n


def delaunay_flips(V, F, passes=4, coplanar_deg=8.0):
    """거의 한 평면인 이웃 삼각형 쌍 (a, b, c)·(b, a, d) 에서 맞은편 두 각의 합이 180° 를 넘으면 모서리 ab 를
    cd 로 뒤집는다 (델로네 뒤집기). CAD 메시의 평면 벽 (긴 부채꼴 바늘 삼각형) 을 고른 모양으로 — 깊은 사각 드로잉
    (오일 팬) 시험에서 삼각형 2/3 의 가장 작은 각이 1° 아래라 원스텝이 시작을 못 하던 것.
    굽은 곳 (두 면 법선 차 > coplanar_deg) 은 모양이 바뀌므로 뒤집지 않는다."""
    F = np.array(F, int)
    cos_c = math.cos(math.radians(coplanar_deg))
    for _ in range(passes):
        n_tri = len(F)
        nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
        edge = {}
        for t in range(n_tri):
            f = F[t]
            for k in range(3):
                a, b = int(f[k]), int(f[(k + 1) % 3])
                edge.setdefault((min(a, b), max(a, b)), []).append((t, k))
        used = np.zeros(n_tri, bool)
        flips = 0
        for (a, b), lst in edge.items():
            if len(lst) != 2:
                continue
            (t1, k1), (t2, k2) = lst
            if used[t1] or used[t2] or float(nrm[t1] @ nrm[t2]) < cos_c:
                continue
            f1, f2 = F[t1], F[t2]
            c = int(f1[(k1 + 2) % 3])
            d = int(f2[(k2 + 2) % 3])
            if c == d:
                continue

            def ang(p, q, r):                 # q 에서의 각
                u, v = V[p] - V[q], V[r] - V[q]
                return math.acos(max(-1.0, min(1.0, float(u @ v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-30))))
            if ang(a, c, b) + ang(a, d, b) <= math.pi + 1e-9:
                continue
            # 새 삼각형이 원래 방향을 지키는지 (뒤집혀 접히지 않게)
            p, q = int(f1[k1]), int(f1[(k1 + 1) % 3])      # t1 = (p, q, c), t2 = (q, p, d)
            n1 = np.cross(V[p] - V[c], V[d] - V[c])          # 새 (c, p, d)
            n2 = np.cross(V[q] - V[d], V[c] - V[d])          # 새 (d, q, c)
            if float(n1 @ nrm[t1]) <= 0 or float(n2 @ nrm[t1]) <= 0:
                continue
            F[t1] = (c, p, d)
            F[t2] = (d, q, c)
            used[t1] = used[t2] = True
            flips += 1
        if not flips:
            break
    return F


def subdivide(V, F, target=6000, N=None):
    """긴 모서리 나누기로 삼각형 크기를 고르게 (target 개쯤).
    CAD 메시는 원통 벽 같은 곳에 벽 높이만큼 긴 바늘 삼각형을 만든다. 4 등분은 모양이 그대로라
    변형률이 이웃끼리 번갈아 튀므로 (체커보드), 기준 길이 h 보다 긴 모서리를 모두 가운데서 나눈다
    (나뉜 모서리 수 1·2·3 에 따라 2·3·4 조각 — 이웃과 저절로 맞물림).
    N (꼭짓점 법선) 을 주면 새 점을 곡면 위로 올린다: 원호의 화살 높이 = (n1 − n0)·d / 8
    (절곡 R 의 현 가운데 점을 그대로 쓰면 호 길이가 짧아진다). 이때 (V, F, N) 을 돌려준다."""
    V = np.asarray(V, float)
    F = np.asarray(F, int)
    if N is not None:
        N = np.asarray(N, float)
    a = V[F[:, 1]] - V[F[:, 0]]
    b = V[F[:, 2]] - V[F[:, 0]]
    area = 0.5 * float(np.linalg.norm(np.cross(a, b), axis=1).sum())
    if area <= 0:
        return (V, F) if N is None else (V, F, N)
    if len(F) >= target:                  # 이미 촘촘해도 바늘 모양은 뒤집기로 고른다
        F = delaunay_flips(V, F)
        return (V, F) if N is None else (V, F, N)
    h = math.sqrt(4 * area / (math.sqrt(3) * target)) * 2.0      # 정삼각형 target 개 변 길이의 2 배 (길쭉한 것만 나뉘게)
    for _ in range(20):
        # 가장 긴 모서리 나누기 (Rivara longest-edge bisection): 나눌 모서리를 가진 삼각형은 자기 가장 긴 모서리도
        # 반드시 나누고 (전파), 나눌 때는 가장 긴 모서리의 가운데에서 맞은편 꼭짓점으로 먼저 자른다 —
        # 각이 처음 가장 작은 각의 절반 아래로 떨어지지 않는다. (모든 긴 모서리를 나누면 바늘 삼각형의
        # 두 긴 변이 같이 나뉘어 바늘이 더 많아졌다: 오일 팬 336 → 15,456 개)
        nF = len(F)
        Lk = np.stack([np.linalg.norm(V[F[:, k]] - V[F[:, (k + 1) % 3]], axis=1) for k in range(3)], axis=1)
        kmax = Lk.argmax(1)
        ar = np.arange(nF)

        def ekey(i, j):
            return (i, j) if i < j else (j, i)
        lkey = [ekey(int(F[t, kmax[t]]), int(F[t, (kmax[t] + 1) % 3])) for t in range(nF)]
        marked = {lkey[t] for t in ar[Lk[ar, kmax] > h]}
        if not marked or len(F) > 7 * target:
            break
        tri_edges = [[ekey(int(F[t, k]), int(F[t, (k + 1) % 3])) for k in range(3)] for t in range(nF)]
        changed = True
        while changed:                       # 전파: 표시된 모서리가 있으면 그 삼각형의 가장 긴 모서리도
            changed = False
            for t in range(nF):
                if lkey[t] not in marked and any(e in marked for e in tri_edges[t]):
                    marked.add(lkey[t])
                    changed = True
        long_ = np.array(sorted(marked), int)
        mid = {(int(i), int(j)): len(V) + k for k, (i, j) in enumerate(long_)}
        p0, p1 = V[long_[:, 0]], V[long_[:, 1]]
        pm = 0.5 * (p0 + p1)
        if N is not None:
            n0, n1 = N[long_[:, 0]], N[long_[:, 1]]
            nm = n0 + n1
            nm /= np.maximum(np.linalg.norm(nm, axis=1), 1e-30)[:, None]
            sag = np.einsum("ij,ij->i", n1 - n0, p1 - p0) / 8.0
            pm = pm + sag[:, None] * nm
            N = np.vstack([N, nm])
        V = np.vstack([V, pm])

        def m(i, j):
            return mid.get(ekey(i, j))

        nf = []
        for t, tri in enumerate(F.tolist()):
            k0 = int(kmax[t])                                    # 가장 긴 모서리를 A→B 로
            A, B, C = tri[k0], tri[(k0 + 1) % 3], tri[(k0 + 2) % 3]
            ab = m(A, B)
            if ab is None:
                nf.append(tri)
                continue
            bc, ca = m(B, C), m(C, A)
            # 가장 긴 모서리 가운데 ab → C 로 반 가르고, 남은 나뉜 모서리는 각 반쪽에서 다시 가른다
            if ca is None:
                nf.append([A, ab, C])
            else:
                nf += [[A, ab, ca], [ab, C, ca]]
            if bc is None:
                nf.append([ab, B, C])
            else:
                nf += [[ab, B, bc], [ab, bc, C]]
        F = np.array(nf, int)
        F = delaunay_flips(V, F, passes=2)
    F = delaunay_flips(V, F)
    return (V, F) if N is None else (V, F, N)


def quality(V, F):
    """삼각형마다 가장 작은 각(도). CAD 메시의 바늘 같은 조각은 변형률을 믿을 수 없다."""
    q = _local_frames(V, F)
    angs = []
    for k in range(3):
        a, b, c = q[:, k], q[:, (k + 1) % 3], q[:, (k + 2) % 3]
        u, v = b - a, c - a
        cos = np.einsum("ij,ij->i", u, v) / np.maximum(
            np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-30)
        angs.append(np.degrees(np.arccos(np.clip(cos, -1, 1))))
    return np.min(angs, axis=0)


def _keep_largest_component(V, F, N=None):
    n = len(V)
    parent = list(range(n))

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
    keep = F[roots == vals[np.argmax(counts)]]
    used = np.unique(keep)
    remap = -np.ones(n, int)
    remap[used] = np.arange(len(used))
    if N is not None:
        return V[used], remap[keep], N[used]
    return V[used], remap[keep]


def vertex_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])   # 넓이 가중
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], n)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)
    return N


# ---------------------------------------------------------------- 펼치기

def _local_frames(V, F):
    """삼각형마다 자기 평면 안의 2D 좌표 (원래 길이 그대로)."""
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1 = p1 - p0
    L1 = np.linalg.norm(e1, axis=1)
    x = e1 / L1[:, None]
    n = np.cross(e1, p2 - p0)
    n /= np.linalg.norm(n, axis=1)[:, None]
    y = np.cross(n, x)
    q = np.zeros((len(F), 3, 2))
    q[:, 1, 0] = L1
    q[:, 2, 0] = np.einsum("ij,ij->i", p2 - p0, x)
    q[:, 2, 1] = np.einsum("ij,ij->i", p2 - p0, y)
    return q


def _cot_weights(q):
    """삼각형마다 맞은편 꼭짓점의 cot 값 (변 (1,2), (2,0), (0,1) 순서)."""
    cots = np.zeros((len(q), 3))
    for k in range(3):
        a, b, c = q[:, k], q[:, (k + 1) % 3], q[:, (k + 2) % 3]
        u, v = b - a, c - a
        cross = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
        cots[:, k] = np.einsum("ij,ij->i", u, v) / np.maximum(np.abs(cross), 1e-30)
    return cots


def _boundary_vertices(F):
    edges = {}
    for t in F:
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
    return sorted({v for e, c in edges.items() if c == 1 for v in e})


def lscm(V, F):
    """최소제곱 등각 사상 (Lévy 외 2002). 경계에서 가장 먼 두 점을 고정한다."""
    n = len(V)
    q = _local_frames(V, F)
    bnd = _boundary_vertices(F)
    if len(bnd) < 2:
        raise FormingError("열린 경계가 없어 펼칠 수 없습니다 (닫힌 곡면).")
    B = V[bnd]
    i0 = bnd[int(np.argmax(np.linalg.norm(B - B.mean(0), axis=1)))]
    i1 = bnd[int(np.argmax(np.linalg.norm(V[bnd] - V[i0], axis=1)))]
    d = float(np.linalg.norm(V[i1] - V[i0]))

    rows, cols, vals = [], [], []
    for t, (tri, qq) in enumerate(zip(F, q)):
        area2 = qq[1, 0] * qq[2, 1]
        s = 1.0 / math.sqrt(max(abs(area2), 1e-30))
        # 복소수 W_j = (x_k - x_l) + i (y_k - y_l)
        for j in range(3):
            k, l = (j + 1) % 3, (j + 2) % 3
            wr = (qq[l, 0] - qq[k, 0]) * s
            wi = (qq[l, 1] - qq[k, 1]) * s
            vj = tri[j]
            # 실수부 식: wr*u - wi*v,  허수부 식: wi*u + wr*v
            rows += [2 * t, 2 * t, 2 * t + 1, 2 * t + 1]
            cols += [vj, n + vj, vj, n + vj]
            vals += [wr, -wi, wi, wr]
    A = csc_matrix(coo_matrix((vals, (rows, cols)), shape=(2 * len(F), 2 * n)))

    fixed_cols = [i0, n + i0, i1, n + i1]
    fixed_vals = np.array([0.0, 0.0, d, 0.0])
    free = np.setdiff1d(np.arange(2 * n), fixed_cols)
    rhs = -A[:, fixed_cols] @ fixed_vals
    Af = A[:, free]
    _check_finite(Af, rhs, what="펼침 행렬")
    sol = spsolve((Af.T @ Af).tocsc(), Af.T @ rhs)
    x = np.zeros(2 * n)
    x[free] = sol
    x[fixed_cols] = fixed_vals
    return np.column_stack([x[:n], x[n:]])


def arap(V, F, U, iterations=60):
    """As-Rigid-As-Possible 매개화 (Liu 외 2008): 삼각형마다 회전만 허용해 길이 변화를 줄인다."""
    n = len(V)
    q = _local_frames(V, F)
    cots = _cot_weights(q)
    # 라플라시안 (cot 가중)
    I, J, W = [], [], []
    for k in range(3):
        a, b = F[:, (k + 1) % 3], F[:, (k + 2) % 3]
        w = 0.5 * cots[:, k]
        I += [a, b, a, b]
        J += [b, a, a, b]
        W += [-w, -w, w, w]
    L = coo_matrix((np.concatenate(W), (np.concatenate(I), np.concatenate(J))), shape=(n, n)).tocsc()
    # 평행이동을 막기 위해 점 하나를 고정
    L = L.tolil()
    L[0, :] = 0
    L[0, 0] = 1
    L = L.tocsc()
    _check_finite(L, what="펼침 행렬")
    solve = factorized(L)

    size = float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
    for _ in range(iterations):
        # 국소 단계: 삼각형마다 가장 가까운 회전
        Rs = np.zeros((len(F), 2, 2))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            du = U[F[:, i]] - U[F[:, j]]
            dq = q[:, i] - q[:, j]
            Rs += cots[:, k, None, None] * np.einsum("ti,tj->tij", du, dq)
        # 2x2 에서 가장 가까운 회전은 각도 하나로 바로 나온다 (SVD 보다 수십 배 빠름)
        th = np.arctan2(Rs[:, 1, 0] - Rs[:, 0, 1], Rs[:, 0, 0] + Rs[:, 1, 1])
        c, sn = np.cos(th), np.sin(th)
        R = np.empty((len(F), 2, 2))
        R[:, 0, 0], R[:, 0, 1], R[:, 1, 0], R[:, 1, 1] = c, -sn, sn, c
        # 전역 단계
        rhs = np.zeros((n, 2))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            dq = q[:, i] - q[:, j]
            b = 0.5 * cots[:, k, None] * np.einsum("tij,tj->ti", R, dq)
            for d in (0, 1):
                rhs[:, d] += np.bincount(F[:, i], weights=b[:, d], minlength=n)
                rhs[:, d] -= np.bincount(F[:, j], weights=b[:, d], minlength=n)
        rhs[0] = U[0]
        U_new = np.column_stack([solve(rhs[:, 0]), solve(rhs[:, 1])])
        # 더 움직이지 않으면 멈춘다 (크기의 10만분의 1 이하)
        moved = float(np.abs(U_new - U).max())
        U = U_new
        if moved < 1e-5 * size:
            break
    return U


def strains(V, F, U):
    """삼각형마다 (주 변형률 ε1, ε2 [진변형률], 넓이 비 = 제품/블랭크)."""
    q = _local_frames(V, F)
    P = U[F]
    D_flat = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]], axis=2)    # 2x2
    D_3d = np.stack([q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]], axis=2)
    Fdef = D_3d @ np.linalg.inv(D_flat)        # 블랭크 → 제품
    s = np.linalg.svd(Fdef, compute_uv=False)
    e1, e2 = np.log(s[:, 0]), np.log(s[:, 1])
    ratio = s[:, 0] * s[:, 1]
    return e1, e2, ratio


# ------------------------------------------------------------------ 원스텝 역해석
#
# 성형 해석 프로그램(Dynaform MSTEP, ANSA Inverse Forming, AutoForm 등)의 "원스텝(역) 해석"은
# 제품 형상에서 출발해, 평판 블랭크가 한 번에 제품으로 변형된다고 보고 (전변형 이론)
# 그 변형에 드는 소성 일이 가장 작은 블랭크를 찾는다 (Lee & Huh 1998, KAIST 의 최소 소성 일 법).
# 여기서는 마찰·블랭크 홀더 힘은 빼고, 판 두께 방향 이방성 r 이 있는 Hill(1948) 등가 변형률과
# 멱법칙 경화 σ = K·ε^n 으로 소성 일 밀도  W = K·ε̄^(n+1)/(n+1)  을 쓴다.
#   ε̄ = (1+r)/√(1+2r) · √(ε1² + ε2² + 2r/(1+r)·ε1·ε2)      (ε1, ε2 = 면 안 주 진변형률)
# r = 1 이면 폰 미세스. 블랭크 좌표마다의 기울기를 직접 구해 L-BFGS 로 줄인다.
# ARAP(길이 보존 최소 제곱)와 달리 두께 변화(넓이 변화)를 재료 성질대로 비싸게 보므로
# 늘어남·줄어듦이 실제 성형처럼 재료가 흘러 들어오는 쪽으로 퍼지고, 블랭크 크기가 더 맞는다.

_EPS = 1e-4          # ε̄ = 0 근처의 꺾임을 펴는 값 (n 이 작을 때 기울기 발산 방지)
# 진변형률 |ε| 이 이 값을 넘으면 늘어남 비(e^|ε|)의 제곱으로 벌을 준다.
# 로그 변형률 에너지는 가는 띠 삼각형 하나에 압축을 몰아 주는 쪽(주름을 한 곳에 접어 넣는 것)이
# 고르게 줄이는 것보다 싸게 나와, 이것이 없으면 블랭크가 터무니없이 커진다.
_CAP = 0.6
_CAP_K = 1.0
# 소성 일을 어느 형상 위에서 적분할지: 0 = 제품(최종) 넓이, 1 = 블랭크(처음 부피) 넓이.
# 비례 변형 경로의 일은 중간 형상에서 재는 것이 맞으므로 (중점 규칙) 두 넓이의 기하 평균 = 0.5.
# 제품 넓이만 쓰면 얇아진 곳을 1/(1-얇아짐) 만큼 무겁게 세어 블랭크가 커지고 (원통 컵 +12 %),
# 블랭크 넓이만 쓰면 반대로 늘림이 싸져 작아진다 (-5 %). 0.5 에서 컵 넓이 비 1.00~1.03.
VOLUME_WEIGHT = 0.5
# 금형 작용 (펀치 면 마찰 · 블랭크 홀더 마찰 · 다이 R 굽힘-펴짐) 을 등가 외력으로 넣는다
TOOL_LOADS = True
# 원스텝 뒤 드로잉 보정 (인장 아래 굽힘 · 드로잉 장력 평형 · 아이어닝, drawcorr)
DRAW_CORRECTION = True


def plastic_work(Vm, F, U, n_exp, r_value=1.0, grad=True, q=None):
    """(소성 일 합 / 제품 넓이, 기울기 (n,2)). 삼각형이 뒤집히면 (inf, None)."""
    if q is None:
        q = _local_frames(Vm, F)
    Q = np.stack([q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]], axis=2)      # 제품 (m,2,2)
    P = U[F]
    D = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]], axis=2)       # 블랭크
    det = D[:, 0, 0] * D[:, 1, 1] - D[:, 0, 1] * D[:, 1, 0]
    if not np.all(det > 0):
        return np.inf, None
    Dinv = np.empty_like(D)
    Dinv[:, 0, 0], Dinv[:, 1, 1] = D[:, 1, 1] / det, D[:, 0, 0] / det
    Dinv[:, 0, 1], Dinv[:, 1, 0] = -D[:, 0, 1] / det, -D[:, 1, 0] / det
    Fd = Q @ Dinv                                                       # 블랭크 → 제품
    Uu, s, Vh = np.linalg.svd(Fd)
    e = np.log(s)
    k = (1 + r_value) ** 2 / (1 + 2 * r_value)
    b = 2 * r_value / (1 + r_value)
    eq = np.sqrt(k * (e[:, 0] ** 2 + e[:, 1] ** 2 + b * e[:, 0] * e[:, 1]) + _EPS ** 2)
    p = n_exp + 1.0
    phi = eq ** p / p
    over = np.maximum(np.exp(np.abs(e)) - math.exp(_CAP), 0.0)
    phi = phi + _CAP_K * np.sum(over ** 2, axis=1)
    # 역해석은 제품(최종) 메시 위에서 적분한다: 블랭크 삼각형이 쪼그라들면 변형률이 무한으로 가
    # 저절로 막힌다 (블랭크 넓이로 적분하면 넓이 0 으로 쪼그라드는 것이 공짜가 된다).
    Aq = 0.5 * np.linalg.det(Q)
    area = float(Aq.sum())
    A = Aq * (0.5 * det / Aq) ** VOLUME_WEIGHT if VOLUME_WEIGHT else Aq
    E = float(np.sum(A * phi)) / area
    if not np.isfinite(E):
        return np.inf, None
    if not grad:
        return E, None
    dphi = eq ** (p - 1) * k / (2 * eq)
    g = np.stack([dphi * (2 * e[:, 0] + b * e[:, 1]), dphi * (2 * e[:, 1] + b * e[:, 0])], axis=1)
    g = (g + 2 * _CAP_K * over * np.exp(np.abs(e)) * np.sign(e)) / s
    G = Uu * g[:, None, :] @ Vh                                         # dφ/dFd
    DinvT = np.transpose(Dinv, (0, 2, 1))
    dD = -A[:, None, None] * (np.transpose(Fd, (0, 2, 1)) @ G @ DinvT)
    if VOLUME_WEIGHT:                                                   # d(블랭크 넓이)/dD
        dD = dD + (VOLUME_WEIGHT * phi * A)[:, None, None] * DinvT
    gU = np.zeros_like(U)
    for c in range(2):
        g1, g2 = dD[:, c, 0], dD[:, c, 1]
        gU[:, c] += np.bincount(F[:, 1], g1, len(U)) + np.bincount(F[:, 2], g2, len(U)) \
            - np.bincount(F[:, 0], g1 + g2, len(U))
    return E, gU / area


def _elem_grad(Qm, A, P, n_exp, r_value):
    """삼각형별 A·φ 의 블랭크 세 꼭짓점 기울기 (m,3,2). 뒤집힌 삼각형은 NaN."""
    D = np.stack([P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]], axis=2)
    det = D[:, 0, 0] * D[:, 1, 1] - D[:, 0, 1] * D[:, 1, 0]
    Dinv = np.empty_like(D)
    Dinv[:, 0, 0], Dinv[:, 1, 1] = D[:, 1, 1] / det, D[:, 0, 0] / det
    Dinv[:, 0, 1], Dinv[:, 1, 0] = -D[:, 0, 1] / det, -D[:, 1, 0] / det
    Fd = Qm @ Dinv
    Uu, s, Vh = np.linalg.svd(Fd)
    e = np.log(s)
    k = (1 + r_value) ** 2 / (1 + 2 * r_value)
    b = 2 * r_value / (1 + r_value)
    eq = np.sqrt(k * (e[:, 0] ** 2 + e[:, 1] ** 2 + b * e[:, 0] * e[:, 1]) + _EPS ** 2)
    p = n_exp + 1.0
    over = np.maximum(np.exp(np.abs(e)) - math.exp(_CAP), 0.0)
    dphi = eq ** (p - 1) * k / (2 * eq)
    g = np.stack([dphi * (2 * e[:, 0] + b * e[:, 1]), dphi * (2 * e[:, 1] + b * e[:, 0])], axis=1)
    g = (g + 2 * _CAP_K * over * np.exp(np.abs(e)) * np.sign(e)) / s
    G = Uu * g[:, None, :] @ Vh
    DinvT = np.transpose(Dinv, (0, 2, 1))
    if VOLUME_WEIGHT:        # A 는 (제품 넓이 / 전체) → (중간 형상 넓이) / 전체 로
        A = A * (det / np.linalg.det(Qm)) ** VOLUME_WEIGHT
    dD = -A[:, None, None] * (np.transpose(Fd, (0, 2, 1)) @ G @ DinvT)
    if VOLUME_WEIGHT:
        phi = eq ** p / p + _CAP_K * np.sum(over ** 2, axis=1)
        dD = dD + (VOLUME_WEIGHT * phi * A)[:, None, None] * DinvT
    out = np.empty((len(P), 3, 2))
    out[:, 1], out[:, 2] = dD[:, :, 0], dD[:, :, 1]
    out[:, 0] = -(dD[:, :, 0] + dD[:, :, 1])
    out[det <= 0] = np.nan
    return out


def _newton_dir(F, Qm, A, X, g, n_exp, r_value, extra=None):
    """투영 뉴턴 방향: 삼각형마다 6x6 헤세 행렬(기울기 차분)을 양의 반정부호로 잘라 모은 뒤 푼다."""
    from scipy.sparse.linalg import splu

    m, n = len(F), len(X)
    P = X[F]
    scale = float(np.sqrt(np.mean(A))) * 1e-5
    H = np.empty((m, 6, 6))
    for j in range(6):
        v, c = divmod(j, 2)
        Pp, Pm = P.copy(), P.copy()
        Pp[:, v, c] += scale
        Pm[:, v, c] -= scale
        H[:, :, j] = ((_elem_grad(Qm, A, Pp, n_exp, r_value) - _elem_grad(Qm, A, Pm, n_exp, r_value))
                      .reshape(m, 6) / (2 * scale))
    H = 0.5 * (H + np.transpose(H, (0, 2, 1)))
    H[~np.isfinite(H).all(axis=(1, 2))] = 0.0
    w, V = np.linalg.eigh(H)
    w = np.maximum(w, 1e-8 * max(float(np.abs(w).max()), 1e-30))
    H = (V * w[:, None, :]) @ np.transpose(V, (0, 2, 1))
    idx = (2 * F[:, :, None] + np.arange(2)).reshape(m, 6)          # x 의 순서: (점, 좌표)
    rows = np.repeat(idx, 6, axis=1).ravel()
    cols = np.tile(idx, (1, 6)).ravel()
    K = coo_matrix((H.ravel(), (rows, cols)), shape=(2 * n, 2 * n)).tocsc()
    if extra is not None:
        K = K + extra
    K = K + 1e-8 * float(K.diagonal().mean()) * identity(2 * n, format="csc")
    return -splu(K).solve(g)


def _max_step(F, X, d):
    """X + α·d 에서 삼각형이 처음 뒤집히는 α (넓이 = α 의 2 차식의 가장 작은 양의 근)."""
    P, Dp = X[F], d[F]
    a = P[:, 1] - P[:, 0]
    b = P[:, 2] - P[:, 0]
    da = Dp[:, 1] - Dp[:, 0]
    db = Dp[:, 2] - Dp[:, 0]

    def cr(u, v):
        return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]

    A2, B2, C2 = cr(da, db), cr(a, db) + cr(da, b), cr(a, b)
    best = np.inf
    with np.errstate(divide="ignore", invalid="ignore"):
        lin = np.abs(A2) < 1e-14 * np.maximum(np.abs(B2), 1e-300)
        r_lin = np.where(lin & (B2 != 0), -C2 / B2, np.inf)
        disc = B2 ** 2 - 4 * A2 * C2
        sq = np.sqrt(np.maximum(disc, 0))
        r1 = np.where(~lin & (disc >= 0), (-B2 - sq) / (2 * A2), np.inf)
        r2 = np.where(~lin & (disc >= 0), (-B2 + sq) / (2 * A2), np.inf)
    for r in (r_lin, r1, r2):
        r = r[np.isfinite(r) & (r > 0)]
        if len(r):
            best = min(best, float(r.min()))
    return best


def _tool_setup(Vm, F, F_all, Ap, tools, n_exp):
    """금형 작용을 등가 외력으로 (Batoz·Guo, Naceur 의 역해석처럼): 펀치 면 마찰과 끌려 들어오는
    가장자리의 저항(블랭크 홀더 마찰 · 다이 R 굽힘-펴짐). 쓸 수 없으면 None."""
    a = Vm[F[:, 1]] - Vm[F[:, 0]]
    b = Vm[F[:, 2]] - Vm[F[:, 0]]
    nrm = np.cross(a, b)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    zsum = (Ap[:, None] * nrm).sum(0)
    if np.linalg.norm(zsum) < 0.08 * Ap.sum():         # 프레스 방향이 뚜렷하지 않음 (관·닫힌 꼴; 깊은 상자는 0.1~0.3)
        return None
    z = zsum / np.linalg.norm(zsum)                     # 투영 넓이가 가장 큰 방향 = 프레스 방향
    e1 = np.cross(z, [1.0, 0, 0] if abs(z[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(z, e1)
    proj = Vm @ np.column_stack([e1, e2])
    nv = len(Vm)
    t = tools["thickness"]
    n = max(n_exp, 0.02)
    sig_k = 0.2 ** n                                     # 흐름 응력 / K (변형률 0.2 근처)
    mu = tools.get("mu", 0.1)
    cap = math.exp(mu * math.pi / 2)                     # 다이 R 를 감아 도는 마찰 (캡스턴)
    # 펀치 면 (프레스 방향에 거의 수직인 면) 마찰: 접촉 압력 p ≈ 4·t·σ_벽/d  →  p/(K·t) = 2·(σ/K)/R
    contact = (nrm @ z) > math.cos(math.radians(10))
    wc = np.zeros(nv)
    for k in range(3):
        wc += np.bincount(F[contact, k], Ap[contact] / 3, nv)
    a_c = float(Ap[contact].sum())
    p_hat = 2 * 0.5 * sig_k / max(math.sqrt(a_c / math.pi), 1.0) if a_c > 0 else 0.0
    # 바깥 가장자리 (구멍은 빼고): 다이 R 굽힘-펴짐 σ·t/(2r+t) (Swift), 블랭크 홀더 마찰 μ·p_bh
    loops = boundary_loops(F_all)
    wb = np.zeros(nv)
    outer = None
    if loops:
        def length(lp):
            P = Vm[lp]
            return float(np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1).sum())
        outer = max(loops, key=length)
        P = Vm[outer]
        seg = np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1)
        w = 0.5 * (seg + np.roll(seg, 1))
        # 누르개 아래에서 끌려 들어오는 가장자리는 다이 면을 따라 눕는다 (트림선이 수평에 가까움). 벽을 따라 위아래로
        # 내려가는 경계 (잘린 끝 단면 — 햇 단면 멤버의 끝) 는 끌려 들어오지 않고, 위에서 본 투영이 한 줄로 겹쳐
        # 저항이 단면을 억지로 당겨 끝 귀퉁이가 100 % 넘게 늘어났다 → 경계 접선이 프레스 방향에 가까운 만큼 뺀다.
        tg = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
        tg /= np.maximum(np.linalg.norm(tg, axis=1), 1e-30)[:, None]
        w = w * (1 - np.abs(tg @ z)) ** 2
        np.add.at(wb, outer, w)
    rd = tools.get("die_r", 5 * t)
    sb_hat = sig_k * t / (2 * rd + t) * cap
    k_e = tools["tensile"] * (math.e / n) ** n
    c_bh = mu * tools.get("p_bh", 2.5) * cap / (k_e * t)
    return dict(proj=proj, wc=wc * mu * p_hat, wb1=wb * sb_hat, wb2=wb * c_bh,
                wfit=wc + wb, total=float(Ap.sum()), outer=outer)


def _boundary_normals(X, loop, nv):
    """블랭크 위 바깥 경계의 꼭짓점별 단위 법선 (n, 2), 경계가 아니면 0."""
    nb = np.zeros((nv, 2))
    if loop is None or len(loop) < 3:
        return nb
    P = X[loop]
    tng = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    nrm = np.column_stack([tng[:, 1], -tng[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    nb[loop] = nrm
    return nb


def _tool_energy(T, X, grad=True):
    """금형 작용 에너지 (/ 제품 넓이) 와 기울기, 꼭짓점별 헤세 대각 (2x2 등방)."""
    W = T["wfit"]
    sel = W > 0
    if sel.sum() < 3:
        return 0.0, np.zeros_like(X), np.zeros(len(X))
    # 블랭크 좌표에 맞춘 제품 투영 (가중 프로크루스테스, 뒤집힘 허용)
    P, Xs, w = T["proj"][sel], X[sel], W[sel][:, None]
    pc = (w * P).sum(0) / w.sum()
    xc = (w * Xs).sum(0) / w.sum()
    H = ((P - pc) * w).T @ (Xs - xc)
    u_, _, vt = np.linalg.svd(H)
    R = (u_ @ vt).T
    Qp = (T["proj"] - pc) @ R.T + xc
    d = X - Qp
    r = np.sqrt((d ** 2).sum(1) + 1e-4)
    # 가장자리 저항 (누르개 마찰·다이 R) 은 끌려 들어오는 방향 = 경계에 수직한 성분에만 건다.
    # 경계를 따라 (접선) 당기면 가파른 벽의 트림선에서 투영이 몰려 블랭크 경계가 국부적으로 쪼그라든다
    # (휀다 시험에서 가장자리 늘림 60 % 가 나온 원인). 법선은 제품 투영의 바깥 경계에서 한 번 정하고, 맞춤 회전 R 로
    # 같이 돌린다. (블랭크 위에서 고정해 두면 블랭크가 통째로 90° 돌아 법선과 끌림 방향이 직각이 되는 것으로
    # 저항이 0 이 된다 — 원통 컵을 오래 돌리면 금형 작용 없는 해로 빠졌다.)
    if "nb" not in T:
        T["nb"] = _boundary_normals(T["proj"], T.get("outer"), len(X))
    nb = T["nb"] @ R.T
    dn = (d * nb).sum(1)
    rb = np.sqrt(dn ** 2 + 1e-4)
    tot = T["total"]
    E = float((T["wc"] * r).sum() + (T["wb1"] * rb).sum() + (T["wb2"] * rb ** 2).sum()) / tot
    if not grad:
        return E, None, None
    cc = T["wc"] / r
    cb = T["wb1"] / rb + 2 * T["wb2"]
    g = (cc[:, None] * d + (cb * dn)[:, None] * nb) / tot
    return E, g, (cc + cb) / tot


def one_step(Vm, F, U0, n_exp, r_value=1.0, maxiter=200, seconds=4.0, tools=None):
    """ARAP 블랭크 U0 에서 시작해 소성 일이 가장 작은 블랭크로. (U, 반복 횟수).
    seconds 가 지나면 그때까지 가장 좋은 블랭크를 쓴다 (조립품의 부품이 많을 때).

    투영 뉴턴법: 삼각형마다 헤세 행렬을 양의 반정부호로 잘라 모아 풀고, 삼각형이 뒤집히지 않는
    걸음 안에서 에너지가 줄 때까지 걸음을 줄인다. 뉴턴 걸음이 막히면 라플라시안으로 전처리한
    기울기 쪽으로 한 걸음 간다. (scipy L-BFGS 는 뒤집힘(무한 에너지)을 만나면 멈추고,
    촘촘한 메시에서는 수백 번을 돌아도 거의 줄지 않았다.)"""
    import time

    deadline = time.monotonic() + seconds
    F_in = F
    # 바늘 같은 조각 삼각형(가장 작은 각 < 1°)은 조금만 움직여도 뒤집혀 최적화를 막는다.
    # 에너지·뒤집힘 검사에서 빼고, 그 변은 길이 용수철로만 잡아 둔다 (꼭짓점이 떠다니지 않게).
    good = quality(Vm, F) > 1.0
    # 시작 블랭크 (ARAP) 에서 이미 뒤집힌 삼각형도 같이 뺀다 — 큰 외판의 가장자리 조각 (가장 작은 각 1~6°) 몇 십 개가
    # 뒤집혀 있으면 원스텝을 못 하고 ARAP 결과를 그대로 써서, 두께 변화가 −12 ~ +21 % 로 크게 틀렸다 (후드 시험).
    U0a = np.asarray(U0, float)
    good &= ~_flipped(U0a, F)
    if good.sum() < 0.5 * len(F):
        raise ValueError("메시에 조각 삼각형이 너무 많습니다")
    bad = F[~good]
    E_ = np.vstack([bad[:, [0, 1]], bad[:, [1, 2]], bad[:, [2, 0]]]) if len(bad) else np.zeros((0, 2), int)
    E_ = np.unique(np.sort(E_, axis=1), axis=0)
    L_ = np.linalg.norm(Vm[E_[:, 0]] - Vm[E_[:, 1]], axis=1)
    E_, L_ = E_[L_ > 1e-9], L_[L_ > 1e-9]
    F = F[good]
    nv = len(U0)
    q = _local_frames(Vm, F)
    Qm = np.stack([q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]], axis=2)
    Ap = 0.5 * np.linalg.det(Qm)
    total = float(Ap.sum())
    w_spring = float(Ap.mean()) / total
    U0 = np.asarray(U0, float)
    P = U0[F]
    a, c = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    flip = (a[:, 0] * c[:, 1] - a[:, 1] * c[:, 0]).sum() < 0
    x = (U0 * (1, -1) if flip else U0.copy()).ravel()
    F_all = F_in
    T = _tool_setup(Vm, F, F_all, Ap, tools, n_exp) if tools else None

    def fun(x):
        X = x.reshape(-1, 2)
        E, g = plastic_work(Vm, F, X, n_exp, r_value, q=q)
        if g is None:
            return E, None
        if T is not None:
            et, gt, _ = _tool_energy(T, X)
            E += et
            g = g + gt
        if len(E_):
            dv = X[E_[:, 0]] - X[E_[:, 1]]
            ln = np.maximum(np.linalg.norm(dv, axis=1), 1e-12)
            st = (ln - L_) / L_
            E += w_spring * float(np.sum(st ** 2))
            cc = (2 * w_spring * st / L_ / ln)[:, None] * dv
            for k in range(2):
                g[:, k] += np.bincount(E_[:, 0], cc[:, k], nv) - np.bincount(E_[:, 1], cc[:, k], nv)
        return E, g.ravel()

    # 용수철의 헤세 행렬 (가우스-뉴턴을 등방으로 어림, 늘 같다)
    spring_H = None
    if len(E_):
        kk = 2 * w_spring / L_ ** 2
        ii = np.stack([2 * E_[:, 0], 2 * E_[:, 0] + 1, 2 * E_[:, 1], 2 * E_[:, 1] + 1], axis=1)
        block = np.kron(np.array([[1.0, -1.0], [-1.0, 1.0]]), np.eye(2))
        spring_H = coo_matrix(((kk[:, None, None] * block[None]).ravel(),
                               (np.repeat(ii, 4, axis=1).ravel(), np.tile(ii, (1, 4)).ravel())),
                              shape=(2 * nv, 2 * nv)).tocsc()

    # 뉴턴이 막혔을 때 쓸 전처리: 제품 메시의 cot 라플라시안
    cots = np.clip(_cot_weights(q), 0.01, 100.0)
    I, J, W = [], [], []
    for k in range(3):
        i_, j_ = F[:, (k + 1) % 3], F[:, (k + 2) % 3]
        w = 0.5 * cots[:, k]
        I += [i_, j_, i_, j_]
        J += [j_, i_, i_, j_]
        W += [-w, -w, w, w]
    Lp = coo_matrix((np.concatenate(W), (np.concatenate(I), np.concatenate(J))), shape=(nv, nv)).tocsc()
    Lp = Lp + 1e-6 * float(Lp.diagonal().mean()) * identity(nv, format="csc")
    _check_finite(Lp, what="전처리 행렬")
    lsolve = factorized(Lp.tocsc())
    span = float(np.ptp(U0, axis=0).max()) or 1.0

    def gradient_dir(g):
        G = g.reshape(-1, 2)
        d = -np.column_stack([lsolve(G[:, 0]), lsolve(G[:, 1])]).ravel()
        return d * (0.01 * span / max(np.abs(d).max(), 1e-30))        # 가장 큰 이동 1 %

    f0, g = fun(x)
    if g is None:
        raise ValueError("시작 블랭크에 뒤집힌 삼각형이 있습니다")
    f, it, stall, fails = f0, 0, 0, 0
    while it < maxiter and time.monotonic() < deadline:
        it += 1
        d = None
        if fails == 0:
            try:
                extra = spring_H
                if T is not None:
                    _, _, hd = _tool_energy(T, x.reshape(-1, 2))
                    from scipy.sparse import diags
                    Ht = diags(np.repeat(hd, 2), format="csc")
                    extra = Ht if extra is None else extra + Ht
                d = _newton_dir(F, Qm, Ap / total, x.reshape(-1, 2), g, n_exp, r_value, extra)
            except (RuntimeError, ValueError, np.linalg.LinAlgError):
                d = None
            if d is not None and not (np.all(np.isfinite(d)) and g @ d < 0):
                d = None
        if d is None:
            d = gradient_dir(g)
        slope = g @ d
        step = min(1.0, 0.8 * _max_step(F, x.reshape(-1, 2), d.reshape(-1, 2)))
        ok = False
        for _ in range(30):
            xn = x + step * d
            fn, gn = fun(xn)
            if gn is not None and fn <= f + 1e-4 * step * slope:
                ok = True
                break
            step *= 0.5
        if not ok:
            fails += 1
            if fails >= 2:
                break
            continue
        fails = 0
        stall = stall + 1 if f - fn < 1e-6 * f0 else 0
        x, f, g = xn, fn, gn
        if stall >= 3:
            break
    U = x.reshape(-1, 2)
    if flip:
        U = U * (1, -1)
    _check_finite(U, what="원스텝 역해석 결과")
    return U, it


# ------------------------------------------------------------------ 성형 한계 (FLC)
#
# Keeler-Brazier 식 (North American Deep Drawing Research Group):
#   FLC0 [% 공칭] = (23.3 + 14.17·t) · n / 0.21      (t: 두께 mm, 강판, t ≤ 약 3 mm)
#   (Keeler 원식은 인치: 23.3 + 360·t — 360 / 25.4 = 14.17. Schaeffler 2019 는 14.2·t)
# 왼쪽(ε2 < 0)은 두께 감소가 FLC0 와 같은 선 (ε1 + ε2 = ε0, 진변형률),
# 오른쪽(ε2 > 0)은 기울기 약 0.6 으로 올라간다. 알루미늄·스테인리스는 식이 맞지 않아
# 재료 표의 대표 FLC0 를 쓴다.

def keeler_flc0(t, n):
    """FLC0 (진변형률)."""
    t = min(max(float(t), 0.3), 3.0)
    return math.log(1 + (23.3 + 360.0 / 25.4 * t) * n / 0.21 / 100)


# 재질별 실측 FLC (ISO 12004-2 성형 한계 시험, 소재 업체 자료): 코드 → [(ε2, ε1)] 진변형률, ε2 오름차순.
# 앱이 설정에서 읽어 넣는다 (flcdata.load). 있으면 Keeler 식 대신 쓴다.
MEASURED_FLC: dict = {}


def flc_limit(minor, flc0, material=None):
    """부 변형률마다 한계 주 변형률 (진변형률). 실측 FLC 가 있으면 그 점들을 잇고 (양 끝 밖은 끝 기울기로),
    없으면 Keeler 꼴: 왼쪽 ε1 = FLC0 − ε2, 오른쪽 ε1 = FLC0 + 0.6 ε2."""
    minor = np.asarray(minor, float)
    pts = MEASURED_FLC.get(material) if material else None
    if pts and len(pts) >= 2:
        x = np.array([p[0] for p in pts], float)
        y = np.array([p[1] for p in pts], float)
        out = np.interp(minor, x, y)
        lo, hi = minor < x[0], minor > x[-1]
        k_lo = (y[1] - y[0]) / max(x[1] - x[0], 1e-12)
        k_hi = (y[-1] - y[-2]) / max(x[-1] - x[-2], 1e-12)
        out = np.where(lo, y[0] + k_lo * (minor - x[0]), out)
        out = np.where(hi, y[-1] + k_hi * (minor - x[-1]), out)
        return np.maximum(out, 0.02)
    return np.where(minor < 0, flc0 - minor, flc0 + 0.6 * minor)


def flc0_of(material, flc0):
    """실측 FLC 가 있으면 ε2 = 0 의 값, 없으면 flc0."""
    pts = MEASURED_FLC.get(material) if material else None
    return float(flc_limit(np.array([0.0]), flc0, material)[0]) if pts and len(pts) >= 2 else flc0


def flc_risk(major, minor, flc0, material=None):
    """주 변형률 / 한계 (1 이상 = 파단 위험)."""
    lim = flc_limit(minor, flc0, material)
    return np.where(major > 0, major / lim, 0.0)


def boundary_loops(F):
    """한 삼각형에만 속한 변을 이어 닫힌 경계들로."""
    count = {}
    for t in F:
        for k in range(3):
            a, b = int(t[k]), int(t[(k + 1) % 3])
            key = (min(a, b), max(a, b))
            count[key] = count.get(key, 0) + 1
    nxt = {}
    for t in F:
        for k in range(3):
            a, b = int(t[k]), int(t[(k + 1) % 3])
            if count[(min(a, b), max(a, b))] == 1:
                nxt[a] = b
    loops = []
    while nxt:
        start, cur = next(iter(nxt.items()))
        loop = [start]
        nxt.pop(start)
        while cur != start and cur in nxt:
            loop.append(cur)
            cur = nxt.pop(cur)
        loops.append(loop)
    return loops


def _drop_degenerate(V, F):
    """넓이가 거의 0 인 삼각형(같은 점이 겹치거나 한 줄 위의 점)을 뺀다.
    남겨 두면 행렬에 NaN 이 들어가 희소 행렬 분해가 멈추거나 프로그램이 죽는다."""
    if not len(F):
        return F
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area2 = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    scale = float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
    shortest = np.minimum(np.minimum(np.linalg.norm(p1 - p0, axis=1), np.linalg.norm(p2 - p1, axis=1)),
                          np.linalg.norm(p0 - p2, axis=1))
    keep = np.isfinite(area2) & (area2 > 1e-10 * scale * scale) & (shortest > 1e-7 * scale)
    return F[keep]


def _check_finite(*arrays, what="메시"):
    for a in arrays:
        data = a.data if hasattr(a, "data") and not isinstance(a, np.ndarray) else a
        if not np.all(np.isfinite(data)):
            raise ValueError(f"{what}가 깨져 펼칠 수 없습니다 (겹친 점·넓이 0 인 면). "
                             "CAD 에서 형상을 확인해 주세요.")


def flatten(V, F, thickness, iterations=60, N=None, n_exp=None, r_value=1.0, info=None, tools=None):
    """제품 겉면 메시 → (가운데 면 메시, 펼친 좌표 U). N: 꼭짓점별 실제 곡면 법선.
    n_exp(가공 경화 지수 n)를 주면 ARAP 결과에서 시작해 소성 일 최소화(원스텝 역해석)로 다듬는다.
    info(dict)에 쓴 방법·반복 횟수를 적어 준다."""
    if N is None:
        N = vertex_normals(V, F)
    V, F, N = _keep_largest_component(V, F, N)
    Nmesh = vertex_normals(V, F)
    bad = np.linalg.norm(N, axis=1) < 0.5          # 곡면 법선을 못 구한 점은 메시 법선으로
    if bad.any():
        N[bad] = Nmesh[bad]
    # CAD 법선이 뒤집혀 나온 점 (오프셋·B-스플라인 면, 면 방향이 섞인 파일) 은 메시 쪽으로 돌린다 — 그대로 두면
    # 가운데 면이 점마다 ±t/2 로 톱니가 되어 (휀다 시험: 곡률 반지름 528 → 4 mm) 변형률·곡률이 틀린다
    N = N * np.where(np.einsum("ij,ij->i", N, Nmesh) < 0, -1.0, 1.0)[:, None]
    Vm = V - 0.5 * thickness * N
    _check_finite(Vm)
    # 두께가 형상 크기만 한 부품(핀·봉·너트)은 가운데 면이 한 점·한 선으로 줄어든다: 판금이 아님
    if float(np.linalg.norm(np.ptp(Vm, axis=0))) < 0.3 * float(np.linalg.norm(np.ptp(V, axis=0))):
        raise ValueError("판금·성형품이 아닌 부품입니다 (두께가 형상 크기와 비슷함: 핀·봉·너트 등).")
    Vm, F, Nm = subdivide(Vm, F, N=N)
    F = _drop_degenerate(Vm, F)
    if len(F) < 2:
        raise ValueError("펼칠 면이 없습니다 (메시가 비었거나 모두 넓이 0).")
    Vm, F, Nm = _keep_largest_component(Vm, F, Nm)
    if info is not None:
        info["normals"] = Nm             # CAD 곡면 법선 (드로잉 보정의 곡률 — 메시 법선은 면 경계에서 뭉개짐)
    U = lscm(Vm, F)
    _check_finite(U, what="1차 펼침 결과")
    U = arap(Vm, F, U, iterations)
    _check_finite(U, what="펼침 결과")
    if info is not None:
        info["method"] = "ARAP"
    if n_exp is not None:
        try:
            U2, it = one_step(Vm, F, U, n_exp, r_value, tools=tools)
            U = U2
            if info is not None:
                info["method"], info["iterations"] = "원스텝 역해석 (소성 일 최소)", it
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            pass                       # 다듬기에 실패하면 ARAP 결과를 그대로 쓴다
    span3 = float(np.linalg.norm(Vm.max(0) - Vm.min(0))) or 1.0
    if float(np.linalg.norm(U.max(0) - U.min(0))) < 0.05 * span3:
        raise ValueError("펼친 결과가 비정상입니다 (크기가 거의 0). 판금·성형품이 아닌 부품일 수 있습니다.")
    # 바깥에서 본 모습이 되도록: 삼각형 방향이 뒤집혔으면 대칭
    P = U[F]
    a, b = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    signed = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum()
    if signed < 0:
        U[:, 1] *= -1
    return Vm, F, _align_min_box(U)


def _flipped(U, F):
    P = U[F]
    a, b = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    s = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    sg = 1.0 if (s > 0).sum() >= (s < 0).sum() else -1.0
    return s * sg <= 0


def _align_min_box(U):
    """바깥 사각형이 가장 작아지게 돌린다 (철판에서 잘라 낼 크기가 바로 보이게)."""
    from scipy.spatial import ConvexHull

    hull = U[ConvexHull(U).vertices]
    best = None
    for i in range(len(hull)):
        d = hull[(i + 1) % len(hull)] - hull[i]
        a = -math.atan2(d[1], d[0])
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        P = hull @ R.T
        w, h = P.max(0) - P.min(0)
        # 넓이가 같으면 가로로 긴 쪽
        key = (round(w * h, 6), -w)
        if best is None or key < best[0]:
            best = (key, R, w < h)
    R = best[1]
    if best[2]:
        R = np.array([[0.0, -1.0], [1.0, 0.0]]) @ R
    return U @ R.T


# ------------------------------------------------------------------ 피어싱 구멍 막기
#
# 차체 부품의 구멍은 대부분 드로잉 뒤 피어싱으로 뚫는다. 구멍이 처음부터 있는 것으로 펼치면 구멍 둘레가
# 자유 가장자리라 늘어나 버려 (실제로는 판이 이어져 있음) 변형률·블랭크가 틀린다. 평평한 판에 뚫린 구멍
# (경계가 한 평면에 놓이고 둘레 판이 그 평면과 나란함) 은 막아서 해석하고, 세운 구멍 (버링 — 둘레가 벽) 은
# 그대로 둔다 (버링은 미리 뚫은 구멍을 넓혀 세움).
PIERCE_FLAT_DEG = 40.0      # 구멍 둘레 삼각형 법선이 구멍 평면 법선과 이 각 안이면 평평한 구멍 (버링 벽은 약 90°)


def fill_pierced_holes(V, F, N=None, t=1.0):
    """(V, F, N, 막은 구멍 목록 [dict(center, normal, poly, d)]). 바깥 경계 (가장 긴 고리) 는 건드리지 않는다."""
    from scipy.spatial import Delaunay
    loops = boundary_loops(F)
    if len(loops) < 2:
        return V, F, N, []

    def length(lp):
        P = V[lp]
        return float(np.linalg.norm(P - np.roll(P, -1, axis=0), axis=1).sum())
    outer = max(loops, key=length)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
    vt = {}
    for ti, tri in enumerate(F):
        for k in tri:
            vt.setdefault(int(k), []).append(ti)
    Vl, Fl, Nl = [V], [F], [N] if N is not None else None
    nv = len(V)
    holes = []
    edge_len = float(np.median(np.linalg.norm(V[F[:, 1]] - V[F[:, 0]], axis=1)))
    for lp in loops:
        if lp is outer or len(lp) < 3:
            continue
        P = V[lp]
        c = P.mean(0)
        _, _, vh = np.linalg.svd(P - c)
        nrm = vh[2]
        flat = np.abs((P - c) @ nrm).max()
        d_eq = 2 * math.sqrt(max(abs(_poly_area2(P, vh)), 1e-12) / math.pi)
        if flat > max(0.15 * d_eq, 0.5 * t):
            continue                                   # 휜 구멍 (곡면을 가로지름) — 그대로
        adj = sorted({ti for k in lp for ti in vt.get(int(k), ())})
        cosang = np.abs(fn[adj] @ nrm)
        if np.median(cosang) < math.cos(math.radians(PIERCE_FLAT_DEG)):
            continue                                   # 둘레가 벽 (버링·세운 구멍) — 그대로
        # 구멍 평면 위 2D 로: 경계점 + 안쪽 격자 → 들로네, 다각형 안 삼각형만
        Q = (P - c) @ vh[:2].T
        step = max(edge_len, 1e-6)
        lo, hi = Q.min(0), Q.max(0)
        gx = np.arange(lo[0] + step / 2, hi[0], step)
        gy = np.arange(lo[1] + step / 2, hi[1], step)
        G = np.array([(x, y) for x in gx for y in gy]).reshape(-1, 2)
        if len(G):
            inside = _in_poly(G, Q)
            dmin = np.min(np.linalg.norm(G[:, None, :] - Q[None, :, :], axis=2), axis=1) if len(G) * len(Q) < 4e6 \
                else np.full(len(G), step)
            G = G[inside & (dmin > 0.5 * step)]
        pts = np.vstack([Q, G])
        try:
            tri = Delaunay(pts).simplices
        except Exception:
            continue
        cen = pts[tri].mean(1)
        tri = tri[_in_poly(cen, Q)]
        if not len(tri):
            continue
        ids = np.concatenate([np.asarray(lp, int), nv + np.arange(len(G))])
        newV = c + G @ vh[:2]
        Ft = ids[tri]
        # 방향: 이웃 삼각형과 같게 (구멍 경계 모서리 a→b 가 이웃에서 b→a 로 돌면 맞음)
        a, b = int(lp[0]), int(lp[1])
        own = None
        for ti in vt.get(a, ()):
            tr = list(F[ti])
            if b in tr:
                i = tr.index(a)
                own = tr[(i + 1) % 3] == b              # 이웃이 a→b 로 돎
                break
        patch_dir = None
        for tr in Ft:
            tr = list(tr)
            if a in tr and b in tr:
                i = tr.index(a)
                patch_dir = tr[(i + 1) % 3] == b
                break
        if own is not None and patch_dir is not None and own == patch_dir:
            Ft = Ft[:, ::-1]
        Vl.append(newV)
        Fl.append(Ft)
        if Nl is not None:
            nn = np.tile(nrm if (N[lp] @ nrm).mean() >= 0 else -nrm, (len(G), 1))
            Nl.append(nn)
        nv += len(G)
        holes.append(dict(center=c, normal=nrm, poly=P.copy(), d=d_eq))
    if not holes:
        return V, F, N, []
    V2 = np.vstack(Vl)
    F2 = np.vstack(Fl)
    N2 = np.vstack(Nl) if Nl is not None else None
    return V2, F2, N2, holes


def _poly_area2(P, vh):
    Q = (P - P.mean(0)) @ vh[:2].T
    x, y = Q[:, 0], Q[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _in_poly(pts, poly):
    """점들이 다각형 안인가 (짝홀 규칙)."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x1, y1 = poly[:, 0][None, :], poly[:, 1][None, :]
    x2, y2 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cross = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / np.where(y2 - y1 == 0, 1e-30, y2 - y1) + x1)
    return (cross.sum(1) % 2) == 1


def filled_mask(V, F, holes, t=1.0):
    """막은 구멍 자리 삼각형 (가운데가 구멍 다각형 안 · 구멍 평면에서 t 안)."""
    m = np.zeros(len(F), bool)
    if not holes:
        return m
    C = V[F].mean(1)
    for h in holes:
        c, n, P = h["center"], h["normal"], h["poly"]
        _, _, vh = np.linalg.svd(P - c)
        near = np.abs((C - c) @ n) < max(2 * t, 0.15 * h["d"])          # fill 의 평평함 기준과 같게
        if not near.any():
            continue
        Q = (P - c) @ vh[:2].T
        idx = np.nonzero(near)[0]
        m[idx] |= _in_poly((C[idx] - c) @ vh[:2].T, Q)
    return m
