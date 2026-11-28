"""실적 보정 창: 종류마다 예측 · 실측 기록, 묶음별 보정 계수 (95 % 범위 · 흩어짐), 켜고 끄기."""
from __future__ import annotations

import math
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from . import calibration as cal

HELP = {
    "springback": "절곡을 시험 타발한 뒤 각도기로 잰 <b>되돌아간 양</b> (접은 각 − 잰 각, °) 을 넣습니다. "
                  "[지금 부품 예측값] 은 절곡마다 예측 스프링백을 넣어 줍니다. 묶음 = 재질 (재질마다 따로 맞춤).",
    "thinning": "성형품을 잘라 (또는 초음파 두께계) 잰 가장 얇은 곳의 <b>얇아짐 %</b> (= (t − 잰 두께)/t × 100). "
                "검사 성적서의 성형 부위 두께를 저장할 때도 여기에 넣을 수 있습니다. 묶음 = 재질.",
    "tonnage": "프레스 하중 모니터 (로드 모니터) 로 잰 <b>최대 하중 tf</b>. 예측은 여유 30 % 를 빼고 비교합니다. "
               "묶음 = 드로잉 / 성형 / 전단·굽힘.",
    "cycle": "실제 생산의 <b>1 타 (프레스) · 1 회 (절곡) · 1 장 (레이저) 시간 초</b> — 견적서 공정 시간과 견줍니다. "
             "묶음 = 기계 이름 (기계·임률 표의 이름).",
    "die_cost": "금형 업체 실제 <b>금형비 (원)</b> 와 이 프로그램 금형 견적서 금액. 묶음 = 구조·형식 "
                "(강판 순차, 주물 단발 …).",
}
KEY_CHOICES = {"tonnage": ["드로잉", "성형", "전단·굽힘"],
               "die_cost": [f"{s} {k}" for s in ("강판", "주물") for k in ("순차", "트랜스퍼", "복합", "단발")]}
HEAD = ["번호", "날짜", "묶음", "부품", "조건", "예측", "실측", "실측/예측", "메모", "씀"]


