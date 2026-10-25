"""제품 성형 해석 (formsim): 성형성 존, 절곡 균열, 하중, 저장, 창."""
import math
import os

import numpy as np
import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import forming
from hanil_unfold import formsim as fs
from hanil_unfold import loader
from hanil_unfold.unfolder import unfold


def solid(shape):
    return loader.list_solids(shape)[0]


@pytest.fixture(scope="module")
def cup():
    from models import drawn_cup
    st = bc.BendSettings(material="SPCC")
    r = unfold(solid(drawn_cup()), settings=st, mode="forming")
    return r, st, fs.analyze(r, st)


def test_cup_zones_and_thickness(cup):
    r, st, fa = cup
    assert fa.mode == "forming"
    assert sum(fa.zone_frac) == pytest.approx(1.0, abs=1e-6)
    assert fa.zone_frac[0] < 0.001                      # 드로잉률 0.59 의 컵은 터지지 않는다
    assert fa.verdict != fs.NG
    # 딥 드로잉 컵: 벽 위쪽이 두꺼워지고 (압축), 바닥은 거의 그대로
    assert -fa.thin_lo > 0.05
    assert fa.zone_frac[5] + fa.zone_frac[6] > 0.15
    names = [n for n, *_ in fa.loads]
    assert "드로잉 (펀치) 힘" in names and "주름 누르개 힘" in names
    # 드로잉력 = 둘레 × t × σb × n(m): Ø100 컵 (가운데 면 Ø99) 둘레 ≈ 311 mm
    f = dict((n, v) for n, v, _ in fa.loads)["드로잉 (펀치) 힘"]
    assert 311 * 1.0 * 414 * 0.6 < f < 311 * 1.0 * 414 * 1.0
    assert "성형 해석" in fs.summary_html(fa)


def test_cup_mesh_has_no_wall_slivers(cup):
    """긴 모서리 나누기: 원통 벽의 벽 높이만 한 바늘 삼각형이 없어지고 변형이 벽 높이에 따라 고르게 바뀐다."""
    r, _, fa = cup
    z = fa.fi.V[fa.fi.F].mean(1) @ np.array([0, 0, 1.0])
    th = fa.fi.thinning
    band = (z > 20) & (z < 35)                          # 벽 가운데 띠: 같은 높이면 두께 변화도 비슷해야
    assert band.sum() > 200
    assert np.std(th[band]) < 0.04
    top = np.median(th[z > z.max() - 8])
    bottom = np.median(th[z < z.min() + 1])
    assert top < -0.05 < bottom                         # 위 끝은 두꺼워지고 바닥은 거의 그대로


def test_one_step_cup_blank_close_to_volume_constant(cup):
    r, _, fa = cup
    d_equal = math.sqrt(4 * fa.fi.product_area / math.pi)
    assert abs(max(r.size) - d_equal) < 0.03 * d_equal
    # 블랭크 넓이 = 제품 넓이 × 평균 (t / t0): 벽이 두꺼워지는 만큼 블랭크가 조금 크다
    assert 1.0 <= fa.fi.blank_area / fa.fi.product_area < 1.06


def test_sheet_bends_crack_check():
    from models import tray
    st = bc.BendSettings(material="SPCC")
    r = unfold(solid(tray()), settings=st)              # R 1.6, t 1.6 (R/t 1)
    fa = fs.analyze(r, st)
    assert fa.mode == "sheet" and fa.bends
    assert fa.verdict == fs.OK
    c = fa.bends[0]
    assert c.strain == pytest.approx(math.log(1 + 1 / (2 * 1.0 + 1)), rel=1e-6)
    assert c.die_angle > c.angle                       # 스프링백만큼 더 접는다
    st6 = bc.BendSettings(material="AL6061")            # 6061-T6 최소 R 2.5 t → R/t 1 은 균열
    fa6 = fs.analyze(unfold(solid(tray()), settings=st6), st6)
    assert fa6.verdict == fs.NG
    assert fa6.bends[0].r_min == pytest.approx(2.5 * 1.6)
    assert any("균열" in m for m in fa6.messages)


def test_save_xlsx_pdf_and_report_sheet(cup, tmp_path):
    from openpyxl import load_workbook

    from hanil_unfold import report
    r, st, fa = cup
    x, p = str(tmp_path / "a.xlsx"), str(tmp_path / "a.pdf")
    fs.save_xlsx(fa, x, "cup")
    fs.save_pdf(fa, p, "cup")
    assert os.path.getsize(p) > 10000
    wb = load_workbook(x)
    assert {"성형 해석", "제품 그림"} <= set(wb.sheetnames)
    d = report.ReportData("cup", "", r, st)
    y = str(tmp_path / "rep.xlsx")
    report.save_xlsx(d, y)
    assert "성형 해석" in load_workbook(y).sheetnames


def test_render_views(cup):
    _, _, fa = cup
    for v in fs.VIEWS:
        img = fs.render_product(fa, v, 400, 300)
        assert img.width() == 400
        # 흰 바탕만이 아니어야 한다
        assert img.pixelColor(200, 150).name() != "#ffffff"


def test_dialog_builds(cup):
    from hanil_unfold.formsim_dialog import FormSimDialog
    r, st, _ = cup
    dlg = FormSimDialog(r, st, "cup")
    assert dlg.fa.verdict in (fs.OK, fs.WARN, fs.NG)
    dlg.view.set_view(fs.VIEWS[1])
    dlg.close()
