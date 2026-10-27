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
        self.spinning = False
        self._spin = QTimer(self, interval=60, timeout=self._spin_step)
        self.setToolTip("끌어서 돌리기 · 두 번 누르면 처음 방향")

    def set_view(self, view):
        self.view = view
        self._render()

    def set_spin(self, on):
        """🔄 회전: 제품을 빙글 돌림 (도는 동안 줄인 메시, 멈추면 원래 메시)."""
        self.spinning = bool(on)
        if self.spinning:
            self._spin.start()
        else:
            self._spin.stop()
            self._render()

    def _spin_step(self):
        self.az = (self.az + 3.0) % 360
        self._render(fast=True)

    def _render(self, fast=False):
        if self.width() < 10:
            return
        pix = QPixmap(self.size())
        pix.fill(QColor(255, 255, 255))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        fs.paint_product(p, QRectF(0, 0, self.width(), self.height()), self.fa, self.view, self.az, self.el,
                         fast=fast, sphere=self.spinning)
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
        self._render(fast=True)                       # 끄는 동안은 줄인 메시로 빠르게

    def mouseReleaseEvent(self, e):
        self._drag = None
        self._render(fast=self.spinning)

    def mouseDoubleClickEvent(self, e):
        self.az, self.el = -35.0, 30.0
        self._render()


def _pct(rows, cols):
    return [[f"{v:.1%}" if j in cols and not isinstance(v, str) else v for j, v in enumerate(r)] for r in rows]


REANALYZE = 2          # exec() 값: FLC 를 바꿔 다시 해석해 달라


