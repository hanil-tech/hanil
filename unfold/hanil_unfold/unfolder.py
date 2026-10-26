"""판금 솔리드를 평면으로 전개한다.

원리
----
판금은 두께가 일정한 판을 접은 것이라, 한쪽 겉면(스킨)만 보면
평면(플랜지)과 원통·원뿔면(절곡부)이 매끄럽게 이어진 한 장의 면이다.

1. 가장 넓은 면을 기준면으로 잡는다.
2. 기준면에서 출발해 매끄럽게(접선으로) 이어진 면만 따라가며 스킨을 모은다.
   두께 방향 옆면이나 구멍 벽은 스킨과 직각으로 만나므로 자연히 빠진다.
3. 면마다 (u, v) 매개변수를 펼친 좌표("기본 전개")로 옮기는 식을 둔다.
   - 평면: 그대로.
   - 원통(절곡부): 둘레 방향 길이를 중립축 기준으로 다시 잰다.
       펼친 폭 = 절곡각 × (안쪽 R + K × 두께)   (bendcalc 에서 재질·상형 R 로 계산)
   - 원뿔(깔때기·경사 절곡): 꼭짓점을 중심으로 한 부채꼴로 편다.
       반지름 = 꼭짓점에서 모선 방향 거리 (중립면 기준),  각도 = u × sin(반각)
   기본 전개를 회전·이동해 이웃한 면과 공유 모서리에서 정확히 맞물리게 이어 붙인다.
   그래서 직각이 아닌 절곡(45°, 120°, 비스듬한 절곡선)과 원뿔도 같은 방법으로 펼친다.
4. 스킨 면들의 바깥 모서리를 옮겨 그리면 전개도의 절단선이 된다.
   절곡부 가운데에는 절곡선을 그린다.

평면·원통은 변환이 (u, v) 의 일차식이라 직선은 직선으로, 평면 위의 원은 원으로 남는다.
원뿔의 둘레 방향 모서리는 꼭짓점을 중심으로 한 호가 된다.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Curve2d, BRepAdaptor_Surface
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import (GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_Circle, GeomAbs_Cone,
                          GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_OffsetSurface, GeomAbs_Plane,
                          GeomAbs_SurfaceOfExtrusion)
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt, gp_Pnt2d, gp_Vec, gp_Vec2d
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN, TopAbs_REVERSED, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from .bendcalc import BendCalc, BendSettings

# 전개 방식
AUTO, SHEET, FORMING = "auto", "sheet", "forming"
MODE_NAMES = {
    AUTO: "자동 (판금이면 정확, 곡면이면 근사)",
    SHEET: "판금 (정확 전개)",
    FORMING: "성형품 (곡면 근사 전개)",
}

# 두 면의 법선이 이 각도 안이면 매끄럽게 이어진 것으로 본다.
TANGENT_COS = math.cos(math.radians(3.0))
# 면 안쪽을 확인할 때 모서리에서 떨어뜨리는 거리(mm)
_PROBE = 0.02
# 자유곡선 (스플라인) 모서리를 폴리라인으로 옮길 때 현의 최대 오차 (mm)
CHORD_TOL = 0.005


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
    kind: str               # "원통" / "원뿔"
    angle_deg: float        # 접은 각도 (두 플랜지 법선 사이 각)
    inner_radius: float     # 계산에 쓴 안쪽 R (원뿔은 평균)
    model_radius: float     # 3D 모델의 안쪽 R
    k: float
    direction: str          # "UP" / "DOWN"  (전개도를 앞에서 본 기준)
    length: float           # 절곡선 길이
    allowance: float        # 펼친 절곡부 길이 (BA)
    deduction: float        # 이 각도의 연신 (BD)
    deduction90: float      # 같은 조건 90° 연신
    source: str             # 값의 출처
    line: tuple             # ((x1, y1), (x2, y2))
    radius_text: str = ""


@dataclass
class FormingInfo:
    """성형품 근사 전개의 메시와 변형 (펼친 좌표 U 는 전개도와 같은 좌표계)."""
    U: np.ndarray            # 펼친 꼭짓점 (n, 2)
    F: np.ndarray            # 삼각형 (m, 3)
    ratio: np.ndarray        # 삼각형별 넓이 비 = 제품 / 블랭크
    major: np.ndarray        # 주 진변형률
    minor: np.ndarray
    product_area: float      # 두께 가운데 면 넓이
    blank_area: float
    reliable: np.ndarray | None = None   # 모양이 괜찮은 삼각형 (가장 작은 각 > 5°)
    method: str = "ARAP"
    flc0: float = 0.0        # 평면 변형 성형 한계 (진변형률), 0 = 판정 안 함
    material: str = ""
    V: np.ndarray | None = None   # 제품 (두께 가운데 면) 꼭짓점 (n, 3) — 성형 해석 3D 그림
    cylinders: list = field(default_factory=list)   # 원통 면 (반지름, 축 방향) — 사각 드로잉 귀 R 판정
    membrane: tuple | None = None    # 보정 전 원스텝 (막) 변형률 (major, minor) — 드로잉 보정을 했을 때
    correction: dict | None = None   # drawcorr.correct 의 설명 (장력·다이 R·얇아짐 몫)

    def _weights(self):
        w = _tri_areas2(self.U, self.F)
        if self.reliable is not None and self.reliable.any():
            w = w * self.reliable
        return w / max(w.sum(), 1e-30)

    @property
    def risk(self):
        """삼각형별 주 변형률 / 성형 한계 (1 이상 = 파단 위험)."""
        from .forming import flc_risk
        if self.flc0 <= 0:
            return np.zeros(len(self.F))
        return flc_risk(self.major, self.minor, self.flc0, self.material)

    @property
    def wrinkle(self):
        """두께가 5 % 넘게 늘고 부 변형률이 압축인 삼각형 (주름 가능)."""
        return (-(self.major + self.minor) > 0.05) & (self.minor < 0)

    @property
    def flc_summary(self):
        """(파단 위험 넓이 비, 한계 근처 0.8~1 넓이 비, 주름 넓이 비, 가장 큰 risk).
        가장 큰 값은 넓이 기준 위 0.5 % 를 뺀 값 (메시 조각 삼각형 때문에 튀지 않게)."""
        w = self._weights()
        rk = self.risk
        order = np.argsort(rk)
        cw = np.cumsum(w[order])
        top = float(rk[order][min(np.searchsorted(cw, 0.995 * cw[-1]), len(rk) - 1)]) if len(rk) else 0.0
        return (float(w[rk >= 1].sum()), float(w[(rk >= 0.8) & (rk < 1)].sum()),
                float(w[self.wrinkle].sum()), top)

    @property
    def thinning(self):
        """삼각형별 두께 감소율 (+ 얇아짐, − 두꺼워짐)."""
        return 1.0 - 1.0 / self.ratio

    @property
    def thinning_range(self):
        """(가장 많이 두꺼워짐, 가장 많이 얇아짐). 바늘 같은 조각 삼각형과
        넓이 기준 위아래 0.5 % 는 빼서, 메시 탓에 튀는 값이 판정을 흔들지 않게 한다."""
        th = self.thinning
        w = _tri_areas2(self.U, self.F)
        if self.reliable is not None and self.reliable.any():
            th, w = th[self.reliable], w[self.reliable]
        order = np.argsort(th)
        cw = np.cumsum(w[order]) / w.sum()
        lo = th[order][np.searchsorted(cw, 0.005)]
        hi = th[order][min(np.searchsorted(cw, 0.995), len(th) - 1)]
        return float(lo), float(hi)


@dataclass
class UnfoldResult:
    thickness: float
    k_factor: float
    entities: list
    bends: list
    warnings: list = field(default_factory=list)
    face_count: int = 0
    settings_text: str = ""
    rolled: list = field(default_factory=list)   # 말아 만든 원통·원뿔 설명
    mode: str = SHEET                             # 실제로 쓴 전개 방식
    forming: FormingInfo | None = None
    coverage: float = 1.0                         # 펼친 겉면 넓이 × 두께 / 부품 부피
    advice: list = field(default_factory=list)    # 정확도 알림 (K·실제 R) — 형상 오류인 warnings 와 따로

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

_KINDS = {GeomAbs_Plane: "plane", GeomAbs_Cylinder: "cylinder", GeomAbs_Cone: "cone"}
# 곡선을 민 면 (일반 원통) 일 수 있는 곡면: 단면이 3차 스플라인·베지어인 절곡·곡면 판
_MAYBE_RULED = (GeomAbs_SurfaceOfExtrusion, GeomAbs_BSplineSurface, GeomAbs_BezierSurface, GeomAbs_OffsetSurface)
RULED_KIND = "곡선 단면"
RULED_SAMPLES = 801


def _ruling(face):
    """면이 한 방향으로 곧은 선을 민 꼴 (일반 원통: 모든 단면이 같은 곡선) 이면 (민 방향 D, 단면 매개변수 'u'/'v'),
    아니면 None. 7 × 7 점에서 한 매개변수 방향의 선이 곧고 (휨 < 2 µm·길이 비례) 서로 나란한지 (0.05°) 본다.
    평면은 미리 평면으로 알아본다."""
    surf = BRepAdaptor_Surface(face)
    u0, u1, v0, v1 = _uv_bounds(face)
    if not (u1 > u0 and v1 > v0):
        return None
    n = 7
    us = np.linspace(u0, u1, n)
    vs = np.linspace(v0, v1, n)
    P = np.array([[_pnt(surf.Value(float(u), float(v))) for v in vs] for u in us])     # (u, v, 3)
    size = float(np.linalg.norm(P.reshape(-1, 3).max(0) - P.reshape(-1, 3).min(0))) or 1.0
    for across in ("u", "v"):
        L = P if across == "u" else np.transpose(P, (1, 0, 2))   # L[i] = 곧아야 할 선 (단면 매개변수 i 고정)
        d = L[:, -1] - L[:, 0]
        ln = np.linalg.norm(d, axis=1)
        if ln.min() < 1e-6 * size:
            continue
        D = d / ln[:, None]
        if np.min(D @ D[0]) < math.cos(math.radians(0.05)):
            continue
        rel = L - L[:, :1]
        off = rel - (rel @ D[0])[..., None] * D[0]
        if np.abs(np.linalg.norm(off, axis=2)).max() > 2e-3 + 1e-5 * size:
            continue
        # 단면이 사실상 직선이면 평면 (평면 인식이 놓친 것) — 그래도 같은 식으로 펼칠 수 있다
        return D[0], across
    return None


@dataclass
class _Face:
    index: int
    face: object
    kind: str                     # "plane" / "cylinder" / "cone" / "other"
    area: float
    # 펼친 좌표 = C + A @ canon(u, v)   (A 는 회전 또는 대칭)
    A: np.ndarray | None = None
    C: np.ndarray | None = None
    convex: bool = False          # 바깥쪽(재료 반대편)으로 볼록한 면
    # 원통
    radius: float = 0.0
    inner_radius: float = 0.0
    su: float = 1.0               # 둘레 1 라디안이 펼친 길이로 몇 mm 인가
    calc: BendCalc | None = None
    # 원뿔
    ref_radius: float = 0.0
    sin_a: float = 0.0
    s_shift: float = 0.0          # 중립면으로 옮길 때 꼭짓점 거리 보정
    k: float = 0.0
    parent: int | None = None
    # 곡선 단면 (일반 원통): 민 방향, 단면 매개변수 ('u'/'v'), 단면 매개변수 → 중립선 길이 표
    ruled_dir: np.ndarray | None = None
    across: str = "u"
    tab_p: np.ndarray | None = None
    tab_s: np.ndarray | None = None
    groups: list = field(default_factory=list)
    surf: object = None

    def canon(self, u, v):
        if self.kind == "cylinder":
            return np.array([self.su * u, v])
        if self.kind == "ruled":
            a = u if self.across == "u" else v
            p, s = self.tab_p, self.tab_s
            if a < p[0]:
                sv = s[0] + (a - p[0]) * (s[1] - s[0]) / (p[1] - p[0])
            elif a > p[-1]:
                sv = s[-1] + (a - p[-1]) * (s[-1] - s[-2]) / (p[-1] - p[-2])
            else:
                sv = float(np.interp(a, p, s))
            return np.array([sv, float(_pnt(self.surf.Value(u, v)) @ self.ruled_dir)])
        if self.kind == "cone":
            sa = abs(self.sin_a)
            s = (self.ref_radius + v * self.sin_a) / sa + self.s_shift
            phi = u * sa
            return np.array([s * math.cos(phi), s * math.sin(phi)])
        return np.array([u, v])

    def to_flat(self, u, v):
        return self.C + self.A @ self.canon(u, v)


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


def _axis_radial(ax, p):
    """축에서 점 p 로 향하는 수직 벡터."""
    o = _pnt(ax.Location())
    d = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
    w = p - o
    return w - (w @ d) * d


# ---------------------------------------------------------------- 본체

class SheetMetalUnfolder:
    def __init__(self, solid, settings: BendSettings | None = None, thickness: float | None = None,
                 mode: str = AUTO):
        self.solid = solid
        self.settings = settings or BendSettings()
        self.user_thickness = thickness
        self.mode = mode
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
            st = BRepAdaptor_Surface(face).GetType()
            kind = _KINDS.get(st, "other")
            info = _Face(idx, face, kind, _face_area(face))
            if kind == "other" and st in _MAYBE_RULED:
                try:
                    rl = _ruling(face)
                except Exception:
                    rl = None
                if rl is not None:
                    info.kind, info.ruled_dir, info.across = "ruled", rl[0], rl[1]
            self.info.append(info)
            for e in _explore(face, TopAbs_EDGE):
                edge = TopoDS.Edge(e)
                if BRep_Tool.Degenerated_s(edge):
                    continue
                ei = self.edges.add(edge)
                lst = self.edge_faces.setdefault(ei, [])
                if idx not in lst:
                    lst.append(idx)

        self._straight: dict[int, bool] = {}
        self._fe = {f.index: [] for f in self.info}
        for ei, fs in self.edge_faces.items():
            for fi in fs:
                self._fe[fi].append(ei)

    # ---- 단계 1: 기준면과 두께

    def _pick_root(self) -> _Face:
        # 판금·성형품의 겉면은 옆면(두께 면)보다 훨씬 넓다.
        if not self.info:
            raise UnfoldError("면이 없습니다.")
        return max(self.info, key=lambda f: f.area)

    def _measure_thickness(self, root: _Face) -> float:
        """기준면 여러 곳에서 재료 안쪽으로 빛을 쏴 반대편 면까지 거리를 재고 가운데 값.

        한 곳만 재면 덧댄 판·리브 밑에서 두께가 크게 나온다."""
        surf = BRepAdaptor_Surface(root.face)
        u0, u1, v0, v1 = _uv_bounds(root.face)
        pts = [_interior_uv(root.face)]
        for i in range(3):
            for j in range(3):
                u = u0 + (u1 - u0) * (i + 0.5) / 3
                v = v0 + (v1 - v0) * (j + 0.5) / 3
                if _classify_in(root.face, u, v):
                    pts.append((u, v))
        hit = IntCurvesFace_ShapeIntersector()
        hit.Load(self.solid, 1e-6)
        found = []
        for u, v in pts:
            p = surf.Value(u, v)
            n = _surface_normal(root.face, u, v)
            # 바깥 법선 반대쪽(재료 안쪽)으로. 면 방향이 뒤집혀 저장된 파일도 있어 반대쪽도 본다.
            for sign in (-1.0, 1.0):
                hit.Perform(gp_Lin(p, gp_Dir(*(sign * n))), 1e-4, 1e7)
                dists = [hit.WParameter(i) for i in range(1, hit.NbPnt() + 1)]
                dists = [d for d in dists if d > 1e-4]
                if dists:
                    found.append(min(dists))
                    break
        if not found:
            raise UnfoldError("두께를 잴 수 없습니다. 두께를 직접 입력해 주세요.")
        found.sort()
        return found[(len(found) - 1) // 2]

    # ---- 단계 2: 스킨 모으기

    @staticmethod
    def _edge_uv_mid(edge, face):
        c = BRepAdaptor_Curve2d(edge, face)
        p = c.Value(0.5 * (c.FirstParameter() + c.LastParameter()))
        return p.X(), p.Y()

    def _tangent(self, ei: int, fa: int, fb: int) -> bool:
        edge = self.edges.items[ei]
        A, B = self.info[fa], self.info[fb]
        try:
            na = _surface_normal(A.face, *self._edge_uv_mid(edge, A.face))
            nb = _surface_normal(B.face, *self._edge_uv_mid(edge, B.face))
        except Exception:
            return False
        return float(na @ nb) > TANGENT_COS

    def _collect_skin(self, root: _Face, t: float | None = None) -> set:
        """기준면과 이어진 겉면들. 둥근 절곡(접하는 모서리)으로 이어진 면, 그리고 t 를 주면
        R 없이 날카롭게 꺾인 평면 플랜지(_sharp_flange)도 모은다."""
        skin = {root.index}
        queue = deque([root.index])
        while queue:
            fi = queue.popleft()
            for ei in self._fe[fi]:
                for fj in self.edge_faces[ei]:
                    if fj in skin or fj == fi:
                        continue
                    if self._tangent(ei, fi, fj) or (t and self._sharp_flange(ei, fi, fj, t)):
                        skin.add(fj)
                        queue.append(fj)
        return skin

    # ---- R 없이 꺾인 모서리 (날카로운 절곡)

    def _ray_hit(self, p, d):
        """p 에서 d 쪽으로 쏜 빛이 처음 닿는 면까지 거리 (없으면 None)."""
        if not hasattr(self, "_hitter"):
            self._hitter = IntCurvesFace_ShapeIntersector()
            self._hitter.Load(self.solid, 1e-6)
        h = self._hitter
        h.Perform(gp_Lin(gp_Pnt(*p), gp_Dir(*d)), 1e-4, 1e7)
        ds = [h.WParameter(i) for i in range(1, h.NbPnt() + 1)]
        ds = [x for x in ds if x > 1e-4]
        return min(ds) if ds else None

    def _inside(self, p) -> bool:
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        c = BRepClass3d_SolidClassifier(self.solid, gp_Pnt(*p), 1e-6)
        return c.State() == TopAbs_IN

    def _sharp_flange(self, ei: int, fa: int, fb: int, t: float) -> bool:
        """fa 에서 날카로운 직선 모서리 ei 를 건너 fb 로 가면 판을 접은 플랜지인가.

        두께 면(옆면)과 가르는 법: 플랜지는 모서리에서 두께보다 훨씬 멀리 뻗고,
        안쪽으로 두께만큼 들어가면 반대쪽 겉면이 있다. 옆면은 폭이 두께와 같고,
        끝면(마구리)은 안쪽으로 부품 길이만큼 가야 반대편이 나온다."""
        key = (ei, fb)
        cache = self.__dict__.setdefault("_sharp_cache", {})
        if key in cache:
            return cache[key]
        cache[key] = False
        A, B = self.info[fa], self.info[fb]
        if A.kind != "plane" or B.kind != "plane" or not self._is_straight(ei):
            return False
        edge = self.edges.items[ei]
        try:
            na = _surface_normal(A.face, *self._edge_uv_mid(edge, A.face))
            nb = _surface_normal(B.face, *self._edge_uv_mid(edge, B.face))
        except Exception:
            return False
        cosang = float(na @ nb)
        if cosang > TANGENT_COS or cosang < math.cos(math.radians(150)):
            return False           # 접하거나, 거의 겹쳐 접힌 것(헤밍)은 아님
        c = BRepAdaptor_Curve(edge)
        p0, p1 = _pnt(c.Value(c.FirstParameter())), _pnt(c.Value(c.LastParameter()))
        e = p1 - p0
        if np.linalg.norm(e) < 2 * t:
            return False
        e /= np.linalg.norm(e)
        d = np.cross(nb, e)
        d /= np.linalg.norm(d)
        ext = [float((_pnt(BRep_Tool.Pnt_s(TopoDS.Vertex(v))) - p0) @ d)
               for v in _explore(B.face, TopAbs_VERTEX)]
        if not ext or max(abs(min(ext)), abs(max(ext))) < 1.5 * t:
            return False           # 폭이 두께 정도: 옆면
        # 기준 겉면이 모서리 너머로 이어지면 (용접한 T 자 이음) 접은 것이 아니다
        ua, va = _interior_uv(A.face)
        pa = _pnt(BRepAdaptor_Surface(A.face).Value(ua, va))
        da = np.cross(na, e)
        if float((pa - p0) @ da) < 0:
            da = -da                # 모서리에서 A 안쪽으로
        mid = 0.5 * (p0 + p1)
        if self._inside(mid - 2 * t * da - 0.1 * t * na):
            return False
        u, v = _interior_uv(B.face)
        pb = _pnt(BRepAdaptor_Surface(B.face).Value(u, v))
        nbi = _surface_normal(B.face, u, v)
        dist = self._ray_hit(pb, -nbi)
        if dist is None or abs(dist - t) > 0.08 * t + 0.02:
            return False           # 안쪽으로 두께만큼 가서 반대 겉면이 없다
        cache[key] = True
        return True

    def _sharp_link(self, ei: int, parent: _Face, child: _Face, t: float):
        """날카로운 절곡의 (각도, 볼록?, 절곡 계산, 펼친 틈)."""
        edge = self.edges.items[ei]
        na = _surface_normal(parent.face, *self._edge_uv_mid(edge, parent.face))
        nb = _surface_normal(child.face, *self._edge_uv_mid(edge, child.face))
        theta = math.acos(max(-1.0, min(1.0, float(na @ nb))))
        c = BRepAdaptor_Curve(edge)
        m = _pnt(c.Value(0.5 * (c.FirstParameter() + c.LastParameter())))
        u, v = _interior_uv(child.face)
        pb = _pnt(BRepAdaptor_Surface(child.face).Value(u, v))
        # 플랜지가 기준 겉면의 바깥 법선 반대쪽으로 꺾이면, 이 겉면에서 보아 볼록 (바깥 꼭짓점)
        convex = float((pb - m) @ na) < 0
        calc = self.settings.resolve(theta, 0.0, t)
        # 겉면 두 장은 바깥(볼록) 또는 안쪽(오목) 꼭짓점에서 만난다:
        #   볼록: 펼친 길이 = 바깥 길이 합 − 연신  → 틈 = BA − 2 (r + t) tan(θ/2)  (보통 음수: 겹침)
        #   오목: 펼친 길이 = 안쪽 길이 합 + BA − 2 r tan(θ/2)
        r = calc.r
        gap = calc.allowance - 2 * math.tan(theta / 2) * (r + (t if convex else 0.0))
        return theta, convex, calc, gap

    # ---- 단계 3: 면마다 기본 전개 정하기

    def _convex(self, f: _Face, ax, u, v) -> bool:
        p = _pnt(BRepAdaptor_Surface(f.face).Value(u, v))
        return float(_surface_normal(f.face, u, v) @ _axis_radial(ax, p)) > 0

    def _setup_cylinder(self, f: _Face, t: float):
        cyl = BRepAdaptor_Surface(f.face).Cylinder()
        f.radius = cyl.Radius()
        u0, u1, v0, v1 = _uv_bounds(f.face)
        f.convex = self._convex(f, cyl.Axis(), 0.5 * (u0 + u1), 0.5 * (v0 + v1))
        f.inner_radius = f.radius - t if f.convex else f.radius
        if f.inner_radius < -1e-3:
            self.warnings.append(
                f"절곡 반지름이 두께보다 작습니다 (R{f.radius:.2f}, 두께 {t:.2f}).")
        f.inner_radius = max(0.0, f.inner_radius)

        theta = u1 - u0
        if theta >= 2 * math.pi - 1e-6:
            # 한 바퀴 도는 관: 절곡이 아니라 말아 만든 것. 중립 반지름으로 둘레를 잰다.
            k, src = self.settings.k_for(f.inner_radius, t)
            f.su = f.inner_radius + k * t
            f.k = k
            return
        f.calc = self.settings.resolve(theta, f.inner_radius, t)
        f.k = f.calc.k
        f.su = f.calc.flat_width / theta
        if f.su <= 0:
            raise UnfoldError(f"절곡 R{f.inner_radius:.2f} 의 펼친 폭이 0 이하입니다. 절곡 조건을 확인해 주세요.")

    def _setup_cone(self, f: _Face, t: float):
        cone = BRepAdaptor_Surface(f.face).Cone()
        f.ref_radius = cone.RefRadius()
        f.sin_a = math.sin(cone.SemiAngle())
        u0, u1, v0, v1 = _uv_bounds(f.face)
        f.convex = self._convex(f, cone.Axis(), 0.5 * (u0 + u1), 0.5 * (v0 + v1))
        # 평균 안쪽 반지름 (축에 수직으로 잰 반지름이 아니라 법선 방향 곡률 반지름)
        rho = f.ref_radius + 0.5 * (v0 + v1) * f.sin_a
        curv_r = abs(rho / math.cos(cone.SemiAngle()))
        inner = curv_r - t if f.convex else curv_r
        k, _ = self.settings.k_for(max(inner, 0.0), t)
        f.k = k
        f.inner_radius = max(inner, 0.0)
        # 중립면까지 법선 방향 거리 (축에서 멀어지는 쪽이 +)
        delta = -(1 - k) * t if f.convex else k * t
        f.s_shift = delta / math.tan(abs(cone.SemiAngle()))

    def _setup_ruled(self, f: _Face, t: float):
        """곡선 단면 (일반 원통) 의 중립선 길이 표. 단면 곡선을 RULED_SAMPLES 점으로 나눠 점마다 곡률 반지름 ρ 와
        볼록·오목 (바깥 법선이 곡률 중심 반대쪽이면 볼록 = 이 겉면이 바깥) 을 구하고, 안쪽 R (볼록이면 ρ − t) 의
        K 로 중립면까지 재료 쪽으로 (볼록 (1 − K)·t, 오목 K·t) 옮긴 선의 길이를 쌓는다 — 원통 절곡의
        BA = θ (R + K t) 를 R 이 바뀌는 곡선으로 넓힌 것 (∫ (1/ρ_안쪽)(R + K t) dθ)."""
        surf = BRepAdaptor_Surface(f.face)
        f.surf = surf
        D = f.ruled_dir
        u0, u1, v0, v1 = _uv_bounds(f.face)
        a0, a1, r0, r1 = (u0, u1, v0, v1) if f.across == "u" else (v0, v1, u0, u1)
        rm = 0.5 * (r0 + r1)
        A = np.linspace(a0, a1, RULED_SAMPLES)
        rev = f.face.Orientation() == TopAbs_REVERSED
        Q, Nn, kap, cen = [], [], [], []
        for a in A:
            u, v = (a, rm) if f.across == "u" else (rm, a)
            p, du, dv, duu, dvv, duv = gp_Pnt(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec()
            surf.D2(u, v, p, du, dv, duu, dvv, duv)
            d1 = np.array([du.X(), du.Y(), du.Z()]) if f.across == "u" else np.array([dv.X(), dv.Y(), dv.Z()])
            d2 = np.array([duu.X(), duu.Y(), duu.Z()]) if f.across == "u" else np.array([dvv.X(), dvv.Y(), dvv.Z()])
            nrm = np.cross([du.X(), du.Y(), du.Z()], [dv.X(), dv.Y(), dv.Z()])
            nrm = nrm / max(np.linalg.norm(nrm), 1e-30) * (-1 if rev else 1)
            d1 = d1 - (d1 @ D) * D
            d2 = d2 - (d2 @ D) * D
            sp = max(float(np.linalg.norm(d1)), 1e-30)
            tg = d1 / sp
            an = d2 - (d2 @ tg) * tg                    # 곡률 중심 쪽 가속도
            k_ = float(np.linalg.norm(an)) / sp ** 2
            P3 = _pnt(p)
            Q.append(P3 - (P3 @ D) * D)
            Nn.append(nrm - (nrm @ D) * D)
            kap.append(k_)
            cen.append(an / max(np.linalg.norm(an), 1e-30))
        Q, Nn, kap, cen = np.array(Q), np.array(Nn), np.array(kap), np.array(cen)
        Nn /= np.maximum(np.linalg.norm(Nn, axis=1), 1e-30)[:, None]
        straight = kap * t < 1e-3                        # ρ > 1000 t: 곧은 곳 (K 0.5 와 같음)
        convex = np.einsum("ij,ij->i", Nn, cen) < 0
        rho = np.where(straight, np.inf, 1 / np.maximum(kap, 1e-30))
        r_in = np.where(convex, rho - t, rho)
        if np.any(~straight & (r_in < -1e-3)):
            self.warnings.append(f"곡선 단면의 R 이 두께보다 작은 곳이 있습니다 (최소 곡률 반지름 {np.nanmin(rho):.2f}).")
        r_in = np.maximum(r_in, 0.0)
        cache = {}

        def k_at(r):
            key = round(math.log(r / t + 0.01), 2)
            if key not in cache:
                cache[key] = self.settings.k_for(r, t)[0]
            return cache[key]
        K = np.array([0.5 if s_ else k_at(float(r)) for s_, r in zip(straight, r_in)])
        delta = np.where(convex, (1 - K) * t, K * t)
        delta = np.where(straight, 0.5 * t, delta)
        Nl = Q - Nn * delta[:, None]                     # 재료 쪽 (바깥 법선 반대) 으로 중립면까지
        S = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Nl, axis=0), axis=1))])
        f.tab_p, f.tab_s = A, S
        f.k = float(np.mean(K))
        f.inner_radius = float(np.min(np.where(straight, np.inf, r_in))) if (~straight).any() else math.inf
        f.convex = bool(np.mean(convex[~straight]) > 0.5) if (~straight).any() else False
        # 같은 쪽으로 휜 구간마다 절곡 하나 (S 자는 둘)
        ds = np.linalg.norm(np.diff(Q, axis=0), axis=1)
        turn = 0.5 * (kap[1:] + kap[:-1]) * ds
        sign = np.where(straight, 0, np.where(convex, 1, -1))
        f.groups = []
        i = 0
        n = len(A)
        while i < n:
            if sign[i] == 0:
                i += 1
                continue
            j = i
            while j + 1 < n and sign[j + 1] == sign[i]:
                j += 1
            ang = float(turn[i:j].sum()) if j > i else 0.0
            if ang > math.radians(1.0):
                rr = r_in[i:j + 1]
                f.groups.append(dict(i0=i, i1=j, angle=ang, convex=sign[i] > 0, r_min=float(rr.min()),
                                     r_max=float(rr.max()), k=float(K[i:j + 1].mean()),
                                     width=float(S[j] - S[i]), a_mid=float(A[(i + j) // 2])))
            i = j + 1

    def _edge_canon(self, f: _Face, edge):
        c = BRepAdaptor_Curve2d(edge, f.face)
        p1, p2 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        return f.canon(p1.X(), p1.Y()), f.canon(p2.X(), p2.Y())

    def _inward(self, f: _Face, edge, K1, K2):
        """공유 모서리(K1→K2, 기본 전개 좌표)의 방향과, 면 안쪽을 향하는 수직 방향."""
        d = K2 - K1
        d = d / np.linalg.norm(d)
        c = BRepAdaptor_Curve2d(edge, f.face)
        tm = 0.5 * (c.FirstParameter() + c.LastParameter())
        p, tv = gp_Pnt2d(), gp_Vec2d()
        c.D1(tm, p, tv)
        um, vm = p.X(), p.Y()
        perp = np.array([-tv.Y(), tv.X()])
        perp /= np.linalg.norm(perp)
        Km = f.canon(um, vm)
        for sign in (1.0, -1.0):
            h = 1e-6
            step = np.linalg.norm(f.canon(um + sign * h * perp[0], vm + sign * h * perp[1]) - Km)
            if step < 1e-15:
                continue
            for target in (_PROBE, _PROBE * 0.05):
                hh = h * target / step
                uu, vv = um + sign * hh * perp[0], vm + sign * hh * perp[1]
                if _classify_in(f.face, uu, vv):
                    n = f.canon(uu, vv) - Km
                    n -= (n @ d) * d
                    return d, n / np.linalg.norm(n)
        raise UnfoldError("면의 안쪽 방향을 판단하지 못했습니다.")

    def _place_root(self, root: _Face):
        # 바깥쪽에서 바라본 모습이 되도록, 기본 전개의 방향이 뒤집혀 있으면 대칭시킨다.
        u, v = _interior_uv(root.face)
        h = 1e-4
        k0 = root.canon(u, v)
        J = np.column_stack([root.canon(u + h, v) - k0, root.canon(u, v + h) - k0])
        sign = np.sign(np.linalg.det(J)) * (-1 if root.face.Orientation() == TopAbs_REVERSED else 1)
        root.A = np.eye(2) if sign >= 0 else np.diag([1.0, -1.0])
        root.C = np.zeros(2)

    def _place_child(self, parent: _Face, child: _Face, ei: int):
        edge = self.edges.items[ei]
        P1, P2 = self._edge_canon(parent, edge)
        S1, S2 = self._edge_canon(child, edge)
        F1, F2 = parent.C + parent.A @ P1, parent.C + parent.A @ P2

        _, np_in = self._inward(parent, edge, P1, P2)
        dc, nc_in = self._inward(child, edge, S1, S2)

        df = F2 - F1
        df /= np.linalg.norm(df)
        nf = parent.A @ np_in
        nf -= (nf @ df) * df
        nf /= np.linalg.norm(nf)

        # 자식 면은 공유 모서리를 기준으로 부모 반대편에 놓인다.
        child.A = np.column_stack([df, -nf]) @ np.column_stack([dc, nc_in]).T
        child.C = F1 - child.A @ S1

    def unfold(self) -> UnfoldResult:
        root = self._pick_root()
        t = self.user_thickness or self._measure_thickness(root)
        if t <= 0:
            raise UnfoldError("두께가 0 입니다.")

        skin = self._collect_skin(root, t)
        unsupported = [fi for fi in skin if self.info[fi].kind == "other"]
        if self.mode == FORMING or (self.mode == AUTO and unsupported):
            return self._unfold_forming(skin, t, len(unsupported))
        if unsupported:
            # [판금] 이어도 곡선을 따라 꺾인 절곡(자유곡면)이 겉면의 상당 부분이면, 빼고 펼치면
            # 판 한 장만 남는다. 그럴 때는 성형품 근사로 펼치고 알린다.
            free = sum(self.info[fi].area for fi in unsupported)
            total = sum(self.info[fi].area for fi in skin)
            if total > 0 and free / total > 0.05:
                r = self._unfold_forming(skin, t, len(unsupported))
                r.warnings.insert(0, f"곡선을 따라 꺾인 절곡(자유곡면 {len(unsupported)}개, 겉면의 "
                                     f"{free / total:.0%})이 있어 정확 전개가 안 됩니다. 성형품 근사로 펼쳤습니다.")
                return r
        if unsupported:
            self.warnings.append(
                f"평면·원통·원뿔이 아닌 면 {len(unsupported)}개는 전개에서 뺐습니다 "
                "(프레스 성형 같은 자유곡면은 지원하지 않습니다).")
            skin -= set(unsupported)

        for fi in skin:
            f = self.info[fi]
            if f.kind == "cylinder":
                self._setup_cylinder(f, t)
            elif f.kind == "cone":
                self._setup_cone(f, t)
            elif f.kind == "ruled":
                self._setup_ruled(f, t)

        # 기준면부터 넓이 우선으로 이어 붙인다.
        self._place_root(root)
        sharp = []        # 날카로운 절곡: (모서리 끝 두 점, 옮긴 두 점, Bend)
        placed = {root.index}
        tree_edges = set()
        queue = deque([root.index])
        while queue:
            fi = queue.popleft()
            for ei in self._fe[fi]:
                for fj in self.edge_faces[ei]:
                    if fj not in skin or fj in placed:
                        continue
                    if not self._is_straight(ei):
                        continue
                    self._place_child(self.info[fi], self.info[fj], ei)
                    if self._sharp_cache_get(ei, fi, fj):
                        sharp.append(self._shift_sharp(ei, self.info[fi], self.info[fj], t))
                    self.info[fj].parent = fi
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

        entities = _close_sharp(_fit_primitives(entities), sharp)
        entities = _join_collinear(_merge_duplicates(entities))
        bends, rolled = self._bends(placed, t)
        if sharp:
            bends = _renumber(bends + [b for _, _, b in sharp])
        for b in bends:
            entities.append(Line(*b.line, layer="BEND"))
        entities = _align_entities(entities, bends)

        result = UnfoldResult(
            thickness=t, k_factor=self.settings.k, entities=entities, bends=bends,
            warnings=self.warnings, face_count=len(placed),
            settings_text=self.settings.describe(), rolled=rolled)
        result.entities = _normalize_origin(result)
        _check_overlap(result)
        self._check_coverage(result, placed, t)
        return result

    def _check_coverage(self, result, placed, t):
        """펼친 겉면 넓이 × 두께가 부품 부피에 크게 못 미치면, 빠진 부분이 있다고 알린다."""
        try:
            g = GProp_GProps()
            BRepGProp.VolumeProperties_s(self.solid, g)
            vol = abs(g.Mass())
        except Exception:
            return
        covered = sum(self.info[fi].area for fi in placed) * t
        if vol <= 0:
            return
        ratio = covered / vol
        result.coverage = ratio
        if ratio > 1.2:
            result.warnings.append(
                f"펼친 면적×두께가 부품 부피의 {ratio:.0%} 입니다. 두께가 곳마다 다릅니다 "
                "(두께를 잘못 쟀거나 판금이 아닌 부품). 두께를 직접 넣어 확인하세요.")
        elif ratio < 0.85:
            result.warnings.append(
                f"펼친 면적×두께가 부품 부피의 {ratio:.0%} 뿐입니다. 전개에 들어가지 않은 부분이 있습니다 — "
                "두께가 일정한 판금이 아니거나(블록·보스·용접 조립), 곡선을 따라 꺾인 플랜지일 수 있습니다. "
                "[전개 방식] 을 [자동] 또는 [성형품 근사] 로 바꿔 보세요.")

    def _sharp_cache_get(self, ei, fi, fj) -> bool:
        c = self.__dict__.get("_sharp_cache", {})
        return c.get((ei, fj), False) or c.get((ei, fi), False)

    def _shift_sharp(self, ei: int, parent: _Face, child: _Face, t: float):
        """_place_child 로 맞붙여 놓은 자식 면을 펼친 틈만큼 밀고, 절곡 하나를 만든다."""
        edge = self.edges.items[ei]
        P1, P2 = self._edge_canon(parent, edge)
        F1, F2 = parent.C + parent.A @ P1, parent.C + parent.A @ P2
        _, np_in = self._inward(parent, edge, P1, P2)
        df = (F2 - F1) / np.linalg.norm(F2 - F1)
        nf = parent.A @ np_in
        nf -= (nf @ df) * df
        nf /= np.linalg.norm(nf)
        theta, convex, calc, gap = self._sharp_link(ei, parent, child, t)
        child.C = child.C - nf * gap          # 부모 반대쪽(-nf)으로 gap 만큼
        mid = -nf * (gap / 2)
        line = (tuple(float(x) for x in F1 + mid), tuple(float(x) for x in F2 + mid))
        b = Bend(number=0, kind="날카로운 모서리", angle_deg=math.degrees(theta),
                 inner_radius=calc.r, model_radius=0.0, k=calc.k,
                 direction="DOWN" if convex else "UP", length=float(np.linalg.norm(F2 - F1)),
                 allowance=calc.allowance,
                 deduction=calc.deduction, deduction90=calc.deduction90,
                 source=f"R 없는 모서리, {calc.source}", line=line, radius_text=f"{calc.r:.2f}")
        return ((tuple(F1), tuple(F2)), (tuple(F1 - nf * gap), tuple(F2 - nf * gap)), b)

    def _unfold_forming(self, skin, t, n_free) -> UnfoldResult:
        from . import forming

        faces = [self.info[fi].face for fi in sorted(skin)]
        V, F, N = forming.mesh_faces(self.solid, faces, _diagonal(self.solid))
        mat = self.settings.mat
        how = {}
        from .diecalc import HOLDER_P, _family
        tools = dict(thickness=t, tensile=mat.tensile_mpa, mu=0.1, p_bh=HOLDER_P[_family(mat.code)],
                     die_r=max(5 * t, 3.0)) if forming.TOOL_LOADS and n_free else None
        # 평면·원통·원뿔뿐인 부품은 굽힘으로 만들어 끌려 들어오는 저항(누르개·다이 R)이 없다
        Vm, F, U = forming.flatten(V, F, t, N=N, n_exp=mat.n, r_value=mat.r, info=how, tools=tools)
        major, minor, ratio = forming.strains(Vm, F, U)
        membrane, corr = None, None
        if tools is not None and forming.DRAW_CORRECTION:
            # 원스텝 (막) 이 못 보는 인장 아래 굽힘·드로잉 장력·아이어닝을 더한다 (drawcorr)
            from . import drawcorr
            try:
                m2, n2, corr = drawcorr.correct(Vm, F, U, major, minor, t, mat, N=how.get("normals"))
                if corr.get("applied"):
                    membrane = (major, minor)
                    major, minor = m2, n2
                    ratio = np.exp(major + minor)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                corr = None

        entities = []
        for loop in forming.boundary_loops(F):
            pts = [tuple(float(x) for x in U[i]) for i in loop]
            entities.append(Polyline(_simplify(pts + [pts[0]])))

        area3d = float(_tri_areas3(Vm, F).sum())
        area2d = float(_tri_areas2(U, F).sum())
        if not 0.8 < area2d / area3d < 1.25:
            raise UnfoldError(
                "펼칠 수 없는 모양입니다 (펼친 넓이가 제품과 크게 다름).\n"
                "관·파이프처럼 둘레가 닫힌 부품이면 펼치는 대상이 아닙니다 "
                "(굽힌 관은 중심선 길이로 재단합니다).")
        cyl = []
        for fc in faces:
            try:
                ad = BRepAdaptor_Surface(fc)
                if ad.GetType() == GeomAbs_Cylinder:
                    c = ad.Cylinder()
                    d = c.Axis().Direction()
                    cyl.append((float(c.Radius()), (d.X(), d.Y(), d.Z())))
            except Exception:
                pass
        fi = FormingInfo(U=U, F=F, ratio=ratio, major=major, minor=minor,
                         product_area=area3d, blank_area=area2d,
                         reliable=forming.quality(Vm, F) > 5.0, method=how.get("method", "ARAP"),
                         flc0=mat.flc0_for(t), material=mat.code, V=Vm, cylinders=cyl,
                         membrane=membrane, correction=corr)
        notes = []
        if n_free:
            notes.append(f"자유곡면 {n_free}개가 있어 성형품 근사 전개를 했습니다.")
        notes.append("성형품 근사 전개: 블랭크 크기·재료비 추정용입니다. "
                     "금형 블랭크는 트라이아웃이나 성형 해석으로 확정하세요.")
        lo, hi = fi.thinning_range
        if hi > 0.25:
            notes.append(f"두께가 최대 {hi:.0%} 얇아지는 곳이 있습니다 (터짐 주의).")
        if lo < -0.15:
            notes.append(f"두께가 최대 {-lo:.0%} 두꺼워지는 곳이 있습니다 (주름 주의).")
        split, marginal, wrinkle, _ = fi.flc_summary
        if split > 0.001:
            notes.append(f"성형 한계(FLC, {mat.code} n={mat.n:g})를 넘는 곳이 {split:.1%} 있습니다 "
                         "(파단 위험: R 을 키우거나 재질·형상을 바꾸세요).")
        elif marginal > 0.001:
            notes.append(f"성형 한계 80 % 이상인 곳이 {marginal:.1%} 있습니다 (파단 여유 적음).")
        if wrinkle > 0.02:
            notes.append(f"압축으로 두꺼워지는(주름 가능) 곳이 {wrinkle:.1%} 있습니다.")
        result = UnfoldResult(
            thickness=t, k_factor=0.5, entities=entities, bends=[],
            warnings=self.warnings + notes, face_count=len(skin),
            settings_text=f"성형품 근사 (두께 가운데 면, {fi.method}, {mat.code} n={mat.n:g} r={mat.r:g})", mode=FORMING, forming=fi)
        result.entities = _normalize_origin(result)
        return result

    def _is_straight(self, ei: int) -> bool:
        if ei not in self._straight:
            self._straight[ei] = _curve_is_straight(BRepAdaptor_Curve(self.edges.items[ei]))
        return self._straight[ei]

    # ---- 단계 4: 모서리 그리기

    def _map_edge(self, edge, f: _Face):
        c = BRepAdaptor_Curve2d(edge, f.face)
        a, b = c.FirstParameter(), c.LastParameter()

        def flat(t):
            p = c.Value(t)
            return tuple(float(x) for x in f.to_flat(p.X(), p.Y()))

        kind = c.GetType()
        if kind == GeomAbs_Line:
            if f.kind != "cone":
                return [Line(flat(a), flat(b))]
            d = c.Line().Direction()
            if abs(d.X()) < 1e-9:
                return [Line(flat(a), flat(b))]          # 모선: 꼭짓점을 지나는 직선
            if abs(d.Y()) < 1e-9:
                # 둘레 방향: 꼭짓점을 중심으로 한 호
                center = tuple(float(x) for x in f.C)
                p = c.Value(a)
                radius = float(np.linalg.norm(f.canon(p.X(), p.Y())))
                if abs(abs(b - a) * abs(f.sin_a) - 2 * math.pi) < 1e-7:
                    return [Arc(center, radius, full=True)]
                return [_arc_through(center, radius, flat(a), flat(0.5 * (a + b)), flat(b))]

        if kind == GeomAbs_Circle and f.kind == "plane":
            circ = c.Circle()
            ctr = circ.Location()
            center = tuple(float(x) for x in f.to_flat(ctr.X(), ctr.Y()))
            r = circ.Radius()
            if abs(abs(b - a) - 2 * math.pi) < 1e-7:
                return [Arc(center, r, full=True)]
            return [_arc_through(center, r, flat(a), flat(0.5 * (a + b)), flat(b))]

        # 그 밖의 곡선 (스플라인·베지어 등) 은 폴리라인으로: 0.5 mm 간격에서 시작해, 현의 가운데가 곡선에서
        # CHORD_TOL 넘게 떨어지는 구간은 반으로 더 나눈다 (작은 R 의 스플라인도 오차 5 µm 안)
        length = _curve_length_estimate(c, a, b, f)
        n = int(min(400, max(16, length / 0.5)))
        ts = [a + (b - a) * i / n for i in range(n + 1)]
        pts = [flat(x) for x in ts]
        out_t, out_p = [ts[0]], [pts[0]]
        for i in range(n):
            stack = [(ts[i], pts[i], ts[i + 1], pts[i + 1], 0)]
            seg = []
            while stack:
                t0, p0, t1, p1, depth = stack.pop()
                tm = 0.5 * (t0 + t1)
                pm = flat(tm)
                q0, q1, qm = np.array(p0), np.array(p1), np.array(pm)
                dv = q1 - q0
                L = float(np.linalg.norm(dv))
                dev = float(np.linalg.norm(qm - q0)) if L < 1e-12 else abs(float(dv[0] * (qm - q0)[1] - dv[1] * (qm - q0)[0])) / L
                if dev > CHORD_TOL and depth < 8:
                    stack.append((tm, pm, t1, p1, depth + 1))
                    stack.append((t0, p0, tm, pm, depth + 1))
                else:
                    seg.append((t1, p1))
            for x, q in seg:
                out_t.append(x)
                out_p.append(q)
        return [Polyline(out_p)]

    def _fold_angle(self, f: _Face, u0, u1, vm):
        n0 = _surface_normal(f.face, u0, vm)
        n1 = _surface_normal(f.face, u1, vm)
        return math.acos(max(-1.0, min(1.0, float(n0 @ n1))))

    def _bends(self, placed, t):
        bends, rolled = [], []
        for fi in sorted(placed):
            f = self.info[fi]
            if f.kind == "ruled":
                bends += self._ruled_bends(f)
                continue
            if f.kind not in ("cylinder", "cone"):
                continue
            u0, u1, v0, v1 = _uv_bounds(f.face)
            full = (u1 - u0) >= 2 * math.pi - 1e-6
            if full:
                if f.kind == "cylinder":
                    rolled.append(f"원통 말기: 안쪽 R{f.inner_radius:.2f}, "
                                  f"펼친 둘레 {2 * math.pi * f.su:.2f} mm (K {f.k:.3f})")
                else:
                    a = math.degrees(math.asin(abs(f.sin_a)))
                    rolled.append(f"원뿔 말기: 반각 {a:.1f}°, 부채꼴 각 "
                                  f"{math.degrees(2 * math.pi * abs(f.sin_a)):.1f}° (K {f.k:.3f})")
                continue

            um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
            vs = self._v_range_at(f, um, v0, v1)
            p1 = tuple(float(x) for x in f.to_flat(um, vs[0]))
            p2 = tuple(float(x) for x in f.to_flat(um, vs[1]))
            direction = "DOWN" if f.convex else "UP"

            if f.kind == "cylinder":
                c = f.calc
                angle = u1 - u0
                bends.append(Bend(
                    number=0, kind="원통", angle_deg=math.degrees(angle),
                    inner_radius=c.r, model_radius=c.model_r, k=c.k, direction=direction,
                    length=abs(vs[1] - vs[0]), allowance=c.allowance, deduction=c.deduction,
                    deduction90=c.deduction90, source=c.source, line=(p1, p2),
                    radius_text=f"{c.r:.2f}"))
            else:
                angle = self._fold_angle(f, u0, u1, vm)
                cos_a = math.sqrt(1 - f.sin_a ** 2)
                rs = [abs((f.ref_radius + v * f.sin_a) / cos_a) - (t if f.convex else 0) for v in vs]
                width = float(np.linalg.norm(f.to_flat(u1, vm) - f.to_flat(u0, vm)))
                bends.append(Bend(
                    number=0, kind="원뿔", angle_deg=math.degrees(angle),
                    inner_radius=f.inner_radius, model_radius=f.inner_radius, k=f.k,
                    direction=direction, length=float(np.linalg.norm(np.subtract(p2, p1))),
                    allowance=width, deduction=float("nan"), deduction90=float("nan"),
                    source="원뿔 (R 이 위치마다 다름)", line=(p1, p2),
                    radius_text=f"{min(rs):.2f}~{max(rs):.2f}"))
        bends.sort(key=lambda b: (round(b.line[0][1], 3), round(b.line[0][0], 3)))
        for i, b in enumerate(bends, 1):
            b.number = i
        return bends, rolled

    def _ruled_bends(self, f: _Face):
        """곡선 단면의 휜 구간마다 Bend (절곡선 = 구간 가운데의 민 방향 선)."""
        out = []
        u0, u1, v0, v1 = _uv_bounds(f.face)
        for g in f.groups:
            if f.across == "u":
                lo, hi = self._v_range_at(f, g["a_mid"], v0, v1)
                q1, q2 = (g["a_mid"], lo), (g["a_mid"], hi)
            else:
                lo, hi = self._u_range_at(f, g["a_mid"], u0, u1)
                q1, q2 = (lo, g["a_mid"]), (hi, g["a_mid"])
            p1 = tuple(float(x) for x in f.to_flat(*q1))
            p2 = tuple(float(x) for x in f.to_flat(*q2))
            rmax = "∞" if not math.isfinite(g["r_max"]) or g["r_max"] > 1e4 else f"{g['r_max']:.1f}"
            out.append(Bend(
                number=0, kind=RULED_KIND, angle_deg=math.degrees(g["angle"]),
                inner_radius=g["r_min"], model_radius=g["r_min"], k=g["k"],
                direction="DOWN" if g["convex"] else "UP",
                length=float(np.linalg.norm(np.subtract(p2, p1))), allowance=g["width"],
                deduction=float("nan"), deduction90=float("nan"),
                source="곡선 단면 (3차 곡선 등): 중립선 길이 적분, K 는 위치마다 R/t 로", line=(p1, p2),
                radius_text=f"{g['r_min']:.1f}~{rmax}"))
        return out

    def _u_range_at(self, f: _Face, v, u0, u1):
        """v 위치에서 면 안에 들어가는 u 범위."""
        n = 200
        us = [u0 + (u1 - u0) * i / n for i in range(n + 1)]
        inside = [i for i, u in enumerate(us) if _classify_in(f.face, u, v)]
        if not inside:
            return u0, u1
        i0, i1 = inside[0], inside[-1]
        return (us[max(i0 - 1, 0)] + us[i0]) / 2 if i0 > 0 else u0, (us[i1] + us[min(i1 + 1, n)]) / 2 if i1 < n else u1

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


def _fit_primitives(entities, tol=2e-3):
    """자유곡선을 잘게 나눈 폴리라인 가운데 사실상 직선·원호인 것을 LINE·ARC 로 바꾼다.
    (평면·원통이 B-스플라인으로 저장된 파일에서 나온 모서리. 가공기는 LINE·ARC 를 좋아한다.)"""
    out = []
    for e in entities:
        if not isinstance(e, Polyline) or len(e.points) < 3:
            out.append(e)
            continue
        P = np.array(e.points)
        a, b = P[0], P[-1]
        d = b - a
        L = float(np.linalg.norm(d))
        if L > 1e-9:
            n = np.array([-d[1], d[0]]) / L
            if np.abs((P - a) @ n).max() < tol:
                out.append(Line(tuple(a), tuple(b), e.layer))
                continue
        c = _circle_through(P[0], P[len(P) // 2], P[-1]) if L > 1e-9 else \
            _circle_through(P[0], P[len(P) // 3], P[2 * len(P) // 3])
        if c is not None:
            ctr, r = c
            if np.abs(np.linalg.norm(P - ctr, axis=1) - r).max() < tol:
                center = (float(ctr[0]), float(ctr[1]))
                if L < tol:
                    out.append(Arc(center, float(r), full=True, layer=e.layer))
                else:
                    arc = _arc_through(center, float(r), tuple(P[0]), tuple(P[len(P) // 2]), tuple(P[-1]))
                    arc.layer = e.layer
                    out.append(arc)
                continue
        out.append(e)
    return out


def _circle_through(p1, p2, p3):
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    ctr = np.array([ux, uy])
    return ctr, float(np.linalg.norm(np.asarray(p1) - ctr))


def _align_entities(entities, bends):
    """바깥 사각형이 가장 작아지게 전개도를 돌린다. 원래 좌표축이 비스듬한 파일도
    전개도가 반듯하게 나와 철판 크기가 바로 보인다."""
    from scipy.spatial import ConvexHull

    if bends:
        # 절곡이 있으면 가장 긴 절곡선을 세로로 (프레스 브레이크에 넣는 방향)
        b = max(bends, key=lambda b: b.length)
        (x1, y1), (x2, y2) = b.line
        ang = math.pi / 2 - math.atan2(y2 - y1, x2 - x1)
        # 세로 방향이 이미 맞으면(180° 차이 포함) 돌리지 않는다
        if abs(math.remainder(ang, math.pi)) < 1e-9:
            return entities
        return _rotate_entities(entities, bends, ang)
    pts = []
    for e in entities:
        if isinstance(e, Arc):
            span = 360.0 if e.full else (e.end_deg - e.start_deg) % 360
            a0 = 0.0 if e.full else e.start_deg
            n = max(2, int(span / 5))
            pts += [(e.center[0] + e.radius * math.cos(math.radians(a0 + span * i / n)),
                     e.center[1] + e.radius * math.sin(math.radians(a0 + span * i / n)))
                    for i in range(n + 1)]
        else:
            pts += list(_entity_points([e]))
    pts = np.array(pts)
    if len(pts) < 3:
        return entities
    try:
        hull = pts[ConvexHull(pts).vertices]
    except Exception:
        return entities
    best = None
    for i in range(len(hull)):
        d = hull[(i + 1) % len(hull)] - hull[i]
        ang = -math.atan2(d[1], d[0])
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        q = hull @ R.T
        w, h = q.max(0) - q.min(0)
        key = (round(w * h, 6), -w)
        if best is None or key < best[0]:
            best = (key, ang, w < h)
    ang = best[1] + (math.pi / 2 if best[2] else 0.0)
    if abs(math.remainder(ang, math.pi / 2)) < 1e-9:
        return entities
    return _rotate_entities(entities, bends, ang)


def _rotate_entities(entities, bends, ang):
    c, s_ = math.cos(ang), math.sin(ang)

    def rot(p):
        return (c * p[0] - s_ * p[1], s_ * p[0] + c * p[1])

    deg = math.degrees(ang)
    out = []
    for e in entities:
        if isinstance(e, Line):
            out.append(Line(rot(e.p1), rot(e.p2), e.layer))
        elif isinstance(e, Arc):
            out.append(Arc(rot(e.center), e.radius, (e.start_deg + deg) % 360,
                           (e.end_deg + deg) % 360, e.full, e.layer))
        else:
            out.append(Polyline([rot(p) for p in e.points], e.layer))
    for b in bends:
        b.line = (rot(b.line[0]), rot(b.line[1]))
    return out


def _curve_is_straight(c, tol=5e-3) -> bool:
    """직선이거나, 자유곡선으로 저장됐어도 점들이 한 직선 위에 있으면 True."""
    if c.GetType() == GeomAbs_Line:
        return True
    a, b = c.FirstParameter(), c.LastParameter()
    p0, p1 = _pnt(c.Value(a)), _pnt(c.Value(b))
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        return False
    d /= L
    for i in range(1, 16):
        q = _pnt(c.Value(a + (b - a) * i / 16)) - p0
        if np.linalg.norm(q - (q @ d) * d) > max(tol, 1e-6 * L):
            return False
    return True


def _diagonal(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    return float(np.linalg.norm(_pnt(box.CornerMax()) - _pnt(box.CornerMin())))


def _tri_areas3(V, F):
    return 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)


def _tri_areas2(U, F):
    a, b = U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]]
    return 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


def _simplify(pts, tol=1e-4):
    """한 직선 위에 있는 가운데 점을 뺀다 (평평한 경계의 점이 줄어 DXF 가 가벼워진다)."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = np.array(out[-1]), np.array(pts[i]), np.array(pts[i + 1])
        ab, ac = b - a, c - a
        L = np.linalg.norm(ac)
        if L > 0 and abs(ab[0] * ac[1] - ab[1] * ac[0]) / L < tol and 0 <= ab @ ac <= L * L:
            continue
        out.append(pts[i])
    out.append(pts[-1])
    return out


