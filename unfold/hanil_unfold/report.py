"""전개 결과 보고서 — PDF 와 엑셀.

PDF  : A4 한 장(절곡이 많으면 두 장). 부품 정보, 재료·무게·절단 길이, 치수가 들어간 전개도,
       3D 그림, 절곡 표(연신·근거), 성형품이면 두께 변화 색 지도, 주의 사항.
엑셀 : [보고서] 시트(같은 정보 + 그림), [절곡표] 시트, 성형품이면 [두께 변화] 시트.
여러 파일을 한꺼번에 처리하면 [부품 목록] 엑셀도 만든다 (견적용).
"""
from __future__ import annotations

import datetime as _dt
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field

import numpy as np

from . import __version__
from . import bendcalc as bc
from . import metrics as mt


@dataclass
class ReportData:
    part_name: str
    source_path: str
    result: object
    settings: bc.BendSettings
    solid: object = None
    solid_index: int = 1
    solid_count: int = 1
    created: _dt.datetime = field(default_factory=_dt.datetime.now)

    @property
    def material(self) -> bc.Material:
        return self.settings.mat

    @property
    def metrics(self) -> mt.Metrics:
        if not hasattr(self, "_m"):
            self._m = mt.compute(self.result, self.material.density)
        return self._m

    @property
    def title(self):
        return "성형품 블랭크 전개 보고서" if self.result.mode == "forming" else "판금 전개 보고서"

    @property
    def display_name(self):
        if self.solid_count > 1:
            return f"{self.part_name} ({self.solid_index}/{self.solid_count})"
        return self.part_name


# ---------------------------------------------------------------- 표에 들어갈 값

def summary_rows(d: ReportData):
    r, m = d.result, d.metrics
    rows = [
        ("파일", os.path.basename(d.source_path)),
        ("부품", d.display_name),
        ("전개 방식", "성형품 근사 전개 (곡면)" if r.mode == "forming" else "판금 정확 전개"),
        ("재질", f"{d.material.code}  {d.material.name}"),
        ("두께", f"{r.thickness:.3f} mm"),
    ]
    if r.mode != "forming":
        rows.append(("계산 조건", r.settings_text))
    rows += [
        ("전개 크기 (가로 × 세로)", f"{m.width:.2f} × {m.height:.2f} mm"),
        ("블랭크 넓이", f"{m.blank_area:,.1f} mm²  ({m.blank_area / 1e6:.4f} m²)"),
        ("사각 원판 넓이", f"{m.rect_area:,.1f} mm²   수율 {m.yield_ratio:.1%}"),
        ("블랭크 무게", f"{m.weight_kg:.3f} kg   (사각 원판 {m.rect_weight_kg:.3f} kg, "
                     f"비중 {d.material.density:g})"),
        ("절단 길이", f"{m.cut_length:,.1f} mm   (피어싱 {m.pierce}곳, 구멍 {m.holes}개)"),
    ]
    if r.mode == "forming":
        fi = r.forming
        th = fi.thinning
        rows += [
            ("제품 면적 (두께 가운데)", f"{fi.product_area:,.1f} mm²"),
            ("블랭크 / 제품 면적", f"{fi.blank_area / fi.product_area:.3f}"),
            ("최대 얇아짐", f"{max(th.max(), 0):.1%}  (두께 약 {r.thickness * (1 - max(th.max(), 0)):.2f} mm)"),
            ("최대 두꺼워짐", f"{max(-th.min(), 0):.1%}"),
        ]
    else:
        rows.append(("절곡 수", f"{len(r.bends)}곳"))
    for txt in r.rolled:
        rows.append(("말기", txt))
    return rows


BEND_HEADER = ["번호", "방향", "각도(°)", "모델 R", "실제 R", "K", "연신", "90° 연신",
               "펼친 길이", "절곡선 길이", "근거"]


def _f(x, n=3):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{n}f}"


def bend_rows(d: ReportData):
    return [[f"B{b.number}", "UP" if b.direction == "UP" else "DOWN", f"{b.angle_deg:.2f}",
             f"{b.model_radius:.2f}", b.radius_text, f"{b.k:.3f}", _f(b.deduction), _f(b.deduction90),
             f"{b.allowance:.3f}", f"{b.length:.2f}", b.source] for b in d.result.bends]


