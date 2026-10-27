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
    k = bc.k_smooth(bc.MEDIUM, 3.0, T, bc.BOTTOM)
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
    k = bc.k_smooth(bc.HARD, 2.0, T)
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
    cos_a = hgt / math.hypot(rt - rb, hgt)
    # 끝면이 축에 수직인 평면 (z = 0, h) — 중립면 (두께 가운데) 끝도 그 평면 위: 같은 높이에서 반지름이
    # (t/2) / cos α 작고, 꼭짓점 거리 (부채꼴 반지름) 로는 (t/2) / (sin α · cos α) 만큼 줄어든다.
    expect = sorted([(rb - t / 2 / cos_a) / sin_a, (rt - t / 2 / cos_a) / sin_a])
    arcs = sorted(e.radius for e in r.entities if isinstance(e, Arc))
    assert arcs == pytest.approx(expect, abs=1e-6)
    assert r.rolled and "원뿔" in r.rolled[0]


# ---------------------------------------------------------------- 성형품 (자유곡면)

def test_dish_blank_area_matches_product():
    from models import dish
    r = unfold(solid(dish(150, 40, 1.2)))
    assert r.mode == "forming"
    fi = r.forming
    assert fi.blank_area == pytest.approx(fi.product_area, rel=0.01)
    # 구면 캡 가운데 면 넓이 2πRh 와 비교 (R=149.4, 높이는 두께만큼 조금 줄어듦)
    assert fi.product_area == pytest.approx(2 * math.pi * 149.4 * 39.84, rel=0.01)
    # 둥근 블랭크: 가로세로가 거의 같다
    w, h = r.size
    assert w == pytest.approx(h, rel=0.01)
    assert abs(fi.thinning).max() < 0.15


def test_freeform_panel_goes_forming_automatically():
    from models import bspline_panel
    r = unfold(solid(bspline_panel()))
    assert r.mode == "forming"
    assert r.forming.blank_area == pytest.approx(r.forming.product_area, rel=0.01)
    assert any("근사" in w for w in r.warnings)


def test_forming_mode_on_sheet_part_matches_exact_mid_layer():
    """판금을 성형품 방식으로 펴도, 두께 가운데(K=0.5) 정확 전개와 거의 같아야 한다."""
    r = unfold(solid(profile_part(STEPS, T, 40)), mode="forming")
    assert max(r.size) == pytest.approx(flat_length(STEPS, T, 0.5), abs=0.01)
    assert min(r.size) == pytest.approx(40, abs=0.01)


def test_sheet_part_stays_exact_in_auto_mode():
    r = unfold(solid(profile_part(STEPS, T, 40)))
    assert r.mode == "sheet" and r.forming is None


# ---------------------------------------------------------------- 자유곡면으로 저장된 판금