def _arc_through(center, r, p0, pm, p1):
    """p0 → pm → p1 을 지나는 반시계 호."""
    ang = lambda p: math.degrees(math.atan2(p[1] - center[1], p[0] - center[0])) % 360
    s, m, e = ang(p0), ang(pm), ang(p1)
    if (m - s) % 360 > (e - s) % 360:
        s, e = e, s
    return Arc(center, r, s, e)


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
    pts = []
    for i in range(17):
        p = c.Value(a + (b - a) * i / 16)
        pts.append(f.to_flat(p.X(), p.Y()))
    return sum(float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(16))


def _renumber(bends):
    bends.sort(key=lambda b: (round(b.line[0][1], 3), round(b.line[0][0], 3)))
    for i, b in enumerate(bends, 1):
        b.number = i
    return bends


def _close_sharp(entities, sharp, tol=1e-4):
    """날카로운 절곡에서 부모 면 끝(F)과 밀어 놓은 자식 면 끝(F')을 잇는다.

    양쪽 옆선이 한 직선 위면 하나로 합치고 (틈이든 겹침이든), 아니면 F–F' 짧은 선을 넣는다."""
    if not sharp:
        return entities
    ents = list(entities)

    def find(pt, exclude=None):
        for i, e in enumerate(ents):
            if i == exclude or not isinstance(e, Line) or e.layer != "CUT":
                continue
            for a, b in ((e.p1, e.p2), (e.p2, e.p1)):
                if abs(a[0] - pt[0]) < tol and abs(a[1] - pt[1]) < tol:
                    return i, b
        return None

    for (F1, F2), (G1, G2), _ in sharp:
        for F, G in ((F1, G1), (F2, G2)):
            d = np.subtract(G, F)
            n = float(np.linalg.norm(d))
            if n < tol:
                continue
            d /= n
            fa = find(F)
            fb = find(G, exclude=fa[0] if fa else None)
            if fa and fb:
                P, Q = np.array(fa[1]), np.array(fb[1])
                # 두 옆선이 F→G 와 같은 직선 위인가
                def on_line(X):
                    w = X - np.array(F)
                    return abs(w[0] * d[1] - w[1] * d[0]) < 1e-3
                if on_line(P) and on_line(Q) and float((P - np.array(F)) @ d) < 0 \
                        and float((Q - np.array(G)) @ d) > 0:
                    i, j = sorted((fa[0], fb[0]))
                    del ents[j]
                    del ents[i]
                    ents.append(Line(tuple(P), tuple(Q)))
                    continue
            ents.append(Line(tuple(F), tuple(G)))
    return ents


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
    if result.forming is not None:
        result.forming.U = result.forming.U - np.array(off)
    return out


