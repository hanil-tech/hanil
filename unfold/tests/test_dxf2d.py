"""2D 도면 (DXF·DWG) → 블랭크 평판: 윤곽·구멍·테두리 찾기, 두께·재질 글자, 단위, 블록, DWG 변환기."""
import math
import os
import stat
import sys

import pytest

ezdxf = pytest.importorskip("ezdxf")

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import dxf2d, loader  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402

R = 10.0
B90 = math.tan(math.radians(90) / 4)


def drawing(path, units=4, scale=1.0):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = units
    msp = doc.modelspace()
    for name in ("DIM", "BEND", "CENTER"):
        doc.layers.add(name)
    k = scale
    msp.add_lwpolyline([(-50 * k, -50 * k), (450 * k, -50 * k), (450 * k, 300 * k), (-50 * k, 300 * k)], close=True)
    r = R * k
    pts = [(r, 0, 0), (200 * k - r, 0, B90), (200 * k, r, 0), (200 * k, 100 * k - r, B90), (200 * k - r, 100 * k, 0),
           (r, 100 * k, B90), (0, 100 * k - r, 0), (0, r, B90)]
    msp.add_lwpolyline(pts, format="xyb", close=True)
    msp.add_circle((30 * k, 50 * k), 5 * k)
    msp.add_circle((170 * k, 50 * k), 5 * k)
    # 장공 (선 + 원호)
    msp.add_line((80 * k, 40 * k), (120 * k, 40 * k))
    msp.add_arc((120 * k, 50 * k), 10 * k, -90, 90)
    msp.add_line((120 * k, 60 * k), (80 * k, 60 * k))
    msp.add_arc((80 * k, 50 * k), 10 * k, 90, 270)
    msp.add_line((100 * k, 0), (100 * k, 100 * k), dxfattribs={"layer": "BEND"})
    msp.add_circle((30 * k, 50 * k), 8 * k, dxfattribs={"layer": "CENTER"})                 # 중심선 층 — 뺌
    # 블록으로 넣은 삼각형 부품
    blk = doc.blocks.new("TRI")
    blk.add_line((0, 0), (150 * k, 0))
    blk.add_line((150 * k, 0), (0, 150 * k))
    blk.add_line((0, 150 * k), (0, 0))
    msp.add_blockref("TRI", (250 * k, 0))
    msp.add_text("MAT: SPCC  t1.6", dxfattribs={"height": 5}).set_placement((0, 200 * k))
    msp.add_linear_dim(base=(0, -20 * k), p1=(0, 0), p2=(200 * k, 0), dxfattribs={"layer": "DIM"}).render()
    doc.saveas(path)
    return path


AREA1 = 200 * 100 - (4 - math.pi) * R * R - 2 * math.pi * 25 - (40 * 20 + math.pi * 100)
CUT1 = 2 * (180 + 80) + 2 * math.pi * R + 2 * 2 * math.pi * 5 + 2 * 40 + 2 * math.pi * 10


def test_parts_holes_frame_and_text(tmp_path):
    fd = dxf2d.read(drawing(str(tmp_path / "a.dxf")))
    real = [p for p in fd.parts if not p.frame]
    assert len(real) == 2 and any(p.frame for p in fd.parts)                # 테두리는 따로 (기본 뺌)
    p1 = real[0]
    assert len(p1.holes) == 3 and p1.size == pytest.approx((200, 100))
    assert p1.area == pytest.approx(AREA1, rel=1e-9)                        # 해석값과 같음 (원호 활꼴까지)
    assert p1.cut_length == pytest.approx(CUT1, rel=1e-9)
    assert real[1].area == pytest.approx(150 * 150 / 2)                     # 블록 안 삼각형
    assert fd.thickness == 1.6 and fd.material == "SPCC" and len(fd.bend_lines) == 1 and fd.open_ends == 0


