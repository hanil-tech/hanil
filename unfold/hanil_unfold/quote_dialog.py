"""견적 창: 공정수·재료비·가공비·부자재를 보고 고친 뒤 견적서 초안 (엑셀·PDF) 저장."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QComboBox, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
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
    def __init__(self, model, parts, settings, excluded=(), title="", parent=None, history=None, items_db=None):
        super().__init__(parent)
        from . import bom
        self.setWindowTitle(f"견적 — {title}")
        self.resize(1200, 760)
        self.model, self.parts, self.settings, self.title = model, parts, settings, title
        self.history = history
        self.items_db = items_db if items_db is not None else history     # 아이템 대장 (기록을 꺼도 씀)
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
        self.item_box = QComboBox()
        self.item_box.setToolTip("아이템 대장의 아이템 — 견적서를 저장하면 그 아이템에 견적 리비전 (R0, R1 …) 이 쌓입니다")
        self.item_box.addItem("(아이템 대장과 잇지 않음)", None)
        if self.items_db is not None:
            for r in self.items_db.search_items():
                d = r.data
                self.item_box.addItem(f"{d.get('customer') or ''} {d.get('part_no') or ''} {d.get('part_name') or ''} "
                                      f"[{d.get('status')}]".strip(), r.id)
        self.item_box.currentIndexChanged.connect(self._item_changed)
        for lab, w in (("견적 수량", self.sets), ("연간 생산량", self.annual), ("수신", self.customer),
                       ("조립·용접·도장 등", self.extra), ("아이템", self.item_box)):
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
        tabs.addTab(self._prod_tab(), "생산 견적")
        tabs.addTab(self._cost_tab(), "원가계산서")
        tabs.addTab(self._quality_tab(), "품질 문서")
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

    # ---- 아이템 대장
    def select_item(self, rid):
        i = self.item_box.findData(rid)
        if i >= 0:
            self.item_box.setCurrentIndex(i)

    def _item_changed(self, *_):
        rid = self.item_box.currentData()
        if rid is None or self.items_db is None:
            return
        it = self.items_db.get_item(rid)
        if it is None:
            return
        d = it.data
        if d.get("annual"):
            self.annual.setValue(int(d["annual"]))
        if d.get("customer"):
            self.customer.setText(d["customer"])
        if d.get("status") == "접수":
            self.items_db.update_item(rid, {"status": "견적 중"})

    def _item_revision(self, files):
        rid = self.item_box.currentData()
        if rid is None or self.items_db is None:
            return ""
        try:
            return self.items_db.add_revision(rid, self.q.unit_price, self.q.die_total, self.q.annual,
                                             f"{self.q.sets:,} 세트 · {len(self.q.parts)} 부품", files)
        except Exception:
            import traceback
            traceback.print_exc()
            return ""

    # ---- 생산 견적 · 원가계산서 · 품질 문서
    def _param_form(self, names, values, slot, text_keys=()):
        form = QFormLayout()
        spins = {}
        for k, label in names.items():
            v = values[k]
            if k in text_keys:
                w = QLineEdit(str(v))
                w.editingFinished.connect(slot)
            else:
                w = QDoubleSpinBox()
                w.setRange(0, 1e9)
                w.setDecimals(2 if isinstance(v, float) and v < 10 else 0)
                w.setGroupSeparatorShown(True)
                w.setValue(float(v))
                w.valueChanged.connect(slot)
            spins[k] = w
            form.addRow(label, w)
        box = QWidget()
        box.setLayout(form)
        from PySide6.QtWidgets import QScrollArea
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(box)
        sc.setMinimumWidth(400)
        return sc, spins

    def _prod_tab(self):
        from . import production as prod
        w = QWidget()
        lay = QHBoxLayout(w)
        left = QVBoxLayout()
        self.prod_label = QLabel()
        self.prod_label.setWordWrap(True)
        self.prod_label.setTextFormat(Qt.RichText)
        left.addWidget(self.prod_label)
        self.t_load = _table(prod.MACHINE_HEAD)
        self.t_load.setEditTriggers(QTableWidget.NoEditTriggers)
        left.addWidget(QLabel("설비 부하 (1 년)"))
        left.addWidget(self.t_load, 2)
        self.t_flow = _table(prod.FLOW_HEAD)
        self.t_flow.setEditTriggers(QTableWidget.NoEditTriggers)
        left.addWidget(QLabel("부품별 사이클타임 · 하루 생산량 · 소재"))
        left.addWidget(self.t_flow, 2)
        self.gantt = QLabel()
        self.gantt.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        from PySide6.QtWidgets import QScrollArea
        gs = QScrollArea()
        gs.setWidget(self.gantt)
        gs.setWidgetResizable(True)
        left.addWidget(gs, 3)
        row = QHBoxLayout()
        row.addStretch(1)
        for text_, kind in (("생산 견적 엑셀…", "xlsx"), ("생산 견적 PDF…", "pdf")):
            b = QPushButton(text_)
            b.clicked.connect(lambda _=False, k_=kind: self.save_doc("prod", k_))
            row.addWidget(b)
        left.addLayout(row)
        lay.addLayout(left, 3)
        self.rates.setdefault("production", {})
        sc, self.prod_spins = self._param_form(prod.NAMES, prod.params(self.rates), self._prod_edited)
        lay.addWidget(sc, 1)
        return w

    def _prod_edited(self, *_):
        if self._busy:
            return
        self.rates["production"] = {k: s.value() for k, s in self.prod_spins.items()}
        self._save_rates()
        self.recalc()

    def _cost_tab(self):
        from . import costsheet as cst
        w = QWidget()
        lay = QHBoxLayout(w)
        left = QVBoxLayout()
        self.cost_label = QLabel()
        self.cost_label.setWordWrap(True)
        self.cost_label.setTextFormat(Qt.RichText)
        left.addWidget(self.cost_label)
        self.t_cost = _table(["항목"])
        self.t_cost.setEditTriggers(QTableWidget.NoEditTriggers)
        left.addWidget(self.t_cost, 3)
        row = QHBoxLayout()
        qb = QPushButton("수량별 단가표 계산")
        qb.setToolTip("수량마다 공정 방식(레이저·단발·순차)과 금형이 바뀌므로 다시 설계해서 계산합니다")
        qb.clicked.connect(self._calc_qty)
        row.addWidget(qb)
        row.addStretch(1)
        for text_, kind in (("원가계산서 엑셀…", "xlsx"), ("원가계산서 PDF…", "pdf")):
            b = QPushButton(text_)
            b.clicked.connect(lambda _=False, k_=kind: self.save_doc("cost", k_))
            row.addWidget(b)
        left.addLayout(row)
        self.t_qty = _table(cst.QTY_HEAD)
        self.t_year = _table(cst.YEAR_HEAD)
        self.t_sens = _table(cst.SENS_HEAD)
        bottom = QHBoxLayout()
        for t, lab in ((self.t_qty, "수량별 단가"), (self.t_year, "연차별 단가"), (self.t_sens, "철강 시세 민감도")):
            t.setEditTriggers(QTableWidget.NoEditTriggers)
            col = QVBoxLayout()
            col.addWidget(QLabel(lab))
            col.addWidget(t)
            bottom.addLayout(col)
        left.addLayout(bottom, 2)
        lay.addLayout(left, 3)
        self.rates.setdefault("costsheet", {})
        self.qty_rows = None
        sc, self.cost_spins = self._param_form(cst.NAMES, cst.params(self.rates), self._cost_edited, ("qty_list",))
        lay.addWidget(sc, 1)
        return w

    def _cost_edited(self, *_):
        if self._busy:
            return
        self.rates["costsheet"] = {k: (s.text() if isinstance(s, QLineEdit) else s.value())
                                   for k, s in self.cost_spins.items()}
        self._save_rates()
        self.qty_rows = None
        self.recalc()

    def quote_for(self, annual):
        """양산 견적: 로트 = 연간 수량 ÷ 1 년 로트 수 (준비 시간을 양산 로트로 나눔)."""
        from . import production as prod
        lots = max(prod.params(self.rates)["lots_per_year"], 1)
        q = qt_.build(self.model, self.parts, self.settings, self.rates, max(int(annual / lots), 1), annual,
                      title=self.title, items=self.items, cache=self.cache)
        for p in q.parts:
            p.process_override = self.overrides.get(p.no)
            p.material_override = self.mat_overrides.get(p.no)
        for s in q.subs:
            s.unit_price = float(self.sub_prices.get(s.name, 0.0))
        q.subs += self.extra_subs
        q.extra = self.extra.value()
        q.customer = self.customer.text().strip()
        return q

    def _calc_qty(self):
        from PySide6.QtWidgets import QApplication

        from . import costsheet as cst
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.qty_rows = cst.qty_table(self.quote_for, cst.params(self.rates), self.q_mass)
        finally:
            QApplication.restoreOverrideCursor()
        self._fill_rows(self.t_qty, [[f"{a:,}", qt_.won(b), qt_.won(c), qt_.won(d), e] for a, b, c, d, e in self.qty_rows])

    def _quality_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("수주 후 양산 승인 (PPAP) 용 초안 — 공정 흐름도 (PFD) · PFMEA (AIAG-VDA 조치 우선순위 AP) · "
                             "관리계획서. 공정은 이 견적의 공정 설계, 발생도는 성형 해석 판정으로 정합니다."))
        self.q_tabs = QTabWidget()
        from . import qualitydocs as qd
        self.t_pfd, self.t_fmea, self.t_cp = _table(qd.PFD_HEAD), _table(qd.FMEA_HEAD), _table(qd.CP_HEAD)
        for t, lab in ((self.t_pfd, "공정 흐름도"), (self.t_fmea, "PFMEA"), (self.t_cp, "관리계획서")):
            t.setEditTriggers(QTableWidget.NoEditTriggers)
            self.q_tabs.addTab(t, lab)
        row = QHBoxLayout()
        row.addWidget(QLabel("부품"))
        self.q_part = QComboBox()
        self.q_part.currentIndexChanged.connect(self._fill_quality)
        row.addWidget(self.q_part)
        row.addStretch(1)
        for text_, kind in (("품질 문서 엑셀 (모든 부품)…", "xlsx"), ("품질 문서 PDF (모든 부품)…", "pdf")):
            b = QPushButton(text_)
            b.clicked.connect(lambda _=False, k_=kind: self.save_doc("quality", k_))
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(self.q_tabs, 1)
        self.qdocs = []
        return w

    def quality_docs(self):
        from . import qualitydocs as qd
        byno = {it.no: it for it in self.items}
        out = []
        for pc in self.q.parts:
            it = byno.get(pc.no)
            res = it.result if it is not None else None
            out.append(qd.build(pc, res, self.settings, self.q.customer, getattr(it, "code", "") or ""))
        return out

    def _fill_quality(self, *_):
        from . import qualitydocs as qd
        i = self.q_part.currentIndex()
        if not (0 <= i < len(self.qdocs)):
            return
        d = self.qdocs[i]
        self._fill_rows(self.t_pfd, qd.pfd_rows(d))
        self._fill_rows(self.t_fmea, qd.fmea_rows(d), color_col=11)
        self._fill_rows(self.t_cp, qd.cp_rows(d))

    def _fill_rows(self, t, rows, color_col=None):
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                it = _item(v if isinstance(v, str) else (f"{v:,.1f}" if isinstance(v, float) else str(v)),
                           right=not isinstance(v, str))
                if color_col == j:
                    it.setBackground({"H": QColor(244, 182, 182), "M": QColor(251, 227, 166),
                                      "L": QColor(207, 232, 207)}.get(str(v), QColor(255, 255, 255)))
                t.setItem(i, j, it)

    def _fill_extra(self, q):
        """생산 견적 · 원가계산서 · 품질 문서 탭."""
        from PySide6.QtGui import QPixmap

        from . import costsheet as cst
        from . import production as prod
        self.pl = pl = prod.plan(q)
        self.prod_label.setText("<b>" + "</b><br>".join(prod.summary_lines(pl)[:3]) + "</b><br>"
                                + "<br>".join(("⚠ " if "부하" in n and "%" in n and "필요" in n else "") + n
                                              for n in prod.summary_lines(pl)[3:]))
        self._fill_rows(self.t_load, [[r[0], r[1], r[2], r[3], r[4], r[5], f"{r[6]:.0%}", r[7], r[8], r[9]]
                                      for r in prod.machine_rows(pl)])
        for i, m in enumerate(pl.machines):
            if m.load > 1:
                self.t_load.item(i, 6).setForeground(QColor(220, 40, 40))
        self._fill_rows(self.t_flow, prod.flow_rows(pl))
        if pl.phases:
            self.gantt.setPixmap(QPixmap.fromImage(prod.render_gantt(pl, 1100)))
        else:
            self.gantt.setText("금형이 없어 금형 제작 일정이 없습니다.")
        self.q_mass = qm = self.quote_for(q.annual)       # 원가계산서는 양산 로트 기준
        self.cs = cs_ = cst.compute(qm)
        head = cst.sheet_head(cs_)
        self.t_cost.setColumnCount(len(head))
        self.t_cost.setHorizontalHeaderLabels(head)
        self._fill_rows(self.t_cost, [[r[0]] + [qt_.won(v) if isinstance(v, float) else v for v in r[1:]]
                                      for r in cst.sheet_rows(cs_)])
        self.cost_label.setText(f"<h3>원가계산서 세트 판매 단가 {qt_.won(cs_.set_price)} 원 "
                                f"(양산 로트 {qm.sets:,} 세트 기준 · 이 견적 {q.sets:,} 세트의 견적서 단가 "
                                f"{qt_.won(q.unit_price)} 원)</h3>"
                                + "<br>".join(cs_.notes)
                                + "<br><span style='color:#888'>원가계산서는 불량 로스·포장·운반·금형 상각까지 넣고, 이윤을 "
                                  "가공비+관리비에만 붙입니다 (자동차 협력사 양식).</span>")
        self._fill_rows(self.t_year, [[a, qt_.won(b), qt_.won(c), d] for a, b, c, d in cst.year_table(cs_)])
        self._fill_rows(self.t_sens, [[a, qt_.won(b), f"{c:+,.0f}", f"{d:+.1%}"] for a, b, c, d in cst.sensitivity(qm)])
        if self.qty_rows:
            self._fill_rows(self.t_qty, [[f"{a:,}", qt_.won(b), qt_.won(c), qt_.won(d), e] for a, b, c, d, e in self.qty_rows])
        try:
            self.qdocs = self.quality_docs()
        except Exception:
            import traceback
            traceback.print_exc()
            self.qdocs = []
        cur = self.q_part.currentIndex()
        self.q_part.blockSignals(True)
        self.q_part.clear()
        for d in self.qdocs:
            self.q_part.addItem(f"{d.part_no} {d.part_name}")
        self.q_part.setCurrentIndex(min(max(cur, 0), len(self.qdocs) - 1))
        self.q_part.blockSignals(False)
        self._fill_quality()

    def save_doc(self, what, kind):
        from . import costsheet as cst
        from . import production as prod
        from . import qualitydocs as qd
        self.recalc()
        name = {"prod": "생산견적", "cost": "원가계산서", "quality": "품질문서"}[what]
        base = os.path.splitext(self.model.path)[0] + f"_{name}.{kind}"
        path, _ = QFileDialog.getSaveFileName(self, f"{name} 저장", base,
                                              "엑셀 (*.xlsx)" if kind == "xlsx" else "PDF (*.pdf)")
        if not path:
            return
        try:
            if what == "prod":
                (prod.save_xlsx if kind == "xlsx" else prod.save_pdf)(self.pl, path, self.title)
            elif what == "cost":
                (cst.save_xlsx if kind == "xlsx" else cst.save_pdf)(self.cs, self.q_mass, path, self.qty_rows, self.title)
            else:
                (qd.save_xlsx if kind == "xlsx" else qd.save_pdf)(self.qdocs, path, self.title)
        except Exception as e:
            QMessageBox.warning(self, f"{name} 저장 실패", str(e))
            return
        if self.history is not None:
            try:
                v = qt_.record_values(self.q)
                v["material"] = self.settings.mat.code
                if what == "prod":
                    v["summary"] = " · ".join(prod.summary_lines(self.pl)[:3])
                elif what == "cost":
                    v["unit_price"] = self.cs.set_price
                    v["summary"] = f"원가계산서 세트 단가 {qt_.won(self.cs.set_price)} 원 · " + " · ".join(self.cs.notes)
                else:
                    v["summary"] = f"품질 문서 {len(self.qdocs)} 부품 · PFMEA AP H " \
                                   f"{sum(f.ap == 'H' for d in self.qdocs for f in d.fmea)} 건"
                self.history.add_doc({"prod": "생산 견적 (설비·일정)", "cost": "원가계산서", "quality": "품질 문서"}[what],
                                     [path], self.model.path, v, None)
            except Exception:
                import traceback
                traceback.print_exc()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

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
        calc = QPushButton("임률 계산 (독일 VDI 3258 · 일본 チャージ)…")
        calc.setToolTip("고른 기계의 임률을 기계 값·감가상각·이자·공간·전력·보수 + 노무비로 계산해 넣습니다")
        calc.clicked.connect(self._rate_calc)
        row.addWidget(calc)
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

    def _rate_calc(self):
        from PySide6.QtWidgets import QDialogButtonBox

        from . import costing as cs
        r = self.t_mach.currentRow()
        ms = self.rates["costing"]["machines"]
        if not (0 <= r < len(ms)):
            QMessageBox.information(self, "임률 계산", "표에서 기계를 하나 고르세요.")
            return
        m = ms[r]
        saved = dict(self.rates.setdefault("rate_calc", {}).get(m["name"], {}))
        if not saved:                                   # 처음이면 톤수로 기계 값 어림
            cap = float(m.get("capacity") or 100)
            saved = {"price": {"프레스": 1_500_000 * cap, "절곡기": 1_000_000 * cap, "레이저": 600_000_000}.get(
                m.get("kind"), 200_000_000), "power_kw": max(cap * 0.2, 7.5) if m.get("kind") != "레이저" else 60}
        p = dict(cs.RATE_DEFAULTS)
        p.update(saved)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"임률 계산 — {m['name']}")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        spins = {}
        out = QLabel()
        out.setTextFormat(Qt.RichText)

        def upd(*_):
            vals = {k: s.value() for k, s in spins.items()}
            total, rows = cs.machine_rate(vals)
            out.setText("<table cellpadding=3>" + "".join(
                f"<tr><td>{a}</td><td align=right>{b:,.0f} 원/h</td><td style='color:#888'>{c}</td></tr>"
                for a, b, c in rows) + f"<tr><td><b>임률 합계</b></td><td align=right><b>{total:,.0f} 원/h</b></td>"
                f"<td style='color:#888'>지금 표의 값 {float(m.get('rate', 0)):,.0f}</td></tr></table>")
            dlg.total, dlg.vals = total, vals
        for k, name in cs.RATE_NAMES.items():
            s = QDoubleSpinBox()
            s.setRange(0, 1e12)
            s.setDecimals(2 if k in ("load", "crew", "interest_pct", "maint_pct") else 0)
            s.setGroupSeparatorShown(True)
            s.setValue(float(p[k]))
            s.valueChanged.connect(upd)
            spins[k] = s
            form.addRow(name, s)
        lay.addLayout(form)
        lay.addWidget(out)
        lay.addWidget(QLabel("<span style='color:#888'>독일 Maschinenstundensatz (VDI 3258): (감가상각 + 이자 + 공간 + 전력 + "
                             "보수) ÷ 가동 시간, 일본 チャージ도 같은 틀 + 노무비</span>"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("이 임률로 넣기")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        upd()
        if dlg.exec():
            m["rate"] = round(dlg.total, -2)
            self.rates["rate_calc"][m["name"]] = dlg.vals
            self._fill_machines()
            self._machines_edited()

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
            if k == "structure":
                cb = QComboBox()
                cb.addItems(cs.STRUCTURES)
                cb.setCurrentIndex(int(self.rates["costing"]["die"].get(k, 0)))
                cb.setToolTip("자동: 금형 긴 변·강판 세트 무게가 기준을 넘으면 주물 (대형 금형)")
                cb.currentIndexChanged.connect(self._die_edited)
                self.die_spins[k] = cb
                form.addRow(name, cb)
                continue
            sp = QDoubleSpinBox()
            sp.setRange(0, 1e10)
            sp.setDecimals(2 if k in ("drawing_factor", "cast_fill") or k.endswith("pct") else 0)
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
            self.rates["costing"]["die"][k] = sp.currentIndex() if k == "structure" else sp.value()
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
            self._fill_extra(q)
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
        if not die:
            self._item_revision(files)
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
