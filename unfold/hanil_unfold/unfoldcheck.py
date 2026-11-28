"""전개 검증표: 펼친 결과를 원래 3D 와 대조해 수치로 보인다 (실무에서 전개도를 믿고 쓰기 위한 확인).

판금 (절곡) 전개
  1. 넓이      펼친 넓이 (외곽 − 구멍) ↔ 3D 가운데 면 넓이 (부피 ÷ t) + 절곡마다 (K − 0.5)·t·θ·L (중립선 옮김)
  2. 구멍 지름  펼친 둥근 구멍 ↔ 3D 평면의 원 모서리 (가장 가까운 지름)
  3. 절곡선 길이 펼친 절곡선 ↔ 3D 절곡 (원통 면) 길이
  4. 외곽 겹침  펼친 외곽·구멍 선이 서로 엇갈리지 않음 (펼치면서 플랜지가 겹치면 잘라 낼 수 없음)
  5. 부피 보존  펼친 겉면 넓이 × t ↔ 부품 부피 (빠진 면·겹친 면이 없음)
성형품 (원스텝) 전개
  넓이 비 (블랭크 / 제품), 모양이 좋은 삼각형 비, 펼친 외곽 겹침
"""
from __future__ import annotations

import math

import numpy as np

OK, WARN, NG = "적합", "주의", "부적합"
HEAD = ["항목", "3D", "전개", "차이", "기준", "판정"]


def _volume(solid):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, g)
    return float(g.Mass())


def _circles_3d(solid):
    """평면 면의 원 모서리 지름들."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    ex = TopExp_Explorer(solid, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current()) if hasattr(TopoDS, "Face_s") else TopoDS.Face(ex.Current())
        try:
            if BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane:
                ee = TopExp_Explorer(f, TopAbs_EDGE)
                while ee.More():
                    e = TopoDS.Edge_s(ee.Current()) if hasattr(TopoDS, "Edge_s") else TopoDS.Edge(ee.Current())
                    c = BRepAdaptor_Curve(e)
                    if c.GetType() == GeomAbs_Circle:
                        out.append(2 * float(c.Circle().Radius()))
                    ee.Next()
        except Exception:  # noqa: BLE001 — 읽지 못한 면은 건너뜀
            pass
        ex.Next()
    return np.array(sorted(set(round(d, 4) for d in out)))


def _curv_integral(solid):
    """원통·원뿔 면의 ∫ κ dA (둘레 방향 곡률) — 안·바깥 면을 다 더한 값 (÷ 2 하면 가운데 면 몫).
    원통 A / R, 원뿔 cos α · A / r_평균 (r_평균 = 면 가운데 높이의 반지름)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    tot = 0.0
    ex = TopExp_Explorer(solid, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current()) if hasattr(TopoDS, "Face_s") else TopoDS.Face(ex.Current())
        try:
            ad = BRepAdaptor_Surface(f)
            kind = ad.GetType()
            if kind in (GeomAbs_Cylinder, GeomAbs_Cone):
                g = GProp_GProps()
                BRepGProp.SurfaceProperties_s(f, g)
                A = float(g.Mass())
                if kind == GeomAbs_Cylinder:
                    tot += A / float(ad.Cylinder().Radius())
                else:
                    c = ad.Cone()
                    a = float(c.SemiAngle())
                    u0, u1, v0, v1 = BRepTools.UVBounds_s(f)
                    r_m = float(c.RefRadius()) + 0.5 * (v0 + v1) * math.sin(a)
                    if r_m > 1e-6:
                        tot += math.cos(a) * A / r_m
        except Exception:  # noqa: BLE001
            pass
        ex.Next()
    return tot


def _segments(loops):
    segs = []
    for k, P in enumerate(loops):
        P = np.asarray(P, float)
        for i in range(len(P)):
            segs.append((k, i, P[i], P[(i + 1) % len(P)], len(P)))
    return segs


def crossings(loops, max_seg=4000):
    """닫힌 선들 사이·자기 자신의 엇갈림 수 (이웃 선분은 뺌)."""
    segs = _segments(loops)
    if len(segs) > max_seg:
        step = int(math.ceil(len(segs) / max_seg))
        loops = [np.asarray(P, float)[::step] for P in loops]
        segs = _segments(loops)
    if len(segs) < 4:
        return 0
    A = np.array([s[2] for s in segs])
    B = np.array([s[3] for s in segs])
    lid = np.array([s[0] for s in segs])
    idx = np.array([s[1] for s in segs])
    nlen = np.array([s[4] for s in segs])
    n = len(segs)
    cnt = 0
    d = B - A
    for i0 in range(0, n, 256):
        a, b, da = A[i0:i0 + 256, None], B[i0:i0 + 256, None], d[i0:i0 + 256, None]

        def cross(u, v):
            return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]
        d1 = cross(da, A[None] - a)
        d2 = cross(da, B[None] - a)
        d3 = cross(d[None], a - A[None])
        d4 = cross(d[None], b - A[None])
        hit = (d1 * d2 < -1e-12) & (d3 * d4 < -1e-12)
        li, ii = lid[i0:i0 + 256, None], idx[i0:i0 + 256, None]
        same = li == lid[None]
        adj = same & ((np.abs(ii - idx[None]) <= 1) | (np.abs(ii - idx[None]) == nlen[None] - 1))
        hit &= ~adj
        cnt += int(hit.sum())
    return cnt // 2


