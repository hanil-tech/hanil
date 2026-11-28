"""전개 검증표 (3D 와 대조) 와 원뿔대 끝면 (수평으로 자른 CAD) 중립면."""
import glob
import math
import os

import pytest

from hanil_unfold import bendcalc as bc
from hanil_unfold import loader, unfoldcheck
from hanil_unfold.unfolder import unfold

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(SAMPLES, "*.step"))))
def test_samples_pass_check(path):
    m = loader.load(path, use_cache=False)
    s = m.solids[0]
    r = unfold(s, settings=bc.BendSettings(material="SPCC"))
    rows = unfoldcheck.check(s, r)
    assert rows and unfoldcheck.verdict(rows) == unfoldcheck.OK, rows


def test_funnel_horizontal_ends():
    """끝을 축에 수직인 평면으로 자른 깔때기 (samples/funnel_t2): 중립면 끝을 그 평면 위에서 — 부채꼴 반지름이
    손 계산 (바깥 원뿔 끝 반지름에서 같은 높이로 (1 − K) t / cos α 들어간 자리) 과 같음."""
    m = loader.load(os.path.join(SAMPLES, "funnel_t2.step"), use_cache=False)
    st = bc.BendSettings(material="SPCC")
    r = unfold(m.solids[0], settings=st)
    arcs = sorted(e.radius for e in r.entities if e.layer == "CUT" and type(e).__name__ == "Arc")
    a = math.radians(33.69006752600457)
    k, t = r.k_factor, r.thickness
    s0 = 40.0 / math.sin(a) - (1 - k) * t / (math.sin(a) * math.cos(a))
    assert arcs[0] == pytest.approx(s0, abs=0.01)
    assert arcs[1] == pytest.approx(s0 + 72.11102550930057, abs=0.01)


def test_report_sheet(tmp_path):
    from hanil_unfold import report
    m = loader.load(os.path.join(SAMPLES, "bracket_t2.step"), use_cache=False)
    st = bc.BendSettings(material="SPCC")
    r = unfold(m.solids[0], settings=st)
    d = report.ReportData("브래킷", "", r, st, m.solids[0])
    assert any("전개 검증 적합" in n for n in report.notes(d))
    p = str(tmp_path / "r.xlsx")
    report.save_xlsx(d, p)
    import openpyxl
    assert "전개 검증" in openpyxl.load_workbook(p).sheetnames


def test_crossing_detects_overlap():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    bow = [(0, 0), (10, 10), (10, 0), (0, 10)]
    assert unfoldcheck.crossings([sq]) == 0
    assert unfoldcheck.crossings([bow]) == 1
    assert unfoldcheck.crossings([sq, [(5, 5), (15, 5), (15, 6), (5, 6)]]) == 2
