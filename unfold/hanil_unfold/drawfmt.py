"""도면 파일 형식: DXF → DWG (변환기), 도면 선 → STEP (2D 와이어), 전개도 → STEP (평판 솔리드).

DWG 는 형식이 공개되지 않아 직접 쓰지 않고, 무료 변환기로 DXF 를 바꾼다 (DWG 읽기와 같은 변환기):
  1. ODA File Converter (Open Design Alliance) — Windows 설치 폴더를 찾아 씀 (dxf2d.find_converter)
  2. LibreDWG 의 dxf2dwg (있으면)
STEP 은 3D 형식이라 도면 (선·원·호) 을 Z = 0 평면의 곡선 (와이어) 으로 넣는다 — CATIA·NX·SolidWorks·Inventor 가 STEP 을
열면 선으로 보인다 (글자는 들어가지 않음 — 글자는 PDF·DXF·DWG 로). 시트마다 이름 붙인 묶음.
"""
from __future__ import annotations

import glob
import math
import os
import shutil
import subprocess
import tempfile

import numpy as np

DWG_VERSION = "ACAD2018"


class DwgWriteError(RuntimeError):
    pass


def find_dwg_writer(user_path=""):
    """('oda' | 'libredwg', 실행 파일) 또는 None."""
    from . import dxf2d
    conv = dxf2d.find_converter(user_path)
    if conv is not None and conv[0] == "oda":
        return conv
    w = shutil.which("dxf2dwg")
    if w:
        return "libredwg", w
    return None


