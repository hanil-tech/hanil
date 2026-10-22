import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models import dish, drill, profile_part, tray  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import loader, metrics, report  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402


def solid(shape):
    return loader.list_solids(shape)[0]


def test_metrics_area_with_hole_and_weight():
    t = 2.0
    part = drill(profile_part([("L", 50), ("B", 90, 2), ("L", 30)], t, 40), 20, 0, 15, 8)
    r = unfold(solid(part), k_factor=0.44)
    m = metrics.compute(r, 7.85)
    w = r.size[0]
    assert m.blank_area == pytest.approx(w * 40 - math.pi * 16, rel=1e-4)
    assert m.holes == 1 and m.pierce == 2
    assert m.cut_length == pytest.approx(2 * (w + 40) + math.pi * 8, rel=1e-6)
    assert m.weight_kg == pytest.approx(m.blank_area * t * 7.85e-6, rel=1e-9)


def test_metrics_tray_corner_notches():
    r = unfold(solid(tray(100, 80, 30, 1.6, 1.6, 5)), k_factor=0.44)
    m = metrics.compute(r, 7.85)
    a = math.pi / 2 * (1.6 + 0.44 * 1.6) + 30
    assert m.blank_area == pytest.approx(m.rect_area - 4 * a * (a + 5), rel=1e-6)


@pytest.fixture(scope="module")
def reports(tmp_path_factory):
    out = tmp_path_factory.mktemp("rep")
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC")
    sheet = solid(profile_part([("L", 50), ("B", 90, 2), ("L", 30), ("B", -45, 2), ("L", 20)], 2, 40))
    curved = solid(dish(150, 40, 1.2))
    items = []
    for name, sol in (("sheet", sheet), ("dish", curved)):
        r = unfold(sol, settings=s)
        d = report.ReportData(name, f"{name}.step", r, s, sol)
        report.save_pdf(d, str(out / f"{name}.pdf"))
        report.save_xlsx(d, str(out / f"{name}.xlsx"))
        items.append(d)
    report.save_parts_list(items, str(out / "parts.xlsx"))
    return out, items


def test_pdf_reports_are_written(reports):
    out, _ = reports
    for name in ("sheet", "dish"):
        data = (out / f"{name}.pdf").read_bytes()
        assert data.startswith(b"%PDF") and len(data) > 5000


def test_excel_report_contents(reports):
    import openpyxl
    out, items = reports
    wb = openpyxl.load_workbook(out / "sheet.xlsx")
    assert wb.sheetnames == ["보고서", "절곡표"]
    ws = wb["절곡표"]
    assert ws.cell(1, 1).value == "번호"
    assert [ws.cell(r, 3).value for r in (2, 3)] == pytest.approx([90, 45], abs=1e-6) or \
        sorted(ws.cell(r, 3).value for r in (2, 3)) == pytest.approx([45, 90], abs=1e-6)
    assert len(wb["보고서"]._images) == 2

    wb = openpyxl.load_workbook(out / "dish.xlsx")
    assert "두께 변화" in wb.sheetnames
    ws = wb["두께 변화"]
    shares = [ws.cell(r, 3).value for r in range(4, 10)]
    assert sum(shares) == pytest.approx(1.0, abs=1e-6)


def test_parts_list(reports):
    import openpyxl
    out, items = reports
    ws = openpyxl.load_workbook(out / "parts.xlsx")["부품 목록"]
    assert ws.cell(2, 1).value == "sheet.step"
    assert ws.cell(3, 3).value == "성형품(근사)"
    assert ws.cell(2, 9).value == pytest.approx(items[0].metrics.weight_kg, rel=1e-3)
    assert ws.cell(4, 9).value == "=SUM(I2:I3)"
