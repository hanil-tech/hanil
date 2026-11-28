"""[레이저·절곡 단가] 창 — 전개한 부품마다 레이저 절단 · 절곡 · 재료 개당 단가, 단가 기준은 왼쪽에서 바로 고쳐 다시 계산."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import laserprice as lp


class LaserPriceDialog(QDialog):
    def __init__(self, model, parts, settings, excluded, name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("레이저 · 절곡 단가 뽑기")
        self.resize(1280, 720)
        self.model, self.parts, self.settings_, self.excluded, self.name = model, parts, settings, excluded, name
        self.st = QSettings("Hanil", "SheetUnfold")
        self.rates = lp.load(self.st.value("laser_rates", ""))
        self.rows, self.tot = [], {}
        lay = QHBoxLayout(self)
        # ---- 왼쪽: 단가 기준
        left = QWidget()
        left.setFixedWidth(330)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.spins = {}

        def spin(key, lo=0.0, hi=1e9, dec=1, step=1.0):
            v = self.rates
            for k in key:
                v = v[k]
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setSingleStep(step)
            w.setValue(float(v))
            w.setGroupSeparatorShown(True)
            w.valueChanged.connect(self.recalc)
            self.spins[key] = w
            return w
        g = QGroupBox("공통")
        f = QFormLayout(g)
        self.lot = QSpinBox()
        self.lot.setRange(1, 1_000_000)
        self.lot.setValue(int(self.rates.get("lot", 100)))
        self.lot.valueChanged.connect(self.recalc)
        f.addRow("로트 (준비 비용 나눌 개수)", self.lot)
        f.addRow("일반관리비 (%)", spin(("overhead_pct",), 0, 100, 1))
        f.addRow("이윤 (%)", spin(("profit_pct",), 0, 100, 1))
        ll.addWidget(g)
        g = QGroupBox("레이저 절단")
        f = QFormLayout(g)
        f.addRow("임률 (원/h)", spin(("laser", "rate"), 0, 1e8, 0, 1000))
        f.addRow("1 mm 속도 (m/분)", spin(("laser", "speed_1mm"), 1, 200, 1))
        f.addRow("피어싱 기본 (초)", spin(("laser", "pierce_sec"), 0, 60, 2, 0.1))
        f.addRow("피어싱 두께 1 mm 당 (초)", spin(("laser", "pierce_per_mm"), 0, 10, 2, 0.05))
        f.addRow("올리고 내리기 (초)", spin(("laser", "load_sec"), 0, 600, 0))
        f.addRow("준비 (분/로트)", spin(("laser", "setup_min"), 0, 600, 1))
        f.addRow("보조 가스 (원/분)", spin(("laser", "gas_per_min"), 0, 1e6, 0, 50))
        f.addRow("최대 두께 (mm)", spin(("laser", "max_t"), 0.5, 60, 1))
        ll.addWidget(g)
        g = QGroupBox("절곡")
        f = QFormLayout(g)
        self.mode = QComboBox()
        for k, lab in lp.BEND_MODES:
            self.mode.addItem(lab, k)
        self.mode.setCurrentIndex([k for k, _ in lp.BEND_MODES].index(self.rates["bend"].get("mode", "time")))
        self.mode.currentIndexChanged.connect(self.recalc)
        f.addRow("계산 방식", self.mode)
        f.addRow("임률 (원/h)", spin(("bend", "rate"), 0, 1e8, 0, 1000))
        f.addRow("1 회 (초)", spin(("bend", "sec_per_bend"), 0, 600, 0))
        f.addRow("준비 (분/로트)", spin(("bend", "setup_min"), 0, 600, 1))
        f.addRow("1 회 기본 (원)", spin(("bend", "per_bend"), 0, 1e6, 0, 50))
        f.addRow("길이 1 m 당 (원)", spin(("bend", "per_m"), 0, 1e6, 0, 50))
        f.addRow("두께 1 mm 당 (원)", spin(("bend", "per_mm_t"), 0, 1e6, 0, 50))
        ll.addWidget(g)
        g = QGroupBox("재료")
        f = QFormLayout(g)
        self.inc = QCheckBox("재료비 포함 (사각 원판 − 자투리 고철)")
        self.inc.setChecked(bool(self.rates["material"].get("include", True)))
        self.inc.toggled.connect(self.recalc)
        f.addRow(self.inc)
        f.addRow("재료 (원/kg, 0 = 재질 표)", spin(("material", "price_kg"), 0, 1e6, 0, 50))
        f.addRow("고철 회수 (원/kg)", spin(("material", "scrap_kg"), 0, 1e6, 0, 50))
        ll.addWidget(g)
        ll.addWidget(QLabel("<span style='color:#888'>단가는 예시값 — 회사 값으로 고치면 저장됩니다.<br>"
                            "레이저 시간 = 절단 길이 ÷ 두께별 속도 + 피어싱 + 올리고 내리기</span>"))
        ll.addStretch(1)
        lay.addWidget(left)
        # ---- 오른쪽: 표
        right = QVBoxLayout()
        self.table = QTableWidget(0, len(lp.HEAD))
        self.table.setHorizontalHeaderLabels(lp.HEAD)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.table, 1)
        self.sum = QLabel()
        right.addWidget(self.sum)
        bb = QHBoxLayout()
        bb.addStretch(1)
        xl = QPushButton("엑셀 저장…")
        xl.clicked.connect(self.save)
        bb.addWidget(xl)
        cl = QPushButton("닫기")
        cl.clicked.connect(self.accept)
        bb.addWidget(cl)
        right.addLayout(bb)
        lay.addLayout(right, 1)
        self.recalc()

    def current_rates(self):
        r = lp.load(None)
        for key, w in self.spins.items():
            d = r
            for k in key[:-1]:
                d = d[k]
            d[key[-1]] = float(w.value())
        r["lot"] = int(self.lot.value())
        r["bend"]["mode"] = self.mode.currentData()
        r["material"]["include"] = self.inc.isChecked()
        return r

    def recalc(self, *_):
        self.rates = self.current_rates()
        self.st.setValue("laser_rates", lp.dump(self.rates))
        try:
            self.rows, self.tot = lp.price_parts(self.model, self.parts, self.settings_, self.excluded, self.rates)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "레이저 · 절곡 단가", str(e))
            return
        data = lp.table_rows(self.rows)
        self.table.setRowCount(len(data))
        for i, row in enumerate(data):
            for j, v in enumerate(row):
                it = QTableWidgetItem(f"{v:,}" if isinstance(v, (int, float)) and j not in (0, 3) else str(v))
                if j not in (1, 14):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, it)
        t = self.tot
        self.sum.setText(f"<b>세트 1 개 ({t.get('parts', 0)} 부품)</b> — 레이저 {t.get('laser', 0):,.0f} 원 "
                         f"({t.get('laser_sec', 0) / 60:.1f} 분) · 절곡 {t.get('bend', 0):,.0f} 원 ({t.get('bends', 0)} 회) · "
                         f"재료 {t.get('material', 0):,.0f} 원 → <b>합계 {t.get('unit_sum', 0):,.0f} 원</b> "
                         f"(관리비 · 이윤 포함, 로트 {self.rates['lot']} 개 기준)")

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "레이저 · 절곡 단가 엑셀", f"{self.name}_레이저절곡단가.xlsx", "엑셀 (*.xlsx)")
        if not path:
            return
        try:
            lp.save_xlsx(self.rows, self.tot, self.rates, path, self.name)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
