"""[레이저·절곡·용접 견적] 창 — 부품마다 레이저 절단 · 절곡 · 재료 개당 단가 (탭 1), 조립품의 용접선을 찾아 용접 견적 (탭 2),
단가 기준은 왼쪽에서 바로 고쳐 다시 계산. 세트 견적 = 부품 단가 합 + 용접."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressDialog, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import laserprice as lp
from . import weldcalc as wc

WELD_HEAD = ["부품 A", "부품 B", "종류", "길이 mm", "면", "t", "아크 초", "전체 초", "원", "비고"]


class LaserPriceDialog(QDialog):
    def __init__(self, model, parts, settings, excluded, name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("레이저 · 절곡 · 용접 견적")
        self.resize(1320, 760)
        self.model, self.parts, self.settings_, self.excluded, self.name = model, parts, settings, excluded, name
        self.st = QSettings("Hanil", "SheetUnfold")
        self.rates = lp.load(self.st.value("laser_rates", ""))
        self.rows, self.tot = [], {}
        self.seams, self.weld_costs, self.weld_tot = [], [], {}
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        page1 = QWidget()
        lay = QHBoxLayout(page1)
        self.tabs.addTab(page1, "부품 단가 (레이저 · 절곡)")
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
        hint1 = QLabel("<span style='color:#888'>단가는 예시값 — 회사 값으로 고치면 저장됩니다.<br>"
                       "레이저 시간 = 절단 길이 ÷ 두께별 속도 + 피어싱 + 올리고 내리기</span>")
        hint1.setWordWrap(True)
        ll.addWidget(hint1)
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
        lay.addLayout(right, 1)
        self._build_weld_tab()
        bb = QHBoxLayout()
        self.grand = QLabel()
        bb.addWidget(self.grand, 1)
        xl = QPushButton("엑셀 저장…")
        xl.clicked.connect(self.save)
        bb.addWidget(xl)
        cl = QPushButton("닫기")
        cl.clicked.connect(self.accept)
        bb.addWidget(cl)
        outer.addLayout(bb)
        self.recalc()
        self.find_seams()

    # ---- 용접
    def _build_weld_tab(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        self.tabs.addTab(page, "용접 (조립)")
        self.wrates = dict(wc.DEFAULTS)
        try:
            import json
            saved = json.loads(self.st.value("weld_rates", "") or "{}")
            self.wrates.update({k: v for k, v in saved.items() if k in wc.DEFAULTS})
        except Exception:  # noqa: BLE001
            pass
        left = QWidget()
        left.setFixedWidth(330)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        g = QGroupBox("용접 단가 기준 (CO2 · MAG 수동)")
        f = QFormLayout(g)
        self.wspins = {}
        for key in ("rate", "arc_ratio", "intermittent", "consumable_per_m", "grind_sec_per_m", "setup_min", "tack_sec", "gap"):
            w = QDoubleSpinBox()
            w.setRange(0, 1e8)
            w.setDecimals(2 if key in ("arc_ratio", "intermittent", "gap") else 0)
            w.setSingleStep(0.05 if key in ("arc_ratio", "intermittent") else 0.1 if key == "gap" else 10)
            w.setGroupSeparatorShown(True)
            w.setValue(float(self.wrates.get(key, wc.DEFAULTS[key])))
            w.valueChanged.connect(self.recalc_weld if key != "gap" else lambda *_: None)
            self.wspins[key] = w
            f.addRow(wc.NAMES[key], w)
        self.both = QCheckBox("모든 용접선 양면 (T 이음 양쪽 필릿)")
        self.both.setChecked(bool(self.wrates.get("both_sides", False)))
        self.both.toggled.connect(self._both_toggled)
        f.addRow(self.both)
        ll.addWidget(g)
        rb = QHBoxLayout()
        fb = QPushButton("용접선 다시 찾기")
        fb.setToolTip("부품끼리 맞닿은 선 (틈 허용 이내) 을 다시 찾습니다 — 손으로 고친 길이는 지워집니다")
        fb.clicked.connect(self.find_seams)
        rb.addWidget(fb)
        ab = QPushButton("용접선 추가")
        ab.setToolTip("자동으로 못 찾은 용접선을 한 줄 넣고 길이 · 두께를 적습니다")
        ab.clicked.connect(self.add_seam)
        rb.addWidget(ab)
        db = QPushButton("지우기")
        db.clicked.connect(self.del_seam)
        rb.addWidget(db)
        ll.addLayout(rb)
        hint = QLabel("<span style='color:#888'>용접선 = 판 끝이 다른 판 면에 닿는 선 (닿는 둘레의 반). 길이 · 종류 · 면 (1 / 2) 은 "
                      "표에서 바로 고칩니다.<br>아크 시간 = 길이 ÷ 두께별 속도 (1.6 t 700 · 3.2 t 450 · 6 t 280 mm/분) ÷ 아크 타임 비율, "
                      "+ 가접 · 사상 · 소모품 · 준비 ÷ 로트.</span>")
        hint.setWordWrap(True)
        ll.addWidget(hint)
        ll.addStretch(1)
        lay.addWidget(left)
        right = QVBoxLayout()
        self.wtable = QTableWidget(0, len(WELD_HEAD))
        self.wtable.setHorizontalHeaderLabels(WELD_HEAD)
        self.wtable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.wtable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.wtable.itemChanged.connect(self._seam_edited)
        right.addWidget(self.wtable, 1)
        self.wsum = QLabel()
        right.addWidget(self.wsum)
        lay.addLayout(right, 1)

    def _both_toggled(self, on):
        for sm in self.seams:
            sm.sides = 2 if on else 1
        self.recalc_weld()

    def _thicknesses(self):
        return {p.index: p.thickness for p in self.parts if p.ok and p.thickness}

    def find_seams(self):
        gap = float(self.wspins["gap"].value())
        skip = set(self.excluded) | set((self.model.hardware or {}).keys())
        prog = QProgressDialog("용접선 찾는 중…", "그만", 0, 100, self)
        prog.setWindowTitle("용접")
        prog.setMinimumDuration(400)
        prog.setWindowModality(Qt.WindowModal)

        def step(i, n):
            prog.setMaximum(max(n, 1))
            prog.setValue(i)
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            return not prog.wasCanceled()
        try:
            self.seams = wc.find_seams(self.model.raw_solids, self.model.names, self._thicknesses(), skip=skip, gap=gap,
                                       progress=step)
        except Exception as e:  # noqa: BLE001
            prog.close()
            QMessageBox.warning(self, "용접선 찾기", str(e))
            return
        prog.close()
        if self.both.isChecked():
            for sm in self.seams:
                sm.sides = 2
        self._fill_weld_table()
        self.recalc_weld()

    def add_seam(self):
        ts = self._thicknesses()
        t = min(ts.values()) if ts else float(self.parts[0].thickness or 1.0) if self.parts else 1.0
        self.seams.append(wc.Seam(-1, -1, "(손으로)", "", 100.0, float(t), "필릿", 2 if self.both.isChecked() else 1, "손으로 넣음"))
        self._fill_weld_table()
        self.recalc_weld()

    def del_seam(self):
        rows = sorted({i.row() for i in self.wtable.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.seams):
                del self.seams[r]
        self._fill_weld_table()
        self.recalc_weld()

    def _fill_weld_table(self):
        self.wtable.blockSignals(True)
        self.wtable.setRowCount(len(self.seams))
        for i, sm in enumerate(self.seams):
            vals = [sm.name_a, sm.name_b, sm.kind, f"{sm.length:.0f}", str(sm.sides), f"{sm.thickness:g}", "", "", "", sm.note]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (6, 7, 8):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if j in (3, 4, 5, 6, 7, 8):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.wtable.setItem(i, j, it)
        self.wtable.blockSignals(False)

    def _seam_edited(self, item):
        r, c = item.row(), item.column()
        if not (0 <= r < len(self.seams)):
            return
        sm = self.seams[r]
        txt = item.text().strip()
        try:
            if c == 0:
                sm.name_a = txt
            elif c == 1:
                sm.name_b = txt
            elif c == 2:
                sm.kind = txt or "필릿"
            elif c == 3:
                sm.length = max(float(txt.replace(",", "")), 0.0)
            elif c == 4:
                sm.sides = 2 if txt.startswith("2") else 1
            elif c == 5:
                sm.thickness = max(float(txt), 0.1)
            elif c == 9:
                sm.note = txt
        except ValueError:
            pass
        self.recalc_weld()

    def recalc_weld(self, *_):
        import json
        for key, w in self.wspins.items():
            self.wrates[key] = float(w.value())
        self.wrates["both_sides"] = self.both.isChecked()
        self.st.setValue("weld_rates", json.dumps(self.wrates))
        self.weld_costs, self.weld_tot = wc.cost(self.seams, self.wrates, self.rates.get("lot", 1))
        self.wtable.blockSignals(True)
        for i, c in enumerate(self.weld_costs):
            for j, v in ((6, c.arc_sec), (7, c.total_sec), (8, c.won)):
                it = self.wtable.item(i, j)
                if it is not None:
                    it.setText(f"{v:,.0f}")
        self.wtable.blockSignals(False)
        t = self.weld_tot
        self.wsum.setText(f"<b>용접선 {t.get('n', 0)} 줄 · {t.get('length_m', 0):.2f} m</b> — 아크 {t.get('arc_sec', 0) / 60:.1f} 분 · "
                          f"전체 {t.get('sec', 0) / 60:.1f} 분 · 준비 {t.get('setup', 0):,.0f} 원 → <b>용접 {t.get('won', 0):,.0f} 원</b> (세트당)")
        self._grand()

    def _grand(self):
        parts = self.tot.get("unit_sum", 0.0) if self.tot else 0.0
        weld = self.weld_tot.get("won", 0.0) if self.weld_tot else 0.0
        self.grand.setText(f"<b>세트 견적</b>: 부품 (레이저 · 절곡 · 재료) {parts:,.0f} + 용접 {weld:,.0f} = "
                           f"<b style='font-size:14px'>{parts + weld:,.0f} 원</b> <span style='color:#888'>(관리비 · 이윤은 부품 단가에만, "
                           "용접은 가공비 그대로)</span>")


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
        if hasattr(self, "weld_tot"):
            if self.seams:
                self.recalc_weld()
            else:
                self._grand()

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "레이저 · 절곡 · 용접 견적 엑셀", f"{self.name}_레이저절곡용접견적.xlsx", "엑셀 (*.xlsx)")
        if not path:
            return
        try:
            lp.save_xlsx(self.rows, self.tot, self.rates, path, self.name, seams=self.seams, weld_costs=self.weld_costs,
                         weld_tot=self.weld_tot, weld_rates=self.wrates)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
