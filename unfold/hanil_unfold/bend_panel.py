"""절곡 조건 패널과 연신 표 창."""
from __future__ import annotations

import csv
import math

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import bendcalc as bc

SHOP_COLOR = QColor(255, 236, 170)


def _spin(lo, hi, dec, suffix="", special=None):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(10 ** -dec * 10 if dec else 1)
    if suffix:
        s.setSuffix(suffix)
    if special:
        s.setSpecialValueText(special)
    return s


class BendPanel(QGroupBox):
    """절곡 조건을 고르는 패널. 값이 바뀌면 changed 신호를 낸다."""

    changed = Signal()

    def __init__(self, store: QSettings):
        super().__init__("절곡 조건 (연신 계산)")
        self.store = store
        self.shop = bc.ShopTable.load(bc.default_shop_table_path())

        self.method = QComboBox()
        for key, name in bc.METHOD_NAMES.items():
            self.method.addItem(name, key)
        self.material = QComboBox()
        for m in bc.MATERIALS:
            self.material.addItem(f"{m.code}  {m.name}", m.code)
        self.process = QComboBox()
        for key, name in bc.PROCESS_NAMES.items():
            self.process.addItem(name, key)
        self.k = _spin(0.0, 1.0, 3)
        self.k.setSingleStep(0.01)
        self.k.setToolTip("중립축 위치. 0 = 안쪽 면, 0.5 = 두께 가운데")
        self.use_r = QCheckBox("상형 R · 하형 V 로 실제 R 계산 (바깥 치수 유지)")
        self.punch = _spin(0.0, 50.0, 2, " mm", "모델 R")
        self.die = _spin(0.0, 200.0, 1, " mm", "자동 (8t)")
        self.use_shop = QCheckBox("회사 연신 표 값이 있으면 먼저 사용")
        self.table_btn = QPushButton("연신 표 보기 · 입력…")
        self.table_btn.clicked.connect(self.open_table)
        self.mill_btn = QPushButton("밀시트 실측값…")
        self.mill_btn.setToolTip("소재 검사 증명서 (밀시트) 의 항복·인장 강도, n, r 값을 넣으면 대표값 대신 "
                                 "성형 해석 · 스프링백 · 하중 · 드로잉 설계에 씁니다 (재질마다 저장)")
        self.mill_btn.clicked.connect(self.open_mill)

        form = QFormLayout()
        form.setContentsMargins(6, 4, 6, 4)
        form.setVerticalSpacing(3)
        form.addRow("계산 방법", self.method)
        form.addRow("재질", self.material)
        self.material.setToolTip("연신 계산과 블랭크 무게(비중)에 쓰입니다")
        form.addRow("가공 방식", self.process)
        form.addRow("K 계수", self.k)
        form.addRow(self.use_r)
        form.addRow("상형 R", self.punch)
        form.addRow("하형 V 폭", self.die)
        form.addRow(self.use_shop)
        form.addRow(self.table_btn)
        form.addRow(self.mill_btn)
        self.setLayout(form)

        self._load()
        for w in (self.method, self.material, self.process):
            w.currentIndexChanged.connect(self._on_change)
        for w in (self.k, self.punch, self.die):
            w.editingFinished.connect(self._on_change)
        for w in (self.use_r, self.use_shop):
            w.toggled.connect(self._on_change)
        self.material.currentIndexChanged.connect(self._mill_text)
        self._enable()
        self._mill_text()

    # ---- 저장·불러오기

    def _load(self):
        st = self.store
        self._select(self.method, st.value("bend/method", bc.K_DIRECT))
        self._select(self.material, st.value("bend/material", "SPCC"))
        self._select(self.process, st.value("bend/process", bc.AIR))
        self.k.setValue(float(st.value("bend/k", st.value("k_factor", 0.44))))
        self.use_r.setChecked(st.value("bend/use_r", "false") == "true")
        self.punch.setValue(float(st.value("bend/punch", 0.0)))
        self.die.setValue(float(st.value("bend/die", 0.0)))
        self.use_shop.setChecked(st.value("bend/use_shop", "true") == "true")

    def _save(self):
        s = self.settings()
        st = self.store
        st.setValue("bend/method", s.method)
        st.setValue("bend/material", s.material)
        st.setValue("bend/process", s.process)
        st.setValue("bend/k", s.k)
        st.setValue("bend/use_r", "true" if s.use_process_radius else "false")
        st.setValue("bend/punch", s.punch_r)
        st.setValue("bend/die", s.die_v)
        st.setValue("bend/use_shop", "true" if s.use_shop_table else "false")

    @staticmethod
    def _select(box, data):
        i = box.findData(data)
        if i >= 0:
            box.setCurrentIndex(i)

    def _enable(self):
        direct = self.method.currentData() == bc.K_DIRECT
        self.k.setEnabled(direct)
        # 재질은 무게 계산에도 쓰므로 늘 고를 수 있다.
        self.use_shop.setEnabled(not direct)
        self.punch.setEnabled(self.use_r.isChecked())
        self.die.setEnabled(self.use_r.isChecked() and self.process.currentData() == bc.AIR)

    def _on_change(self):
        self._enable()
        self._save()
        self.changed.emit()

    def settings(self) -> bc.BendSettings:
        return bc.BendSettings(
            method=self.method.currentData(), k=self.k.value(),
            material=self.material.currentData(), process=self.process.currentData(),
            use_process_radius=self.use_r.isChecked(), punch_r=self.punch.value(),
            die_v=self.die.value(), use_shop_table=self.use_shop.isChecked(),
            shop_table=self.shop, mill=self.mill(self.material.currentData()))

    def mill(self, code) -> dict:
        import json
        try:
            d = json.loads(self.store.value(f"bend/mill/{code}", "") or "{}")
        except ValueError:
            d = {}
        return {k: float(v) for k, v in d.items() if k in dict(bc.MILL_KEYS) and v}

    def _mill_text(self):
        code = self.material.currentData()
        d = self.mill(code)
        self.mill_btn.setText(f"밀시트 실측값 사용 중 ({len(d)} 항목)…" if d else "밀시트 실측값…")
        self.mill_btn.setStyleSheet("QPushButton { color: #1f6e2c; font-weight: bold; }" if d else "")

    def open_mill(self):
        import json
        code = self.material.currentData()
        dlg = MillDialog(bc.MATERIAL_BY_CODE[code], self.mill(code), self)
        if dlg.exec():
            self.store.setValue(f"bend/mill/{code}", json.dumps(dlg.values()))
            self._mill_text()
            self.changed.emit()

    def open_table(self):
        dlg = DeductionDialog(self.settings(), self.shop, self)
        dlg.exec()
        if dlg.dirty:
            self.shop.save()
            self.changed.emit()


