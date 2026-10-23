import math
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hanil_unfold import nesting as N  # noqa: E402
from hanil_unfold.unfolder import Arc, Line, UnfoldResult  # noqa: E402


def rect(w, h, x=0.0, y=0.0):
    p = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return [Line(p[i], p[(i + 1) % 4]) for i in range(4)]


def flat(entities, t=2.0):
    return UnfoldResult(thickness=t, k_factor=0.44, entities=entities, bends=[])


def placed_boxes(r):
    """철판마다 [(x0, y0, x1, y1)] (돌리고 옮긴 절단선의 상자)."""
    out = []
    for s in r.sheets:
        boxes = []
        for pl in s.placements:
            pts = np.vstack([N._rot_poly(c, pl.angle) for c in r.parts[pl.part].cut]) + (pl.dx, pl.dy)
            boxes.append((*pts.min(0), *pts.max(0)))
        out.append(boxes)
    return out


def test_parse_size():
    assert N.parse_size("1219*2438") == (1219, 2438)
    assert N.parse_size("1219 x 2438") == (1219, 2438)
    assert N.parse_size("1,524 × 3,048") == (1524, 3048)
    assert N.parse_size("4×8  1219 × 2438") == (1219, 2438)
    assert N.parse_size("abc") is None


def test_rectangles_fit_without_overlap_and_inside_margin():
    part = N.NestPart.from_result("판", flat(rect(500, 300)), qty=14)
    assert part.area == pytest.approx(150000)
    gap, margin = 5.0, 10.0
    r = N.nest([part], 1219, 2438, gap=gap, margin=margin)
    assert r.placed_count == 14 and not r.unplaced
    # 2418 × 1199 안에 500 × 300 은 (4 × 3) 또는 (8 × 2) 로 한 장에 16 개까지
    assert len(r.sheets) == 1
    for boxes in placed_boxes(r):
        for b in boxes:
            assert b[0] >= margin - 1e-6 and b[1] >= margin - 1e-6
            assert b[2] <= 2438 - margin + 1e-6 and b[3] <= 1219 - margin + 1e-6
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, c = boxes[i], boxes[j]
                dx = max(c[0] - a[2], a[0] - c[2])
                dy = max(c[1] - a[3], a[1] - c[3])
                assert max(dx, dy) >= gap - 1e-6, "부품 간격이 모자랍니다"
    assert r.utilization == pytest.approx(14 * 150000 / (1219 * 2438))


def test_more_sheets_when_full_and_too_big_part_reported():
    small = N.NestPart.from_result("판", flat(rect(1100, 1100)), qty=3, number=1)
    huge = N.NestPart.from_result("큰 판", flat(rect(3000, 500)), qty=1, number=2)
    r = N.nest([small, huge], 1219, 2438, gap=5, margin=10)
    assert len(r.sheets) == 2            # 한 장에 1100 × 1100 두 개
    assert [len(s.placements) for s in r.sheets] == [2, 1]
    assert r.unplaced == [(1, 1, "철판보다 큽니다")]
    assert r.sheets[-1].used_length == pytest.approx(1110, abs=4)


def test_small_part_goes_into_big_hole():
    ring = flat(rect(1000, 1000) + [Arc((500, 500), 350, full=True)])
    big = N.NestPart.from_result("링", ring, qty=1, number=1)
    assert len(big.holes) == 1
    assert big.area == pytest.approx(1e6 - math.pi * 350 ** 2, rel=1e-3)
    small = N.NestPart.from_result("작은 판", flat(rect(200, 200)), qty=4, number=2)
    r = N.nest([big, small], 1020, 1020, gap=5, margin=5, rotations="none")
    assert len(r.sheets) == 1 and r.placed_count == 5
    for b in placed_boxes(r)[0][1:]:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        # 작은 판의 네 모서리가 구멍(반지름 350) 안
        for x in (b[0], b[2]):
            for y in (b[1], b[3]):
                assert math.hypot(x - 510, y - 510) < 350, (cx, cy)


def test_broken_outline_with_t_junction_is_still_nested_as_solid_area():
    # 외곽 위·아래 변이 가운데에서 갈라지고, 가운데 세로선이 T 자로 만난다 (전개 이음매)
    ents = [Line((0, 0), (100, 0)), Line((100, 0), (200, 0)), Line((200, 0), (200, 100)),
            Line((200, 100), (100, 100)), Line((100, 100), (0, 100)), Line((0, 100), (0, 0)),
            Line((100, 0), (100, 100))]
    p = N.NestPart.from_result("이음매", flat(ents), qty=30)
    assert p.area == pytest.approx(20000, rel=0.03)
    r = N.nest([p], 1219, 2438, gap=5, margin=10)
    assert r.placed_count == 30
    boxes = placed_boxes(r)[0]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, c = boxes[i], boxes[j]
            assert max(c[0] - a[2], a[0] - c[2], c[1] - a[3], a[1] - c[3]) >= 5 - 1e-6


def test_transform_entities_rotates_arcs():
    out = N.transform_entities([Arc((10, 0), 5, 0, 90), Line((0, 0), (1, 0))], 90, 100, 0)
    a, ln = out
    assert a.center == pytest.approx((100, 10))
    assert (a.start_deg, a.end_deg) == pytest.approx((90, 180))
    assert ln.p2 == pytest.approx((100, 1))


def test_by_thickness_groups_and_saves(tmp_path):
    parts = [N.NestPart.from_result("a", flat(rect(300, 200), t=1.6), qty=3),
             N.NestPart.from_result("b", flat(rect(400, 100) + [Arc((50, 50), 10, full=True)], t=2.0), qty=2)]
    rs = N.nest_by_thickness(parts, 1219, 2438, tries=3)
    assert [r.thickness for r in rs] == [1.6, 2.0]
    assert [r.placed_count for r in rs] == [3, 2]
    dxf = tmp_path / "n.dxf"
    N.save_dxf(rs, str(dxf))
    import ezdxf
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    assert len(msp.query('LWPOLYLINE[layer=="SHEET"]')) == 2
    assert len(msp.query('CIRCLE[layer=="CUT"]')) == 2
    from hanil_unfold import report
    pdf = tmp_path / "n.pdf"
    report.save_nesting_pdf(rs, str(pdf), "test.stp", 7.85)
    assert pdf.stat().st_size > 1000
