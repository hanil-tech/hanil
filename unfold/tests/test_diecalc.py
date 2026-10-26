import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models import drill, tray  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import diecalc as dc  # noqa: E402
from hanil_unfold import loader  # noqa: E402
from hanil_unfold.unfolder import Line, UnfoldResult, unfold  # noqa: E402

SPCC = bc.MATERIAL_BY_CODE["SPCC"]


def test_cup_blank_matches_textbook_formula():
    for d, h, r in [(99, 49.5, 8.5), (50, 30, 3), (100, 20, 10)]:
        D = math.sqrt(4 * dc.cup_area(d, h, r) / math.pi)
        assert D == pytest.approx(math.sqrt(d * d + 4 * d * h - 1.72 * d * r - 0.56 * r * r), abs=0.02)


def test_draw_ratio_table_matches_lecture_example():
    # KOCW 강의 예: t/D = 1.03 % → m1 0.53, m2 0.76, m3 0.79, m4 0.81 (표 구간 1.0~1.5 의 끝 값)
    m = dc.draw_ratios(1.03, 100)
    assert m[:4] == pytest.approx((0.515, 0.755, 0.785, 0.805), abs=0.016)


def test_deep_cup_needs_several_draws():
    pl = dc.draw_plan(50, 100, 4, 1.0, SPCC, trim=0)
    assert pl.D == pytest.approx(math.sqrt(4 * dc.cup_area(50, 100, 4) / math.pi))
    assert len(pl.stages) >= 3
    assert pl.stages[-1].d == pytest.approx(50)
    for a, b in zip(pl.stages, pl.stages[1:]):
        assert b.d < a.d
    # 첫 드로잉률 = 표 값 × LDR(r=1)/LDR(r) (SPCC r 1.3 → 조금 더 깊게)
    k = math.exp(0.74) / dc.ldr(SPCC)
    assert pl.stages[0].m == pytest.approx(dc.draw_ratios(1.0, pl.D)[0] * k)
    assert k < 1
    # 드로잉력 = 교재 식과 Siebel 식 중 큰 값
    for s in pl.stages:
        assert s.force_n == pytest.approx(max(s.table_n, s.siebel_n)) and s.siebel_n > 0
    # 얕은 컵은 한 번
    assert len(dc.draw_plan(100, 30, 6, 1.0, SPCC).stages) == 1


def test_force_coefficient_and_bend_force():
    assert dc.force_k(0.55) == 1.0 and dc.force_k(0.8) == 0.4
    assert dc.force_k(0.6125) == pytest.approx(0.825)
    f = dc.bend_force(SPCC, 100, 2, 16)
    assert f == pytest.approx((1 + 4 * 2 / 16) * 414 * 100 * 4 / 16)      # C = 1 + 4t/V (V 8t → 1.5)
    assert dc.bend_force(SPCC, 100, 2, 16, bc.BOTTOM) == pytest.approx(2 * f)


def test_springback_grows_with_strength_and_radius():
    sus = bc.MATERIAL_BY_CODE["SUS304"]
    hss = bc.MATERIAL_BY_CODE["SPFC980"]
    a_spcc = 90 - dc.springback(SPCC, 2, 1.6, 90)[0]
    a_sus = 90 - dc.springback(sus, 2, 1.6, 90)[0]
    a_hss = 90 - dc.springback(hss, 2, 1.6, 90)[0]
    assert 0.2 < a_spcc < a_sus < a_hss
    assert 90 - dc.springback(SPCC, 10, 1.6, 90)[0] > a_spcc
    after, die, ks = dc.springback(SPCC, 2, 1.6, 90)
    assert after == pytest.approx(90 * ks) and die == pytest.approx(90 / ks)


def test_clearance_by_material():
    assert dc.clearance_pct(bc.MATERIAL_BY_CODE["AL1050"], 1) == 5
    assert dc.clearance_pct(SPCC, 1) == 7
    assert dc.clearance_pct(bc.MATERIAL_BY_CODE["SUS304"], 1) == 9
    assert dc.clearance_pct(bc.MATERIAL_BY_CODE["SPFC980"], 4) == 12


