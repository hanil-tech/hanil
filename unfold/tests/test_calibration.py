"""실적 보정: 예측·실측 기록 → 보정 계수 (원점 최소 제곱), 묶음·전체, 켜고 끄기, 계산에 곱하기."""
import sqlite3

import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import calibration as cal
from hanil_unfold import diecalc as dc
from hanil_unfold import loader
from hanil_unfold.unfolder import unfold

SPCC = bc.MATERIAL_BY_CODE["SPCC"]


@pytest.fixture
def store():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    s = cal.Store(db)
    yield s
    cal.ACTIVE.clear()


def test_fit_least_squares_and_interval(store):
    for p, a in ((1.0, 1.2), (2.0, 2.4), (3.0, 3.6)):
        store.add("springback", "SPCC", "트레이", p, a, "B1")
    (key, f), (_, f_all) = store.fits("springback")
    assert key == "SPCC" and f.n == 3 and f.k == pytest.approx(1.2) and f.status == "씀"
    assert f.mean == pytest.approx(1.2) and f.sd == pytest.approx(0.0, abs=1e-12)
    store.add("springback", "SPCC", "트레이", 1.0, 0.0, "B2", "실측 대기")        # 실측 대기는 빠짐
    assert store.fits("springback")[0][1].n == 3
    store.add("cycle", "프레스 60톤", "x", 2.0, 2.6)
    store.add("cycle", "프레스 60톤", "x", 2.0, 2.2)
    assert store.fits("cycle")[0][1].k is None                                     # 2 개 — 아직 안 씀
    store.add("die_cost", "강판 순차", "x", 1e7, 5e7)
    store.add("die_cost", "강판 순차", "x", 1e7, 4e7)
    store.add("die_cost", "강판 순차", "x", 1e7, 6e7)
    assert store.fits("die_cost")[0][1].k is None and "범위" in store.fits("die_cost")[0][1].status   # ×5 = 입력 실수


def test_factor_scope_and_enable(store):
    for p, a in ((1.0, 1.3), (2.0, 2.6), (1.5, 1.95)):
        store.add("springback", "SPCC", "a", p, a)
        store.add("cycle", "프레스 60톤", "a", p, a * 0.8 / 1.3)
    cal.load(store)
    assert cal.factor("springback", "SPCC")[0] == pytest.approx(1.3)
    assert cal.factor("springback", "SPFC590") == (1.0, "")                       # 다른 재질 계수는 안 빌림
    assert cal.factor("cycle", "프레스 200톤")[0] == pytest.approx(0.8)            # 기계는 전체 계수로
    store.set_enabled("springback", False)
    cal.load(store)
    assert cal.factor("springback", "SPCC") == (1.0, "") and "공정 시간" in cal.summary()


def test_applied_to_springback_thinning_and_tonnage(store):
    from models import drawn_cup

    from hanil_unfold import formsim as fs
    base = 90 - dc.springback(SPCC, 2.0, 1.6, 90)[0]
    st = bc.BendSettings(material="SPCC")
    r = unfold(loader.list_solids(drawn_cup())[0], settings=st, mode="forming")
    fa0 = fs.analyze(r, st)
    for p, a in ((1.0, 1.5), (2.0, 3.0), (3.0, 4.5)):
        store.add("springback", "SPCC", "a", p, a)
        store.add("thinning", "SPCC", "a", p, a)
        store.add("tonnage", "드로잉", "a", p, a * 1.1 / 1.5)
    cal.load(store)
    assert 90 - dc.springback(SPCC, 2.0, 1.6, 90)[0] == pytest.approx(1.5 * base, rel=1e-6)
    fa1 = fs.analyze(r, st)
    assert fa1.thin_hi == pytest.approx(1.5 * fa0.thin_hi, rel=0.02)
    assert fa1.press_tonf == pytest.approx(1.1 * fa0.press_tonf, rel=0.02)
    assert any("실적 보정" in m for m in fa1.messages)
    rows = cal.predictions("springback", r, st)                                    # 예측은 보정 빼고
    assert rows == [] or all(p_ > 0 for _, _, p_ in rows)
    th = cal.predictions("thinning", r, st)
    assert th and th[-1][2] == pytest.approx(100 * max(fa0.thin_hi, 0), rel=0.02)


def test_cycle_and_die_cost_in_quote(store):
    from models import tray

    from hanil_unfold import costing as cs
    from hanil_unfold import procplan as pp
    from hanil_unfold.die_cost_dialog import part_item
    st = bc.BendSettings(material="SPCC")
    r = unfold(loader.list_solids(tray())[0], settings=st)
    it = part_item(r, "t", 7.85)
    rt = pp.route(r, st, 100_000)
    ops = [s.op for s in rt.steps]
    c = cs.default_costing()
    d0 = cs.die_quote(it, rt.die_type, ops, c, st)
    for p, a in ((1e6, 1.2e6), (2e6, 2.4e6), (3e6, 3.6e6)):
        store.add("die_cost", cal.die_key(d0.structure, rt.die_type), "a", p, a)
    cal.load(store)
    d1 = cs.die_quote(it, rt.die_type, ops, c, st)
    assert d1.cost == pytest.approx(1.2 * d0.cost) and "실적 보정" in d1.lines[-1][0]


def test_inspection_thickness_feeds_calibration():
    from hanil_unfold import inspection as ip
    ins = ip.Inspection("p", material="SPCC", thickness=1.0)
    c = ip.Char(1, "성형", "성형 부위 ① 두께", 0.75, kind=ip.MIN, values=[0.80, 0.82], pred_thin=0.15)
    ins.chars.append(c)
    (cond, pred, act), = ip.calibration_rows(ins)
    assert pred == pytest.approx(15) and act == pytest.approx(19)


def test_dialog_builds(store):
    from hanil_unfold.report import ensure_gui
    ensure_gui()
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from models import tray

    from hanil_unfold.calibration_dialog import CalibrationDialog
    st = bc.BendSettings(material="SPCC")
    r = unfold(loader.list_solids(tray())[0], settings=st)
    d = CalibrationDialog(store, r, st, "tray", ["프레스 60톤"])
    pg = d.pages["springback"]
    pg._from_part.__func__  # noqa: B018 — 메서드 존재
    rows = cal.predictions("springback", r, st, "tray")
    for key, cond, pred in rows:
        store.add("springback", key, "tray", pred, pred * 1.1, cond)
    pg.refresh()
    assert pg.table.rowCount() == len(rows) == len(r.bends) and pg.fits.rowCount() == 2
    d.accept()
    assert cal.factor("springback", "SPCC")[0] == pytest.approx(1.1)
