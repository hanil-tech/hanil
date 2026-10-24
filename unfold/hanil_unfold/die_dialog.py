"""금형 검토 창: 하중·클리어런스·스프링백, 설계 규칙, 스트립 배치, 원통 드로잉 계산."""
from __future__ import annotations

import math
import os

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import bendcalc as bc
from . import diecalc as dc

VERDICT_COLOR = {dc.OK: QColor(60, 160, 80), dc.WARN: QColor(220, 150, 0), dc.NG: QColor(220, 50, 50)}


def _table(head, rows, colors=None):
    t = QTableWidget(len(rows), len(head))
    t.setHorizontalHeaderLabels(head)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            it = QTableWidgetItem(v if isinstance(v, str) else f"{v:,.2f}")
            if not isinstance(v, str):
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if colors and colors[i] is not None and j == len(r) - 1:
                it.setForeground(colors[i])
            t.setItem(i, j, it)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def load_rows(rep):
    rows = [[L.name, L.length if L.length else "", L.force_n / 1000, L.tonf, L.note] for L in rep.loads]
    rows.append(["합계 (전단 + 스트리퍼)", "", rep.total_n / 1000, rep.total_n / dc.TON, ""])
    rows.append(["권장 프레스 (가장 큰 하중 × 1.3)", "", rep.press_tonf * dc.TON / 1000, rep.press_tonf,
                 "여유 30 % (관례)"])
    return rows


def bend_rows(rep):
    out = []
    for no, length, f, after, die, ks in rep.bends:
        die_txt = f"{die:.2f}" if math.isfinite(die) else "-"
        out.append([f"B{no}", length, f / 1000, f / dc.TON, f"{after:.2f}", die_txt, f"{ks:.4f}"])
    return out


def check_rows(rep):
    return [[c.rule, c.target, c.value, c.limit, c.note, c.verdict] for c in rep.checks]


def render_strip(result, strip, w=1100, h=360, copies=4):
    """스트립 그림: 부품 copies 개를 피치 간격으로, 잔폭·피치 치수."""
    from .nesting import NestPart, _rot_poly
    part = NestPart.from_result("p", result)
    polys = [_rot_poly(c, strip.angle) for c in part.cut]
    P = np.vstack(polys)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)
    total_w = (copies - 1) * strip.pitch + (x1 - x0) + 2 * strip.bridge
    sw = strip.width
    sc = min((w - 40) / total_w, (h - 70) / sw)
    ox = 20 - (x0 - strip.bridge) * sc
    oy = h - 40 - (strip.side - y0) * sc

    def pt(x, y):
        return QPointF(ox + x * sc, oy - y * sc)

    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(120, 120, 120), 1.5))
    p.setBrush(QColor(235, 240, 248))
    ys0, ys1 = y0 - strip.side, y1 + strip.side
    p.drawRect(QRectF(pt(x0 - strip.bridge, ys1), pt(x0 - strip.bridge + total_w, ys0)))
    p.setPen(QPen(QColor(30, 80, 160), 1.6))
    p.setBrush(QColor(200, 215, 240))
    for k in range(copies):
        for poly in polys:
            q = QPolygonF([pt(a + k * strip.pitch, b) for a, b in poly])
            p.drawPolygon(q)
    f = p.font()
    f.setPixelSize(14)
    p.setFont(f)
    p.setPen(QColor(200, 30, 30))
    ya = ys1 + 3 / sc
    a, b = pt(x0, ya), pt(x0 + strip.pitch, ya)
    p.drawLine(QPointF(a.x(), a.y() - 14), QPointF(b.x(), b.y() - 14))
    p.drawText(QRectF(a.x(), a.y() - 34, b.x() - a.x(), 18), Qt.AlignCenter, f"피치 {strip.pitch:.1f}")
    c1 = pt(x0 - strip.bridge + total_w, ys1)
    p.drawText(QRectF(c1.x() - 200, c1.y() - 22, 200, 18), Qt.AlignRight | Qt.AlignVCenter,
               f"폭 {strip.width:.1f}")
    p.setPen(QColor(40, 40, 40))
    p.drawText(QRectF(10, h - 30, w - 20, 22), Qt.AlignLeft | Qt.AlignVCenter,
               f"부품 {strip.angle:g}° 돌림 · 피치 {strip.pitch:.2f} · 폭 {strip.width:.2f} · "
               f"잔폭 {strip.bridge:.2f} · 옆 잔폭 {strip.side:.2f} · 재료 이용률 {strip.utilization:.1%} · "
               f"1 m 에 {strip.per_meter:.2f} 개")
    p.end()
    return img