def test_bspline_saved_sheet_metal_is_recognized():
    """HOOPS 등으로 변환해 평면·절곡 R 까지 B-스플라인이 된 파일도 정확 전개해야 한다."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    from hanil_unfold import canonical
    from models import drill

    part = drill(profile_part([("L", 50), ("B", 90, 2), ("L", 30), ("B", -60, 3), ("L", 20)], T, 40),
                 20, 0, 15, 8)
    nurbs = solid(BRepBuilderAPI_NurbsConvert(part, True).Shape())
    assert canonical.has_freeform(nurbs)
    fixed, changed, kept = canonical.canonicalize(nurbs)
    assert changed > 0 and kept == 0
    r = unfold(fixed, k_factor=0.44)
    assert r.mode == "sheet"
    steps = [("L", 50), ("B", 90, 2), ("L", 30), ("B", -60, 3), ("L", 20)]
    assert max(r.size) == pytest.approx(flat_length(steps, T, 0.44), abs=1e-3)
    assert sorted(round(b.angle_deg, 3) for b in r.bends) == [60.0, 90.0]
    # 구멍은 원으로, 바깥선은 직선으로 다시 맞춰져야 한다 (가공용 DXF)
    assert any(isinstance(e, Arc) and e.full and e.radius == pytest.approx(4, abs=1e-3)
               for e in r.entities)
    assert not any(isinstance(e, Polyline) for e in r.entities if e.layer == "CUT")


# ---------------------------------------------------------------- 원스텝 역해석 · 성형 한계

def _dome_mesh(n=10):
    import numpy as np
    xs = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(xs, xs)
    V = np.c_[X.ravel() * 50, Y.ravel() * 50, 20 * np.exp(-(X ** 2 + Y ** 2)).ravel()]
    F = []
    for i in range(n - 1):
        for j in range(n - 1):
            a = i * n + j
            F += [[a, a + 1, a + n + 1], [a, a + n + 1, a + n]]
    return V, np.array(F)


def test_plastic_work_gradient_matches_finite_difference():
    import numpy as np
    from hanil_unfold import forming
    V, F = _dome_mesh()
    rng = np.random.default_rng(1)
    U = V[:, :2] * 1.02 + rng.random((len(V), 2)) * 0.3
    E, g = forming.plastic_work(V, F, U, 0.2, 1.6)
    for i, c in [(3, 0), (17, 1), (55, 0), (80, 1)]:
        U2 = U.copy()
        U2[i, c] += 1e-6
        E2, _ = forming.plastic_work(V, F, U2, 0.2, 1.6, grad=False)
        assert g[i, c] == pytest.approx((E2 - E) / 1e-6, rel=1e-3, abs=1e-9)


def test_one_step_lowers_plastic_work_without_fold_over():
    import numpy as np
    from hanil_unfold import forming
    V, F = _dome_mesh()
    U0 = forming.arap(V, F, forming.lscm(V, F))
    U, it = forming.one_step(V, F, U0, 0.21, 1.6)

    def det(X):
        P = X[F]
        a, b = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
        return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]

    d = det(U)
    assert np.all(d > 0) or np.all(d < 0)          # 뒤집힌 삼각형 없음
    m = (1, 1) if np.all(det(U0) > 0) else (1, -1)   # 방향을 맞춰 소성 일 비교
    E0, _ = forming.plastic_work(V, F, U0 * m, 0.21, 1.6, grad=False)
    E1, _ = forming.plastic_work(V, F, U * m, 0.21, 1.6, grad=False)
    assert E1 < 0.95 * E0 and it > 0


def test_keeler_flc0_and_limit_curve():
    import numpy as np
    from hanil_unfold import forming
    # n=0.21, t=1.0: FLC0 = 23.3 + 14.17 = 37.47 % 공칭 (Keeler 원식 23.3 + 360·t[in])
    assert forming.keeler_flc0(1.0, 0.21) == pytest.approx(math.log(1 + (23.3 + 360 / 25.4) / 100), rel=1e-9)
    f0 = forming.keeler_flc0(1.0, 0.21)
    assert forming.flc_limit(np.array([-0.1, 0.0, 0.1]), f0) == pytest.approx([f0 + 0.1, f0, f0 + 0.06])
    assert bc.MATERIAL_BY_CODE["AL5052"].flc0_for(1.0) == 0.18      # 알루미늄은 표의 대표값


def test_forming_result_uses_one_step_and_flc():
    from models import dish
    r = unfold(solid(dish(150, 40, 1.2)), settings=bc.BendSettings(material="SPCC"))
    fi = r.forming
    assert fi.method.startswith("원스텝")
    assert fi.flc0 == pytest.approx(bc.MATERIAL_BY_CODE["SPCC"].flc0_for(1.2))
    split, marginal, wrinkle, top = fi.flc_summary
    assert split == 0 and 0 < top < 0.8              # 얕은 접시는 한계까지 여유가 많다
    assert f"n={bc.MATERIAL_BY_CODE['SPCC'].n:g}" in r.settings_text


def test_drawn_cup_one_step_beats_arap():
    """딥 드로잉 컵: ARAP 은 바닥까지 30 % 넘게 얇아진다고 보고 블랭크를 작게 잡는다.
    원스텝 역해석은 바닥 두께가 거의 그대로이고 블랭크가 같은 넓이 지름에 가깝다."""
    import numpy as np
    from models import drawn_cup
    from hanil_unfold import forming
    sol = solid(drawn_cup())
    st = bc.BendSettings(material="SPCC")
    r = unfold(sol, settings=st, mode="forming")
    fi = r.forming
    assert fi.method.startswith("원스텝")
    d_equal = math.sqrt(4 * fi.product_area / math.pi)           # 같은 넓이 블랭크 (≈ 167.6)
    d_one = max(r.size)
    orig = forming.one_step
    forming.one_step = lambda *a, **k: (_ for _ in ()).throw(ValueError("off"))
    try:
        ra = unfold(sol, settings=st, mode="forming")
    finally:
        forming.one_step = orig
    assert ra.forming.method == "ARAP"
    d_arap = max(ra.size)
    assert abs(d_one - d_equal) < abs(d_arap - d_equal)
    assert abs(d_one - d_equal) < 0.03 * d_equal                 # 1.24: 중간 형상 적분 + 금형 작용
    # 바닥(가운데 반지름 30 안) 두께 변화
    U = fi.U
    c = U[fi.F].mean(1) - U.mean(0)
    bottom = np.linalg.norm(c, axis=1) < 30
    assert abs(float(np.median(fi.thinning[bottom]))) < 0.05
    ca = ra.forming.U[ra.forming.F].mean(1) - ra.forming.U.mean(0)
    assert float(np.median(ra.forming.thinning[np.linalg.norm(ca, axis=1) < 30])) > 0.2


def test_k_smooth_has_no_steps():
    """재질별 K: 표 (계단) 의 구간 대표점 값을 지나면서 R/t 1·3 에서 튀지 않음, R/t 클수록 커짐."""
    for g in (bc.SOFT, bc.MEDIUM, bc.HARD):
        for p in (bc.AIR, bc.BOTTOM, bc.COIN):
            lo, mid, hi = bc.K_TABLE[p][g]
            assert bc.k_smooth(g, 0.7, 1, p) == pytest.approx(lo) and bc.k_smooth(g, 3 ** 0.5, 1, p) == pytest.approx(mid)
            assert bc.k_smooth(g, 5, 1, p) == pytest.approx(hi) and bc.k_smooth(g, 20, 1, p) == pytest.approx(0.5)
            xs = [0.1 * 1.05 ** i for i in range(90)]
            ks = [bc.k_smooth(g, x, 1, p) for x in xs]
            assert all(b >= a - 1e-12 for a, b in zip(ks, ks[1:]))
            assert max(abs(b - a) for a, b in zip(ks, ks[1:])) < 0.01                 # 5 % 걸음마다 0.01 안
    # 예전 계단: R/t 0.99 → 1.01 에 0.38 → 0.43, 지금은 거의 같음
    assert abs(bc.k_smooth(bc.MEDIUM, 1.01, 1) - bc.k_smooth(bc.MEDIUM, 0.99, 1)) < 0.002


def test_k_from_test_bend_roundtrip():
    for ang, r, t, k in ((90, 2.0, 2.0, 0.42), (60, 1.0, 1.6, 0.36), (120, 4.0, 3.0, 0.47)):
        bd = bc.bend_deduction(math.radians(ang), r, k, t)
        L = 50 + 60 - bd
        k2, bd2, bd90 = bc.k_from_test(L, 50, 60, ang, r, t)
        assert k2 == pytest.approx(k, abs=1e-12) and bd2 == pytest.approx(bd)
        assert bd90 == pytest.approx(bc.bend_deduction(math.pi / 2, r, k, t))


def test_shop_table_interpolates_by_r_over_t():
    """같은 재질 측정 2 점 (R/t 0.5 · 2) 이 있으면 그 사이 두께·R 도 R/t 로 이어 쓰고, 밖은 식을 측정만큼 옮겨 씀."""
    shop = bc.ShopTable()
    # 측정: t1 R0.5 → K 0.30, t2 R4 → K 0.45 (바텀 벤딩이라 실제 R = 상형 R)
    for t, r, k in ((1.0, 0.5, 0.30), (2.0, 4.0, 0.45)):
        shop.set(bc.ShopEntry("SPCC", t, r, bc.bend_deduction(math.pi / 2, r, k, t)))
    st = bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", process=bc.BOTTOM, shop_table=shop)
    k, src = st.k_for(1.0, 1.0)                                   # R/t 1: log 사이 (0.5 와 2 의 가운데)
    assert "보간" in src and k == pytest.approx(0.375, abs=1e-9)
    assert st.k_for(0.5, 1.0)[0] == pytest.approx(0.30) and "회사 연신 표" in st.k_for(0.5, 1.0)[1]   # 정확히 맞는 칸
    k_out, _ = st.k_for(10.0, 2.0)                                # R/t 5: 측정 밖 → 식 + (0.45 − 식(2))
    f = lambda x: bc.k_smooth(bc.MEDIUM, x, 1, bc.BOTTOM)          # noqa: E731
    assert k_out == pytest.approx(min(max(f(5) + 0.45 - f(2), 0.15), 0.55))


def test_accuracy_advice(tmp_path):
    from models import profile_part

    from hanil_unfold import loader
    from hanil_unfold.unfolder import unfold
    steps = [("L", 50), ("B", 90, 0.5), ("L", 40)]
    sol = loader.list_solids(profile_part(steps, 2.0, 50))[0]
    r = unfold(sol, settings=bc.BendSettings(k=0.44, material="SPCC"))
    assert any("K 0.44 고정" in a for a in r.advice) and any("실제 안쪽 R" in a for a in r.advice)
    assert not r.warnings
    r2 = unfold(sol, settings=bc.BendSettings(method=bc.K_MATERIAL, material="SPCC", use_process_radius=True))
    assert not any("고정" in a or "실제 안쪽 R" in a for a in r2.advice)