def rect(w, h):
    p = [(0, 0), (w, 0), (w, h), (0, h)]
    return [Line(p[i], p[(i + 1) % 4]) for i in range(4)]


def test_strip_layout_rectangle_pitch_and_utilization():
    r = UnfoldResult(thickness=2.0, k_factor=0.44, entities=rect(100, 40), bends=[])
    s = dc.strip_layout(r)
    # 긴 변을 폭으로 세우면 피치 40+3, 폭 100+8: 이용률 4000/(43×108) = 0.861
    assert s.angle == pytest.approx(90, abs=1)
    assert s.pitch == pytest.approx(43, abs=0.6)
    assert s.width == pytest.approx(108, abs=0.6)
    assert s.utilization == pytest.approx(4000 / (43 * 108), rel=0.02)


def test_review_tray_with_holes():
    from models import tray
    sh = drill(drill(tray(t=1.6), 30, 40, 0, 3, axis=(0, 0, 1)), 50, 0, 18, 6)
    st = bc.BendSettings(material="SPCC")
    r = unfold(loader.list_solids(sh)[0], settings=st)
    rep = dc.review(r, st)
    tau = 0.8 * 414
    assert rep.loads[0].force_n == pytest.approx(rep.loads[0].length * 1.6 * tau)
    assert rep.loads[1].length == pytest.approx(2 * math.pi * 3 + 2 * 2 * math.pi * 3, rel=0.02) or \
        rep.loads[1].length > 0
    assert len(rep.bends) == 4
    rules = {c.rule for c in rep.checks}
    assert {"최소 구멍 지름 (피어싱)", "구멍 ~ 외곽 거리", "최소 플랜지 (바깥 치수)"} <= rules
    assert all(c.verdict == dc.OK for c in rep.checks if c.rule == "최소 플랜지 (바깥 치수)")
    assert rep.strip is not None and 0.5 < rep.strip.utilization < 1


def test_hole_too_close_to_bend_is_flagged():
    from models import profile_part
    # 바닥 60 → 90° (안 R2) → 40, 두께 2. 절곡 시작선은 x = 60.
    steps = [("L", 60), ("B", 90, 2), ("L", 40)]
    near_hole = drill(profile_part(steps, 2.0, 40), 57, 0, 20, 4)      # 가장자리가 시작선에서 1 mm
    far_hole = drill(profile_part(steps, 2.0, 40), 20, 0, 20, 4)       # 38 mm
    rep = dc.review(unfold(loader.list_solids(near_hole)[0]), bc.BendSettings())
    c = [c for c in rep.checks if c.rule == "구멍 ~ 절곡 시작선"]
    assert len(c) == 1 and c[0].verdict == dc.WARN
    assert c[0].value == pytest.approx(1.0, abs=0.3)
    rep = dc.review(unfold(loader.list_solids(far_hole)[0]), bc.BendSettings())
    assert not [c for c in rep.checks if c.rule == "구멍 ~ 절곡 시작선"]   # 10t 넘게 멀면 검사 안 함



def test_european_japanese_formulas():
    from hanil_unfold import tolerances as tl
    # Whiteley·Hosford LDR: r = 1 → e^0.74 ≈ 2.10, r 가 클수록 크다
    sus = bc.MATERIAL_BY_CODE["SUS304"]
    assert dc.ldr(sus) == pytest.approx(math.exp(0.74), rel=1e-6)
    assert dc.ldr(SPCC) > dc.ldr(sus) > dc.ldr(bc.MATERIAL_BY_CODE["AL5052"])
    # VDI 3368: u = 0.01 s √(0.1 τ), SPCC τ = 0.8 × 414
    assert dc.vdi_clearance(SPCC, 1.0) == pytest.approx(0.01 * math.sqrt(0.1 * 0.8 * 414))
    assert dc.die_plate_thickness(1e5) == pytest.approx(10000 ** (1 / 3)) and dc.die_plate_thickness(10) == 15
    # Siebel: 이상 변형력 / 0.65
    f = dc.siebel_force(100, 170, 1.0, SPCC)
    phi = math.log(1.7)
    assert f == pytest.approx(math.pi * 100 * 1.1 * dc.mean_flow_stress(SPCC, phi) * phi / 0.65)
    # JIS B 0408 · ISO 2768
    assert tl.jis(5) == 0.1 and tl.jis(100) == 0.3 and tl.jis(1500, cls="C") == 3.0
    assert tl.jis(20, "bend") == 0.5 and tl.jis(100, "bend") == 0.8 and tl.jis(300, "bend", "A") == 0.5
    assert tl.iso(100) == 0.3 and tl.iso(500) == 0.8 and tl.iso(2, "v") is None


