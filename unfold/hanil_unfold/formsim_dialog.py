"""성형 해석 창: 제품 3D 위의 성형성 존·두께·변형률 (마우스로 돌려 보기), 성형 한계도, 절곡 균열·스프링백, 하중."""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from . import bendcalc as bc
from . import formexplain as fx
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


REANALYZE = 2          # exec() 값: FLC 를 바꿔 다시 해석해 달라


class SectionPanel(QWidget):
    """단면: X·Y·Z 평면 위치를 옮기며 그 단면을 따라 두께 변화 그래프 (시험품을 잘라 잰 두께와 견주기)."""

    def __init__(self, fa, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QSlider
        self.fa = fa
        V = fa.fi.V
        self.axis = QComboBox()
        self.axis.addItems(["X", "Y", "Z"])
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(500)
        self.pos = QLabel()
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.pic = QLabel()
        self.pic.setAlignment(Qt.AlignCenter)
        self.pic.setMinimumSize(520, 380)
        self._lo, self._hi = V.min(0), V.max(0)
        self.axis.currentIndexChanged.connect(self._update)
        self.slider.valueChanged.connect(self._update)
        exp = QPushButton("이 단면 엑셀로…")
        exp.clicked.connect(self._export)
        row = QHBoxLayout()
        row.addWidget(QLabel("단면 축"))
        row.addWidget(self.axis)
        row.addWidget(self.slider, 1)
        row.addWidget(self.pos)
        row.addWidget(exp)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.pic, 1)
        lay.addWidget(self.note)
        hl = QLabel("모델 좌표의 X·Y·Z 평면으로 제품을 잘라, 그 단면을 따라 두께 변화를 그립니다 (빨간 동그라미 = 가장 얇은 곳). "
                    "시험품을 같은 자리에서 잘라 마이크로미터로 잰 두께와 견주면 해석이 맞는지 바로 보입니다 "
                    "([실적 보정] 의 얇아짐 기록으로).")
        hl.setWordWrap(True)
        hl.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
        lay.addWidget(hl)
        self.sec = None
        self._update()

    def _value(self):
        k = self.axis.currentIndex()
        return float(self._lo[k] + (self._hi[k] - self._lo[k]) * self.slider.value() / 1000)

    def _update(self, *_):
        v = self._value()
        self.pos.setText(f"{self.axis.currentText()} = {v:.1f} mm")
        self.sec = fs.section(self.fa, self.axis.currentText(), v)
        if self.sec is None or len(self.sec.s) < 3:
            self.pic.setText("이 자리에는 단면이 없습니다 — 막대를 옮기세요")
            self.note.setText("")
            return
        w, h = max(self.pic.width(), 700), max(self.pic.height(), 460)
        self.pic.setPixmap(QPixmap.fromImage(fs.render_section(self.sec, w, h)))
        self.note.setText(fs.section_note(self.sec))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._update)

    def _export(self):
        if self.sec is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "단면 엑셀", f"단면_{self.sec.axis}{self.sec.pos:.0f}.xlsx", "엑셀 (*.xlsx)")
        if not path:
            return
        from openpyxl import Workbook

        from .company import stamp_workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "단면"
        ws.append([fs.section_note(self.sec)])
        ws.append(fs.SECTION_HEAD)
        for r in self.sec.rows():
            ws.append(r)
        stamp_workbook(wb)
        wb.save(path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class FlcPanel(QWidget):
    """재질별 실측 FLC 입력 (소재 업체 ISO 12004-2 성적)."""

    def __init__(self, dlg, code, flc0, parent=None):
        super().__init__(parent)
        import json

        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QPlainTextEdit

        from . import flcdata
        self.dlg, self.code = dlg, code
        self.st = QSettings("Hanil", "SheetUnfold")
        self.unit = QComboBox()
        for k, v in flcdata.UNITS.items():
            self.unit.addItem(v, k)
        self.text = QPlainTextEdit()
        try:
            d = json.loads(self.st.value(f"form/flc/{code}", "") or "{}")
        except ValueError:
            d = {}
        pts = d.get("points") or []
        self.text.setPlainText("\n".join(f"{a:.4f}\t{b:.4f}" for a, b in pts))
        self.text.setPlaceholderText("한 줄에 '부 변형률 ε2   주 변형률 ε1' (엑셀에서 두 칸 복사해 붙여 넣기)\n"
                                     "예 (진변형률):\n-0.30\t0.62\n-0.15\t0.45\n0.00\t0.30\n0.15\t0.36\n0.30\t0.44")
        self.out = QLabel()
        self.out.setWordWrap(True)
        save = QPushButton("저장하고 다시 해석")
        save.clicked.connect(self._save)
        clear = QPushButton("지우기 (Keeler 식으로)")
        clear.clicked.connect(self._clear)
        self.text.textChanged.connect(self._check)
        self.unit.currentIndexChanged.connect(self._check)
        row = QHBoxLayout()
        row.addWidget(QLabel("단위"))
        row.addWidget(self.unit)
        row.addStretch(1)
        row.addWidget(clear)
        row.addWidget(save)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>{code}</b> 의 성형 한계 곡선 (FLC) 실측값 — 지금 FLC0 {flc0:.3f} "
                             f"({'실측' if pts else 'Keeler 식'}). 소재 업체의 ISO 12004-2 (Nakajima·Marciniak) 시험 성적의 "
                             "(ε2, ε1) 점들을 넣으면 성형 해석·FLD 가 이 곡선을 씁니다 (재질마다 저장)."))
        lay.addLayout(row)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.out)
        self._check()

    def _points(self):
        from . import flcdata
        return flcdata.parse(self.text.toPlainText(), self.unit.currentData())

    def _check(self, *_):
        from . import flcdata
        pts = self._points()
        ok, why = flcdata.check(pts) if pts else (False, "")
        if not pts:
            self.out.setText("<span style='color:#888'>점이 없으면 Keeler 식 FLC 를 씁니다.</span>")
        elif ok:
            import numpy as np

            from .forming import flc_limit
            from . import forming
            old = forming.MEASURED_FLC.get(self.code)
            forming.MEASURED_FLC[self.code] = pts
            f0 = float(flc_limit(np.array([0.0]), 0.0, self.code)[0])
            if old is None:
                forming.MEASURED_FLC.pop(self.code, None)
            else:
                forming.MEASURED_FLC[self.code] = old
            self.out.setText(f"<span style='color:#2a8c3c'>{len(pts)} 점 · ε2 {pts[0][0]:.3f} ~ {pts[-1][0]:.3f} · "
                             f"FLC0 (ε2 = 0) {f0:.3f} (진변형률)</span>")
        else:
            self.out.setText(f"<span style='color:#d22828'>{why}</span>")

    def _save(self):
        from . import flcdata
        pts = self._points()
        ok, why = flcdata.check(pts)
        if not ok:
            QMessageBox.warning(self, "FLC", why)
            return
        flcdata.save(self.st, self.code, pts)
        self.dlg.done(REANALYZE)

    def _clear(self):
        from . import flcdata
        flcdata.save(self.st, self.code, [])
        self.dlg.done(REANALYZE)


