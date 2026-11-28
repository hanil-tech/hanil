"""용접 견적 — 조립품에서 부품끼리 맞닿은 선 (용접선) 을 찾아 길이를 재고, 두께별 용접 속도 × 임률로 비용을 낸다.

용접선 찾기: 두 부품의 상자가 (틈 허용만큼) 겹치면, 한쪽 부품의 모서리를 몇 mm 마다 점으로 떠서 다른 부품 표면에 틈 이내로
닿는 점이 이어진 구간의 길이를 더한다 (판 끝이 다른 판 면에 닿는 필릿 용접 자리). 양쪽으로 재서 긴 쪽을 쓴다.
비용: 아크 시간 = 길이 ÷ 두께별 속도 (CO2/MAG 수동, mm/분) ÷ 아크 타임 비율 (운봉 · 자세 바꾸기 몫) × 단속률,
      + 소모품 (와이어 · 가스, 원/m) + 사상 (초/m) + 준비 (분/로트 ÷ 로트). 값은 모두 예시 — 회사 실적으로 바꿀 것."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# CO2/MAG 수동 용접 아크 속도 어림 (두께 mm → mm/분). 얇은 판은 빠르고 두꺼우면 다층 · 느림.
SPEED = [(1.0, 800.0), (1.6, 700.0), (2.3, 550.0), (3.2, 450.0), (4.5, 350.0), (6.0, 280.0), (9.0, 200.0), (12.0, 150.0),
         (16.0, 110.0)]
DEFAULTS = {"rate": 40_000.0, "arc_ratio": 0.4, "intermittent": 1.0, "consumable_per_m": 300.0, "grind_sec_per_m": 60.0,
            "setup_min": 10.0, "gap": 0.5, "tack_sec": 15.0, "both_sides": False}
NAMES = {"rate": "용접 임률 (원/h)", "arc_ratio": "아크 타임 비율 (0~1)", "intermittent": "단속률 (1 = 연속)",
         "consumable_per_m": "소모품 와이어 · 가스 (원/m)", "grind_sec_per_m": "사상 · 그라인딩 (초/m)",
         "setup_min": "준비 (분/로트)", "gap": "맞닿음 틈 허용 (mm)", "tack_sec": "가접 (초/용접선)"}
KINDS = ["필릿", "맞대기", "플러그", "겹치기"]


def speed(t: float) -> float:
    xs = [a for a, _ in SPEED]
    ys = [b for _, b in SPEED]
    return float(np.interp(max(t, 0.5), xs, ys))


@dataclass
class Seam:
    a: int                      # 부품 번호 (0부터)
    b: int
    name_a: str
    name_b: str
    length: float               # mm (자동으로 잰 값, 창에서 고칠 수 있음)
    thickness: float            # 얇은 쪽 두께
    kind: str = "필릿"
    sides: int = 1
    note: str = ""

    @property
    def label(self):
        return f"{self.name_a} ↔ {self.name_b}"


def _bbox(shape, tol=0.0):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    if box.IsVoid():
        return None
    lo, hi = box.CornerMin(), box.CornerMax()
    return (lo.X() - tol, lo.Y() - tol, lo.Z() - tol, hi.X() + tol, hi.Y() + tol, hi.Z() + tol)


def _overlap(b1, b2):
    return b1 is not None and b2 is not None and all(b1[i] <= b2[i + 3] and b2[i] <= b1[i + 3] for i in range(3))


def _edges(solid, step):
    """[(모서리, 점 배열 (n, 3), 길이)] — 모서리마다 step mm 쯤으로 고르게 (양 끝 포함)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    seen = set()
    exp = TopExp_Explorer(solid, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        exp.Next()
        h = hash(e)
        if h in seen:
            continue
        seen.add(h)
        try:
            c = BRepAdaptor_Curve(e)
            L = GCPnts_AbscissaPoint.Length_s(c)
        except Exception:  # noqa: BLE001
            continue
        if L < 1e-6:
            continue
        n = max(2, int(math.ceil(L / step)) + 1)
        a, b = c.FirstParameter(), c.LastParameter()
        pts = []
        for i in range(n):
            q = c.Value(a + (b - a) * i / (n - 1))
            pts.append((q.X(), q.Y(), q.Z()))
        out.append((e, np.array(pts), L))
    return out


def _contact_length(edges, other, gap):
    """다른 부품 표면에 gap 이내로 닿는 점이 이어진 구간 길이 합. 모서리 전체의 가장 가까운 거리로 먼저 거르고,
    가까운 모서리만 점마다 거리를 잰다 (BRepExtrema — 틈이 있어도 됨)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    total = 0.0
    for e, pts, L in edges:
        d = BRepExtrema_DistShapeShape(e, other)
        if not d.IsDone() or d.Value() > gap:
            continue
        on = []
        for q in pts:
            dv = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(float(q[0]), float(q[1]), float(q[2]))).Vertex(),
                                            other)
            on.append(bool(d.IsDone()) and dv.IsDone() and dv.Value() <= gap)
        seg = L / (len(pts) - 1)
        total += seg * sum(1 for i in range(len(pts) - 1) if on[i] and on[i + 1])
    return total


def find_seams(solids, names, thicknesses, skip=(), gap=0.5, step=4.0, min_len=5.0, progress=None):
    """부품끼리 맞닿은 선. solids: 원래 솔리드 (조립 좌표), thicknesses: 부품 번호 → 두께 (없으면 None),
    skip: 뺄 부품 번호 (체결품). progress(i, n) 가 False 면 멈춤."""
    idx = [i for i in range(len(solids)) if i not in skip]
    boxes = {i: _bbox(solids[i], gap + 0.5) for i in idx}
    pts = {}
    seams = []
    pairs = [(i, j) for k, i in enumerate(idx) for j in idx[k + 1:] if _overlap(boxes[i], boxes[j])]
    for n, (i, j) in enumerate(pairs):
        if progress is not None and progress(n, len(pairs)) is False:
            break
        for k in (i, j):
            if k not in pts:
                pts[k] = _edges(solids[k], step)
        la = _contact_length(pts[i], solids[j], gap)
        lb = _contact_length(pts[j], solids[i], gap)
        # 닿는 모서리 둘레 (판 끝 면의 네 변) 의 반 = 한쪽 용접선 길이 (T 이음의 양쪽 필릿은 [양면] 으로)
        L = max(la, lb) / 2.0
        if L < min_len:
            continue
        ta, tb = thicknesses.get(i) or 0.0, thicknesses.get(j) or 0.0
        t = min([x for x in (ta, tb) if x > 0] or [max(ta, tb)])
        kind = "맞대기" if la > 0 and lb > 0 and abs(la - lb) < 0.2 * L and la > 0.8 * L else "필릿"
        seams.append(Seam(i, j, names[i] if names else f"부품 {i + 1}", names[j] if names else f"부품 {j + 1}", L, t, kind,
                          note=f"자동 (틈 ≤ {gap:g} mm, {la:.0f} / {lb:.0f} mm)"))
    return seams


@dataclass
class WeldCost:
    seam: Seam
    arc_sec: float
    total_sec: float
    won: float


def cost(seams, rates=None, lot=None):
    """용접선마다 (아크 초, 전체 초, 원) 과 합계 dict."""
    r = dict(DEFAULTS)
    r.update(rates or {})
    lot = max(int(lot or 1), 1)
    out = []
    for s in seams:
        L_m = s.length / 1000.0 * s.sides * float(r.get("intermittent", 1.0))
        arc_min = (s.length * s.sides * float(r.get("intermittent", 1.0))) / speed(s.thickness)
        work_sec = arc_min * 60.0 / max(float(r.get("arc_ratio", 0.4)), 0.05) + float(r.get("tack_sec", 0.0)) \
            + L_m * float(r.get("grind_sec_per_m", 0.0))
        won = work_sec * float(r.get("rate", 0.0)) / 3600.0 + L_m * float(r.get("consumable_per_m", 0.0))
        out.append(WeldCost(s, arc_min * 60.0, work_sec, won))
    setup = float(r.get("setup_min", 0.0)) * float(r.get("rate", 0.0)) / 60.0 / lot if seams else 0.0
    tot = {"length_m": sum(s.length * s.sides for s in seams) / 1000.0, "arc_sec": sum(c.arc_sec for c in out),
           "sec": sum(c.total_sec for c in out), "won": sum(c.won for c in out) + setup, "setup": setup, "n": len(seams)}
    return out, tot
