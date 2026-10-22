"""한일 판금 전개 — Windows 화면.

왼쪽에 3D 형상, 오른쪽에 전개도, 아래에 절곡 목록을 보여 준다.
파일을 창에 끌어다 놓아도 열린다.
"""
from __future__ import annotations

import math
import os
import sys
import traceback

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout,
                               QWidget)

from . import __version__, dxf_export, loader
from .bend_panel import BendPanel
from .unfolder import Arc, Line, Polyline, UnfoldError, unfold

APP_NAME = "한일 판금 전개"
OPEN_FILTER = "3D 도면 (*.stp *.step *.igs *.iges *.brep);;STEP (*.stp *.step);;모든 파일 (*.*)"

BG = QColor(32, 34, 38)
CUT = QColor(235, 235, 235)
BEND = QColor(255, 200, 40)
NOTE = QColor(120, 220, 120)
EDGE3D = QColor(150, 200, 255)


# ---------------------------------------------------------------- 3D 보기

def _solid_polylines(solid, samples=24):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    seen = set()
    out = []
    exp = TopExp_Explorer(solid, TopAbs_EDGE)
    while exp.More():
        e = TopoDS.Edge(exp.Current())
        exp.Next()
        h = hash(e)
        if h in seen:
            continue
        seen.add(h)
        try:
            c = BRepAdaptor_Curve(e)
        except Exception:
            continue
        a, b = c.FirstParameter(), c.LastParameter()
        n = 1 if c.GetType() == GeomAbs_Line else samples
        pts = []
        for i in range(n + 1):
            p = c.Value(a + (b - a) * i / n)
            pts.append((p.X(), p.Y(), p.Z()))
        out.append(np.array(pts))
    return out


class ModelView(QWidget):
    """마우스로 돌려 보는 선 모델."""

    def __init__(self):
        super().__init__()
        self.lines = []
        self.center = np.zeros(3)
        self.extent = 1.0
        self.yaw, self.pitch = math.radians(-35), math.radians(25)
        self.zoom = 1.0
        self._drag = None
        self.setMinimumSize(300, 300)

    def set_solid(self, solid):
        self.lines = _solid_polylines(solid) if solid is not None else []
        if self.lines:
            allp = np.vstack(self.lines)
            lo, hi = allp.min(0), allp.max(0)
            self.center = (lo + hi) / 2
            self.extent = float(np.linalg.norm(hi - lo)) or 1.0
        self.zoom = 1.0
        self.update()

    def _rot(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        # 화면 x = 오른쪽, 화면 y = 위, z 축이 위로 오게
        view = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
        return rx @ view @ rz

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.lines:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self.rect(), Qt.AlignCenter, "3D 형상")
            return
        R = self._rot()
        s = 0.85 * min(self.width(), self.height()) / self.extent * self.zoom
        cx, cy = self.width() / 2, self.height() / 2
        p.setPen(QPen(EDGE3D, 1.2))
        for pts in self.lines:
            q = (pts - self.center) @ R.T
            path = QPainterPath(QPointF(cx + s * q[0, 0], cy - s * q[0, 1]))
            for x, y, _z in q[1:]:
                path.lineTo(cx + s * x, cy - s * y)
            p.drawPath(path)
        p.setPen(QColor(150, 150, 150))
        p.drawText(8, self.height() - 8, "끌어서 돌리기 · 휠로 확대")

    def mousePressEvent(self, ev):
        self._drag = ev.position()

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        d = ev.position() - self._drag
        self._drag = ev.position()
        self.yaw += d.x() * 0.01
        self.pitch = max(-1.55, min(1.55, self.pitch + d.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None

    def wheelEvent(self, ev):
        self.zoom *= 1.15 ** (ev.angleDelta().y() / 120)
        self.update()


# ---------------------------------------------------------------- 전개도 보기

class FlatView(QWidget):
    """전개도. 휠로 확대, 끌어서 이동, 두 번 눌러 맞춤."""

    def __init__(self):
        super().__init__()
        self.result = None
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self._drag = None
        self.setMinimumSize(300, 300)

    def set_result(self, result):
        self.result = result
        self.fit()

    def fit(self):
        if self.result is None:
            self.update()
            return
        x0, y0, x1, y1 = self.result.bbox
        w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        self.scale = 0.85 * min(self.width() / w, self.height() / h)
        self.offset = QPointF(self.width() / 2 - self.scale * (x0 + x1) / 2,
                              self.height() / 2 + self.scale * (y0 + y1) / 2)
        self.update()

    def resizeEvent(self, ev):
        self.fit()
        super().resizeEvent(ev)

    def _pt(self, p):
        return QPointF(self.offset.x() + self.scale * p[0], self.offset.y() - self.scale * p[1])

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.result
        if r is None:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "STEP 파일을 열거나 이 창에 끌어다 놓으세요")
            return

        cut = QPen(CUT, 1.4)
        bend = QPen(BEND, 1.2, Qt.DashLine)
        for e in r.entities:
            p.setPen(bend if e.layer == "BEND" else cut)
            if isinstance(e, Line):
                p.drawLine(self._pt(e.p1), self._pt(e.p2))
            elif isinstance(e, Polyline):
                path = QPainterPath(self._pt(e.points[0]))
                for q in e.points[1:]:
                    path.lineTo(self._pt(q))
                p.drawPath(path)
            elif isinstance(e, Arc):
                c = self._pt(e.center)
                rr = e.radius * self.scale
                rect = QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr)
                if e.full:
                    p.drawEllipse(rect)
                else:
                    span = (e.end_deg - e.start_deg) % 360
                    p.drawArc(rect, int(e.start_deg * 16), int(span * 16))

        p.setPen(NOTE)
        f = QFont(self.font())
        f.setPointSize(9)
        p.setFont(f)
        for b in r.bends:
            m = self._pt(((b.line[0][0] + b.line[1][0]) / 2, (b.line[0][1] + b.line[1][1]) / 2))
            p.drawText(m + QPointF(4, -4), f"B{b.number}")

        w, h = r.size
        p.setPen(QColor(200, 200, 200))
        p.drawText(8, 18, f"전개 크기  {w:.2f} × {h:.2f} mm   두께 {r.thickness:.2f}   "
                          f"{r.settings_text}")
        p.setPen(QColor(150, 150, 150))
        p.drawText(8, self.height() - 8, "휠로 확대 · 끌어서 이동 · 두 번 눌러 맞춤")

    def mousePressEvent(self, ev):
        self._drag = ev.position()

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        self.offset += ev.position() - self._drag
        self._drag = ev.position()
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None

    def mouseDoubleClickEvent(self, _):
        self.fit()

    def wheelEvent(self, ev):
        k = 1.15 ** (ev.angleDelta().y() / 120)
        pos = ev.position()
        self.offset = pos + (self.offset - pos) * k
        self.scale *= k
        self.update()