def notes(d: ReportData):
    out = list(d.result.warnings)
    if d.result.mode == "forming":
        out.append("두께 변화는 블랭크→제품 면적 비로 어림한 값입니다 (체적 일정). "
                   "실제 성형성은 성형 해석으로 확인하세요.")
    else:
        out.append("연신 = 2·tan(θ/2)·(R+t) − θ·(R+K·t).  문헌값은 출발점이므로 시험 절곡으로 확인하세요.")
    out.append("방향 UP/DOWN 은 전개도를 앞에서 본 기준입니다.")
    return out


# ---------------------------------------------------------------- Qt 준비

def ensure_gui():
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        ensure_gui.app = QGuiApplication([])
    return QGuiApplication.instance()


def _font(size_pt, bold=False):
    from PySide6.QtGui import QFont
    f = QFont()
    f.setFamilies(["Malgun Gothic", "맑은 고딕", "Noto Sans CJK KR", "NanumGothic", "Sans Serif"])
    f.setPointSizeF(size_pt)
    f.setBold(bold)
    return f


def render_flat_image(d: ReportData, w=1600, h=1000, dims=True):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from .drawing import LIGHT, FlatTransform, paint_dimensions, paint_flat, paint_legend

    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(LIGHT.bg)
    p = QPainter(img)
    p.setFont(_font(14))
    legend_h = 70 if d.result.forming is not None else 0
    rect = QRectF(20, 20, w - 110, h - 90 - legend_h)
    tf = FlatTransform.fit(d.result, rect)
    paint_flat(p, d.result, tf, LIGHT, line_scale=2.0)
    if dims:
        paint_dimensions(p, d.result, tf, LIGHT)
    if legend_h:
        paint_legend(p, QRectF(w * 0.25, h - legend_h - 10, w * 0.5, 22), LIGHT)
    p.end()
    return img


def render_model_image(d: ReportData, w=900, h=700):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from .drawing import LIGHT, paint_model, solid_polylines

    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(LIGHT.bg)
    if d.solid is not None:
        p = QPainter(img)
        paint_model(p, solid_polylines(d.solid), QRectF(10, 10, w - 20, h - 20), LIGHT, line_width=2.0)
        p.end()
    return img


# ---------------------------------------------------------------- PDF

