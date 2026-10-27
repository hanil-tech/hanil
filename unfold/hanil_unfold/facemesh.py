"""고른 크기의 면 메시 (성형품 근사·성형 해석용).

CAD 메시기 (BRepMesh) 는 모양을 맞추는 데만 점을 써서, 길게 곧은 면 (햇 단면 멤버의 벽·평면 패널) 에
면 길이만큼 긴 바늘 삼각형 부채꼴을 만든다. 그런 삼각형이 절곡 R 을 가로지르면 원스텝 변형률이 점점이 튄다
(사이드 멤버 시험: 끝 귀퉁이 가장자리 늘림 104 %). 여기서는 면마다 매개변수 (u, v) 위에 실제 길이로
고른 격자를 깔고, 굽은 쪽은 곡률에 맞춰 촘촘하게 (한 칸에 0.15 rad), 경계선은 모서리마다 한 번만 나눠
이웃 면과 같은 점을 쓰고, 들로네 삼각분할 뒤 면 밖 삼각형을 버린다.
"""
from __future__ import annotations

import math

import numpy as np

ANGLE_STEP = 0.15         # 굽은 쪽 한 칸의 각 (rad) — 절곡 R 90° 에 11 칸 (현 길이 오차 θ²/24 = 0.1 %)
MAX_POINTS = 60_000
ASPECT = 6.0              # 칸의 가로세로 비 한도
SAMPLES = 15              # 곡률을 재는 매개변수 격자 (한 방향) — 자유곡면의 작은 R 을 놓치지 않게


class _Index:
    """같은 모서리 (IsSame — 방향만 다른 것도 같음) 를 같은 번호로."""

    def __init__(self):
        self.items, self._b = [], {}

    def find(self, shape):
        for i in self._b.get(hash(shape), ()):
            if self.items[i].IsSame(shape):
                return i
        return None

    def add(self, shape):
        i = self.find(shape)
        if i is None:
            self.items.append(shape)
            i = len(self.items) - 1
            self._b.setdefault(hash(shape), []).append(i)
        return i


def _area(face):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    return abs(g.Mass())