def test_inch_units(tmp_path):
    fd = dxf2d.read(drawing(str(tmp_path / "in.dxf"), units=1, scale=1 / 25.4))
    p1 = [p for p in fd.parts if not p.frame][0]
    assert p1.area == pytest.approx(AREA1, rel=1e-6) and fd.scale == 25.4


def test_text_parse_variants():
    assert dxf2d.parse_texts(["SUS304 2.0T"]) == (2.0, "SUS304")
    assert dxf2d.parse_texts(["재질 SS400 두께 3.2"]) == (3.2, "SS275")
    assert dxf2d.parse_texts(["T=1.2 STS430"]) == (1.2, "SUS430")
    assert dxf2d.parse_texts(["수량 4 EA"]) == (None, None)


def test_open_contour_is_reported(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))                                        # 한 변이 빠짐
    p = str(tmp_path / "open.dxf")
    doc.saveas(p)
    fd = dxf2d.read(p)
    assert not fd.parts and fd.open_ends and any("닫힌" in w for w in fd.warnings)


def test_load_plate_unfold_and_volume(tmp_path):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    m = loader.load(drawing(str(tmp_path / "b.dxf")))
    assert len(m.solids) == 2 and m.flat_thickness == 1.6 and m.flat is not None
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(m.solids[0], g)
    assert g.Mass() == pytest.approx(AREA1 * 1.6, rel=1e-6)
    st = bc.BendSettings(material="SPCC")
    r = unfold(m.solids[0], settings=st)
    assert r.thickness == pytest.approx(1.6) and not r.bends and r.size == pytest.approx((200, 100), abs=1e-3)
    from hanil_unfold import dims
    assert len(dims.compute(r).holes) == 3
    m2 = loader.load(str(tmp_path / "b.dxf"), flat={"thickness": 3.0, "parts": [1]})
    assert len(m2.solids) == 1 and m2.flat_thickness == 3.0


def test_dwg_without_converter_explains(tmp_path, monkeypatch):
    dwg = tmp_path / "part.dwg"
    dwg.write_bytes(b"AC1032 fake")
    monkeypatch.setattr(dxf2d, "ODA_GLOBS", [])
    monkeypatch.setattr(dxf2d, "USER_CONVERTER", "")
    monkeypatch.setenv("HANIL_ODA", "")
    monkeypatch.setenv("PATH", str(tmp_path / "nobin"))
    with pytest.raises(dxf2d.DwgConverterMissing) as e:
        dxf2d.read(str(dwg))
    assert "ODA File Converter" in str(e.value)


@pytest.mark.skipif(sys.platform == "win32", reason="가짜 변환기 스크립트 (#!) 는 유닉스에서만")
def test_dwg_via_fake_libredwg(tmp_path, monkeypatch):
    src = drawing(str(tmp_path / "src.dxf"))
    dwg = tmp_path / "part.dwg"
    dwg.write_bytes(b"AC1032 fake")
    monkeypatch.setattr(dxf2d, "ODA_GLOBS", [])
    monkeypatch.setattr(dxf2d, "USER_CONVERTER", "")
    monkeypatch.setenv("HANIL_ODA", "")
    # LibreDWG dwg2dxf 처럼 움직이는 가짜 변환기: -o <출력> <입력>
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "dwg2dxf"
    fake.write_text(f"#!{sys.executable}\nimport shutil, sys\na = sys.argv\nshutil.copy({src!r}, a[a.index('-o') + 1])\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    assert dxf2d.find_converter()[0] == "libredwg"
    m = loader.load(str(dwg))
    assert len(m.solids) == 2


def test_import_dialog(tmp_path):
    from hanil_unfold.report import ensure_gui
    ensure_gui()
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from hanil_unfold.flat_import_dialog import FlatImportDialog
    fd = dxf2d.read(drawing(str(tmp_path / "c.dxf")))
    d = FlatImportDialog(fd)
    assert d.thickness() == 1.6 and d.material() == "SPCC" and d.parts() == [0, 1]
    d.list.item(1).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Unchecked)
    assert d.parts() == [0]
