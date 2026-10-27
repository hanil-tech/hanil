"""금형 3D 조립 (die3d): 부품 · STEP (이름) · 조립도 · 파트리스트."""
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import die3d, loader
from hanil_unfold.unfolder import unfold


@pytest.fixture(scope="module")
def plate():
    st = bc.BendSettings(material="SPCC")
    s, _ = models.spline_plate(t=2.0, hole_d=12.0)
    r = unfold(s, settings=st)
    return r, st, die3d.build(r, st)


def test_parts_and_sizes(plate):
    r, st, a = plate
    names = [p.name for p in a.parts]
    for must in ("하형 다이 세트", "다이 플레이트", "스트리퍼 플레이트", "펀치 플레이트", "상형 다이 세트", "가이드 포스트",
                 "가이드 부시", "블랭킹 펀치", "피어싱 펀치 Ø12", "다이 스프링", "스트리퍼 볼트"):
        assert must in names
    assert [p.no for p in a.parts] == list(range(1, len(a.parts) + 1))
    die = next(p for p in a.parts if p.name == "다이 플레이트")
    F = a.force_n
    assert die.prims[0].p[5] >= dc.die_plate_thickness(F) and die.prims[0].p[5] % 5 == 0
    assert len(die.prims[0].cuts) == 2                     # 블랭크 외곽 + 구멍 Ø12
    assert next(p for p in a.parts if p.name == "가이드 포스트").qty == 4
    assert a.L > a.W > 0 and a.shut > 100
    assert any("절단력" in n for n in a.notes)


def test_step_names_and_reload(plate, tmp_path):
    _, _, a = plate
    p = die3d.save_step(a, str(tmp_path / "die.step"))
    m = loader.load(p, use_cache=False)
    n_solids = sum(len(x.prims) for x in a.parts)
    assert len(m.solids) == n_solids
    assert m.names[0] == "01 LOWER DIE SET" and any("PIERCE PUNCH" in n for n in m.names)


def test_drawing_and_parts_list(plate, tmp_path):
    _, _, a = plate
    img = die3d.render(a, 900, 450)
    assert not img.isNull()
    x = die3d.save_xlsx(a, str(tmp_path / "pl.xlsx"), "판")
    import openpyxl
    wb = openpyxl.load_workbook(x)
    assert wb.sheetnames[:2] == ["파트리스트", "조립도"]
    ws = wb["파트리스트"]
    assert [c.value for c in ws[3]][:7] == die3d.HEAD
    assert ws.cell(4, 2).value == "하형 다이 세트"
    pdf = die3d.save_pdf(a, str(tmp_path / "as.pdf"), "판")
    assert open(pdf, "rb").read(4) == b"%PDF"


def test_progressive_die_uses_strip():
    from hanil_unfold import process as pr
    st = bc.BendSettings(material="SPCC")
    r = unfold(models.profile_part([("L", 40), ("B", 90, 2.0), ("L", 25)], 1.6, 30), settings=st)
    plan = pr.progressive(r, st)
    a = die3d.build(r, st, plan=plan)
    assert a.kind.startswith("순차")
    die = next(p for p in a.parts if p.name == "다이 플레이트")
    assert die.prims[0].p[3] >= len(plan.stations) * plan.pitch
    assert "블랭킹 펀치" not in [p.name for p in a.parts]
