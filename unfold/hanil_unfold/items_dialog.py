"""아이템 (견적 요청) 대장 창: 받은 아이템 등록 · 상태 (접수 → 견적 중 → 제출 → 수주/실주) · 견적 리비전 비교."""
from __future__ import annotations

import datetime as _dt
import json
import os

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout)

from .items import ITEM_LABELS, STATUSES

SHOW = ["id", "status", "customer", "project", "part_no", "part_name", "drawing_rev", "annual", "due", "sop",
        "unit_price", "die_total", "owner", "updated", "note"]
STATUS_COLOR = {"접수": QColor(120, 120, 120), "견적 중": QColor(30, 110, 200), "제출": QColor(200, 130, 0),
                "수주": QColor(30, 150, 60), "실주": QColor(200, 50, 50), "보류": QColor(140, 100, 160)}


class _Num(QTableWidgetItem):
    """천 단위 쉼표로 보이고 숫자로 정렬되는 칸."""

    def __init__(self, v):
        super().__init__(f"{v:,.0f}")
        self.v = float(v)
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):
        return self.v < getattr(other, "v", float("-inf"))


class ItemForm(QDialog):
    def __init__(self, data=None, parent=None, source_path=""):
        super().__init__(parent)
        self.setWindowTitle("아이템 고치기" if data else "새 아이템")
        d = dict(data or {})
        if not d.get("source_path") and source_path:
            d["source_path"] = source_path
        form = QFormLayout(self)
        self.w = {}
        for k in ("customer", "project", "part_no", "part_name", "drawing_rev", "owner", "note"):
            e = QLineEdit(d.get(k) or "")
            self.w[k] = e
            form.addRow(ITEM_LABELS[k], e)
        self.annual = QSpinBox()
        self.annual.setRange(0, 100_000_000)
        self.annual.setGroupSeparatorShown(True)
        self.annual.setSingleStep(10_000)
        self.annual.setValue(int(d.get("annual") or 0))
        form.addRow(ITEM_LABELS["annual"], self.annual)
        self.dates = {}
        for k in ("due", "sop", "eop"):
            de = QDateEdit()
            de.setCalendarPopup(True)
            de.setDisplayFormat("yyyy-MM-dd")
            v = d.get(k)
            de.setDate(QDate.fromString(v, "yyyy-MM-dd") if v else QDate.currentDate().addDays(14 if k == "due" else 365))
            self.dates[k] = de
            form.addRow(ITEM_LABELS[k], de)
        self.status = QComboBox()
        self.status.addItems(STATUSES)
        self.status.setCurrentText(d.get("status") or "접수")
        form.addRow(ITEM_LABELS["status"], self.status)
        row = QHBoxLayout()
        self.src = QLineEdit(d.get("source_path") or "")
        b = QPushButton("찾기…")
        b.clicked.connect(self._browse)
        row.addWidget(self.src)
        row.addWidget(b)
        form.addRow(ITEM_LABELS["source_path"], row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "3D 도면", self.src.text(), "3D (*.step *.stp *.iges *.igs *.stl);;모든 파일 (*)")
        if p:
            self.src.setText(p)

    def values(self):
        v = {k: e.text().strip() for k, e in self.w.items()}
        v["annual"] = self.annual.value()
        for k, de in self.dates.items():
            v[k] = de.date().toString("yyyy-MM-dd")
        v["status"] = self.status.currentText()
        v["source_path"] = self.src.text().strip()
        return v


