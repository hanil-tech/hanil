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


def drawn_cup(R=50.0, H=50.0, rf=8.0, t=1.0):
    """딥 드로잉 원통 컵 (바닥 모서리 R rf, 위가 열림). 블랭크 지름 교과서 값 √(d² + 4dh) 근처."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.collections import List_TopoDS_Shape
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    s = BRepPrimAPI_MakeCylinder(R, H).Shape()
    fl = BRepFilletAPI_MakeFillet(s)
    exp = TopExp_Explorer(s, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        if abs(c.Value(c.FirstParameter()).Z()) < 1e-6 and abs(c.Value(c.LastParameter()).Z()) < 1e-6:
            fl.Add(rf, e)
        exp.Next()
    s = fl.Shape()
    top = List_TopoDS_Shape()
    exp = TopExp_Explorer(s, TopAbs_FACE)
    while exp.More():
        fc = TopoDS.Face(exp.Current())
        a = BRepAdaptor_Surface(fc)
        if a.GetType() == GeomAbs_Plane and abs(a.Plane().Location().Z() - H) < 1e-6:
            top.Append(fc)
        exp.Next()
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(s, top, -t, 1e-4)
    return mk.Shape()


def burring(R=20.0, H=8.0, R_out=50.0, t=1.0, ri=2.0):
    """구멍 버링 (플랜지 구멍): 평판 Ø2R_out 가운데 구멍 가장자리를 높이 H 로 세움 (안쪽 R ri) — 단면을 돌려 만듦.
    펼치면 세운 벽이 구멍 안쪽으로 눕혀져 가장자리가 R / (R − H) 배쯤 늘어난다."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp, gp_Pnt

    ro = ri + t
    c = math.cos(math.pi / 4)

    def P(x, z):
        return gp_Pnt(x, 0, z)

    def seg(a, b):
        return BRepBuilderAPI_MakeEdge(P(*a), P(*b)).Edge()

    def arc(a, m, b):
        return BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(P(*a), P(*m), P(*b)).Value()).Edge()

    x0 = R - t
    edges = [seg((R_out, 0), (x0 + ro, 0)),
             arc((x0 + ro, 0), (x0 + ro - ro * c, ro - ro * c), (x0, ro)),
             seg((x0, ro), (x0, H)), seg((x0, H), (R, H)), seg((R, H), (R, t + ri)),
             arc((R, t + ri), (R + ri - ri * c, t + ri - ri * c), (R + ri, t)),
             seg((R + ri, t), (R_out, t)), seg((R_out, t), (R_out, 0))]
    w = BRepBuilderAPI_MakeWire()
    for e in edges:
        w.Add(e)
    face = BRepBuilderAPI_MakeFace(w.Wire()).Face()
    return BRepPrimAPI_MakeRevol(face, gp.OZ_s(), 2 * math.pi).Shape()


