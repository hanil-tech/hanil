import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from models import flat_length, funnel, oblique_bracket, profile_part  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import loader  # noqa: E402
from hanil_unfold.unfolder import Arc, Line, Polyline, unfold  # noqa: E402

HALF_PI = math.pi / 2


def solid(shape):
    return loader.list_solids(shape)[0]


def long_side(r):
    return max(r.size)


# ---------------------------------------------------------------- 문헌 값

def test_k_table_matches_literature():
    # 에어 벤딩, 중간 재질: r ≤ t / t~3t / 3t 초과
    assert bc.k_from_table(bc.MEDIUM, 1.0, 2.0) == 0.38
    assert bc.k_from_table(bc.MEDIUM, 4.0, 2.0) == 0.43
    assert bc.k_from_table(bc.MEDIUM, 8.0, 2.0) == 0.50
    assert bc.k_from_table(bc.HARD, 1.0, 2.0, bc.BOTTOM) == 0.46
    assert bc.k_from_table(bc.SOFT, 1.0, 2.0, bc.COIN) == 0.38


def test_din6935_correction_factor():
    # r/s = 1 → k = 0.65, 중립 K = 0.325.  r/s ≥ 5 → 가운데(0.5)
    assert bc.k_din6935(2.0, 2.0) == pytest.approx(0.325)
    assert bc.k_din6935(10.0, 2.0) == pytest.approx(0.5)
    assert bc.k_din6935(9.99, 2.0) == pytest.approx(0.5, abs=1e-3)
    # 90° 연신: 2(r+s) − π/2 (r + k s/2)
    assert bc.bend_deduction(HALF_PI, 2, 0.325, 2) == pytest.approx(8 - HALF_PI * 2.65)


def test_deduction_and_k_round_trip():
    for r, t, k in [(1.0, 1.6, 0.38), (3.0, 2.0, 0.43), (0.5, 1.0, 0.33)]:
        bd = bc.bend_deduction(HALF_PI, r, k, t)
        assert bc.k_from_deduction90(bd, r, t) == pytest.approx(k)


def test_air_bend_natural_radius():
    # SPCC: V 폭의 16 %. V 를 정하지 않으면 8t.
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", use_process_radius=True, punch_r=1.0)
    r, why = s.actual_radius(model_r=1.0, t=2.0)
    assert r == pytest.approx(0.16 * 16)
    assert "자연" in why
    # 상형 R 이 자연 R 보다 크면 상형 R 을 따른다.
    s.punch_r = 5.0
    assert s.actual_radius(1.0, 2.0)[0] == 5.0
    # 바텀 벤딩은 상형 R 그대로
    s.punch_r, s.process = 1.0, bc.BOTTOM
    assert s.actual_radius(1.0, 2.0)[0] == 1.0


def test_typical_spcc_deduction_is_in_shop_range():
    """SPCC 1.6t 에어 벤딩 90° 연신은 현장 경험값(약 2.8~3.0)과 비슷해야 한다."""
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", use_process_radius=True, punch_r=0.5)
    c = s.resolve(HALF_PI, 0.5, 1.6)
    assert 2.7 < c.deduction90 < 3.1


def test_deduction_table_shape():
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SUS304")
    rows = bc.deduction_table(s, [1.0, 2.0], [0.5, 1.0, 3.0])
    assert len(rows) == 2 and len(rows[0]) == 3
    # 같은 두께에서 상형 R 이 커지면 연신이 커진다 (R 이 자연 R 보다 클 때)
    assert rows[0][2].deduction90 > rows[0][0].deduction90


def test_shop_table_save_load(tmp_path):
    path = str(tmp_path / "t.json")
    t = bc.ShopTable(path=path)
    t.set(bc.ShopEntry("SPCC", 1.6, 0.5, 2.9))
    t.set(bc.ShopEntry("SPCC", 1.6, 0.5, 2.85))      # 같은 조건은 덮어쓰기
    t.save()
    again = bc.ShopTable.load(path)
    assert len(again.entries) == 1
    assert again.find("SPCC", 1.6, 0.5, 0).deduction90 == 2.85


# ---------------------------------------------------------------- 전개에 반영

STEPS = [("L", 50), ("B", 90, 2), ("L", 30)]
T = 2.0


def mold_total():
    # 바깥 치수: 각 플랜지 + (R + t)
    return 50 + 30 + 2 * (2 + T)


