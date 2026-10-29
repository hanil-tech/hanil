"""금형비 계산 창 (지금 부품 하나): 자동 공정 설계 → 금형 형식·공정수·톤수 → 금형비 내역, 금형 간략도.
금형 몸체는 자동으로 강판 다이 세트 / 주물 (FC300·FCD) 을 고르고 (크기·무게 기준), 직접 고를 수도 있다.
단가는 [견적] 창의 금형 단가와 같은 설정을 쓴다 (한쪽에서 바꾸면 다른 쪽도)."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter, QTextBrowser,
                               QVBoxLayout, QWidget)

from . import bendcalc as bc
from . import costing as cs
from . import quote as qt_


def part_item(result, name, density):
    from . import metrics as mt
    from .bom import BomItem
    m = mt.compute(result, density)
    w, h = result.size
    return BomItem(no=1, name=name or "부품", indices=[0], kind="판금", thickness=result.thickness,
                   flat_w=w, flat_h=h, blank_area=m.blank_area, weight=m.weight_kg,
                   bends=len(result.bends), result=result, category="자작 부품(판금)", procure="자작")


class DieCostDialog(QDialog):
    def __init__(self, result, settings: bc.BendSettings, name="", parent=None, history=None, source_path=""):
        super().__init__(parent)
        self.setWindowTitle(f"금형비 계산 — {name}" if name else "금형비 계산")
        self.resize(1400, 860)
        self.result, self.settings, self.name = result, settings, name
        self.history, self.source_path = history, source_path
        self.st = QSettings("Hanil", "SheetUnfold")
        self.rates = qt_.load_rates(self.st.value("quote_rates", ""))
        self.item = part_item(result, os.path.splitext(name)[0] if name else "", settings.mat.density)
        self.cache, self.q, self._busy = {}, None, False

        top = QHBoxLayout()
        self.annual = QSpinBox()
        self.annual.setRange(1, 100_000_000)
        self.annual.setSingleStep(10_000)
        self.annual.setGroupSeparatorShown(True)
        self.annual.setValue(int(self.st.value("die_cost_annual", 100_000)))
        self.annual.setSuffix(" 개/년")
        self.annual.valueChanged.connect(self.recalc)
        self.struct = QComboBox()
        self.struct.addItems(cs.STRUCTURES)
        self.struct.setCurrentIndex(int(self.rates["costing"]["die"].get("structure", 0)))
        self.struct.setToolTip("자동: 금형 몸체 긴 변이나 강판 다이 세트 무게가 기준을 넘으면 주물 (대형 금형)")
        self.struct.currentIndexChanged.connect(self._struct_changed)
        top.addWidget(QLabel("연간 생산량"))
        top.addWidget(self.annual)
        top.addSpacing(16)
        top.addWidget(QLabel("금형 몸체"))
        top.addWidget(self.struct)
        top.addStretch(1)
        self.total = QLabel()
        self.total.setStyleSheet("font-size:16px; font-weight:bold; color:#1f4e8c")
        top.addWidget(self.total)

        self.text = QTextBrowser()
        self.sketch = QLabel()
        self.sketch.setAlignment(Qt.AlignCenter)
        left = QSplitter(Qt.Vertical)
        left.addWidget(self.text)
        left.addWidget(self.sketch)
        left.setSizes([430, 380])

        form = QFormLayout()
        self.spins = {}
        for k, label in cs.DIE_NAMES.items():
            if k == "structure":
                continue
            sp = QDoubleSpinBox()
            sp.setRange(0, 1e10)
            sp.setDecimals(2 if k in ("drawing_factor", "cast_fill") or k.endswith("pct") else 0)
            sp.setGroupSeparatorShown(True)
            sp.setValue(float(self.rates["costing"]["die"].get(k, cs.DEFAULT_DIE.get(k, 0))))
            sp.valueChanged.connect(self._edited)
            self.spins[k] = sp
            form.addRow(label, sp)
        reset = QPushButton("단가 처음 값으로")
        reset.clicked.connect(self._reset)
        form.addRow(reset)
        fw = QWidget()
        fw.setLayout(form)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(fw)
        sc.setMinimumWidth(380)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(sc)
        split.setSizes([1000, 400])

        buttons = QHBoxLayout()
        buttons.addWidget(QLabel("<span style='color:#888'>단가는 [견적] 창의 금형 단가와 같은 설정입니다 — "
                                 "회사·업체 견적에 맞게 고치세요.</span>"))
        buttons.addStretch(1)
        for text_, kind in (("엑셀…", "xlsx"), ("PDF…", "pdf"), ("엑셀 + PDF 모두…", "both")):
            b = QPushButton(text_)
            b.clicked.connect(lambda _=False, k_=kind: self.save(k_))
            buttons.addWidget(b)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)
        lay.addLayout(buttons)
        self.recalc()

    # ---- 단가
    def _save_rates(self):
        self.st.setValue("quote_rates", json.dumps(self.rates, ensure_ascii=False))

    def _struct_changed(self, i):
        self.rates["costing"]["die"]["structure"] = i
        self._save_rates()
        self.recalc()

    def _edited(self, *_):
        if self._busy:
            return
        for k, sp in self.spins.items():
            self.rates["costing"]["die"][k] = sp.value()
        self._save_rates()
        self.recalc()

    def _reset(self):
        self._busy = True
        for k, sp in self.spins.items():
            sp.setValue(float(cs.DEFAULT_DIE[k]))
        self._busy = False
        self._edited()

    # ---- 계산
    def recalc(self, *_):
        self.st.setValue("die_cost_annual", self.annual.value())
        pc = qt_.part_cost(self.item, self.settings, self.rates, self.annual.value(), self.cache)
        self.q = qt_.Quote(self.item.name, 1, self.annual.value(), [pc], [], self.rates)
        d = pc.die
        if d is None:
            self.total.setText("금형 없음")
            self.text.setHtml(f"<b>{pc.method}</b><br>이 생산량에서는 금형 없이 만드는 쪽이 맞습니다 "
                              "(연간 생산량을 늘려 보세요).")
            self.sketch.clear()
            return
        supply, vat, total = qt_.die_total_with_vat(self.q)
        self.total.setText(f"금형비 {supply:,.0f} 원 (VAT 별도) · 합계 {total:,.0f} 원")
        rows = "".join(f"<tr><td>{a}</td><td style='color:#555'>{b}</td><td align=right>{c:,.0f}</td></tr>"
                       for a, b, c in d.lines)
        body = ("주물 금형 — " + d.reason) if d.structure == "주물" else "강판 다이 세트 (SM45C·SS + SKD11 인서트)"
        L, W, T = d.size
        self.text.setHtml(
            f"<b style='font-size:14px'>{d.die_type}</b> · {d.stations} 공정"
            + (f" × {d.sets} 벌" if d.sets > 1 else "") + f" · 필요 프레스 {d.press_tonf:,.0f} tf<br>"
            f"<b>금형 몸체: {body}</b><br>크기 {L:,.0f} × {W:,.0f} × {T:,.0f} mm"
            + (f" · 주물 {d.cast_kg:,.0f} kg" if d.structure == "주물" else f" · 강재 {d.steel_kg:,.0f} kg")
            + f" · 인서트 {d.insert_kg:,.0f} kg<br>공정: {' → '.join(d.ops)}<br><br>"
            "<table border=1 cellspacing=0 cellpadding=4 width=100%><tr><th>항목</th><th>산식</th><th>금액 (원)</th></tr>"
            f"{rows}<tr><td colspan=2><b>금형비 (VAT 별도)</b></td><td align=right><b>{supply:,.0f}</b></td></tr>"
            f"<tr><td colspan=2>부가세</td><td align=right>{vat:,.0f}</td></tr></table>"
            "<p style='color:#888'>대형 금형(주물)은 금형 무게 × kg 단가 + 형면 가공 시간 × 임률로 어림합니다 "
            "(다이 베이스 + 공구실 비용). 주물 단가는 회주철 FC300(=KS GC300), 구상흑연주철 FCD 는 고순도 선철을 써서 "
            "더 비쌉니다. 견적용 어림 — 금형 설계 후 확정하세요.</p>")
        try:
            from . import diesketch
            img = diesketch.render(d, 1200, 760)
            self.sketch.setPixmap(QPixmap.fromImage(img).scaled(self.sketch.width() or 900, self.sketch.height() or 380,
                                                               Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            import traceback
            traceback.print_exc()

    def save(self, kind="xlsx"):
        if self.q is None or not self.q.dies:
            QMessageBox.information(self, "금형비 계산", "금형이 필요 없는 부품입니다 (연간 생산량을 확인하세요).")
            return
        base = (self.item.name or "part") + "_금형견적"
        filt = "PDF (*.pdf)" if kind == "pdf" else "엑셀 (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "금형 견적 저장", base + (".pdf" if kind == "pdf" else ".xlsx"), filt)
        if not path:
            return
        stem = os.path.splitext(path)[0]
        out = []
        try:
            if kind in ("xlsx", "both"):
                qt_.save_die_xlsx(self.q, stem + ".xlsx")
                out.append(stem + ".xlsx")
            if kind in ("pdf", "both"):
                qt_.save_die_pdf(self.q, stem + ".pdf")
                out.append(stem + ".pdf")
        except Exception as e:
            QMessageBox.warning(self, "금형 견적 저장 실패", str(e))
            return
        if self.history is not None:
            try:
                self.history.add_doc("금형 견적", out, self.source_path, qt_.record_values(self.q, True),
                                     qt_.record_detail(self.q, True))
            except Exception:
                import traceback
                traceback.print_exc()
        QMessageBox.information(self, "금형비 계산", "저장했습니다.\n" + "\n".join(out))
        QDesktopServices.openUrl(QUrl.fromLocalFile(out[-1]))
