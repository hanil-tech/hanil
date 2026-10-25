"""전개 결과를 레이저·터렛 가공용 DXF 로 저장한다.

레이어
  CUT   절단 외곽선과 구멍 (흰색, 실선)
  BEND  절곡선 (노란색, 점선)
  NOTE  절곡 번호·방향·각도 글씨, 두께·면적·무게 (초록색) — 가공기로 넘길 때는 끄면 된다.
  DIM   기본 치수: 전체 크기, 절곡선까지 연속 치수, 구멍 지름·번호 (하늘색)

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
    "DIM": dict(color=4),
}


def save(result: UnfoldResult, path: str, part_name: str = "", notes: bool = True,
         dims: bool = True, density: float = 7.85, user_dims=None) -> None:
    """user_dims: 화면에서 찍은 치수 [(p1, p2)] — DIM 레이어에 정렬 치수로 넣는다."""
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

    d = None
    if dims or notes:
        from . import dims as dimsmod
        d = dimsmod.compute(result, density)
    if dims:
        _add_dimensions(msp, result, d)
    if notes:
        _add_notes(msp, result, part_name, d)
    if user_dims:
        _add_user_dims(msp, result, user_dims)

    doc.saveas(path)


def _add_user_dims(msp, result, user_dims):
    x0, y0, x1, y1 = result.bbox
    size = min(x1 - x0, y1 - y0) or 1.0
    over = {"dimtxt": max(2.0, size / 45), "dimasz": max(1.5, size / 60), "dimdec": 2,
            "dimdsep": ord("."), "dimlfac": 1.0, "dimclrd": 6, "dimclre": 6, "dimclrt": 6}
    for p1, p2 in user_dims:
        dim = msp.add_aligned_dim(p1=p1, p2=p2, distance=over["dimtxt"] * 1.5, dimstyle="EZDXF",
                                  override=over, dxfattribs={"layer": "DIM"})
        dim.render()


def bend_label(b) -> str:
    return f"B{b.number} {b.direction} {b.angle_deg:.1f}%%d R{b.radius_text} K{b.k:.3f}"


def _add_dimensions(msp, result, d) -> None:
    """DIM 레이어: CAD 에서 고칠 수 있는 진짜 치수 객체로 넣는다."""
    x0, y0, x1, y1 = result.bbox
    w, h = x1 - x0, y1 - y0
    step = max(4.0, min(w, h) / 12)
    attrs = {"layer": "DIM"}
    over = {"dimtxt": max(2.0, min(w, h) / 45), "dimasz": max(1.5, min(w, h) / 60),
            "dimdec": 2, "dimdsep": ord("."), "dimlfac": 1.0, "dimclrd": 4, "dimclre": 4, "dimclrt": 4}

    def lin(p1, p2, base, angle):
        dim = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="EZDXF",
                                 override=over, dxfattribs=attrs)
        dim.render()

    chains = {c.axis: c for c in d.chains}
    level = 1
    if "x" in chains:
        c = chains["x"]
        for a, b in zip(c.positions[:-1], c.positions[1:]):
            lin((x0 + a, y0), (x0 + b, y0), (x0, y0 - step * level), 0)
        level += 1
    lin((x0, y0), (x1, y0), (x0, y0 - step * level), 0)
    level = 1
    if "y" in chains:
        c = chains["y"]
        for a, b in zip(c.positions[:-1], c.positions[1:]):
            lin((x1, y0 + a), (x1, y0 + b), (x1 + step * level, y0), 90)
        level += 1
    lin((x1, y0), (x1, y1), (x1 + step * level, y0), 90)

    for hole in d.holes:
        cx, cy = x0 + hole.center[0], y0 + hole.center[1]
        if hole.diameter:
            dim = msp.add_diameter_dim(center=(cx, cy), radius=hole.diameter / 2, angle=45,
                                       dimstyle="EZDXF", override=over, dxfattribs=attrs)
            dim.render()
            label = hole.label
        else:
            label = f"{hole.label} {hole.size[0]:.2f}x{hole.size[1]:.2f}"
        r = (hole.diameter or max(hole.size)) / 2
        msp.add_text(label, height=over["dimtxt"], dxfattribs=attrs).set_placement(
            (cx - r, cy + r * 0.8), align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
        # 구멍 중심 좌표 (원점 = 전개도 왼쪽 아래)
        msp.add_text(f"X{hole.center[0]:.2f} Y{hole.center[1]:.2f}", height=over["dimtxt"] * 0.8,
                     dxfattribs=attrs).set_placement(
            (cx - r, cy - r * 0.8), align=ezdxf.enums.TextEntityAlignment.TOP_RIGHT)


def _add_notes(msp, result: UnfoldResult, part_name: str, d=None) -> None:
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
    ks = sorted({round(b.k, 3) for b in result.bends})
    k_text = f"K={'/'.join(f'{k:.3f}' for k in ks)}  " if ks else ""
    lines.append(f"T={result.thickness:.2f}  {k_text}"
                 f"SIZE {w:.2f} x {h:.2f}  BENDS {len(result.bends)}")
    if d is not None and d.metrics is not None:
        m = d.metrics
        lines.append(f"AREA {m.blank_area:.1f} mm2 (OUTER {m.outer_area:.1f})  "
                     f"WEIGHT {m.weight_kg:.3f} kg  CUT {m.cut_length:.1f} mm  PIERCE {m.pierce}")
    from . import BUILD_NUMBER, __version__
    from . import company
    lines.append(f"HANIL UNFOLD v{__version__}" + (f" build {BUILD_NUMBER}" if BUILD_NUMBER else "")
                 + f"  {company.MAKER}")
    # 치수선 아래로 비켜 쓴다
    below = (max(4.0, min(w, h) / 12) * 3 + height) if d is not None else 0
    x0, y0 = result.bbox[0], result.bbox[1]
    for i, line in enumerate(lines):
        msp.add_text(line, height=height, dxfattribs={"layer": "NOTE"}).set_placement(
            (x0, y0 - below - height * 2.0 * (i + 1)))
