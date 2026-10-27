"""도면 형식: DWG (변환기), 도면 선 STEP, 전개도 평판·선 STEP, 도면집의 제품도·입체도."""
import os
import stat
import sys

import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import die3d, diedraw, drawfmt, dxf2d, dxf_export, loader
from hanil_unfold.unfolder import unfold

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


@pytest.fixture(scope="module")
def bracket():
    m = loader.load(os.path.join(SAMPLES, "bracket_t2.step"), use_cache=False)
    st = bc.BendSettings(material="SPCC")
    r = unfold(m.solids[0], settings=st)
    return m.solids[0], r, st


def _count_edges(path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    rd = STEPControl_Reader()
    assert rd.ReadFile(path) == IFSelect_RetDone
    rd.TransferRoots()
    n = 0
    ex = TopExp_Explorer(rd.OneShape(), TopAbs_EDGE)
    while ex.More():
        n += 1
        ex.Next()
    return n


def test_flat_step_solid(bracket, tmp_path):
    solid, r, st = bracket
    p = drawfmt.flat_step(r, str(tmp_path / "flat.step"))
    m = loader.load(p, use_cache=False)
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(m.solids[0], g)
    from hanil_unfold.nesting import NestPart
    assert g.Mass() == pytest.approx(NestPart.from_result("p", r).area * r.thickness, rel=1e-4)


def test_flat_lines_step(bracket, tmp_path):
    _, r, _ = bracket
    d = dxf_export.save(r, str(tmp_path / "f.dxf")) or str(tmp_path / "f.dxf")
    p = drawfmt.dxf_to_step(str(tmp_path / "f.dxf"), str(tmp_path / "f.stp"))
    assert _count_edges(p) > 7


def test_dwg_needs_converter(tmp_path, monkeypatch):
    monkeypatch.setattr(drawfmt, "find_dwg_writer", lambda user_path="": None)
    (tmp_path / "a.dxf").write_text("0\nEOF\n")
    with pytest.raises(dxf2d.DwgConverterMissing):
        drawfmt.dxf_to_dwg(str(tmp_path / "a.dxf"), str(tmp_path / "a.dwg"))


@pytest.mark.skipif(sys.platform.startswith("win"), reason="가짜 변환기 셸 스크립트")
def test_dwg_with_converter(tmp_path, monkeypatch):
    """LibreDWG dxf2dwg 꼴 변환기 (여기서는 복사만 하는 가짜) 로 DXF → DWG 경로."""
    fake = tmp_path / "bin" / "dxf2dwg"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\n# dxf2dwg -y -o OUT IN\ncp "$4" "$3"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(fake.parent) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(dxf2d, "find_converter", lambda user_path="": None)
    (tmp_path / "a.dxf").write_text("0\nEOF\n")
    out = drawfmt.dxf_to_dwg(str(tmp_path / "a.dxf"), str(tmp_path / "a.dwg"))
    assert os.path.exists(out) and out.endswith(".dwg")


def test_drawing_set_product_and_iso(bracket, tmp_path):
    solid, r, st = bracket
    a = die3d.build(r, st)
    sheets = diedraw.build(a, {"product": "브래킷", "material": "SPCC t2", "solid": solid, "result": r})
    titles = [s.title for s in sheets]
    assert "제품도 · 전개도" in titles
    texts = lambda sh: [e[3] for e in sh.ents if e[0] == "text"]  # noqa: E731
    asm = sheets[titles.index("금형 조립도")]
    assert any(t.startswith("제품도 —") for t in texts(asm)) and "제품 입체도" in texts(asm)
    die = sheets[titles.index("다이 플레이트")]
    assert "입체도" in texts(die)
    prod = sheets[titles.index("제품도 · 전개도")]
    assert any("154.05" in t for t in texts(prod))           # 전개 길이 치수
    p = drawfmt.sheets_to_step(sheets, str(tmp_path / "set.step"))
    assert _count_edges(p) > 1000


def test_drawing_set_without_solid():
    st = bc.BendSettings(material="SPCC")
    s, _ = models.spline_plate(t=2.0, hole_d=12.0)
    r = unfold(s, settings=st)
    sheets = diedraw.build(die3d.build(r, st), {"product": "판", "result": r})
    prod = next(x for x in sheets if x.title == "제품도 · 전개도")
    assert not any(e[3] == "제품 입체도 (3D 모델)" for e in prod.ents if e[0] == "text")
