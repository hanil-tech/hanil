"""레이저 절단 · 절곡 단가 뽑기."""
import openpyxl
import pytest

import models
from hanil_unfold import assembly_calc, bendcalc as bc, laserprice as lp, loader, metrics
from hanil_unfold.unfolder import unfold

ST = bc.BendSettings(material="SPCC")


def test_price_one_tray_time_and_table():
    """트레이 (t1.6, 절곡 4): 레이저 시간 = 절단 ÷ 속도 + 피어싱 + 로딩, 절곡 두 방식, 재료 포함 · 제외, 관리비 · 이윤."""
    r = unfold(models.tray(), settings=ST)
    m = metrics.compute(r, ST.mat.density)
    rates = lp.load(None)
    p = lp.price_one(1, "tray", 2, r, m, "SPCC", rates)
    assert p.bends == len(r.bends) == 4 and p.pierce == m.pierce and p.cut_m == pytest.approx(m.cut_length / 1000)
    from hanil_unfold import costing as cs
    sp = cs.laser_speed({"speed_1mm": 35.0}, r.thickness)
    sec = m.cut_length / 1000 / sp * 60 + m.pierce * (0.5 + 0.1 * r.thickness) + 20
    assert p.laser_sec == pytest.approx(sec)
    assert p.laser_won == pytest.approx(sec * 80_000 / 3600 + sec / 60 * 300 + 5 * 80_000 / 60 / 100)
    assert p.bend_won == pytest.approx(4 * 18 * 35_000 / 3600 + 10 * 35_000 / 60 / 100)
    assert p.material_won == pytest.approx(m.rect_weight_kg * 1300 - (m.rect_weight_kg - m.weight_kg) * 300)
    assert p.unit == pytest.approx((p.laser_won + p.bend_won + p.material_won) * 1.1 * 1.1) and p.total == pytest.approx(p.unit * 2)
    rates["bend"]["mode"] = "table"
    rates["material"]["include"] = False
    q = lp.price_one(1, "tray", 1, r, m, "SPCC", rates)
    assert q.material_won == 0 and q.bend_won == pytest.approx(4 * 500 + q.bend_m * 300 + 4 * r.thickness * 150)
    rates["material"]["include"] = True
    rates["material"]["price_kg"] = 2000
    assert lp.material_price("SPCC", rates) == 2000 and lp.material_price("SUS304", lp.load(None)) == 4500
    assert lp.load('{"laser": {"rate": 99000}, "junk": 1}')["laser"]["rate"] == 99000
    assert lp.load("bad json")["laser"]["rate"] == 80_000


def test_price_parts_and_xlsx(tmp_path):
    """조립품: 같은 부품은 묶여 한 줄 (세트당 개수), 체결품 · 제외 · 판금 아닌 것은 빠짐, 엑셀 두 시트."""
    path = models.nested_assembly_step(str(tmp_path / "n.stp"))
    m = loader.load(path, use_cache=False)
    parts = assembly_calc.compute_all(m, ST, skip=set(m.hardware))
    rows, tot = lp.price_parts(m, parts, ST, set(m.hardware), lp.load(None))
    names = {r.name: r for r in rows}
    assert "SIDE PANEL" in names and names["SIDE PANEL"].qty == 2 and "BRACKET" in names and names["BRACKET"].qty == 4
    assert "NUT M8" not in names and "BOSS" not in names
    assert tot["unit_sum"] == pytest.approx(sum(r.total for r in rows)) and tot["parts"] == sum(r.qty for r in rows)
    out = lp.save_xlsx(rows, tot, lp.load(None), str(tmp_path / "p.xlsx"), "n")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["레이저·절곡 단가", "단가 기준"]
    ws = wb["레이저·절곡 단가"]
    assert [ws.cell(4, j).value for j in range(1, 4)] == ["품번", "부품명", "세트당"]
    assert ws.cell(5 + len(rows), 1).value == "합계" and ws.cell(5 + len(rows), 14).value == round(tot["unit_sum"])


def test_dialog(tmp_path):
    from hanil_unfold.laser_dialog import LaserPriceDialog
    path = models.nested_assembly_step(str(tmp_path / "n2.stp"))
    m = loader.load(path, use_cache=False)
    parts = assembly_calc.compute_all(m, ST, skip=set(m.hardware))
    d = LaserPriceDialog(m, parts, ST, set(m.hardware), "n")
    assert d.table.rowCount() == len(d.rows) >= 3 and "합계" in d.sum.text()
    d.mode.setCurrentIndex(0)                    # 시간 × 임률 (저장된 값과 무관하게)
    d.inc.setChecked(True)
    before = d.tot["unit_sum"]
    d.mode.setCurrentIndex(1)                    # 회당 단가표
    assert d.rates["bend"]["mode"] == "table" and d.tot["unit_sum"] != before
    d.inc.setChecked(False)
    assert all(r.material_won == 0 for r in d.rows)
    d.close()