def _bspline_shell(pts, t, deg=3):
    """점 격자 (list of rows of (x, y, z)) → B-스플라인 면 → 두께 t 판."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.collections import Array2_gp_Pnt as TColgp_Array2OfPnt
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    from OCP.GeomAbs import GeomAbs_C2
    nu, nv = len(pts), len(pts[0])
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        for j in range(nv):
            arr.SetValue(i + 1, j + 1, gp_Pnt(*pts[i][j]))
    surf = GeomAPI_PointsToBSplineSurface(arr, deg, deg, GeomAbs_C2, 1e-3).Surface()
    face = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidBySimple(face, t)
    sh = mk.Shape()
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, g)
    return sh.Reversed() if g.Mass() < 0 else sh          # 면 방향에 따라 안팎이 뒤집혀 나옴


def hood(L=1500.0, W=1300.0, crown_x=55.0, crown_y=40.0, flange=18.0, t=0.7, n=(57, 51), alpha=0.0,
         band=0.08):
    """자동차 본네트 (후드) 바깥판 대용: 길이 L · 폭 W, 두 방향 크라운, 앞쪽이 내려감 (노즈),
    양쪽 캐릭터 라인 (R 약 6 mm 의 능선), 둘레 플랜지가 아래로 꺾임 (헤밍용, 높이 flange).
    평면 모양은 정사각 격자를 둥근 사각형으로 옮긴 것 (x = s·√(1 − α t²/2), y = t·√(1 − α s²/2)) —
    모서리가 둥글고, 모서리에서는 플랜지가 줄어드는 (shrink) 플랜지가 된다 (불리언 트림 없이)."""
    nu, nv = n
    rows = []
    for i in range(nu):
        sp = -1 + 2 * i / (nu - 1)
        row = []
        for j in range(nv):
            tp = -1 + 2 * j / (nv - 1)
            X = sp * math.sqrt(1 - alpha * tp * tp / 2)
            Y = tp * math.sqrt(1 - alpha * sp * sp / 2)
            x, y = (X + 1) / 2 * L, Y * W / 2
            z = crown_x * math.sin(math.pi * x / L) * 0.7 + crown_y * (1 - (2 * y / W) ** 2)
            z -= 54 * max(0.0, 0.25 - x / L) ** 2 / 0.0625              # 앞쪽 노즈 내려감
            for yl in (-0.3 * W, 0.3 * W):                             # 캐릭터 라인
                z += 4.0 * math.exp(-((y - yl) / 12.0) ** 2) * (1 - abs(sp) ** 8)
            r = (abs(sp) ** 6 + abs(tp) ** 6) ** (1 / 6)                # 가장자리까지 (등고선이 모서리에서 둥긂)
            e = (1 - r) / band
            if e < 1:                                                  # 둘레 플랜지
                z -= flange * (1 - e) ** 2
            row.append((x, y, z))
        rows.append(row)
    return _bspline_shell(rows, t)


def fender(L=950.0, top=170.0, R=35.0, side=420.0, bulge=45.0, arch_r=360.0, t=0.7, n=(33, 31)):
    """자동차 앞 휀다 대용: 위 면 (후드 맞닿는 곳) 이 R 로 90° 꺾여 옆면으로 내려가고, 옆면은 바퀴 쪽으로
    볼록 (bulge), 아래 가운데를 바퀴 아치 (반지름 arch_r) 로 도려냄."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir
    nu, nv = n
    s_tot = top + math.pi / 2 * R + side
    rows = []
    for i in range(nu):
        u = i / (nu - 1)
        x = u * L
        row = []
        for j in range(nv):
            s = j / (nv - 1) * s_tot
            if s <= top:
                y, z = s, 0.0
            elif s <= top + math.pi / 2 * R:
                a = (s - top) / R
                y, z = top + R * math.sin(a), -R * (1 - math.cos(a))
            else:
                y, z = top + R, -R - (s - top - math.pi / 2 * R)
            depth = -z / (R + side)
            y += bulge * math.sin(math.pi * u) * math.sin(math.pi * min(depth, 1.0)) ** 1.5   # 옆면 볼록
            y += 0.04 * x * depth                                                          # 뒤로 갈수록 바깥
            z -= 30 * (u - 0.5) ** 2 * (1 - depth)                                         # 위 선 휨
            row.append((x, y, z))
        rows.append(row)
    sh = _bspline_shell(rows, t)
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(L * 0.5, -500, -R - side - 60), gp_Dir(0, 1, 0)), arch_r, 1500).Shape()
    return BRepAlgoAPI_Cut(sh, cyl).Shape()


