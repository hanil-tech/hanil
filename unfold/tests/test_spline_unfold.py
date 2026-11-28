"""3차 곡선 (베지어·B-스플라인) 이 있는 도면: 곡선 단면 판 (일반 원통) 의 정확 전개, 스플라인 윤곽,
곡면 (판 한 겹) 만 있는 판금 파일."""
import math

import numpy as np
import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import loader
from hanil_unfold.unfolder import RULED_KIND, SHEET, Polyline, SheetMetalUnfolder, unfold


def _prep(s):
    from hanil_unfold.canonical import canonicalize
    s2, _, _ = canonicalize(loader._first_solid(loader._fix(s)))
    return loader._outward(s2)


@pytest.mark.parametrize("nurbs", [False, True])
@pytest.mark.parametrize("ctrl, n_bends", [
    (((0, 0), (30, 0), (70, 40), (100, 40)), 2),        # 계단 (S 자: 오목 → 볼록)
    (((0, 0), (40, 30), (60, -30), (100, 0)), 2),       # 물결
    (((0, 0), (50, 60), (100, 60), (150, 0)), 1),       # 아치 (한쪽으로만 휨)
])
def test_cubic_section_exact_length(nurbs, ctrl, n_bends):
    """K 0.5: 펼친 길이 = 가운데 면 단면 곡선 길이 (OCC 로 잰 값) — 0.01 mm 안.
    모든 면을 B-스플라인으로 바꾼 파일 (변환 STEP) 도 같아야 한다."""
    s, L = models.spline_section(ctrl=ctrl, nurbs=nurbs)
    r = unfold(_prep(s), k_factor=0.5)
    assert r.mode == SHEET
    assert not any("근사" in w for w in r.warnings)
    assert max(r.size) == pytest.approx(L, abs=0.01)
    assert min(r.size) == pytest.approx(120.0, abs=0.01)
    curved = [b for b in r.bends if b.kind == RULED_KIND]
    assert len(curved) == n_bends
    assert sum(b.allowance for b in curved) < L


def test_ruled_bspline_cylinder_matches_exact_cylinder():
    """원통 절곡을 B-스플라인으로 바꿔 원통으로 못 알아봐도 (곡선 단면 길로) 같은 길이가 나와야 한다 —
    위치마다 쓰는 K (R/t 공식) 가 원통 절곡 BA = θ (R + K t) 와 같은 값인지."""
    st = bc.BendSettings(material="SPCC")
    s = models.profile_part([("L", 50), ("B", 90, 2.0), ("L", 30), ("B", 60, 6.0), ("L", 25)], 2.0, 60)
    exact = unfold(s, settings=st)
    nur = BRepBuilderAPI_NurbsConvert(s, True).Shape()           # canonicalize 없이: 원통도 B-스플라인
    u = SheetMetalUnfolder(nur, st)
    assert sum(f.kind == "ruled" for f in u.info) >= 2
    r = unfold(nur, settings=st)
    assert r.mode == SHEET
    assert max(r.size) == pytest.approx(max(exact.size), abs=0.02)
    curved = sorted((b for b in r.bends if b.kind == RULED_KIND), key=lambda b: b.angle_deg)
    assert [round(b.angle_deg) for b in curved] == [60, 90]
    want = sorted(exact.bends, key=lambda b: b.angle_deg)
    for a, b in zip(curved, want):
        assert a.allowance == pytest.approx(b.allowance, abs=0.02)
        assert a.k == pytest.approx(b.k, abs=0.01)


def test_spline_outline_plate():
    """윤곽이 닫힌 3차 B-스플라인인 평판: 폴리라인 현 오차 5 µm 안 → 넓이 오차 1 mm² 안."""
    s, area = models.spline_plate()
    r = unfold(s)
    polys = [e for e in r.entities if isinstance(e, Polyline)]
    assert len(polys) == 1
    P = np.array(polys[0].points)
    a = 0.5 * abs(np.sum(P[:-1, 0] * P[1:, 1] - P[1:, 0] * P[:-1, 1]) + P[-1, 0] * P[0, 1] - P[0, 0] * P[-1, 1])
    assert a == pytest.approx(area, abs=1.0)


def test_surface_only_sheet_file(tmp_path):
    """두께 없이 곡면 (판 한 겹) 만 저장한 판금 STEP: 가운데 면으로 보고 두껍게 만들어 연다."""
    from OCP.BRep import BRep_Builder
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCP.TopoDS import TopoDS_Compound
    s = models.profile_part([("L", 40), ("B", 90, 3.0), ("L", 30), ("B", -90, 3.0), ("L", 40)], 1.6, 80)
    u = SheetMetalUnfolder(s)
    skin = u._collect_skin(u._pick_root(), 1.6)
    B = BRep_Builder()
    c = TopoDS_Compound()
    B.MakeCompound(c)
    for fi in skin:
        B.Add(c, u.info[fi].face)
    w = STEPControl_Writer()
    w.Transfer(c, STEPControl_AsIs)
    p = str(tmp_path / "surface_sheet.step")
    w.Write(p)
    m = loader.load(p)
    assert m.surface_t == loader.SURFACE_T and len(m.solids) == 1
    m2 = loader.load(p, sheet_thickness=1.6)
    assert m2.surface_t == 1.6
    r = unfold(m2.solids[0])
    assert r.thickness == pytest.approx(1.6, abs=1e-3)
    assert len(r.bends) == 2
    ref = unfold(s)
    assert max(r.size) == pytest.approx(max(ref.size), abs=0.5)


def test_report_with_curved_section(tmp_path):
    from hanil_unfold import dxf_export, report
    s, _ = models.spline_section()
    st = bc.BendSettings(material="SPCC")
    r = unfold(s, settings=st)
    assert any(b.kind == RULED_KIND for b in r.bends)
    dxf_export.save(r, str(tmp_path / "x.dxf"))
    d = report.ReportData("곡선", "곡선.step", r, st, s)
    report.save_xlsx(d, str(tmp_path / "x.xlsx"))
    import openpyxl
    ws = openpyxl.load_workbook(tmp_path / "x.xlsx")["절곡표"]
    assert any("~" in str(c.value) for c in ws["E"])            # 곡선 단면은 R 범위