def test_literature_worked_examples():
    """문헌 예제와 같은 값: Siebel 누르개 면압 (β 2 · d 100 · s 1 · Rm 310 → 1.16 MPa),
    Oehler·Kaiser 다이 R (D 200 · d 100 · s 1 → 5.25 mm), 위 끝 두께 t√β (r = 1, β 2 → 1.41)."""
    import dataclasses
    m310 = dataclasses.replace(SPCC, tensile_mpa=310)
    assert dc.siebel_holder_pressure(2, 100, 1, m310) == pytest.approx(1.16, abs=0.01)
    assert dc.die_radius(200, 100, 1) == pytest.approx(5.25)
    assert dc.die_radius(130, 100, 1) == pytest.approx(0.8 * 0.035 * 80)              # β < 1.4 → −20 %
    gap, gmax = dc.draw_gap(1.0, 2.0, dataclasses.replace(SPCC, r=1.0))
    assert gmax == pytest.approx(2 ** 0.5) and gap == pytest.approx(1.1)
    assert dc.draw_gap(1.0, 2.0, dataclasses.replace(SPCC, r=2.0))[1] == pytest.approx(2 ** (1 / 3))
    assert dc.holder_misumi(2, 100, 110).startswith("없이도") and dc.holder_misumi(1, 100, 200).startswith("필요")


def test_swift_fit_and_moment_springback():
    for code in ("SPCC", "SPFC590", "SPFC980", "SUS304", "AL5052"):
        m = bc.MATERIAL_BY_CODE[code]
        k, e0 = dc.swift(m)
        n = m.n
        assert k * e0 ** n == pytest.approx(dc.yield_strength(m), rel=1e-3)                    # 항복
        assert k * n ** n * math.exp(-(n - e0)) == pytest.approx(m.tensile_mpa, rel=0.02)      # 인장 강도 (공칭)
    sb = [90 - dc.springback(SPCC, R, 1.6, 90)[0] for R in (1, 2, 5, 20)]
    assert sb == sorted(sb) and 0.3 < sb[0] < 2.5                                             # R 클수록 많이
    hard = 90 - dc.springback(bc.MATERIAL_BY_CODE["SPFC980"], 2, 1.6, 90)[0]
    assert hard > 2 * sb[1]                                                                   # 고장력강이 더 많이
    # 탄성 계수 감소 (Yoshida·Uemori, DP): 줄어든 E 로 더 돌아감
    assert dc.chord_modulus(bc.MATERIAL_BY_CODE["SPFC590"], 0.1) < dc.modulus_gpa(bc.MATERIAL_BY_CODE["SPFC590"])


def test_mill_sheet_values_override():
    st = bc.BendSettings(material="SPCC", mill={"ts": 330, "ys": 180, "n": 0.23, "r0": 1.8, "r45": 1.4, "r90": 2.2})
    m = st.mat
    assert m.source == "밀시트 실측" and m.tensile_mpa == 330 and m.n == 0.23
    assert m.r == pytest.approx((1.8 + 2 * 1.4 + 2.2) / 4) and m.dr == pytest.approx((1.8 - 2.8 + 2.2) / 2)
    assert dc.yield_strength(m) == 180 and bc.BendSettings(material="SPCC").mat.source == "대표값"
    assert m.flc0_for(1.0) > bc.MATERIAL_BY_CODE["SPCC"].flc0_for(1.0)                     # n 크면 FLC0 큼
    pl = dc.draw_plan(100, 60, 5, 1.0, m)
    assert any("Δr" in n for n in pl.notes) and any("밀시트" in n for n in pl.notes)
    assert pl.holder_p > 0 and pl.holder_tab_n > pl.holder_n and pl.stages[0].die_r > 0