def _check_overlap(result: UnfoldResult):
    """절단선끼리 서로 가로지르면 펼친 플랜지가 겹친 것이다 (모서리 릴리프 부족 등)."""
    segs = []
    for e in result.entities:
        if e.layer != "CUT":
            continue
        if isinstance(e, Line):
            segs.append((e.p1, e.p2))
        elif isinstance(e, Polyline):
            segs.extend(zip(e.points[:-1], e.points[1:]))
    if len(segs) > 3000:
        return
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if _segments_cross(*segs[i], *segs[j]):
                result.warnings.append(
                    "펼친 모양이 서로 겹칩니다. 모서리 릴리프(따내기)가 필요한지 확인해 주세요.")
                return


def _segments_cross(a, b, c, d):
    """끝점 공유는 빼고, 두 선분이 안쪽에서 엇갈리는지."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    eps = 1e-6
    d1, d2 = orient(c, d, a), orient(c, d, b)
    d3, d4 = orient(a, b, c), orient(a, b, d)
    return ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
           ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))


def unfold(solid, k_factor: float = 0.44, thickness: float | None = None,
           settings: BendSettings | None = None, mode: str = AUTO) -> UnfoldResult:
    """settings 가 없으면 K 계수 직접 입력 방식으로 계산한다."""
    if settings is None:
        settings = BendSettings(k=k_factor)
    r = SheetMetalUnfolder(solid, settings, thickness, mode).unfold()
    curved = [b for b in r.bends if b.kind == RULED_KIND]
    if curved:
        r.advice.append(f"곡선 단면 {len(curved)} 곳 (R 이 위치마다 바뀌는 곡선, 최소 안쪽 R "
                        f"{min(b.inner_radius for b in curved):.1f}): 중립선 길이를 적분해 펼쳤습니다 (K 는 위치마다 R/t 로). "
                        "프레스 브레이크로는 작은 각을 여러 번 나눠 접는 스텝 벤딩, 또는 롤 벤딩·전용 금형으로 만듭니다.")
    if r.mode == SHEET and r.bends:
        from .bendcalc import accuracy_notes
        try:
            r.advice += accuracy_notes(settings, [b for b in r.bends if b.kind == "원통"], r.thickness)
        except Exception:
            pass
    return r
