"""드로잉 보정 (drawcorr): 인장 아래 굽힘 · 드로잉 장력 · 아이어닝, 원스텝 금형 저항의 회전 불변."""
import math

import numpy as np
import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import drawcorr
from hanil_unfold import forming
from hanil_unfold import formsim as fs
from hanil_unfold.unfolder import unfold


def test_bend_under_tension_formula():
    # 강소성 평면 변형: 굽힘 한 번에 가운데 면 (T/Ty)·t/(2ρ), 굽힘-펴짐 두 번이면 두 배
    assert drawcorr.bend_thinning(1.0, 1.0, 5.0) == pytest.approx(0.1)
    assert drawcorr.bend_thinning(0.5, 1.0, 5.0, events=2) == pytest.approx(0.1)
    assert drawcorr.bend_thinning(1.7, 1.0, 5.0) == pytest.approx(0.1)      # T ≥ Ty 는 1 로
    assert drawcorr.bend_thinning(-0.2, 1.0, 5.0) == 0.0


def test_hill_stress_ratio():
    r = 1.3
    hp = (1 + r) / math.sqrt(1 + 2 * r)
    assert drawcorr.stress_ratio(np.array([0.1]), np.array([0.0]), r)[0] == pytest.approx(hp)
    assert drawcorr.stress_ratio(np.array([0.1]), np.array([0.1]), r)[0] == pytest.approx(math.sqrt((1 + r) / 2))
    assert drawcorr.stress_ratio(np.array([0.1]), np.array([-0.1 * r / (1 + r)]), r)[0] == pytest.approx(1.0)


@pytest.mark.parametrize("code", ["SPCC", "SPHC", "SGCC", "SAPH440", "SPFC590", "SPFC980", "SUS430", "AL5052",
                                  "AL6061", "C1100", "C2600"])
def test_siebel_tension_meets_wall_capacity_at_ldr(code):
    """Siebel 드로잉 장력의 최대 / 평면 변형 벽 강도 가 한계 드로잉비 (Whiteley·Hosford LDR) 에서 1 근처 —
    두 독립 모델이 같은 곳에서 터진다고 해야 보정이 믿을 만하다. (SUS304 는 0.72 — n 0.45 로 벽 강도가 커서
    Siebel 장력이 LDR 에서도 벽 강도에 못 미침: 터짐 판정이 덜 보수적인 쪽이라 빼 둠.)"""
    mat = bc.MATERIAL_BY_CODE[code]
    t = 1.0
    cap, e_cap = drawcorr.wall_capacity(mat, t)
    # 평면 변형 최대 하중: d/dε1 [(ε0 + ε1/hp)ⁿ e^(−ε1)] = 0 → ε1 = n − hp·ε0 (Swift 의 Considère 조건)
    _, e0 = dc.swift(mat)
    assert e_cap == pytest.approx(max(mat.n, 0.02) - dc._hill_ps(mat.r) * e0, abs=0.002)

    def util(beta):
        a_open = math.pi * 50.0 ** 2
        a_blank = a_open * beta ** 2
        f = np.linspace(0, 1, 200)
        a_in = a_open + f * (a_blank - a_open)
        T = drawcorr.draw_tension(mat, t, a_blank - a_in, a_open, a_blank, np.full(200, 99.0), 5.0)
        return T.max() / cap
    lim = dc.ldr(mat)
    assert 0.8 < util(lim) < 1.15
    assert util(1.5) < util(1.8) < util(lim)


@pytest.fixture(scope="module")
def cup():
    from models import drawn_cup
    st = bc.BendSettings(material="SPCC")
    r = unfold(drawn_cup(), settings=st, mode="forming")
    return r, st, fs.analyze(r, st)


def test_cup_punch_radius_thinning(cup):
    """Ø100 · 깊이 50 · 바닥 R 8 · t 1 SPCC 컵 (β 1.71): 원스텝 막 해석은 펀치 R 쪽 얇아짐을 5 % 아래로 보지만
    실제 컵은 펀치 R ~ 벽 아래에서 10 ~ 18 % 얇아진다 (연강 컵 시험: 0.7 mm 15.6 %, 2 mm 18 %).
    보정 뒤 가장 얇은 곳이 그 범위·그 자리에 와야 한다."""
    r, _, fa = cup
    fi = fa.fi
    assert fi.correction and fi.correction["applied"] and fi.correction["drawn"]
    m0, n0 = fi.membrane
    z = fi.V[fi.F].mean(1)[:, 2]
    th0 = 1 - np.exp(-(m0 + n0))
    th = fi.thinning
    low = z < 20
    assert np.quantile(th0[low], 0.99) < 0.06
    assert 0.10 < np.quantile(th[low], 0.99) < 0.20
    assert z[np.argmax(th)] < 20                         # 가장 얇은 곳은 펀치 R · 벽 아래
    assert 0.5 < fi.correction["util"] < 0.75            # β 1.71 / LDR 2.21
    # 다이 틈새 (1.1 t) 보다 두꺼운 벽은 없다 (아이어닝)
    wall = z > 15
    assert (1 - th[wall]).max() <= fi.correction["gap"] / 1.0 + 1e-6
    assert fi.correction["ironed"] > 0                   # 위 끝은 틈새보다 두꺼워지려다 훑인다
    assert fa.verdict != fs.NG
    assert any("드로잉 보정" in m for m in fa.messages)
    # 블랭크 크기는 그대로 (원스텝 결과)
    assert abs(max(r.size) - math.sqrt(4 * fi.product_area / math.pi)) < 0.03 * max(r.size)


def test_deeper_cup_near_ldr_is_riskier(cup):
    from models import drawn_cup
    st = bc.BendSettings(material="SPCC")
    fa2 = fs.analyze(unfold(drawn_cup(R=30.0, H=60.0), settings=st, mode="forming"), st)   # β 2.11
    assert fa2.fi.correction["util"] > cup[2].fi.correction["util"]
    assert fa2.risk_top > 0.8 > cup[2].risk_top


def test_tool_energy_rotation_invariant(cup):
    """원스텝 금형 저항은 블랭크를 통째로 돌려도 같아야 한다 (돌리면 저항이 사라지던 허점)."""
    fi = cup[2].fi
    V, F, U = fi.V, fi.F, fi.U
    q = forming._local_frames(V, F)
    Ap = 0.5 * np.abs(np.linalg.det(np.stack([q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]], axis=2)))
    T = forming._tool_setup(V, F, F, Ap, dict(thickness=1.0, tensile=414.0, mu=0.1, p_bh=2.5, die_r=5.0), 0.2)
    assert T is not None
    e0, _, _ = forming._tool_energy(T, U, grad=False)
    a = math.radians(90)
    Rm = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    e1, _, _ = forming._tool_energy(T, (U - U.mean(0)) @ Rm.T + (5.0, -3.0), grad=False)
    assert e0 > 0
    assert e1 == pytest.approx(e0, rel=1e-6)


def test_no_correction_on_shallow_panel():
    from hanil_unfold.loader import load
    st = bc.BendSettings(material="SPCC")
    r = unfold(load("samples/freeform_panel_t1.step").solids[0], settings=st, mode="forming")
    c = r.forming.correction
    assert c is None or not c.get("applied") or not c.get("drawn")
