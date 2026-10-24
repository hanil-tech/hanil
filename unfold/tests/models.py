"""시험용 판금 모델을 만든다.

단면(플랜지 길이와 절곡)을 주면 두께 t, 폭 width 로 밀어낸 솔리드를 만든다.
펼친 길이를 손으로 계산한 값과 비교하기 쉽게, 길이는 모두 절곡 접선 사이의 직선 길이다.
"""
from __future__ import annotations

import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec


def profile_part(steps, t, width):
    """steps: [("L", 길이), ("B", 각도(도, +는 왼쪽으로 꺾음), 안쪽 반지름), ...]

    XY 평면에 단면을 그리고 Z 방향으로 width 만큼 밀어낸다.
    기준선 A 를 따라가고, 두께는 진행 방향 왼쪽으로 준다.
    """
    a_edges, b_edges = [], []
    x, y, h = 0.0, 0.0, 0.0     # 기준선 A 위의 현재 위치와 진행 각도

    def left(hh):
        return (-math.sin(hh), math.cos(hh))

    for st in steps:
        if st[0] == "L":
            L = st[1]
            nx, ny = x + L * math.cos(h), y + L * math.sin(h)
            lx, ly = left(h)
            a_edges.append(("L", (x, y), (nx, ny)))
            b_edges.append(("L", (x + t * lx, y + t * ly), (nx + t * lx, ny + t * ly)))
            x, y = nx, ny
        else:
            ang = math.radians(st[1])
            R = st[2]
            lx, ly = left(h)
            if ang > 0:
                # 왼쪽으로 꺾음: 중심은 왼쪽, A 가 바깥
                ra = R + t
                cx, cy = x + ra * lx, y + ra * ly
            else:
                ra = R
                cx, cy = x - ra * lx, y - ra * ly
            rb = ra - t if ang > 0 else ra + t
            a0 = math.atan2(y - cy, x - cx)

            def arc(r, a0=a0, cx=cx, cy=cy, ang=ang):
                pts = [(cx + r * math.cos(a0 + ang * s), cy + r * math.sin(a0 + ang * s))
                       for s in (0.0, 0.5, 1.0)]
                return ("A",) + tuple(pts)

            a_edges.append(arc(ra))
            b_edges.append(arc(rb))
            x, y = cx + ra * math.cos(a0 + ang), cy + ra * math.sin(a0 + ang)
            h += ang

    def mk(e, reverse=False):
        if e[0] == "L":
            p, q = e[1], e[2]
            if reverse:
                p, q = q, p
            return BRepBuilderAPI_MakeEdge(gp_Pnt(*p, 0), gp_Pnt(*q, 0)).Edge()
        p, m, q = e[1], e[2], e[3]
        if reverse:
            p, q = q, p
        arc = GC_MakeArcOfCircle(gp_Pnt(*p, 0), gp_Pnt(*m, 0), gp_Pnt(*q, 0)).Value()
        return BRepBuilderAPI_MakeEdge(arc).Edge()

    wire = BRepBuilderAPI_MakeWire()
    for e in a_edges:
        wire.Add(mk(e))
    end_a, end_b = _end(a_edges[-1]), _end(b_edges[-1])
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*end_a, 0), gp_Pnt(*end_b, 0)).Edge())
    for e in reversed(b_edges):
        wire.Add(mk(e, reverse=True))
    st_a, st_b = _start(a_edges[0]), _start(b_edges[0])
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*st_b, 0), gp_Pnt(*st_a, 0)).Edge())

    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, width)).Shape()


def _start(e):
    return e[1]


def _end(e):
    return e[2] if e[0] == "L" else e[3]


def flat_length(steps, t, k):
    total = 0.0
    for st in steps:
        if st[0] == "L":
            total += st[1]
        else:
            total += math.radians(abs(st[1])) * (st[2] + k * t)
    return total


def drill(shape, x, y, z, d, axis=(0, 1, 0), depth=1000):
    """(x,y,z) 를 지나는 axis 방향 구멍. 앞뒤로 충분히 길게 뚫는다."""
    ax = gp_Dir(*axis)
    start = gp_Pnt(x - ax.X() * depth / 2, y - ax.Y() * depth / 2, z - ax.Z() * depth / 2)
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(start, ax), d / 2, depth).Shape()
    return BRepAlgoAPI_Cut(shape, cyl).Shape()


