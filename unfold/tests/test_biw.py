"""차체 (BIW) 프레스 부품: 고른 면 메시, 피어싱 구멍 막기, 곡선 햇 단면 사이드 멤버, 자동차 고장력강."""
import numpy as np
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import facemesh, forming
from hanil_unfold import formsim as fs
from hanil_unfold.unfolder import SheetMetalUnfolder, unfold


def _skin(s, t):
    u = SheetMetalUnfolder(s)
    return [u.info[i].face for i in sorted(u._collect_skin(u._pick_root(), t))]


@pytest.mark.parametrize("name, t", [("side_member", 1.6), ("oil_pan", 1.0), ("biw_floor", 0.8), ("drawn_cup", 1.0)])
def test_uniform_face_mesh_quality(name, t):
    """면마다 고른 메시: 바늘 삼각형 (가장 작은 각 < 5°) 없이, CAD 메시와 구멍 수 (경계 고리) 가 같게 (이음 틈 없음)."""
    s = getattr(models, name)()
    faces = _skin(s, t)
    V0, F0, _ = forming.mesh_faces(s, faces, 1000.0)
    V, F, N = facemesh.mesh(faces)
    q = forming.quality(V, F)
    assert np.mean(q < 5) < 0.005
    assert np.quantile(q, 0.05) > np.quantile(forming.quality(V0, F0), 0.05)
    assert len(forming.boundary_loops(F)) == len(forming.boundary_loops(F0))
    assert np.allclose(np.linalg.norm(N, axis=1), 1, atol=1e-6)


def test_side_member_curved_hat():
    """S 자로 휘고 올라가는 햇 단면 멤버 (DP590 t1.6): CAD 메시의 바늘 삼각형·끝단 경계 저항 탓에 가장자리가
    100 % 넘게 늘던 것 — 이제 휜 플랜지만큼 (20 % 안) 이고 판정 적합."""
    st = bc.BendSettings(material="SPFC590")
    fa = fs.analyze(unfold(models.side_member(), settings=st), st)
    assert fa.edge[0] < 0.25
    assert fa.verdict != fs.NG
    assert fa.thin_hi < 0.1


def test_pierced_holes_filled_burring_kept():
    st = bc.BendSettings(material="SGARC440")
    r = unfold(models.biw_floor(), settings=st, mode="forming")
    fi = r.forming
    assert len(fi.holes) == 4 and fi.filled is not None and fi.filled.any()
    assert len(forming.boundary_loops(fi.F)) == 1                     # 바깥 트림선만
    assert any("피어싱" in w for w in r.warnings)
    fa = fs.analyze(r, st)
    w = fi._weights()
    assert w[fi.filled].sum() == 0                                    # 막은 자리는 판정·통계에서 뺌
    cols, leg = fs.tri_colors(fa, fs.VIEWS[0])
    assert any("피어싱" in name for name, _ in leg)
    rb = unfold(models.burring(), settings=st, mode="forming")        # 세운 구멍은 그대로
    assert not rb.forming.holes and len(forming.boundary_loops(rb.forming.F)) == 2


def test_fill_keeps_blank_without_holes():
    """막은 구멍은 블랭크 (드로잉 전 평판) 에도 없다 — 블랭크 윤곽 하나."""
    r = unfold(models.biw_floor(), settings=bc.BendSettings(material="SGARC440"), mode="forming")
    assert len([e for e in r.entities if getattr(e, "layer", "") != "BEND"]) == 1


@pytest.mark.parametrize("code, ts, ys", [("SPFC440", 440, 300), ("SPFC780", 780, 500), ("SPFC1180", 1180, 900)])
def test_auto_high_strength_steels(code, ts, ys):
    m = bc.MATERIAL_BY_CODE[code]
    assert m.tensile_mpa == ts and dc.yield_strength(m) == ys
    assert fs.MIN_BEND_RT[code] > 0
    lst = [x.code for x in bc.MATERIALS]
    assert lst.index("SPFC440") < lst.index("SPFC590") < lst.index("SPFC780") < lst.index("SPFC980") < lst.index("SPFC1180")