class ItemsDialog(QDialog):
    """quote_item(source_path, item_id): 그 도면을 열고 견적 창을 아이템에 이어서 연다 (메인 창이 줌)."""

    def __init__(self, history, parent=None, quote_item=None, current_path=""):
        super().__init__(parent)
        self.setWindowTitle("아이템 대장 (견적 요청)")
        self.resize(1300, 760)
        self.history, self.quote_item, self.current_path = history, quote_item, current_path
        self.search = QLineEdit()
        self.search.setPlaceholderText("고객 · 차종 · 품번 · 품명 · 담당 · 메모로 찾기")
        self.search.textChanged.connect(self.refresh)
        self.status = QComboBox()
        self.status.addItem("모든 상태", "")
        for s in STATUSES:
            self.status.addItem(s, s)
        self.status.currentIndexChanged.connect(self.refresh)
        top = QHBoxLayout()
        top.addWidget(self.search, 3)
        top.addWidget(self.status)
        self.table = QTableWidget(0, len(SHOW))
        self.table.setHorizontalHeaderLabels([ITEM_LABELS[c] for c in SHOW])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self.edit)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.detail = QTextBrowser()
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setSizes([480, 220])
        self.summary = QLabel()
        buttons = QHBoxLayout()
        for text, slot in (("새 아이템…", self.add), ("고치기…", self.edit), ("견적 내기 (도면 열고 견적 창)", self.quote),
                           ("수주", lambda: self.set_status("수주")), ("실주", lambda: self.set_status("실주")),
                           ("엑셀로 내보내기", self.export), ("선택 삭제", self.remove)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)
        lay.addWidget(self.summary)
        lay.addLayout(buttons)
        self.records = []
        self.refresh()

    def refresh(self, *_):
        self.records = self.history.search_items(self.search.text(), self.status.currentData())
        t = self.table
        t.setSortingEnabled(False)
        t.setRowCount(len(self.records))
        today = _dt.date.today().isoformat()
        for i, r in enumerate(self.records):
            for j, c in enumerate(SHOW):
                v = r.data.get(c)
                if c in ("unit_price", "die_total", "annual", "id") and v not in (None, ""):
                    it = _Num(v)
                else:
                    it = QTableWidgetItem("" if v is None else str(v)[:16].replace("T", " ") if c == "updated" else str(v))
                it.setData(Qt.UserRole, r.id)
                if c == "status":
                    it.setForeground(STATUS_COLOR.get(v, QColor(0, 0, 0)))
                if c == "due" and v and v < today and r.data.get("status") in ("접수", "견적 중"):
                    it.setForeground(QColor(220, 40, 40))
                    it.setToolTip("견적 마감이 지났습니다")
                t.setItem(i, j, it)
        t.setSortingEnabled(True)
        stats, rate = self.history.item_stats()
        parts = [f"{s} {stats[s][0]}" for s in STATUSES if s in stats]
        won = stats.get("수주", (0, 0))[1]
        self.summary.setText(f"아이템 {len(self.records)}건 · " + " · ".join(parts)
                             + (f" · 수주율 {rate:.0%}" if rate is not None else "")
                             + (f" · 수주 연 매출 (단가 × 연간 수량) {won:,.0f} 원" if won else ""))

    def _selected(self):
        ids = sorted({self.table.item(i.row(), 0).data(Qt.UserRole) for i in self.table.selectedIndexes()})
        return [r for r in self.records if r.id in ids]

    def show_detail(self):
        sel = self._selected()
        if not sel:
            self.detail.clear()
            return
        d = sel[0].data
        revs = json.loads(d.get("revisions") or "[]")
        html = [f"<b>{d.get('customer') or ''} · {d.get('project') or ''} · {d.get('part_no') or ''} "
                f"{d.get('part_name') or ''}</b> (도면 {d.get('drawing_rev') or '-'}) — <b>{d.get('status')}</b><br>"
                f"연간 {int(d.get('annual') or 0):,} · 양산 {d.get('sop') or '-'} ~ {d.get('eop') or '-'} · "
                f"견적 마감 {d.get('due') or '-'} · 담당 {d.get('owner') or '-'}<br>3D: {d.get('source_path') or '-'}"]
        if revs:
            html.append("<table border=1 cellspacing=0 cellpadding=3><tr><th>Rev</th><th>날짜</th><th>세트 단가</th>"
                        "<th>앞 Rev 대비</th><th>금형비</th><th>연간 수량</th><th>메모</th><th>파일</th></tr>")
            prev = None
            for rv in revs:
                diff = f"{rv['unit_price'] / prev - 1:+.1%}" if prev else ""
                html.append(f"<tr><td>{rv['rev']}</td><td>{rv['date']}</td><td align=right>{rv['unit_price']:,}</td>"
                            f"<td align=right>{diff}</td><td align=right>{rv['die_total']:,}</td>"
                            f"<td align=right>{(rv.get('annual') or 0):,}</td><td>{rv.get('note') or ''}</td>"
                            f"<td>{', '.join(os.path.basename(f) for f in rv.get('files') or [])}</td></tr>")
                prev = rv["unit_price"] or prev
            html.append("</table>")
        else:
            html.append("<p style='color:#888'>아직 낸 견적이 없습니다 — [견적 내기] 로 견적 창을 열고 견적서를 저장하면 "
                        "리비전 (R0, R1 …) 이 쌓입니다.</p>")
        self.detail.setHtml("".join(html))

    def add(self):
        f = ItemForm(parent=self, source_path=self.current_path)
        if f.exec():
            self.history.add_item(f.values())
            self.refresh()

    def edit(self, *_):
        sel = self._selected()
        if not sel:
            return
        f = ItemForm(sel[0].data, self)
        if f.exec():
            self.history.update_item(sel[0].id, f.values())
            self.refresh()

    def set_status(self, st):
        for r in self._selected():
            self.history.update_item(r.id, {"status": st})
        self.refresh()

    def quote(self):
        sel = self._selected()
        if not sel:
            return
        path = sel[0].data.get("source_path") or ""
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "아이템 대장", "3D 도면 경로가 없거나 파일이 없습니다 — [고치기] 에서 넣으세요.")
            return
        if self.quote_item:
            self.accept()
            self.quote_item(path, sel[0].id)

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, "아이템 대장 내보내기", "아이템_대장.xlsx", "엑셀 (*.xlsx)")
        if p:
            self.history.export_items_xlsx(p, self.records)
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def remove(self):
        sel = self._selected()
        if sel and QMessageBox.question(self, "아이템 대장", f"{len(sel)}건을 지울까요?") == QMessageBox.Yes:
            self.history.delete_items([r.id for r in sel])
            self.refresh()
