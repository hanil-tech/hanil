import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import models  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import diecalc as dc  # noqa: E402
from hanil_unfold import loader  # noqa: E402
from hanil_unfold import process as pr  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402

HAT = [("L", 20), ("B", -90, 2), ("L", 30), ("B", 90, 2), ("L", 50), ("B", 90, 2), ("L", 30),
       ("B", -90, 2), ("L", 20)]


def hat_result():
    return unfold(loader.list_solids(models.profile_part(HAT, 1.6, 40))[0])


def test_hat_progressive_stations_and_section():
    r = hat_result()
    plan = pr.progressive(r, bc.BendSettings(), idle=True)
    kinds = [s.kind for s in plan.stations]
    assert kinds == [pr.PIERCE, pr.NOTCH, pr.IDLE, pr.BEND, pr.BEND, pr.CUTOFF]
    # 바깥 플랜지(작은 쪽) 둘을 먼저 함께, 그다음 안쪽 둘
    first = {n for n, _ in plan.stations[3].bends}
    second = {n for n, _ in plan.stations[4].bends}
    outer = {b.number for b in r.bends if abs(b.line[0][0] - r.bbox[0]) < 30 or abs(b.line[0][0] - r.bbox[2]) < 30}
    assert len(first) == 2 and len(second) == 2 and first | second == {b.number for b in r.bends}
    assert first == outer or first == {b.number for b in r.bends} - second
    assert not plan.notes                              # 캐리어가 플랜지에 붙지 않음
    assert 0.5 < plan.utilization < 1
    # 단면: 다 접으면 모자 모양 — 양 끝 플랜지는 바닥 판과 높이가 다르고 수평
    done = {b.number: b.angle_deg for b in r.bends}
    sec = pr.section(plan, done)
    assert sec is not None and len(sec) == 6
    assert sec[0][1] == pytest.approx(sec[1][1], abs=0.5)        # 바깥 플랜지 수평
    assert 28 < abs(sec[1][1]) < 38                            # 벽 높이(30)만큼 떨어짐 (R 무시 근사)
    # 위에서 본 모양: 다 접은 뒤 너비는 펼친 너비보다 작다
    w_flat = np.ptp(plan.outer[:, 0])
    w_done = np.ptp(pr.fold_points(plan.outer, plan.folds, done)[:, 0])
    assert w_done < w_flat - 50


def test_loads_match_diecalc():
    r = hat_result()
    st = bc.BendSettings()
    plan = pr.progressive(r, st)
    tau = dc.shear_strength(st.mat)
    notch = next(s for s in plan.stations if s.kind == pr.NOTCH)
    assert notch.force_n == pytest.approx((dc._perimeter(plan.outer) - plan.tab[1]) * 1.6 * tau)
    assert plan.total_force == pytest.approx(sum(s.force_n for s in plan.stations))


def test_drawing_process_heights_conserve_area():
    dp = dc.draw_plan(50, 100, 4, 1.0, bc.MATERIAL_BY_CODE["SPCC"], trim=0)
    for s in dp.stages:
        h = pr.cup_height(dp.D, s.d, 4)
        assert dc.cup_area(s.d, h, 4) == pytest.approx(np.pi * dp.D ** 2 / 4, rel=1e-6)
    r = hat_result()
    plan = pr.drawing(r, bc.BendSettings(), dp, 4, 100)
    assert [s.kind for s in plan.stations][:2] == [pr.BLANK, pr.DRAW]
    assert plan.stations[-1].kind in (pr.TRIM, pr.PIERCE)


def test_outputs(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    r = hat_result()
    plan = pr.progressive(r, bc.BendSettings())
    pr.save_pdf(plan, str(tmp_path / "p.pdf"), "hat")
    pr.save_dxf(plan, str(tmp_path / "p.dxf"), "hat")
    assert (tmp_path / "p.pdf").stat().st_size > 5000
    import ezdxf
    msp = ezdxf.readfile(str(tmp_path / "p.dxf")).modelspace()
    assert len(msp.query('CIRCLE[layer=="PILOT"]')) == len(plan.stations)
    assert len(msp.query('LINE[layer=="BEND"]')) == 4
    img = pr.render(plan, 800, 300)
    assert img.width() == 800


def test_orientation_follows_most_common_bend_direction():
    """0°·90° 절곡이 섞인 트레이가 45° 로 돌아가지 않는다."""
    r = unfold(loader.list_solids(models.tray())[0])
    plan = pr.progressive(r, bc.BendSettings())
    O = plan.outer
    w, h = np.ptp(O, axis=0)
    assert w * h == pytest.approx(r.size[0] * r.size[1], rel=0.02)       # 돌리지 않은 상자 크기