def dxf_to_dwg(dxf_path, dwg_path, user_path="", timeout=180):
    """DXF → DWG (AutoCAD 2018). 변환기가 없으면 dxf2d.DwgConverterMissing."""
    from . import dxf2d
    conv = find_dwg_writer(user_path)
    if conv is None:
        raise dxf2d.DwgConverterMissing(
            "DWG 로 저장하려면 무료 변환기 ODA File Converter 가 필요합니다 (DWG 읽기와 같은 것).\n\n"
            f"  1. {dxf2d.ODA_URL} 에서 Windows 판을 내려받아 설치\n"
            "  2. 다시 저장 (설치 폴더는 자동으로 찾습니다 — 다른 곳에 깔았으면 [파일] → [DWG 변환기 위치])\n\n"
            "DXF 는 그대로 저장했습니다 — AutoCAD 에서 DXF 를 열어 DWG 로 저장해도 됩니다.")
    kind, exe = conv
    out_dir = tempfile.mkdtemp(prefix="hanil_dwg_out_")
    if kind == "oda":
        in_dir = tempfile.mkdtemp(prefix="hanil_dwg_src_")
        src = os.path.join(in_dir, os.path.basename(dxf_path))
        shutil.copy2(dxf_path, src)
        cmd = [exe, in_dir, out_dir, DWG_VERSION, "DWG", "0", "1", os.path.basename(dxf_path)]
    else:
        cmd = [exe, "-y", "-o", os.path.join(out_dir, os.path.splitext(os.path.basename(dxf_path))[0] + ".dwg"),
               dxf_path]
    try:
        subprocess.run(cmd, check=False, timeout=timeout, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as e:
        raise DwgWriteError("DWG 변환이 너무 오래 걸립니다 (변환기 멈춤)") from e
    found = glob.glob(os.path.join(out_dir, "*.dwg")) + glob.glob(os.path.join(out_dir, "*.DWG"))
    if not found:
        raise DwgWriteError(f"DXF 를 DWG 로 바꾸지 못했습니다 ({kind}: {os.path.basename(exe)})")
    shutil.move(found[0], dwg_path)
    return dwg_path


# ---------------------------------------------------------------- STEP

def _edges_for(ents, ox=0.0, oy=0.0):
    """Sheet.ents 꼴 (line · poly · circle) 을 OCC 모서리로."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.GC import GC_MakeCircle
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    out = []

    def P(x, y):
        return gp_Pnt(float(x + ox), float(y + oy), 0.0)
    for e in ents:
        k = e[0]
        try:
            if k == "line":
                _, x1, y1, x2, y2 = e[:5]
                if math.hypot(x2 - x1, y2 - y1) > 1e-6:
                    out.append(BRepBuilderAPI_MakeEdge(P(x1, y1), P(x2, y2)).Edge())
            elif k == "poly":
                pts, closed = e[1], e[2]
                Q = list(pts) + ([pts[0]] if closed else [])
                for a, b in zip(Q[:-1], Q[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                        out.append(BRepBuilderAPI_MakeEdge(P(*a), P(*b)).Edge())
            elif k == "circle":
                _, x, y, r = e[:4]
                c = gp_Circ(gp_Ax2(P(x, y), gp_Dir(0, 0, 1)), float(r))
                out.append(BRepBuilderAPI_MakeEdge(GC_MakeCircle(c).Value()).Edge())
        except Exception:  # noqa: BLE001 — 못 만드는 조각은 뺌
            continue
    return out


def _write_named(shapes_names, path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for shp, nm in shapes_names:
        lab = st.AddShape(shp, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString("".join(ch if ord(ch) < 128 else "_" for ch in nm)))
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    from .loader import step_write
    return step_write(w, path)


def _compound(edges):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for e in edges:
        b.Add(c, e)
    return c


def sheets_to_step(sheets, path, gap=30.0):
    """도면집 (diedraw.Sheet 목록) → STEP: 시트마다 선·원을 Z = 0 와이어 묶음 (DXF 와 같은 자리, 옆으로 늘어놓음)."""
    items = []
    ox = 0.0
    for i, sh in enumerate(sheets, 1):
        edges = _edges_for([e for e in sh.ents if e[0] != "text"], ox, 0.0)
        if edges:
            items.append((_compound(edges), f"SHEET {i:02d} {sh.number}"))
        ox += sh.size[0] + gap
    return _write_named(items, path)


def dxf_to_step(dxf_path, path):
    """DXF (선·폴리선·원·호) → STEP 와이어 (전개도 DXF 를 STEP 으로)."""
    import ezdxf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.GC import GC_MakeArcOfCircle, GC_MakeCircle
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    doc = ezdxf.readfile(dxf_path)
    by_layer = {}

    def P(v):
        return gp_Pnt(float(v[0]), float(v[1]), 0.0)
    for e in doc.modelspace():
        t = e.dxftype()
        lay = e.dxf.layer
        try:
            if t == "LINE":
                if (e.dxf.start - e.dxf.end).magnitude > 1e-6:
                    by_layer.setdefault(lay, []).append(BRepBuilderAPI_MakeEdge(P(e.dxf.start), P(e.dxf.end)).Edge())
            elif t == "CIRCLE":
                c = gp_Circ(gp_Ax2(P(e.dxf.center), gp_Dir(0, 0, 1)), float(e.dxf.radius))
                by_layer.setdefault(lay, []).append(BRepBuilderAPI_MakeEdge(GC_MakeCircle(c).Value()).Edge())
            elif t == "ARC":
                c = gp_Circ(gp_Ax2(P(e.dxf.center), gp_Dir(0, 0, 1)), float(e.dxf.radius))
                a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
                if a1 <= a0:
                    a1 += 2 * math.pi
                by_layer.setdefault(lay, []).append(
                    BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(c, a0, a1, True).Value()).Edge())
            elif t in ("LWPOLYLINE", "POLYLINE"):
                pts = [tuple(p[:2]) for p in (e.get_points("xy") if t == "LWPOLYLINE" else e.points())]
                if getattr(e, "closed", False) or (t == "LWPOLYLINE" and e.closed):
                    pts.append(pts[0])
                for a, b in zip(pts[:-1], pts[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                        by_layer.setdefault(lay, []).append(BRepBuilderAPI_MakeEdge(P(a), P(b)).Edge())
        except Exception:  # noqa: BLE001
            continue
    items = [(_compound(es), f"LAYER {lay}") for lay, es in by_layer.items() if es]
    return _write_named(items, path)


def flat_step(result, path, name="FLAT"):
    """전개도 → 평판 솔리드 STEP (바깥 − 구멍 을 두께만큼 밀어냄) — 레이저·펀칭 CAM, 조립 검토용."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    from .die3d import _simplify, _wire
    from .nesting import NestPart
    from OCP.BRepCheck import BRepCheck_Analyzer

    from . import unfoldcheck
    part = NestPart.from_result("p", result)
    if part.outer is None:
        raise ValueError("전개 외곽이 닫혀 있지 않아 평판 솔리드를 만들 수 없습니다")
    t = float(result.thickness)
    if not (t > 0):
        raise ValueError("두께가 0 이라 평판 솔리드를 만들 수 없습니다")
    outer = _simplify(np.asarray(part.outer, float), 0.002)
    # 스스로 가로지르는 외곽 (성형품 전개의 주름 · 겹침) 으로 면을 만들면 OpenCASCADE 가 죽을 수 있어 먼저 거른다
    if len(outer) < 3 or unfoldcheck.crossings([outer]):
        raise ValueError("전개 외곽이 스스로 가로질러 (겹침) 평판 솔리드를 만들 수 없습니다 — DXF 로 저장해 CAD 에서 정리해 주세요")

    def prism(P, z0, h):
        f = BRepBuilderAPI_MakeFace(_wire(P, z0), True).Face()
        if not BRepCheck_Analyzer(f).IsValid():
            raise ValueError("면이 올바르지 않음")
        sh = BRepPrimAPI_MakePrism(f, gp_Vec(0, 0, h)).Shape()
        if not BRepCheck_Analyzer(sh).IsValid():
            raise ValueError("밀어낸 솔리드가 올바르지 않음")
        return sh
    s = prism(outer, 0.0, t)
    for h in part.holes:
        try:
            hp = _simplify(np.asarray(h, float), 0.002)
            if len(hp) < 3 or unfoldcheck.crossings([hp]):
                continue
            cut = BRepAlgoAPI_Cut(s, prism(hp, -1.0, t + 2))
            if not cut.IsDone():
                continue
            s2 = cut.Shape()
            if BRepCheck_Analyzer(s2).IsValid():
                s = s2
        except Exception:  # noqa: BLE001
            pass
    return _write_named([(s, name)], path)
