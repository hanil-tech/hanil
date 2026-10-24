"""견적·금형 기록 창: 저장한 생산 견적서·금형 견적서·금형 검토를 찾아보고, 사본을 열고, 엑셀로 내보낸다."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QFileDialog,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout)

from .history import DOC_LABELS

SHOW = ["id", "created", "kind", "title", "customer", "material", "sets", "annual", "unit_price", "total",
        "die_total", "max_tonf", "total_ops", "machines", "note"]
NUMS = {"id", "sets", "annual", "unit_price", "total", "die_total", "max_tonf", "total_ops"}
KINDS = ["", "생산 견적", "금형 견적", "금형 검토"]


class DocHistoryDialog(QDialog):
    def __init__(self, history, open_source=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("견적·금형 기록")
        self.resize(1300, 720)
        self.history, self.open_source = history, open_source
        self.records = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("제품 · 수신 업체 · 파일 · 재질 · 메모로 찾기")
        self.search.textChanged.connect(self.refresh)
        self.kind = QComboBox()
        for k in KINDS:
            self.kind.addItem(k or "모든 종류", k)
        self.kind.currentIndexChanged.connect(self.refresh)
        self.use_date = QCheckBox("기간")
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-3))
        self.date_to = QDateEdit(QDate.currentDate())
        for w in (self.date_from, self.date_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.dateChanged.connect(self.refresh)
        self.use_date.toggled.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(self.search, 3)
        top.addWidget(self.kind)
        top.addWidget(self.use_date)
        top.addWidget(self.date_from)
        top.addWidget(QLabel("~"))
        top.addWidget(self.date_to)

        self.table = QTableWidget(0, len(SHOW))
        self.table.setHorizontalHeaderLabels([DOC_LABELS[c] for c in SHOW])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.open_copy)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.detail = QTextBrowser()
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setSizes([460, 200])
        self.summary = QLabel()

        buttons = QHBoxLayout()
        for text, slot in (("보관 사본 열기", self.open_copy), ("저장했던 파일 열기", self.open_saved),
                           ("원본 다시 열기", self.reopen), ("메모", self.edit_note),
                           ("엑셀로 내보내기", self.export), ("보관 폴더 열기", self.open_folder),
                           ("선택 삭제", self.remove)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch()
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)
        lay.addWidget(self.summary)
        lay.addLayout(buttons)
        self.refresh()

    def refresh(self):
        df = self.date_from.date().toString("yyyy-MM-dd") if self.use_date.isChecked() else ""
        dt = self.date_to.date().toString("yyyy-MM-dd") if self.use_date.isChecked() else ""
        self.records = self.history.search_docs(self.search.text(), self.kind.currentData(), df, dt)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.records))
        for i, r in enumerate(self.records):
            for j, c in enumerate(SHOW):
                v = r.data.get(c)
                if c == "created" and v:
                    v = v.replace("T", " ")[:16]
                elif c in ("unit_price", "total", "die_total") and v is not None:
                    v = f"{v:,.0f}"
                elif c == "max_tonf" and v is not None:
                    v = f"{v:,.1f}"
                item = QTableWidgetItem("" if v is None else str(v))
                if c in NUMS:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    raw = r.data.get(c)
                    if raw is not None:
                        item.setData(Qt.EditRole, round(raw, 1) if c == "max_tonf" else
                                     round(raw) if c in ("unit_price", "total", "die_total") else raw)
                item.setData(Qt.UserRole, r.id)
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.DescendingOrder)
        tot = sum(r.data.get("total") or 0 for r in self.records if r.data.get("kind") == "생산 견적")
        die = sum(r.data.get("total") or 0 for r in self.records if r.data.get("kind") == "금형 견적")
        self.summary.setText(f"기록 {len(self.records)}건 (전체 {self.history.count_docs()}건) · "
                             f"생산 견적 합계 {tot:,.0f} 원 · 금형 견적 합계 {die:,.0f} 원 · "
                             f"보관 위치: {self.history.archive_root}")

    def _selected(self):
        ids = sorted({self.table.item(i.row(), 0).data(Qt.UserRole) for i in self.table.selectedIndexes()})
        return [r for r in self.records if r.id in ids]

    def show_detail(self):
        sel = self._selected()
        if not sel:
            self.detail.clear()
            return
        r = sel[0].data
        html = [f"<b>{r.get('kind')}</b> · {r.get('title') or ''} · {r.get('customer') or ''}<br>{r.get('summary') or ''}"]
        try:
            d = json.loads(r.get("detail") or "null")
        except ValueError:
            d = None
        if isinstance(d, list):
            html.append("<table border=1 cellspacing=0 cellpadding=3><tr><th>품번</th><th>품명</th><th>수량</th>"
                        "<th>방식</th><th>공정</th><th>톤수</th><th>기계</th><th>자재/개</th><th>가공/개</th><th>금형</th></tr>")
            for p in d:
                html.append("<tr>" + "".join(f"<td>{p.get(k, '') if p.get(k) is not None else ''}</td>" for k in
                                              ("no", "name", "qty", "method", "n_ops", "tonf", "machines",
                                               "material", "process", "die")) + "</tr>")
            html.append("</table>")
        elif isinstance(d, dict):
            for key, title in (("route", "자동 공정 설계"), ("stations", "공정도"), ("checks", "설계 규칙")):
                if d.get(key):
                    html.append(f"<p><b>{title}</b><br>" + "<br>".join(" · ".join(str(x) for x in row)
                                                                        for row in d[key]) + "</p>")
        html.append(f"<p style='color:#888'>저장한 파일: {r.get('files') or ''}<br>보관 사본: {r.get('archived') or ''}</p>")
        self.detail.setHtml("".join(html))

    def _open_files(self, key):
        sel = self._selected()
        if not sel:
            return
        files = [f for f in (sel[0].data.get(key) or "").split(";") if f]
        ok = [f for f in files if os.path.exists(f)]
        if not ok:
            QMessageBox.information(self, "견적·금형 기록", "파일을 찾을 수 없습니다 (옮겼거나 지웠음).")
            return
        for f in ok:
            QDesktopServices.openUrl(QUrl.fromLocalFile(f))

    def open_copy(self, *_):
        self._open_files("archived")

    def open_saved(self):
        self._open_files("files")

    def reopen(self):
        sel = self._selected()
        if not sel or not sel[0].data.get("source_path"):
            return
        path = sel[0].data["source_path"]
        if not os.path.exists(path):
            QMessageBox.information(self, "견적·금형 기록", f"원본 파일이 없습니다.\n{path}")
            return
        if self.open_source:
            self.open_source(path, 1)
            self.accept()
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def edit_note(self):
        sel = self._selected()
        if not sel:
            return
        text, ok = QInputDialog.getText(self, "메모", "메모 (수주·실패·수정 내용 등)", text=sel[0].data.get("note") or "")
        if ok:
            self.history.set_doc_note(sel[0].id, text)
            self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "견적·금형 기록 내보내기", "견적_금형_기록.xlsx", "엑셀 (*.xlsx)")
        if path:
            self.history.export_docs_xlsx(path, self.records)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_folder(self):
        os.makedirs(self.history.archive_root, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.history.archive_root))

    def remove(self):
        sel = self._selected()
        if not sel:
            return
        if QMessageBox.question(self, "견적·금형 기록", f"{len(sel)}건을 지울까요? (보관 사본도 지웁니다)") \
                != QMessageBox.Yes:
            return
        self.history.delete_docs([r.id for r in sel])
        self.refresh()
