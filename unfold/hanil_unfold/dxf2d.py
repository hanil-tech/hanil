"""2D 도면 (DXF · DWG) 읽기: 블랭크 (전개도) 윤곽과 구멍을 찾아 판 두께만큼 3D 평판으로 만든다.

평판 솔리드가 되면 STEP 부품과 똑같이 전개 (그대로 평판) · 무게 · 절단 길이 · 네스팅 · 레이저·블랭킹 견적 ·
금형 검토 · 검사 성적서를 쓸 수 있다.

DWG 는 AutoCAD 고유 형식이라 무료 변환기로 DXF 로 바꾼 뒤 읽는다:
  1. ODA File Converter (Open Design Alliance, 무료) — Windows 기본 설치 폴더를 찾아 쓴다
  2. LibreDWG 의 dwg2dxf (있으면)
윤곽 찾기
  · 선·원호·원·폴리선 (볼록 bulge)·스플라인·타원, 블록 (INSERT) 은 펼쳐서
  · 치수·글자·해치·중심선·숨은선 (선 종류 CENTER·HIDDEN·DASH…, 층 이름 DIM·TEXT·CENTER·치수·중심…) 은 뺀다
  · 절곡선 층 (BEND·절곡·벤딩) 의 선은 절곡선으로 따로 센다
  · 끝점을 이어 닫힌 고리로, 고리 안에 고리가 있으면 구멍 — 바깥 고리 하나 = 부품 하나
  · 다른 고리를 둘러싼 큰 사각형은 도면 테두리로 보고 뺀다 (가져오기 창에서 고칠 수 있음)
  · 글자에서 두께 (t1.6, T=2.0, 1.6t) · 재질 (SPCC, SUS304 …) 을 찾는다
단위: 헤더 $INSUNITS (1 inch → 25.4, 5 cm → 10, 6 m → 1000, 그 밖은 mm).
"""
from __future__ import annotations

import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

TOL = 0.02                     # 끝점 잇기 허용 (mm)
SKIP_TYPES = {"DIMENSION", "TEXT", "MTEXT", "HATCH", "POINT", "LEADER", "MLEADER", "ATTRIB", "ATTDEF", "TOLERANCE",
              "IMAGE", "WIPEOUT", "SOLID", "3DFACE", "VIEWPORT", "XLINE", "RAY", "ACAD_TABLE", "MULTILEADER"}
SKIP_LAYER = re.compile(r"(?i)(dim|text|txt|center|centre|hidden|hide|note|title|frame|border|anno|hatch|"
                        r"치수|문자|글자|중심|숨은|표제|도곽|테두리|주석)")
BEND_LAYER = re.compile(r"(?i)(bend|fold|절곡|벤딩|꺾)")
SKIP_LTYPE = re.compile(r"(?i)(center|centre|hidden|dash|dot|phantom|divide)")
UNITS = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 13: 0.001, 14: 0.0001}

ODA_GLOBS = [r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
             r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe",
             "/usr/bin/ODAFileConverter", "/opt/ODAFileConverter*/ODAFileConverter"]
ODA_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
USER_CONVERTER = ""            # 앱 설정 [파일] → [DWG 변환기 위치] 에서 고른 실행 파일


class DwgConverterMissing(Exception):
    pass


# ---------------------------------------------------------------- DWG → DXF

def find_converter(user_path=""):
    """('oda' 또는 'libredwg', 실행 파일) 또는 None."""
    cands = [user_path or USER_CONVERTER]
    cands += [os.environ.get("HANIL_ODA", "")]
    for g in ODA_GLOBS:
        cands += sorted(glob.glob(g), reverse=True)
    for c in cands:
        if c and os.path.isfile(c):
            return "oda", c
    w = shutil.which("ODAFileConverter")
    if w:
        return "oda", w
    w = shutil.which("dwg2dxf")
    if w:
        return "libredwg", w
    return None


