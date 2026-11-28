"""철판 배치(네스팅): 전개한 부품들을 정해진 크기의 철판(예: 1219 × 2438) 위에 빈틈 적게 늘어놓는다.

방법 (격자 바닥-왼쪽 채우기)
  1. 부품 외곽(구멍은 비움)을 작은 칸(보통 2 mm)으로 칠한 그림으로 만든다. 칸에 조금이라도 걸리면 칠한다.
  2. 철판 그림에는 이미 놓은 부품을 [부품 간격] 만큼 부풀려 칠하고, 가장자리 [여유] 도 칠해 둔다.
  3. 큰 부품부터 하나씩, 허용한 각도마다 "겹치지 않는 자리" 를 FFT 합성곱으로 한꺼번에 구해
     철판 왼쪽(길이 방향 처음)에 가장 가까운, 그다음 아래쪽 자리에 놓는다. 자리가 없으면 새 철판.
  4. 큰 부품의 구멍이 충분히 크면 작은 부품이 그 안에 들어간다.

칸 크기만큼 보수적으로 칠하므로 실제 간격은 설정한 간격보다 같거나 조금 넓다.
두께·재질이 다르면 다른 철판이므로 따로 배치한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import metrics as mt
from .unfolder import Arc, Line, Polyline

# 자주 쓰는 철판 (mm). "4×8" 은 4 피트 × 8 피트.
STANDARD_SHEETS = [
    ("4×8  1219 × 2438", 1219, 2438),
    ("4×10  1219 × 3048", 1219, 3048),
    ("5×10  1524 × 3048", 1524, 3048),
    ("3×6  914 × 1829", 914, 1829),
    ("5×20  1524 × 6096", 1524, 6096),
    ("1000 × 2000", 1000, 2000),
    ("1250 × 2500", 1250, 2500),
    ("1500 × 3000", 1500, 3000),
]

ROTATIONS = {
    "45": tuple(range(0, 360, 45)),  # 45° 씩 (느리지만 비스듬한 부품이 잘 들어간다)
    "free": (0, 90, 180, 270),       # 90° 씩
    "grain": (0, 180),               # 결 방향 유지 (뒤집기만)
    "none": (0,),
}
ROTATION_NAMES = {"free": "90° 씩 돌리기", "45": "45° 씩 돌리기 (느림)", "grain": "결 방향 유지 (180° 만)", "none": "돌리지 않음"}


def parse_size(text: str):
    """'1219*2438', '1219x2438', '1219 × 2438' → (1219.0, 2438.0). 못 읽으면 None."""
    import re
    nums = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
    if len(nums) < 2:
        return None
    a, b = float(nums[-2]), float(nums[-1])
    if "×" in text and len(nums) >= 4:        # "4×8  1219 × 2438"
        a, b = float(nums[2]), float(nums[3])
    return (a, b) if a > 0 and b > 0 else None


# ---------------------------------------------------------------- 도형 옮기기

def _rot(p, c, s):
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def transform_entities(entities, angle_deg, dx, dy):
    """원점 둘레로 angle_deg 돌린 뒤 (dx, dy) 만큼 옮긴 새 도형 목록."""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)

    def t(p):
        q = _rot(p, c, s)
        return (q[0] + dx, q[1] + dy)

    out = []
    for e in entities:
        if isinstance(e, Line):
            out.append(Line(t(e.p1), t(e.p2), e.layer))
        elif isinstance(e, Polyline):
            out.append(Polyline([t(p) for p in e.points], e.layer))
        elif isinstance(e, Arc):
            out.append(Arc(t(e.center), e.radius, (e.start_deg + angle_deg) % 360,
                           (e.end_deg + angle_deg) % 360, e.full, e.layer))
    return out


# ---------------------------------------------------------------- 자료

@dataclass
class NestPart:
    """배치할 부품 하나 (수량 qty 개).

    cut 은 절단선을 점 목록들로 (외곽이 끊기거나 T 자로 만나도 배치에 쓸 수 있게 선 그대로),
    holes 는 그 안의 닫힌 구멍들, outer 는 닫힌 외곽 (끊긴 도면이면 None)."""
    name: str
    entities: list
    qty: int = 1
    thickness: float = 0.0
    material: str = ""
    number: int = 0                 # 화면·조립도의 부품 번호 (1부터, 0 이면 없음)
    cut: list = field(default_factory=list)
    holes: list = field(default_factory=list)
    outer: list | None = None
    area: float = 0.0               # 블랭크 넓이 (구멍 뺌)

    @classmethod
    def from_result(cls, name, result, qty=1, material="", number=0):
        cut = [mt._points(e) for e in result.entities if e.layer == "CUT"]
        if not cut:
            raise ValueError(f"{name}: 절단선이 없습니다")
        P = np.vstack([np.asarray(c, float) for c in cut])
        x0, y0 = P.min(0)
        x1, y1 = P.max(0)
        span = max(x1 - x0, y1 - y0)
        lps = sorted(mt.loops(result.entities), key=mt.polygon_area, reverse=True)
        outer = None
        if lps:
            b = np.asarray(lps[0])
            if (b[:, 0].min() - x0 + x1 - b[:, 0].max() + b[:, 1].min() - y0 + y1 - b[:, 1].max()
                    < 1e-3 * span + 1e-6):
                outer = lps[0]          # 가장 큰 닫힌 윤곽이 전체를 감싸면 그것이 외곽
        tol = 1e-3 * span + 1e-6
        holes = []
        for lp in lps:
            if lp is outer:
                continue
            b = np.asarray(lp)
            inside = (b[:, 0].min() > x0 + tol and b[:, 0].max() < x1 - tol
                      and b[:, 1].min() > y0 + tol and b[:, 1].max() < y1 - tol)
            if inside:
                holes.append(lp)
        part = cls(name, list(result.entities), qty, result.thickness, material, number,
                   cut, holes, outer)
        if outer is not None:
            part.area = mt.polygon_area(outer) - sum(mt.polygon_area(h) for h in holes)
        else:   # 외곽이 끊긴 도면: 0.5 mm 격자로 센다
            m, _ = _rasterize(part, 0, 0.5, conservative=False)
            part.area = float(m.sum()) * 0.25
        return part

    @property
    def label(self):
        return str(self.number) if self.number else self.name


@dataclass
class Placement:
    part: int            # parts 목록 번호
    angle: int           # 돌린 각도
    dx: float            # 돌린 뒤 옮긴 거리
    dy: float
    copy: int = 0        # 같은 부품 중 몇 번째 (0부터)

    def entities(self, parts):
        return transform_entities(parts[self.part].entities, self.angle, self.dx, self.dy)

    def center(self, parts):
        pts = np.vstack([np.asarray(c, float) for c in parts[self.part].cut])
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        x = pts[:, 0] * c - pts[:, 1] * s + self.dx
        y = pts[:, 0] * s + pts[:, 1] * c + self.dy
        return ((x.min() + x.max()) / 2, (y.min() + y.max()) / 2)


@dataclass
class Sheet:
    width: float          # 가로 (긴 쪽)
    height: float         # 세로
    placements: list = field(default_factory=list)
    used_area: float = 0.0
    used_length: float = 0.0     # 왼쪽 끝에서 가장 먼 부품까지 (남은 철판을 잘라 쓸 때)

    @property
    def utilization(self):
        return self.used_area / (self.width * self.height) if self.width * self.height else 0.0


@dataclass
class NestResult:
    parts: list
    sheets: list
    sheet_w: float
    sheet_h: float
    gap: float
    margin: float
    thickness: float = 0.0
    material: str = ""
    unplaced: list = field(default_factory=list)    # (부품 번호, 개수, 이유)
    resolution: float = 2.0

    @property
    def placed_count(self):
        return sum(len(s.placements) for s in self.sheets)

    @property
    def total_qty(self):
        return sum(p.qty for p in self.parts)

    @property
    def utilization(self):
        a = sum(s.width * s.height for s in self.sheets)
        return sum(s.used_area for s in self.sheets) / a if a else 0.0

    def sheet_weight_kg(self, density_g_cm3):
        """철판 한 장 무게."""
        return self.sheet_w * self.sheet_h * self.thickness / 1e6 * density_g_cm3

    def summary_lines(self, density=None):
        lines = [f"철판 {self.sheet_h:g} × {self.sheet_w:g}  t{self.thickness:g}"
                 + (f"  {self.material}" if self.material else ""),
                 f"필요 철판 {len(self.sheets)}장 · 부품 {self.placed_count} / {self.total_qty}개 배치",
                 f"전체 사용률 {self.utilization * 100:.1f}%"
                 + ("  (장마다 " + ", ".join(f"{s.utilization * 100:.0f}%" for s in self.sheets) + ")"
                    if self.sheets else "")]
        if self.sheets:
            last = self.sheets[-1]
            lines.append(f"마지막 장 사용 길이 {last.used_length:.0f} mm "
                         f"(남는 철판 {last.height:g} × {max(0.0, last.width - last.used_length):.0f})")
        if density:
            w = self.sheet_weight_kg(density)
            used = sum(s.used_area for s in self.sheets) * self.thickness / 1e6 * density
            lines.append(f"철판 무게 {w * len(self.sheets):.1f} kg (장당 {w:.1f}) · 부품 {used:.1f} kg · "
                         f"자투리 {w * len(self.sheets) - used:.1f} kg")
        lines.append(f"간격 {self.gap:g} mm · 가장자리 여유 {self.margin:g} mm · 격자 {self.resolution:g} mm")
        for i, n, why in self.unplaced:
            lines.append(f"못 놓음: {self.parts[i].label} {self.parts[i].name} × {n} — {why}")
        return lines


# ---------------------------------------------------------------- 격자 그림

def _rasterize(part, angle, res, conservative=True):
    """부품을 angle 돌려 res 칸으로 칠한 그림 → (bool[h, w], 그림 (0,0) 칸의 왼쪽 아래 좌표).

    절단선을 모두 선으로 긋고 바깥에서부터 물을 채우듯 칠해, 안 닿는 곳을 부품으로 본다.
    (외곽이 T 자로 만나거나 칸보다 작게 끊겨도 된다.) 그다음 닫힌 구멍을 비운다."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    cut = [_rot_poly(c, angle) for c in part.cut]
    P = np.vstack(cut)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    pad = 2
    ox, oy = x0 - pad * res, y0 - pad * res
    w = int(math.ceil((x1 - ox) / res)) + pad + 1
    h = int(math.ceil((y1 - oy) / res)) + pad + 1

    def px(poly):
        q = (np.asarray(poly, float) - (ox, oy)) / res
        return [tuple(v) for v in q]

    img = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(img)
    for c in cut:
        d.line(px(c), fill=1, width=1)
    lines = np.array(img, dtype=bool)
    walls = ndimage.binary_dilation(lines, structure=np.ones((3, 3), bool))   # 칸보다 작은 틈 막기
    lab, _ = ndimage.label(~walls)
    outside = lab == lab[0, 0]
    m = ~outside
    if not conservative:
        m &= ~ndimage.binary_dilation(outside, structure=np.ones((3, 3), bool)) | lines
    if part.holes:
        img = Image.new("1", (w, h), 0)
        d = ImageDraw.Draw(img)
        for hole in part.holes:
            d.polygon(px(_rot_poly(hole, angle)), fill=1, outline=1)
        hole = np.array(img, dtype=bool)
        # 구멍 테두리 칸은 부품 쪽으로 (보수적으로)
        hole &= ~ndimage.binary_dilation(lines, structure=np.ones((3, 3), bool) if conservative else None)
        m &= ~hole
    return m, (ox, oy)


