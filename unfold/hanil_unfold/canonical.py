"""자유곡면(B-스플라인)으로 저장된 평면·원통·원뿔을 원래 모양으로 되돌린다.

다른 CAD 에서 변환한 STEP(예: HOOPS Exchange, 일부 NX·CATIA 내보내기)은 평면과 절곡 R 까지
모두 B-스플라인 곡면으로 저장하는 경우가 많다. 그대로 두면 판금도 "자유곡면" 으로 보여
정확 전개와 절곡 표를 쓸 수 없으므로, 열 때 면마다 실제 모양을 알아내 바꿔 끼운다.

판별 순서 (허용 오차 tol mm 안에서)
  1. 평면              GeomLib_IsPlanarSurface
  2. 원통 · 원뿔       ShapeAnalysis_CanonicalRecognition
  3. 그 밖의 해석 곡면  GeomConvert_SurfToAnaSurf
알아낸 면은 같은 모서리(경계선)를 그대로 써서 다시 만들고, 바깥 방향도 원래대로 맞춘다.
다시 만든 솔리드가 올바르지 않으면 원래 솔리드를 그대로 쓴다.
"""
from __future__ import annotations

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepTools import BRepTools
from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface, Geom_Plane
from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_OffsetSurface
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.GeomConvert import GeomConvert_SurfToAnaSurf
from OCP.GeomLib import GeomLib_IsPlanarSurface
from OCP.gp import gp_Cone, gp_Cylinder, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition
from OCP.ShapeFix import ShapeFix_Face, ShapeFix_Shape
from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_SOLID, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shell, TopoDS_Solid

_FREEFORM = (GeomAbs_BSplineSurface, GeomAbs_BezierSurface, GeomAbs_OffsetSurface)


def _explore(shape, kind):
    exp = TopExp_Explorer(shape, kind)
    while exp.More():
        yield exp.Current()
        exp.Next()


def has_freeform(solid) -> bool:
    return any(BRepAdaptor_Surface(TopoDS.Face(f)).GetType() in _FREEFORM
               for f in _explore(solid, TopAbs_FACE))


def recognize(face, tol):
    """면의 실제 해석 곡면 (Geom_Surface) 또는 None."""
    surf = BRep_Tool.Surface_s(face)
    try:
        pl = GeomLib_IsPlanarSurface(surf, tol)
        if pl.IsPlanar():
            return Geom_Plane(pl.Plan())
    except Exception:
        pass
    cr = ShapeAnalysis_CanonicalRecognition(face)
    cyl = gp_Cylinder()
    if cr.IsCylinder(tol, cyl):
        return Geom_CylindricalSurface(cyl)
    cone = gp_Cone()
    if cr.IsCone(tol, cone):
        return Geom_ConicalSurface(cone)
    try:
        u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
        conv = GeomConvert_SurfToAnaSurf(surf)
        ana = conv.ConvertToAnalytical(tol, u0, u1, v0, v1)
        if ana is not None:
            return ana
    except Exception:
        pass
    return None


def _inside_uv(face):
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    for n in (1, 3, 5, 9):
        for i in range(n):
            for j in range(n):
                u = u0 + (u1 - u0) * (i + 0.5) / n
                v = v0 + (v1 - v0) * (j + 0.5) / n
                if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN:
                    return u, v
    return 0.5 * (u0 + u1), 0.5 * (v0 + v1)


def rebuild_face(face, surf):
    """같은 경계선으로 새 곡면 위에 면을 다시 만든다.

    경계선은 원래 곡면의 방향에 맞춰 돌고 있다. 새 곡면의 방향이 반대면 넓이가 음수로 나오므로,
    곡면 그대로와 u 방향을 뒤집은 것 둘 다 만들어 넓이가 원래와 같은 쪽을 쓴다.
    (넓이가 양수로 맞으면 경계선 방향이 새 곡면에서도 같으므로 바깥 방향도 원래와 같다.)
    """
    from OCP.TopAbs import TopAbs_FORWARD

    fwd = TopoDS.Face(face.Oriented(TopAbs_FORWARD))
    a_old = _area(fwd)
    outer = BRepTools.OuterWire_s(fwd)
    inner = [TopoDS.Wire(w) for w in _explore(fwd, TopAbs_WIRE) if not w.IsSame(outer)]
    for cand in (surf, surf.UReversed()):
        mk = BRepBuilderAPI_MakeFace(cand, outer, True)
        for w in inner:
            mk.Add(w)
        if not mk.IsDone():
            continue
        fix = ShapeFix_Face(mk.Face())
        fix.Perform()
        nf = fix.Face()
        a_new = _area(nf)
        if a_new > 0 and abs(a_new - a_old) <= 0.005 * abs(a_old) + 1e-6:
            nf.Orientation(face.Orientation())
            return nf
    raise ValueError("다시 만든 면의 넓이가 원래와 다릅니다")


def _area(face):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    return g.Mass()


def canonicalize(solid, tol=0.01):
    """(새 솔리드, 바꾼 면 수, 자유곡면으로 남은 면 수). 실패하면 원래 솔리드."""
    if not has_freeform(solid):
        return solid, 0, 0
    B = BRep_Builder()
    shell = TopoDS_Shell()
    B.MakeShell(shell)
    changed = kept = 0
    for f in _explore(solid, TopAbs_FACE):
        face = TopoDS.Face(f)
        new = face
        if BRepAdaptor_Surface(face).GetType() in _FREEFORM:
            surf = recognize(face, tol)
            if surf is not None:
                try:
                    new = rebuild_face(face, surf)
                    changed += 1
                except Exception:
                    new = face
                    kept += 1
            else:
                kept += 1
        B.Add(shell, new)
    sol = TopoDS_Solid()
    B.MakeSolid(sol)
    B.Add(sol, shell)
    fix = ShapeFix_Shape(sol)
    fix.Perform()
    out = fix.Shape()
    solids = [TopoDS.Solid(s) for s in _explore(out, TopAbs_SOLID)]
    if len(solids) != 1 or not BRepCheck_Analyzer(solids[0]).IsValid():
        return solid, 0, kept + changed
    return solids[0], changed, kept
