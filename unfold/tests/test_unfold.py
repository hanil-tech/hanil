import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from models import drill, flat_length, profile_part, rotated, tube  # noqa: E402

from hanil_unfold import dxf_export, loader  # noqa: E402
from hanil_unfold.unfolder import Arc, Polyline, unfold  # noqa: E402

K = 0.44


def solid(shape):
    return loader.list_solids(shape)[0]


def long_side(r):
    return max(r.size)


def full_circles(r):
    return [e for e in r.entities if isinstance(e, Arc) and e.full]


@pytest.mark.parametrize("steps,t,width", [
    ([("L", 50), ("B", 90, 2), ("L", 30)], 2.0, 40),                         # ㄱ자
    ([("L", 40), ("B", 90, 1.5), ("L", 60), ("B", 90, 1.5), ("L", 40)], 1.6, 100),  # ㄷ자
    ([("L", 30), ("B", 90, 3), ("L", 50), ("B", -90, 3), ("L", 30)], 3.2, 80),  # Z자 (반대 방향)
    ([("L", 70), ("B", 45, 5), ("L", 20), ("B", -120, 2), ("L", 25)], 2.3, 55),  # 각도 여러 가지
    ([("L", 60), ("B", 170, 1), ("L", 15)], 1.0, 30),                        # 거의 접힘(헤밍)
])
def test_flat_length_matches_hand_calculation(steps, t, width):
    r = unfold(solid(profile_part(steps, t, width)), k_factor=K)
    assert r.thickness == pytest.approx(t, abs=1e-6)
    assert long_side(r) == pytest.approx(flat_length(steps, t, K), abs=1e-4)
    assert min(r.size) == pytest.approx(width, abs=1e-6)
    assert len(r.bends) == sum(1 for s in steps if s[0] == "B")
    assert not r.warnings


def test_bend_table():
    steps = [("L", 30), ("B", 90, 3), ("L", 50), ("B", -60, 4), ("L", 30)]
    r = unfold(solid(profile_part(steps, 2.0, 80)), k_factor=0.5)
    angles = sorted(round(b.angle_deg, 6) for b in r.bends)
    assert angles == [60.0, 90.0]
    by_angle = {round(b.angle_deg): b for b in r.bends}
    assert by_angle[90].inner_radius == pytest.approx(3)
    assert by_angle[60].inner_radius == pytest.approx(4)
    # 반대 방향으로 꺾었으니 위/아래가 서로 달라야 한다.
    assert by_angle[90].direction != by_angle[60].direction
    for b in r.bends:
        assert b.length == pytest.approx(80, abs=1e-4)
        assert b.allowance == pytest.approx(math.radians(b.angle_deg) * (b.inner_radius + 0.5 * 2.0))


def test_k_factor_changes_length():
    steps = [("L", 50), ("B", 90, 2), ("L", 30)]
    part = solid(profile_part(steps, 2.0, 40))
    for k in (0.3, 0.5):
        assert long_side(unfold(part, k_factor=k)) == pytest.approx(flat_length(steps, 2.0, k), abs=1e-4)


def test_given_thickness_is_used():
    steps = [("L", 50), ("B", 90, 2), ("L", 30)]
    r = unfold(solid(profile_part(steps, 2.0, 40)), k_factor=K, thickness=2.0)
    assert r.thickness == 2.0


def test_orientation_does_not_matter():
    steps = [("L", 40), ("B", 90, 1.5), ("L", 60), ("B", 90, 1.5), ("L", 40)]
    part = rotated(profile_part(steps, 1.6, 100))
    r = unfold(solid(part), k_factor=K)
    assert long_side(r) == pytest.approx(flat_length(steps, 1.6, K), abs=1e-4)
    assert min(r.size) == pytest.approx(100, abs=1e-4)


