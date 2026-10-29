"""강건성 해석 (Sigma 비슷하게) · 트림선 전개 · 플랜지 스프링백 보정 · 보고서."""
import numpy as np
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import formops, formrobust, formtrim
from hanil_unfold import formsim as fs
from hanil_unfold.unfolder import unfold


@pytest.fixture(scope="module")
def cup():
    st = bc.BendSettings(material="SPCC")
    r = unfold(models.drawn_cup(), settings=st, mode="forming")
    return r, st, fs.analyze(r, st)


@pytest.fixture(scope="module")
def hood():
    st = bc.BendSettings(material="SPCC")
    r = unfold(models.hood(), settings=st, mode="forming")
    fa = fs.analyze(r, st)
    return r, st, fa, formops.build(fa, r, st)


def test_robust_cup(cup):
    r, st, fa = cup
    rob = formrobust.run(r, st, n=16, seed=3)
    assert rob.risk_max.shape == (16,) and rob.p_fail.shape == (len(r.forming.F),)
    # 기준 근처에서 흩어짐 (최대 한계 비 0.62 안팎), 흩어짐은 작지만 0 이 아님
    assert 0.4 < rob.risk_max.mean() < 0.9 and rob.risk_max.std() > 1e-3
    assert rob.verdict == "안정" and rob.cpk_risk > 1.33
    # n 값이 클수록 안전 (FLC 와 경화) — 가장 크게 흔드는 값이고 계수가 음
    nm, c = rob.sens[0]
    assert "n 값" in nm and c < 0
    cols, leg = fs.tri_colors(type("A", (), {"robust": rob, "fi": r.forming})(), formrobust.ROBUST_VIEWS[0])
    assert len(cols) == len(r.forming.F) and leg


def test_robust_more_scatter_wider(cup):
    r, st, _ = cup
    a = formrobust.run(r, st, n=16, seed=3, scatter={"n": 0.02, "t": 0.01, "r": 0.02, "ts": 0.01, "eta": 0.02})
    b = formrobust.run(r, st, n=16, seed=3, scatter={"n": 0.2, "t": 0.1, "r": 0.2, "ts": 0.1, "eta": 0.2})
    assert b.risk_max.std() > 3 * a.risk_max.std()
    assert b.cpk_risk < a.cpk_risk


def test_trim_cup_wall(cup):
    """플랜지 없는 컵: 트림선 = 제품 위 끝 (벽) — 둘레가 그대로, 벽 트림 (캠·핀치)."""
    r, st, fa = cup
    o = formops.build(fa, r, st)
    tl = o.trim
    assert tl is not None and len(tl.loops3d) == 1
    from hanil_unfold.forming import boundary_loops
    lp = max(boundary_loops(r.forming.F), key=len)
    P = r.forming.V[lp]
    L_edge = float(np.linalg.norm(np.roll(P, -1, axis=0) - P, axis=1).sum())
    assert tl.length == pytest.approx(L_edge, rel=1e-6)
    assert tl.cam_frac > 0.9 and any("벽 트림" in n for n in tl.notes)


def test_trim_hood_flange(hood, tmp_path):
    """후드: 아래로 꺾은 플랜지를 드로잉 형면 접평면으로 펼친 트림선 — 플랜지 길이 (원스텝 블랭크) 만큼 바깥,
    꺾는 각에서 스프링백 보정, DXF (2D · 3D · CAM)."""
    r, st, fa, o = hood
    tl = o.trim
    assert tl is not None
    L = np.concatenate(tl.flange_len)
    assert (L > 1).mean() > 0.3 and 5 < L[L > 1].mean() < 40
    # 트림선은 뿌리 (드로잉 모양 가장자리) 바깥 — 평면 넓이가 드로잉 모양 평면보다 큼
    P2 = tl.loops2d[0]
    area = 0.5 * abs(np.sum(P2[:, 0] * np.roll(P2[:, 1], -1) - np.roll(P2[:, 0], -1) * P2[:, 1]))
    e1, e2 = tl.basis
    V2 = np.column_stack([r.forming.V @ e1, r.forming.V @ e2])
    from scipy.spatial import ConvexHull
    assert area > 0.95 * ConvexHull(V2).volume
    C = np.concatenate(tl.comp)
    assert np.isfinite(C).any() and np.nanmax(C) > 0
    assert any("스프링백 보정" in x for x in tl.summary())
    p = formtrim.save_dxf(tl, str(tmp_path / "trim.dxf"), "후드")
    import ezdxf
    doc = ezdxf.readfile(p)
    lay = {e.dxf.layer for e in doc.modelspace()}
    assert {"TRIM_2D", "TRIM_3D", "TEXT"} <= lay
    op20 = next(x for x in o.ops if x.code == "OP20")
    assert any("트림 각" in ln for ln in op20.lines)
    op30 = next(x for x in o.ops if x.code == "OP30")
    assert any("꺾는 각" in ln for ln in op30.lines)


def test_report_pages(hood, tmp_path):
    r, st, fa, o = hood
    fa.ops = o
    fa.robust = formrobust.run(r, st, n=8, seed=1)
    pdf = str(tmp_path / "fa.pdf")
    fs.save_pdf(fa, pdf, "후드")
    assert open(pdf, "rb").read(4) == b"%PDF"
    x = str(tmp_path / "fa.xlsx")
    fs.save_xlsx(fa, x, "후드")
    import openpyxl
    names = openpyxl.load_workbook(x).sheetnames
    assert "트림선 전개" in names and "강건성" in names


def test_dialog_tabs(cup):
    from hanil_unfold.formsim_dialog import FormSimDialog
    r, st, _ = cup
    dlg = FormSimDialog(r, st, "컵")
    assert dlg.robust_panel is not None
    dlg.robust_panel.n_box.setCurrentText("12")
    dlg.robust_panel.run()
    assert dlg.fa.robust is not None and dlg.fa.robust.n == 12
    dlg.ops_panel.run()
    assert dlg.ops_panel.trim_btn.isEnabled()
    dlg.close()
