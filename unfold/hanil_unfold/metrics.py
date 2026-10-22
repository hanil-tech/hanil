"""전개도에서 넓이·절단 길이·무게 같은 수치를 뽑는다 (보고서용)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .unfolder import Arc, Line, Polyline


@dataclass
class Metrics:
    width: float
    height: float
    blank_area: float        # 외곽 넓이 − 구멍 넓이 (mm²)
    outer_area: float        # 외곽만
    rect_area: float         # 가로 × 세로 (철판에서 잘라 낼 사각형)
    holes: int
    cut_length: float        # 절단선 전체 길이 (mm)
    pierce: int              # 뚫는 횟수 (닫힌 윤곽 수)
    weight_kg: float         # 블랭크 무게
    rect_weight_kg: float    # 사각 원판 무게
    yield_ratio: float       # 수율 = 블랭크 / 사각 원판


def _points(e, step_deg=2.0):
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Polyline):
        return list(e.points)
    a0 = 0.0 if e.full else e.start_deg
    span = 360.0 if e.full else (e.end_deg - e.start_deg) % 360
    n = max(2, int(math.ceil(span / step_deg)))
    cx, cy = e.center
    return [(cx + e.radius * math.cos(math.radians(a0 + span * i / n)),
             cy + e.radius * math.sin(math.radians(a0 + span * i / n))) for i in range(n + 1)]


def _length(e):
    if isinstance(e, Line):
        return math.dist(e.p1, e.p2)
    if isinstance(e, Polyline):
        return sum(math.dist(a, b) for a, b in zip(e.points[:-1], e.points[1:]))
    span = 360.0 if e.full else (e.end_deg - e.start_deg) % 360
    return e.radius * math.radians(span)


def loops(entities, tol=1e-3):
    """절단선 조각들을 끝점으로 이어 닫힌 윤곽(점 목록)들로."""
    pieces = [_points(e) for e in entities if e.layer == "CUT"]
    closed, open_ = [], []
    for pts in pieces:
        (closed if math.dist(pts[0], pts[-1]) < tol and len(pts) > 2 else open_).append(pts)

    def key(p):
        return (round(p[0] / tol), round(p[1] / tol))

    ends = {}
    for i, pts in enumerate(open_):
        ends.setdefault(key(pts[0]), []).append(i)
        ends.setdefault(key(pts[-1]), []).append(i)
    used = [False] * len(open_)
    for i in range(len(open_)):
        if used[i]:
            continue
        used[i] = True
        chain = list(open_[i])
        while True:
            k = key(chain[-1])
            nxt = next((j for j in ends.get(k, []) if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            seg = open_[nxt]
            chain += seg[1:] if key(seg[0]) == k else list(reversed(seg))[1:]
            if key(chain[-1]) == key(chain[0]):
                break
        if len(chain) > 2 and math.dist(chain[0], chain[-1]) < tol * 10:
            closed.append(chain)
    return closed


def polygon_area(pts):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def compute(result, density_g_cm3: float) -> Metrics:
    w, h = result.size
    lps = loops(result.entities)
    areas = sorted((polygon_area(lp) for lp in lps), reverse=True)
    outer = areas[0] if areas else w * h
    blank = outer - sum(areas[1:])
    cut = sum(_length(e) for e in result.entities if e.layer == "CUT")
    vol_cm3 = blank * result.thickness / 1000.0
    rect = w * h
    return Metrics(
        width=w, height=h, blank_area=blank, outer_area=outer, rect_area=rect,
        holes=max(0, len(areas) - 1), cut_length=cut, pierce=len(areas),
        weight_kg=vol_cm3 * density_g_cm3 / 1000.0,
        rect_weight_kg=rect * result.thickness / 1000.0 * density_g_cm3 / 1000.0,
        yield_ratio=blank / rect if rect > 0 else 0.0)