def tube(outer_r, t, length):
    outer = BRepPrimAPI_MakeCylinder(outer_r, length).Shape()
    inner = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)),
                                     outer_r - t, length + 2).Shape()
    return BRepAlgoAPI_Cut(outer, inner).Shape()


def rotated(shape, axis=(1, 2, 3), angle_deg=37.0, move=(15, -40, 7)):
    tr = gp_Trsf()
    tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(*axis)), math.radians(angle_deg))
    mv = gp_Trsf()
    mv.SetTranslation(gp_Vec(*move))
    return BRepBuilderAPI_Transform(shape, mv.Multiplied(tr), True).Shape()


def _place(shape, rows, offset):
    tr = gp_Trsf()
    (a, b, c), (d, e, f), (g, h, i) = rows
    tr.SetValues(a, b, c, offset[0], d, e, f, offset[1], g, h, i, offset[2])
    return BRepBuilderAPI_Transform(shape, tr, True).Shape()


def tray(length=100.0, width=80.0, height=30.0, t=1.6, r=1.6, relief=5.0):
    """네 변을 세운 쟁반 모양. 모서리는 relief 만큼 띄워 둔다.

    바닥 바깥면이 z=0, 바닥은 x∈[0,length], y∈[0,width].
    height 는 절곡 접선부터 플랜지 끝까지의 직선 길이다.
    """
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    top = height + r + t
    ux = profile_part([("L", height), ("B", 90, r), ("L", length),
                       ("B", 90, r), ("L", height)], t, width)
    ux = _place(ux, ((0, 1, 0), (0, 0, -1), (-1, 0, 0)), (-(r + t), width, top))
    uy = profile_part([("L", height), ("B", 90, r), ("L", width),
                       ("B", 90, r), ("L", height)], t, length - 2 * relief)
    uy = _place(uy, ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), (relief, -(r + t), top))
    fused = BRepAlgoAPI_Fuse(ux, uy).Shape()
    unify = ShapeUpgrade_UnifySameDomain(fused, True, True, True)
    unify.Build()
    return unify.Shape()


def funnel(r_bottom=40.0, r_top=80.0, height=60.0, t=2.0):
    """원뿔대 깔때기 (바깥면 기준 반지름). 안쪽은 법선 방향으로 t 만큼 들어간 원뿔."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopoDS import TopoDS

    solid = BRepPrimAPI_MakeCone(r_bottom, r_top, height).Shape()
    caps = TopTools_ListOfShape()
    exp = TopExp_Explorer(solid, TopAbs_FACE)
    while exp.More():
        if BRepAdaptor_Surface(TopoDS.Face(exp.Current())).GetType() == GeomAbs_Plane:
            caps.Append(exp.Current())
        exp.Next()
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(solid, caps, -t, 1e-4)
    return mk.Shape()


def oblique_bracket(t=2.0, r=2.0, l1=60.0, l2=30.0, width=50.0, skew_deg=25.0):
    """절곡선이 판 바깥선과 비스듬한 ㄱ자: 밀어낸 뒤 양 끝을 기울어진 평면으로 잘라 낸다."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    part = profile_part([("L", l1), ("B", 90, r), ("L", l2)], t, width + 200)
    part = _place(part, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, -100))
    big = 1000.0
    sk = math.radians(skew_deg)
    for side, z0 in ((-1, 0.0), (1, width)):
        box = BRepPrimAPI_MakeBox(gp_Pnt(-big / 2, -big / 2, 0), big, big, big).Shape()
        tr = gp_Trsf()
        # 기울어진 자르기 면: x 방향으로 skew 만큼 돌린 평면
        tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), sk)
        if side < 0:
            mirror = gp_Trsf()
            mirror.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))
            tr = tr.Multiplied(mirror)
        mv = gp_Trsf()
        mv.SetTranslation(gp_Vec(0, 0, z0))
        box = BRepBuilderAPI_Transform(box, mv.Multiplied(tr), True).Shape()
        part = BRepAlgoAPI_Cut(part, box).Shape()
    return part