def test_process_radius_keeps_outside_dimensions():
    """상형 R 로 실제 R 이 바뀌면, 바깥 치수를 유지한 채 연신만 달라져야 한다."""
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", process=bc.BOTTOM,
                        use_process_radius=True, punch_r=3.0)
    r = unfold(solid(profile_part(STEPS, T, 40)), settings=s)
    k = bc.k_from_table(bc.MEDIUM, 3.0, T, bc.BOTTOM)
    assert long_side(r) == pytest.approx(mold_total() - bc.bend_deduction(HALF_PI, 3.0, k, T), abs=1e-4)
    b = r.bends[0]
    assert b.inner_radius == 3.0 and b.model_radius == pytest.approx(2.0)


def test_shop_table_value_is_used():
    table = bc.ShopTable(entries=[bc.ShopEntry("SPCC", 2.0, 2.0, 3.5)])
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", shop_table=table)
    r = unfold(solid(profile_part(STEPS, T, 40)), settings=s)
    assert long_side(r) == pytest.approx(mold_total() - 3.5, abs=1e-4)
    assert "회사" in r.bends[0].source
    assert r.bends[0].deduction90 == pytest.approx(3.5)


def test_din_method_in_unfold():
    s = bc.BendSettings(method=bc.K_DIN)
    r = unfold(solid(profile_part(STEPS, T, 40)), settings=s)
    assert long_side(r) == pytest.approx(flat_length(STEPS, T, 0.325), abs=1e-4)


@pytest.mark.parametrize("angle", [30, 60, 120, 135])
def test_non_right_angle_with_material_method(angle):
    steps = [("L", 40), ("B", angle, 2), ("L", 25)]
    s = bc.BendSettings(method=bc.K_MATERIAL, material="SUS304")
    r = unfold(solid(profile_part(steps, T, 30)), settings=s)
    k = bc.k_from_table(bc.HARD, 2.0, T)
    assert long_side(r) == pytest.approx(flat_length(steps, T, k), abs=1e-4)
    assert r.bends[0].angle_deg == pytest.approx(angle)
    # 이 각도의 연신 = 2·tan(θ/2)(R+t) − BA
    th = math.radians(angle)
    assert r.bends[0].deduction == pytest.approx(2 * math.tan(th / 2) * 4 - th * (2 + k * T))


# ---------------------------------------------------------------- 직각이 아닌 모양

def test_oblique_edges_follow_skew():
    r = unfold(solid(oblique_bracket(skew_deg=25)), k_factor=0.44)
    assert len(r.bends) == 1
    assert r.bends[0].length == pytest.approx(50, abs=1e-4)
    # 비스듬히 잘린 절곡부 모서리는 펼치면 곡선이 된다.
    assert any(isinstance(e, Polyline) for e in r.entities)
    assert max(r.size) == pytest.approx(60 + HALF_PI * (2 + 0.44 * 2) + 30, abs=1e-4)
    # 첫 플랜지의 잘린 변은 절곡선에 대해 25° 기울어져 있어야 한다.
    slanted = [e for e in r.entities if isinstance(e, Line) and e.layer == "CUT"
               and abs(e.p1[0] - e.p2[0]) > 1 and abs(e.p1[1] - e.p2[1]) > 1]
    assert len(slanted) == 2
    for e in slanted:
        slope = abs(e.p2[1] - e.p1[1]) / abs(e.p2[0] - e.p1[0])
        assert slope == pytest.approx(math.tan(math.radians(25)), abs=1e-9)


def test_funnel_unrolls_to_sector():
    rb, rt, hgt, t = 40.0, 80.0, 60.0, 2.0
    r = unfold(solid(funnel(rb, rt, hgt, t)), k_factor=0.5)
    assert r.thickness == pytest.approx(t, abs=1e-6)
    sin_a = (rt - rb) / math.hypot(rt - rb, hgt)
    cot_a = hgt / (rt - rb)
    # 바깥 원뿔 꼭짓점 거리에서 중립면(두께 가운데)까지 cot(반각) × t/2 만큼 줄어든다.
    expect = sorted([rb / sin_a - cot_a * t / 2, rt / sin_a - cot_a * t / 2])
    arcs = sorted(e.radius for e in r.entities if isinstance(e, Arc))
    assert arcs == pytest.approx(expect, abs=1e-6)
    assert r.rolled and "원뿔" in r.rolled[0]
