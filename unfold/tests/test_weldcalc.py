"""용접 견적: 맞닿은 선 찾기 · 비용 · 창 (탭) · 엑셀."""
import os

import openpyxl
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from hanil_unfold import assembly_calc, bendcalc as bc, laserprice as lp, loader, weldcalc as wc

ST = bc.BendSettings(material="SPCC")


def _t_joint():
    base = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 300.0, 200.0, 3.0).Shape()
    wall = BRepPrimAPI_MakeBox(gp_Pnt(100, 0, 3.0), 2.0, 200.0, 80.0).Shape()
    far = BRepPrimAPI_MakeBox(gp_Pnt(200, 0, 4.0), 2.0, 200.0, 80.0).Shape()        # 1 mm 틈
    apart = BRepPrimAPI_MakeBox(gp_Pnt(0, 300, 0), 50.0, 50.0, 3.0).Shape()
    return [base, wall, far, apart]


def test_find_seams_and_cost():
    sol = _t_joint()
    seams = wc.find_seams(sol, ["BASE", "WALL", "FAR", "APART"], {0: 3.0, 1: 2.0, 2: 2.0, 3: 3.0}, gap=0.5)
    assert [(s.label, s.kind) for s in seams] == [("BASE ↔ WALL", "필릿")]
    assert seams[0].length == pytest.approx(200.0, abs=4.0) and seams[0].thickness == 2.0      # 닿는 둘레 404 의 반
    seams2 = wc.find_seams(sol, None, {0: 3.0, 1: 2.0, 2: 2.0}, gap=1.5)                       # 틈 1 mm 도 잡힘
    assert len(seams2) == 2 and seams2[1].name_a == "부품 1"
    assert not wc.find_seams(sol, None, {}, skip={1, 2}, gap=0.5)                               # 체결품처럼 뺀 것
    costs, tot = wc.cost(seams, {"rate": 36_000, "arc_ratio": 0.5, "consumable_per_m": 0, "grind_sec_per_m": 0,
                                 "tack_sec": 0, "setup_min": 0}, lot=10)
    L = seams[0].length
    assert costs[0].arc_sec == pytest.approx(L / wc.speed(2.0) * 60) and costs[0].total_sec == pytest.approx(costs[0].arc_sec / 0.5)
    assert costs[0].won == pytest.approx(costs[0].total_sec * 10) and tot["won"] == pytest.approx(costs[0].won) and tot["setup"] == 0
    seams[0].sides = 2
    costs2, _ = wc.cost(seams, {"setup_min": 0}, lot=1)
    assert costs2[0].arc_sec == pytest.approx(2 * costs[0].arc_sec)
    assert wc.speed(3.2) == 450.0 and wc.speed(0.2) == 800.0 and 150 < wc.speed(10.0) < 200


def test_dialog_weld_tab_and_xlsx(tmp_path):
    from hanil_unfold.laser_dialog import LaserPriceDialog
    sol = _t_joint()[:2]
    path = loader.save_step(sol, str(tmp_path / "tj.step"), "tj")
    m = loader.load(path, use_cache=False)
    assert len(m.solids) == 2
    parts = assembly_calc.compute_all(m, ST)
    assert all(p.ok for p in parts)
    d = LaserPriceDialog(m, parts, ST, set(), "tj")
    assert d.tabs.count() == 2 and len(d.seams) == 1 and d.wtable.rowCount() == 1
    assert d.weld_tot["won"] > 0 and "세트 견적" in d.grand.text()
    # 길이를 표에서 고치면 다시 계산
    before = d.weld_tot["won"]
    d.wtable.item(0, 3).setText("400")
    assert d.seams[0].length == 400 and d.weld_tot["won"] > before
    d.add_seam()
    assert len(d.seams) == 2 and d.wtable.rowCount() == 2
    d.both.setChecked(True)
    assert all(s.sides == 2 for s in d.seams)
    out = lp.save_xlsx(d.rows, d.tot, d.rates, str(tmp_path / "q.xlsx"), "tj", seams=d.seams, weld_costs=d.weld_costs,
                       weld_tot=d.weld_tot, weld_rates=d.wrates)
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["레이저·절곡 단가", "단가 기준", "용접"]
    wt = wb["용접"]
    assert wt.cell(4, 1).value == "부품 A" and wt.cell(5, 4).value == 400 and wt.cell(7, 1).value == "합계"
    assert "세트 견적" == wb["레이저·절곡 단가"].cell(3, 1).value
    d.close()