def check(solid, result, settings=None):
    """[(항목, 3D, 전개, 차이, 기준, 판정)]."""
    from .nesting import NestPart
    rows = []
    t = result.thickness
    try:
        part = NestPart.from_result("p", result)
    except ValueError as e:
        return [["외곽", "", str(e), "", "닫힌 외곽", NG]]
    loops = ([part.outer] if part.outer is not None else []) + list(part.holes)
    fi = getattr(result, "forming", None)
    if fi is not None:
        r_area = fi.blank_area / max(fi.product_area, 1e-9)
        rows.append(["넓이 비 (블랭크 / 제품)", f"{fi.product_area:,.1f} mm²", f"{fi.blank_area:,.1f} mm²",
                     f"{(r_area - 1) * 100:+.2f} %", "0.8 ~ 1.25 (성형 늘림)", OK if 0.8 < r_area < 1.25 else NG])
        if fi.reliable is not None:
            good = float(np.mean(fi.reliable))
            rows.append(["모양이 좋은 삼각형 (가장 작은 각 > 5°)", "", f"{good:.1%}", "", "≥ 95 %",
                         OK if good >= 0.95 else WARN])
    elif solid is not None:
        V = _volume(solid)
        a_mid = V / t
        if getattr(result, "rolled", None):         # 말아 만든 원통·원뿔: 굽은 면 전체가 중립선으로 옮겨 감
            corr = (result.k_factor - 0.5) * t * _curv_integral(solid) / 2
        else:
            corr = sum((b.k - 0.5) * t * math.radians(b.angle_deg) * b.length for b in result.bends)
        exp = a_mid + corr
        dev = (part.area - exp) / max(exp, 1e-9)
        rows.append(["넓이 (가운데 면 + 중립선 옮김)", f"{exp:,.2f} mm²", f"{part.area:,.2f} mm²", f"{dev * 100:+.3f} %",
                     "± 0.2 %", OK if abs(dev) <= 0.002 else WARN if abs(dev) <= 0.01 else NG])
        d3 = _circles_3d(solid)
        # 펼친 둥근 구멍: 전개도의 원 (Arc full) 지름 그대로
        fl_eq = [2 * float(e.radius) for e in result.entities
                 if getattr(e, "layer", "") == "CUT" and type(e).__name__ == "Arc" and getattr(e, "full", False)]
        if fl_eq and len(d3):
            devs = [min(abs(d - x) for x in d3) for d in fl_eq]
            worst = int(np.argmax(devs))
            rows.append([f"구멍 지름 ({len(fl_eq)} 개)", f"Ø{d3[np.argmin(np.abs(d3 - fl_eq[worst]))]:g}",
                         f"Ø{fl_eq[worst]:.3f}", f"{devs[worst]:.3f} mm", "≤ 0.02 mm (가장 큰 차)",
                         OK if max(devs) <= 0.02 else WARN if max(devs) <= 0.1 else NG])
        if result.bends:
            dl = []
            for b in result.bends:
                (x1, y1), (x2, y2) = b.line
                dl.append(abs(math.hypot(x2 - x1, y2 - y1) - b.length))
            rows.append([f"절곡선 길이 ({len(result.bends)} 개)", f"{max(b.length for b in result.bends):,.2f} mm (가장 긴 것)",
                         "", f"{max(dl):.3f} mm", "≤ 0.02 mm", OK if max(dl) <= 0.02 else WARN])
    cr = crossings(loops)
    rows.append(["외곽·구멍 선 겹침", "", f"{cr} 곳", "", "0 곳", OK if cr == 0 else NG])
    cov = getattr(result, "coverage", 1.0)
    if fi is None and not getattr(result, "rolled", None):     # 말아 만든 부품은 겉면이 가운데 면보다 커서 맞지 않음
        rows.append(["부피 보존 (펼친 넓이 × t ÷ 부피)", "", f"{cov:.4f}", f"{(cov - 1) * 100:+.2f} %", "0.98 ~ 1.02",
                     OK if 0.98 <= cov <= 1.02 else WARN])
    return rows


def verdict(rows):
    v = [r[5] for r in rows]
    return NG if NG in v else WARN if WARN in v else OK
