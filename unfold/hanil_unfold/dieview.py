"""금형 3D 도면용 투영: 숨은선 지운 입체도 (OCC HLR) 와 단면 (평면으로 자른 면 + 해칭).

hlr(shapes, view)  — 보이는 선 · 숨은 선 (투영 평면 2D 꺾은선 목록). view 는 보는 방향 (보는 쪽으로 향함).
section(shape, y)  — 평면 y = y0 으로 자른 단면 고리들 [(바깥 꺾은선 (x, z), [구멍 꺾은선 …])].
hatch(loops, ...)  — 단면 고리 안을 45° 빗금 (짝홀 규칙) 선분으로.
"""
from __future__ import annotations

import math

import numpy as np

ISO_DIR = (1.0, -1.0, 0.8)          # 오른쪽 앞 위에서 봄 (등각에 가까움)


def _edges_polylines(shape, samples=24, deflection=None):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    if shape is None or shape.IsNull():
        return out
    ex = TopExp_Explorer(shape, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current()) if hasattr(TopoDS, "Edge_s") else TopoDS.Edge(ex.Current())
        ex.Next()
        try:
            c = BRepAdaptor_Curve(e)
        except Exception:  # noqa: BLE001
            continue
        a, b = c.FirstParameter(), c.LastParameter()
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        n = 1 if c.GetType() == GeomAbs_Line else samples
        P = []
        for i in range(n + 1):
            q = c.Value(a + (b - a) * i / n)
            P.append((q.X(), q.Y()))
        out.append(np.asarray(P))
    return out


def projector(view=ISO_DIR, up=(0.0, 0.0, 1.0)):
    """HLR 투영기: 보는 방향 view (눈 쪽), 화면 위 = up 을 투영한 방향."""
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    v = np.asarray(view, float)
    v /= np.linalg.norm(v)
    u = np.asarray(up, float)
    xd = np.cross(u, v)
    if np.linalg.norm(xd) < 1e-9:
        xd = np.array([1.0, 0, 0])
    xd /= np.linalg.norm(xd)
    return HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*v), gp_Dir(*xd)))


def hlr(shapes, view=ISO_DIR, hidden=False, poly=False, up=(0.0, 0.0, 1.0)):
    """숨은선 제거: (보이는 선, 숨은 선) — 투영 평면 (화면 x 오른쪽, y 위) 의 꺾은선 목록.
    poly: 메시로 (HLRBRep_PolyAlgo — 큰 조립품에서 빠름)."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    comp = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(comp)
    for s in shapes:
        bld.Add(comp, s)
    pr = projector(view, up)
    if poly:
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape
        BRepMesh_IncrementalMesh(comp, 0.3, False, 0.3, True)
        algo = HLRBRep_PolyAlgo(comp)
        algo.Projector(pr)
        algo.Update()
        h = HLRBRep_PolyHLRToShape()
        h.Update(algo)
    else:
        from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
        algo = HLRBRep_Algo()
        algo.Add(comp)
        algo.Projector(pr)
        algo.Update()
        algo.Hide()
        h = HLRBRep_HLRToShape(algo)
    vis = []
    for get in (h.VCompound, h.OutLineVCompound):
        try:
            vis += _edges_polylines(get())
        except Exception:  # noqa: BLE001
            pass
    hid = []
    if hidden:
        for get in (h.HCompound, h.OutLineHCompound):
            try:
                hid += _edges_polylines(get())
            except Exception:  # noqa: BLE001
                pass
    # 투영 상자 밖으로 뻗은 선 (B-스플라인 윤곽선의 엉뚱한 끝) 은 버림
    lim = _proj_box(shapes, view, up)
    if lim is not None:
        (ax, ay), (bx, by) = lim
        pad = 0.05 * max(bx - ax, by - ay, 1.0) + 1.0

        def ok(P):
            return bool(np.all((P[:, 0] >= ax - pad) & (P[:, 0] <= bx + pad) & (P[:, 1] >= ay - pad) & (P[:, 1] <= by + pad)))
        vis = [P for P in vis if ok(P)]
        hid = [P for P in hid if ok(P)]
    return vis, hid


def _proj_box(shapes, view, up):
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        b = Bnd_Box()
        for s in shapes:
            BRepBndLib.Add_s(s, b)
        p0, p1 = b.CornerMin(), b.CornerMax()
        pts = [project_point((x, y, z), view, up) for x in (p0.X(), p1.X()) for y in (p0.Y(), p1.Y())
               for z in (p0.Z(), p1.Z())]
        P = np.array(pts)
        return P.min(0), P.max(0)
    except Exception:  # noqa: BLE001
        return None


# 3각법 정투상 (보는 쪽 방향, 화면 위): 정면도 = 앞 (−y) 에서 (x, z), 평면도 = 위에서 (x, y), 우측면도 = 오른쪽 (+x) 에서 (y, z)
FRONT = ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0))
TOP = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
RIGHT = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def project_point(p, view=ISO_DIR, up=(0.0, 0.0, 1.0)):
    """3D 점을 hlr 과 같은 화면 좌표로."""
    v = np.asarray(view, float)
    v /= np.linalg.norm(v)
    xd = np.cross(np.asarray(up, float), v)
    xd /= np.linalg.norm(xd)
    yd = np.cross(v, xd)
    q = np.asarray(p, float)
    return float(q @ xd), float(q @ yd)


def section(shape, y0, ext=1e5):
    """평면 y = y0 으로 자른 단면: [(바깥 (n, 2) (x, z), [구멍 …])]."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    pln = gp_Pln(gp_Ax3(gp_Pnt(0, float(y0), 0), gp_Dir(0, 1, 0), gp_Dir(1, 0, 0)))
    face = BRepBuilderAPI_MakeFace(pln, -ext, ext, -ext, ext).Face()
    try:
        com = BRepAlgoAPI_Common(shape, face).Shape()
    except Exception:  # noqa: BLE001
        return []
    out = []
    ex = TopExp_Explorer(com, TopAbs_FACE)
    if not ex.More():                                     # 교집합이 빈 결과 (큰 주물 상형의 B-스플라인 형면) → 자른 선으로
        return _section_by_edges(shape, face)
    while ex.More():
        f = TopoDS.Face_s(ex.Current()) if hasattr(TopoDS, "Face_s") else TopoDS.Face(ex.Current())
        ex.Next()
        outer_w = BRepTools.OuterWire_s(f)
        loops, outer = [], None
        we = TopExp_Explorer(f, TopAbs_WIRE)
        while we.More():
            w = TopoDS.Wire_s(we.Current()) if hasattr(TopoDS, "Wire_s") else TopoDS.Wire(we.Current())
            we.Next()
            pts = _wire_points(w)
            if len(pts) < 3:
                continue
            if w.IsSame(outer_w):
                outer = pts
            else:
                loops.append(pts)
        if outer is not None:
            out.append((outer, loops))
    return out


