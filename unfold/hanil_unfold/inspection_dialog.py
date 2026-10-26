"""검사 성적서 창: 도면에서 뽑은 검사 항목 · 공차, 측정값 넣기 (붙여넣기·엑셀 읽기), 합격·불합격 · Cpk, 성적서 저장."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import inspection as ip

FIXED = ["번호", "구분", "검사 항목", "기준", "+공차", "−공차", "측정기"]
TAILS = ["평균", "σ", "Cpk", "판정", "공정 능력"]
EDITABLE = {1, 2, 3, 4, 5, 6}
OKC, NGC, GREY = QColor(207, 232, 207), QColor(244, 182, 182), QColor(245, 245, 245)


class InspectionDialog(QDialog):
    def __init__(self, ins: ip.Inspection, parent=None, history=None, items_db=None, source_path=""):
        super().__init__(parent)
        self.setWindowTitle(f"검사 성적서 — {ins.part_name}")
        self.resize(1400, 820)
        self.ins, self.history, self.items_db, self.source_path = ins, history, items_db, source_path
        self.st = QSettings("Hanil", "SheetUnfold")
        self._busy = False

        self.kind = QComboBox()
        self.kind.addItems(ip.KINDS)
        self.kind.setCurrentText(ins.kind)
        self.part_no = QLineEdit(ins.part_no)
        self.customer = QLineEdit(ins.customer or self.st.value("quote_customer", "") or "")
        self.lot = QLineEdit(ins.lot)
        self.lot.setPlaceholderText("예: 2026-10-25-A")
        self.inspector = QLineEdit(ins.inspector or self.st.value("inspector", "") or "")
        self.n = QSpinBox()
        self.n.setRange(1, ip.MAX_N)
        self.n.setValue(ins.n)
        self.n.setSuffix(" 개")
        self.n.valueChanged.connect(self._resize)
        self.cls = QComboBox()
        self.cls.addItems(["A (정밀)", "B (보통)", "C (거침)"])
        self.cls.setCurrentIndex(1)
        self.cls.setToolTip("JIS B 0408 보통 공차 등급 — 바꾸면 항목을 다시 만듭니다 (측정값 지움)")
        self.cls.activated.connect(self._reclass)
        self.item = QComboBox()
        self.item.addItem("(아이템 대장과 잇지 않음)", None)
        if items_db is not None:
            for r in items_db.search_items():
                d = r.data
                self.item.addItem(f"{d.get('customer') or ''} {d.get('part_no') or ''} {d.get('part_name') or ''}".strip(), r.id)
        self.item.currentIndexChanged.connect(self._item_changed)
        top = QHBoxLayout()
        f1, f2, f3 = QFormLayout(), QFormLayout(), QFormLayout()
        f1.addRow("검사 종류", self.kind)
        f1.addRow("공차 등급", self.cls)
        f2.addRow("고객", self.customer)
        f2.addRow("품번", self.part_no)
        f2.addRow("아이템", self.item)
        f3.addRow("로트", self.lot)
        f3.addRow("검사자", self.inspector)
        f3.addRow("시료 수", self.n)
        for f in (f1, f2, f3):
            w = QWidget()
            w.setLayout(f)
            top.addWidget(w, 1)
        self.verdict = QLabel()
        self.verdict.setAlignment(Qt.AlignCenter)
        self.verdict.setMinimumWidth(220)
        top.addWidget(self.verdict)

        self.table = QTableWidget()
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.itemChanged.connect(self._changed)
        self.table.verticalHeader().setVisible(False)
        hint = QLabel("<span style='color:#666'>측정값 칸에 숫자 (외관·밀시트는 OK / NG) — 엑셀·3차원 측정기 결과를 "
                      "복사해 <b>Ctrl+V</b> 로 붙여 넣을 수 있습니다. 공차 밖 값은 빨강. 기준·공차·측정기도 고칠 수 있습니다 "
                      "(도면 공차가 있으면 그 값으로).</span>")
        hint.setWordWrap(True)

        btns = QHBoxLayout()
        for text, fn in (("항목 추가", self._add), ("항목 지우기", self._delete), ("엑셀에서 측정값 읽기…", self._read),
                         ("엑셀 양식 내보내기…", lambda: self.save(blank=True))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        self.append = QCheckBox("같은 파일이 있으면 시트로 이어 쌓기 (이력)")
        self.append.setChecked(True)
        btns.addWidget(self.append)
        save = QPushButton("성적서 저장 (엑셀 + PDF)…")
        save.setStyleSheet("QPushButton { font-weight: bold; padding: 5px 14px; }")
        save.clicked.connect(lambda: self.save())
        btns.addWidget(save)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        btns.addWidget(close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(hint)
        lay.addWidget(self.table, 1)
        if ins.note:
            lay.addWidget(QLabel(f"<span style='color:#888'>{ins.note}</span>"))
        lay.addLayout(btns)
        self._fill()

    # ---------------------------------------------------------- 표
    def _cols(self):
        n = self.ins.n
        return FIXED + [f"S{k}" for k in range(1, n + 1)] + TAILS

    def _fill(self):
        self._busy = True
        t = self.table
        cols = self._cols()
        t.clear()
        t.setColumnCount(len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.setRowCount(len(self.ins.chars))
        for r, c in enumerate(self.ins.chars):
            row = [str(c.no), c.group, c.name, "" if c.nominal is None else f"{c.nominal:g}",
                   "" if c.kind in (ip.ATTR, ip.MIN) else f"{c.upper:g}",
                   "" if c.kind in (ip.ATTR, ip.MAX) else f"{c.lower:g}", c.gauge]
            for j, v in enumerate(row):
                it = QTableWidgetItem(v)
                if j not in EDITABLE:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if j == 2:
                    it.setToolTip(f"{c.spec_text()} · 근거: {c.source}")
                t.setItem(r, j, it)
            for k in range(self.ins.n):
                v = c.values[k] if k < len(c.values) else None
                t.setItem(r, len(FIXED) + k, QTableWidgetItem("" if v in (None, "") else
                                                               str(v) if c.kind == ip.ATTR else f"{float(v):g}"))
            for j in range(len(TAILS)):
                it = QTableWidgetItem("")
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(r, len(FIXED) + self.ins.n + j, it)
            self._row(r)
        h = t.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        for j, w in enumerate([40, 55, 300, 70, 55, 55, 150]):
            t.setColumnWidth(j, w)
        for k in range(self.ins.n):
            t.setColumnWidth(len(FIXED) + k, 64)
        for j, w in enumerate([72, 60, 52, 60, 150]):
            t.setColumnWidth(len(FIXED) + self.ins.n + j, w)
        self._busy = False
        self._summary()

    def _row(self, r):
        """한 줄의 판정 색 · 통계."""
        c = self.ins.chars[r]
        t = self.table
        base = len(FIXED)
        for k in range(self.ins.n):
            it = t.item(r, base + k)
            if it is None:
                continue
            j = c.judge(c.values[k] if k < len(c.values) else None)
            it.setBackground(NGC if j == "NG" else QColor(255, 255, 255))
        s = ip.stats(c)
        tail = ["" if s.mean is None else f"{s.mean:.3f}", "" if s.sd is None else f"{s.sd:.3f}",
                "" if s.cpk is None else f"{s.cpk:.2f}", s.verdict, s.capability]
        for j, v in enumerate(tail):
            it = t.item(r, base + self.ins.n + j)
            it.setText(v)
            if j == 3:
                it.setBackground(NGC if v == "불합격" else OKC if v == "합격" else QColor(255, 255, 255))
            if j == 2:
                it.setForeground(QColor(210, 40, 40) if s.cpk is not None and s.cpk < 1.33 else QColor(20, 20, 20))
        for j in range(len(FIXED)):
            it = t.item(r, j)
            if it is not None and j not in EDITABLE:
                it.setBackground(GREY)

    def _summary(self):
        ins = self.ins
        v = ins.verdict
        col = {"합격": "#2a8c3c", "불합격": "#d22828"}.get(v, "#888")
        ks = ins.cpk_min()
        ng = ins.ng_chars()
        self.verdict.setText(f"<div style='font-size:26px; color:{col}'><b>{v}</b></div>"
                             f"<div>불합격 {len(ng)} 항목" + (f" · 최저 Cpk {ks:.2f}" if ks is not None else "") + "</div>"
                             + ("<div style='color:#d22828'>" + ", ".join(str(c.no) for c in ng[:12]) + "</div>" if ng else ""))

    def _changed(self, it):
        if self._busy:
            return
        r, j = it.row(), it.column()
        c = self.ins.chars[r]
        txt = it.text().strip()
        base = len(FIXED)
        if base <= j < base + self.ins.n:
            k = j - base
            if c.kind == ip.ATTR:
                c.values[k] = txt.upper() if txt else None
            else:
                try:
                    c.values[k] = float(txt.replace(",", "")) if txt else None
                except ValueError:
                    c.values[k] = None
                    self._busy = True
                    it.setText("")
                    self._busy = False
        elif j in EDITABLE:
            num = None
            try:
                num = float(txt) if txt else None
            except ValueError:
                pass
            if j == 1:
                c.group = txt
            elif j == 2:
                c.name = txt
            elif j == 3:
                c.nominal = num
                if num is None:
                    c.kind = ip.ATTR
                elif c.kind == ip.ATTR:
                    c.kind = ip.VAR
            elif j == 4:
                c.upper = abs(num) if num is not None else 0.0
                if num is None and c.kind == ip.VAR:
                    c.kind = ip.MIN
                elif num is not None and c.kind == ip.MIN:
                    c.kind = ip.VAR
            elif j == 5:
                c.lower = -abs(num) if num is not None else 0.0
                if num is None and c.kind == ip.VAR:
                    c.kind = ip.MAX
                elif num is not None and c.kind == ip.MAX:
                    c.kind = ip.VAR
            elif j == 6:
                c.gauge = txt
        self._busy = True
        self._row(r)
        self._busy = False
        self._summary()

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Paste) and self.table.hasFocus():
            self._paste()
            return
        super().keyPressEvent(e)

    def _paste(self):
        """엑셀·측정기 결과 (탭·줄 바꿈) 를 지금 칸부터 붙여 넣기."""
        text = QApplication.clipboard().text()
        if not text:
            return
        r0, c0 = max(self.table.currentRow(), 0), max(self.table.currentColumn(), len(FIXED))
        rows = [ln.split("\t") for ln in text.rstrip("\n").split("\n")]
        for i, cells in enumerate(rows):
            for j, v in enumerate(cells):
                r, c = r0 + i, c0 + j
                if r < self.table.rowCount() and c < len(FIXED) + self.ins.n:
                    it = self.table.item(r, c)
                    if it is not None and it.flags() & Qt.ItemIsEditable:
                        it.setText(v.strip())

    def _resize(self, n):
        self.ins.resize(n)
        self._fill()

    def _reclass(self, *_):
        cls = "ABC"[self.cls.currentIndex()]
        if not getattr(self, "rebuild", None):
            return
        if any(c.values and any(v not in (None, "") for v in c.values) for c in self.ins.chars):
            if QMessageBox.question(self, "공차 등급", "항목을 다시 만들면 넣은 측정값이 지워집니다. 계속할까요?") != \
                    QMessageBox.Yes:
                return
        new = self.rebuild(cls)
        new.resize(self.ins.n)
        self.ins.chars, self.ins.note = new.chars, new.note
        self._fill()

    def _add(self):
        name, ok = QInputDialog.getText(self, "항목 추가", "검사 항목 (예: 구멍 피치, 평면도, 버 높이)")
        if not ok or not name.strip():
            return
        r = self.table.currentRow()
        at = r + 1 if r >= 0 else len(self.ins.chars)
        self.ins.chars.insert(at, ip.Char(0, "추가", name.strip(), 0.0, 0.1, -0.1, ip.VAR, "", "도면",
                                          values=[None] * self.ins.n))
        self.ins.renumber()
        self._fill()
        self.table.setCurrentCell(at, 3)

    def _delete(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            del self.ins.chars[r]
        self.ins.renumber()
        self._fill()

    def _item_changed(self, *_):
        rid = self.item.currentData()
        if rid is None or self.items_db is None:
            return
        it = self.items_db.get_item(rid)
        if it is not None:
            if it.data.get("customer"):
                self.customer.setText(it.data["customer"])
            if it.data.get("part_no"):
                self.part_no.setText(it.data["part_no"])

    def _read(self):
        path, _ = QFileDialog.getOpenFileName(self, "측정값이 든 성적서 엑셀", self.st.value("inspection_dir", ""),
                                              "엑셀 (*.xlsx)")
        if not path:
            return
        try:
            got = ip.read_xlsx(path)
        except Exception as e:
            QMessageBox.warning(self, "엑셀 읽기", str(e))
            return
        # 같은 번호 · 같은 이름 항목에 값을 옮김 (없는 항목은 새로)
        by = {(c.no, c.name): c for c in self.ins.chars}
        n = max(self.ins.n, got.n)
        self.ins.resize(n)
        moved = 0
        for g in got.chars:
            c = by.get((g.no, g.name))
            if c is None:
                g.values = (g.values + [None] * n)[:n]
                self.ins.chars.append(g)
            else:
                c.values = (g.values + [None] * n)[:n]
                c.nominal, c.upper, c.lower, c.kind = g.nominal, g.upper, g.lower, g.kind
            moved += 1
        self.ins.renumber()
        self.n.blockSignals(True)
        self.n.setValue(n)
        self.n.blockSignals(False)
        for w, v in ((self.lot, got.lot), (self.inspector, got.inspector), (self.part_no, got.part_no)):
            if v and not w.text():
                w.setText(v)
        self._fill()
        QMessageBox.information(self, "엑셀 읽기", f"{os.path.basename(path)} 의 마지막 회차 시트에서 "
                                                f"{moved} 항목을 읽었습니다.")

    # ---------------------------------------------------------- 저장
    def _sync(self):
        ins = self.ins
        ins.kind, ins.part_no, ins.customer = self.kind.currentText(), self.part_no.text().strip(), self.customer.text().strip()
        ins.lot, ins.inspector = self.lot.text().strip(), self.inspector.text().strip()
        self.st.setValue("inspector", ins.inspector)

    def save(self, blank=False):
        import copy
        import datetime as _dt
        self._sync()
        ins = copy.deepcopy(self.ins)
        ins.when = _dt.datetime.now().replace(microsecond=0)
        if blank:
            for c in ins.chars:
                c.values = [None] * ins.n
        base = os.path.join(self.st.value("inspection_dir", "") or os.path.dirname(self.source_path or ""),
                            f"{os.path.splitext(ins.part_name or 'part')[0]}_검사성적서.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "검사 성적서 양식" if blank else "검사 성적서 저장", base, "엑셀 (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        self.st.setValue("inspection_dir", os.path.dirname(path))
        out = [path]
        try:
            sheet = ip.save_xlsx(ins, path, append=self.append.isChecked())
            if not blank:
                pdf = os.path.splitext(path)[0] + f"_{ins.when:%Y%m%d_%H%M}.pdf"
                ip.save_pdf(ins, pdf)
                out.append(pdf)
        except PermissionError:
            QMessageBox.warning(self, "검사 성적서", "파일이 열려 있어 저장하지 못했습니다 — 엑셀에서 닫고 다시 하세요.")
            return
        except Exception as e:
            QMessageBox.warning(self, "검사 성적서 저장 실패", str(e))
            return
        if not blank:
            self._log(ins, out)
        QMessageBox.information(self, "검사 성적서", ("양식을" if blank else "저장했습니다") +
                                f"\n{os.path.basename(path)} [{sheet}]" + "\n".join([""] + out[1:]))
        QDesktopServices.openUrl(QUrl.fromLocalFile(out[-1]))

    def _log(self, ins, files):
        if self.history is None:
            return
        try:
            v, detail = ip.record(ins)
            self.history.add_doc("검사 성적서", files, self.source_path, v, detail)
        except Exception:
            import traceback
            traceback.print_exc()
        rows = ip.calibration_rows(ins)
        store = getattr(self.history, "calib", None)
        if rows and store is not None and QMessageBox.question(
                self, "실적 보정", f"성형 부위 두께 {len(rows)} 항목을 [실적 보정] (얇아짐) 기록에 넣을까요?\n"
                "넣으면 기록이 3 개 넘을 때부터 성형 해석 얇아짐에 보정 계수가 곱해집니다.") == QMessageBox.Yes:
            for cond, pred, act in rows:
                store.add("thinning", ins.material, ins.part_name, round(pred, 3), round(act, 3), cond,
                          f"검사 성적서 {ins.kind} {ins.lot}".strip())
            from . import calibration
            calibration.load(store)
