"""AI BOM 창: 도면 PDF 를 고르고, Claude 로 분석해 BOM 엑셀을 저장한다."""
from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout)

from . import ai_bom


class _Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, pdf, items, key):
        super().__init__()
        self.pdf, self.items, self.key = pdf, items, key

    def run(self):
        try:
            self.done.emit(ai_bom.analyze(self.pdf, self.items, api_key=self.key or None))
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(_explain(e))


def _explain(e):
    try:
        import anthropic
        if isinstance(e, anthropic.AuthenticationError):
            return "API 키가 맞지 않습니다. 키를 다시 확인해 주세요."
        if isinstance(e, anthropic.PermissionDeniedError):
            return "이 API 키로는 쓸 수 없는 기능입니다 (권한)."
        if isinstance(e, anthropic.RateLimitError):
            return "요청이 너무 많습니다. 잠시 뒤 다시 해 주세요."
        if isinstance(e, anthropic.APIConnectionError):
            return "인터넷(api.anthropic.com)에 연결하지 못했습니다. 회사 방화벽·프록시를 확인해 주세요."
        if isinstance(e, anthropic.APIStatusError):
            return f"AI 서버 오류 ({e.status_code}): {e.message}"
    except ImportError:
        return "AI 기능 모듈(anthropic)이 설치되어 있지 않습니다."
    return str(e)


class AiBomDialog(QDialog):
    """items: bom.build 결과 (3D). source_3d: 3D 파일 경로."""

    def __init__(self, items, source_3d, material="", density=7.85, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI BOM — 도면 PDF + 3D")
        self.resize(640, 260)
        self.items, self.source_3d = items, source_3d
        self.material, self.density = material, density
        self.st = QSettings("Hanil", "SheetUnfold")

        self.pdf = QLineEdit()
        self.pdf.setPlaceholderText("2D 도면 PDF (부품표·표제란이 있는 조립도)")
        guess = os.path.splitext(source_3d)[0] + ".pdf"
        if os.path.exists(guess):
            self.pdf.setText(guess)
        browse = QPushButton("찾기…")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.pdf, 1)
        row.addWidget(browse)

        self.key = QLineEdit(self.st.value("anthropic_api_key", "") or "")
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-…  (비우면 ANTHROPIC_API_KEY 환경 변수)")
        self.save_key = QCheckBox("이 PC 에 키 저장")
        self.save_key.setChecked(bool(self.key.text()))

        form = QFormLayout()
        form.addRow("도면 PDF", row)
        form.addRow("3D", QLabel(f"{os.path.basename(source_3d)}  ·  {len(items)} 품목 / "
                                 f"{sum(i.qty for i in items)} 개"))
        form.addRow("Anthropic API 키", self.key)
        form.addRow("", self.save_key)
        note = QLabel(f"도면과 3D 부품 목록을 Claude ({ai_bom.MODEL}) 에 보내 분석합니다. "
                      "요금은 API 사용량대로 나가며, 결과는 AI 가 읽은 값이므로 도면과 한 번 맞춰 보세요.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#777")
        run = QPushButton("분석해서 엑셀로 저장")
        run.setDefault(True)
        run.setMinimumHeight(32)
        run.clicked.connect(self.run)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        lay.addWidget(run)
        self._worker = None

    def _browse(self):
        start = self.pdf.text() or os.path.dirname(self.source_3d)
        path, _ = QFileDialog.getOpenFileName(self, "도면 PDF", start, "PDF (*.pdf)")
        if path:
            self.pdf.setText(path)

    def run(self):
        pdf = self.pdf.text().strip()
        if not os.path.isfile(pdf):
            QMessageBox.warning(self, "AI BOM", "도면 PDF 를 골라 주세요.")
            return
        key = self.key.text().strip()
        if not key and not os.environ.get("ANTHROPIC_API_KEY"):
            QMessageBox.warning(self, "AI BOM", "Anthropic API 키를 넣어 주세요.")
            return
        self.st.setValue("anthropic_api_key", key if self.save_key.isChecked() else "")
        self._prog = QProgressDialog("AI 가 도면을 읽고 3D 와 맞춰 보는 중… (1~3분)", None, 0, 0, self)
        self._prog.setWindowTitle("AI BOM")
        self._prog.setMinimumDuration(0)
        self._prog.setWindowModality(Qt.WindowModal)
        self._prog.show()
        self._worker = _Worker(pdf, self.items, key)
        self._worker.done.connect(lambda ai: self._done(ai, pdf))
        self._worker.failed.connect(self._failed)
        self._worker.start()

    def _failed(self, msg):
        self._prog.close()
        QMessageBox.warning(self, "AI BOM 실패", msg)

    def _done(self, ai, pdf):
        self._prog.close()
        base = os.path.splitext(self.source_3d)[0] + "_AI_BOM.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "AI BOM 저장", base, "엑셀 (*.xlsx)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            rows, unmatched = ai_bom.save_xlsx(ai, self.items, path, os.path.basename(self.source_3d),
                                               os.path.basename(pdf), self.material, self.density)
        finally:
            QApplication.restoreOverrideCursor()
        bad = sum(1 for r in rows if not r["qty_ok"])
        QMessageBox.information(
            self, "AI BOM",
            f"도면 {len(rows)} 줄 · 수량이 다르거나 짝 없는 줄 {bad} · 3D 에만 있는 품목 {len(unmatched)}\n{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.accept()