# ---------------------------------------------------------------- 주 화면

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1300, 820)
        self.setAcceptDrops(True)
        self.settings = QSettings("Hanil", "SheetUnfold")

        self.model = None
        self.result = None

        self._build_toolbar()

        self.model_view = ModelView()
        self.flat_view = FlatView()
        views = QSplitter(Qt.Horizontal)
        views.addWidget(self.model_view)
        views.addWidget(self.flat_view)
        views.setSizes([500, 800])

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(6, 0, 6, 6)
        self.bend_panel = BendPanel(self.settings)
        self.bend_panel.changed.connect(self.run_unfold)
        bl.addWidget(self.table, 5)
        bl.addWidget(self.bend_panel, 0)
        bl.addWidget(self.info, 2)

        split = QSplitter(Qt.Vertical)
        split.addWidget(views)
        split.addWidget(bottom)
        split.setSizes([540, 280])
        self.setCentralWidget(split)

        self._set_info("STEP 파일을 여세요. (솔리드웍스·NX·CATIA 에서 STEP 으로 저장)")
        self._update_actions()

    # ---- 화면 구성

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)

        self.act_open = QAction("열기", self, shortcut="Ctrl+O", triggered=self.open_dialog)
        self.act_save = QAction("DXF 저장", self, shortcut="Ctrl+S", triggered=self.save_dxf)
        self.act_batch = QAction("여러 파일 한꺼번에", self, triggered=self.batch)
        self.act_help = QAction("도움말", self, triggered=self.show_help)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addAction(self.act_batch)
        tb.addSeparator()

        tb.addWidget(QLabel(" 부품 "))
        self.solid_box = QComboBox()
        self.solid_box.setMinimumWidth(110)
        self.solid_box.currentIndexChanged.connect(lambda _: self.run_unfold())
        tb.addWidget(self.solid_box)

        tb.addWidget(QLabel("  두께 "))
        self.t_auto = QCheckBox("자동")
        self.t_auto.setChecked(True)
        self.t_auto.toggled.connect(self._thickness_mode)
        tb.addWidget(self.t_auto)
        self.t_spin = QDoubleSpinBox()
        self.t_spin.setRange(0.01, 100.0)
        self.t_spin.setDecimals(3)
        self.t_spin.setSuffix(" mm")
        self.t_spin.setEnabled(False)
        self.t_spin.editingFinished.connect(self.run_unfold)
        tb.addWidget(self.t_spin)

        self.notes_box = QCheckBox("DXF 에 절곡 글씨 넣기")
        self.notes_box.setChecked(self.settings.value("notes", "true") == "true")
        tb.addSeparator()
        tb.addWidget(self.notes_box)
        tb.addSeparator()
        tb.addAction(self.act_help)

    def _thickness_mode(self, auto):
        self.t_spin.setEnabled(not auto)
        self.run_unfold()

    def _update_actions(self):
        self.act_save.setEnabled(self.result is not None)
        self.solid_box.setEnabled(self.model is not None and len(self.model.solids) > 1)

    def _set_info(self, text, error=False):
        color = "#e06060" if error else "inherit"
        self.info.setText(f"<div style='color:{color}'>{text}</div>")

    # ---- 파일 열기

    def open_dialog(self):
        start = self.settings.value("last_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "3D 도면 열기", start, OPEN_FILTER)
        if path:
            self.open_file(path)

    def open_file(self, path):
        self.settings.setValue("last_dir", os.path.dirname(path))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            model = loader.load(path)
        except loader.UnsupportedFormat as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "STEP 으로 저장해 주세요", str(e))
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "열기 실패", str(e))
            return
        QApplication.restoreOverrideCursor()

        self.model = model
        self.setWindowTitle(f"{APP_NAME} — {os.path.basename(path)}")
        self.solid_box.blockSignals(True)
        self.solid_box.clear()
        for i in range(len(model.solids)):
            self.solid_box.addItem(f"{i + 1} / {len(model.solids)}")
        self.solid_box.blockSignals(False)
        self.t_auto.setChecked(True)
        self.run_unfold()

    def current_solid(self):
        if self.model is None:
            return None
        return self.model.solids[max(0, self.solid_box.currentIndex())]

    # ---- 전개

    def run_unfold(self):
        solid = self.current_solid()
        if solid is None:
            return
        self.model_view.set_solid(solid)
        thickness = None if self.t_auto.isChecked() else self.t_spin.value()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.result = unfold(solid, thickness=thickness, settings=self.bend_panel.settings())
        except UnfoldError as e:
            self.result = None
            self._set_info(f"전개하지 못했습니다.<br>{e}", error=True)
        except Exception as e:
            self.result = None
            traceback.print_exc()
            self._set_info(f"전개 중 오류가 났습니다.<br>{e}<br>"
                           "판금(두께 일정, 평면+원통 절곡) 형상인지 확인해 주세요.", error=True)
        finally:
            QApplication.restoreOverrideCursor()

        self.flat_view.set_result(self.result)
        self._fill_table()
        self._update_actions()
        if self.result is not None:
            r = self.result
            if self.t_auto.isChecked():
                self.t_spin.blockSignals(True)
                self.t_spin.setValue(r.thickness)
                self.t_spin.blockSignals(False)
            w, h = r.size
            lines = [
                f"<b>전개 크기</b> {w:.2f} × {h:.2f} mm",
                f"<b>두께</b> {r.thickness:.3f} mm" + (" (자동 측정)" if thickness is None else ""),
                f"<b>절곡 조건</b> {r.settings_text}",
                f"<b>절곡</b> {len(r.bends)}곳",
                "<span style='color:#999'>UP = 전개도를 보는 쪽으로 세움, "
                "DOWN = 반대쪽으로 세움</span>",
            ]
            for txt in r.rolled:
                lines.append(txt)
            for wmsg in r.warnings:
                lines.append(f"<span style='color:#e0a040'>⚠ {wmsg}</span>")
            self._set_info("<br>".join(lines))

    def _fill_table(self):
        bends = self.result.bends if self.result else []
        self.table.setRowCount(len(bends))
        for row, b in enumerate(bends):
            vals = [f"B{b.number}", "UP (위)" if b.direction == "UP" else "DOWN (아래)",
                    f"{b.angle_deg:.2f}", f"{b.model_radius:.2f}", b.radius_text, f"{b.k:.3f}",
                    _num(b.deduction), _num(b.deduction90), f"{b.allowance:.3f}",
                    f"{b.length:.2f}", b.source]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

    # ---- 저장

    def _default_dxf_name(self):
        base = os.path.splitext(self.model.path)[0]
        if len(self.model.solids) > 1:
            base += f"_{self.solid_box.currentIndex() + 1}"
        return base + "_flat.dxf"

    def save_dxf(self):
        if self.result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "DXF 저장", self._default_dxf_name(),
                                              "DXF (*.dxf)")
        if not path:
            return
        self.settings.setValue("notes", "true" if self.notes_box.isChecked() else "false")
        try:
            dxf_export.save(self.result, path,
                            part_name=os.path.splitext(os.path.basename(self.model.path))[0],
                            notes=self.notes_box.isChecked())
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        self.statusBar().showMessage(f"저장했습니다: {path}", 8000)

    def batch(self):
        start = self.settings.value("last_dir", "")
        paths, _ = QFileDialog.getOpenFileNames(self, "전개할 파일 고르기", start, OPEN_FILTER)
        if not paths:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "DXF 를 저장할 폴더", os.path.dirname(paths[0]))
        if not out_dir:
            return
        thickness = None if self.t_auto.isChecked() else self.t_spin.value()
        report = batch_convert(paths, out_dir, self.bend_panel.settings(), thickness,
                               self.notes_box.isChecked(),
                               progress=lambda: QApplication.processEvents())
        QMessageBox.information(self, "한꺼번에 전개 결과", report)

    def show_help(self):
        QMessageBox.information(self, "도움말", HELP_TEXT.format(version=__version__))

    # ---- 끌어다 놓기

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls:
            self.open_file(urls[0].toLocalFile())


