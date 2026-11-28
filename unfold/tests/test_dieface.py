"""다이 페이스 (어덴덤 · 바인더) 와 공정별 해석 (OP10 드로잉 → OP20 트림·피어싱 → OP30 플랜지 → OP40 리스트라이크)."""
import numpy as np
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import dieface, formops
from hanil_unfold import formsim as fs
from hanil_unfold.unfolder import unfold


def _fa(s, mat="SPCC"):
    st = bc.BendSettings(material=mat)
    r = unfold(s, settings=st, mode="forming")
    return r, st, fs.analyze(r, st)


@pytest.fixture(scope="module")
def cup():
    return _fa(models.drawn_cup())


def test_cup_die_face(cup):
    r, st, fa = cup
    fi = r.forming
    df = dieface.build(fi.V, fi.F, r.thickness)
    assert df is not None
    assert set(np.unique(df.region)) == {dieface.PRODUCT, dieface.ADDENDUM, dieface.BIND}
    assert (df.region[:df.n_product] == dieface.PRODUCT).all()
    # 바인더는 트림선 (컵 위 끝) 높이의 평면 — 컵은 바인더 높이 = 위 끝이라 어덴덤은 다이 R 만
    hb = df.V[np.unique(df.F[df.region == dieface.BIND])] @ df.z
    assert np.ptp(hb) < 0.05
    dieface.solve(df, r.thickness, st.mat)
    # 끌려 들어감: 둥근 컵이라 둘레가 고르게 (± 15 %)
    assert df.draw_in.mean() > 5 and df.draw_in.std() < 0.15 * df.draw_in.mean()
    rd = dieface.as_result(df, r.thickness, st.mat)
    assert max(rd.size) > max(r.size)                 # 드로잉 블랭크 = 제품 블랭크 + 바인더에 남는 판
    fad = fs.analyze(rd, st)
    prod = df.region == dieface.PRODUCT
    th = fad.fields[2][prod]
    assert 0.08 < np.quantile(th, 0.995) < 0.25       # 펀치 R 쪽 얇아짐 (연강 컵 시험 15~18 %)
    cols, leg = fs.tri_colors(fad, fs.VIEWS[0])
    assert any("어덴덤" in name for name, _ in leg)


def test_cup_ops_no_flange(cup):
    r, st, fa = cup
    o = formops.build(fa, r, st)
    codes = [x.code for x in o.ops]
    assert codes[:2] == ["OP10", "OP20"] and "OP30" not in codes     # 컵 벽은 드로잉에서 — 꺾는 플랜지 아님
    assert o.fa_die is not None and "다이 페이스" in o.ops[0].name
    assert o.ops[1].force_n > 0 and o.press_tonf > 0
    from openpyxl import Workbook
    wb = Workbook()
    formops.add_sheet(wb, o, "컵")
    assert "공정별 해석" in wb.sheetnames


def test_hood_flange_ops():
    """후드: 둘레가 아래로 꺾은 플랜지 → 떼어 낸 드로잉 모양에 다이 페이스, OP30 플랜지 · OP40 리스트라이크·캠."""
    r, st, fa = _fa(models.hood())
    o = formops.build(fa, r, st)
    codes = [x.code for x in o.ops]
    assert "OP30" in codes and "OP40" in codes
    assert o.flange.any()
    assert o.fa_die is not None
    assert any("떼어 낸 드로잉 모양" in n for n in o.notes)


def test_cut_end_member_no_die_face():
    r, st, fa = _fa(models.side_member(), "SPFC590")
    assert dieface.build(r.forming.V, r.forming.F, r.thickness) is None
    o = formops.build(fa, r, st)
    assert o.fa_die is None and "제품 원스텝" in o.ops[0].name
    assert any("다이 페이스를 자동으로 못 만듦" in n for n in o.notes)


def test_ops_panel_runs(cup):
    from hanil_unfold.formsim_dialog import FormSimDialog
    r, st, _ = cup
    dlg = FormSimDialog(r, st, "컵")
    dlg.ops_panel.run()
    assert dlg.fa.ops is not None and dlg.ops_panel.ops.ops
    dlg.close()