def oil_pan(L=320.0, W=220.0, H=110.0, r_corner=25.0, r_bottom=10.0, flange=30.0, t=1.0):
    """깊은 사각 드로잉 (오일 팬·사각 용기): 바닥 L × W, 깊이 H, 세로 모서리 R r_corner, 바닥 R r_bottom,
    둘레 플랜지 폭 flange. 모서리 (네 귀) 가 원통 드로잉처럼 압축·바닥 R 에서 얇아짐 — 성형이 어려운 부품."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane
    from OCP.collections import List_TopoDS_Shape
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    box = BRepPrimAPI_MakeBox(gp_Pnt(-L / 2, -W / 2, 0), L, W, H).Shape()
    fl = BRepFilletAPI_MakeFillet(box)
    exp = TopExp_Explorer(box, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(p0.Z() - p1.Z()) > 1e-6:
            fl.Add(r_corner, e)                     # 세로 모서리
        exp.Next()
    s = fl.Shape()
    fl = BRepFilletAPI_MakeFillet(s)
    exp = TopExp_Explorer(s, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(p0.Z()) < 1e-6 and abs(p1.Z()) < 1e-6:
            fl.Add(r_bottom, e)                     # 바닥 둘레
        exp.Next()
    s = fl.Shape()
    top = List_TopoDS_Shape()
    exp = TopExp_Explorer(s, TopAbs_FACE)
    while exp.More():
        fc = TopoDS.Face(exp.Current())
        a = BRepAdaptor_Surface(fc)
        if a.GetType() == GeomAbs_Plane and abs(a.Plane().Location().Z() - H) < 1e-6:
            top.Append(fc)
        exp.Next()
    mk = BRepOffsetAPI_MakeThickSolid()
    mk.MakeThickSolidByJoin(s, top, -t, 1e-4)
    cup = mk.Shape()
    if flange <= 0:
        return cup
    ring = BRepPrimAPI_MakeBox(gp_Pnt(-L / 2 - flange, -W / 2 - flange, H - t), L + 2 * flange, W + 2 * flange, t).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(-L / 2 + t, -W / 2 + t, H - t - 1), L - 2 * t, W - 2 * t, t + 2).Shape()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    ring = BRepAlgoAPI_Cut(ring, inner).Shape()
    return BRepAlgoAPI_Fuse(cup, ring).Shape()


def spline_section(t=1.6, width=120.0, flats=(30.0, 40.0), ctrl=((0, 0), (30, 0), (70, 40), (100, 40)),
                   nurbs=False):
    """단면이 3차 (베지어) 곡선인 판: 평판 flats[0] — 3차 곡선 — 평판 flats[1] (접하게 이어짐) 을 두께 t 로
    XY 평면에 그려 Z 로 width 만큼 밀어낸 것. 곡선 쪽 면은 일반 원통 (곡선을 민 면) 이라 펼칠 수 있다.
    (솔리드, 가운데 면 단면 길이) — K 0.5 의 정확한 펼친 길이. nurbs=True 면 모든 면을 B-스플라인으로 바꾼다
    (다른 CAD 에서 변환한 STEP 처럼)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.Geom import Geom_BezierCurve, Geom_OffsetCurve, Geom_TrimmedCurve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAdaptor import GeomAdaptor_Curve
    from OCP.collections import Array1_gp_Pnt as TColgp_Array1OfPnt

    arr = TColgp_Array1OfPnt(1, len(ctrl))
    for i, (x, y) in enumerate(ctrl):
        arr.SetValue(i + 1, gp_Pnt(x, y, 0))
    bez = Geom_BezierCurve(arr)
    zdir = gp_Dir(0, 0, 1)

    def tangent(u):
        p, v = gp_Pnt(), gp_Vec()
        bez.D1(u, p, v)
        return (p.X(), p.Y()), (v.X() / v.Magnitude(), v.Y() / v.Magnitude())

    (x0, y0), (dx0, dy0) = tangent(0.0)
    (x1, y1), (dx1, dy1) = tangent(1.0)
    a0, a1 = (x0 - flats[0] * dx0, y0 - flats[0] * dy0), (x1 + flats[1] * dx1, y1 + flats[1] * dy1)

    def side(off):
        """기준 곡선을 진행 방향 왼쪽으로 off 만큼 옮긴 [선, 곡선, 선] 과 그 길이."""
        def sh(p, d):
            return (p[0] - off * d[1], p[1] + off * d[0])
        c = Geom_OffsetCurve(bez, -off, zdir) if off else bez   # Geom_OffsetCurve: +off 는 진행 방향 오른쪽
        cur = Geom_TrimmedCurve(c, 0.0, 1.0)
        p_s, p_e = sh(a0, (dx0, dy0)), sh(a1, (dx1, dy1))
        q_s, q_e = sh((x0, y0), (dx0, dy0)), sh((x1, y1), (dx1, dy1))
        edges = ([BRepBuilderAPI_MakeEdge(gp_Pnt(*p_s, 0), gp_Pnt(*q_s, 0)).Edge()] if flats[0] > 0 else []) + \
            [BRepBuilderAPI_MakeEdge(cur).Edge()] + \
            ([BRepBuilderAPI_MakeEdge(gp_Pnt(*q_e, 0), gp_Pnt(*p_e, 0)).Edge()] if flats[1] > 0 else [])
        L = flats[0] + flats[1] + GCPnts_AbscissaPoint.Length_s(GeomAdaptor_Curve(cur))
        return edges, p_s, p_e, L

    ea, pa_s, pa_e, _ = side(0.0)
    eb, pb_s, pb_e, _ = side(t)
    _, _, _, L_mid = side(t / 2)
    w = BRepBuilderAPI_MakeWire()
    for e in ea:
        w.Add(e)
    w.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*pa_e, 0), gp_Pnt(*pb_e, 0)).Edge())
    for e in reversed(eb):
        w.Add(e)
    w.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*pb_s, 0), gp_Pnt(*pa_s, 0)).Edge())
    face = BRepBuilderAPI_MakeFace(w.Wire(), True).Face()
    solid = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, width)).Shape()
    if nurbs:
        solid = BRepBuilderAPI_NurbsConvert(solid, True).Shape()
    return solid, L_mid


def spline_plate(t=2.0, hole_d=12.0):
    """윤곽이 3차 B-스플라인 (닫힌 곡선) 인 평판 + 구멍. (솔리드, 윤곽 안 넓이)."""
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.collections import HArray1_gp_Pnt as TColgp_HArray1OfPnt
    pts = [(0, 0), (60, -10), (120, 5), (150, 50), (110, 90), (40, 80), (-10, 40)]
    arr = TColgp_HArray1OfPnt(1, len(pts))
    for i, (x, y) in enumerate(pts):
        arr.SetValue(i + 1, gp_Pnt(x, y, 0))
    it = GeomAPI_Interpolate(arr, True, 1e-6)
    it.Perform()
    curve = it.Curve()
    edge = BRepBuilderAPI_MakeEdge(curve).Edge()
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(edge).Wire(), True).Face()
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    solid = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t)).Shape()
    solid = drill(solid, 70, 40, -1, hole_d, axis=(0, 0, 1))
    return solid, g.Mass()