class ComparePanel(QWidget):
    """재질 · 두께 바꿔 보기: 같은 제품을 후보마다 다시 펼쳐 성형 해석."""

    def __init__(self, solid, settings, fa, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem
        self.solid, self.settings, self.fa = solid, settings, fa
        self.mats = QListWidget()
        for m in bc.MATERIALS:
            it = QListWidgetItem(f"{m.code}  {m.name}")
            it.setData(Qt.UserRole, m.code)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if m.code in (settings.material, "SPCC", "SPFC590") else Qt.Unchecked)
            self.mats.addItem(it)
        self.mats.setMaximumWidth(300)
        self.thk = QLineEdit(f"{fa.thickness:g}")
        self.thk.setToolTip("쉼표로 여러 두께 (예: 0.8, 1.0, 1.2) — 3D 의 두께 가운데 면은 그대로 두고 판만 바꿈")
        run = QPushButton("비교 (후보마다 다시 펼침 — 시간이 걸림)")
        run.clicked.connect(self._run)
        self.table = QWidget()
        self.tlay = QVBoxLayout(self.table)
        self.best = QLabel()
        self.best.setWordWrap(True)
        left = QVBoxLayout()
        left.addWidget(QLabel("재질 (체크)"))
        left.addWidget(self.mats, 1)
        left.addWidget(QLabel("두께 mm"))
        left.addWidget(self.thk)
        left.addWidget(run)
        right = QVBoxLayout()
        right.addWidget(self.best)
        right.addWidget(self.table, 1)
        lay = QHBoxLayout(self)
        lw = QWidget()
        lw.setLayout(left)
        lay.addWidget(lw)
        rw = QWidget()
        rw.setLayout(right)
        lay.addWidget(rw, 1)
        if solid is None:
            run.setEnabled(False)
            self.best.setText("3D 부품이 있어야 비교할 수 있습니다 (메인 창에서 성형 해석을 여세요).")

    def candidates(self):
        codes = [self.mats.item(i).data(Qt.UserRole) for i in range(self.mats.count())
                 if self.mats.item(i).checkState() == Qt.Checked]
        ts = []
        for x in self.thk.text().replace(";", ",").split(","):
            try:
                v = float(x)
                if 0.1 <= v <= 20:
                    ts.append(v)
            except ValueError:
                pass
        ts = ts or [None]
        return [(c, None if t is None or abs(t - self.fa.thickness) < 1e-9 else t) for c in codes for t in ts]

    def _run(self):
        from PySide6.QtWidgets import QApplication, QProgressDialog
        cands = self.candidates()
        if not cands:
            return
        prog = QProgressDialog("재질·두께 비교 중…", "그만", 0, len(cands), self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        stop = []

        def step(k, n, code, t):
            prog.setValue(k)
            prog.setLabelText(f"{code} t{t or self.fa.thickness:g} 펼치는 중… ({k + 1}/{n})")
            QApplication.processEvents()
            if prog.wasCanceled():
                stop.append(1)
                raise KeyboardInterrupt
        try:
            rows = fs.compare(self.solid, self.settings, cands, progress=step)
        except KeyboardInterrupt:
            return
        finally:
            prog.close()
        self.rows = rows
        for i in reversed(range(self.tlay.count())):
            w = self.tlay.itemAt(i).widget()
            if w:
                w.deleteLater()
        show = [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]] for r in rows]
        self.tlay.addWidget(_table(fs.COMPARE_HEAD, _pct(show, (3, 4, 5, 7)),
                                   [VERDICT_COLOR.get(r[2]) for r in rows]))
        b = fs.best_row(rows)
        self.best.setText(f"<b>추천: {b[0]} t{b[1]:g}</b> — 판정 {b[2]}, 가장 큰 한계 비 {b[7]:.0%}, 가장 많이 얇아짐 {b[5]:.1%} "
                          f"(판정 → 한계 비 순)" if b else "비교 결과 없음")


