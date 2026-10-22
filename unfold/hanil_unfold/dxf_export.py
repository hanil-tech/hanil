"""전개 결과를 레이저·터렛 가공용 DXF 로 저장한다.

레이어
  CUT   절단 외곽선과 구멍 (흰색, 실선)
  BEND  절곡선 (노란색, 점선)
  NOTE  절곡 번호·방향·각도 글씨 (초록색) — 가공기로 넘길 때는 끄면 된다.

단위는 mm. 글씨는 한글 글꼴이 없는 가공기에서도 깨지지 않게 영문으로 쓴다.
"""
from __future__ import annotations

import math

import ezdxf
from ezdxf import units

from .unfolder import Arc, Line, Polyline, UnfoldResult

_LAYERS = {
    "CUT": dict(color=7),
    "BEND": dict(color=2, linetype="DASHED"),
    "NOTE": dict(color=3),
}


def save(result: UnfoldResult, path: str, part_name: str = "", notes: bool = True) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    for name, attrs in _LAYERS.items():
        doc.layers.add(name, **attrs)
    msp = doc.modelspace()

    for e in result.entities:
        attribs = {"layer": e.layer}
        if isinstance(e, Line):
            msp.add_line(e.p1, e.p2, dxfattribs=attribs)
        elif isinstance(e, Arc):
            if e.full:
                msp.add_circle(e.center, e.radius, dxfattribs=attribs)
            else:
                msp.add_arc(e.center, e.radius, e.start_deg, e.end_deg, dxfattribs=attribs)
        elif isinstance(e, Polyline):
            msp.add_lwpolyline(e.points, dxfattribs=attribs)

    if notes:
        _add_notes(msp, result, part_name)

    doc.saveas(path)


def bend_label(b) -> str:
    return f"B{b.number} {b.direction} {b.angle_deg:.1f}%%d R{b.inner_radius:.2f}"


def _add_notes(msp, result: UnfoldResult, part_name: str) -> None:
    w, h = result.size
    height = max(2.0, min(w, h) / 40)

    for b in result.bends:
        (x1, y1), (x2, y2) = b.line
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        # 글씨가 거꾸로 보이지 않게
        if angle > 90 or angle <= -90:
            angle -= 180 if angle > 0 else -180
        text = msp.add_text(bend_label(b), height=height,
                            dxfattribs={"layer": "NOTE", "rotation": angle})
        text.set_placement((mx, my), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    lines = []
    if part_name:
        lines.append(part_name)
    lines.append(f"T={result.thickness:.2f}  K={result.k_factor:.3f}  "
                 f"SIZE {w:.2f} x {h:.2f}  BENDS {len(result.bends)}")
    for i, line in enumerate(lines):
        msp.add_text(line, height=height, dxfattribs={"layer": "NOTE"}).set_placement(
            (0, -height * 2.0 * (i + 1)))
