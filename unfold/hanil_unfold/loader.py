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


class LazySolids:
    """솔리드 목록. 처음 꺼낼 때 자유곡면 되돌리기(canonical)를 해 두고 다시 쓴다.

    부품이 100개 넘는 조립품도 여는 즉시 화면에 나오고, 고른 부품만 손질하게 하려는 것이다.
    """

    def __init__(self, raw):
        self.raw = list(raw)
        self._done = {}
        self.recognized = {}

    def __len__(self):
        return len(self.raw)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [self[k] for k in range(*i.indices(len(self)))]
        if i < 0:
            i += len(self.raw)
        if i not in self._done:
            from .canonical import canonicalize
            # 형상 보정(ShapeFix)도 꺼낼 때 한다 — 열 때 모든 부품을 고치면 큰 조립품이 느리다
            solid, changed, kept = canonicalize(_first_solid(_fix(self.raw[i])))
            self._done[i] = solid
            self.recognized[i] = (changed, kept)
        return self._done[i]

    def __iter__(self):
        return (self[i] for i in range(len(self)))


def _first_solid(shape):
    found = list_solids(shape)
    return found[0] if found else shape


@dataclass
class LoadedModel:
    path: str
    shape: TopoDS_Shape
    solids: LazySolids
    names: list = None          # 부품 이름 (STEP 의 제품 이름, 없으면 "부품 N")
    cache_dir: str = ""         # 다시 열 때 쓰는 보관 폴더 (메시 등도 여기에)
    from_cache: bool = False

    @property
    def recognized(self):
        """솔리드 번호 → (자유곡면에서 평면·원통·원뿔로 되돌린 면 수, 남은 자유곡면 수)"""
        return self.solids.recognized

    @property
    def raw_solids(self):
        """손질하지 않은 원래 솔리드 (조립품 전체 그림용, 빠름)"""
        return self.solids.raw

    def label(self, i):
        return f"{i + 1}. {self.names[i]}" if self.names else f"{i + 1}"


def load(path: str, use_cache: bool = True) -> LoadedModel:
    ext = os.path.splitext(path)[1].lower()

    if ext in _CONVERT_HELP:
        raise UnsupportedFormat(CONVERT_GUIDE.format(name=_CONVERT_HELP[ext]))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")

    cdir = cache_dir_for(path) if use_cache else ""
    if cdir:
        cached = _read_cache(cdir)
        if cached is not None:
            solids, names = cached
            return LoadedModel(path=path, shape=_compound(solids), solids=LazySolids(solids),
                               names=names, cache_dir=cdir, from_cache=True)

    names = None
    if ext in (".stp", ".step"):
        parts = _read_step_parts(path)
        if parts is not None:
            solids = [s for s, _ in parts]
            names = _part_names([n for _, n in parts])
            shape = _compound(solids)
        else:
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

    if names is None:
        shape = _fix(shape)
        solids = list_solids(shape)
        names = [f"부품 {i + 1}" for i in range(len(solids))]
    if len(solids) == 1:
        # 부품 하나짜리 파일은 파일 이름이 곧 부품 이름 (제품 이름 칸에 변환기 이름이 든 파일이 많다)
        names = [os.path.splitext(os.path.basename(path))[0]]
    if not solids:
        raise ValueError(
            "파일 안에 솔리드(두께가 있는 3D 형상)가 없습니다.\n"
            "곡면(서피스)만 들어 있는 파일이면 CAD 에서 솔리드로 저장해 주세요."
        )
    if cdir:
        _write_cache(cdir, solids, names)
    # 평면·절곡 R 까지 자유곡면으로 저장된 파일은 부품을 꺼낼 때 원래 모양으로 되돌린다.
    return LoadedModel(path=path, shape=shape, solids=LazySolids(solids), names=names,
                       cache_dir=cdir)


# ---------------------------------------------------------------- 다시 열기 보관 (캐시)

CACHE_VERSION = "2"


def cache_root():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~/.cache")
    return os.path.join(base, "HanilUnfold", "cache")


def cache_dir_for(path):
    """파일 경로·크기·수정 시각이 같으면 같은 폴더. 파일이 바뀌면 새로 읽는다."""
    import hashlib
    try:
        st = os.stat(path)
    except OSError:
        return ""
    key = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}|{CACHE_VERSION}"
    return os.path.join(cache_root(), hashlib.sha1(key.encode("utf-8")).hexdigest()[:20])


