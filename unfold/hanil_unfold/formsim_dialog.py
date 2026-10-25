"""성형 해석 창: 제품 3D 위의 성형성 존·두께·변형률 (마우스로 돌려 보기), 성형 한계도, 절곡 균열·스프링백, 하중."""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import bendcalc as bc
from . import formsim as fs
from .die_dialog import VERDICT_COLOR, _table


class ProductView(QWidget):
    """제품 메시 색 지도. 끌면 돌아가고, 다 그리는 데 시간이 걸려 그림을 저장해 두고 쓴다."""

    def __init__(self, fa, parent=None):
        super().__init__(parent)
        self.fa, self.view, self.az, self.el = fa, fs.VIEWS[0], -35.0, 30.0
        self.setMinimumSize(520, 420)
        self._pix, self._drag = None, None
        self._timer = QTimer(self, singleShot=True, interval=30, timeout=self._render)
        self.setToolTip("끌어서 돌리기 · 두 번 누르면 처음 방향")

    def set_view(self, view):
        self.view = view
        self._render()

    def _render(self):
        if self.width() < 10:
            return
        pix = QPixmap(self.size())
        pix.fill(QColor(255, 255, 255))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        fs.paint_product(p, QRectF(0, 0, self.width(), self.height()), self.fa, self.view, self.az, self.el)
        p.end()
        self._pix = pix
        self.update()

    def resizeEvent(self, e):
        self._timer.start()

    def paintEvent(self, e):
        p = QPainter(self)
        if self._pix is not None:
            p.drawPixmap(0, 0, self._pix)

    def mousePressEvent(self, e):
        self._drag = (e.position().x(), e.position().y(), self.az, self.el)

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        x0, y0, az, el = self._drag
        self.az = az + (e.position().x() - x0) * 0.5
        self.el = max(-89.0, min(89.0, el + (e.position().y() - y0) * 0.5))
        if not self._timer.isActive():
            self._timer.start()

    def mouseReleaseEvent(self, e):
        self._drag = None
        self._render()

    def mouseDoubleClickEvent(self, e):
        self.az, self.el = -35.0, 30.0
        self._render()


def _pct(rows, cols):
    return [[f"{v:.1%}" if j in cols and not isinstance(v, str) else v for j, v in enumerate(r)] for r in rows]


