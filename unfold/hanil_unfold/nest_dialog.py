"""철판 배치 창: 전개한 부품을 1219 × 2438 같은 철판 위에 늘어놓고, 필요한 장 수·사용률을 보여 준다.

왼쪽: 배치할 부품(넣기·수량), 철판 크기·간격·여유·회전. 오른쪽: 철판 그림 (두께별, 장별).
DXF(가공기용, 철판마다 테두리) 와 PDF(요약 + 장마다 그림) 로 저장한다.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QListWidget, QMessageBox, QProgressDialog,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from . import nesting as N
from .drawing import DARK, paint_sheet, sheet_shapes


class SheetView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 300)
        self.result = None
        self.sheet = None
        self.shapes = None

    def show_sheet(self, result, sheet):
        self.result, self.sheet = result, sheet
        self.shapes = sheet_shapes(result, sheet) if sheet is not None else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), DARK.bg)
        if self.sheet is None:
            p.setPen(DARK.text)
            p.drawText(self.rect(), Qt.AlignCenter, "[배치하기] 를 누르면 철판 그림이 나옵니다")
            return
        r = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        paint_sheet(p, self.result, self.sheet, r, DARK, self.shapes)
        p.end()


class NestDialog(QDialog):
    """items: [(번호 1부터, 이름, UnfoldResult)]. material: 재질 기호, density: g/cm³."""

    COLS = ["넣기", "번호", "부품", "두께", "크기 (mm)", "면적 (m²)", "수량"]

    def __init__(self, items, material="", density=7.85, source_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("철판 배치")
        self.resize(1400, 820)
        self.items = items
        self.material = material
        self.density = density
        self.source_name = source_name
        self.results = []
        self.st = QSettings("Hanil", "SheetUnfold")

        # ---- 부품 표
        self.table = QTableWidget(len(items), len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.qty = []
        self.use = []
        for row, (num, name, res) in enumerate(items):
            cb = QCheckBox()
            cb.setChecked(True)
            self.use.append(cb)
            self.table.setCellWidget(row, 0, cb)
            w, h = res.size
            from . import metrics as mt
            area = mt.compute(res, density).blank_area
            for col, txt in ((1, str(num)), (2, name), (3, f"{round(res.thickness, 2):g}"),
                             (4, f"{w:.0f} × {h:.0f}"), (5, f"{area / 1e6:.4f}")):
                it = QTableWidgetItem(txt)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, it)
            sp = QSpinBox()
            sp.setRange(0, 9999)
            sp.setValue(1)
            self.qty.append(sp)
            self.table.setCellWidget(row, 6, sp)

        all_on = QPushButton("모두 넣기")
        all_on.clicked.connect(lambda: [c.setChecked(True) for c in self.use])
        all_off = QPushButton("모두 빼기")
        all_off.clicked.connect(lambda: [c.setChecked(False) for c in self.use])
        self.sets = QSpinBox()
        self.sets.setRange(1, 9999)
        self.sets.setValue(1)
        self.sets.setToolTip("수량에 곱합니다 (예: 조립품 10세트)")

        # ---- 설정
        self.size_box = QComboBox()
        self.size_box.setEditable(True)
        for label, a, b in N.STANDARD_SHEETS:
            self.size_box.addItem(label, (a, b))
        self.size_box.setEditText(self.st.value("nest/size", N.STANDARD_SHEETS[0][0]))
        self.size_box.setToolTip("목록에서 고르거나 1219*2438 처럼 직접 쓰세요")
        self.gap = QDoubleSpinBox()
        self.gap.setRange(0, 100)
        self.gap.setSuffix(" mm")
        self.gap.setValue(float(self.st.value("nest/gap", 5.0)))
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 200)
        self.margin.setSuffix(" mm")
        self.margin.setValue(float(self.st.value("nest/margin", 10.0)))
        self.rot = QComboBox()
        for k, v in N.ROTATION_NAMES.items():
            self.rot.addItem(v, k)
        i = self.rot.findData(self.st.value("nest/rot", "free"))
        self.rot.setCurrentIndex(max(0, i))
        self.quality = QComboBox()
        self.quality.addItem("빠르게 (한 번)", 1)
        self.quality.addItem("꼼꼼히 (놓는 순서 3가지 중 가장 좋은 것)", 3)
        self.quality.setCurrentIndex(int(self.st.value("nest/quality", 1)))
        self.fine = QCheckBox("정밀 격자 (1 mm, 느림)")
        self.fine.setChecked(self.st.value("nest/fine", "false") == "true")

        form = QFormLayout()
        form.addRow("철판 크기", self.size_box)
        form.addRow("부품 간격", self.gap)
        form.addRow("가장자리 여유", self.margin)
        form.addRow("돌리기", self.rot)
        form.addRow("배치 방식", self.quality)
        form.addRow("", self.fine)
        form.addRow("세트 수", self.sets)
        box = QGroupBox("철판")
        box.setLayout(form)

        run = QPushButton("배치하기")
        run.setDefault(True)
        run.setMinimumHeight(34)
        run.clicked.connect(self.run)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        hb = QHBoxLayout()
        hb.addWidget(QLabel("배치할 부품"))
        hb.addStretch()
        hb.addWidget(all_on)
        hb.addWidget(all_off)
        lv.addLayout(hb)
        lv.addWidget(self.table, 1)
        lv.addWidget(box)
        lv.addWidget(run)

        # ---- 결과
        self.view = SheetView()
        self.sheet_list = QListWidget()
        self.sheet_list.setMaximumWidth(300)
        self.sheet_list.currentRowChanged.connect(self._show)
        self.summary = QLabel("두께가 다른 부품은 다른 철판에 따로 배치합니다.")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_dxf = QPushButton("DXF 저장")
        self.btn_dxf.clicked.connect(self.save_dxf)
        self.btn_pdf = QPushButton("PDF 저장")
        self.btn_pdf.clicked.connect(self.save_pdf)
        for b in (self.btn_dxf, self.btn_pdf):
            b.setEnabled(False)
        side = QWidget()
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.addWidget(QLabel("철판 (눌러서 보기)"))
        sv.addWidget(self.sheet_list, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.summary)
        sv.addWidget(scroll, 1)
        sv.addWidget(self.btn_dxf)
        sv.addWidget(self.btn_pdf)

        right = QSplitter(Qt.Horizontal)
        right.addWidget(self.view)
        right.addWidget(side)
        right.setStretchFactor(0, 1)
        right.setSizes([700, 300])

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([430, 970])
        lay = QVBoxLayout(self)
        lay.addWidget(split)
        self._index = []      # 목록 줄 → (결과, 철판)

    # ---- 계산

    def sheet_size(self):
        i = self.size_box.findText(self.size_box.currentText())
        if i >= 0 and self.size_box.itemData(i):
            return self.size_box.itemData(i)
        return N.parse_size(self.size_box.currentText())

    def parts(self):
        out = []
        for row, (num, name, res) in enumerate(self.items):
            q = self.qty[row].value() * self.sets.value()
            if not self.use[row].isChecked() or q <= 0:
                continue
            try:
                out.append(N.NestPart.from_result(name, res, q, self.material, num))
            except ValueError as e:
                QMessageBox.warning(self, "철판 배치", str(e))
        return out

    def run(self):
        size = self.sheet_size()
        if size is None:
            QMessageBox.warning(self, "철판 배치", "철판 크기를 1219*2438 처럼 써 주세요.")
            return
        parts = self.parts()
        if not parts:
            QMessageBox.information(self, "철판 배치", "배치할 부품이 없습니다 (넣기·수량을 확인하세요).")
            return
        self.st.setValue("nest/size", self.size_box.currentText())
        self.st.setValue("nest/gap", self.gap.value())
        self.st.setValue("nest/margin", self.margin.value())
        self.st.setValue("nest/rot", self.rot.currentData())
        self.st.setValue("nest/quality", self.quality.currentIndex())
        self.st.setValue("nest/fine", "true" if self.fine.isChecked() else "false")

        dlg = QProgressDialog("부품을 철판에 놓는 중…", "그만", 0, 1000, self)
        dlg.setWindowTitle("철판 배치")
        dlg.setMinimumDuration(300)

        def progress(done, total):
            dlg.setValue(int(1000 * done / max(total, 1)))
            QApplication.processEvents()
            return not dlg.wasCanceled()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.results = N.nest_by_thickness(
                parts, size[0], size[1], gap=self.gap.value(), margin=self.margin.value(),
                rotations=self.rot.currentData(), tries=self.quality.currentData(),
                resolution=1.0 if self.fine.isChecked() else None, progress=progress)
        finally:
            QApplication.restoreOverrideCursor()
            dlg.close()
        if any(r is None for r in self.results):
            self.results = []
            return
        self._fill()

    def _fill(self):
        self.sheet_list.clear()
        self._index = []
        for r in self.results:
            for k, s in enumerate(r.sheets):
                self.sheet_list.addItem(f"t{r.thickness:g}  {k + 1}/{len(r.sheets)}장  "
                                        f"{len(s.placements)}개 · {s.utilization * 100:.0f}%")
                self._index.append((r, s))
        total = sum(len(r.sheets) for r in self.results)
        lines = [f"<b>철판 모두 {total}장</b>"]
        for r in self.results:
            sl = r.summary_lines(self.density)
            lines.append(f"<b>{sl[0]}</b><br>" + "<br>".join(sl[1:]))
        self.summary.setText("<br><br>".join(lines))
        for b in (self.btn_dxf, self.btn_pdf):
            b.setEnabled(total > 0)
        if self._index:
            self.sheet_list.setCurrentRow(0)
        else:
            self.view.show_sheet(None, None)

    def _show(self, row):
        if 0 <= row < len(self._index):
            self.view.show_sheet(*self._index[row])

    # ---- 저장

    def _base(self, ext):
        size = self.sheet_size() or (0, 0)
        stem = os.path.splitext(self.source_name)[0] if self.source_name else "nesting"
        return f"{stem}_철판배치_{size[0]:g}x{size[1]:g}.{ext}"

    def save_dxf(self):
        path, _ = QFileDialog.getSaveFileName(self, "철판 배치 DXF", self._base("dxf"), "DXF (*.dxf)")
        if path:
            N.save_dxf(self.results, path)
            QMessageBox.information(self, "철판 배치", f"저장했습니다.\n{path}\n\n"
                                    "레이어: SHEET 철판 테두리, CUT 절단, BEND 절곡, NOTE 번호·설명")

    def save_pdf(self):
        from . import report
        path, _ = QFileDialog.getSaveFileName(self, "철판 배치 PDF", self._base("pdf"), "PDF (*.pdf)")
        if path:
            report.save_nesting_pdf(self.results, path, self.source_name, self.density)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
