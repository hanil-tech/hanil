"""판금 솔리드를 평면으로 전개한다.

원리
----
판금은 두께가 일정한 판을 접은 것이라, 한쪽 겉면(스킨)만 보면
평면(플랜지)과 원통면(절곡부)이 매끄럽게 이어진 한 장의 면이다.

1. 가장 넓은 평면을 기준면으로 잡는다.
2. 기준면에서 출발해 매끄럽게(접선으로) 이어진 면만 따라가며 스킨을 모은다.
   두께 방향 옆면이나 구멍 벽은 스킨과 직각으로 만나므로 자연히 빠진다.
3. 각 면의 (u, v) 매개변수 공간을 평면 좌표로 옮기는 변환을 정한다.
   - 평면: 그대로 회전·이동만 한다.
   - 원통(절곡부): 둘레 방향 길이를 중립축 반지름으로 다시 잰다.
       중립축 반지름 = 안쪽 반지름 + K 계수 × 두께
   이웃한 면끼리는 공유 모서리에서 정확히 맞물리도록 이어 붙인다.
4. 스킨 면들의 바깥 모서리를 옮겨 그리면 전개도의 절단선이 된다.
   절곡부 가운데에는 절곡선을 그린다.

변환이 모두 (u, v) 에 대해 일차식이라 직선은 직선으로, 평면 위의 원은 원으로 남는다.
그래서 구멍과 라운드가 레이저 가공용 DXF 에 원·호로 정확히 나온다.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Curve2d, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

# 두 면의 법선이 이 각도 안이면 매끄럽게 이어진 것으로 본다.
TANGENT_COS = math.cos(math.radians(3.0))
# 면 안쪽을 확인할 때 모서리에서 떨어뜨리는 거리(mm)
_PROBE = 0.02


class UnfoldError(Exception):
    pass


# ---------------------------------------------------------------- 결과 형식

@dataclass
class Line:
    p1: tuple
    p2: tuple
    layer: str = "CUT"


@dataclass
class Arc:
    """반시계 방향 호. full=True 이면 완전한 원."""
    center: tuple
    radius: float
    start_deg: float = 0.0
    end_deg: float = 360.0
    full: bool = False
    layer: str = "CUT"


@dataclass
class Polyline:
    points: list
    layer: str = "CUT"


@dataclass
class Bend:
    number: int
    angle_deg: float
    inner_radius: float
    direction: str          # "UP" / "DOWN"  (전개도를 앞에서 본 기준)
    length: float           # 절곡선 길이
    allowance: float        # 펼친 길이 (절곡 여유)
    line: tuple             # ((x1, y1), (x2, y2))


@dataclass
class UnfoldResult:
    thickness: float
    k_factor: float
    entities: list
    bends: list
    warnings: list = field(default_factory=list)
    face_count: int = 0

    @property
    def bbox(self):
        pts = list(_entity_points(self.entities))
        if not pts:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def size(self):
        x0, y0, x1, y1 = self.bbox
        return (x1 - x0, y1 - y0)


def _entity_points(entities):
    for e in entities:
        if isinstance(e, Line):
            yield e.p1
            yield e.p2
        elif isinstance(e, Polyline):
            yield from e.points
        elif isinstance(e, Arc):
            cx, cy = e.center
            if e.full:
                yield (cx - e.radius, cy - e.radius)
                yield (cx + e.radius, cy + e.radius)
            else:
                a0, a1 = e.start_deg, e.end_deg
                if a1 < a0:
                    a1 += 360.0
                # 시작·끝과 그 사이에 걸리는 0/90/180/270 도 점
                angles = [a0, a1] + [a for a in range(0, 721, 90) if a0 < a < a1]
                for a in angles:
                    r = math.radians(a)
                    yield (cx + e.radius * math.cos(r), cy + e.radius * math.sin(r))


# ---------------------------------------------------------------- 모양 색인

class _ShapeIndex:
    """같은 모양(IsSame)을 같은 번호로 묶는다. OCP 의 hash 가 IsSame 기준이다."""

    def __init__(self):
        self._buckets: dict = {}
        self.items: list = []

    def add(self, shape) -> int:
        idx = self.find(shape)
        if idx is not None:
            return idx
        self.items.append(shape)
        idx = len(self.items) - 1
        self._buckets.setdefault(hash(shape), []).append(idx)
        return idx

    def find(self, shape):
        for idx in self._buckets.get(hash(shape), ()):
            if self.items[idx].IsSame(shape):
                return idx
        return None


def _explore(shape, kind):
    exp = TopExp_Explorer(shape, kind)
    while exp.More():
        yield exp.Current()
        exp.Next()


# ---------------------------------------------------------------- 면 정보

@dataclass
class _Face:
    index: int
    face: object
    kind: str                     # "plane" / "cylinder" / "other"
    area: float
    su: float = 1.0               # u 를 길이로 바꾸는 배율 (원통은 중립 반지름)
    # 평면 좌표 = C + A @ (su*u, v)
    A: np.ndarray | None = None
    C: np.ndarray | None = None
    radius: float = 0.0
    convex: bool = False
    inner_radius: float = 0.0
    parent: int | None = None
    parent_edge: int | None = None

    def to_flat(self, u, v):
        return self.C + self.A @ np.array([self.su * u, v])


def _surface_normal(face, u, v) -> np.ndarray:
    """면의 바깥쪽 법선 (면 방향 반영)."""
    surf = BRepAdaptor_Surface(face)
    p, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    surf.D1(u, v, p, du, dv)
    n = du.Crossed(dv)
    if n.Magnitude() < 1e-12:
        return np.zeros(3)
    n.Normalize()
    if face.Orientation() == TopAbs_REVERSED:
        n.Reverse()
    return np.array([n.X(), n.Y(), n.Z()])


def _face_area(face) -> float:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.Mass()


def _classify_in(face, u, v) -> bool:
    return BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-9).State() == TopAbs_IN


def _interior_uv(face):
    """면 안쪽의 한 점 (u, v)."""
    u0, u1, v0, v1 = _uv_bounds(face)
    for n in (1, 3, 5, 9, 17):
        for i in range(n):
            for j in range(n):
                u = u0 + (u1 - u0) * (i + 0.5) / n
                v = v0 + (v1 - v0) * (j + 0.5) / n
                if _classify_in(face, u, v):
                    return u, v
    return (u0 + u1) / 2, (v0 + v1) / 2


def _uv_bounds(face):
    s = BRepAdaptor_Surface(face, True)
    return s.FirstUParameter(), s.LastUParameter(), s.FirstVParameter(), s.LastVParameter()


def _pnt(p) -> np.ndarray:
    return np.array([p.X(), p.Y(), p.Z()])


# ---------------------------------------------------------------- 본체

class SheetMetalUnfolder:
    def __init__(self, solid, k_factor: float = 0.44, thickness: float | None = None):
        self.solid = solid
        self.k = float(k_factor)
        self.user_thickness = thickness
        self.warnings: list = []

        self.faces = _ShapeIndex()
        self.edges = _ShapeIndex()
        self.info: list[_Face] = []
        self.edge_faces: dict[int, list[int]] = {}

        for f in _explore(solid, TopAbs_FACE):
            face = TopoDS.Face(f)
            if self.faces.find(face) is not None:
                continue
            idx = self.faces.add(face)
            kind = {GeomAbs_Plane: "plane", GeomAbs_Cylinder: "cylinder"}.get(
                BRepAdaptor_Surface(face).GetType(), "other")
            self.info.append(_Face(idx, face, kind, _face_area(face)))
            for e in _explore(face, TopAbs_EDGE):
                edge = TopoDS.Edge(e)
                if BRep_Tool.Degenerated_s(edge):
                    continue
                ei = self.edges.add(edge)
                lst = self.edge_faces.setdefault(ei, [])
                if idx not in lst:
                    lst.append(idx)

    # ---- 단계 1: 기준면과 두께

    def _pick_root(self) -> _Face:
        # 판금의 겉면은 옆면(두께 면)보다 훨씬 넓다. 말아 만든 관이면 원통면이 가장 넓다.
        pool = [f for f in self.info if f.kind in ("plane", "cylinder")]
        if not pool:
            raise UnfoldError("평면이나 원통면이 없어 판금으로 볼 수 없습니다.")
        return max(pool, key=lambda f: f.area)

    def _measure_thickness(self, root: _Face) -> float:
        u, v = _interior_uv(root.face)
        p = BRepAdaptor_Surface(root.face).Value(u, v)
        n = _surface_normal(root.face, u, v)
        # 바깥 법선 반대쪽(재료 안쪽)으로 빛을 쏴 반대편 면까지 거리를 잰다.
        line = gp_Lin(p, gp_Dir(-n[0], -n[1], -n[2]))
        hit = IntCurvesFace_ShapeIntersector()
        hit.Load(self.solid, 1e-6)
        hit.Perform(line, 1e-4, 1e7)
        dists = [hit.WParameter(i) for i in range(1, hit.NbPnt() + 1)]
        dists = [d for d in dists if d > 1e-4]
        if not dists:
            raise UnfoldError("두께를 잴 수 없습니다. 두께를 직접 입력해 주세요.")
        return min(dists)

    # ---- 단계 2: 스킨 모으기

    def _edge_param_mid(self, edge, face):
        c = BRepAdaptor_Curve2d(edge, face)
        t = 0.5 * (c.FirstParameter() + c.LastParameter())
        p = c.Value(t)
        return p.X(), p.Y()

    def _tangent(self, ei: int, fa: int, fb: int) -> bool:
        edge = self.edges.items[ei]
        A, B = self.info[fa], self.info[fb]
        try:
            ua, va = self._edge_param_mid(edge, A.face)
            ub, vb = self._edge_param_mid(edge, B.face)
        except Exception:
            return False
        na = _surface_normal(A.face, ua, va)
        nb = _surface_normal(B.face, ub, vb)
        return float(na @ nb) > TANGENT_COS

    def _collect_skin(self, root: _Face) -> set:
        skin = {root.index}
        queue = deque([root.index])
        face_edges = self._face_edge_indices()
        while queue:
            fi = queue.popleft()
            for ei in face_edges[fi]:
                for fj in self.edge_faces[ei]:
                    if fj in skin or fj == fi:
                        continue
                    if self._tangent(ei, fi, fj):
                        skin.add(fj)
                        queue.append(fj)
        return skin

    def _face_edge_indices(self):
        if not hasattr(self, "_fe"):
            self._fe = {f.index: [] for f in self.info}
            for ei, fs in self.edge_faces.items():
                for fi in fs:
                    self._fe[fi].append(ei)
        return self._fe

    # ---- 단계 3: 펼치기

    def _setup_cylinder(self, f: _Face, t: float):
        surf = BRepAdaptor_Surface(f.face)
        cyl = surf.Cylinder()
        f.radius = cyl.Radius()
        u0, u1, v0, v1 = _uv_bounds(f.face)
        um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
        p = _pnt(surf.Value(um, vm))
        ax = cyl.Axis()
        o = _pnt(ax.Location())
        d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        radial = (p - o) - ((p - o) @ d) * d
        n = _surface_normal(f.face, um, vm)
        f.convex = float(n @ radial) > 0
        f.inner_radius = f.radius - t if f.convex else f.radius
        if f.inner_radius < -1e-3:
            self.warnings.append(
                f"절곡 반지름이 두께보다 작습니다 (R{f.radius:.2f}, 두께 {t:.2f}).")
            f.inner_radius = 0.0
        f.su = f.inner_radius + self.k * t

    def _inward_dir(self, f: _Face, edge, S1, S2):
        """모서리(S1→S2, 배율 적용 uv)에서 면 안쪽을 향하는 수직 방향."""
        d = S2 - S1
        d = d / np.linalg.norm(d)
        perp = np.array([-d[1], d[0]])
        Sm = 0.5 * (S1 + S2)
        for sign in (1.0, -1.0):
            q = Sm + sign * _PROBE * perp
            if _classify_in(f.face, q[0] / f.su, q[1]):
                return d, sign * perp
        # 아주 좁은 면이면 탐침을 더 짧게
        for sign in (1.0, -1.0):
            q = Sm + sign * _PROBE * 0.05 * perp
            if _classify_in(f.face, q[0] / f.su, q[1]):
                return d, sign * perp
        raise UnfoldError("면의 안쪽 방향을 판단하지 못했습니다.")

    def _edge_points(self, edge, f: _Face):
        c = BRepAdaptor_Curve2d(edge, f.face)
        a, b = c.FirstParameter(), c.LastParameter()
        p1, p2 = c.Value(a), c.Value(b)
        S1 = np.array([f.su * p1.X(), p1.Y()])
        S2 = np.array([f.su * p2.X(), p2.Y()])
        return S1, S2

    def _place_root(self, root: _Face):
        root.A = np.eye(2)
        if root.face.Orientation() == TopAbs_REVERSED:
            # 바깥쪽에서 바라본 모습이 되도록 뒤집는다.
            root.A = np.diag([1.0, -1.0])
        root.C = np.zeros(2)

    def _place_child(self, parent: _Face, child: _Face, ei: int):
        edge = self.edges.items[ei]
        P1, P2 = self._edge_points(edge, parent)
        S1, S2 = self._edge_points(edge, child)
        F1, F2 = parent.C + parent.A @ P1, parent.C + parent.A @ P2

        dp, np_in = self._inward_dir(parent, edge, P1, P2)
        dc, nc_in = self._inward_dir(child, edge, S1, S2)

        df = F2 - F1
        df /= np.linalg.norm(df)
        nf = parent.A @ np_in
        nf -= (nf @ df) * df
        nf /= np.linalg.norm(nf)

        # 자식 면은 공유 모서리를 기준으로 부모 반대편에 놓인다.
        Mf = np.column_stack([df, -nf])
        Mc = np.column_stack([dc, nc_in])
        child.A = Mf @ Mc.T
        child.C = F1 - child.A @ S1

    def unfold(self) -> UnfoldResult:
        root = self._pick_root()
        t = self.user_thickness or self._measure_thickness(root)
        if t <= 0:
            raise UnfoldError("두께가 0 입니다.")

        skin = self._collect_skin(root)
        unsupported = [fi for fi in skin if self.info[fi].kind == "other"]
        if unsupported:
            self.warnings.append(
                f"평면·원통이 아닌 면 {len(unsupported)}개는 전개에서 뺐습니다 "
                "(원뿔·자유곡면 절곡은 지원하지 않습니다).")
            skin -= set(unsupported)

        for fi in skin:
            if self.info[fi].kind == "cylinder":
                self._setup_cylinder(self.info[fi], t)
        if root.kind == "cylinder" and root.su <= 0:
            raise UnfoldError("원통 반지름을 판단하지 못했습니다.")

        # 기준면부터 넓이 우선으로 이어 붙인다.
        self._place_root(root)
        placed = {root.index}
        tree_edges = set()
        queue = deque([root.index])
        face_edges = self._face_edge_indices()
        while queue:
            fi = queue.popleft()
            for ei in face_edges[fi]:
                for fj in self.edge_faces[ei]:
                    if fj not in skin or fj in placed:
                        continue
                    if not self._is_straight(ei):
                        continue
                    self._place_child(self.info[fi], self.info[fj], ei)
                    self.info[fj].parent = fi
                    self.info[fj].parent_edge = ei
                    placed.add(fj)
                    tree_edges.add(ei)
                    queue.append(fj)

        missing = skin - placed
        if missing:
            self.warnings.append(f"이어 붙이지 못한 면 {len(missing)}개가 있습니다.")

        entities = []
        for fi in sorted(placed):
            f = self.info[fi]
            for e in _explore(f.face, TopAbs_EDGE):
                edge = TopoDS.Edge(e)
                if BRep_Tool.Degenerated_s(edge):
                    continue
                if self.edges.find(edge) in tree_edges:
                    continue
                entities.extend(self._map_edge(edge, f))

        entities = _join_collinear(_merge_duplicates(entities))
        bends = self._bends(placed, t)
        for b in bends:
            entities.append(Line(*b.line, layer="BEND"))

        result = UnfoldResult(
            thickness=t, k_factor=self.k, entities=entities, bends=bends,
            warnings=self.warnings, face_count=len(placed))
        result.entities = _normalize_origin(result)
        return result

    def _is_straight(self, ei: int) -> bool:
        return BRepAdaptor_Curve(self.edges.items[ei]).GetType() == GeomAbs_Line

    # ---- 단계 4: 모서리 그리기

    def _map_edge(self, edge, f: _Face):
        c = BRepAdaptor_Curve2d(edge, f.face)
        a, b = c.FirstParameter(), c.LastParameter()

        def flat(t):
            p = c.Value(t)
            return tuple(float(x) for x in f.to_flat(p.X(), p.Y()))

        kind = c.GetType()
        if kind == GeomAbs_Line:
            return [Line(flat(a), flat(b))]

        if kind == GeomAbs_Circle and f.kind == "plane":
            circ = c.Circle()
            ctr = circ.Location()
            center = tuple(float(x) for x in f.to_flat(ctr.X(), ctr.Y()))
            r = circ.Radius()
            if abs(abs(b - a) - 2 * math.pi) < 1e-7:
                return [Arc(center, r, full=True)]
            p0, pm, p1 = flat(a), flat(0.5 * (a + b)), flat(b)
            ang = lambda p: math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360
            s, m, e = ang(p0), ang(pm), ang(p1)
            # 반시계로 s→e 사이에 m 이 있으면 그대로, 아니면 뒤집는다.
            if (m - s) % 360 > (e - s) % 360:
                s, e = e, s
            return [Arc(center, r, s, e)]

        # 그 밖의 곡선은 잘게 나눠 폴리라인으로
        length = _curve_length_estimate(c, a, b, f)
        n = int(min(400, max(16, length / 0.5)))
        pts = [flat(a + (b - a) * i / n) for i in range(n + 1)]
        return [Polyline(pts)]

    def _bends(self, placed, t):
        bends = []
        for fi in sorted(placed):
            f = self.info[fi]
            if f.kind != "cylinder":
                continue
            u0, u1, v0, v1 = _uv_bounds(f.face)
            angle = u1 - u0
            if angle >= 2 * math.pi - 1e-6:
                # 둥근 관처럼 한 바퀴 도는 면은 절곡이 아니라 말아 붙인 것
                continue
            um = 0.5 * (u0 + u1)
            vs = self._v_range_at(f, um, v0, v1)
            p1 = tuple(float(x) for x in f.to_flat(um, vs[0]))
            p2 = tuple(float(x) for x in f.to_flat(um, vs[1]))
            bends.append(Bend(
                number=0,
                angle_deg=math.degrees(angle),
                inner_radius=f.inner_radius,
                direction="DOWN" if f.convex else "UP",
                length=abs(vs[1] - vs[0]),
                allowance=angle * f.su,
                line=(p1, p2),
            ))
        bends.sort(key=lambda b: (round(b.line[0][1], 3), round(b.line[0][0], 3)))
        for i, b in enumerate(bends, 1):
            b.number = i
        return bends

    def _v_range_at(self, f: _Face, u, v0, v1):
        """u 위치에서 면 안에 들어가는 v 범위 (절곡선 길이)."""
        n = 200
        vs = [v0 + (v1 - v0) * i / n for i in range(n + 1)]
        inside = [i for i, v in enumerate(vs) if _classify_in(f.face, u, v)]
        if not inside:
            return v0, v1
        i0, i1 = inside[0], inside[-1]
        lo = _boundary(f, u, vs[i0], vs[i0 - 1]) if i0 > 0 else v0
        hi = _boundary(f, u, vs[i1], vs[i1 + 1]) if i1 < n else v1
        return lo, hi


def _boundary(f, u, v_in, v_out):
    """면 안의 v_in 과 밖의 v_out 사이를 이분해 경계를 찾는다."""
    a, b = v_in, v_out
    for _ in range(40):
        m = 0.5 * (a + b)
        if _classify_in(f.face, u, m):
            a = m
        else:
            b = m
    return 0.5 * (a + b)


def _curve_length_estimate(c, a, b, f):
    pts = [f.to_flat(c.Value(a + (b - a) * i / 16).X(), c.Value(a + (b - a) * i / 16).Y())
           for i in range(17)]
    return sum(float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(16))


def _merge_duplicates(entities):
    """서로 다른 면에서 같은 선이 두 번 나오는 것을 하나로."""
    seen = set()
    out = []
    for e in entities:
        if isinstance(e, Line):
            a = (round(e.p1[0], 4), round(e.p1[1], 4))
            b = (round(e.p2[0], 4), round(e.p2[1], 4))
            if a == b:
                continue
            key = ("L", e.layer) + tuple(sorted([a, b]))
        elif isinstance(e, Arc):
            key = ("A", e.layer, round(e.center[0], 4), round(e.center[1], 4),
                   round(e.radius, 4), e.full,
                   None if e.full else round(e.start_deg, 3),
                   None if e.full else round(e.end_deg, 3))
        else:
            key = None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        out.append(e)
    return out


def _join_collinear(entities):
    """한 직선 위에서 끝이 맞닿은 선분들을 하나로 잇는다 (절곡 접선에서 끊긴 외곽선)."""
    lines = [e for e in entities if isinstance(e, Line)]
    others = [e for e in entities if not isinstance(e, Line)]
    changed = True
    while changed:
        changed = False
        ends = {}
        for i, ln in enumerate(lines):
            for p in (ln.p1, ln.p2):
                ends.setdefault((round(p[0], 4), round(p[1], 4)), []).append(i)
        for key, idx in ends.items():
            if len(idx) != 2:
                continue
            a, b = lines[idx[0]], lines[idx[1]]
            if a.layer != b.layer:
                continue
            fa = a.p2 if _close(a.p1, key) else a.p1
            fb = b.p2 if _close(b.p1, key) else b.p1
            da = np.subtract(fa, key)
            db = np.subtract(fb, key)
            na, nb = np.linalg.norm(da), np.linalg.norm(db)
            if na < 1e-9 or nb < 1e-9:
                continue
            if float(da @ db) / (na * nb) > -1 + 1e-10:
                continue
            lines[idx[0]] = Line(fa, fb, a.layer)
            del lines[idx[1]]
            changed = True
            break
    return lines + others


def _close(p, key):
    return abs(p[0] - key[0]) < 1e-4 and abs(p[1] - key[1]) < 1e-4


def _normalize_origin(result: UnfoldResult):
    """전개도 왼쪽 아래 구석을 원점(0, 0)으로 옮긴다."""
    x0, y0, _, _ = result.bbox
    off = (x0, y0)

    def sh(p):
        return (p[0] - off[0], p[1] - off[1])

    out = []
    for e in result.entities:
        if isinstance(e, Line):
            out.append(Line(sh(e.p1), sh(e.p2), e.layer))
        elif isinstance(e, Arc):
            out.append(Arc(sh(e.center), e.radius, e.start_deg, e.end_deg, e.full, e.layer))
        else:
            out.append(Polyline([sh(p) for p in e.points], e.layer))
    for b in result.bends:
        b.line = (sh(b.line[0]), sh(b.line[1]))
    return out


def unfold(solid, k_factor: float = 0.44, thickness: float | None = None) -> UnfoldResult:
    return SheetMetalUnfolder(solid, k_factor, thickness).unfold()