class ProcessPanel(QWidget):
    """성형 과정 3D: ▶ 재생 (펀치가 들어가며 성형) · 🔄 회전 (돌려 보기) · 한 단계씩 · 속도 · 반복.
    재생·회전 중에는 줄인 메시로 빠르게, 멈추면 원래 메시로 다시 그린다."""

    STEP = 0.02          # 재생 한 칸 (행정 비)
    TURN = 3.0           # 회전 한 칸 (도)

    def __init__(self, fa, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QCheckBox, QSlider, QToolButton

        from . import formprocess as fp
        self.fp = fp
        self.pr = fp.build(fa)
        self.az, self.el, self._drag = -35.0, 30.0, None
        self.playing = self.rotating = False
        self._hold = 0
        self.pic = QLabel()
        self.pic.setAlignment(Qt.AlignCenter)
        self.pic.setMinimumSize(520, 400)
        self.pic.setToolTip("끌어서 돌리기 · 두 번 눌러 처음 방향")
        self.pic.installEventFilter(self)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(lambda *_: self._draw(fast=self.busy))
        self.slider.sliderReleased.connect(lambda: self._draw())

        def tb(text, tip, fn, check=False):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(check)
            b.setMinimumWidth(34)
            b.clicked.connect(fn)
            return b
        self.b_first = tb("⏮", "처음 (블랭크)", lambda: self._go(0))
        self.b_back = tb("◀", "한 단계 뒤로 (5 %)", lambda: self._go(self.slider.value() - 5))
        self.b_play = tb("▶ 재생", "펀치가 들어가며 성형되는 모습 재생 / 멈춤 (스페이스)", self.toggle_play, True)
        self.b_fwd = tb("▶|", "한 단계 앞으로 (5 %)", lambda: self._go(self.slider.value() + 5))
        self.b_last = tb("⏭", "끝 (제품)", lambda: self._go(100))
        self.b_rot = tb("🔄 회전", "제품을 빙글 돌리며 보기 / 멈춤 (재생과 같이 쓸 수 있음)", self.toggle_rotate, True)
        self.b_onset = tb("⚠ 터지는 곳으로", "처음 터지기 시작하는 행정으로 가기", self._go_crack)
        self.speed = QComboBox()
        for t_, v in (("느리게 ×0.5", 0.5), ("보통 ×1", 1.0), ("빠르게 ×2", 2.0)):
            self.speed.addItem(t_, v)
        self.speed.setCurrentIndex(1)
        self.loop = QCheckBox("반복")
        self.loop.setChecked(True)
        gif = QPushButton("GIF 저장…")
        gif.setToolTip("행정 0 → 100 % 움직이는 그림 (지금 보는 방향)")
        gif.clicked.connect(self._gif)
        self.timer = QTimer(self, interval=60, timeout=self._tick)
        self.lab = QLabel()
        self.lab.setMinimumWidth(130)
        row = QHBoxLayout()
        for w in (self.b_first, self.b_back, self.b_play, self.b_fwd, self.b_last):
            row.addWidget(w)
        row.addSpacing(8)
        row.addWidget(self.b_rot)
        row.addWidget(self.speed)
        row.addWidget(self.loop)
        row.addWidget(self.b_onset)
        row.addStretch(1)
        row.addWidget(gif)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("행정"))
        row2.addWidget(self.slider, 1)
        row2.addWidget(self.lab)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addLayout(row2)
        lay.addWidget(self.pic, 1)
        lay.addWidget(self.info)
        note = QLabel("원스텝 해석은 블랭크 (처음) 와 제품 (끝) 만 알므로, 가운데는 비례 변형 (행정 s 에서 변형 = s × 끝 변형) 과 "
                      "펀치 깊이에 따라 블랭크를 제품으로 이어 붙인 모양으로 그립니다 — 실제 금형 접촉 순서·다단 공정은 아님. "
                      "빨간 동그라미 = 처음 FLC 에 닿는 곳 (터지기 시작), 보라 = 처음 5 % 넘게 두꺼워지는 곳 (주름 시작).")
        note.setWordWrap(True)
        note.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
        lay.addWidget(note)
        if self.pr is None:
            self.info.setText("성형 과정을 그릴 수 없습니다 (성형품 메시 없음).")
            for w in (self.b_first, self.b_back, self.b_play, self.b_fwd, self.b_last, self.b_rot, self.b_onset):
                w.setEnabled(False)
            return
        self.b_onset.setEnabled(any(o.kind == "crack" for o in self.pr.onsets))
        self.info.setText("<br>".join(("⚠ " if "시작" in t else "✔ ") + t for t in fp.summary(self.pr)))
        self._draw()

    @property
    def busy(self):
        return self.playing or self.rotating

    def _draw(self, fast=False):
        if self.pr is None:
            return
        s = self.slider.value() / 100
        self.lab.setText(f"{s:.0%} · 깊이 {s * self.pr.depth:.0f} mm")
        w, h = max(self.pic.width(), 640), max(self.pic.height(), 480)
        self.pic.setPixmap(QPixmap.fromImage(self.fp.render_stage(self.pr, s, w, h, self.az, self.el,
                                                                  fast=fast, sphere=self.rotating)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, lambda: self._draw(fast=self.busy))

    def _go(self, v):
        self.slider.setValue(max(0, min(100, int(v))))
        if not self.busy:
            self._draw()

    def _go_crack(self):
        o = next((o for o in self.pr.onsets if o.kind == "crack"), None)
        if o is not None:
            self._go(round(o.s * 100))

    def _sync(self):
        self.b_play.setChecked(self.playing)
        self.b_play.setText("❚❚ 멈춤" if self.playing else "▶ 재생")
        self.b_rot.setChecked(self.rotating)
        if self.busy and not self.timer.isActive():
            self.timer.start()
        elif not self.busy and self.timer.isActive():
            self.timer.stop()
            self._draw()                           # 멈추면 원래 메시로

    def toggle_play(self):
        self.playing = not self.playing
        if self.playing and self.slider.value() >= 100:
            self.slider.setValue(0)
        self._sync()

    def toggle_rotate(self):
        self.rotating = not self.rotating
        self._sync()
        if not self.busy:
            self._draw()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space:
            self.toggle_play()
            return
        if e.key() == Qt.Key_Right:
            self._go(self.slider.value() + 5)
            return
        if e.key() == Qt.Key_Left:
            self._go(self.slider.value() - 5)
            return
        super().keyPressEvent(e)

    def _tick(self):
        k = float(self.speed.currentData() or 1.0)
        if self.rotating:
            self.az = (self.az + self.TURN * k) % 360
        if self.playing:
            if self._hold > 0:                     # 끝에서 잠깐 멈췄다가 반복
                self._hold -= 1
                if self._hold == 0:
                    self.slider.blockSignals(True)
                    self.slider.setValue(0)
                    self.slider.blockSignals(False)
            else:
                v = self.slider.value() + max(1, round(self.STEP * 100 * k))
                if v >= 100:
                    v = 100
                    if self.loop.isChecked():
                        self._hold = 12
                    else:
                        self.playing = False
                self.slider.blockSignals(True)
                self.slider.setValue(v)
                self.slider.blockSignals(False)
        self._draw(fast=True)
        if not self.busy:
            self._sync()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if obj is self.pic and self.pr is not None:
            if ev.type() == QEvent.MouseButtonPress:
                self._drag = (ev.position().x(), ev.position().y(), self.az, self.el)
            elif ev.type() == QEvent.MouseMove and self._drag:
                x0, y0, az, el = self._drag
                self.az = az + (ev.position().x() - x0) * 0.5
                self.el = max(-89.0, min(89.0, el + (ev.position().y() - y0) * 0.5))
                self._draw(fast=True)
            elif ev.type() == QEvent.MouseButtonRelease:
                self._drag = None
                if not self.busy:
                    self._draw()
            elif ev.type() == QEvent.MouseButtonDblClick:
                self.az, self.el = -35.0, 30.0
                self._draw(fast=self.busy)
        return super().eventFilter(obj, ev)

    def _gif(self):
        if self.pr is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "성형 과정 GIF", "성형과정.gif", "GIF (*.gif)")
        if not path:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.fp.save_gif(self.pr, path, 30, 720, 540, self.az, self.el)
        finally:
            QApplication.restoreOverrideCursor()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


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