class DeductionDialog(QDialog):
    """재질별 · 두께 × 상형 R 연신 표. 칸을 고쳐 회사 측정값을 넣는다."""

    def __init__(self, settings: bc.BendSettings, shop: bc.ShopTable, parent=None):
        super().__init__(parent)
        self.setWindowTitle("연신 표 (90° 한 번 접을 때 빼는 길이)")
        self.resize(1050, 640)
        self.base = settings
        self.shop = shop
        self.dirty = False
        self._filling = False

        self.material = QComboBox()
        for m in bc.MATERIALS:
            self.material.addItem(f"{m.code}  {m.name}", m.code)
        BendPanel._select(self.material, settings.material)
        self.method = QComboBox()
        for key, name in bc.METHOD_NAMES.items():
            if key != bc.K_DIRECT:
                self.method.addItem(name, key)
        BendPanel._select(self.method, settings.method if settings.method != bc.K_DIRECT else bc.K_MATERIAL)
        self.process = QComboBox()
        for key, name in bc.PROCESS_NAMES.items():
            self.process.addItem(name, key)
        BendPanel._select(self.process, settings.process)
        self.die = _spin(0.0, 200.0, 1, " mm", "자동 (8t)")
        self.die.setValue(settings.die_v)

        top = QHBoxLayout()
        for label, w in (("재질", self.material), ("계산 방법", self.method),
                         ("가공", self.process), ("하형 V", self.die)):
            top.addWidget(QLabel(label))
            top.addWidget(w)
        top.addStretch()

        self.grid = QTableWidget()
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.itemChanged.connect(self._edited)

        hint = QLabel("칸 값 = 90° 연신(mm).  노란 칸은 회사에서 잰 값입니다. "
                      "칸을 두 번 눌러 측정값을 넣고, 지우면 계산값으로 돌아갑니다.  "
                      "칸에 마우스를 올리면 실제 R · K · 출처가 보입니다.")
        hint.setWordWrap(True)

        export = QPushButton("CSV 로 저장…")
        export.clicked.connect(self._export)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("닫기")
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(export)
        bottom.addStretch()
        bottom.addWidget(buttons)

        table_tab = QWidget()
        lay = QVBoxLayout(table_tab)
        lay.addLayout(top)
        lay.addWidget(self.grid)
        lay.addWidget(hint)

        tabs = QTabWidget()
        tabs.addTab(table_tab, "연신 표")
        tabs.addTab(self._materials_tab(), "재질 · 참고 문헌")

        outer = QVBoxLayout(self)
        outer.addWidget(tabs)
        outer.addLayout(bottom)

        for w in (self.material, self.method, self.process):
            w.currentIndexChanged.connect(self._fill)
        self.die.editingFinished.connect(self._fill)
        self._fill()

    def _settings(self):
        return bc.BendSettings(
            method=self.method.currentData(), material=self.material.currentData(),
            process=self.process.currentData(), die_v=self.die.value(),
            use_shop_table=True, shop_table=self.shop)

    def _fill(self):
        self._filling = True
        s = self._settings()
        ts, rs = bc.STANDARD_THICKNESSES, bc.STANDARD_PUNCH_R
        rows = bc.deduction_table(s, ts, rs)
        self.grid.clear()
        self.grid.setRowCount(len(ts))
        self.grid.setColumnCount(len(rs))
        self.grid.setHorizontalHeaderLabels([f"상형 R{r:g}" for r in rs])
        self.grid.setVerticalHeaderLabels([f"t {t:g}" for t in ts])
        bold = QFont()
        bold.setBold(True)
        for i, t in enumerate(ts):
            for j, pr in enumerate(rs):
                c = rows[i][j]
                item = QTableWidgetItem(f"{c.deduction90:.2f}")
                item.setTextAlignment(Qt.AlignCenter)
                item.setToolTip(f"실제 R {c.r:.2f}  ·  K {c.k:.3f}\n{c.source}")
                if "회사" in c.source:
                    item.setBackground(QBrush(SHOP_COLOR))
                    item.setForeground(QBrush(QColor(0, 0, 0)))
                    item.setFont(bold)
                item.setData(Qt.UserRole, (t, pr))
                self.grid.setItem(i, j, item)
        self._filling = False

    def _edited(self, item):
        if self._filling:
            return
        t, pr = item.data(Qt.UserRole)
        text = item.text().strip()
        mat = self.material.currentData()
        die = self.die.value()
        if not text:
            self.shop.remove(mat, t, pr, die)
        else:
            try:
                val = float(text.replace(",", "."))
            except ValueError:
                self._fill()
                return
            self.shop.set(bc.ShopEntry(mat, t, pr, val, die, "현장 측정"))
        self.dirty = True
        self._fill()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV 저장", f"연신표_{self.material.currentData()}.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["두께"] + [f"상형R{r:g}" for r in bc.STANDARD_PUNCH_R])
            for i in range(self.grid.rowCount()):
                w.writerow([bc.STANDARD_THICKNESSES[i]] +
                           [self.grid.item(i, j).text() for j in range(self.grid.columnCount())])

    def _materials_tab(self):
        rows = "".join(
            f"<tr><td>{m.code}</td><td>{m.name}</td><td>{bc.GROUP_NAMES[m.group]}</td>"
            f"<td align=right>{m.tensile_mpa:.0f}</td><td align=right>{m.air_ratio:.1%}</td>"
            f"<td>{m.note}</td></tr>" for m in bc.MATERIALS)
        k_rows = "".join(
            f"<tr><td>{bc.PROCESS_NAMES[p]}</td>" + "".join(
                f"<td align=center>{' / '.join(f'{v:.2f}' for v in bc.K_TABLE[p][g])}</td>"
                for g in (bc.SOFT, bc.MEDIUM, bc.HARD)) + "</tr>" for p in bc.K_TABLE)
        html = f"""
<h3>재질</h3>
<table border=1 cellspacing=0 cellpadding=3>
<tr><th>코드</th><th>이름</th><th>K 표 분류</th><th>대표 인장강도(MPa)</th>
<th>에어 벤딩 자연 R / V 폭</th><th>근거</th></tr>{rows}</table>
<p>대표 인장강도는 규격 하한~일반 납품값 사이의 어림값입니다. 밀시트 값이 있으면 그 값을 기준으로 보세요.</p>

<h3>K 계수 표 [1]</h3>
<table border=1 cellspacing=0 cellpadding=3>
<tr><th>가공</th><th>연질 (r≤t / ≤3t / &gt;3t)</th><th>중간</th><th>경질</th></tr>{k_rows}</table>

<h3>계산식</h3>
<ul>
<li>펼친 절곡부 길이 BA = θ × (R + K × t)</li>
<li>연신(굽힘 공제) BD = 2 × tan(θ/2) × (R + t) − BA &nbsp; (90° 이면 2(R+t) − BA)</li>
<li>전개 길이 = 바깥 치수 합 − Σ 연신</li>
<li>에어 벤딩 실제 R = max(상형 R, 자연 R),  자연 R = 하형 V 폭 × 재질 비율 [3]</li>
<li>DIN 6935: k = 0.65 + 0.5·log10(R/t) (R/t &lt; 5), 중립 K = k/2 [2]</li>
<li>회사 연신 표 값이 있으면 그 값에서 K 를 거꾸로 구해, 다른 각도에도 같은 K 를 씁니다.</li>
</ul>

<h3>참고 문헌</h3>
<ol>
<li>일반 K 계수 표 (에어·바텀·코이닝 / 연질·중간·경질). Machinery's Handbook 계열 표로,
여러 판금 실무서와 The Fabricator 절곡 기사에 같은 값이 실려 있습니다.</li>
<li>DIN 6935 Kaltbiegen von Flacherzeugnissen aus Stahl (및 Beiblatt 1) — 보정 계수 k.</li>
<li>The Fabricator 절곡 연재 "20% 규칙": 에어 벤딩 안쪽 R 은 하형 V 폭의 일정 비율
(냉연강 15~17%, SUS304 20~22%, AL5052-H32 약 11~13%), 다른 재질은 인장강도에 비례.</li>
</ol>
<p><b>문헌값은 출발점입니다.</b> 문헌들도 시험 절곡으로 확인하라고 권합니다.
현장에서 잰 연신을 [연신 표] 탭에 넣으면 그 값이 계산값보다 우선합니다.</p>
"""
        view = QTextBrowser()
        view.setHtml(html)
        return view