def _disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r + r


def _dilate(m, r):
    """r 칸 부풀린 그림. 사방으로 r 칸씩 커진다 (모양 (h+2r, w+2r))."""
    if r <= 0:
        return m
    from scipy.ndimage import binary_dilation
    return binary_dilation(np.pad(m, r), structure=_disk(r))


def _rot_poly(poly, angle):
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    p = np.asarray(poly, float)
    return np.c_[p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c]


class _Shape:
    """부품 하나·각도 하나의 격자 그림 (부풀린 것 포함)."""

    def __init__(self, part, angle, res, gap_cells):
        self.mask, self.origin = _rasterize(part, angle, res)
        self.xmax = max(float(_rot_poly(c, angle)[:, 0].max()) for c in part.cut)
        # 철판에 남길 자국: 간격만큼 부풀림 (그림이 gap_cells 만큼 커진다)
        self.stamp = _dilate(self.mask, gap_cells)
        self.g = gap_cells
        self.angle = angle


class _FFT:
    """같은 크기의 FFT 로 철판·부품 그림의 스펙트럼을 한 번씩만 구해 두고 곱해서 겹침을 센다."""

    def __init__(self, GH, GW, hmax, wmax):
        from scipy.fft import next_fast_len
        self.GH, self.GW = GH, GW
        self.P = (next_fast_len(GH + hmax), next_fast_len(GW + wmax, real=True))
        self.spec = {}

    def mask_spec(self, key, mask):
        if key not in self.spec:
            from scipy.fft import rfft2
            self.spec[key] = rfft2(mask[::-1, ::-1].astype(np.float32), s=self.P, workers=-1)
        return self.spec[key]

    def free(self, occ_spec, mask, key):
        """mask 를 겹치지 않게 놓을 수 있는 왼쪽 아래 칸들 (bool[GH-h+1, GW-w+1]) 또는 None."""
        from scipy.fft import irfft2
        h, w = mask.shape
        if h > self.GH or w > self.GW:
            return None
        full = irfft2(occ_spec * self.mask_spec(key, mask), s=self.P, workers=-1)
        return full[h - 1:self.GH, w - 1:self.GW] < 0.5

    def occ_spec(self, occ):
        from scipy.fft import rfft2
        return rfft2(occ.astype(np.float32), s=self.P, workers=-1)


