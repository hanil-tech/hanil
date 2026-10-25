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
    def __init__(self, model, parts, settings, excluded=(), title="", parent=None, history=None):
        super().__init__(parent)
        from . import bom
        self.setWindowTitle(f"견적 — {title}")
        self.resize(1200, 760)
        self.model, self.parts, self.settings, self.title = model, parts, settings, title
        self.history = history
        self.st = QSettings("Hanil", "SheetUnfold")
        self.rates = qt_.load_rates(self.st.value("quote_rates", ""))
        self.items = bom.build(model, parts, settings.mat.density, excluded, settings.mat.code)
        self.cache = {}
        self.overrides = {}          # 품번 → 가공비 직접 입력
        self.mat_overrides = {}      # 품번 → 자재비 직접 입력
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
                               "필요 톤수 tf", "사용 기계", "시간 초/개", "제품 kg", "소요 kg",
                               "자재비/개 (고칠 수 있음)", "가공비/개 (고칠 수 있음)", "단가/개",
                               "세트 금액", "금형비", "비고"])
        self.t_parts.itemChanged.connect(self._part_edited)
        tabs.addTab(self.t_parts, "부품별 (공정·톤수·자재비)")
        self.t_ops = _table(["품번", "품명", "공정", "종류", "힘 tf", "사용 기계", "시간 초/개", "가공비 원/개", "비고"])
        self.t_ops.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.t_ops, "공정별 (톤수·기계)")

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

        tabs.addTab(self._machine_tab(), "기계·임률")
        tabs.addTab(self._die_tab(), "금형 견적")
        tabs.addTab(self._rates_tab(), "자재 단가·관리비")

        btns = QHBoxLayout()
        xl = QPushButton("생산 견적서 엑셀…")
        pdf = QPushButton("생산 견적서 PDF…")
        dxl = QPushButton("금형 견적서 엑셀…")
        dpdf = QPushButton("금형 견적서 PDF…")
        xl.clicked.connect(lambda: self.save("xlsx"))
        pdf.clicked.connect(lambda: self.save("pdf"))
        dxl.clicked.connect(lambda: self.save("xlsx", die=True))
        dpdf.clicked.connect(lambda: self.save("pdf", die=True))
        btns.addWidget(QLabel("단가·기계·임률은 예시값입니다 — 탭에서 회사 값으로 바꾸면 저장됩니다."))
        allb = QPushButton("엑셀 + PDF 모두 저장…")
        allb.setToolTip("생산 견적서와 (금형이 있으면) 금형 견적서를 엑셀·PDF 로 한 번에")
        allb.clicked.connect(self.save_all)
        self.pkg_btn = QPushButton("전체 분석 (한 번에)…")
        self.pkg_btn.setStyleSheet("QPushButton { font-weight: bold; padding: 4px 12px; }")
        self.pkg_btn.setToolTip("BOM · 자재비 · 부품별 공정도 · 생산 견적서 · 금형 견적서를 한 폴더에")
        self.pkg_btn.clicked.connect(self.save_package)
        logb = QPushButton("견적·금형 기록…")
        logb.setToolTip("지금까지 저장한 견적서·금형 견적서·금형 검토 기록")
        logb.clicked.connect(self.show_log)
        btns.addStretch(1)
        for b in (logb, xl, pdf, dxl, dpdf, allb, self.pkg_btn):
            btns.addWidget(b)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(tabs, 1)
        lay.addLayout(btns)
        self.tabs = tabs

        for w in (self.sets, self.annual, self.extra):
            w.valueChanged.connect(self.recalc)
        self.amort.toggled.connect(self.recalc)
        self.recalc()

    # ---- 기계·임률
    def _machine_tab(self):
        from . import costing as cs
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("회사 기계로 바꾸세요. 필요 톤수 × 여유 이상인 가장 작은 기계를 고릅니다 "
                             "(절곡기는 절곡 길이도 봄). 노란 칸을 고치면 바로 다시 계산하고 저장합니다."))
        self.t_mach = _table([h for _, h in cs.MACHINE_COLS])
        self.t_mach.itemChanged.connect(self._machines_edited)
        lay.addWidget(self.t_mach, 1)
        row = QHBoxLayout()
        add = QPushButton("기계 추가")
        add.clicked.connect(self._add_machine)
        rem = QPushButton("고른 기계 지우기")
        rem.clicked.connect(self._remove_machine)
        self.safety = QDoubleSpinBox()
        self.safety.setRange(1.0, 3.0)
        self.safety.setSingleStep(0.05)
        self.safety.setValue(float(self.rates["costing"].get("safety", cs.SAFETY)))
        self.safety.valueChanged.connect(self._machines_edited)
        reset = QPushButton("예시 기계로 되돌리기")
        reset.clicked.connect(self._reset_machines)
        row.addWidget(add)
        row.addWidget(rem)
        row.addWidget(reset)
        row.addStretch(1)
        row.addWidget(QLabel("톤수 여유 (배)"))
        row.addWidget(self.safety)
        lay.addLayout(row)
        self._fill_machines()
        return w

    def _fill_machines(self):
        from . import costing as cs
        self._busy = True
        t = self.t_mach
        ms = self.rates["costing"]["machines"]
        t.setRowCount(len(ms))
        for i, m in enumerate(ms):
            for j, (k, _) in enumerate(cs.MACHINE_COLS):
                v = m.get(k, "")
                t.setItem(i, j, _item(v if isinstance(v, str) else f"{v:g}", True, right=not isinstance(v, str)))
        self._busy = False

    def _machines_edited(self, *_):
        from . import costing as cs
        if self._busy:
            return
        ms = []
        for i in range(self.t_mach.rowCount()):
            m = {}
            for j, (k, _) in enumerate(cs.MACHINE_COLS):
                it = self.t_mach.item(i, j)
                txt = it.text() if it else ""
                m[k] = txt.strip() if k in ("name", "kind") else _num(txt)
            if m["name"]:
                ms.append(m)
        self.rates["costing"]["machines"] = ms
        self.rates["costing"]["safety"] = self.safety.value()
        self._save_rates()
        self.recalc()

    def _add_machine(self):
        self.rates["costing"]["machines"].append({"name": "새 프레스", "kind": "프레스", "capacity": 150,
                                                  "length": 0, "rate": 60000, "spm": 25, "setup_min": 40})
        self._fill_machines()
        self._machines_edited()

    def _remove_machine(self):
        r = self.t_mach.currentRow()
        if 0 <= r < len(self.rates["costing"]["machines"]):
            del self.rates["costing"]["machines"][r]
            self._fill_machines()
            self._machines_edited()

    def _reset_machines(self):
        from . import costing as cs
        self.rates["costing"]["machines"] = [dict(m) for m in cs.DEFAULT_MACHINES]
        self._fill_machines()
        self._machines_edited()

    # ---- 금형 견적
    def _die_tab(self):
        from . import costing as cs
        w = QWidget()
        lay = QHBoxLayout(w)
        self.die_label = QLabel()
        self.die_label.setTextFormat(Qt.RichText)
        self.die_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.die_label.setWordWrap(True)
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.die_label)
        lay.addWidget(sc, 3)
        form = QFormLayout()
        self.die_spins = {}
        for k, name in cs.DIE_NAMES.items():
            sp = QDoubleSpinBox()
            sp.setRange(0, 1e10)
            sp.setDecimals(2 if k in ("drawing_factor",) or k.endswith("pct") else 0)
            sp.setGroupSeparatorShown(True)
            sp.setValue(float(self.rates["costing"]["die"][k]))
            sp.valueChanged.connect(self._die_edited)
            self.die_spins[k] = sp
            form.addRow(name, sp)
        box = QWidget()
        box.setLayout(form)
        lay.addWidget(box, 2)
        return w

    def _die_edited(self, *_):
        if self._busy:
            return
        for k, sp in self.die_spins.items():
            self.rates["costing"]["die"][k] = sp.value()
        self._save_rates()
        self.recalc()

    def _save_rates(self):
        self.st.setValue("quote_rates", json.dumps(self.rates, ensure_ascii=False))

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
        self._save_rates()
        self.recalc()

    def _reset_rates(self):
        keep = self.rates["costing"]
        self.rates = qt_.load_rates(None)
        self.rates["costing"] = keep
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
            p.material_override = self.mat_overrides.get(p.no)
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
            f"견적 수량 {q.sets:,} 세트 · 연간 {q.annual:,} 개 기준<br>"
            f"<b>필요 톤수 최대 {q.max_tonf:,.1f} tf</b> · 사용 기계: {', '.join(q.machine_list) or '-'}<br>"
            f"금형 견적 {qt_.won(q.die_total)} 원 ({len(q.dies)} 벌, 부가세 별도) → [금형 견적] 탭",
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
        over = sorted({o.machine for p in q.parts for o in p.opc if "⚠" in o.note})
        if over:
            lines.append(f"<p style='color:#d40'>⚠ 용량이 모자란 기계: {', '.join(over)} — [기계·임률] 에 더 큰 기계를 넣으세요.</p>")
        rough = [p.name for p in q.parts if p.note.startswith("가공비는")]
        if rough:
            lines.append(f"<p style='color:#c80'>⚠ 기계 가공 부품 {len(rough)}개는 가공비가 무게 어림입니다.</p>")
        self.sum_label.setText("".join(lines))

    def _fill_parts(self, q):
        t = self.t_parts
        t.setRowCount(len(q.parts))
        for i, p in enumerate(q.parts):
            vals = [p.no, p.name, p.qty, p.category, p.spec, p.method, p.n_ops, " → ".join(p.ops),
                    f"{p.need_tonf:,.1f}", ", ".join(p.machines), f"{p.seconds:,.1f}",
                    f"{p.weight:.3f}", f"{p.gross_kg:.3f}", None, None, float(p.unit),
                    float(p.amount), float(p.die_cost), p.note]
            for j, v in enumerate(vals):
                if j == 13:
                    it = _item(float(p.material), True)
                    if p.material_override is not None:
                        it.setForeground(QColor(200, 60, 0))
                elif j == 14:
                    it = _item(float(p.process_cost), True)
                    if p.process_override is not None:
                        it.setForeground(QColor(200, 60, 0))
                else:
                    it = _item(v, right=j in (8, 10, 11, 12))
                    if j == 9 and "⚠" in " ".join(o.note for o in p.opc):
                        it.setForeground(QColor(220, 60, 0))
                t.setItem(i, j, it)
        rows = [(p, o) for p in q.parts for o in p.opc]
        self.t_ops.setRowCount(len(rows))
        for i, (p, o) in enumerate(rows):
            for j, v in enumerate([str(p.no), p.name, o.op, o.kind, f"{o.tonf:,.2f}", o.machine,
                                   f"{o.seconds:,.1f}", f"{o.cost:,.1f}", o.note]):
                it = _item(v, right=j in (4, 6, 7))
                if "⚠" in o.note:
                    it.setForeground(QColor(220, 60, 0))
                self.t_ops.setItem(i, j, it)
        # 금형 견적
        from html import escape
        supply, vat, total = qt_.die_total_with_vat(q)
        html = [f"<h3>금형 견적 합계 {qt_.won(supply)} 원 (부가세 별도) · {len(q.dies)} 벌</h3>"]
        if not q.dies:
            html.append("금형이 필요 없는 공정입니다 (연간 생산량을 늘리면 금형 공정으로 바뀝니다).")
        for d in q.dies:
            html.append(f"<p><b>{escape(d.part_name)}</b> — {escape(d.die_type)}, {d.stations} 공정, "
                        f"{d.size[0]:.0f}×{d.size[1]:.0f}×{d.size[2]:.0f} mm<br><table cellpadding=2>")
            for name, formula, amt in d.lines:
                html.append(f"<tr><td>{escape(name)}</td><td style='color:#888'>{escape(formula)}</td>"
                            f"<td align=right>{qt_.won(amt)}</td></tr>")
            html.append(f"<tr><td><b>소계</b></td><td></td><td align=right><b>{qt_.won(d.cost)}</b></td></tr>"
                        "</table></p>")
        self.die_label.setText("".join(html))

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
        if self._busy or it.column() not in (13, 14):
            return
        no = int(self.t_parts.item(it.row(), 0).text())
        target = self.mat_overrides if it.column() == 13 else self.overrides
        txt = it.text().strip()
        if txt == "":
            target.pop(no, None)
        else:
            target[no] = _num(txt)
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

    def save_package(self):
        """전체 분석: 고른 폴더 안에 '제품_분석_날짜시각' 폴더를 만들고 BOM·자재비·공정도·견적서를 모두."""
        import datetime as _dt

        from PySide6.QtWidgets import QApplication, QProgressDialog

        from . import package
        self.recalc()
        self.st.setValue("quote_annual", self.annual.value())
        self.st.setValue("quote_customer", self.customer.text())
        start = self.st.value("package_dir", "") or os.path.dirname(self.model.path)
        root = QFileDialog.getExistingDirectory(self, "전체 분석 결과를 둘 폴더", start)
        if not root:
            return
        self.st.setValue("package_dir", root)
        folder = os.path.join(root, f"{package._safe(self.title)}_분석_{_dt.datetime.now():%Y%m%d_%H%M}")
        prog = QProgressDialog("전체 분석 중…", None, 0, 0, self)
        prog.setWindowTitle("전체 분석")
        prog.setMinimumDuration(0)
        prog.setWindowModality(Qt.WindowModal)
        prog.show()

        def step(text):
            prog.setLabelText(f"전체 분석 중… {text}")
            QApplication.processEvents()

        try:
            files = package.run(self.q, self.model, self.parts, self.settings, folder, self.items, step)
        except Exception as e:
            prog.close()
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "전체 분석 실패", str(e))
            return
        prog.close()
        if self.history is not None:
            try:
                v = qt_.record_values(self.q)
                v["material"] = self.settings.mat.code
                v["summary"] = "전체 분석 · " + v["summary"]
                self.history.add_doc("전체 분석", files, self.model.path, v, qt_.record_detail(self.q))
            except Exception:
                import traceback
                traceback.print_exc()
        QMessageBox.information(self, "전체 분석", f"{len(files)}개 파일을 만들었습니다.\n{folder}\n\n"
                                + "\n".join(os.path.basename(f) for f in files))
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def save_all(self):
        self.recalc()                 # 수신 업체 등 마지막 입력을 반영
        self.st.setValue("quote_annual", self.annual.value())
        self.st.setValue("quote_customer", self.customer.text())
        base = os.path.splitext(self.model.path)[0] + "_견적서.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "견적서 모두 저장 (이름 하나로 엑셀·PDF)", base, "엑셀 (*.xlsx)")
        if not path:
            return
        stem = os.path.splitext(path)[0]
        if stem.endswith("_견적서"):
            stem = stem[:-4]
        jobs = [(qt_.save_xlsx, stem + "_견적서.xlsx"), (qt_.save_pdf, stem + "_견적서.pdf")]
        if self.q.dies:
            jobs += [(qt_.save_die_xlsx, stem + "_금형견적서.xlsx"), (qt_.save_die_pdf, stem + "_금형견적서.pdf")]
        try:
            for fn, out in jobs:
                fn(self.q, out)
        except Exception as e:
            QMessageBox.warning(self, "견적서 저장 실패", str(e))
            return
        self._log(False, [o for _, o in jobs[:2]])
        if self.q.dies:
            self._log(True, [o for _, o in jobs[2:]])
        QMessageBox.information(self, "견적서", "저장했습니다.\n" + "\n".join(o for _, o in jobs)
                                + ("\n(견적·금형 기록에 남겼습니다)" if self.history is not None else ""))
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(jobs[0][1])))

    def _log(self, die, files):
        if self.history is None:
            return
        try:
            v = qt_.record_values(self.q, die)
            v["material"] = self.settings.mat.code
            self.history.add_doc("금형 견적" if die else "생산 견적", files, self.model.path, v,
                                 qt_.record_detail(self.q, die))
        except Exception:
            import traceback
            traceback.print_exc()

    def show_log(self):
        if self.history is None:
            QMessageBox.information(self, "견적·금형 기록", "기록을 쓸 수 없습니다 ([전개 기록 남기기] 가 꺼져 있음).")
            return
        from .doc_history_dialog import DocHistoryDialog
        DocHistoryDialog(self.history, parent=self).exec()

    def save(self, kind, die=False):
        self.recalc()
        self.st.setValue("quote_annual", self.annual.value())
        self.st.setValue("quote_customer", self.customer.text())
        if die and not self.q.dies:
            QMessageBox.information(self, "금형 견적", "금형이 필요한 부품이 없습니다 (연간 생산량을 확인하세요).")
            return
        base = os.path.splitext(self.model.path)[0] + (f"_금형견적서.{kind}" if die else f"_견적서.{kind}")
        path, _ = QFileDialog.getSaveFileName(self, "견적서 저장", base,
                                              "엑셀 (*.xlsx)" if kind == "xlsx" else "PDF (*.pdf)")
        if not path:
            return
        try:
            if die:
                (qt_.save_die_xlsx if kind == "xlsx" else qt_.save_die_pdf)(self.q, path)
            else:
                (qt_.save_xlsx if kind == "xlsx" else qt_.save_pdf)(self.q, path)
        except Exception as e:
            QMessageBox.warning(self, "견적서 저장 실패", str(e))
            return
        self._log(die, [path])
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
