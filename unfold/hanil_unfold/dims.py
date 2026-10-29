"""전개도의 기본 치수를 뽑는다.

전개도 왼쪽 아래 구석이 원점 (0, 0) 이다 (unfolder 가 그렇게 맞춘다).

  · 전체 크기          가로 × 세로
  · 절곡선 위치        원점에서 각 절곡선까지 (세로 절곡선은 X, 가로 절곡선은 Y)
  · 플랜지 길이        끝 → 절곡선 → 절곡선 → 끝 사이 간격 (연속 치수)
  · 구멍               H1, H2 … 번호, 지름(원) 또는 가로×세로(장공·사각), 중심 X·Y
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import metrics as mt
from .unfolder import Arc


@dataclass
class Chain:
    """한 방향 연속 치수. positions 는 원점에서의 좌표(처음 0, 끝 전체 길이)."""
    axis: str                 # "x" (가로 방향 치수) / "y"
    positions: list
    labels: list              # 각 위치 이름: "끝", "B1" …

    @property
    def spans(self):
        return [b - a for a, b in zip(self.positions[:-1], self.positions[1:])]


@dataclass
class Hole:
    label: str                # H1 …
    center: tuple
    diameter: float | None    # 원이면 지름
    size: tuple | None        # 원이 아니면 (가로, 세로)
    count: int = 1


@dataclass
class Dimensions:
    width: float
    height: float
    thickness: float = 0.0
    metrics: object = None             # metrics.Metrics (면적·무게·절단 길이)
    chains: list = field(default_factory=list)
    holes: list = field(default_factory=list)
    oblique_bends: list = field(default_factory=list)   # 가로·세로가 아닌 절곡선 (각도 표시)

    def summary_lines(self):
        """전개도 구석 요약 상자에 넣을 줄."""
        m = self.metrics
        out = [f"두께 {self.thickness:.2f} mm",
               f"전개 크기 {self.width:.2f} × {self.height:.2f} mm"]
        if m is not None:
            out += [f"블랭크 면적 {m.blank_area:,.1f} mm² ({m.blank_area / 1e6:.4f} m²)",
                    f"사각 원판 {m.rect_area:,.1f} mm²  수율 {m.yield_ratio:.1%}",
                    f"무게 {m.weight_kg:.3f} kg  (원판 {m.rect_weight_kg:.3f} kg)",
                    f"절단 길이 {m.cut_length:,.1f} mm  피어싱 {m.pierce}곳"]
        return out

    def rows(self):
        """표로 보여 줄 (항목, 값) 목록."""
        m = self.metrics
        out = [("두께", f"{self.thickness:.3f} mm"),
               ("전체 크기 (가로 × 세로)", f"{self.width:.2f} × {self.height:.2f} mm")]
        if m is not None:
            out += [("블랭크 면적 (구멍 뺌)", f"{m.blank_area:,.1f} mm²  ({m.blank_area / 1e6:.4f} m²)"),
                    ("외곽 면적 (구멍 포함)", f"{m.outer_area:,.1f} mm²"),
                    ("사각 원판 면적", f"{m.rect_area:,.1f} mm²   수율 {m.yield_ratio:.1%}"),
                    ("블랭크 무게", f"{m.weight_kg:.3f} kg   (사각 원판 {m.rect_weight_kg:.3f} kg)"),
                    ("절단 길이", f"{m.cut_length:,.1f} mm   (피어싱 {m.pierce}곳)")]
        for c in self.chains:
            name = "가로(X)" if c.axis == "x" else "세로(Y)"
            for lab, pos in zip(c.labels[1:-1], c.positions[1:-1]):
                out.append((f"{lab} 위치 ({c.axis.upper()})", f"{pos:.2f}"))
            spans = " + ".join(f"{s:.2f}" for s in c.spans)
            out.append((f"{name} 플랜지 길이", f"{spans} = {c.positions[-1]:.2f}"))
        for b, ang in self.oblique_bends:
            out.append((f"{b} 절곡선", f"비스듬함 ({ang:.1f}°)"))
        for h in self.holes:
            what = f"Ø{h.diameter:.2f}" if h.diameter else f"{h.size[0]:.2f} × {h.size[1]:.2f}"
            out.append((f"{h.label} 구멍", f"{what}   X {h.center[0]:.2f}   Y {h.center[1]:.2f}"))
        return out


def compute(result, density=7.85, tol=0.01) -> Dimensions:
    """density: 재질 비중 (g/cm³, 무게 계산용)."""
    x0, y0, x1, y1 = result.bbox
    w, h = x1 - x0, y1 - y0
    d = Dimensions(width=w, height=h, thickness=result.thickness,
                   metrics=mt.compute(result, density))

    # 절곡선: 세로 → X 위치, 가로 → Y 위치
    xs, ys = [], []
    for b in result.bends:
        (ax, ay), (bx, by) = b.line
        ang = math.degrees(math.atan2(by - ay, bx - ax)) % 180
        if abs(ang - 90) < 0.5:
            xs.append(((ax + bx) / 2 - x0, f"B{b.number}"))
        elif ang < 0.5 or ang > 179.5:
            ys.append(((ay + by) / 2 - y0, f"B{b.number}"))
        else:
            d.oblique_bends.append((f"B{b.number}", ang))
    for axis, items, total in (("x", xs, w), ("y", ys, h)):
        if not items:
            continue
        items = sorted(_dedupe(items, tol))
        d.chains.append(Chain(axis, [0.0] + [p for p, _ in items] + [total],
                              ["끝"] + [n for _, n in items] + ["끝"]))

    # 구멍: 바깥 윤곽 말고 안쪽 닫힌 윤곽
    holes = []
    circles = [e for e in result.entities if isinstance(e, Arc) and e.full and e.layer == "CUT"]
    for c in circles:
        holes.append(((c.center[0] - x0, c.center[1] - y0), 2 * c.radius, None))
    loops = mt.loops([e for e in result.entities
                      if not (isinstance(e, Arc) and e.full)])
    if loops:
        areas = [mt.polygon_area(lp) for lp in loops]
        outer = max(range(len(loops)), key=lambda i: areas[i])
        for i, lp in enumerate(loops):
            if i == outer:
                continue
            xs_ = [p[0] for p in lp]
            ys_ = [p[1] for p in lp]
            cx, cy = (min(xs_) + max(xs_)) / 2, (min(ys_) + max(ys_)) / 2
            # 원호 몇 조각으로 된 둥근 구멍이면 지름으로
            rs = [math.hypot(p[0] - cx, p[1] - cy) for p in lp]
            r_avg = sum(rs) / len(rs)
            if r_avg > 0 and max(abs(r - r_avg) for r in rs) < max(0.005 * r_avg, 0.01):
                holes.append(((cx - x0, cy - y0), 2 * r_avg, None))
            else:
                holes.append(((cx - x0, cy - y0), None,
                              (float(max(xs_) - min(xs_)), float(max(ys_) - min(ys_)))))
    # 아래에서 위로, 왼쪽에서 오른쪽으로 번호
    holes.sort(key=lambda t: (round(t[0][1], 1), round(t[0][0], 1)))
    for i, (c, dia, size) in enumerate(holes, 1):
        d.holes.append(Hole(f"H{i}", c, dia, size))
    return d


def _dedupe(items, tol):
    out = []
    for p, n in sorted(items):
        if out and abs(out[-1][0] - p) < tol:
            continue
        out.append((p, n))
    return out
