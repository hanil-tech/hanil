"""SolidCraft (다른 CAD) 가 만든 판금 STEP 을 열어 전개 — 두께·절곡 각·R·전개 크기가 SolidCraft 의 전개 (flat pattern) 와 같다.

STEP 과 스크립트: tests/data/solidcraft (SolidCraft 0.23 solidcraft-cli 로 만듦, reference.json 에 그쪽 결과)."""
import json
import os

import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import formsim as fs
from hanil_unfold import loader
from hanil_unfold.unfolder import unfold

D = os.path.join(os.path.dirname(__file__), "data", "solidcraft")
REF = json.load(open(os.path.join(D, "reference.json"), encoding="utf-8"))["cases"]


@pytest.mark.parametrize("name", sorted(REF))
def test_solidcraft_sheet_step(name):
    ref = REF[name]
    m = loader.load(os.path.join(D, name + ".step"), use_cache=False)
    assert len(m.solids) == 1
    r = unfold(m.solids[0], k_factor=ref["k_factor"])
    assert r.mode == "sheet" and r.thickness == pytest.approx(ref["thickness"], abs=1e-6)
    assert sorted(r.size) == pytest.approx(sorted(ref["flat_size_mm"]), abs=1e-4)
    assert sorted(b.angle_deg for b in r.bends) == pytest.approx(sorted(b["angle_deg"] for b in ref["bends"]), abs=1e-6)
    assert sorted(b.inner_radius for b in r.bends) == pytest.approx(sorted(b["radius"] for b in ref["bends"]), abs=1e-6)
    assert sorted(b.allowance for b in r.bends) == pytest.approx(sorted(b["allowance"] for b in ref["bends"]), abs=1e-6)
    st = bc.BendSettings(material="SPCC", k=ref["k_factor"])
    assert dc.review(r, st, strip=False).press_tonf > 0 and fs.analyze(r, st).verdict