TABLE_COLUMNS = ["번호", "방향", "각도(°)", "모델 R", "실제 R", "K", "연신",
                 "90° 연신", "펼친 길이", "절곡선 길이", "근거"]


def _num(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def batch_convert(paths, out_dir, settings, thickness, notes, progress=None):
    ok, failed = 0, []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            model = loader.load(path)
            for i, solid in enumerate(model.solids, 1):
                r = unfold(solid, thickness=thickness, settings=settings)
                suffix = f"_{i}" if len(model.solids) > 1 else ""
                dxf_export.save(r, os.path.join(out_dir, f"{name}{suffix}_flat.dxf"),
                                part_name=name, notes=notes)
                ok += 1
        except Exception as e:
            failed.append(f"{os.path.basename(path)}: {str(e).splitlines()[0]}")
        if progress:
            progress()
    text = f"DXF {ok}개를 만들었습니다.\n저장 위치: {out_dir}"
    if failed:
        text += "\n\n실패한 파일:\n" + "\n".join(failed)
    return text


HELP_TEXT = """\
한일 판금 전개  {version}

1. [열기] 로 STEP(.stp) 파일을 엽니다. 창에 끌어다 놓아도 됩니다.
   솔리드웍스·NX·CATIA 파일은 각 프로그램에서 STEP 으로 저장해서 여세요.
2. 아래 [절곡 조건] 에서 계산 방법을 고릅니다. 바꾸면 바로 다시 전개됩니다.
     · K 계수 직접 입력
     · 재질별 K 표 (문헌) — 재질·가공 방식(에어/바텀/코이닝)·R 로 K 결정
     · DIN 6935 공식
   [상형 R · 하형 V 로 실제 R 계산] 을 켜면 모델 R 대신 실제 절곡 R 로
   연신을 다시 계산합니다 (도면의 바깥 치수는 그대로 유지).
   [연신 표] 에서 재질별 두께 × 상형 R 연신을 보고, 현장에서 잰 값을 넣으면
   그 값이 먼저 쓰입니다.
3. 두께는 자동으로 잽니다. 다르면 [자동] 을 끄고 직접 넣으세요.
4. [DXF 저장] 을 누르면 레이저 가공용 DXF 가 만들어집니다.
     CUT  레이어 : 절단선 (외곽, 구멍)
     BEND 레이어 : 절곡선
     NOTE 레이어 : 절곡 번호·방향·각도 (가공기로 보낼 때 끄세요)

전개 길이 = 바깥 치수 합 − Σ 연신
연신 = 2·tan(θ/2)·(R + t) − θ·(R + K·t)

전개할 수 있는 형상: 두께가 일정한 판금 부품.
  · 어떤 각도의 절곡이든 (30°, 45°, 120°, 헤밍), 비스듬한 절곡선
  · 원통 절곡, 말아 만든 관, 원뿔(깔때기)·원뿔 절곡
자유곡면 성형품(엠보·루버)과 용접으로 붙인 조립품은 전개하지 않습니다.
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        w.open_file(sys.argv[1])
    sys.exit(app.exec())