def dish(sphere_r=150.0, depth=40.0, t=1.2):
    """구면 접시 (자유곡면 성형품 대용): 구를 잘라 두께 t 의 껍질로."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.collections import List_TopoDS_Shape
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    a1 = math.asin((sphere_r - depth) / sphere_r)
    solid = BRepPrimAPI_MakeSphere(sphere_r, a1, math.pi / 2).Shape()
    caps = List_TopoDS_Shape()
    exp = TopExp_Explorer(solid, TopAbs_FACE)
    while exp.More():
        if BRepAdaptor_Surface(TopoDS.Face(exp.Current())).GetType() == GeomAbs_Plane:
            caps.Append(exp.Current())
        exp.Next()
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(solid, caps, -t, 1e-4)
    return mk.Shape()


def bspline_panel(t=1.0):
    """자동차 패널처럼 두 방향으로 휜 자유곡면(B-스플라인) 판."""
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    from OCP.collections import Array2_gp_Pnt as TColgp_Array2OfPnt
    n = 6
    arr = TColgp_Array2OfPnt(1, n, 1, n)
    for i in range(n):
        for j in range(n):
            x, y = i * 40.0, j * 30.0
            z = 25 * math.sin(math.pi * i / (n - 1)) * math.sin(math.pi * j / (n - 1)) + 0.1 * x
            arr.SetValue(i + 1, j + 1, gp_Pnt(x, y, z))
    surf = GeomAPI_PointsToBSplineSurface(arr).Surface()
    face = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidBySimple(face, t)
    return mk.Shape()


def sharp_channel(w=100.0, h=40.0, t=3.2, length=300.0):
    """R 없이 날카롭게 꺾은 ㄷ 형강 (바깥 치수 w × h). 바닥이 기준면."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    pts = [(0, h), (0, 0), (w, 0), (w, h), (w - t, h), (w - t, t), (t, t), (t, h)]
    mp = BRepBuilderAPI_MakePolygon()
    for x, y in pts:
        mp.Add(gp_Pnt(x, y, 0))
    mp.Close()
    f = BRepBuilderAPI_MakeFace(mp.Wire()).Face()
    return BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, length)).Shape()


def sharp_hat(t=2.0, length=200.0):
    """R 없는 모자 단면: 날개 30, 높이 40, 윗면 80 (바깥 치수). 볼록·오목 모서리가 섞인다."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    pts = [(0, 0), (30 + t, 0), (30 + t, 40 - t), (110 - t, 40 - t), (110 - t, 0), (140, 0), (140, t),
           (110, t), (110, 40), (30, 40), (30, t), (0, t)]
    mp = BRepBuilderAPI_MakePolygon()
    for x, y in pts:
        mp.Add(gp_Pnt(x, y, 0))
    mp.Close()
    f = BRepBuilderAPI_MakeFace(mp.Wire()).Face()
    return BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, length)).Shape()


def nested_assembly_step(path):
    """시험용 다단계 STEP: TRUCK BOX ⊃ SIDE PANEL ASSY ×2 (패널·브래킷·NUT M8·와셔), FLOOR PLATE, BOSS."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    def ring(ro, ri, h):
        return BRepAlgoAPI_Cut(BRepPrimAPI_MakeCylinder(ro, h).Shape(),
                               BRepPrimAPI_MakeCylinder(ri, h).Shape()).Shape()

    def at(x, y, z):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(x, y, z))
        return TopLoc_Location(t)

    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    def named(label, name):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        return label

    panel = named(st.AddShape(tray(), False), "SIDE PANEL")
    bracket = named(st.AddShape(profile_part([("L", 50), ("B", 90, 2), ("L", 30)], 2.0, 40), False),
                    "BRACKET")
    nut = named(st.AddShape(ring(6.5, 4.0, 6.5), False), "NUT M8")
    washer = named(st.AddShape(ring(8.0, 4.2, 1.6), False), "W1")
    floor = named(st.AddShape(BRepPrimAPI_MakeBox(400, 300, 3.2).Shape(), False), "FLOOR PLATE")
    boss = named(st.AddShape(ring(15, 8, 60), False), "BOSS")
    sub = named(st.NewShape(), "SIDE PANEL ASSY")
    st.AddComponent(sub, panel, at(0, 0, 0))
    for k in range(2):
        st.AddComponent(sub, bracket, at(200 + 60 * k, 0, 0))
    for k in range(4):
        st.AddComponent(sub, nut, at(20 * k, 200, 0))
        st.AddComponent(sub, washer, at(20 * k, 230, 0))
    top = named(st.NewShape(), "TRUCK BOX")
    st.AddComponent(top, sub, at(0, 0, 0))
    st.AddComponent(top, sub, at(0, 500, 0))
    st.AddComponent(top, floor, at(0, 0, -50))
    st.AddComponent(top, boss, at(500, 0, 0))
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.Transfer(doc, STEPControl_AsIs)
    assert w.Write(path) == IFSelect_RetDone
    return path