class FormSimDialog(QDialog):
    def __init__(self, result, settings: bc.BendSettings, name="", parent=None, history=None, source_path=""):
        super().__init__(parent)
        self.setWindowTitle(f"성형 해석 — {name}" if name else "성형 해석")
        self.resize(1300, 800)
        self.name, self.history, self.source_path = name, history, source_path
        self.fa = fa = fs.analyze(result, settings)
        col = VERDICT_COLOR[fa.verdict].name()
        head = QLabel(f"<b style='font-size:15px'>판정 <span style='color:{col}'>{fa.verdict}</span></b> · "
                      f"{fa.material} t {fa.thickness:g} · n {fa.n:g} · r {fa.r:g} · FLC0 {fa.flc0:.3f} · "
                      f"권장 프레스 {fa.press_tonf:.1f} tf · "
                      + ("원스텝 역해석 (제품 메시 위 변형률)" if fa.mode == "forming" else "판금 절곡 해석"))

        info = QTabWidget()
        # 요약
        w = QWidget()
        lw = QVBoxLayout(w)
        if fa.mode == "forming":
            lw.addWidget(QLabel("성형성 존 (넓이 비)"))
            lw.addWidget(_table(["성형성 존", "넓이 비", "판정"], _pct(fs.zone_rows(fa), (1,)),
                                [VERDICT_COLOR[z[2]] if f > 0.001 else None for z, f in zip(fs.ZONES, fa.zone_frac)]))
            lw.addWidget(QLabel(f"두께 {fa.t_min:.3f} ~ {fa.t_max:.3f} mm (얇아짐 최대 {max(fa.thin_hi, 0):.1%} · "
                                f"두꺼워짐 최대 {max(-fa.thin_lo, 0):.1%}) · 가장 큰 한계 비 {fa.risk_top:.0%}"))
        lw.addWidget(QLabel("하중"))
        lw.addWidget(_table(["하중", "kN", "tf", "설명"], fs.load_rows(fa)))
        msg = QTextBrowser()
        msg.setHtml("<br>".join(f"• {m}" for m in fa.messages) + "<br><br><span style='color:#888'>"
                    + "<br>".join(fs.NOTES) + "</span>")
        lw.addWidget(msg, 1)
        info.addTab(w, "요약")
        if fa.bends:
            info.addTab(_table(fs.BEND_HEAD, _pct(fs.bend_rows(fa), (5,)),
                               [VERDICT_COLOR[c.verdict] for c in fa.bends]), f"절곡 ({len(fa.bends)})")
        if fa.mode == "forming":
            from .report import render_fld
            lab = QLabel()
            lab.setPixmap(QPixmap.fromImage(render_fld(fa.fi, 760, 600)))
            lab.setAlignment(Qt.AlignCenter)
            info.addTab(lab, "성형 한계도 (FLD)")

        if fa.mode == "forming":
            self.view = ProductView(fa)
            box = QComboBox()
            box.addItems(fs.VIEWS)
            box.currentTextChanged.connect(self.view.set_view)
            left = QWidget()
            ll = QVBoxLayout(left)
            row = QHBoxLayout()
            row.addWidget(QLabel("보기"))
            row.addWidget(box)
            row.addStretch(1)
            row.addWidget(QLabel("<span style='color:#888'>끌어서 돌리기 · 두 번 눌러 처음 방향</span>"))
            ll.addLayout(row)
            ll.addWidget(self.view, 1)
            split = QSplitter()
            split.addWidget(left)
            split.addWidget(info)
            split.setSizes([700, 600])
            body = split
        else:
            body = info

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for text, kind in (("엑셀…", "xlsx"), ("PDF…", "pdf"), ("엑셀 + PDF 모두…", "both")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, k_=kind: self.save(k_))
            buttons.addWidget(b)
        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(head)
        lay.addWidget(body, 1)
        lay.addLayout(buttons)

    def _log(self, files):
        if self.history is None:
            return
        fa = self.fa
        if fa.mode == "forming":
            fr = fa.zone_frac
            summ = (f"성형 해석 {fa.verdict} · 파단 {fr[0]:.1%} · 위험 {fr[1]:.1%} · 두께 {fa.t_min:.2f}~{fa.t_max:.2f} mm"
                    f" · 프레스 {fa.press_tonf:.0f} tf")
            detail = {"checks": [[z[0], f"{f:.1%}", z[2]] for z, f in zip(fs.ZONES, fa.zone_frac)]}
        else:
            summ = f"성형 해석 {fa.verdict} · 절곡 {len(fa.bends)} · 균열 위험도 최대 {fa.risk_top:.0%}"
            detail = {"checks": [[f"B{c.no}", f"R {c.radius:.2f}", f"{c.risk:.0%}", c.verdict] for c in fa.bends]}
        v = dict(title=self.name, material=fa.material, max_tonf=fa.press_tonf, parts=1, summary=summ)
        try:
            self.history.add_doc("성형 해석", files, self.source_path, v, detail)
        except Exception:
            import traceback
            traceback.print_exc()

    def save(self, kind="xlsx"):
        base = os.path.splitext(self.name or "part")[0] + "_성형해석"
        filt = "PDF (*.pdf)" if kind == "pdf" else "엑셀 (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "성형 해석 저장", base + (".pdf" if kind == "pdf" else ".xlsx"), filt)
        if not path:
            return
        stem = os.path.splitext(path)[0]
        out = []
        try:
            if kind in ("xlsx", "both"):
                fs.save_xlsx(self.fa, stem + ".xlsx", self.name)
                out.append(stem + ".xlsx")
            if kind in ("pdf", "both"):
                fs.save_pdf(self.fa, stem + ".pdf", self.name)
                out.append(stem + ".pdf")
        except Exception as e:
            QMessageBox.warning(self, "성형 해석 저장 실패", str(e))
            return
        self._log(out)
        QMessageBox.information(self, "성형 해석", "저장했습니다.\n" + "\n".join(out))
        QDesktopServices.openUrl(QUrl.fromLocalFile(out[-1]))