def dwg_to_dxf(path, user_path="", timeout=180):
    """DWG → 임시 DXF 경로. 변환기가 없으면 DwgConverterMissing."""
    conv = find_converter(user_path)
    if conv is None:
        raise DwgConverterMissing(
            "DWG 를 읽으려면 무료 변환기 ODA File Converter 가 필요합니다.\n\n"
            f"  1. {ODA_URL} 에서 Windows 판을 내려받아 설치\n"
            "  2. 이 파일을 다시 열기 (설치 폴더는 자동으로 찾습니다 — 다른 곳에 깔았으면 [파일] → [DWG 변환기 위치])\n\n"
            "또는 AutoCAD 에서 DXF 로 저장 (SAVEAS → AutoCAD 2018 DXF) 해서 여세요.")
    kind, exe = conv
    out_dir = tempfile.mkdtemp(prefix="hanil_dwg_")
    base = os.path.splitext(os.path.basename(path))[0]
    if kind == "oda":
        in_dir = tempfile.mkdtemp(prefix="hanil_dwg_in_")
        src = os.path.join(in_dir, os.path.basename(path))
        shutil.copy2(path, src)
        # ODAFileConverter <입력 폴더> <출력 폴더> <버전> <형식> <하위 폴더 0/1> <검사 0/1> [<필터>]
        cmd = [exe, in_dir, out_dir, "ACAD2018", "DXF", "0", "1", os.path.basename(path)]
    else:
        cmd = [exe, "-y", "-o", os.path.join(out_dir, base + ".dxf"), path]
    try:
        subprocess.run(cmd, check=False, timeout=timeout, capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise RuntimeError("DWG 변환이 너무 오래 걸립니다 (변환기 멈춤)")
    found = glob.glob(os.path.join(out_dir, "*.dxf")) + glob.glob(os.path.join(out_dir, "*.DXF"))
    if not found:
        raise RuntimeError(f"DWG 를 DXF 로 바꾸지 못했습니다 ({kind}: {os.path.basename(exe)}). "
                           "도면이 깨졌거나 아주 새 버전일 수 있습니다 — AutoCAD 에서 DXF 로 저장해 보세요.")
    return found[0]


# ---------------------------------------------------------------- 선 조각

@dataclass
class Seg:
    """선분 (bulge 0) 또는 원호 조각 (bulge = tan(사잇각/4), 반시계 +)."""
    a: tuple
    b: tuple
    bulge: float = 0.0

    def reversed(self):
        return Seg(self.b, self.a, -self.bulge)

    def length(self):
        c = math.dist(self.a, self.b)
        if abs(self.bulge) < 1e-12:
            return c
        th = 4 * math.atan(abs(self.bulge))
        return c * th / (2 * math.sin(th / 2)) if th > 1e-9 else c

    def points(self, n=None):
        if abs(self.bulge) < 1e-12:
            return [self.a, self.b]
        th = 4 * math.atan(self.bulge)
        n = n or max(4, int(abs(th) / math.radians(5)))
        (cx, cy), r = self.center_radius()
        a0 = math.atan2(self.a[1] - cy, self.a[0] - cx)
        return [(cx + r * math.cos(a0 + th * k / n), cy + r * math.sin(a0 + th * k / n)) for k in range(n + 1)]

    def center_radius(self):
        """원호의 중심·반지름 (bulge 정의에서 바로)."""
        (x1, y1), (x2, y2) = self.a, self.b
        bl = self.bulge
        c = math.dist(self.a, self.b)
        r = c * (1 + bl * bl) / (4 * abs(bl))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # 현 가운데에서 왼쪽 법선 방향으로 (r − sagitta) — sagitta = bulge · c/2
        sag = bl * c / 2
        nx, ny = -(y2 - y1) / c, (x2 - x1) / c
        off = (r - abs(sag)) * (1 if bl > 0 else -1)
        return (mx + nx * off, my + ny * off), r

    def mid(self):
        if abs(self.bulge) < 1e-12:
            return ((self.a[0] + self.b[0]) / 2, (self.a[1] + self.b[1]) / 2)
        (cx, cy), r = self.center_radius()
        th = 4 * math.atan(self.bulge)
        a0 = math.atan2(self.a[1] - cy, self.a[0] - cx)
        return (cx + r * math.cos(a0 + th / 2), cy + r * math.sin(a0 + th / 2))


@dataclass
class Loop:
    segs: list
    circle: tuple | None = None          # (중심, 반지름) — 원 하나로 된 고리

    @property
    def area(self):
        return abs(self.signed_area)

    @property
    def signed_area(self):
        if self.circle:
            return math.pi * self.circle[1] ** 2
        a = 0.0
        for s in self.segs:
            (x1, y1), (x2, y2) = s.a, s.b
            a += (x1 * y2 - x2 * y1) / 2
            if abs(s.bulge) > 1e-12:          # 원호 조각 몫 (활꼴)
                th = 4 * math.atan(s.bulge)
                _, r = s.center_radius()
                a += r * r * (th - math.sin(th)) / 2
        return a

    def polygon(self):
        if self.circle:
            (cx, cy), r = self.circle
            return [(cx + r * math.cos(2 * math.pi * k / 72), cy + r * math.sin(2 * math.pi * k / 72)) for k in range(72)]
        pts = []
        for s in self.segs:
            pts += s.points()[:-1]
        return pts

    def bbox(self):
        P = self.polygon()
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        return min(xs), min(ys), max(xs), max(ys)

    def length(self):
        if self.circle:
            return 2 * math.pi * self.circle[1]
        return sum(s.length() for s in self.segs)

    def contains(self, p):
        """점이 고리 안에 있나 (홀짝 규칙, 다각형 근사)."""
        P = self.polygon()
        x, y = p
        inside = False
        j = len(P) - 1
        for i in range(len(P)):
            xi, yi = P[i]
            xj, yj = P[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi:
                inside = not inside
            j = i
        return inside

    def sample(self):
        """고리 위의 한 점 (안쪽 판정용)."""
        if self.circle:
            (cx, cy), r = self.circle
            return (cx + r, cy)
        return self.segs[0].mid()

    def is_rect(self):
        P = self.polygon()
        if self.circle or len(P) != 4:
            return False
        x0, y0, x1, y1 = self.bbox()
        return abs(self.area - (x1 - x0) * (y1 - y0)) < 1e-3 * self.area


@dataclass
class FlatPart:
    outer: Loop
    holes: list = field(default_factory=list)
    name: str = ""
    frame: bool = False                    # 도면 테두리로 보임 (기본 뺌)

    @property
    def size(self):
        x0, y0, x1, y1 = self.outer.bbox()
        return x1 - x0, y1 - y0

    @property
    def area(self):
        return self.outer.area - sum(h.area for h in self.holes)

    @property
    def cut_length(self):
        return self.outer.length() + sum(h.length() for h in self.holes)


@dataclass
class FlatDrawing:
    path: str
    parts: list
    thickness: float | None = None         # 글자에서 찾은 두께
    material: str | None = None            # 글자에서 찾은 재질 코드
    scale: float = 1.0                     # 도면 단위 → mm
    bend_lines: list = field(default_factory=list)   # [(a, b)]
    open_ends: int = 0                     # 닫히지 않은 끝 (빠진 선이 있으면)
    texts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------- DXF 읽기

def _entity_segs(e, scale, out_segs, out_circles, bends, texts, depth=0):
    t = e.dxftype()
    layer = e.dxf.get("layer", "0") or "0"
    if t in ("TEXT", "MTEXT", "ATTRIB"):
        try:
            texts.append(e.plain_text() if t == "MTEXT" else e.dxf.text)
        except Exception:
            pass
        return
    if t == "INSERT":
        if depth > 8:
            return
        try:
            for v in e.virtual_entities():
                _entity_segs(v, scale, out_segs, out_circles, bends, texts, depth + 1)
        except Exception:
            pass
        return
    if t in SKIP_TYPES:
        return
    lt = ""
    try:
        lt = e.dxf.get("linetype", "") or ""
    except Exception:
        pass
    is_bend = bool(BEND_LAYER.search(layer))
    if not is_bend and (SKIP_LAYER.search(layer) or SKIP_LTYPE.search(lt)):
        return

    def P(v):
        return (float(v[0]) * scale, float(v[1]) * scale)
    segs = []
    if t == "LINE":
        segs.append(Seg(P(e.dxf.start), P(e.dxf.end)))
    elif t == "CIRCLE":
        if is_bend:
            return
        out_circles.append((P(e.dxf.center), float(e.dxf.radius) * scale))
        return
    elif t == "ARC":
        c, r = P(e.dxf.center), float(e.dxf.radius) * scale
        a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
        sweep = (a1 - a0) % (2 * math.pi) or 2 * math.pi
        if abs(sweep - 2 * math.pi) < 1e-9:
            out_circles.append((c, r))
            return
        pa = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
        pb = (c[0] + r * math.cos(a0 + sweep), c[1] + r * math.sin(a0 + sweep))
        segs.append(Seg(pa, pb, math.tan(sweep / 4)))
    elif t == "LWPOLYLINE":
        pts = list(e.get_points("xyb"))
        n = len(pts)
        for i in range(n if e.closed else n - 1):
            x1, y1, b = pts[i]
            x2, y2, _ = pts[(i + 1) % n]
            segs.append(Seg(P((x1, y1)), P((x2, y2)), float(b or 0.0)))
    elif t == "POLYLINE":
        if not e.is_2d_polyline:
            return
        vs = list(e.vertices)
        n = len(vs)
        for i in range(n if e.is_closed else n - 1):
            v1, v2 = vs[i], vs[(i + 1) % n]
            segs.append(Seg(P(v1.dxf.location), P(v2.dxf.location), float(v1.dxf.get("bulge", 0.0) or 0.0)))
    elif t in ("SPLINE", "ELLIPSE"):
        try:
            pts = [P(p) for p in e.flattening(0.01 / max(scale, 1e-9))]
        except Exception:
            return
        segs += [Seg(a, b) for a, b in zip(pts[:-1], pts[1:]) if math.dist(a, b) > 1e-9]
    else:
        return
    segs = [s for s in segs if math.dist(s.a, s.b) > 1e-9]
    if is_bend:
        bends += [(s.a, s.b) for s in segs if abs(s.bulge) < 1e-12]
    else:
        out_segs += segs


def _chain(segs, tol=TOL):
    """끝점을 이어 고리로. (닫힌 고리들, 남은 열린 끝 수)."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))  # noqa: E731
    ends = {}
    for i, s in enumerate(segs):
        for end, p in ((0, s.a), (1, s.b)):
            kx, ky = key(p)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    ends.setdefault((kx + dx, ky + dy), []).append((i, end))
    used = [False] * len(segs)
    loops, open_ends = [], 0

    def near(p):
        return [(i, e) for i, e in ends.get(key(p), []) if not used[i]
                and math.dist(p, segs[i].a if e == 0 else segs[i].b) <= tol * 1.5]
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        used[i0] = True
        chain = [segs[i0]]
        start = segs[i0].a
        cur = segs[i0].b
        while math.dist(cur, start) > tol:
            nxt = near(cur)
            if not nxt:
                break
            i, e = nxt[0]
            used[i] = True
            s = segs[i] if e == 0 else segs[i].reversed()
            chain.append(s)
            cur = s.b
        if math.dist(cur, start) <= tol and len(chain) >= 2 or (len(chain) == 1 and abs(chain[0].bulge) > 0
                                                                 and math.dist(cur, start) <= tol):
            chain[-1] = Seg(chain[-1].a, start, chain[-1].bulge)     # 끝을 처음 점에 딱 맞춤
            loops.append(Loop(chain))
        else:
            open_ends += 1
    return loops, open_ends


THICK_RE = [re.compile(r"(?i)\b[tT]\s*[=:]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\b"),
            re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*[tT]\b"),
            re.compile(r"(?:두께|板厚|THK|THICK(?:NESS)?)\s*[=:]?\s*(\d+(?:\.\d+)?)", re.I)]
MAT_ALIASES = {"SS400": "SS275", "SS41": "SS275", "SPCD": "SPCC", "SPCE": "SPCC", "SPHD": "SPHC", "SPHE": "SPHC",
               "STS304": "SUS304", "STS430": "SUS430", "A5052": "AL5052", "A1050": "AL1050", "A6061": "AL6061",
               "AL5052P": "AL5052", "SAPH440P": "SAPH440", "SGARC": "SGARC440"}


def parse_texts(texts):
    """(두께, 재질 코드) — 글자에서. 못 찾으면 None."""
    from . import bendcalc as bc
    thick, mat = None, None
    codes = sorted(list(bc.MATERIAL_BY_CODE) + list(MAT_ALIASES), key=len, reverse=True)
    for tx in texts:
        s = (tx or "").replace("\n", " ")
        up = s.upper().replace("-", "").replace(" ", "")
        if mat is None:
            for c in codes:
                if c in up:
                    mat = MAT_ALIASES.get(c, c)
                    break
        if thick is None:
            for rx in THICK_RE:
                m = rx.search(s)
                if m:
                    v = float(m.group(1))
                    if 0.1 <= v <= 25:
                        thick = v
                        break
    return thick, mat


def read(path, converter="") -> FlatDrawing:
    """DXF (또는 DWG) → FlatDrawing."""
    import ezdxf
    from ezdxf import recover
    src = path
    if path.lower().endswith(".dwg"):
        src = dwg_to_dxf(path, converter)
    try:
        doc = ezdxf.readfile(src)
    except Exception:
        doc, _ = recover.readfile(src)                 # 깨진 DXF 도 되살려 읽기
    scale = UNITS.get(int(doc.header.get("$INSUNITS", 4) or 4), 1.0)
    segs, circles, bends, texts = [], [], [], []
    for e in doc.modelspace():
        _entity_segs(e, scale, segs, circles, bends, texts)
    loops, open_ends = _chain(segs)
    loops += [Loop([], circle=(c, r)) for c, r in circles if r > 1e-6]
    loops = [lp for lp in loops if lp.area > 1e-4]
    fd = FlatDrawing(path, [], scale=scale, bend_lines=bends, open_ends=open_ends, texts=texts)
    fd.thickness, fd.material = parse_texts(texts)
    fd.parts = _parts(loops)
    if open_ends:
        fd.warnings.append(f"닫히지 않은 선 {open_ends} 묶음은 뺐습니다 (선 끝이 {TOL} mm 넘게 떨어짐)")
    if not fd.parts:
        fd.warnings.append("닫힌 윤곽을 못 찾았습니다 — 외곽선이 끊겼거나 치수·중심선 층에만 그려져 있을 수 있습니다")
    return fd


def _parts(loops):
    """고리 → 부품 (바깥 + 바로 안 구멍). 고리 깊이: 짝수 = 바깥, 홀수 = 구멍."""
    loops = sorted(loops, key=lambda lp: -lp.area)
    parent = [None] * len(loops)
    for i, lp in enumerate(loops):
        p = lp.sample()
        for j in range(i - 1, -1, -1):                 # 자기보다 큰 것 중 가장 작은 것
            if loops[j].area > lp.area and loops[j].contains(p):
                parent[i] = j
                break
    depth = []
    for i in range(len(loops)):
        d, k = 0, parent[i]
        while k is not None:
            d, k = d + 1, parent[k]
        depth.append(d)
    # 도면 테두리: 깊이 0 사각형이 다른 바깥 고리 (깊이 1 이면서 그 안에 또 고리 — 즉 부품) 를 둘러쌈
    frame = set()
    for i, lp in enumerate(loops):
        if depth[i] == 0 and lp.is_rect():
            kids = [k for k in range(len(loops)) if parent[k] == i]
            if any(any(parent[g] == k for g in range(len(loops))) for k in kids) or len(kids) >= 2:
                frame.add(i)
    shift = {i: (1 if any(a in frame for a in _ancestors(parent, i)) else 0) for i in range(len(loops))}
    parts = {}
    for i in range(len(loops)):
        if i in frame:
            continue
        d = depth[i] - shift[i]
        if d % 2 == 0:
            parts[i] = FlatPart(loops[i])
    for i in range(len(loops)):
        if i in frame or i in parts:
            continue
        if parent[i] in parts:
            parts[parent[i]].holes.append(loops[i])
    out = sorted(parts.values(), key=lambda p: -p.area)
    for k, p in enumerate(out, 1):
        w, h = p.size
        p.name = f"블랭크 {k} ({w:,.1f} × {h:,.1f}" + (f", 구멍 {len(p.holes)}" if p.holes else "") + ")"
    for i in frame:                                    # 테두리도 목록에 (기본 뺌)
        fp = FlatPart(loops[i], [], "도면 테두리로 보임", True)
        out.append(fp)
    return out


def _ancestors(parent, i):
    k = parent[i]
    while k is not None:
        yield k
        k = parent[k]


# ---------------------------------------------------------------- 3D 평판

def _wire(loop, z=0.0):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
    mk = BRepBuilderAPI_MakeWire()
    if loop.circle:
        (cx, cy), r = loop.circle
        mk.Add(BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(cx, cy, z), gp_Dir(0, 0, 1)), r)).Edge())
        return mk.Wire()
    for s in loop.segs:
        a, b = gp_Pnt(s.a[0], s.a[1], z), gp_Pnt(s.b[0], s.b[1], z)
        if abs(s.bulge) < 1e-12:
            e = BRepBuilderAPI_MakeEdge(a, b).Edge()
        else:
            m = s.mid()
            e = BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a, gp_Pnt(m[0], m[1], z), b).Value()).Edge()
        mk.Add(e)
    if not mk.IsDone():
        raise ValueError("윤곽을 선으로 잇지 못했습니다")
    return mk.Wire()


def plate(part: FlatPart, t: float):
    """윤곽 + 구멍 → 두께 t 평판 솔리드 (z 0 ~ t)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    from OCP.ShapeFix import ShapeFix_Face
    outer = _wire(part.outer)
    mf = BRepBuilderAPI_MakeFace(outer, True)
    for h in part.holes:
        w = _wire(h)
        mf.Add(w)
    face = mf.Face()
    fx = ShapeFix_Face(face)
    fx.FixOrientation()
    fx.Perform()
    face = fx.Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t)).Shape()
