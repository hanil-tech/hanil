"""견적 창: 공정수·재료비·가공비·부자재를 보고 고친 뒤 견적서 초안 (엑셀·PDF) 저장."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import quote as qt_

EDIT_BG = QColor(255, 250, 220)


def _num(text, default=0.0):
    try:
        return float(str(text).replace(",", "").replace("원", "").strip() or default)
    except ValueError:
        return default


def _item(v, editable=False, right=False):
    it = QTableWidgetItem(v if isinstance(v, str) else (f"{v:,.0f}" if isinstance(v, float) else str(v)))
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    else:
        it.setBackground(EDIT_BG)
    if right or not isinstance(v, str):
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


def _table(head):
    t = QTableWidget(0, len(head))
    t.setHorizontalHeaderLabels(head)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class QuoteDialog(QDialog):
    def __init__(self, model, parts, settings, excluded=(), title="", parent=None):
        super().__init__(parent)
        from . import bom
        self.setWindowTitle(f"견적 — {title}")
        self.resize(1200, 760)
        self.model, self.parts, self.settings, self.title = model, parts, settings, title
        self.st = QSettings("Hanil", "SheetUnfold")
        self.rates = qt_.load_rates(self.st.value("quote_rates", ""))
        self.items = bom.build(model, parts, settings.mat.density, excluded, settings.mat.code)
        self.cache = {}
        self.overrides = {}          # 품번 → 가공비 직접 입력
        self.sub_prices = json.loads(self.st.value("quote_sub_prices", "{}") or "{}")
        self.extra_subs = []         # 직접 넣은 부자재 SubItem
        self._busy = False

        # 위: 조건
        top = QHBoxLayout()
        self.sets = QSpinBox()
        self.sets.setRange(1, 10_000_000)
        self.sets.setValue(1)
        self.sets.setSuffix(" 세트")
        self.annual = QSpinBox()
        self.annual.setRange(1, 100_000_000)
        self.annual.setSingleStep(10_000)
        self.annual.setGroupSeparatorShown(True)
        self.annual.setValue(int(self.st.value("quote_annual", 1_000)))
        self.annual.setSuffix(" 개/년")
        self.customer = QLineEdit(self.st.value("quote_customer", "") or "")
        self.customer.setPlaceholderText("수신 업체")
        self.amort = QCheckBox("금형비를 세트 단가에 나눠 넣기")
        self.extra = QDoubleSpinBox()
        self.extra.setRange(0, 1e9)
        self.extra.setDecimals(0)
        self.extra.setGroupSeparatorShown(True)
        self.extra.setSuffix(" 원/세트")
        for lab, w in (("견적 수량", self.sets), ("연간 생산량", self.annual), ("수신", self.customer),
                       ("조립·용접·도장 등", self.extra)):
            top.addWidget(QLabel(lab))
            top.addWidget(w)
        top.addWidget(self.amort)
        top.addStretch(1)

        tabs = QTabWidget()
        self.sum_label = QLabel()
        self.sum_label.setTextFormat(Qt.RichText)
        self.sum_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.sum_label.setWordWrap(True)
        w0 = QWidget()
        QVBoxLayout(w0).addWidget(self.sum_label)
        tabs.addTab(w0, "요약")

        self.t_parts = _table(["품번", "품명", "수량/세트", "구분", "재질·두께", "공정 방식", "공정수", "공정",
                               "제품 kg", "소요 kg", "재료비/개", "가공비/개 (고칠 수 있음)", "단가/개",
                               "세트 금액", "금형비", "비고"])
        self.t_parts.itemChanged.connect(self._part_edited)
        tabs.addTab(self.t_parts, "부품별 (공정·재료비)")

        w2 = QWidget()
        l2 = QVBoxLayout(w2)
        self.t_subs = _table(["품명", "규격", "수량/세트", "단위", "단가 (원)", "금액", "비고"])
        self.t_subs.itemChanged.connect(self._sub_edited)
        l2.addWidget(QLabel("노란 칸을 고치세요. 같은 이름 부자재의 단가는 기억합니다."))
        l2.addWidget(self.t_subs)
        row = QHBoxLayout()
        add = QPushButton("줄 넣기 (도장·포장·볼트 …)")
        add.clicked.connect(self._add_sub)
        rem = QPushButton("넣은 줄 지우기")
        rem.clicked.connect(self._remove_sub)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        l2.addLayout(row)
        tabs.addTab(w2, "부자재")

        tabs.addTab(self._rates_tab(), "단가표")

        btns = QHBoxLayout()
        xl = QPushButton("견적서 엑셀…")
        pdf = QPushButton("견적서 PDF…")
        xl.clicked.connect(lambda: self.save("xlsx"))
        pdf.clicked.connect(lambda: self.save("pdf"))
        btns.addWidget(QLabel("단가는 예시값입니다 — [단가표] 에서 회사 단가로 바꾸면 저장됩니다."))
        btns.addStretch(1)
        btns.addWidget(xl)
        btns.addWidget(pdf)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(tabs, 1)
        lay.addLayout(btns)
        self.tabs = tabs

        for w in (self.sets, self.annual, self.extra):
            w.valueChanged.connect(self.recalc)
        self.amort.toggled.connect(self.recalc)
        self.recalc()

    # ---- 단가표
    def _rates_tab(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        self.t_mat = _table(["재질", "원/kg"])
        for code, v in self.rates["material"].items():
            r = self.t_mat.rowCount()
            self.t_mat.insertRow(r)
            self.t_mat.setItem(r, 0, _item(code))
            self.t_mat.setItem(r, 1, _item(float(v), True))
        self.t_mat.itemChanged.connect(self._rates_edited)
        lay.addWidget(self.t_mat, 1)
        form = QFormLayout()
        self.rate_spins = {}
        for k, name in qt_.RATE_NAMES.items():
            s = QDoubleSpinBox()
            s.setRange(0, 1e10)
            s.setDecimals(2 if k in ("laser_t",) or k.endswith("pct") else 0)
            s.setGroupSeparatorShown(True)
            s.setValue(float(self.rates[k]))
            s.valueChanged.connect(self._rates_edited)
            self.rate_spins[k] = s
            form.addRow(name, s)
        self.sup_edits = {}
        for k in ("대표", "주소", "전화", "사업자번호", "담당"):
            e = QLineEdit(self.rates["supplier"].get(k, ""))
            e.editingFinished.connect(self._rates_edited)
            self.sup_edits[k] = e
            form.addRow(f"공급자 {k}", e)
        reset = QPushButton("예시값으로 되돌리기")
        reset.clicked.connect(self._reset_rates)
        form.addRow("", reset)
        box = QWidget()
        box.setLayout(form)
        lay.addWidget(box, 1)
        return w

    def _rates_edited(self, *_):
        if self._busy:
            return
        for r in range(self.t_mat.rowCount()):
            self.rates["material"][self.t_mat.item(r, 0).text()] = _num(self.t_mat.item(r, 1).text())
        for k, s in self.rate_spins.items():
            self.rates[k] = s.value()
        for k, e in self.sup_edits.items():
            self.rates["supplier"][k] = e.text()
        self.st.setValue("quote_rates", json.dumps(self.rates, ensure_ascii=False))
        self.recalc()

    def _reset_rates(self):
        self.rates = qt_.load_rates(None)
        self._busy = True
        for r in range(self.t_mat.rowCount()):
            code = self.t_mat.item(r, 0).text()
            self.t_mat.item(r, 1).setText(f"{self.rates['material'].get(code, 0):,.0f}")
        for k, s in self.rate_spins.items():
            s.setValue(float(self.rates[k]))
        self._busy = False
        self._rates_edited()

    # ---- 계산
    def build_quote(self):
        q = qt_.build(self.model, self.parts, self.settings, self.rates, self.sets.value(), self.annual.value(),
                      title=self.title, items=self.items, cache=self.cache)
        for p in q.parts:
            p.process_override = self.overrides.get(p.no)
        for s in q.subs:
            s.unit_price = float(self.sub_prices.get(s.name, 0.0))
        q.subs += self.extra_subs
        q.amortize_die = self.amort.isChecked()
        q.customer = self.customer.text().strip()
        q.extra = self.extra.value()
        return q

    def recalc(self, *_):
        if self._busy:
            return
        self.q = q = self.build_quote()
        self._busy = True
        try:
            self._fill_parts(q)
            self._fill_subs(q)
        finally:
            self._busy = False
        r = q.rates
        lines = [
            f"<h2>세트 단가 {qt_.won(q.unit_price)} 원 · 견적 합계 {qt_.won(q.total)} 원 (부가세 포함)</h2>",
            f"자작 부품 {len(q.parts)}종 · <b>공정 합계 {q.total_ops}</b> · 부자재 {len(q.subs)}종 · "
            f"견적 수량 {q.sets:,} 세트 · 연간 {q.annual:,} 개 기준",
            "<table cellpadding=4>",
            f"<tr><td>재료비</td><td align=right>{qt_.won(q.material)}</td></tr>",
            f"<tr><td>가공비 (조립 등 포함)</td><td align=right>{qt_.won(q.process)}</td></tr>",
            f"<tr><td>부자재비</td><td align=right>{qt_.won(q.sub_total)}</td></tr>",
            f"<tr><td>금형비 상각</td><td align=right>{qt_.won(q.die_per_set)}</td></tr>",
            f"<tr><td><b>제조원가</b></td><td align=right><b>{qt_.won(q.manufacturing)}</b></td></tr>",
            f"<tr><td>일반관리비 {r['overhead_pct']:g} %</td><td align=right>{qt_.won(q.overhead)}</td></tr>",
            f"<tr><td>이윤 {r['profit_pct']:g} %</td><td align=right>{qt_.won(q.profit)}</td></tr>",
            f"<tr><td><b>세트 단가</b></td><td align=right><b>{qt_.won(q.unit_price)}</b></td></tr>",
            f"<tr><td>× {q.sets:,} 세트 + 금형비 {'(상각함)' if q.amortize_die else qt_.won(q.die_total)}"
            f"</td><td align=right>{qt_.won(q.supply)}</td></tr>",
            f"<tr><td>부가세 {r['vat_pct']:g} %</td><td align=right>{qt_.won(q.vat)}</td></tr>",
            f"<tr><td><b>합계</b></td><td align=right><b>{qt_.won(q.total)}</b></td></tr></table>",
            f"<p>일금 <b>{qt_.korean_amount(q.total)}</b>원정</p>",
        ]
        zero = [s.name for s in q.subs if not s.unit_price]
        if zero:
            lines.append(f"<p style='color:#c80'>⚠ 단가가 0 인 부자재 {len(zero)}개: "
                         + ", ".join(zero[:8]) + (" …" if len(zero) > 8 else "") + " — [부자재] 에서 넣으세요.</p>")
        rough = [p.name for p in q.parts if p.note.startswith("가공비는")]
        if rough:
            lines.append(f"<p style='color:#c80'>⚠ 기계 가공 부품 {len(rough)}개는 가공비가 무게 어림입니다.</p>")
        self.sum_label.setText("".join(lines))

    def _fill_parts(self, q):
        t = self.t_parts
        t.setRowCount(len(q.parts))
        for i, p in enumerate(q.parts):
            vals = [p.no, p.name, p.qty, p.category, p.spec, p.method, p.n_ops, " → ".join(p.ops),
                    f"{p.weight:.3f}", f"{p.gross_kg:.3f}", float(p.material), None, float(p.unit),
                    float(p.amount), float(p.die_cost), p.note]
            for j, v in enumerate(vals):
                if j == 11:
                    it = _item(float(p.process_cost), True)
                    if p.process_override is not None:
                        it.setForeground(QColor(200, 60, 0))
                else:
                    it = _item(v, right=j in (8, 9))
                t.setItem(i, j, it)

    def _fill_subs(self, q):
        t = self.t_subs
        t.setRowCount(len(q.subs))
        n_bom = len(q.subs) - len(self.extra_subs)
        for i, s in enumerate(q.subs):
            mine = i >= n_bom
            vals = [s.name, s.spec, s.qty, s.unit, float(s.unit_price), float(s.amount), s.note]
            for j, v in enumerate(vals):
                t.setItem(i, j, _item(v, editable=(j == 4 or j == 2 and mine or j in (0, 1, 3) and mine)))

    def _part_edited(self, it):
        if self._busy or it.column() != 11:
            return
        no = int(self.t_parts.item(it.row(), 0).text())
        txt = it.text().strip()
        self.overrides[no] = None if txt == "" else _num(txt)
        if self.overrides[no] is None:
            del self.overrides[no]
        self.recalc()

    def _sub_edited(self, it):
        if self._busy:
            return
        n_bom = self.t_subs.rowCount() - len(self.extra_subs)
        r, c = it.row(), it.column()
        name = self.t_subs.item(r, 0).text()
        if r >= n_bom:
            s = self.extra_subs[r - n_bom]
            if c == 0:
                s.name = it.text()
            elif c == 1:
                s.spec = it.text()
            elif c == 2:
                s.qty = _num(it.text(), 1)
            elif c == 3:
                s.unit = it.text()
            elif c == 4:
                s.unit_price = _num(it.text())
        elif c == 4:
            self.sub_prices[name] = _num(it.text())
            self.st.setValue("quote_sub_prices", json.dumps(self.sub_prices, ensure_ascii=False))
        self.recalc()

    def _add_sub(self):
        self.extra_subs.append(qt_.SubItem("도장 (분체)", "", 1, 0.0, "식", "직접 입력"))
        self.recalc()
        self.t_subs.scrollToBottom()

    def _remove_sub(self):
        if self.extra_subs:
            self.extra_subs.pop()
            self.recalc()

    def save(self, kind):
        self.st.setValue("quote_annual", self.annual.value())
        self.st.setValue("quote_customer", self.customer.text())
        base = os.path.splitext(self.model.path)[0] + f"_견적서.{kind}"
        path, _ = QFileDialog.getSaveFileName(self, "견적서 저장", base,
                                              "엑셀 (*.xlsx)" if kind == "xlsx" else "PDF (*.pdf)")
        if not path:
            return
        try:
            (qt_.save_xlsx if kind == "xlsx" else qt_.save_pdf)(self.q, path)
        except Exception as e:
            QMessageBox.warning(self, "견적서 저장 실패", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
