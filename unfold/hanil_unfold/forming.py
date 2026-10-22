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
from scipy.sparse import coo_matrix, csc_matrix
from scipy.sparse.linalg import factorized, spsolve

from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location


class FormingError(Exception):
    pass


# ---------------------------------------------------------------- 메시

def mesh_faces(solid, faces, size_hint):
    """faces 를 삼각형으로 나눠 (꼭짓점, 삼각형) 을 돌려준다. 공유 모서리 점은 하나로 합친다."""
    lin = max(size_hint / 600.0, 0.02)
    BRepMesh_IncrementalMesh(solid, lin, False, 0.15, True)

    verts, tris = [], []
    keymap = {}
    tol = max(size_hint * 1e-7, 1e-7)

    def vid(p):
        key = (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
        i = keymap.get(key)
        if i is None:
            i = len(verts)
            verts.append(p)
            keymap[key] = i
        return i

    for face in faces:
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            raise FormingError("면을 삼각형으로 나누지 못했습니다.")
        trsf = loc.Transformation()
        ids = []
        for i in range(1, tri.NbNodes() + 1):
            p = tri.Node(i).Transformed(trsf)
            ids.append(vid((p.X(), p.Y(), p.Z())))
        flip = face.Orientation() == TopAbs_REVERSED
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(i).Get()
            t = (ids[a - 1], ids[b - 1], ids[c - 1])
            if len(set(t)) < 3:
                continue
            tris.append((t[0], t[2], t[1]) if flip else t)
    return np.array(verts, float), np.array(tris, int)


def subdivide(V, F, target=6000):
    """삼각형이 target 개쯤 될 때까지 4 등분한다 (변형 분포를 고르게 보려고)."""
    while len(F) * 4 <= target * 1.5 and len(F) < target:
        mids = {}
        newV = list(V)

        def mid(a, b):
            key = (a, b) if a < b else (b, a)
            i = mids.get(key)
            if i is None:
                i = len(newV)
                newV.append(0.5 * (V[a] + V[b]))
                mids[key] = i
            return i

        nf = []
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        V, F = np.array(newV), np.array(nf, int)
    return V, F


def _keep_largest_component(V, F):
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
    solve = factorized(L.tocsc())

    for _ in range(iterations):
        # 국소 단계: 삼각형마다 가장 가까운 회전
        Rs = np.zeros((len(F), 2, 2))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            du = U[F[:, i]] - U[F[:, j]]
            dq = q[:, i] - q[:, j]
            Rs += cots[:, k, None, None] * np.einsum("ti,tj->tij", du, dq)
        u_, s_, vt = np.linalg.svd(Rs)
        R = u_ @ vt
        bad = np.linalg.det(R) < 0
        if bad.any():
            u_[bad, :, 1] *= -1
            R[bad] = u_[bad] @ vt[bad]
        # 전역 단계
        rhs = np.zeros((n, 2))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            dq = q[:, i] - q[:, j]
            b = 0.5 * cots[:, k, None] * np.einsum("tij,tj->ti", R, dq)
            np.add.at(rhs, F[:, i], b)
            np.add.at(rhs, F[:, j], -b)
        rhs[0] = U[0]
        U = np.column_stack([solve(rhs[:, 0]), solve(rhs[:, 1])])
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


def flatten(V, F, thickness, iterations=60):
    """제품 겉면 메시 → (가운데 면 메시, 펼친 좌표 U)."""
    V, F = _keep_largest_component(V, F)
    N = vertex_normals(V, F)        # 나누기 전 (곡면 위의 점) 법선
    Vm = V - 0.5 * thickness * N
    Vm, F = subdivide(Vm, F)
    U = lscm(Vm, F)
    U = arap(Vm, F, U, iterations)
    # 바깥에서 본 모습이 되도록: 삼각형 방향이 뒤집혔으면 대칭
    P = U[F]
    a, b = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    signed = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum()
    if signed < 0:
        U[:, 1] *= -1
    return Vm, F, _align_min_box(U)


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