def _section_by_edges(shape, face):
    """평면과의 교선 (BRepAlgoAPI_Section) 을 닫힌 고리로 이어 단면으로 — 교집합 (Common) 이 빈 결과를 낼 때.
    고리는 넓이 큰 것이 바깥, 그 안에 든 것은 구멍."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.collections import HSequence_TopoDS_Shape

    from .die3d import _area, _inside
    try:
        sec = BRepAlgoAPI_Section(shape, face)
        sec.Build()
        edges = HSequence_TopoDS_Shape()
        ex = TopExp_Explorer(sec.Shape(), TopAbs_EDGE)
        while ex.More():
            edges.Append(ex.Current())
            ex.Next()
        if edges.Length() == 0:
            return []
        wires = ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(edges, 0.05, False)
        loops = []
        for i in range(1, wires.Length() + 1):
            pts = _wire_points(TopoDS.Wire(wires.Value(i)))
            if len(pts) >= 3 and abs(_area(pts)) > 1e-6:
                loops.append(pts)
    except Exception:  # noqa: BLE001
        return []
    loops.sort(key=lambda P: -abs(_area(P)))
    out = []
    used = [False] * len(loops)
    for i, P in enumerate(loops):
        if used[i]:
            continue
        holes = []
        for j in range(i + 1, len(loops)):
            if not used[j] and _inside(P, tuple(loops[j].mean(0))):
                holes.append(loops[j])
                used[j] = True
        out.append((P, holes))
    return out


def _wire_points(w, samples=16):
    """고리 꼭짓점 (x, z) — 모서리 순서대로 (BRepTools_WireExplorer)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_REVERSED
    pts = []
    we = BRepTools_WireExplorer(w)
    while we.More():
        e = we.Current()
        c = BRepAdaptor_Curve(e)
        a, b = c.FirstParameter(), c.LastParameter()
        n = 1 if c.GetType() == GeomAbs_Line else samples
        ts = [a + (b - a) * i / n for i in range(n + 1)]
        if e.Orientation() == TopAbs_REVERSED:
            ts = ts[::-1]
        for t_ in ts[:-1]:
            q = c.Value(t_)
            pts.append((q.X(), q.Z()))
        we.Next()
    return np.asarray(pts)


def hatch(loops, spacing, angle_deg=45.0):
    """단면 고리 (바깥 · 구멍 모두) 안을 빗금 — [(p, q)] 선분 (같은 좌표)."""
    if not loops:
        return []
    a = math.radians(angle_deg)
    d = np.array([math.cos(a), math.sin(a)])
    nrm = np.array([-d[1], d[0]])
    segs = []
    for P in loops:
        P = np.asarray(P, float)
        segs.append((P, np.roll(P, -1, axis=0)))
    allp = np.vstack([P for P, _ in segs])
    proj = allp @ nrm
    out = []
    for c in np.arange(proj.min() + spacing / 2, proj.max(), spacing):
        ts = []
        for A, B in segs:
            pa, pb = A @ nrm - c, B @ nrm - c
            m = (pa * pb < 0)
            if not m.any():
                continue
            u = pa[m] / (pa[m] - pb[m])
            X = A[m] + u[:, None] * (B[m] - A[m])
            ts += list(X @ d)
        ts.sort()
        base = c * nrm
        for i in range(0, len(ts) - 1, 2):
            out.append((base + ts[i] * d, base + ts[i + 1] * d))
    return out
