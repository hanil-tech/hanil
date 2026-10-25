"""성형이 어려운 자동차 부품 대용 모델 (후드 · 휀다 · 오일 팬) 의 전개 · 성형 해석 시험.

이 시험을 만들면서 고친 것: 큰 외판의 CAD 메시 (56 만 개 → 수 만 개), 가장자리 바늘 삼각형의 뒤집힘으로
원스텝을 못 하던 것, 가파른 벽 트림선에서 누르개 저항이 경계를 따라 당겨 블랭크가 쪼그라들던 것,
긴 모서리 나누기가 바늘을 늘리던 것 (Rivara 나누기 + 델로네 뒤집기), 깊은 상자에서 프레스 방향을 못 찾던 것."""
import time

import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import forming
from hanil_unfold import formsim as fs
from hanil_unfold import loader
from hanil_unfold.unfolder import unfold


def run(shape, mat="SGARC440"):
    st = bc.BendSettings(material=mat)
    t = time.time()
    r = unfold(loader.list_solids(shape)[0], settings=st)
    return r, fs.analyze(r, st), time.time() - t


def test_hood_outer_panel():
    from models import hood
    r, fa, sec = run(hood())
    fi = r.forming
    assert r.mode == "forming" and fi.method.startswith("원스텝")
    assert len(fi.F) < 70_000 and sec < 60
    assert fi.blank_area == pytest.approx(fi.product_area, rel=0.01)
    lo, hi = fi.thinning_range
    assert -0.06 < lo and hi < 0.06                     # 얕은 외판: 두께 변화 몇 %
    assert fa.zone_frac[4] > 0.5                        # 늘림 부족 (외판 강성·오일 캔 경고)
    assert any("늘림 부족" in m for m in fa.messages)
    assert fa.edge[0] < 0.3                             # 트림선이 가짜로 늘지 않음


def test_fender_trim_line_not_shrunk():
    from models import fender
    r, fa, _ = run(fender())
    fi = r.forming
    assert fi.method.startswith("원스텝")
    assert fi.blank_area == pytest.approx(fi.product_area, rel=0.005)
    assert fa.edge[0] < 0.1                             # 예전 60 % (누르개 저항이 경계를 따라 당김)
    assert fa.verdict == fs.OK


def test_deep_oil_pan_needs_redraw():
    from models import oil_pan
    r, fa, _ = run(oil_pan(H=160, r_corner=15, flange=0), "SPCC")
    fi = r.forming
    assert fi.method.startswith("원스텝")
    assert (forming.quality(fi.V, fi.F) < 1).mean() < 0.1
    assert fa.box and fa.box[0] == pytest.approx(15) and fa.box[2] > 6 and fa.box_ng
    assert fa.verdict in (fs.WARN, fs.NG)
    from hanil_unfold import procplan as pp
    rt = pp.route(r, bc.BendSettings(material="SPCC"), 100_000)
    assert rt.features.box_draws == 2 and rt.steps[0].op.startswith("DR1")
    # 얕은 오일 팬은 한 번
    r2, fa2, _ = run(oil_pan(flange=0), "SPCC")
    assert fa2.box and fa2.box[2] < 6 and not fa2.box_ng