class DieDialog(QDialog):
    def __init__(self, result, settings: bc.BendSettings, name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"금형 검토 — {name}" if name else "금형 검토")
        self.resize(1150, 720)
        self.result, self.settings, self.name = result, settings, name
        self.rep = dc.review(result, settings)
        rep = self.rep
        tabs = QTabWidget()

        # 1) 하중
        w1 = QWidget()
        l1 = QVBoxLayout(w1)
        l1.addWidget(QLabel(
            f"<b>{rep.material}</b>  두께 {rep.thickness:g} mm · 전단 저항 τ = 0.8 × 인장강도 = {rep.shear_mpa:.0f} MPa · "
            f"<b>한쪽 클리어런스 {rep.clearance_pct:g} % = {rep.clearance_mm:.3f} mm</b> "
            f"(다이 = 펀치 + {2 * rep.clearance_mm:.3f} mm)"))
        l1.addWidget(_table(["하중", "길이 mm", "힘 kN", "톤 (tf)", "비고"], load_rows(rep)))
        if rep.bends:
            l1.addWidget(QLabel("절곡별 굽힘력 · 스프링백 (추정 — 시험 절곡으로 확정)"))
            l1.addWidget(_table(["절곡", "길이 mm", "힘 kN", "톤 (tf)", "보정 없이 접으면 (°)",
                                 "금형 보정 각 (°)", "Ks"], bend_rows(rep)))
        if rep.blank_d:
            l1.addWidget(QLabel(f"성형품: 같은 넓이 원판 지름 Ø{rep.blank_d:.1f} (드로잉 탭에서 공정 계산)"))
        tabs.addTab(w1, "하중 · 클리어런스")

        # 2) 설계 규칙
        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        bad = sum(c.verdict == dc.NG for c in rep.checks)
        warn = sum(c.verdict == dc.WARN for c in rep.checks)
        l2.addWidget(QLabel(f"검사 {len(rep.checks)}건 · <span style='color:#d33'>부적합 {bad}</span> · "
                            f"<span style='color:#d90'>주의 {warn}</span>"))
        l2.addWidget(_table(["규칙", "대상", "값 mm", "기준 mm", "설명", "판정"], check_rows(rep),
                            [VERDICT_COLOR[c.verdict] for c in rep.checks]))
        tabs.addTab(w2, f"설계 규칙 ({bad + warn})" if bad + warn else "설계 규칙")

        # 3) 스트립
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        if rep.strip is not None:
            from PySide6.QtGui import QPixmap
            self.strip_img = render_strip(result, rep.strip)
            lab = QLabel()
            lab.setPixmap(QPixmap.fromImage(self.strip_img))
            l3.addWidget(lab)
            l3.addWidget(QLabel("순차(프로그레시브) 금형 1열 배치: 부품 사이 잔폭 max(1.5t, 1 mm), "
                                "옆 잔폭(캐리어) max(2t, 1.5 mm). 각도를 바꿔 가며 재료 이용률이 가장 큰 쪽."))
        else:
            self.strip_img = None
            l3.addWidget(QLabel("스트립 배치를 계산하지 못했습니다."))
        l3.addStretch(1)
        tabs.addTab(w3, "스트립 배치")

        # 4) 드로잉
        tabs.addTab(self._draw_tab(), "원통 드로잉 계산")

        # 5) 금형 공정도
        tabs.addTab(self._process_tab(), "금형 공정도")
        self.tabs = tabs

        save = QPushButton("엑셀로 저장…")
        save.clicked.connect(self.save)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(save)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addLayout(row)

    def _draw_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        form = QFormLayout()

        def spin(v, lo=0.0, hi=5000.0, dec=2):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(dec)
            s.setValue(v)
            s.valueChanged.connect(self._calc_draw)
            return s

        t = self.result.thickness
        guess_d = 100.0
        if self.rep.blank_d:
            guess_d = round(self.rep.blank_d * 0.6, 1)
        self.d_d = spin(guess_d, 1)
        self.d_h = spin(round(guess_d * 0.5, 1))
        self.d_r = spin(max(4 * t, 1.0))
        self.d_fd = spin(0.0)
        self.d_rf = spin(max(4 * t, 1.0))
        self.d_t = spin(t, 0.05, 50, 3)
        self.d_trim = spin(max(1.0, 0.03 * guess_d * 0.5))
        self.d_mat = QComboBox()
        for m in bc.MATERIALS:
            self.d_mat.addItem(f"{m.code}  {m.name}", m.code)
        self.d_mat.setCurrentIndex(max(0, self.d_mat.findData(self.settings.material)))
        self.d_mat.currentIndexChanged.connect(self._calc_draw)
        form.addRow("컵 지름 d (두께 가운데)", self.d_d)
        form.addRow("높이 h (바닥 ~ 위 끝)", self.d_h)
        form.addRow("바닥 모서리 R", self.d_r)
        form.addRow("플랜지 바깥 지름 (0 = 없음)", self.d_fd)
        form.addRow("플랜지 R", self.d_rf)
        form.addRow("두께 t", self.d_t)
        form.addRow("트림 여유 (높이·플랜지)", self.d_trim)
        form.addRow("재질", self.d_mat)
        note = QLabel("블랭크 지름은 두께 가운데 면 넓이가 같다는 가정 (D = √(d² + 4dh − 1.72dr − 0.56r²) 와 같음). "
                      "드로잉률은 주름 누르개를 쓴 플랜지 없는 원통의 대표 표.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#777")
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(note)
        left.addStretch(1)
        lay.addLayout(left, 1)
        self.draw_out = QLabel()
        self.draw_out.setTextFormat(Qt.RichText)
        self.draw_out.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.draw_out.setWordWrap(True)
        lay.addWidget(self.draw_out, 2)
        self._calc_draw()
        return w

    def _process_tab(self):
        from PySide6.QtWidgets import QCheckBox, QScrollArea
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.p_kind = QComboBox()
        self.p_kind.addItem("순차 금형 스트립 (판금)", "progressive")
        self.p_kind.addItem("드로잉 공정 ([원통 드로잉 계산] 값)", "draw")
        if self.result.forming is not None or not self.result.bends and not self.rep.checks:
            self.p_kind.setCurrentIndex(1)
        self.p_idle = QCheckBox("절곡 앞에 빈 공정")
        pdf = QPushButton("PDF 저장…")
        dxf = QPushButton("DXF 저장…")
        row.addWidget(QLabel("공정"))
        row.addWidget(self.p_kind)
        row.addWidget(self.p_idle)
        row.addStretch(1)
        row.addWidget(pdf)
        row.addWidget(dxf)
        lay.addLayout(row)
        self.p_img = QLabel()
        self.p_img.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sc = QScrollArea()
        sc.setWidget(self.p_img)
        sc.setWidgetResizable(True)
        lay.addWidget(sc, 1)
        self.p_table = QTableWidget(0, 5)
        self.p_table.setHorizontalHeaderLabels(["공정", "작업", "내용", "하중 kN", "tf"])
        self.p_table.verticalHeader().setVisible(False)
        self.p_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.p_table.horizontalHeader().setStretchLastSection(True)
        self.p_table.setMaximumHeight(200)
        lay.addWidget(self.p_table)
        self.p_sum = QLabel()
        self.p_sum.setWordWrap(True)
        lay.addWidget(self.p_sum)
        self.p_kind.currentIndexChanged.connect(self._calc_process)
        self.p_idle.toggled.connect(self._calc_process)
        pdf.clicked.connect(lambda: self._save_process("pdf"))
        dxf.clicked.connect(lambda: self._save_process("dxf"))
        self._calc_process()
        return w

    def process_plan(self):
        from . import process as pr
        if self.p_kind.currentData() == "draw":
            return pr.drawing(self.result, self.settings, self.draw_plan(), self.d_r.value(), self.d_h.value())
        return pr.progressive(self.result, self.settings, idle=self.p_idle.isChecked())

    def _calc_process(self, *_):
        from PySide6.QtGui import QPixmap

        from . import process as pr
        self.p_idle.setEnabled(self.p_kind.currentData() == "progressive")
        try:
            plan = self.process_plan()
        except Exception as e:
            self.plan = None
            self.p_img.setPixmap(QPixmap())
            self.p_img.setText(f"공정도를 만들 수 없습니다: {e}")
            self.p_table.setRowCount(0)
            self.p_sum.setText("")
            return
        self.plan = plan
        self.p_img.setPixmap(QPixmap.fromImage(pr.render(plan, 1080, 420)))
        rows = pr.station_rows(plan)
        self.p_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                it = QTableWidgetItem(v if isinstance(v, str) else f"{v:,.1f}")
                if not isinstance(v, str):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.p_table.setItem(i, j, it)
        self.p_sum.setText("<br>".join(pr.summary_lines(plan)))

    def _save_process(self, kind):
        from . import process as pr
        if self.plan is None:
            return
        if kind == "dxf" and self.plan.kind != "progressive":
            QMessageBox.information(self, "금형 공정도", "DXF 는 순차 금형 스트립 공정도만 됩니다. PDF 로 저장하세요.")
            return
        base = os.path.splitext(self.name or "part")[0] + f"_공정도.{kind}"
        filt = "PDF (*.pdf)" if kind == "pdf" else "DXF (*.dxf)"
        path, _ = QFileDialog.getSaveFileName(self, "금형 공정도 저장", base, filt)
        if not path:
            return
        (pr.save_pdf if kind == "pdf" else pr.save_dxf)(self.plan, path, self.name)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def draw_plan(self):
        mat = bc.MATERIAL_BY_CODE[self.d_mat.currentData()]
        return dc.draw_plan(self.d_d.value(), self.d_h.value(), self.d_r.value(), self.d_t.value(), mat,
                            self.d_fd.value(), self.d_rf.value(), self.d_trim.value())

    def _calc_draw(self, *_):
        if getattr(self, "p_kind", None) is not None and self.p_kind.currentData() == "draw":
            self._calc_process()
        try:
            pl = self.draw_plan()
        except (ValueError, ZeroDivisionError) as e:
            self.draw_out.setText(f"계산할 수 없습니다: {e}")
            return
        rows = "".join(f"<tr><td>{s.no}</td><td align=right>{s.m:.3f}</td><td align=right>Ø{s.d:.1f}</td>"
                       f"<td align=right>{s.force_n / 1000:,.1f}</td><td align=right>{s.force_n / dc.TON:.2f}</td></tr>"
                       for s in pl.stages)
        from html import escape
        notes = "".join(f"<br>⚠ {escape(n)}" for n in pl.notes)
        self.draw_out.setText(
            f"<h3>블랭크 Ø{pl.D:.2f} mm</h3>"
            f"상대 두께 t/D = {pl.rel_thickness:.2f} % · 전체 드로잉률 d/D = {pl.ratio_total:.3f} · "
            f"<b>드로잉 {len(pl.stages)}회</b><br>"
            f"주름 누르개: {escape(pl.holder_needed)} · 누르개 힘 약 {pl.holder_n / 1000:,.1f} kN "
            f"({pl.holder_n / dc.TON:.2f} tf){notes}<br><br>"
            "<table border=1 cellspacing=0 cellpadding=4><tr><th>공정</th><th>드로잉률 m</th><th>지름</th>"
            f"<th>드로잉력 kN</th><th>tf</th></tr>{rows}</table>"
            "<br><span style='color:#777'>드로잉력 F = π·d·t·σb·n (n: 드로잉률에 따른 계수 0.4~1.0)</span>")

    def save(self):
        base = os.path.splitext(self.name or "part")[0] + "_금형검토.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "금형 검토 저장", base, "엑셀 (*.xlsx)")
        if not path:
            return
        save_xlsx(self.rep, path, self.name, self.strip_img, self.draw_plan())
        QMessageBox.information(self, "금형 검토", f"저장했습니다.\n{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def save_xlsx(rep, path, name="", strip_img=None, plan=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    from . import company
    from .report import _add_image

    wb = Workbook()
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E8C")

    def sheet(ws, title, head, rows, start=3):
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=13)
        ws.cell(1, len(head) + 1, company.MAKER)
        for j, h in enumerate(head, 1):
            c = ws.cell(start, j, h)
            c.font, c.fill = head_font, head_fill
            ws.column_dimensions[c.column_letter].width = max(12, len(h) * 2 + 2)
        for i, r in enumerate(rows, start + 1):
            for j, v in enumerate(r, 1):
                c = ws.cell(i, j, v)
                if isinstance(v, float):
                    c.number_format = "#,##0.00"
        return start + len(rows) + 2

    ws = wb.active
    ws.title = "하중"
    nxt = sheet(ws, f"금형 검토 — {name}  ({rep.material}, t {rep.thickness:g})",
                ["하중", "길이 mm", "힘 kN", "톤 (tf)", "비고"], load_rows(rep))
    ws.cell(nxt, 1, f"한쪽 클리어런스 {rep.clearance_pct:g} % = {rep.clearance_mm:.3f} mm · "
                    f"전단 저항 {rep.shear_mpa:.0f} MPa")
    if rep.bends:
        sheet(ws, "", ["절곡", "길이 mm", "힘 kN", "톤 (tf)", "보정 없이 (°)", "금형 보정 각 (°)", "Ks"],
              bend_rows(rep), start=nxt + 2)
    sheet(wb.create_sheet("설계 규칙"), "설계 규칙 검사", ["규칙", "대상", "값 mm", "기준 mm", "설명", "판정"],
          check_rows(rep))
    if rep.strip is not None:
        s = rep.strip
        ws3 = wb.create_sheet("스트립")
        sheet(ws3, "스트립 배치 (1열)", ["항목", "값"],
              [["부품 각도 (°)", float(s.angle)], ["피치 mm", s.pitch], ["폭 mm", s.width],
               ["잔폭 mm", s.bridge], ["옆 잔폭 mm", s.side], ["재료 이용률", s.utilization],
               ["1 m 당 개수", s.per_meter]])
        ws3.cell(9, 2).number_format = "0.0%"
        tmp = _add_image(ws3, strip_img, "D3", 800) if strip_img is not None else None
    else:
        tmp = None
    if plan is not None:
        ws4 = wb.create_sheet("원통 드로잉")
        nxt = sheet(ws4, f"원통 드로잉 — 블랭크 Ø{plan.D:.2f} mm, {len(plan.stages)}회",
                    ["공정", "드로잉률 m", "지름 mm", "드로잉력 kN", "tf"],
                    [[s.no, s.m, s.d, s.force_n / 1000, s.force_n / dc.TON] for s in plan.stages])
        ws4.cell(nxt, 1, f"t/D {plan.rel_thickness:.2f} % · 주름 누르개 {plan.holder_needed} · "
                         f"누르개 힘 {plan.holder_n / 1000:,.1f} kN")
        for k, n in enumerate(plan.notes, 1):
            ws4.cell(nxt + k, 1, n)
    wb.save(path)
    if tmp:
        try:
            os.remove(tmp)
        except OSError:
            pass
