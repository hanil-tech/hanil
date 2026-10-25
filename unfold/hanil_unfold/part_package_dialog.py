"""부품 한 번에 분석 창: 도면(조립품)에서 부품 하나를 골라 전개·성형 해석·금형 설계·금형 견적·원가계산서·
생산 계획·품질 문서를 한 폴더에."""
from __future__ import annotations

import datetime as _dt
import os

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressDialog, QPushButton, QSpinBox, QTextBrowser,
                               QVBoxLayout)

from . import part_package as ppk
from . import quote as qt_


class PartPackageDialog(QDialog):
    """select_part(i) → (result, solid, name): 메인 창에서 그 부품을 전개해 돌려준다."""

    def __init__(self, model, index, select_part, settings_fn, parent=None, history=None, items_db=None):
        super().__init__(parent)
        self.setWindowTitle("부품 한 번에 분석 — 전개 · 성형 해석 · 금형 설계 · 원가 · 생산 · 품질")
        self.resize(980, 720)
        self.model, self.select_part, self.settings_fn = model, select_part, settings_fn
        self.history, self.items_db = history, items_db if items_db is not None else history
        self.st = QSettings("Hanil", "SheetUnfold")
        self.files, self.folder = [], ""

        self.part = QComboBox()
        for i in range(len(model.solids)):
            self.part.addItem(model.label(i), i)
        self.part.setCurrentIndex(max(index, 0))
        self.part.currentIndexChanged.connect(self._part_changed)
        self.part_info = QLabel()
        self.part_info.setWordWrap(True)
        self.annual = QSpinBox()
        self.annual.setRange(1, 100_000_000)
        self.annual.setSingleStep(10_000)
        self.annual.setGroupSeparatorShown(True)
        self.annual.setSuffix(" 개/년")
        self.annual.setValue(int(self.st.value("quote_annual", 100_000)))
        self.customer = QLineEdit(self.st.value("quote_customer", "") or "")
        self.customer.setPlaceholderText("고객 (견적서·품질 문서에)")
        self.item = QComboBox()
        self.item.addItem("(아이템 대장과 잇지 않음)", None)
        if self.items_db is not None:
            for r in self.items_db.search_items():
                d = r.data
                self.item.addItem(f"{d.get('customer') or ''} {d.get('part_no') or ''} {d.get('part_name') or ''} "
                                  f"[{d.get('status')}]".strip(), r.id)
        self.item.currentIndexChanged.connect(self._item_changed)
        row = QHBoxLayout()
        self.dir = QLineEdit(self.st.value("part_package_dir", "") or os.path.dirname(model.path))
        b = QPushButton("바꾸기…")
        b.clicked.connect(self._browse)
        row.addWidget(self.dir, 1)
        row.addWidget(b)
        form = QFormLayout()
        form.addRow("부품 (도면에서 하나)", self.part)
        form.addRow("", self.part_info)
        form.addRow("연간 생산량", self.annual)
        form.addRow("고객", self.customer)
        form.addRow("아이템 대장", self.item)
        form.addRow("결과 폴더 (안에 새 폴더)", row)

        self.out = QTextBrowser()
        self.out.setOpenExternalLinks(False)
        self.out.anchorClicked.connect(lambda u: QDesktopServices.openUrl(u))
        self.out.setHtml("<p>부품을 고르고 <b>[한 번에 분석]</b> 을 누르세요. 다음을 한 폴더에 만듭니다:</p><ol>"
                         "<li>전개도 DXF · 전개 보고서 (PDF·엑셀)</li><li>성형 해석 (성형성 존·두께·FLD / 절곡 균열·스프링백)</li>"
                         "<li>금형 검토 (하중·클리어런스·설계 규칙·스트립·드로잉·자동 공정 설계)</li><li>금형 공정도 (PDF·DXF)</li>"
                         "<li>생산 견적서 · 금형 견적서 (금형 간략도, 큰 금형은 주물)</li><li>원가계산서 (수량별 단가표)</li>"
                         "<li>생산 계획 (설비 부하·인원·소재·금형 → 양산 일정)</li><li>품질 문서 (공정 흐름도·PFMEA·관리계획서)</li>"
                         "<li>첫 장: 한 쪽 요약</li></ol>")
        run = QPushButton("한 번에 분석")
        run.setStyleSheet("QPushButton { font-weight: bold; padding: 6px 18px; }")
        run.setDefault(True)
        run.clicked.connect(self.run)
        self.open_sum = QPushButton("요약 열기")
        self.open_sum.clicked.connect(lambda: self.files and QDesktopServices.openUrl(QUrl.fromLocalFile(self.files[0])))
        self.open_dir = QPushButton("폴더 열기")
        self.open_dir.clicked.connect(lambda: self.folder and QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder)))
        for x in (self.open_sum, self.open_dir):
            x.setEnabled(False)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        btns = QHBoxLayout()
        btns.addStretch(1)
        for x in (run, self.open_sum, self.open_dir, close):
            btns.addWidget(x)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.out, 1)
        lay.addLayout(btns)
        self._part_changed()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "결과 폴더", self.dir.text())
        if d:
            self.dir.setText(d)

    def _item_changed(self, *_):
        rid = self.item.currentData()
        if rid is None or self.items_db is None:
            return
        it = self.items_db.get_item(rid)
        if it is not None:
            if it.data.get("annual"):
                self.annual.setValue(int(it.data["annual"]))
            if it.data.get("customer"):
                self.customer.setText(it.data["customer"])

    def _part_changed(self, *_):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.cur = self.select_part(self.part.currentData())
        finally:
            QApplication.restoreOverrideCursor()
        r = self.cur[0] if self.cur else None
        if r is None:
            self.part_info.setText("<span style='color:#d33'>이 부품은 펼칠 수 없습니다 (판금·성형품이 아님) — 다른 부품을 고르세요.</span>")
        else:
            w, h = r.size
            self.part_info.setText(f"<span style='color:#555'>{'성형품 근사' if r.mode == 'forming' else '판금 정확'} 전개 · "
                                   f"t {r.thickness:g} · {w:,.1f} × {h:,.1f} mm · 절곡 {len(r.bends)} 곳</span>")

    def run(self):
        if not self.cur or self.cur[0] is None:
            QMessageBox.information(self, "부품 한 번에 분석", "펼칠 수 있는 부품을 고르세요.")
            return
        result, solid, name = self.cur
        root = self.dir.text().strip() or os.path.dirname(self.model.path)
        self.st.setValue("part_package_dir", root)
        self.st.setValue("quote_annual", self.annual.value())
        self.st.setValue("quote_customer", self.customer.text())
        self.folder = os.path.join(root, f"{ppk._safe(os.path.splitext(name)[0])}_부품분석_{_dt.datetime.now():%Y%m%d_%H%M}")
        rates = qt_.load_rates(self.st.value("quote_rates", ""))
        prog = QProgressDialog("부품 분석 중…", None, 0, 0, self)
        prog.setWindowTitle("부품 한 번에 분석")
        prog.setMinimumDuration(0)
        prog.setWindowModality(Qt.WindowModal)
        prog.show()

        def step(t):
            prog.setLabelText(f"부품 분석 중… {t}")
            QApplication.processEvents()
        settings = self.settings_fn()
        try:
            self.files, summ = ppk.run(result, settings, name, self.folder, self.annual.value(), rates,
                                       self.customer.text().strip(), solid, self.model.path, step)
        except Exception as e:
            prog.close()
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "부품 분석 실패", str(e))
            return
        prog.close()
        html = [f"<h3>{name} — 분석 끝 ({len(self.files)} 파일)</h3><table border=1 cellspacing=0 cellpadding=4>"]
        for k, v in summ.items():
            html.append(f"<tr><td style='background:#1f4e8c;color:white'><b>{k}</b></td><td>{v}</td></tr>")
        html.append("</table><p><b>파일</b> (누르면 열림)<br>")
        for f in self.files:
            html.append(f"<a href='{QUrl.fromLocalFile(f).toString()}'>{os.path.basename(f)}</a><br>")
        html.append("</p>")
        self.out.setHtml("".join(html))
        for x in (self.open_sum, self.open_dir):
            x.setEnabled(True)
        self._log(summ)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.files[0]))

    def _log(self, summ):
        rid = self.item.currentData()
        price = 0.0
        try:
            price = float(summ.get("판매 단가", "0").split(" ")[0].replace(",", ""))
        except ValueError:
            pass
        die = 0.0
        try:
            die = float(summ.get("금형비", "0").split(" ")[0].replace(",", ""))
        except ValueError:
            pass
        if rid is not None and self.items_db is not None:
            try:
                self.items_db.add_revision(rid, price, die, self.annual.value(), "부품 한 번에 분석", self.files[:1])
            except Exception:
                import traceback
                traceback.print_exc()
        if self.history is not None:
            try:
                v = dict(title=summ.get("부품"), customer=self.customer.text().strip(), annual=self.annual.value(),
                         unit_price=price, die_total=die, material=summ.get("재질·두께"), parts=1,
                         summary=" · ".join(f"{k} {v}" for k, v in summ.items() if k in ("성형 해석", "금형 형식", "금형비",
                                                                                       "판매 단가", "양산 일정")))
                self.history.add_doc("부품 분석", self.files, self.model.path, v, {"checks": [[k, v] for k, v in summ.items()]})
            except Exception:
                import traceback
                traceback.print_exc()