def _best(free):
    """왼쪽(가로 칸) 먼저, 그다음 아래쪽."""
    cols = np.flatnonzero(free.any(axis=0))
    if not len(cols):
        return None
    j = int(cols[0])
    i = int(np.flatnonzero(free[:, j])[0])
    return i, j


# ---------------------------------------------------------------- 배치

def _extent(p):
    P = np.vstack([np.asarray(c, float) for c in p.cut])
    return np.ptp(P, axis=0)


ORDERS = {
    "area": lambda p: -p.area,                     # 넓은 것부터
    "long": lambda p: -max(_extent(p)),            # 긴 변이 긴 것부터
    "short": lambda p: -min(_extent(p)),           # 짧은 변이 긴 것부터
}


def _score(r):
    """적은 철판, 그다음 마지막 장을 짧게 쓴 것이 좋다. 못 놓은 것은 크게 나쁘다."""
    left = sum(n for _, n, _ in r.unplaced)
    last = r.sheets[-1].used_length if r.sheets else 0.0
    return (left, len(r.sheets), last)


def nest(parts, sheet_w, sheet_h, gap=5.0, margin=10.0, rotations="free", resolution=None,
         max_sheets=200, progress=None, thickness=None, material="", tries=1):
    """parts: NestPart 목록. 철판은 긴 쪽을 가로로 놓는다.

    tries 가 2 이상이면 놓는 순서를 바꿔 여러 번 해 보고 가장 좋은 것을 고른다.
    progress(놓은 개수, 전체 개수) 가 False 를 돌려주면 멈춘다."""
    keys = list(ORDERS)[:max(1, int(tries))]
    best = None
    shapes = {}
    total = sum(max(0, int(p.qty)) for p in parts) * len(keys)
    for n, key in enumerate(keys):
        def prog(done, _total, base=n * (total // len(keys))):
            return progress(base + done, total) if progress is not None else None
        r = _nest_once(parts, sheet_w, sheet_h, gap, margin, rotations, resolution, max_sheets,
                       prog, thickness, material, ORDERS[key], shapes)
        if r is None:
            break
        if best is None or _score(r) < _score(best):
            best = r
    return best


def _nest_once(parts, sheet_w, sheet_h, gap, margin, rotations, resolution, max_sheets, progress,
               thickness, material, order_key, shapes):
    W, H = max(sheet_w, sheet_h), min(sheet_w, sheet_h)
    if resolution is None:
        # 철판 긴 쪽이 1200~1600 칸 쯤 되게 (4×8 이면 2 mm)
        resolution = max(1.0, min(5.0, round(W / 1200.0 * 2) / 2))
    res = float(resolution)
    angles = ROTATIONS.get(rotations, rotations) if isinstance(rotations, str) else tuple(rotations)
    gcell = int(math.ceil(gap / res))
    mcell = int(math.ceil(margin / res))
    GW, GH = int(math.floor(W / res)), int(math.floor(H / res))
    result = NestResult(parts, [], W, H, gap, margin,
                        thickness if thickness is not None else (parts[0].thickness if parts else 0.0),
                        material, resolution=res)

    def shape(pi, a):
        k = (id(parts[pi]), a, res, gcell)
        if k not in shapes:
            shapes[k] = _Shape(parts[pi], a, res, gcell)
        return shapes[k]

    def blank_sheet():
        occ = np.zeros((GH, GW), dtype=bool)
        if mcell:
            occ[:mcell, :] = occ[-mcell:, :] = True
            occ[:, :mcell] = occ[:, -mcell:] = True
        return occ

    order = sorted(range(len(parts)), key=lambda i: order_key(parts[i]))
    queue = [(i, c) for i in order for c in range(max(0, int(parts[i].qty)))]
    total = len(queue)
    used = sorted({pi for pi, _ in queue})
    allshapes = [shape(pi, a) for pi in used for a in angles]
    fft = _FFT(GH, GW, max((x.mask.shape[0] for x in allshapes), default=1),
               max((x.mask.shape[1] for x in allshapes), default=1))
    blank = blank_sheet()
    blank_spec = fft.occ_spec(blank)
    occs, specs = [], []
    no_room = set()          # (철판, 부품): 한 번 안 들어가면 그 철판엔 다시 안 들어간다 (채우기만 하므로)
    failed = {}
    done = 0
    for pi, copy in queue:
        if progress is not None and progress(done, total) is False:
            return None
        done += 1
        placed = False
        fits_empty = False
        need = int(shape(pi, angles[0]).mask.sum())
        for si in range(len(occs) + 1):
            new = si == len(occs)
            if new:
                if len(occs) >= max_sheets:
                    break
                occ, spec = blank.copy(), blank_spec
            else:
                if (si, pi) in no_room:
                    continue
                occ = occs[si]
                if occ.size - occ.sum() < need:
                    no_room.add((si, pi))
                    continue
                if specs[si] is None:
                    specs[si] = fft.occ_spec(occ)
                spec = specs[si]
            best = None
            for a in angles:
                sh = shape(pi, a)
                free = fft.free(spec, sh.mask, (id(parts[pi]), a))
                if free is None:
                    continue
                pos = _best(free)
                if pos is None:
                    continue
                key = (pos[1], pos[0])
                if best is None or key < best[0]:
                    best = (key, pos, sh)
            if best is None:
                if new:
                    break           # 빈 철판에도 안 들어간다
                no_room.add((si, pi))
                continue
            fits_empty = True
            (_, (i, j), sh) = best
            if new:
                occs.append(occ)
                specs.append(None)
                result.sheets.append(Sheet(W, H))
            # 자국 남기기 (부풀린 그림은 g 칸씩 더 크다)
            g = sh.g
            i0, j0 = i - g, j - g
            st = sh.stamp
            a0, b0 = max(0, -i0), max(0, -j0)
            a1 = min(st.shape[0], GH - i0)
            b1 = min(st.shape[1], GW - j0)
            occ[i0 + a0:i0 + a1, j0 + b0:j0 + b1] |= st[a0:a1, b0:b1]
            specs[si] = None
            # 칸 (i, j) 의 왼쪽 아래 = 철판 좌표 (j·res, i·res) ← 그림 원점 sh.origin
            dx = j * res - sh.origin[0]
            dy = i * res - sh.origin[1]
            s = result.sheets[si]
            s.placements.append(Placement(pi, sh.angle, dx, dy, copy))
            s.used_area += parts[pi].area
            s.used_length = max(s.used_length, dx + sh.xmax)
            placed = True
            break
        if not placed:
            why = "철판보다 큽니다" if not fits_empty else f"철판 {max_sheets}장을 넘습니다"
            failed[pi] = (failed.get(pi, (0, why))[0] + 1, why)
    result.unplaced = [(pi, n, why) for pi, (n, why) in failed.items()]
    return result


def nest_by_thickness(parts, sheet_w, sheet_h, **kw):
    """두께(와 재질)가 같은 것끼리 따로 배치. NestResult 목록 (얇은 것부터)."""
    groups = {}
    for p in parts:
        groups.setdefault((round(p.thickness, 2), p.material), []).append(p)
    out = []
    for (t, m), ps in sorted(groups.items()):
        out.append(nest(ps, sheet_w, sheet_h, thickness=t, material=m, **kw))
    return out


# ---------------------------------------------------------------- 저장

def save_dxf(results, path, notes=True):
    """철판마다 나란히 (위아래로 간격을 두고) 그린다.

    레이어: SHEET 철판 테두리, CUT·BEND 부품, NOTE 부품 번호·철판 설명."""
    import ezdxf
    from ezdxf import units

    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    for name, attrs in {"SHEET": dict(color=1), "CUT": dict(color=7),
                        "BEND": dict(color=2, linetype="DASHED"), "NOTE": dict(color=3)}.items():
        doc.layers.add(name, **attrs)
    msp = doc.modelspace()
    y = 0.0
    for r in results:
        for k, s in enumerate(r.sheets):
            msp.add_lwpolyline([(0, y), (s.width, y), (s.width, y + s.height), (0, y + s.height)],
                               close=True, dxfattribs={"layer": "SHEET"})
            if notes:
                msp.add_text(f"SHEET {k + 1}/{len(r.sheets)}  {r.sheet_w:g}x{r.sheet_h:g}  T{r.thickness:g}"
                             f"  USE {s.utilization * 100:.1f}%",
                             height=max(8.0, r.sheet_h / 60),
                             dxfattribs={"layer": "NOTE"}).set_placement((0, y + s.height + 8))
            for pl in s.placements:
                for e in pl.entities(r.parts):
                    at = {"layer": e.layer}
                    if isinstance(e, Line):
                        msp.add_line((e.p1[0], e.p1[1] + y), (e.p2[0], e.p2[1] + y), dxfattribs=at)
                    elif isinstance(e, Arc):
                        c = (e.center[0], e.center[1] + y)
                        if e.full:
                            msp.add_circle(c, e.radius, dxfattribs=at)
                        else:
                            msp.add_arc(c, e.radius, e.start_deg, e.end_deg, dxfattribs=at)
                    elif isinstance(e, Polyline):
                        msp.add_lwpolyline([(p[0], p[1] + y) for p in e.points], dxfattribs=at)
                if notes:
                    cx, cy = pl.center(r.parts)
                    from ezdxf.enums import TextEntityAlignment
                    msp.add_text(r.parts[pl.part].label, height=max(6.0, r.sheet_h / 120),
                                 dxfattribs={"layer": "NOTE"}).set_placement(
                        (cx, cy + y), align=TextEntityAlignment.MIDDLE_CENTER)
            y += s.height + max(100.0, r.sheet_h * 0.15)
    doc.saveas(path)