def save_pdf(d: ReportData, path: str):
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

    from .drawing import LIGHT, FlatTransform, paint_dimensions, paint_flat, paint_legend

    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(f"{d.title} - {d.display_name}")
    pdf.setCreator(f"한일 판금 전개 {__version__}")

    k = 300 / 25.4                      # mm → 점

    def R(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    p = QPainter(pdf)
    page_w, page_h, margin = 210.0, 297.0, 12.0
    inner_w = page_w - 2 * margin
    gray = QColor(110, 110, 110)
    line = QColor(180, 180, 180)

    def header(y):
        p.setPen(QColor(20, 20, 20))
        p.setFont(_font(16, True))
        p.drawText(R(margin, y, inner_w, 9), Qt.AlignLeft | Qt.AlignVCenter, d.title)
        p.setFont(_font(8))
        p.setPen(gray)
        p.drawText(R(margin, y, inner_w, 9), Qt.AlignRight | Qt.AlignVCenter,
                   f"한일  ·  {d.created:%Y-%m-%d %H:%M}  ·  한일 판금 전개 {__version__}")
        p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
        p.drawLine(QPointF(margin * k, (y + 10) * k), QPointF((page_w - margin) * k, (y + 10) * k))
        return y + 13

    y = header(margin)

    # 요약 표
    rows = summary_rows(d)
    p.setFont(_font(8.5))
    row_h = 5.4
    key_w = 42.0
    for i, (key, val) in enumerate(rows):
        ry = y + i * row_h
        if i % 2 == 0:
            p.fillRect(R(margin, ry, inner_w, row_h), QColor(244, 246, 249))
        p.setPen(gray)
        p.drawText(R(margin + 2, ry, key_w, row_h), Qt.AlignLeft | Qt.AlignVCenter, key)
        p.setPen(QColor(20, 20, 20))
        p.drawText(R(margin + key_w, ry, inner_w - key_w - 2, row_h), Qt.AlignLeft | Qt.AlignVCenter, val)
    y += len(rows) * row_h + 4

    # 전개도 + 3D
    bends = bend_rows(d)
    table_h = 7 + 5 * min(len(bends), 12) if bends else 0
    note_list = notes(d)
    notes_h = 4 + 4.2 * len(note_list)
    avail = page_h - margin - y - table_h - notes_h - 6
    draw_h = max(70.0, min(avail, 130.0))
    flat_w = inner_w * 0.68
    box = R(margin, y, flat_w, draw_h)
    p.setPen(QPen(line, 0.2 * k))
    p.drawRect(box)
    p.setFont(_font(7))
    legend_h = 9 if d.result.forming is not None else 0
    inner = R(margin + 3, y + 5, flat_w - 14, draw_h - 13 - legend_h)
    tf = FlatTransform.fit(d.result, inner, margin=0.92)
    paint_flat(p, d.result, tf, LIGHT, line_scale=0.25 * k)
    paint_dimensions(p, d.result, tf, LIGHT)
    if legend_h:
        paint_legend(p, R(margin + flat_w * 0.2, y + draw_h - legend_h - 2, flat_w * 0.6, 3), LIGHT)
    p.setPen(gray)
    p.drawText(R(margin + 2, y + 0.5, flat_w, 4), Qt.AlignLeft, "전개도 (mm)")

    mx = margin + flat_w + 3
    mw = inner_w - flat_w - 3
    p.setPen(QPen(line, 0.2 * k))
    p.drawRect(R(mx, y, mw, draw_h))
    if d.solid is not None:
        from .drawing import paint_model, solid_polylines
        paint_model(p, solid_polylines(d.solid), R(mx + 2, y + 6, mw - 4, draw_h - 8), LIGHT,
                    line_width=0.2 * k)
    p.setPen(gray)
    p.drawText(R(mx + 2, y + 0.5, mw, 4), Qt.AlignLeft, "3D 형상")
    y += draw_h + 5

    # 절곡 표
    if bends:
        y = _bend_table(p, R, bends, y, margin, inner_w, page_h, header)

    # 주의 사항
    p.setFont(_font(7.5))
    if y + notes_h > page_h - margin:
        pdf.newPage()
        y = header(margin)
    p.setPen(QColor(20, 20, 20))
    p.drawText(R(margin, y, inner_w, 4), Qt.AlignLeft, "참고")
    y += 4.5
    p.setPen(gray)
    for n in note_list:
        p.drawText(R(margin + 2, y, inner_w - 2, 4.2), Qt.AlignLeft | Qt.TextWordWrap, "· " + n)
        y += 4.2
    p.end()


def _bend_table(p, R, bends, y, margin, inner_w, page_h, header):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor

    widths = [9, 11, 12, 11, 15, 11, 12, 13, 14, 15]
    widths.append(inner_w - sum(widths))
    row_h = 5.0

    def head(yy):
        p.fillRect(R(margin, yy, inner_w, row_h + 1), QColor(40, 60, 90))
        p.setPen(QColor(255, 255, 255))
        p.setFont(_font(7, True))
        x = margin
        for h, w in zip(BEND_HEADER, widths):
            p.drawText(R(x, yy, w, row_h + 1), Qt.AlignCenter, h)
            x += w
        return yy + row_h + 1

    y = head(y)
    p.setFont(_font(7))
    for i, row in enumerate(bends):
        if y + row_h > page_h - 14:
            p.device().newPage()
            y = head(header(12))
            p.setFont(_font(7))
        if i % 2:
            p.fillRect(R(margin, y, inner_w, row_h), QColor(244, 246, 249))
        p.setPen(QColor(20, 20, 20))
        x = margin
        for j, (v, w) in enumerate(zip(row, widths)):
            align = Qt.AlignLeft | Qt.AlignVCenter if j == len(row) - 1 else Qt.AlignCenter
            p.drawText(R(x + (1 if j == len(row) - 1 else 0), y, w, row_h), align, v)
            x += w
        y += row_h
    return y + 4


# ---------------------------------------------------------------- 엑셀

def _xl_styles():
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    thin = Side(style="thin", color="BBBBBB")
    return {
        "title": Font(name="맑은 고딕", size=16, bold=True),
        "head": Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF"),
        "head_fill": PatternFill("solid", fgColor="28405A"),
        "key": Font(name="맑은 고딕", size=10, color="555555"),
        "val": Font(name="맑은 고딕", size=10),
        "zebra": PatternFill("solid", fgColor="F4F6F9"),
        "border": Border(left=thin, right=thin, top=thin, bottom=thin),
        "center": Alignment(horizontal="center", vertical="center"),
        "left": Alignment(horizontal="left"),
        "wrap": Alignment(wrap_text=True, vertical="top"),
    }


def _add_image(ws, qimage, anchor, width_px):
    from openpyxl.drawing.image import Image as XLImage

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    qimage.save(tmp, "PNG")
    img = XLImage(tmp)
    ratio = width_px / img.width
    img.width, img.height = int(img.width * ratio), int(img.height * ratio)
    ws.add_image(img, anchor)
    return tmp


def save_xlsx(d: ReportData, path: str):
    from openpyxl import Workbook

    st = _xl_styles()
    wb = Workbook()
    ws = wb.active
    ws.title = "보고서"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 70
    ws["A1"] = d.title
    ws["A1"].font = st["title"]
    ws["A2"] = f"한일  ·  {d.created:%Y-%m-%d %H:%M}  ·  한일 판금 전개 {__version__}"
    ws["A2"].font = st["key"]
    r = 4
    for i, (k, v) in enumerate(summary_rows(d)):
        ws.cell(r, 1, k).font = st["key"]
        ws.cell(r, 2, v).font = st["val"]
        if i % 2 == 0:
            ws.cell(r, 1).fill = st["zebra"]
            ws.cell(r, 2).fill = st["zebra"]
        r += 1

    # 숫자로도 넣어 둔다 (계산·견적에 바로 쓰게)
    m = d.metrics
    r += 1
    ws.cell(r, 1, "숫자 값").font = st["val"]
    r += 1
    for k, v, unit in [("가로", m.width, "mm"), ("세로", m.height, "mm"), ("두께", d.result.thickness, "mm"),
                       ("블랭크 넓이", m.blank_area, "mm²"), ("사각 원판 넓이", m.rect_area, "mm²"),
                       ("수율", m.yield_ratio, ""), ("블랭크 무게", m.weight_kg, "kg"),
                       ("사각 원판 무게", m.rect_weight_kg, "kg"), ("절단 길이", m.cut_length, "mm"),
                       ("피어싱 수", m.pierce, "곳"), ("절곡 수", len(d.result.bends), "곳")]:
        ws.cell(r, 1, f"{k} ({unit})" if unit else k).font = st["key"]
        c = ws.cell(r, 2, round(float(v), 4))
        c.font = st["val"]
        c.number_format = "0.0%" if k == "수율" else "#,##0.000"
        c.alignment = st["left"]
        r += 1

    r += 1
    ws.cell(r, 1, "참고").font = st["val"]
    for n in notes(d):
        r += 1
        ws.cell(r, 2, n).alignment = st["wrap"]
        ws.cell(r, 2).font = st["key"]

    tmps = [
        _add_image(ws, render_flat_image(d), "D1", 760),
        _add_image(ws, render_model_image(d), "D27", 420),
    ]

    # 절곡표
    if d.result.bends:
        wsb = wb.create_sheet("절곡표")
        for j, h in enumerate(BEND_HEADER, 1):
            c = wsb.cell(1, j, h)
            c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
            wsb.column_dimensions[c.column_letter].width = 12
        wsb.column_dimensions[wsb.cell(1, len(BEND_HEADER)).column_letter].width = 44
        for i, b in enumerate(d.result.bends, 2):
            vals = [f"B{b.number}", b.direction, b.angle_deg, b.model_radius, b.inner_radius, b.k,
                    b.deduction, b.deduction90, b.allowance, b.length, b.source]
            for j, v in enumerate(vals, 1):
                if isinstance(v, float):
                    v = None if math.isnan(v) else round(v, 4)
                c = wsb.cell(i, j, v)
                c.border = st["border"]
                c.alignment = st["center"] if j < len(vals) else st["wrap"]
                if isinstance(v, float):
                    c.number_format = "0.000"
            if b.kind == "원뿔":
                wsb.cell(i, 5, b.radius_text)
        wsb.freeze_panes = "A2"

    # 성형품 두께 변화 분포
    if d.result.forming is not None:
        _thinning_sheet(wb, d, st)

    wb.save(path)
    for t in tmps:
        try:
            os.remove(t)
        except OSError:
            pass


def _thinning_sheet(wb, d, st):
    fi = d.result.forming
    from .unfolder import _tri_areas2
    areas = _tri_areas2(fi.U, fi.F)
    th = fi.thinning
    ws = wb.create_sheet("두께 변화")
    ws["A1"] = "두께 변화 분포 (블랭크 면적 기준)"
    ws["A1"].font = st["val"]
    head = ["구간", "넓이 (mm²)", "비율", "판정"]
    for j, h in enumerate(head, 1):
        c = ws.cell(3, j, h)
        c.font, c.fill, c.alignment = st["head"], st["head_fill"], st["center"]
        ws.column_dimensions[c.column_letter].width = 22
    edges = [-1, -0.15, -0.05, 0.05, 0.15, 0.25, 1]
    names = ["15% 넘게 두꺼워짐", "5~15% 두꺼워짐", "±5% 이내", "5~15% 얇아짐", "15~25% 얇아짐", "25% 넘게 얇아짐"]
    verdict = ["주름 위험", "주의", "양호", "양호", "주의", "터짐 위험"]
    total = areas.sum()
    for i in range(len(names)):
        sel = (th >= edges[i]) & (th < edges[i + 1])
        a = float(areas[sel].sum())
        ws.cell(4 + i, 1, names[i])
        ws.cell(4 + i, 2, round(a, 1)).number_format = "#,##0.0"
        ws.cell(4 + i, 3, a / total if total else 0).number_format = "0.0%"
        ws.cell(4 + i, 4, verdict[i])
    r = 4 + len(names) + 1
    ws.cell(r, 1, "최대 얇아짐")
    ws.cell(r, 2, float(max(th.max(), 0))).number_format = "0.0%"
    ws.cell(r + 1, 1, "최대 두꺼워짐")
    ws.cell(r + 1, 2, float(max(-th.min(), 0))).number_format = "0.0%"


def save_parts_list(items, path: str):
    """여러 부품을 한 표로 (견적·재료 발주용). items: ReportData 목록."""
    from openpyxl import Workbook

    st = _xl_styles()
    wb = Workbook()
    ws = wb.active
    ws.title = "부품 목록"
    head = ["파일", "부품", "전개 방식", "재질", "두께(mm)", "가로(mm)", "세로(mm)", "블랭크 넓이(mm²)",
            "블랭크 무게(kg)", "사각 원판 무게(kg)", "수율", "절단 길이(mm)", "피어싱", "절곡 수", "주의"]
    for j, h in enumerate(head, 1):
        c = ws.cell(1, j, h)
        c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
        ws.column_dimensions[c.column_letter].width = 14
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["O"].width = 50
    for i, d in enumerate(items, 2):
        m, r = d.metrics, d.result
        vals = [os.path.basename(d.source_path), d.display_name,
                "성형품(근사)" if r.mode == "forming" else "판금", d.material.code, r.thickness,
                m.width, m.height, m.blank_area, m.weight_kg, m.rect_weight_kg, m.yield_ratio,
                m.cut_length, m.pierce, len(r.bends),
                " / ".join(w for w in r.warnings if "근사 전개:" not in w)]
        for j, v in enumerate(vals, 1):
            if isinstance(v, (float, np.floating)):
                v = round(float(v), 4)
            c = ws.cell(i, j, v)
            c.border = st["border"]
            if j == 11:
                c.number_format = "0.0%"
            elif isinstance(v, float):
                c.number_format = "#,##0.000"
    n = len(items) + 1
    ws.cell(n + 1, 1, "합계").font = st["val"]
    for col in ("I", "J", "L"):
        c = ws[f"{col}{n + 1}"]
        c.value = f"=SUM({col}2:{col}{n})"
        c.number_format = "#,##0.000"
    ws.freeze_panes = "A2"
    wb.save(path)