class MillDialog(QDialog):
    """밀시트 실측값 입력: 0 칸은 대표값."""

    def __init__(self, mat: bc.Material, values: dict, parent=None):
        super().__init__(parent)
        from . import diecalc as dc
        self.setWindowTitle(f"밀시트 실측값 — {mat.code}")
        rep = {"ys": dc.yield_strength(mat), "ts": mat.tensile_mpa, "el": 0, "n": mat.n, "r0": mat.r, "r45": mat.r,
               "r90": mat.r, "e": dc.modulus_gpa(mat)}
        form = QFormLayout()
        self.box = {}
        for key, name in bc.MILL_KEYS:
            dec = 3 if key in ("n", "r0", "r45", "r90") else 1 if key in ("el",) else 0
            sp = _spin(0.0, 3000.0 if key in ("ys", "ts") else 400.0 if key == "e" else 100.0 if key == "el" else 5.0,
                       dec, special="대표값")
            sp.setValue(float(values.get(key, 0) or 0))
            sp.setToolTip(f"대표값 {rep[key]:g}" if rep[key] else "")
            sp.valueChanged.connect(self._calc)
            self.box[key] = sp
            form.addRow(f"{name}  (대표 {rep[key]:g})" if rep[key] else name, sp)
        self.info = QLabel()
        self.info.setWordWrap(True)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Reset).setText("모두 대표값으로")
        bb.button(QDialogButtonBox.Reset).clicked.connect(lambda: [b.setValue(0) for b in self.box.values()])
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("밀시트 (소재 검사 증명서) 값을 넣으면 대표값 대신 씁니다. 0 = 대표값.\n"
                             "r 값 셋을 넣으면 평균 r̄ = (r0 + 2 r45 + r90)/4 와 면내 이방성 Δr 을 계산합니다."))
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addWidget(bb)
        self._calc()

    def values(self):
        return {k: b.value() for k, b in self.box.items() if b.value() > 0}

    def _calc(self, *_):
        v = self.values()
        out = []
        if all(k in v for k in ("r0", "r45", "r90")):
            rm, dr = bc.r_mean(v["r0"], v["r45"], v["r90"])
            out.append(f"r̄ = {rm:.3f} · Δr = {dr:+.3f}" + (" — 귀 (earing) 가 4 곳 생기기 쉬움" if abs(dr) > 0.2 else ""))
        if "ys" in v and "ts" in v:
            out.append(f"항복비 YS/TS = {v['ys'] / v['ts']:.2f}")
            if v["ys"] >= v["ts"]:
                out.append("⚠ 항복 강도가 인장 강도 이상 — 값을 확인하세요")
        self.info.setText(" · ".join(out))
