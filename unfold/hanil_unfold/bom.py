"""BOM (부품표): 조립품의 부품을 같은 것끼리 묶어 품번·수량·재질·두께·전개 크기·무게를 낸다.

같은 부품 찾기: 부피·겉넓이·관성 모멘트(돌려도 변하지 않는 값)가 같으면 같은 부품으로 본다.
조립품 안에서 옮기거나 돌려 놓은 같은 부품도 하나로 묶인다.

구분
  판금      정확 전개된 부품
  성형품    곡면이 있어 근사 전개한 부품
  기타      펼칠 수 없거나 두께가 일정하지 않은 부품 (가공품·구매품: 너트·부싱·핀 등)
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from dataclasses import dataclass

import numpy as np

from . import version_text

KINDS = ("판금", "성형품", "기타")


@dataclass
class BomItem:
    no: int                          # 품번 (1부터)
    name: str
    indices: list                    # 조립품 안 부품 번호들 (0부터)
    kind: str
    thickness: float | None = None
    flat_w: float | None = None
    flat_h: float | None = None
    blank_area: float | None = None  # mm² (개당)
    weight: float = 0.0              # kg (개당, 3D 부피 × 밀도)
    bends: int = 0
    note: str = ""
    result: object = None
    solid: object = None
    excluded: bool = False

    @property
    def qty(self):
        return len(self.indices)

    @property
    def total_weight(self):
        return self.weight * self.qty

    @property
    def numbers(self):
        """조립도 번호 (1부터) 를 줄여 쓴 글: 3, 6, 12~15"""
        return compress([i + 1 for i in self.indices])


def compress(nums):
    nums = sorted(nums)
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if j == i else f"{nums[i]}~{nums[j]}")
        i = j + 1
    return ", ".join(out)


def signature(solid, rel=2e-4):
    """돌리고 옮겨도 같은 값: (부피, 겉넓이, 주 관성 모멘트 3개) 를 반올림한 것."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, g)
    vol = abs(g.Mass())
    m = g.MatrixOfInertia()
    M = np.array([[m.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    eig = np.sort(np.abs(np.linalg.eigvalsh(M)))
    gs = GProp_GProps()
    BRepGProp.SurfaceProperties_s(solid, gs)
    area = gs.Mass()

    def q(x, scale):
        step = max(abs(scale) * rel, 1e-9)
        return int(round(x / step))
    return (q(vol, vol), q(area, area)) + tuple(q(e, eig[-1]) for e in eig)


def _kind(part):
    if not part.ok:
        return "기타"
    r = part.result
    if abs(getattr(r, "coverage", 1.0) - 1.0) > 0.15:
        return "기타"
    return "성형품" if r.mode == "forming" else "판금"


def build(model, parts, density=7.85, excluded=()):
    """parts: assembly_calc.compute_all 결과. 품번 순서는 조립품에서 처음 나오는 부품 순서."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    groups = {}
    order = []
    for p in parts:
        solid = model.raw_solids[p.index]
        try:
            key = signature(solid)
        except Exception:
            key = ("?", p.index)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)
    items = []
    for no, key in enumerate(order, 1):
        ps = groups[key]
        first = ps[0]
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(model.raw_solids[first.index], g)
        it = BomItem(no=no, name=first.name, indices=[p.index for p in ps], kind=_kind(first),
                     weight=abs(g.Mass()) * density / 1e6, solid=model.raw_solids[first.index],
                     excluded=all(p.index in excluded for p in ps))
        if first.ok:
            r, m = first.result, first.metrics
            it.result = r
            it.thickness = r.thickness
            it.bends = len(r.bends)
            if it.kind != "기타":
                it.flat_w, it.flat_h, it.blank_area = m.width, m.height, m.blank_area
            else:
                it.note = "판금 아님 (가공·구매품)"
        else:
            it.note = first.error
        names = {p.name for p in ps}
        generic = all(re.fullmatch(r"부품 \d+", n or "") for n in names)
        if len(names) > 1 and not generic:
            it.note = (it.note + " / " if it.note else "") + "이름 다름: " + ", ".join(sorted(names))[:80]
        if it.excluded:
            it.note = ("제외 / " + it.note) if it.note else "제외"
        items.append(it)
    return items


# ---------------------------------------------------------------- 그림

def thumb(item, w=180, h=110):
    """부품 3D 모양 작은 그림 (흰 바탕)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .drawing import LIGHT, paint_model, solid_polylines
    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    try:
        lines = solid_polylines(item.solid, samples=16, iso=False)
    except Exception:
        lines = []
    p = QPainter(img)
    paint_model(p, lines, QRectF(2, 2, w - 4, h - 4), LIGHT, line_width=0.9)
    p.end()
    return img


# ---------------------------------------------------------------- 저장

HEADER = ["품번", "부품명", "모양", "수량", "구분", "재질", "두께 (mm)", "전개 크기 (mm)",
          "블랭크 면적 (m²)", "개당 무게 (kg)", "합계 무게 (kg)", "절곡", "조립도 번호", "비고"]


def _row(it, material):
    size = f"{it.flat_w:.1f} × {it.flat_h:.1f}" if it.flat_w is not None else ""
    return [it.no, it.name, None, it.qty, it.kind, material if it.kind != "기타" else "",
            round(it.thickness, 2) if it.thickness else None, size,
            it.blank_area / 1e6 if it.blank_area is not None else None,
            it.weight, it.total_weight, it.bends or None, it.numbers, it.note]


def save_xlsx(items, path, source_name="", material="", density=7.85):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    from . import company
    from .report import _add_image, _xl_font, _xl_styles

    st = _xl_styles()
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.cell(1, 1, "BOM (부품표)").font = st["title"]
    ws.row_dimensions[1].height = 34
    tmps = [_add_image(ws, company.logo_image(96), "K1", 100)]
    ws.cell(1, 12, company.MAKER).font = _xl_font(st["val"], bold=True)
    ws.cell(1, 12).hyperlink = company.HOMEPAGE
    info = [("도면", source_name), ("만든 때", f"{_dt.datetime.now():%Y-%m-%d %H:%M}"),
            ("재질 · 밀도", f"{material} · {density:g} g/cm³"),
            ("품목 / 전체 수량", f"{len(items)} 품목 / {sum(i.qty for i in items)} 개"),
            ("프로그램", f"한일 판금 전개 {version_text(long=True)}")]
    for i, (k, v) in enumerate(info, 2):
        ws.cell(i, 1, k).font = st["key"]
        ws.cell(i, 2, v).font = st["val"]
    row0 = 2 + len(info) + 1
    widths = [7, 30, 16, 7, 9, 10, 10, 18, 13, 12, 12, 7, 22, 40]
    for j, (hname, wdt) in enumerate(zip(HEADER, widths), 1):
        c = ws.cell(row0, j, hname)
        c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
        ws.column_dimensions[c.column_letter].width = wdt
    fmt = [None, None, None, "0", None, None, "0.0#", None, "0.0000", "0.000", "0.000", "0", None, None]
    tot_qty, tot_w = 0, 0.0
    for k, it in enumerate(items):
        r = row0 + 1 + k
        for j, v in enumerate(_row(it, material), 1):
            c = ws.cell(r, j, v)
            c.font, c.border = st["val"], st["border"]
            c.alignment = Alignment(vertical="center", wrap_text=j in (2, 13, 14))
            if k % 2:
                c.fill = st["zebra"]
            if fmt[j - 1]:
                c.number_format = fmt[j - 1]
            if it.excluded:
                c.font = _xl_font(st["val"], color="999999")
        ws.row_dimensions[r].height = 60
        tmps.append(_add_image(ws, thumb(it), f"C{r}", 112))
        if not it.excluded:
            tot_qty += it.qty
            tot_w += it.total_weight
    r = row0 + 1 + len(items)
    ws.cell(r, 2, "합계 (제외 빼고)").font = _xl_font(st["val"], bold=True)
    ws.cell(r, 4, tot_qty).font = _xl_font(st["val"], bold=True)
    ws.cell(r, 11, round(tot_w, 3)).font = _xl_font(st["val"], bold=True)
    ws.cell(r, 11).number_format = "0.000"
    ws.freeze_panes = ws.cell(row0 + 1, 3)
    ws.print_title_rows = f"{row0}:{row0}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # 두께별 소요량
    wm = wb.create_sheet("두께별 소요량")
    names = ["재질", "두께 (mm)", "수량", "블랭크 면적 합계 (m²)", "블랭크 무게 합계 (kg)"]
    for j, hname in enumerate(names, 1):
        c = wm.cell(1, j, hname)
        c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
        wm.column_dimensions[c.column_letter].width = 22
    rows = {}
    for it in items:
        if it.excluded or it.kind == "기타" or it.blank_area is None:
            continue
        e = rows.setdefault(round(it.thickness, 2), [0, 0.0])
        e[0] += it.qty
        e[1] += it.blank_area * it.qty
    for i, (t, (n, a)) in enumerate(sorted(rows.items()), 2):
        vals = [material, t, n, a / 1e6, a * t * density / 1e6]
        for j, v in enumerate(vals, 1):
            c = wm.cell(i, j, v)
            c.font, c.border = st["val"], st["border"]
            c.number_format = ["@", "0.0#", "0", "0.0000", "0.000"][j - 1]
    wm.cell(len(rows) + 3, 1, "판금·성형품만 (기타·제외 빼고). 블랭크 무게 = 블랭크 면적 × 두께 × 밀도.").font = st["key"]
    wb.save(path)
    for t in tmps:
        try:
            os.remove(t)
        except OSError:
            pass


def save_pdf(items, path, source_name="", material="", density=7.85):
    """A4 가로, 부품 그림이 든 BOM 표 (쪽마다 머리글)."""
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

    from .report import _brand, _font, ensure_gui

    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(f"BOM - {source_name}")
    pdf.setCreator(f"한일 판금 전개 {version_text()}")
    k = 300 / 25.4
    page_w, page_h, margin = 297.0, 210.0, 10.0

    def R(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    p = QPainter(pdf)
    gray = QColor(110, 110, 110)
    cols = [("품번", 10), ("모양", 26), ("부품명", 52), ("수량", 11), ("구분", 14), ("두께", 12),
            ("전개 크기 (mm)", 32), ("블랭크 (m²)", 20), ("개당 kg", 17), ("합계 kg", 17),
            ("조립도 번호", 33), ("비고", 33)]
    row_h, head_h = 15.0, 6.0
    total_qty = sum(i.qty for i in items if not i.excluded)
    total_w = sum(i.total_weight for i in items if not i.excluded)

    def header(page):
        y = margin
        p.setPen(QColor(20, 20, 20))
        p.setFont(_font(15, True))
        p.drawText(R(margin, y, 150, 9), Qt.AlignLeft | Qt.AlignVCenter, f"BOM  {source_name}")
        bw = _brand(p, R(margin, y + 1.5, page_w - 2 * margin, 6)) / k
        p.setFont(_font(7.5))
        p.setPen(gray)
        p.drawText(R(margin, y, page_w - 2 * margin - bw - 4, 9), Qt.AlignRight | Qt.AlignVCenter,
                   f"{len(items)} 품목 · {total_qty} 개 · {total_w:.2f} kg · 재질 {material}  ·  "
                   f"{_dt.datetime.now():%Y-%m-%d}  ·  {page} 쪽")
        p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
        p.drawLine(QPointF(margin * k, (y + 10) * k), QPointF((page_w - margin) * k, (y + 10) * k))
        y += 13
        p.fillRect(R(margin, y, page_w - 2 * margin, head_h), QColor(40, 60, 90))
        p.setPen(QColor(255, 255, 255))
        p.setFont(_font(7.5, True))
        x = margin
        for name, w in cols:
            p.drawText(R(x, y, w, head_h), Qt.AlignCenter, name)
            x += w
        return y + head_h

    page = 1
    y = header(page)
    p.setFont(_font(7.5))
    for n, it in enumerate(items):
        if y + row_h > page_h - margin:
            pdf.newPage()
            page += 1
            y = header(page)
            p.setFont(_font(7.5))
        if n % 2:
            p.fillRect(R(margin, y, page_w - 2 * margin, row_h), QColor(244, 246, 249))
        size = f"{it.flat_w:.1f} × {it.flat_h:.1f}" if it.flat_w is not None else ""
        vals = [str(it.no), None, it.name, str(it.qty), it.kind,
                f"{it.thickness:.2f}" if it.thickness else "", size,
                f"{it.blank_area / 1e6:.4f}" if it.blank_area is not None else "",
                f"{it.weight:.3f}", f"{it.total_weight:.3f}", it.numbers, it.note]
        x = margin
        for (name, w), v in zip(cols, vals):
            if name == "모양":
                img = thumb(it, 260, 150)
                p.drawImage(R(x + 0.5, y + 0.5, w - 1, row_h - 1), img)
            else:
                p.setPen(QColor(150, 150, 150) if it.excluded else QColor(20, 20, 20))
                flags = (Qt.AlignLeft if name in ("부품명", "조립도 번호", "비고") else Qt.AlignHCenter) \
                    | Qt.AlignVCenter | Qt.TextWordWrap
                p.drawText(R(x + 1, y, w - 2, row_h), flags, v)
            x += w
        p.setPen(QPen(QColor(210, 210, 210), 0.15 * k))
        p.drawLine(QPointF(margin * k, (y + row_h) * k), QPointF((page_w - margin) * k, (y + row_h) * k))
        y += row_h
    p.end()
