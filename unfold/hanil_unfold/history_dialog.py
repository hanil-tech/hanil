"""전개 기록 창: 쌓인 기록을 찾아보고, 엑셀로 내보내고, 보관 DXF 를 연다."""
from __future__ import annotations

import os

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDateEdit, QDialog, QFileDialog,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from .history import LABELS

SHOW = ["id", "updated", "source_name", "part_index", "mode", "material", "thickness", "width",
        "height", "weight_kg", "yield_ratio", "cut_length", "bends", "bend_summary", "note",
        "app_version"]


class HistoryDialog(QDialog):
    def __init__(self, history, open_source=None, change_folder=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("전개 기록")
        self.resize(1300, 680)
        self.history = history
        self.open_source = open_source
        self.change_folder = change_folder
        self.records = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("파일 이름 · 재질 · 메모로 찾기 (띄어 쓰면 모두 포함)")
        self.search.textChanged.connect(self.refresh)
        self.use_date = QCheckBox("기간")
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(QDate.currentDate())
        for w in (self.date_from, self.date_to):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.dateChanged.connect(self.refresh)
        self.use_date.toggled.connect(self.refresh)

        top = QHBoxLayout()
        top.addWidget(self.search, 3)
        top.addWidget(self.use_date)
        top.addWidget(self.date_from)
        top.addWidget(QLabel("~"))
        top.addWidget(self.date_to)

        self.table = QTableWidget(0, len(SHOW))
        self.table.setHorizontalHeaderLabels([LABELS[c] for c in SHOW])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.open_dxf)

        self.summary = QLabel()

        buttons = QHBoxLayout()
        for text, slot in (("보관 DXF 열기", self.open_dxf), ("원본 다시 열기", self.reopen),
                           ("메모", self.edit_note), ("엑셀로 내보내기", self.export),
                           ("보관 폴더 열기", self.open_folder), ("보관 위치 바꾸기", self.move),
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
        lay.addWidget(self.table)
        lay.addWidget(self.summary)
        lay.addLayout(buttons)
        self.refresh()

    # ---- 목록

    def refresh(self):
        df = self.date_from.date().toString("yyyy-MM-dd") if self.use_date.isChecked() else ""
        dt = self.date_to.date().toString("yyyy-MM-dd") if self.use_date.isChecked() else ""
        self.records = self.history.search(self.search.text(), df, dt)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.records))
        for i, r in enumerate(self.records):
            for j, c in enumerate(SHOW):
                v = r.data.get(c)
                if c == "updated" and v:
                    v = v.replace("T", " ")[:16]
                elif c == "mode":
                    v = "성형품(근사)" if v == "forming" else "판금"
                elif c == "part_index" and (r.data.get("part_count") or 1) > 1:
                    v = f"{v}/{r.data['part_count']}"
                elif c == "yield_ratio" and v is not None:
                    v = f"{v:.0%}"
                elif isinstance(v, float):
                    v = f"{v:.3f}" if c == "weight_kg" else f"{v:.2f}"
                item = QTableWidgetItem("" if v is None else str(v))
                if c in ("id", "thickness", "width", "height", "weight_kg", "cut_length", "bends"):
                    raw = r.data.get(c)                         # 숫자로 정렬
                    if isinstance(raw, float):
                        raw = round(raw, 3 if c == "weight_kg" else 2)
                    item.setData(Qt.EditRole, raw)
                item.setData(Qt.UserRole, r.id)
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.DescendingOrder)     # 최근 기록이 위로
        total = sum(r.data.get("weight_kg") or 0 for r in self.records)
        cut = sum(r.data.get("cut_length") or 0 for r in self.records)
        self.summary.setText(
            f"기록 {len(self.records)}건 (전체 {self.history.count()}건)   ·   "
            f"블랭크 무게 합계 {total:,.3f} kg   ·   절단 길이 합계 {cut / 1000:,.2f} m   ·   "
            f"보관 위치: {self.history.folder}")

    def _selected(self):
        ids = sorted({self.table.item(i.row(), 0).data(Qt.UserRole)
                      for i in self.table.selectionModel().selectedRows()})
        by_id = {r.id: r for r in self.records}
        return [by_id[i] for i in ids if i in by_id]

    # ---- 단추

    def open_dxf(self, *_):
        for r in self._selected()[:5]:
            p = r.data.get("archive_dxf")
            if p and os.path.exists(p):
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
            else:
                QMessageBox.information(self, "전개 기록", "보관 DXF 가 없습니다.")

    def reopen(self):
        sel = self._selected()
        if not sel:
            return
        p = sel[0].data.get("source_path")
        if not p or not os.path.exists(p):
            QMessageBox.information(self, "전개 기록", f"원본 파일을 찾을 수 없습니다.\n{p}")
            return
        if self.open_source:
            self.open_source(p, sel[0].data.get("part_index") or 1)
            self.accept()

    def edit_note(self):
        sel = self._selected()
        if not sel:
            return
        text, ok = QInputDialog.getText(self, "메모", "메모 (주문처, 수량, 도면 번호 등)",
                                        text=sel[0].data.get("note") or "")
        if ok:
            for r in sel:
                self.history.set_note(r.id, text)
            self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "전개 기록 엑셀", "전개기록.xlsx", "엑셀 (*.xlsx)")
        if not path:
            return
        sel = self._selected()
        self.history.export_xlsx(path, sel if len(sel) > 1 else self.records)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_folder(self):
        os.makedirs(self.history.archive_root, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.history.archive_root))

    def remove(self):
        sel = self._selected()
        if not sel:
            return
        if QMessageBox.question(self, "삭제", f"기록 {len(sel)}건과 보관 DXF 를 지울까요?") != QMessageBox.Yes:
            return
        self.history.delete([r.id for r in sel])
        self.refresh()

    def move(self):
        """기록 위치를 바꾼다. 공유 폴더로 지정하면 여러 PC 의 기록을 한곳에 모을 수 있다."""
        if self.change_folder is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "전개 기록을 둘 폴더", self.history.folder)
        if not folder:
            return
        self.history = self.change_folder(folder)
        self.refresh()
