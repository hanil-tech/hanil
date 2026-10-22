"""3D 도면 파일을 읽어 솔리드 목록으로 돌려준다.

읽을 수 있는 형식: STEP(.stp/.step), IGES(.igs/.iges), OpenCASCADE BREP(.brep)

CATIA(.CATPart), NX(.prt), 솔리드웍스(.sldprt), DWG 는 각 회사 고유 형식이라
무료 라이브러리로는 열 수 없다. 이 경우 어떻게 STEP 으로 저장하는지 안내 문구를 돌려준다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from OCP.BRep import BRep_Builder
from OCP.BRepTools import BRepTools
from OCP.IFSelect import IFSelect_RetDone
from OCP.IGESControl import IGESControl_Reader
from OCP.ShapeFix import ShapeFix_Shape
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape


class UnsupportedFormat(Exception):
    """직접 열 수 없는 형식. 메시지에 변환 방법이 들어 있다."""


# 확장자별 안내. 사용자가 그대로 따라 할 수 있게 메뉴 이름까지 적는다.
_CONVERT_HELP = {
    ".catpart": "CATIA 파일(.CATPart)",
    ".catproduct": "CATIA 조립 파일(.CATProduct)",
    ".prt": "NX 파일(.prt)",
    ".sldprt": "솔리드웍스 파일(.sldprt)",
    ".sldasm": "솔리드웍스 조립 파일(.sldasm)",
    ".dwg": "AutoCAD 파일(.dwg)",
    ".dxf": "DXF 파일",
    ".x_t": "Parasolid 파일(.x_t)",
    ".x_b": "Parasolid 파일(.x_b)",
    ".sat": "ACIS 파일(.sat)",
}

CONVERT_GUIDE = """\
{name}은(는) 만든 회사 고유 형식이라 이 프로그램에서 바로 열 수 없습니다.
쓰시는 CAD 에서 STEP 으로 저장한 뒤 그 파일을 열어 주세요.

  · 솔리드웍스 : 파일 → 다른 이름으로 저장 → 파일 형식 "STEP AP214 (*.step)"
  · NX         : 파일 → 내보내기 → STEP  (또는 STEP214)
  · CATIA      : File → Save As → 형식 "stp"
  · AutoCAD    : 3D 솔리드를 STEP 으로 내보내기 (EXPORT 또는 STEPOUT 명령)

판금 부품 하나씩 저장하시면 가장 정확합니다.
"""

SUPPORTED_EXTENSIONS = (".stp", ".step", ".igs", ".iges", ".brep", ".brp")


@dataclass
class LoadedModel:
    path: str
    shape: TopoDS_Shape
    solids: list
    # 솔리드마다 (자유곡면에서 평면·원통·원뿔로 되돌린 면 수, 자유곡면으로 남은 면 수)
    recognized: list = None


def load(path: str) -> LoadedModel:
    ext = os.path.splitext(path)[1].lower()

    if ext in _CONVERT_HELP:
        raise UnsupportedFormat(CONVERT_GUIDE.format(name=_CONVERT_HELP[ext]))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")

    if ext in (".stp", ".step"):
        shape = _read_step(path)
    elif ext in (".igs", ".iges"):
        shape = _read_iges(path)
    elif ext in (".brep", ".brp"):
        shape = _read_brep(path)
    else:
        raise UnsupportedFormat(
            f"알 수 없는 파일 형식입니다: {ext or '(확장자 없음)'}\n"
            "STEP(.stp, .step) 파일을 열어 주세요."
        )

    fixer = ShapeFix_Shape(shape)
    fixer.Perform()
    shape = fixer.Shape()

    solids = list_solids(shape)
    if not solids:
        raise ValueError(
            "파일 안에 솔리드(두께가 있는 3D 형상)가 없습니다.\n"
            "곡면(서피스)만 들어 있는 파일이면 CAD 에서 솔리드로 저장해 주세요."
        )
    # 평면·절곡 R 까지 자유곡면으로 저장된 파일이면 원래 모양으로 되돌린다.
    from .canonical import canonicalize
    recognized = []
    for i, s in enumerate(solids):
        solids[i], changed, kept = canonicalize(s)
        recognized.append((changed, kept))
    return LoadedModel(path=path, shape=shape, solids=solids, recognized=recognized)


def list_solids(shape: TopoDS_Shape) -> list:
    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        solids.append(TopoDS.Solid(exp.Current()))
        exp.Next()
    return solids


def _read_step(path: str) -> TopoDS_Shape:
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError("STEP 파일을 읽지 못했습니다. 파일이 손상되었을 수 있습니다.")
    reader.TransferRoots()
    return reader.OneShape()


def _read_iges(path: str) -> TopoDS_Shape:
    reader = IGESControl_Reader()
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise ValueError("IGES 파일을 읽지 못했습니다. 파일이 손상되었을 수 있습니다.")
    reader.TransferRoots()
    return reader.OneShape()


def _read_brep(path: str) -> TopoDS_Shape:
    shape = TopoDS_Shape()
    if not BRepTools.Read_s(shape, path, BRep_Builder()):
        raise ValueError("BREP 파일을 읽지 못했습니다.")
    return shape