def _edge_params(edge, h, ang=ANGLE_STEP, samples=400):
    """모서리를 길이 h 이하 · 꺾임 ang 이하로 나눈 매개변수들 (양 끝 포함, 같은 호 길이 간격). 퇴화 모서리는 None.
    곡선을 samples 점으로 재서 누적 길이를 거꾸로 찾는다 (OCC 의 등간격 함수는 큰 B-스플라인 판 경계에서
    수십 초가 걸렸다)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    if BRep_Tool.Degenerated_s(edge):
        return None
    c = BRepAdaptor_Curve(edge)
    a, b = c.FirstParameter(), c.LastParameter()
    T = np.linspace(a, b, samples + 1)
    P = np.array([[c.Value(t).X(), c.Value(t).Y(), c.Value(t).Z()] for t in T])
    d = np.diff(P, axis=0)
    seg = np.linalg.norm(d, axis=1)
    L = float(seg.sum())
    if L < 1e-9:
        return None
    ok = seg > 1e-12
    tg = d[ok] / seg[ok, None]
    turn = float(np.arccos(np.clip(np.einsum("ij,ij->i", tg[1:], tg[:-1]), -1, 1)).sum()) if len(tg) > 1 else 0.0
    n = max(1, math.ceil(L / h), math.ceil(turn / ang))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    return list(np.interp(np.linspace(0, L, n + 1), cum, T))


def _spacing(surf, u0, u1, v0, v1, h, ang=ANGLE_STEP):
    """(du, dv, |Su| 평균, |Sv| 평균): 실제 길이 h, 굽은 쪽은 ANGLE_STEP / 곡률 이 되는 매개변수 간격 (SAMPLES² 점 중 가장 작게)."""
    from OCP.gp import gp_Pnt, gp_Vec
    du = dv = math.inf
    su, sv = [], []
    m = SAMPLES
    for i in range(m):
        for j in range(m):
            u = u0 + (u1 - u0) * (i + 0.5) / m
            v = v0 + (v1 - v0) * (j + 0.5) / m
            p, d1u, d1v, d2u, d2v, duv = gp_Pnt(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec()
            surf.D2(u, v, p, d1u, d1v, d2u, d2v, duv)
            a, b = d1u.Magnitude(), d1v.Magnitude()
            if a < 1e-12 or b < 1e-12:
                continue
            n = d1u.Crossed(d1v)
            if n.Magnitude() < 1e-12:
                continue
            n.Normalize()
            ku = abs(d2u.Dot(n)) / a ** 2
            kv = abs(d2v.Dot(n)) / b ** 2
            du = min(du, min(h, ang / max(ku, 1e-12)) / a)
            dv = min(dv, min(h, ang / max(kv, 1e-12)) / b)
            su.append(a)
            sv.append(b)
    if not su:
        return None
    a, b = float(np.mean(su)), float(np.mean(sv))
    # 길쭉함 한도: 한 방향 칸이 다른 방향의 ASPECT 배를 넘지 않게 (절곡 R 의 축 방향 칸을 줄임 — 바늘 삼각형 방지)
    pu, pv = du * a, dv * b
    pu, pv = min(pu, ASPECT * pv), min(pv, ASPECT * pu)
    return pu / a, pv / b, a, b


def _inside(P, A, B, chunk=2000):
    """점들이 경계 선분들 (A→B, 닫힌 고리들 — 순서·방향 상관없음) 안인가 (짝홀 규칙, 가로 반직선)."""
    out = np.zeros(len(P), bool)
    if not len(P) or not len(A):
        return out
    ay, by = A[:, 1][None, :], B[:, 1][None, :]
    ax, bx = A[:, 0][None, :], B[:, 0][None, :]
    dy = np.where(by - ay == 0, 1e-300, by - ay)
    for i in range(0, len(P), chunk):
        x, y = P[i:i + chunk, 0][:, None], P[i:i + chunk, 1][:, None]
        cr = ((ay > y) != (by > y)) & (x < ax + (y - ay) * (bx - ax) / dy)
        out[i:i + chunk] = (cr.sum(1) % 2) == 1
    return out


def mesh(faces, target=6000):
    """(V, F, N) 또는 None (못 만들면 — 이음매 없는 닫힌 면 등은 CAD 메시를 쓴다).
    점이 target 의 MAX_FACTOR 배를 넘으면 평평한 곳 간격만 1.5 배씩 키워 다시 — 그래도 많으면 (굽은 곳이 넓게 흩어진 큰
    외판) None (CAD 메시가 굽은 곳만 촘촘해 낫다)."""
    from OCP.BRepTools import BRepTools
    for f in faces:                  # 붙어 있는 CAD 메시를 지운다 — 있으면 면 안·밖 판정이 그 다각형을 써서 수백 배 느림
        BRepTools.Clean_s(f)
    for k in range(5):
        out = _mesh(faces, target, 1.5 ** k)
        if out is not _TOO_MANY:
            return out
    return None


_TOO_MANY = object()
MAX_FACTOR = 3.0


def _mesh(faces, target, scale):
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Curve2d, BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Pnt, gp_Pnt2d, gp_Vec, gp_Vec2d
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_IN, TopAbs_ON, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from scipy.spatial import Delaunay, cKDTree

    area = sum(_area(f) for f in faces)
    if area <= 0:
        return None
    h = math.sqrt(2 * area / target) * scale
    ang = ANGLE_STEP                  # 굽은 곳 칸 각은 그대로 (키우면 절곡·캐릭터 라인에서 현이 짧아져 변형이 틀림)
    emap = _Index()
    eparams = {}
    P3, PN = [], []                # 꼭짓점 (3D), 법선
    tris = []
    spacing = []
    for face in faces:
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        sp = _spacing(BRepAdaptor_Surface(face), u0, u1, v0, v1, h, ang)
        if sp is None:
            return None
        spacing.append(sp)
    est = sum(max(1, int((BRepTools.UVBounds_s(f)[1] - BRepTools.UVBounds_s(f)[0]) / sp[0]))
              * max(1, int((BRepTools.UVBounds_s(f)[3] - BRepTools.UVBounds_s(f)[2]) / sp[1]))
              for f, sp in zip(faces, spacing))
    if est > min(MAX_POINTS, MAX_FACTOR * target):     # 먼저 어림해 보고 많으면 바로 더 성글게 (모서리 나누기 전에)
        return _TOO_MANY
    # 모서리 나눔 간격 = 그 모서리를 가진 면들의 그 방향 격자 간격 중 작은 것 (경계와 안쪽 칸이 맞게 — 안 맞으면
    # 경계에 바늘 삼각형)
    estep = {}
    for face, (du, dv, a, b) in zip(faces, spacing):
        pu, pv = du * a, dv * b
        exp = TopExp_Explorer(face, TopAbs_EDGE)
        while exp.More():
            ed = TopoDS.Edge(exp.Current())
            k = emap.add(ed)
            try:
                c2 = BRepAdaptor_Curve2d(ed, face)
                p2, t2 = gp_Pnt2d(), gp_Vec2d()
                c2.D1(0.5 * (c2.FirstParameter() + c2.LastParameter()), p2, t2)
                x, y = t2.X() * a, t2.Y() * b
                L = math.hypot(x, y)
                st = 1 / math.hypot(x / L / pu, y / L / pv) if L > 1e-12 else h
            except Exception:
                st = h
            estep[k] = min(estep.get(k, h), st)
            exp.Next()
    for k in range(len(emap.items)):
        eparams[k] = _edge_params(emap.items[k], estep.get(k, h), ang)
    epts = {}
    for k, ps in eparams.items():
        if ps is None:
            continue
        c = BRepAdaptor_Curve(emap.items[k])
        epts[k] = np.array([[c.Value(t).X(), c.Value(t).Y(), c.Value(t).Z()] for t in ps])
    total_pts = 0
    for face, sp in zip(faces, spacing):
        surf = BRepAdaptor_Surface(face)
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        du, dv, Su, Sv = sp
        nu, nv = max(1, int((u1 - u0) / du)), max(1, int((v1 - v0) / dv))
        total_pts += nu * nv
        if total_pts > min(MAX_POINTS, MAX_FACTOR * target):
            return _TOO_MANY
        buv, b3, segs = [], [], []
        exp = TopExp_Explorer(face, TopAbs_EDGE)
        while exp.More():
            ed = TopoDS.Edge(exp.Current())
            k = emap.find(ed)
            ps = eparams.get(k)
            if ps is not None:
                c2 = BRepAdaptor_Curve2d(ed, face)
                start = len(buv)
                for t, q in zip(ps, epts[k]):
                    p2 = c2.Value(t)
                    buv.append((p2.X(), p2.Y()))
                    b3.append(q)
                segs += [(i, i + 1) for i in range(start, len(buv) - 1)]
            exp.Next()
        if len(buv) < 3:
            return None
        buv = np.array(buv)
        scale = np.array([Su, Sv])
        tree = cKDTree(buv * scale)
        gu = u0 + (np.arange(nu) + 0.5) * (u1 - u0) / nu
        gv = v0 + (np.arange(nv) + 0.5) * (v1 - v0) / nv
        G = np.array([(u, v) for u in gu for v in gv])
        S = np.array(segs, int).reshape(-1, 2)
        A, B = buv[S[:, 0]], buv[S[:, 1]]
        inner = np.zeros((0, 2))
        if len(G):
            dmin = 0.45 * min((u1 - u0) / nu * Su, (v1 - v0) / nv * Sv)
            dist, _ = tree.query(G * scale)
            G = G[dist > dmin]
            inner = G[_inside(G, A, B)]
        uv = np.vstack([buv, inner])
        try:
            tri = Delaunay(uv * scale)
        except Exception:
            return None
        base = len(P3)
        P3.extend(b3)
        rev = face.Orientation() == TopAbs_REVERSED
        for (u, v) in inner:
            p = surf.Value(u, v)
            P3.append(np.array([p.X(), p.Y(), p.Z()]))
        for (u, v) in uv:
            p, d1u, d1v = gp_Pnt(), gp_Vec(), gp_Vec()
            surf.D1(u, v, p, d1u, d1v)
            n = d1u.Crossed(d1v)
            m = n.Magnitude()
            nn = np.array([n.X(), n.Y(), n.Z()]) / m if m > 1e-12 else np.zeros(3)
            PN.append(-nn if rev else nn)
        simp = tri.simplices[_inside(uv[tri.simplices].mean(1), A, B)] + base
        tris += [(a, cc, b) if rev else (a, b, cc) for a, b, cc in simp.tolist()]
    V = np.array(P3, float)
    N = np.array(PN, float)
    F = np.array(tris, int)
    if len(F) < 2:
        return None
    # 이웃 면과 같은 경계 점 (같은 모서리에서 나왔거나 모서리 끝 꼭짓점) 을 하나로
    size = float(np.linalg.norm(V.max(0) - V.min(0))) or 1.0
    tol = max(1e-6 * size, 1e-5)
    tree = cKDTree(V)
    pairs = tree.query_pairs(tol, output_type="ndarray")
    parent = np.arange(len(V))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    root = np.array([find(i) for i in range(len(V))])
    uniq, inv = np.unique(root, return_inverse=True)
    Nn = np.zeros((len(uniq), 3))
    np.add.at(Nn, inv, N)
    L = np.linalg.norm(Nn, axis=1)
    Nn[L > 0] /= L[L > 0, None]
    F = inv[F]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    return V[uniq], F, Nn