def test_holes_become_circles_at_right_place():
    t = 2.0
    steps = [("L", 50), ("B", 90, 2), ("L", 30)]
    part = profile_part(steps, t, 40)
    part = drill(part, 20, 0, 15, 8, axis=(0, 1, 0))          # 첫 플랜지 (기준면)
    part = drill(part, 0, 2 + t + 20, 25, 6, axis=(1, 0, 0))  # 세운 플랜지, 접선에서 20mm
    r = unfold(solid(part), k_factor=K)
    holes = sorted(full_circles(r), key=lambda a: a.radius)
    assert [round(h.radius, 6) for h in holes] == [3.0, 4.0]

    flat = flat_length(steps, t, K)
    big, small = holes[1], holes[0]
    # 기준면 구멍: 시작 끝에서 20
    xs = sorted([big.center[0], flat - big.center[0]])
    assert xs[0] == pytest.approx(20, abs=1e-4)
    # 세운 플랜지 구멍: 첫 플랜지 50 + 절곡 여유 + 20
    bend = math.radians(90) * (2 + K * t)
    expected = 50 + bend + 20
    assert expected == pytest.approx(
        small.center[0] if abs(small.center[0] - expected) < 1 else flat - small.center[0], abs=1e-4)


def test_hole_across_bend_is_drawn():
    t = 2.0
    part = profile_part([("L", 50), ("B", 90, 4), ("L", 30)], t, 40)
    part = drill(part, 52, 2, 20, 6, axis=(1, -1, 0))  # 절곡부를 비스듬히 지나는 구멍
    r = unfold(solid(part), k_factor=K)
    assert any(isinstance(e, Polyline) for e in r.entities)
    assert not r.warnings


def test_tube_unrolls_to_rectangle():
    R, t, L = 50.0, 3.0, 120.0
    r = unfold(solid(tube(R, t, L)), k_factor=0.5)
    assert r.thickness == pytest.approx(t, abs=1e-6)
    w, h = sorted(r.size)
    assert w == pytest.approx(L, abs=1e-4)
    assert h == pytest.approx(2 * math.pi * (R - t + 0.5 * t), abs=1e-3)


def test_step_round_trip_and_dxf(tmp_path):
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    steps = [("L", 40), ("B", 90, 1.5), ("L", 60), ("B", 90, 1.5), ("L", 40)]
    part = drill(profile_part(steps, 1.6, 100), 0, 30, 50, 10, axis=(1, 0, 0))
    path = str(tmp_path / "part.step")
    w = STEPControl_Writer()
    w.Transfer(part, STEPControl_AsIs)
    w.Write(path)

    model = loader.load(path)
    assert len(model.solids) == 1
    r = unfold(model.solids[0], k_factor=K)
    assert long_side(r) == pytest.approx(flat_length(steps, 1.6, K), abs=1e-3)

    out = str(tmp_path / "flat.dxf")
    dxf_export.save(r, out, part_name="part")

    import ezdxf
    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    layers = {e.dxf.layer for e in msp}
    assert {"CUT", "BEND"} <= layers
    assert len(msp.query("CIRCLE")) == 1
    assert len(msp.query('LINE[layer=="BEND"]')) == 2


@pytest.mark.parametrize("ext", [".CATPart", ".dwg", ".sldprt", ".prt"])
def test_native_cad_files_explain_how_to_convert(tmp_path, ext):
    p = tmp_path / ("a" + ext)
    p.write_bytes(b"x")
    with pytest.raises(loader.UnsupportedFormat) as err:
        loader.load(str(p))
    assert "STEP" in str(err.value)


def test_tray_with_four_flanges():
    from models import tray
    t, r_in = 1.6, 1.6
    r = unfold(solid(tray(100, 80, 30, t, r_in)), k_factor=K)
    allowance = math.pi / 2 * (r_in + K * t)
    w, h = r.size
    assert w == pytest.approx(100 + 2 * (allowance + 30), abs=1e-4)
    assert h == pytest.approx(80 + 2 * (allowance + 30), abs=1e-4)
    assert len(r.bends) == 4
    assert {b.direction for b in r.bends} == {r.bends[0].direction}