class OpsPanel(QWidget):
    """공정별 해석: 다이 페이스 (바인더·어덴덤) 위 원스텝 OP10 → OP20 트림·피어싱 → OP30 플랜지 → OP40 리스트라이크.
    다이 페이스를 푸는 데 몇 초~수십 초 걸려 단추를 눌러 시작한다."""

    def __init__(self, result, settings, fa, parent=None):
        super().__init__(parent)
        self.result, self.settings, self.fa = result, settings, fa
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.run_btn = QPushButton("▶ 다이 페이스 · 공정별 해석")
        self.run_btn.clicked.connect(self.run)
        top.addWidget(self.run_btn)
        self.view_box = QComboBox()
        self.view_box.addItems(fs.VIEWS)
        self.view_box.setEnabled(False)
        top.addWidget(QLabel("다이 페이스 보기"))
        top.addWidget(self.view_box)
        top.addStretch(1)
        lay.addLayout(top)
        self.help = QLabel("트림선 바깥에 어덴덤 벽 (빼기 10°) · 다이 R · 바인더 (폭 25 mm, 트림선에 맞춘 평면) 를 붙여 그 판 전체로 "
                           "원스텝을 풀고 (OP10), 트림·피어싱 전단력 (OP20), 트림 뒤 꺾는 플랜지의 늘림·줄임·스프링백 (OP30), "
                           "리스트라이크·캠 (OP40) 을 공정마다 봅니다. 아래로 꺾는 플랜지는 떼어 낸 드로잉 모양에 다이 페이스를 붙입니다.")
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color:#444; background:#f4f6fa; padding:4px")
        lay.addWidget(self.help)
        self.body = QVBoxLayout()
        lay.addLayout(self.body, 1)
        self.ops = None

    def run(self):
        from PySide6.QtWidgets import QApplication

        from . import formops
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.ops = formops.build(self.fa, self.result, self.settings)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "공정별 해석 실패", str(e))
            return
        QApplication.restoreOverrideCursor()
        self.fa.ops = self.ops
        while self.body.count():
            w = self.body.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        rows = [[r[0], r[1], r[2], f"{r[3]:,.0f}", f"{r[4]:,.1f}", r[5]] for r in self.ops.rows()]
        self.body.addWidget(_table(formops.HEAD, rows, [VERDICT_COLOR[o.verdict] for o in self.ops.ops]))
        if self.ops.fa_die is not None:
            v = ProductView(self.ops.fa_die)
            self.view_box.setEnabled(True)
            self.view_box.currentTextChanged.connect(v.set_view)
            self.body.addWidget(v, 1)
        if self.ops.notes:
            n = QLabel("<br>".join("• " + x for x in self.ops.notes))
            n.setWordWrap(True)
            self.body.addWidget(n)
        self.run_btn.setText("↻ 다시 해석")


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
            info.insertTab(1, ProcessPanel(fa), "성형 과정 (3D)")
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
            self.ops_panel = OpsPanel(result, settings, fa)
            info.insertTab(2, self.ops_panel, "공정별 (다이 페이스)")

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
            from PySide6.QtWidgets import QToolButton
            spin = QToolButton()
            spin.setText("🔄 회전")
            spin.setCheckable(True)
            spin.setToolTip("제품을 빙글 돌리며 보기 / 멈춤")
            spin.toggled.connect(self.view.set_spin)
            row.addWidget(spin)
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
