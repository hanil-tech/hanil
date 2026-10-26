"""2D 도면 (DXF·DWG) 가져오기 창: 찾은 블랭크 윤곽 미리 보기, 쓸 부품 고르기, 두께·재질."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget)

from . import bendcalc as bc


class _Preview(QWidget):
    def __init__(self, fd, parent=None):
        super().__init__(parent)
        self.fd, self.on, self.hi = fd, set(), -1
        self.setMinimumSize(460, 360)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(32, 34, 38))
        boxes = [pt.outer.bbox() for pt in self.fd.parts]
        if not boxes:
            p.setPen(QColor(220, 220, 220))
            p.drawText(self.rect(), Qt.AlignCenter, "닫힌 윤곽이 없습니다")
            return
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        s = min((self.width() - 30) / max(x1 - x0, 1e-9), (self.height() - 30) / max(y1 - y0, 1e-9))
        ox = (self.width() - (x1 - x0) * s) / 2
        oy = (self.height() - (y1 - y0) * s) / 2

        def q(pt):
            return QPointF(ox + (pt[0] - x0) * s, self.height() - oy - (pt[1] - y0) * s)

        def path(loop):
            pp = QPainterPath()
            P = loop.polygon()
            pp.moveTo(q(P[0]))
            for v in P[1:]:
                pp.lineTo(q(v))
            pp.closeSubpath()
            return pp
        for i, pt in enumerate(self.fd.parts):
            on = i in self.on
            col = QColor(120, 120, 120) if pt.frame else QColor(80, 200, 255) if on else QColor(150, 150, 150)
            pp = path(pt.outer)
            for h in pt.holes:
                pp.addPath(path(h))
            pp.setFillRule(Qt.OddEvenFill)
            if on:
                p.fillPath(pp, QColor(80, 200, 255, 60 if i != self.hi else 120))
            p.setPen(QPen(col, 2.2 if i == self.hi else 1.2, Qt.DashLine if pt.frame else Qt.SolidLine))
            p.drawPath(pp)
            c = q(((pt.outer.bbox()[0] + pt.outer.bbox()[2]) / 2, (pt.outer.bbox()[1] + pt.outer.bbox()[3]) / 2))
            if not pt.frame:
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRectF(c.x() - 20, c.y() - 10, 40, 20), Qt.AlignCenter, str(i + 1))
        p.setPen(QPen(QColor(255, 200, 40), 1.4, Qt.DashLine))
        for a, b in self.fd.bend_lines:
            p.drawLine(q(a), q(b))


class FlatImportDialog(QDialog):
    """exec() 뒤 parts() · thickness() · material()."""

    def __init__(self, fd, default_t=1.0, default_mat="SPCC", parent=None):
        super().__init__(parent)
        import os
        self.setWindowTitle(f"2D 도면 가져오기 — {os.path.basename(fd.path)}")
        self.resize(980, 600)
        self.fd = fd
        self.view = _Preview(fd)
        self.list = QListWidget()
        for i, pt in enumerate(fd.parts):
            w, h = pt.size
            it = QListWidgetItem(f"{i + 1}. {pt.name} — 넓이 {pt.area:,.0f} mm² · 절단 {pt.cut_length:,.0f} mm"
                                 if not pt.frame else f"{i + 1}. {pt.name} ({w:,.0f} × {h:,.0f})")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if pt.frame else Qt.Checked)
            self.list.addItem(it)
        self.list.itemChanged.connect(self._sync)
        self.list.currentRowChanged.connect(self._hi)
        self.t = QDoubleSpinBox()
        self.t.setRange(0.1, 30)
        self.t.setDecimals(2)
        self.t.setSuffix(" mm")
        self.t.setValue(fd.thickness or default_t)
        self.mat = QComboBox()
        for m in bc.MATERIALS:
            self.mat.addItem(f"{m.code}  {m.name}", m.code)
        i = self.mat.findData(fd.material or default_mat)
        self.mat.setCurrentIndex(max(i, 0))
        form = QFormLayout()
        form.addRow("판 두께", self.t)
        form.addRow("재질", self.mat)
        found = []
        if fd.thickness:
            found.append(f"두께 t{fd.thickness:g}")
        if fd.material:
            found.append(f"재질 {fd.material}")
        info = [f"도면 글자에서 찾음: {', '.join(found)}" if found else "도면 글자에 두께·재질이 없음 — 직접 넣으세요"]
        if fd.scale != 1.0:
            info.append(f"도면 단위 × {fd.scale:g} → mm")
        if fd.bend_lines:
            info.append(f"절곡선 {len(fd.bend_lines)} 개 (노란 점선) — 평판 (블랭크) 으로 엽니다. 절곡 검토·견적은 3D (STEP) 로 하면 정확")
        info += fd.warnings
        lab = QLabel("<br>".join(info))
        lab.setWordWrap(True)
        lab.setStyleSheet("color:#444")
        right = QVBoxLayout()
        right.addWidget(QLabel("찾은 윤곽 (체크한 것을 부품으로 엽니다 · 점선 = 도면 테두리로 보여 뺌)"))
        right.addWidget(self.list, 1)
        right.addLayout(form)
        right.addWidget(lab)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("평판으로 열기")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        lay = QHBoxLayout(self)
        lay.addWidget(self.view, 3)
        w = QWidget()
        w.setLayout(right)
        lay.addWidget(w, 2)
        self._sync()

    def _sync(self, *_):
        self.view.on = set(self.parts())
        self.view.update()

    def _hi(self, row):
        self.view.hi = row
        self.view.update()

    def parts(self):
        return [i for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.Checked]

    def thickness(self):
        return self.t.value()

    def material(self):
        return self.mat.currentData()