class FormSimDialog(QDialog):
    def __init__(self, result, settings: bc.BendSettings, name="", parent=None, history=None, source_path="",
                 solid=None):
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
        # 설명: 어디가 · 얼마나 · 왜 · 어떻게
        self.explain = QTextBrowser()
        self.explain.setHtml(fx.html(fa))
        info.addTab(self.explain, "설명 (원인 · 대책)")
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
            fw = QWidget()
            fl = QVBoxLayout(fw)
            fl.addWidget(lab, 1)
            hl = QLabel(fx.VIEW_HELP["FLD"])
            hl.setWordWrap(True)
            hl.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
            fl.addWidget(hl)
            info.addTab(fw, "성형 한계도 (FLD)")
            info.addTab(SectionPanel(fa), "단면 (두께 그래프)")
            ls = fs.load_stroke(fa, settings.mat)
            if ls is not None:
                lw2 = QWidget()
                l2 = QVBoxLayout(lw2)
                pic = QLabel()
                pic.setPixmap(QPixmap.fromImage(fs.render_load_stroke(ls, 760, 480)))
                pic.setAlignment(Qt.AlignCenter)
                l2.addWidget(pic, 1)
                nl = QLabel(ls.note + "<br><span style='color:#666'>같은 둘레의 원통 컵으로 본 어림: 플랜지 지름 "
                            "D(h) = √(D0² − 4dh), Siebel 드로잉력 + 홀더 마찰, Siebel 누르개 면압, 크랭크 능력 곡선 "
                            "F = P·sin30°/sin α. 행정 ≥ 2 × 깊이.</span>")
                nl.setWordWrap(True)
                l2.addWidget(nl)
                info.addTab(lw2, "하중 - 행정")
            info.addTab(FlcPanel(self, fa.material, fa.flc0), "FLC 입력 (실측)")
            info.addTab(ComparePanel(solid, settings, fa), "재질·두께 비교")

        if fa.mode == "forming":
            self.view = ProductView(fa)
            box = QComboBox()
            box.addItems(fs.VIEWS)
            box.currentTextChanged.connect(self.view.set_view)
            self.view_help = QLabel(fx.VIEW_HELP[fs.VIEWS[0]])
            self.view_help.setWordWrap(True)
            self.view_help.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
            box.currentTextChanged.connect(lambda v: self.view_help.setText(fx.VIEW_HELP.get(v, "")))
            left = QWidget()
            ll = QVBoxLayout(left)
            row = QHBoxLayout()
            row.addWidget(QLabel("보기"))
            row.addWidget(box)
            row.addStretch(1)
            row.addWidget(QLabel("<span style='color:#888'>끌어서 돌리기 · 두 번 눌러 처음 방향</span>"))
            ll.addLayout(row)
            ll.addWidget(self.view, 1)
            ll.addWidget(self.view_help)
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
