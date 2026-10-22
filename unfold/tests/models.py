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