def _read_cache(cdir):
    import json
    shape_path = os.path.join(cdir, "shape.bin")
    names_path = os.path.join(cdir, "names.json")
    if not (os.path.exists(shape_path) and os.path.exists(names_path)):
        return None
    try:
        from OCP.BinTools import BinTools
        shape = TopoDS_Shape()
        BinTools.Read_s(shape, shape_path)
        solids = list_solids(shape)
        with open(names_path, encoding="utf-8") as f:
            names = json.load(f)
        if not solids or len(names) != len(solids):
            return None
        os.utime(cdir, None)       # 최근에 쓴 보관 폴더로 표시 (오래된 것부터 지운다)
        return solids, names
    except Exception:
        return None


def _write_cache(cdir, solids, names, keep=15):
    import json
    import shutil
    try:
        from OCP.BinTools import BinTools
        os.makedirs(cdir, exist_ok=True)
        BinTools.Write_s(_compound(solids), os.path.join(cdir, "shape.bin"))
        with open(os.path.join(cdir, "names.json"), "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False)
        # 보관 폴더는 최근 keep 개만 남긴다
        root = cache_root()
        dirs = sorted((os.path.join(root, d) for d in os.listdir(root)),
                      key=lambda d: os.path.getmtime(d), reverse=True)
        for d in dirs[keep:]:
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def _fix(shape):
    fixer = ShapeFix_Shape(shape)
    fixer.Perform()
    return fixer.Shape()


def _compound(solids):
    from OCP.TopoDS import TopoDS_Compound
    comp = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(comp)
    for s in solids:
        b.Add(comp, s)
    return comp


def _part_names(raw):
    """STEP 제품 이름을 부품 이름으로. 이름이 없거나 모두 같으면(한 덩어리로 저장된 파일) '부품 N'.
    같은 이름이 여러 번 나오면(같은 부품을 여러 개 조립) 뒤에 #2, #3 을 붙인다."""
    import re
    junk = re.compile(r"^\s*(open cascade.*|.*step translator.*|"
                      r"(shell|solid|body|part|unnamed|noname)\s*(\(\d+\)|\d+)?)\s*$", re.I)
    raw = ["" if not n or junk.match(n) else n for n in raw]
    if not raw or len(set(raw)) == 1 and len(raw) > 1 or not any(raw):
        return [f"부품 {i + 1}" for i in range(len(raw))]
    seen = {}
    out = []
    for i, n in enumerate(raw):
        n = n.strip() or f"부품 {i + 1}"
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} #{seen[n]}")
    return out


def _read_step_parts(path):
    """조립 구조를 살려 읽는다: [(솔리드, 부품 이름)]. 실패하면 None (일반 읽기로)."""
    try:
        from OCP.collections import Sequence_TDF_Label
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDataStd import TDataStd_Name
        from OCP.TDF import TDF_Label
        from OCP.TDocStd import TDocStd_Document
        from OCP.TopLoc import TopLoc_Location
        from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    except ImportError:
        return None

    def name_of(label):
        attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
            return attr.Get().ToExtString()
        return ""

    try:
        doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        # 이름만 쓴다. 색·레이어·치수 주석 같은 것은 읽지 않아 빠르게
        for flag in ("SetColorMode", "SetLayerMode", "SetPropsMode", "SetSHUOMode",
                     "SetGDTMode", "SetMatMode", "SetViewMode"):
            try:
                getattr(reader, flag)(False)
            except Exception:
                pass
        if reader.ReadFile(path) != IFSelect_RetDone:
            raise ValueError("STEP 파일을 읽지 못했습니다. 파일이 손상되었을 수 있습니다.")
        if not reader.Transfer(doc):
            return None
        tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        out = []

        def walk(label, loc, name, depth=0):
            if depth > 50:
                return
            if XCAFDoc_ShapeTool.IsAssembly_s(label):
                comps = Sequence_TDF_Label()
                XCAFDoc_ShapeTool.GetComponents_s(label, comps, False)
                for i in range(1, comps.Length() + 1):
                    comp = comps.Value(i)
                    ref = TDF_Label()
                    XCAFDoc_ShapeTool.GetReferredShape_s(comp, ref)
                    walk(ref, loc.Multiplied(XCAFDoc_ShapeTool.GetLocation_s(comp)),
                         name_of(ref) or name_of(comp), depth + 1)
            else:
                shape = XCAFDoc_ShapeTool.GetShape_s(label)
                if not loc.IsIdentity():
                    shape = shape.Moved(loc)
                for s in list_solids(shape):
                    out.append((s, name or name_of(label)))

        free = Sequence_TDF_Label()
        tool.GetFreeShapes(free)
        for i in range(1, free.Length() + 1):
            label = free.Value(i)
            walk(label, TopLoc_Location(), name_of(label))
        return out or None
    except ValueError:
        raise
    except Exception:
        return None


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