class _Tab(QWidget):
    def __init__(self, dlg, kind):
        super().__init__()
        self.dlg, self.kind = dlg, kind
        name, unit, keyname = cal.KINDS[kind]
        self.on = QCheckBox(f"{name} 보정 쓰기 (기록 {cal.MIN_N} 개 이상인 묶음)")
        self.on.setChecked(dlg.store.enabled(kind))
        self.on.toggled.connect(lambda v: (dlg.store.set_enabled(kind, v), self.refresh()))
        help_ = QLabel(HELP[kind])
        help_.setWordWrap(True)
        help_.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
        self.fits = QTableWidget()
        self.fits.setColumnCount(8)
        self.fits.setHorizontalHeaderLabels([keyname, "기록", "보정 계수 k", "비 평균", "95 % 범위", "흩어짐 CV",
                                             "상태", "뜻"])
        self.fits.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fits.verticalHeader().setVisible(False)
        self.fits.setMaximumHeight(170)
        self.table = QTableWidget()
        self.table.setColumnCount(len(HEAD))
        self.table.setHorizontalHeaderLabels([h if h not in ("예측", "실측") else f"{h} ({unit})" for h in HEAD])
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._edited)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        btns = QHBoxLayout()
        for text, fn in (("지금 부품 예측값 넣기", self._from_part), ("빈 줄 추가", self._blank), ("지우기", self._delete)):
            if text.startswith("지금") and kind in ("cycle", "die_cost"):
                continue
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addWidget(self.on)
        lay.addWidget(help_)
        lay.addWidget(QLabel("보정 계수 (묶음별)"))
        lay.addWidget(self.fits)
        lay.addWidget(QLabel("기록 — 실측 칸을 채우면 계수가 바로 다시 계산됩니다"))
        lay.addWidget(self.table, 1)
        lay.addLayout(btns)
        self._busy = False
        self.refresh()

    def refresh(self):
        self._busy = True
        recs = self.dlg.store.records(self.kind)
        t = self.table
        t.setRowCount(len(recs))
        for i, r in enumerate(recs):
            vals = [str(r.id), r.created[:10], r.key, r.part, r.condition, f"{r.predicted:g}",
                    "" if r.actual is None or (r.actual == 0 and r.note == "실측 대기") else f"{r.actual:g}",
                    "" if not r.predicted or r.note == "실측 대기" else f"{r.ratio:.3f}", r.note, ""]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (0, 1, 7):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    it.setBackground(QColor(245, 245, 245))
                if j == 9:
                    it = QTableWidgetItem()
                    it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    it.setCheckState(Qt.Checked if r.used else Qt.Unchecked)
                it.setData(Qt.UserRole, r.id)
                t.setItem(i, j, it)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        for j, w in enumerate([50, 85, 110, 140, 0, 90, 90, 80, 120, 40]):
            if w:
                t.setColumnWidth(j, w)
        fits = self.dlg.store.fits(self.kind)
        f = self.fits
        f.setRowCount(len(fits))
        unit = cal.KINDS[self.kind][1]
        for i, (key, ft) in enumerate(fits):
            nan = lambda x: x is None or (isinstance(x, float) and math.isnan(x))  # noqa: E731
            used = ft.k is not None and self.on.isChecked() and not (key == cal.ALL and self.kind in cal.PER_KEY_ONLY)
            meaning = ""
            if ft.k is not None:
                meaning = (f"실제가 예측보다 {abs(ft.k - 1):.0%} {'큼' if ft.k > 1 else '작음'} → 예측에 ×{ft.k:.2f}"
                           if abs(ft.k - 1) > 0.005 else "예측이 맞음")
            if key == cal.ALL and self.kind in cal.PER_KEY_ONLY:
                meaning = "참고 (재질마다 따로 씀)"
            row = ["전체" if key == cal.ALL else key, str(ft.n), "" if ft.k is None else f"{ft.k:.3f}",
                   "" if nan(ft.mean) else f"{ft.mean:.3f}",
                   "" if nan(ft.lo) else f"{ft.lo:.2f} ~ {ft.hi:.2f}",
                   "" if nan(ft.cv) or ft.n < 2 else f"{ft.cv:.0%}",
                   ("쓰는 중" if used else "참고" if key == cal.ALL and self.kind in cal.PER_KEY_ONLY
                    else ft.status if ft.k is None else "꺼짐"),
                   meaning]
            for j, v in enumerate(row):
                it = QTableWidgetItem(v)
                if j == 6:
                    it.setForeground(QColor(40, 140, 60) if used else QColor(150, 150, 150))
                if j == 5 and not nan(ft.cv) and ft.cv > 0.25:
                    it.setForeground(QColor(210, 40, 40))
                    it.setToolTip(f"흩어짐이 큼 ({unit}) — 조건이 다른 기록이 섞였을 수 있음 (묶음을 나누세요)")
                f.setItem(i, j, it)
        f.resizeColumnsToContents()
        self._busy = False

    def _edited(self, it):
        if self._busy:
            return
        rid = it.data(Qt.UserRole)
        j = it.column()
        st = self.dlg.store
        if j == 9:
            st.update(rid, used=it.checkState() == Qt.Checked)
        else:
            txt = it.text().strip()
            if j in (5, 6):
                try:
                    v = float(txt.replace(",", ""))
                except ValueError:
                    self.refresh()
                    return
                kw = {"predicted" if j == 5 else "actual": v}
                if j == 6:
                    rec = next((r for r in st.records(self.kind) if r.id == rid), None)
                    if rec is not None and rec.note == "실측 대기":
                        kw["note"] = ""
                st.update(rid, **kw)
            else:
                st.update(rid, **{{2: "key", 3: "part", 8: "note"}.get(j, "note"): txt})
        self.refresh()

    def _from_part(self):
        d = self.dlg
        if d.result is None:
            QMessageBox.information(self, "실적 보정", "먼저 부품을 전개하세요.")
            return
        rows = cal.predictions(self.kind, d.result, d.settings, d.name)
        if not rows:
            QMessageBox.information(self, "실적 보정", "이 부품에서 뽑을 예측값이 없습니다 "
                                                   "(스프링백은 절곡, 얇아짐은 성형품).")
            return
        for key, cond, pred in rows:
            d.store.add(self.kind, key, d.name, round(pred, 3), 0.0, cond, "실측 대기")
        self.refresh()
        QMessageBox.information(self, "실적 보정", f"{len(rows)} 줄을 넣었습니다 — 실측 칸을 채우세요 "
                                               "(실측이 빈 줄은 '실측 대기' 로 계수에서 빠짐).")

    def _blank(self):
        key = (KEY_CHOICES.get(self.kind) or [self.dlg.settings.mat.code if self.dlg.settings else cal.ALL])[0]
        if self.kind == "cycle" and self.dlg.machines:
            key = self.dlg.machines[0]
        self.dlg.store.add(self.kind, key, self.dlg.name, 1.0, 0.0, "", "실측 대기")
        self.refresh()
        self.table.scrollToBottom()

    def _delete(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        for r in rows:
            self.dlg.store.delete(self.table.item(r, 0).data(Qt.UserRole))
        self.refresh()


class CalibrationDialog(QDialog):
    def __init__(self, store: cal.Store, result=None, settings=None, name="", machines=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle("실적 보정 — 예측과 실측으로 계수 맞추기")
        self.resize(1150, 760)
        self.store, self.result, self.settings, self.name = store, result, settings, name
        self.machines = list(machines)
        top = QLabel("시험 타발·양산에서 잰 값을 넣으면 프로그램 예측과 견줘 <b>보정 계수 k = Σ(예측·실측)/Σ(예측²)</b> 를 "
                     f"구하고, 기록이 {cal.MIN_N} 개 이상인 묶음부터 다음 계산에 곱합니다 (스프링백 · 얇아짐 · 프레스 하중 · "
                     "공정 시간 · 금형비). 쓰인 곳에는 '실적 보정 ×k' 가 표시됩니다.")
        top.setWordWrap(True)
        self.tabs = QTabWidget()
        self.pages = {}
        for kind, (nm, unit, _) in cal.KINDS.items():
            pg = _Tab(self, kind)
            self.pages[kind] = pg
            self.tabs.addTab(pg, f"{nm} ({unit})")
        btns = QHBoxLayout()
        b = QPushButton("엑셀로…")
        b.clicked.connect(self._xlsx)
        btns.addWidget(b)
        btns.addStretch(1)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(top)
        lay.addWidget(self.tabs, 1)
        lay.addLayout(btns)

    def _xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "실적 보정 엑셀", "실적보정.xlsx", "엑셀 (*.xlsx)")
        if path:
            cal.save_xlsx(self.store, path)
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def done(self, r):
        cal.load(self.store)            # 닫을 때 계수를 다시 읽어 바로 씀
        super().done(r)
