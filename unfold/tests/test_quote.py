import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models import nested_assembly_step  # noqa: E402

from hanil_unfold import assembly_calc, loader  # noqa: E402
from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import quote as q  # noqa: E402


@pytest.fixture(scope="module")
def assy(tmp_path_factory):
    path = tmp_path_factory.mktemp("q") / "truck.step"
    nested_assembly_step(str(path))
    m = loader.load(str(path), use_cache=False)
    st = bc.BendSettings(material="SPCC")
    return m, assembly_calc.compute_all(m, st), st


def test_korean_amount():
    assert q.korean_amount(0) == "영"
    assert q.korean_amount(1_038_400) == "일백삼만팔천사백"
    assert q.korean_amount(33_528_000) == "삼천삼백오십이만팔천"
    assert q.korean_amount(1_0000_0000) == "일억"
    assert q.korean_amount(2_0005_0010) == "이억오만십" or q.korean_amount(2_0005_0010) == "이억오만일십"


def test_rates_load_merges_saved():
    r = q.load_rates('{"material": {"SPCC": 999}, "profit_pct": 5, "supplier": {"전화": "02"}}')
    assert r["material"]["SPCC"] == 999 and r["material"]["SUS304"] == q.MATERIAL_PRICE["SUS304"]
    assert r["profit_pct"] == 5 and r["supplier"]["전화"] == "02" and r["supplier"]["주소"] == ""
    assert q.load_rates("깨진 글")["profit_pct"] == q.DEFAULT_RATES["profit_pct"]


def test_quote_low_volume_laser(assy):
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=10, annual=1000, title="TRUCK")
    names = {p.name: p for p in qt.parts}
    assert {"SIDE PANEL", "BRACKET", "FLOOR PLATE", "BOSS"} <= set(names)
    assert {s.name for s in qt.subs} >= {"NUT M8"}
    panel = names["SIDE PANEL"]
    assert "레이저" in panel.method and panel.ops[0] == "레이저 절단"
    assert panel.n_ops == 1 + sum(o.startswith("절곡") for o in panel.ops) == 5     # 트레이: 절곡 4
    assert panel.qty == 2 and panel.die_cost == 0
    # 재료비 = 소요 kg × 단가 − 스크랩
    assert panel.material == pytest.approx(panel.gross_kg * 1300 - (panel.gross_kg - panel.weight) * 300, rel=0.05)
    assert names["BOSS"].method == "기계 가공"
    # 합계 관계
    assert qt.manufacturing == pytest.approx(qt.material + qt.process + qt.sub_total)
    assert qt.unit_price >= qt.manufacturing * 1.21 - 10
    assert qt.supply == qt.unit_price * 10
    assert qt.total == qt.supply + qt.vat
    assert qt.total_ops == sum(p.n_ops for p in qt.parts)


def test_quote_high_volume_dies_and_overrides(assy):
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=1000, annual=300_000)
    panel = next(p for p in qt.parts if p.name == "SIDE PANEL")
    assert "순차" in panel.method and panel.die_cost == panel.n_ops * rates["die_station"]
    assert qt.supply == qt.unit_price * 1000 + qt.die_total
    before = qt.unit_price
    qt.amortize_die = True
    assert qt.unit_price > before and qt.supply == qt.unit_price * 1000
    panel.process_override = 0.0
    assert panel.process_cost == 0 and panel.unit == panel.material
    qt.subs[0].unit_price = 100
    assert qt.sub_total == pytest.approx(100 * qt.subs[0].qty)


def test_outputs(assy, tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    m, parts, st = assy
    qt = q.build(m, parts, st, q.load_rates(None), sets=5, annual=1000, title="TRUCK")
    qt.customer = "고객사"
    q.save_xlsx(qt, str(tmp_path / "q.xlsx"))
    q.save_pdf(qt, str(tmp_path / "q.pdf"))
    import openpyxl
    wb = openpyxl.load_workbook(tmp_path / "q.xlsx")
    assert wb.sheetnames == ["견적서", "산출 근거", "단가표"]
    ws = wb["견적서"]
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    assert any("일금" in t and q.korean_amount(qt.total) in t for t in texts)
    assert any("고객사" in t for t in texts)
    assert (tmp_path / "q.pdf").stat().st_size > 5000
