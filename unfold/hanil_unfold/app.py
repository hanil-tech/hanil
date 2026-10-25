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
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout,
                               QWidget, QListWidget, QTabWidget, QPushButton)

from . import __version__, version_text, dxf_export, loader
from . import report
from .bend_panel import BendPanel
from .history import History
from .history_dialog import HistoryDialog
from . import assembly_calc
from .gl_view import GLView, gl_available, mesh_parts, mesh_parts_cached
from . import dims as dimsmod
from .drawing import (DARK, FlatTransform, assembly_polylines, paint_assembly, paint_dimensions,
                      paint_flat, paint_legend, paint_summary, solid_polylines, view_rotation)
from .unfolder import AUTO, MODE_NAMES, UnfoldError, unfold

APP_NAME = "한일 판금 전개"
OPEN_FILTER = "3D 도면 (*.stp *.step *.igs *.iges *.brep);;STEP (*.stp *.step);;모든 파일 (*.*)"

BG = QColor(32, 34, 38)
CUT = QColor(235, 235, 235)
BEND = QColor(255, 200, 40)
NOTE = QColor(120, 220, 120)
EDGE3D = QColor(150, 200, 255)


# ---------------------------------------------------------------- 3D 보기

class ModelView(QWidget):
    """마우스로 돌려 보는 선 모델."""

    enlargeRequested = Signal()

    def mouseDoubleClickEvent(self, _):
        self.enlargeRequested.emit()

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
        self.lines = solid_polylines(solid) if solid is not None else []
        if self.lines:
            allp = np.vstack(self.lines)
            lo, hi = allp.min(0), allp.max(0)
            self.center = (lo + hi) / 2
            self.extent = float(np.linalg.norm(hi - lo)) or 1.0
        self.zoom = 1.0
        self.update()

    def _rot(self):
        return view_rotation(self.yaw, self.pitch)

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

class AssemblyView(QWidget):
    """조립품 전체. 부품마다 번호 풍선이 붙고, 풍선(또는 부품 목록)을 누르면 그 부품을 고른다."""

    partClicked = Signal(int)
    enlargeRequested = Signal()

    def mouseDoubleClickEvent(self, _):
        self.enlargeRequested.emit()

    def __init__(self):
        super().__init__()
        self.parts = []
        self.highlight = None
        self.yaw, self.pitch = math.radians(-35), math.radians(25)
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self._drag = None
        self._moved = False
        self._hits = []
        self.show_numbers = True
        self.setMinimumSize(300, 300)

    def set_parts(self, parts):
        self.parts = parts
        self.zoom, self.pan = 1.0, QPointF(0, 0)
        self.update()

    def set_highlight(self, idx):
        self.highlight = idx
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), DARK.bg)
        if not self.parts:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self.rect(), Qt.AlignCenter, "조립품 전체")
            return
        self._hits = paint_assembly(p, self.parts, QRectF(self.rect()), DARK, self.highlight,
                                    self.yaw, self.pitch, self.zoom, (self.pan.x(), self.pan.y()),
                                    balloons=self.show_numbers)
        p.setPen(QColor(150, 150, 150))
        p.setFont(QFont(self.font()))
        p.drawText(8, self.height() - 8, "번호를 누르면 그 부품 · 왼쪽 끌기 돌리기 · 오른쪽 끌기 이동 · 휠 확대")

    def mousePressEvent(self, ev):
        self._drag = (ev.position(), ev.button())
        self._moved = False

    def mouseMoveEvent(self, ev):
        if self._drag is None:
            return
        d = ev.position() - self._drag[0]
        if abs(d.x()) + abs(d.y()) > 2:
            self._moved = True
        self._drag = (ev.position(), self._drag[1])
        if self._drag[1] == Qt.RightButton or ev.modifiers() & Qt.ShiftModifier:
            self.pan += d
        else:
            self.yaw += d.x() * 0.01
            self.pitch = max(-1.55, min(1.55, self.pitch + d.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag is not None and not self._moved:
            pos = ev.position()
            best = None
            for idx, c, r in self._hits:
                d = math.hypot(pos.x() - c.x(), pos.y() - c.y())
                if d <= r * 1.3 and (best is None or d < best[0]):
                    best = (d, idx)
            if best:
                self.partClicked.emit(best[1])
        self._drag = None

    def wheelEvent(self, ev):
        self.zoom *= 1.15 ** (ev.angleDelta().y() / 120)
        self.update()


class FlatView(QWidget):
    """전개도. 휠로 확대, 끌어서 이동, 두 번 눌러 맞춤.

    오른쪽 단추 메뉴: 색칠 켜기/끄기, 색 바꾸기, 이 부품 제외 (전체 계산·철판 배치 합계에서 뺀다)."""

    excludeToggled = Signal(bool)
    SNAP_PX = 12            # 이 픽셀 안에 끝점·원 중심이 있으면 거기에 붙는다
    exportRequested = Signal()
    fldRequested = Signal()
    FILL = QColor(70, 130, 200, 110)

    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings
        self.fill_on = (settings.value("flat_fill", "true") == "true") if settings else True
        c = QColor(settings.value("flat_fill_color", "")) if settings else QColor()
        self.fill_color = c if c.isValid() else QColor(self.FILL)
        self.excluded = False
        self._fill_cache = None
        # 보이기 설정: 연속 치수, 구멍 번호·지름, 절곡 번호, 요약 상자
        self.show = {}
        for key in ("chain", "holes", "bends", "summary"):
            self.show[key] = (settings.value(f"flat_show_{key}", "true") == "true") if settings else True
        self.holes_auto_hidden = False
        # 치수 찍기
        self.measure = False
        self.user_dims = []          # [(p1, p2)] 전개도 좌표 (mm)
        self._m_first = None
        self._hover = None           # (점, 붙었나)
        self._snaps = None
        self._press = None
        self._shift = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.result = None
        self.dims = None
        self.show_dims = True
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self._drag = None
        self.setMinimumSize(300, 300)
        self._build_buttons()

    MANY_HOLES = 60       # 구멍이 이보다 많으면 번호·지름은 처음에 숨긴다 (글씨가 겹쳐 안 보이므로)
    TOGGLES = [("chain", "치수", "절곡선까지 연속 치수 (끄면 전체 크기만)"),
               ("holes", "구멍", "구멍 번호·지름·좌표 글씨"),
               ("bends", "절곡", "절곡 번호 B1, B2 …"),
               ("summary", "요약", "두께·크기·면적·무게 상자")]

    def _build_buttons(self):
        from PySide6.QtWidgets import QToolButton
        self.buttons = {}
        mb = QToolButton(self)
        mb.setText("치수 찍기")
        mb.setToolTip("두 점을 눌러 거리 치수 (끝점·구멍 중심에 붙음). Shift: 수평/수직, Esc: 취소, "
                      "Ctrl+Z: 마지막 지우기, 오른쪽 단추: 모두 지우기")
        mb.setCheckable(True)
        mb.setStyleSheet("QToolButton{color:#ddd;background:rgba(40,44,52,210);border:1px solid #556;"
                         "border-radius:3px;padding:1px 6px;} QToolButton:checked{background:#c0408f;color:white;}")
        mb.toggled.connect(self.set_measure)
        self.measure_btn = mb
        style = ("QToolButton{color:#ddd;background:rgba(40,44,52,210);border:1px solid #556;"
                 "border-radius:3px;padding:1px 6px;} QToolButton:hover{background:#7a2050;}")
        self.undo_btn = QToolButton(self)
        self.undo_btn.setText("지우기")
        self.undo_btn.setToolTip("마지막에 찍은 치수 지우기 (Ctrl+Z). 치수 위에 커서를 두고 Delete 를 누르면 그 치수만")
        self.undo_btn.setStyleSheet(style)
        self.undo_btn.clicked.connect(self.undo_dim)
        self.clear_btn = QToolButton(self)
        self.clear_btn.setText("모두 지우기")
        self.clear_btn.setToolTip("찍은 치수 모두 지우기")
        self.clear_btn.setStyleSheet(style)
        self.clear_btn.clicked.connect(self.clear_dims)
        self._hot_dim = None         # 커서 아래 치수 번호
        for key, label, tip in self.TOGGLES:
            b = QToolButton(self)
            b.setText(label)
            b.setToolTip(f"{tip} 보이기 / 숨기기")
            b.setCheckable(True)
            b.setChecked(self.show[key])
            b.setStyleSheet("QToolButton{color:#ddd;background:rgba(40,44,52,210);border:1px solid #556;"
                            "border-radius:3px;padding:1px 6px;} QToolButton:checked{background:#2f6fb0;color:white;}")
            b.toggled.connect(lambda on, k=key: self.set_show(k, on))
            self.buttons[key] = b
        self._place_buttons()

    def _place_buttons(self):
        x = self.width() - 6
        for key, _, _ in reversed(self.TOGGLES):
            b = self.buttons[key]
            b.adjustSize()
            x -= b.width()
            b.move(x, 6)
            x -= 3
        self.measure_btn.adjustSize()
        x -= 8 + self.measure_btn.width()
        self.measure_btn.move(x, 6)
        has = bool(self.user_dims)
        for b in (self.undo_btn, self.clear_btn):
            b.setVisible(has)
        # 지우기 단추는 [치수 찍기] 바로 밑에
        self.undo_btn.adjustSize()
        self.clear_btn.adjustSize()
        self.undo_btn.move(x, 6 + self.measure_btn.height() + 3)
        self.clear_btn.move(x + self.undo_btn.width() + 3, 6 + self.measure_btn.height() + 3)

    # ---- 치수 찍기

    def set_measure(self, on):
        self.measure = on
        self._m_first = None
        self._hover = None
        self.setMouseTracking(on or bool(self.user_dims))
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)
        if self.measure_btn.isChecked() != on:
            self.measure_btn.setChecked(on)
        if on:
            self.setFocus()
        self.update()

    def _to_flat(self, pos):
        return ((pos.x() - self.offset.x()) / self.scale, (self.offset.y() - pos.y()) / self.scale)

    def _snap(self, pos):
        """화면 점 → (전개도 점, 붙었나)."""
        if self._snaps is None and self.result is not None:
            from .drawing import snap_points
            self._snaps = snap_points(self.result)
        raw = self._to_flat(pos)
        if self._snaps is not None and len(self._snaps):
            d = np.hypot(self._snaps[:, 0] - raw[0], self._snaps[:, 1] - raw[1]) * self.scale
            k = int(np.argmin(d))
            if d[k] <= self.SNAP_PX:
                return (float(self._snaps[k, 0]), float(self._snaps[k, 1])), True
        return raw, False

    def _constrained(self, a, b, shift):
        if not shift:
            return b
        return (b[0], a[1]) if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else (a[0], b[1])

    def _measure_click(self, pos, shift):
        pt, _ = self._snap(pos)
        if self._m_first is None:
            self._m_first = pt
        else:
            b = self._constrained(self._m_first, pt, shift)
            if math.dist(self._m_first, b) > 1e-6:
                self.user_dims.append((self._m_first, b))
                self.setMouseTracking(True)       # 치수 위에 커서를 두면 강조 (Delete 로 지우기)
            self._m_first = None
            self._place_buttons()
        self.update()

    def undo_dim(self):
        if self._m_first is not None:
            self._m_first = None
        elif self.user_dims:
            self.user_dims.pop()
        self._dims_changed()

    def clear_dims(self):
        self.user_dims.clear()
        self._m_first = None
        self._dims_changed()

    def delete_dim(self, k):
        if 0 <= k < len(self.user_dims):
            del self.user_dims[k]
        self._dims_changed()

    def _dims_changed(self):
        self._hot_dim = None
        self._place_buttons()
        self.update()

    def _dim_at(self, pos, tol=7):
        """커서 아래 찍은 치수 번호 (선에서 tol 픽셀 안이거나 길이 글씨 위), 없으면 None."""
        best, bd = None, tol
        for k, (a, b) in enumerate(self.user_dims):
            A, B = self._pt(a), self._pt(b)
            ax, ay, bx, by = A.x(), A.y(), B.x(), B.y()
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-9 else max(0.0, min(1.0, ((pos.x() - ax) * dx + (pos.y() - ay) * dy) / L2))
            d = math.hypot(pos.x() - (ax + t * dx), pos.y() - (ay + t * dy))
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if abs(pos.x() - mx) < 60 and my - 24 < pos.y() < my:
                d = min(d, 2.0)                       # 길이 글씨 위
            if d < bd:
                best, bd = k, d
        return best

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            if self._m_first is not None:
                self._m_first = None
                self.update()
            elif self.measure:
                self.set_measure(False)
        elif ev.key() == Qt.Key_Z and ev.modifiers() & Qt.ControlModifier:
            self.undo_dim()
        elif ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self._hot_dim is not None:
            self.delete_dim(self._hot_dim)
        else:
            super().keyPressEvent(ev)

    def set_show(self, key, on, remember=True):
        self.show[key] = on
        if key == "holes":
            self.holes_auto_hidden = False
        if remember and self.settings:
            self.settings.setValue(f"flat_show_{key}", "true" if on else "false")
        b = self.buttons.get(key)
        if b is not None and b.isChecked() != on:
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)
        self.update()

    def set_result(self, result, dims=None, excluded=False):
        self.result = result
        self.dims = dims
        self.excluded = excluded
        self._fill_cache = None
        self._snaps = None
        self.user_dims = []
        self._m_first = None
        self._hot_dim = None
        self._place_buttons()
        # 구멍이 아주 많으면 번호 글씨는 처음에 숨긴다 (저장한 설정은 그대로)
        many = dims is not None and len(dims.holes) > self.MANY_HOLES
        want = self.settings.value("flat_show_holes", "true") == "true" if self.settings else True
        self.set_show("holes", want and not many, remember=False)
        self.holes_auto_hidden = want and many
        self.fit()

    def set_excluded(self, on):
        self.excluded = on
        self.update()

    def _fill_shape(self):
        """색칠할 모양: 닫힌 외곽이면 (외곽 − 구멍) 경로, 끊긴 외곽이면 격자 그림."""
        if self._fill_cache is not None:
            return self._fill_cache
        from . import metrics as mt
        from .nesting import NestPart, _rasterize
        r = self.result
        lps = sorted(mt.loops(r.entities), key=mt.polygon_area, reverse=True)
        if lps and mt._encloses(lps[0], r.bbox):
            self._fill_cache = ("path", lps)
        else:
            try:
                part = NestPart.from_result("", r)
                x0, y0, x1, y1 = r.bbox
                res = max(x1 - x0, y1 - y0) / 700 or 1.0
                m, origin = _rasterize(part, 0, res, conservative=False)
                self._fill_cache = ("mask", (m, origin, res))
            except Exception:
                self._fill_cache = ("none", None)
        return self._fill_cache

    def _paint_fill(self, p, tf):
        kind, data = self._fill_shape()
        col = QColor(120, 120, 120, 90) if self.excluded else self.fill_color
        if kind == "path":
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            from PySide6.QtGui import QPolygonF
            for lp in data:
                path.addPolygon(QPolygonF([tf.pt(q) for q in lp]))
                path.closeSubpath()
            p.fillPath(path, col)
        elif kind == "mask":
            from PySide6.QtGui import QImage
            m, (ox, oy), res = data
            h, w = m.shape
            rgba = np.zeros((h, w, 4), np.uint8)
            rgba[m] = (col.red(), col.green(), col.blue(), col.alpha())
            rgba = np.ascontiguousarray(rgba[::-1])          # 그림은 위가 +y
            img = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            tl = tf.pt((ox, oy + h * res))
            p.drawImage(QRectF(tl.x(), tl.y(), w * res * tf.scale, h * res * tf.scale), img)

    def contextMenuEvent(self, ev):
        if self.result is None:
            return
        from PySide6.QtWidgets import QColorDialog, QMenu
        m = QMenu(self)
        hot = self._dim_at(QPointF(ev.pos()))
        if hot is not None:
            from .drawing import dim_text
            a_, b_ = self.user_dims[hot]
            m.addAction(f"이 치수 지우기  ({dim_text(a_, b_).split('  ')[0]})", lambda: self.delete_dim(hot))
            m.addSeparator()
        a = m.addAction("색칠")
        a.setCheckable(True)
        a.setChecked(self.fill_on)
        a.toggled.connect(self._set_fill)

        def pick():
            c = QColorDialog.getColor(self.fill_color, self, "전개도 색",
                                      QColorDialog.ShowAlphaChannel)
            if c.isValid():
                self.fill_color = c
                if self.settings:
                    self.settings.setValue("flat_fill_color", c.name(QColor.HexArgb))
                self._set_fill(True)

        m.addAction("색 바꾸기…", pick)
        m.addSeparator()
        for key, label, tip in self.TOGGLES:
            t = m.addAction(f"{tip}")
            t.setCheckable(True)
            t.setChecked(self.show[key])
            t.toggled.connect(lambda on, k=key: self.set_show(k, on))
        m.addSeparator()
        md = m.addAction("치수 찍기")
        md.setCheckable(True)
        md.setChecked(self.measure)
        md.toggled.connect(self.set_measure)
        u = m.addAction("마지막 찍은 치수 지우기  (Ctrl+Z)", self.undo_dim)
        u.setEnabled(bool(self.user_dims))
        c = m.addAction(f"찍은 치수 모두 지우기 ({len(self.user_dims)}개)", self.clear_dims)
        c.setEnabled(bool(self.user_dims))
        m.addSeparator()
        if self.result is not None and self.result.forming is not None:
            m.addAction("성형 한계도 (FLD) 보기…", self.fldRequested.emit)
        m.addAction("이 부품만 STEP 으로 저장…", self.exportRequested.emit)
        x = m.addAction("이 부품 제외 (전체 계산·철판 배치에서 뺌)")
        x.setCheckable(True)
        x.setChecked(self.excluded)
        x.toggled.connect(self.excludeToggled.emit)
        m.addSeparator()
        m.addAction("맞춤", self.fit)
        m.exec(ev.globalPos())

    def _set_fill(self, on):
        self.fill_on = on
        if self.settings:
            self.settings.setValue("flat_fill", "true" if on else "false")
        self.update()

    def set_show_dims(self, on):
        self.show_dims = on
        self.fit()

    def fit(self):
        if self.result is None:
            self.update()
            return
        x0, y0, x1, y1 = self.result.bbox
        w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        # 치수선과 요약 상자 자리를 남긴다
        room = 0.70 if self.show_dims else 0.85
        self.scale = room * min(self.width() / w, self.height() / h)
        self.offset = QPointF(self.width() / 2 - self.scale * (x0 + x1) / 2,
                              self.height() / 2 + self.scale * (y0 + y1) / 2)
        self.update()

    def resizeEvent(self, ev):
        self.fit()
        self._place_buttons()
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

        tf = FlatTransform(self.scale, self.offset.x(), self.offset.y())
        f = QFont(self.font())
        f.setPointSize(9)
        p.setFont(f)
        if self.fill_on and r.forming is None:
            self._paint_fill(p, tf)
        paint_flat(p, r, tf, DARK, labels=self.show["bends"])
        if self.excluded:
            fx = QFont(self.font())
            fx.setPointSize(16)
            fx.setBold(True)
            p.setFont(fx)
            p.setPen(QColor(230, 120, 60))
            p.drawText(self.rect().adjusted(0, 0, 0, -30), Qt.AlignHCenter | Qt.AlignBottom,
                       "제외한 부품 (전체 계산·철판 배치에서 빠짐)")
            p.setFont(f)
        if r.forming is not None:
            paint_legend(p, QRectF(self.width() - 280, self.height() - 50, 260, 12), DARK)

        p.setPen(QColor(150, 150, 150))
        p.drawText(8, 18, r.settings_text)
        if self.show_dims and self.dims is not None:
            paint_dimensions(p, r, tf, DARK, self.dims, chains_on=self.show["chain"],
                             holes_on=self.show["holes"])
        if self.show["summary"] and self.dims is not None:
            paint_summary(p, self.dims.summary_lines(), 8, 26, DARK)
        if self.user_dims or self.measure:
            from .drawing import paint_user_dims
            prev = None
            if self.measure and self._m_first is not None and self._hover is not None:
                prev = (self._m_first, self._constrained(self._m_first, self._hover[0], self._shift))
            paint_user_dims(p, self.user_dims, tf, DARK, preview=prev, hot=self._hot_dim)
            if self.measure and self._hover is not None:
                q = tf.pt(self._hover[0])
                p.setPen(QPen(QColor(255, 230, 0) if self._hover[1] else QColor(255, 120, 200), 1.5))
                p.setBrush(Qt.NoBrush)
                if self._hover[1]:
                    p.drawRect(QRectF(q.x() - 5, q.y() - 5, 10, 10))
                else:
                    p.drawLine(QPointF(q.x() - 6, q.y()), QPointF(q.x() + 6, q.y()))
                    p.drawLine(QPointF(q.x(), q.y() - 6), QPointF(q.x(), q.y() + 6))
            if self.measure:
                p.setPen(QColor(255, 150, 210))
                p.drawText(self.rect().adjusted(0, 0, -8, -24), Qt.AlignRight | Qt.AlignBottom,
                           "치수 찍기: 두 점을 누르세요 (노란 네모 = 끝점·중심에 붙음) · Shift 수평/수직 · "
                           "Esc 취소 · Ctrl+Z 지우기")
        if self.holes_auto_hidden and self.dims is not None:
            p.setPen(QColor(220, 170, 80))
            p.drawText(self.rect().adjusted(0, 34, -8, 0), Qt.AlignRight | Qt.AlignTop,
                       f"구멍 {len(self.dims.holes)}개 — 번호·지름은 [구멍] 을 눌러 보기")
        p.setPen(QColor(150, 150, 150))
        p.drawText(8, self.height() - 8, "휠로 확대 · 끌어서 이동 · 두 번 눌러 맞춤 · 오른쪽 단추: 색칠 · 제외")

    def mousePressEvent(self, ev):
        self._drag = ev.position() if ev.button() == Qt.LeftButton else None
        self._press = ev.position() if ev.button() == Qt.LeftButton else None

    def mouseMoveEvent(self, ev):
        self._shift = bool(ev.modifiers() & Qt.ShiftModifier)
        if self.user_dims and self._drag is None:
            hot = self._dim_at(ev.position())
            if hot != self._hot_dim:
                self._hot_dim = hot
                self.update()
        if self.measure and self.result is not None:
            self._hover = self._snap(ev.position())
            self.update()
        if self._drag is None:
            return
        self.offset += ev.position() - self._drag
        self._drag = ev.position()
        self.update()

    def mouseReleaseEvent(self, ev):
        clicked = self._press is not None and \
            (ev.position() - self._press).manhattanLength() < 4
        self._drag = None
        self._press = None
        if clicked and self.measure and self.result is not None:
            self._measure_click(ev.position(), bool(ev.modifiers() & Qt.ShiftModifier))

    def mouseDoubleClickEvent(self, _):
        if not self.measure:          # 치수 찍는 중에는 두 번 누름이 점 찍기와 겹치므로 맞춤 안 함
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
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.resize(1300, 820)
        self.setAcceptDrops(True)
        self.settings = QSettings("Hanil", "SheetUnfold")

        self.model = None
        self.result = None
        self.record_id = None
        self.history = History(self.settings.value("history_dir") or None)

        self._build_toolbar()

        # 그래픽 카드(OpenGL)를 쓸 수 있으면 3D 를 그래픽 카드로 그린다 (큰 조립품도 부드럽게).
        self.use_gl = self.settings.value("use_gl", "true") == "true" and gl_available()
        if self.use_gl:
            self.model_view = GLView(balloons=False, hint="끌어서 돌리기 · 오른쪽 끌기 이동 · 휠로 확대 · 두 번 눌러 크게 보기")
            self.assembly_view = GLView(
                hint="부품·번호를 누르면 그 부품 · 오른쪽 단추: 숨기기 메뉴 · 왼쪽 끌기 돌리기 · "
                     "오른쪽 끌기 이동 · 휠 확대 · 두 번 눌러 크게 보기")
        else:
            self.model_view = ModelView()
            self.assembly_view = AssemblyView()
        self.assembly_view.partClicked.connect(self.select_part)
        self.part_list = QListWidget()
        self.part_list.currentRowChanged.connect(
            lambda row: row >= 0 and row != self.solid_box.currentIndex() and self.select_part(row))
        self.part_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.part_list.customContextMenuRequested.connect(self._part_menu)
        self.part_list.setToolTip("오른쪽 단추: 숨기기 · 보이기 · 이것만 보기 · 제외")
        if hasattr(self.assembly_view, "hide_part"):
            self.assembly_view.hiddenChanged.connect(self._mark_hidden)
            self.assembly_view.exportRequested.connect(self.export_part_step)
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.part_list, 1)
        row = QHBoxLayout()
        self.calc_all_btn = QPushButton("전체 계산")
        self.calc_all_btn.setToolTip("모든 부품을 전개해 두께·면적·무게를 구하고 두께별로 합칩니다")
        self.calc_all_btn.clicked.connect(self.calc_all)
        self.calc_xlsx_btn = QPushButton("엑셀로")
        self.calc_xlsx_btn.clicked.connect(self.save_assembly_xlsx)
        self.calc_xlsx_btn.setEnabled(False)
        row.addWidget(self.calc_all_btn)
        row.addWidget(self.calc_xlsx_btn)
        sl.addLayout(row)
        self.all_balloons_box = QCheckBox("번호 모두 보기")
        self.all_balloons_box.setToolTip("끄면 고른 부품 번호만 보입니다 (부품이 많을 때)")
        self.all_balloons_box.toggled.connect(self._balloons_toggled)
        self.hide_balloons_box = QCheckBox("번호 숨기기")
        self.hide_balloons_box.setToolTip("조립품 그림의 번호 풍선을 모두 숨깁니다")
        self.hide_balloons_box.toggled.connect(self._hide_balloons)
        nb = QHBoxLayout()
        nb.addWidget(self.all_balloons_box)
        nb.addWidget(self.hide_balloons_box)
        sl.addLayout(nb)
        if hasattr(self.assembly_view, "btn_num"):     # 3D 화면 위 [번호] 단추와 같이 움직임
            self.assembly_view.btn_num.toggled.connect(lambda on: self.hide_balloons_box.setChecked(not on))
        self.assy_summary = QLabel("[전체 계산] 을 누르면 모든 부품의\n두께·면적·무게 합계가 나옵니다.")
        self.assy_summary.setWordWrap(True)
        self.assy_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sl.addWidget(self.assy_summary)
        side.setMaximumWidth(320)
        self.assy_parts_result = None
        assy = QSplitter(Qt.Horizontal)
        assy.addWidget(self.assembly_view)
        assy.addWidget(side)
        assy.setSizes([520, 260])
        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(self.model_view, "부품 3D")
        self.left_tabs.addTab(assy, "조립품 전체 (번호)")
        self.flat_view = FlatView(self.settings)
        self.flat_view.excludeToggled.connect(self._exclude_current)
        self.flat_view.exportRequested.connect(lambda: self.export_part_step())
        self.flat_view.fldRequested.connect(self.show_fld)
        self.excluded = set()          # 전체 계산·철판 배치에서 뺄 부품 번호 (0부터)
        views = QSplitter(Qt.Horizontal)
        self.views_split = views
        self._big = None              # 3D 크게 보기 창
        for v in (self.model_view, self.assembly_view):
            if hasattr(v, "enlargeRequested"):
                v.enlargeRequested.connect(self.toggle_big_3d)
        views.addWidget(self.left_tabs)
        views.addWidget(self.flat_view)
        views.setSizes([620, 700])

        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.info.linkActivated.connect(lambda link: self.show_fld() if link == "fld" else None)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(6, 0, 6, 6)
        self.bend_panel = BendPanel(self.settings)
        self.bend_panel.changed.connect(self.run_unfold)
        self.dim_table = QTableWidget(0, 2)
        self.dim_table.setHorizontalHeaderLabels(["항목", "값 (mm)"])
        self.dim_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dim_table.horizontalHeader().setStretchLastSection(True)
        self.dim_table.verticalHeader().setVisible(False)
        self.dim_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.addTab(self.dim_table, "치수 · 면적")
        self.bottom_tabs.addTab(self.table, "절곡")
        bl.addWidget(self.bottom_tabs, 5)
        bl.addWidget(self.bend_panel, 0)
        bl.addWidget(self.info, 2)

        split = QSplitter(Qt.Vertical)
        split.addWidget(views)
        split.addWidget(bottom)
        split.setSizes([540, 280])
        self.setCentralWidget(split)

        self._set_info("STEP 파일을 여세요. (솔리드웍스·NX·CATIA 에서 STEP 으로 저장)")
        # 상태 표시줄 오른쪽에 늘 버전을 보인다
        ver = QLabel(f"버전 {version_text(long=True)}")
        ver.setStyleSheet("color: #888; padding-right: 8px;")
        from . import company
        from PySide6.QtGui import QPixmap
        brand = QPushButton(QIcon(QPixmap.fromImage(company.logo_image(36))), " " + company.MAKER)
        brand.setIconSize(QPixmap.fromImage(company.logo_image(18)).size())
        brand.setFlat(True)
        brand.setCursor(Qt.PointingHandCursor)
        brand.setToolTip(f"회사 홈페이지 열기  {company.HOMEPAGE}")
        brand.setStyleSheet("QPushButton{color:#555; font-weight:bold; border:none; padding:0 6px;}"
                            "QPushButton:hover{color:#1f4e8c; text-decoration:underline;}")
        brand.clicked.connect(company.open_homepage)
        self.statusBar().addPermanentWidget(brand)
        self.statusBar().addPermanentWidget(ver)
        self._update_actions()

    # ---- 화면 구성

    def _build_toolbar(self):
        tb = QToolBar("작업 줄")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)

        self.act_open = QAction("열기", self, shortcut="Ctrl+O", triggered=self.open_dialog)
        self.act_save = QAction("DXF 저장", self, shortcut="Ctrl+S", triggered=self.save_dxf)
        self.act_batch = QAction("여러 파일 한꺼번에", self, triggered=self.batch)
        self.act_help = QAction("도움말", self, triggered=self.show_help)
        self.act_pdf = QAction("보고서 PDF", self, triggered=lambda: self.save_report("pdf"))
        self.act_xlsx = QAction("보고서 엑셀", self, triggered=lambda: self.save_report("xlsx"))
        self.act_history = QAction("전개 기록", self, shortcut="Ctrl+H", triggered=self.show_history)
        self.act_assy = QAction("조립도 PDF", self, triggered=self.save_assembly_pdf)
        self.act_nest = QAction("철판 배치", self, shortcut="Ctrl+N", triggered=self.show_nesting)
        self.act_bom = QAction("BOM", self, shortcut="Ctrl+B", triggered=self.save_bom)
        self.act_quote = QAction("견적", self, shortcut="Ctrl+E", triggered=self.show_quote)
        self.act_quote.setToolTip("도면(3D)으로 공정수·재료비·가공비·부자재를 계산해 견적서 초안 (엑셀·PDF)")
        self.act_die = QAction("금형 검토", self, shortcut="Ctrl+K", triggered=self.show_die)
        self.act_process = QAction("금형 공정", self, shortcut="Ctrl+J", triggered=lambda: self.show_die(4))
        self.act_process.setToolTip("3D 를 보고 문헌 규칙으로 금형 형식·공정 순서를 자동으로 (AI 도면 검토 선택), "
                                    "순차 금형 스트립 공정도 — PDF·DXF")
        self.act_die.setToolTip("지금 부품의 전단·굽힘 하중, 클리어런스, 스프링백, 설계 규칙, "
                                "스트립 배치, 원통 드로잉 공정 (프레스 금형 교재 계산)")
        self.act_bom.setToolTip("부품표: 같은 부품끼리 묶어 품번·수량·재질·두께·전개 크기·무게 (엑셀·PDF)")
        self.act_zip = QAction("ZIP 만들기", self, triggered=self.make_zip)
        self.act_zip.setToolTip("지금 연 3D 파일을 압축(.zip) 해서 보내기 쉽게 만듭니다")
        self.act_ai_bom = QAction("AI BOM", self, triggered=self.show_ai_bom)
        self.act_ai_bom.setToolTip("2D 도면 PDF 와 3D 를 AI(Claude)로 맞춰 보고 BOM 엑셀을 만듭니다")
        self.act_nest.setToolTip("전개한 부품을 1219 × 2438 같은 철판 위에 늘어놓아 필요한 장 수를 셉니다")
        self.act_doc_log = QAction("견적·금형 기록", self, triggered=self.show_doc_log)
        self.act_doc_log.setToolTip("저장한 생산 견적서·금형 견적서·금형 검토 기록 (찾기·메모·엑셀)")
        self.act_quit = QAction("끝내기", self, triggered=self.close)
        self.act_package = QAction("전체 분석", self, shortcut="Ctrl+Shift+A", triggered=lambda: self.show_quote(True))
        self.act_package.setToolTip("3D 조립품 → 부품 분리 → 전개 → 자재비 → 부품별 공정도 → 생산 견적 → 금형 견적을 "
                                    "한 폴더에 (견적 창에서 수량을 넣고 [전체 분석])")
        tb.setObjectName("작업 줄")
        self._build_ribbon()
        self.addToolBarBreak()
        self.addToolBar(tb)
        tb.addWidget(QLabel("  전개 방식 "))
        self.mode_box = QComboBox()
        for key, name in MODE_NAMES.items():
            self.mode_box.addItem(name, key)
        i = self.mode_box.findData(self.settings.value("mode", AUTO))
        self.mode_box.setCurrentIndex(max(0, i))
        self.mode_box.setToolTip("자동: 평면·원통·원뿔로만 된 판금은 정확 전개,\n"
                                 "자동차 부품처럼 자유곡면이 있으면 성형품 근사 전개")
        self.mode_box.currentIndexChanged.connect(self._mode_changed)
        tb.addWidget(self.mode_box)

        tb.addWidget(QLabel(" 부품 "))
        self.solid_box = QComboBox()
        self.solid_box.setMinimumWidth(240)
        self.solid_box.setMaxVisibleItems(25)
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
        self.dims_box = QCheckBox("치수")
        self.dims_box.setToolTip("전개도에 기본 치수(전체·절곡선 위치·구멍)와 두께·면적 요약을 표시하고\n"
                                 "DXF 의 DIM 레이어에도 넣습니다")
        self.dims_box.setChecked(self.settings.value("dims_on", "true") == "true")
        self.dims_box.toggled.connect(self._dims_toggled)
        tb.addWidget(self.dims_box)
        self.gl_box = QCheckBox("그래픽 가속")
        self.gl_box.setToolTip("3D 를 그래픽 카드(OpenGL)로 그립니다. 큰 조립품이 훨씬 빠릅니다.\n"
                               "화면이 깨지거나 원격 데스크톱이면 끄세요 (다시 시작하면 적용).")
        self.gl_box.setChecked(self.settings.value("use_gl", "true") == "true")
        self.gl_box.toggled.connect(self._gl_toggled)
        self.history_box = QCheckBox("전개 기록 남기기")
        self.history_box.setToolTip("전개한 부품의 수치와 DXF 사본을 자동으로 쌓아 둡니다.\n"
                                    "같은 날 같은 부품을 다시 전개하면 최신 값으로 갱신합니다.")
        self.history_box.setChecked(self.settings.value("history_on", "true") == "true")
        self.history_box.toggled.connect(
            lambda on: self.settings.setValue("history_on", "true" if on else "false"))
        self._fill_ribbon_options()

    # ---- 큰 분류 (리본): 파일 · 전개 · 네스팅 · BOM · 금형 · 견적 · 기록 · 설정·도움말
    CATEGORIES = [
        ("파일", "3D 도면(STEP·IGES·STL …)을 열고, 여러 파일을 한꺼번에 전개하거나 압축합니다."),
        ("전개", "판금 정확 전개 · 성형품 근사 전개 → 전개도 DXF, 보고서, 조립도"),
        ("네스팅", "전개한 부품을 철판(1219 × 2438 등)에 늘어놓아 장 수·사용률을 셉니다."),
        ("BOM", "같은 부품끼리 묶은 부품표(다단계 BOM), 도면 PDF 와 맞춘 AI BOM"),
        ("금형", "하중·클리어런스·스프링백·설계 규칙, 자동 공정 설계, 금형 공정도"),
        ("견적", "공정수·톤수·기계·자재비·가공비 → 생산 견적서, 금형 견적서"),
        ("기록", "전개 기록, 견적·금형 기록 — 찾기·메모·엑셀로 내보내기"),
        ("설정·도움말", "그래픽 가속, 도움말·바뀐 것"),
    ]

    def _build_ribbon(self):
        from PySide6.QtWidgets import QMenuBar, QTabWidget
        groups = {
            "파일": [self.act_open, self.act_package, self.act_batch, self.act_zip],
            "전개": [self.act_save, self.act_pdf, self.act_xlsx, self.act_assy],
            "네스팅": [self.act_nest],
            "BOM": [self.act_bom, self.act_ai_bom],
            "금형": [self.act_die, self.act_process],
            "견적": [self.act_package, self.act_quote, self.act_doc_log],
            "기록": [self.act_history, self.act_doc_log],
            "설정·도움말": [self.act_help],
        }
        self.ribbon = QTabWidget()
        self.ribbon.setDocumentMode(True)
        self.ribbon.setStyleSheet("QTabBar::tab { padding: 5px 16px; font-weight: bold; }"
                                  "QToolButton { padding: 3px 10px; }")
        self.ribbon_bars = {}
        menubar = QMenuBar(self)
        for name, hint in self.CATEGORIES:
            bar = QToolBar()
            bar.setToolButtonStyle(Qt.ToolButtonTextOnly)
            for act in groups[name]:
                bar.addAction(act)
            self.ribbon_bars[name] = bar
            page = QWidget()
            lay = QHBoxLayout(page)
            lay.setContentsMargins(4, 0, 4, 2)
            lay.addWidget(bar)
            lay.addStretch(1)
            tip = QLabel(hint)
            tip.setStyleSheet("color:#888")
            lay.addWidget(tip)
            self.ribbon.addTab(page, name)
            menu = menubar.addMenu(name)
            for act in groups[name]:
                menu.addAction(act)
            if name == "파일":
                menu.addSeparator()
                menu.addAction(self.act_quit)
        self.setMenuBar(menubar)
        for acts in groups.values():                 # 단축키는 어느 분류를 보고 있어도
            for act in acts:
                if act not in self.actions():
                    self.addAction(act)
        self.ribbon.setCurrentIndex(int(self.settings.value("ribbon_tab", 1)))
        self.ribbon.currentChanged.connect(lambda i: self.settings.setValue("ribbon_tab", i))
        holder = QToolBar("분류")
        holder.setObjectName("분류")
        holder.setMovable(False)
        holder.addWidget(self.ribbon)
        self.addToolBar(holder)

    def _fill_ribbon_options(self):
        """분류에 맞는 설정 상자: 전개 → DXF 절곡 글씨, 기록 → 전개 기록 남기기, 설정 → 그래픽 가속."""
        self.ribbon_bars["전개"].addSeparator()
        self.ribbon_bars["전개"].addWidget(self.notes_box)
        self.ribbon_bars["기록"].addSeparator()
        self.ribbon_bars["기록"].addWidget(self.history_box)
        self.ribbon_bars["설정·도움말"].addSeparator()
        self.ribbon_bars["설정·도움말"].addWidget(self.gl_box)

    def show_doc_log(self):
        from .doc_history_dialog import DocHistoryDialog
        DocHistoryDialog(self.history, open_source=self._open_part, parent=self).exec()

    def _gl_toggled(self, on):
        self.settings.setValue("use_gl", "true" if on else "false")
        QMessageBox.information(self, "그래픽 가속",
                                "프로그램을 다시 시작하면 적용됩니다." + (
                                    "" if not on or gl_available() else
                                    "\n\n이 PC 는 OpenGL 2.1 을 쓸 수 없어 예전 방식으로 그립니다."))

    def _dims_toggled(self, on):
        self.settings.setValue("dims_on", "true" if on else "false")
        self.flat_view.set_show_dims(on)

    def _mode_changed(self, _):
        self.settings.setValue("mode", self.mode_box.currentData())
        self.run_unfold()

    def _thickness_mode(self, auto):
        self.t_spin.setEnabled(not auto)
        self.run_unfold()

    def _update_actions(self):
        for act in (self.act_save, self.act_pdf, self.act_xlsx):
            act.setEnabled(self.result is not None)
        self.act_assy.setEnabled(self.model is not None)
        self.act_nest.setEnabled(self.model is not None)
        self.act_bom.setEnabled(self.model is not None)
        self.act_die.setEnabled(self.result is not None)
        self.act_quote.setEnabled(self.model is not None)
        self.act_package.setEnabled(self.model is not None)
        self.act_process.setEnabled(self.result is not None)
        self.act_ai_bom.setEnabled(self.model is not None)
        self.act_zip.setEnabled(self.model is not None)
        self.solid_box.setEnabled(self.model is not None and len(self.model.solids) > 1)

    def show_fld(self):
        """성형 한계도 (FLD) 창."""
        r = self.result
        if r is None or r.forming is None:
            return
        img = report.render_fld(r.forming, 900, 700)
        dlg = QDialog(self)
        dlg.setWindowTitle("성형 한계도 (FLD)")
        lab = QLabel()
        lab.setPixmap(QPixmap.fromImage(img))
        note = QLabel("점 하나 = 메시 삼각형 하나의 (부 변형률, 주 변형률). 빨간 선(FLC)을 넘으면 터질 위험, "
                      "보라 점은 두꺼워지는 곳(주름 가능). FLC 는 Keeler 식·재료 대표값이므로 "
                      "금형 확정 전에는 성형 해석·시험으로 확인하세요.")
        note.setWordWrap(True)
        lay = QVBoxLayout(dlg)
        lay.addWidget(lab)
        lay.addWidget(note)
        dlg.exec()

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
        self.setWindowTitle(f"{APP_NAME}  v{__version__} — {os.path.basename(path)}")
        self.solid_box.blockSignals(True)
        self.part_list.blockSignals(True)
        self.solid_box.clear()
        self.part_list.clear()
        for i in range(len(model.solids)):
            self.solid_box.addItem(model.label(i))
            self.part_list.addItem(model.label(i))
        self.solid_box.blockSignals(False)
        self.part_list.blockSignals(False)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.assembly_parts = assembly_polylines(model.raw_solids)
            if self.use_gl:
                self.assembly_meshes = mesh_parts_cached(model.raw_solids, model.cache_dir)
        finally:
            QApplication.restoreOverrideCursor()
        if self.use_gl:
            self.assembly_view.set_parts(self.assembly_meshes, self.assembly_parts)
        else:
            self.assembly_view.set_parts(self.assembly_parts)
        self.assy_parts_result = None
        self.excluded = set()
        self.calc_xlsx_btn.setEnabled(False)
        self.assy_summary.setText("[전체 계산] 을 누르면 모든 부품의\n두께·면적·무게 합계가 나옵니다.")
        # 부품이 많으면 번호는 고른 부품만 (화면이 번호로 덮이지 않게)
        self.all_balloons_box.blockSignals(True)
        self.all_balloons_box.setChecked(len(model.solids) <= 40)
        self.all_balloons_box.blockSignals(False)
        self._balloons_toggled(self.all_balloons_box.isChecked())
        # 부품이 여럿이면 조립품 전체부터 보여 준다
        self.left_tabs.setCurrentIndex(1 if len(model.solids) > 1 else 0)
        self.t_auto.setChecked(True)
        self.run_unfold()

    def calc_all(self):
        if self.model is None:
            return
        from PySide6.QtWidgets import QProgressDialog
        n = len(self.model.solids)
        dlg = QProgressDialog("부품을 전개하는 중…", "그만", 0, n, self)
        dlg.setWindowTitle("조립품 전체 계산")
        dlg.setMinimumDuration(0)

        def progress(i, total, name):
            dlg.setValue(i)
            dlg.setLabelText(f"{i + 1} / {total}  {name}")
            QApplication.processEvents()
            return not dlg.wasCanceled()

        settings = self.bend_panel.settings()
        thickness = None if self.t_auto.isChecked() else self.t_spin.value()
        parts = assembly_calc.compute_all(self.model, settings, self.mode_box.currentData(),
                                          thickness, progress)
        dlg.setValue(n)
        self.assy_parts_result = parts
        self.calc_xlsx_btn.setEnabled(bool(parts))
        for p in parts:
            item = self.part_list.item(p.index)
            if p.ok:
                item.setText(f"{self.model.label(p.index)}   t{p.thickness:.2f} · "
                             f"{p.metrics.blank_area / 1e6:.4f} m² · {p.metrics.weight_kg:.3f} kg")
            else:
                item.setText(f"{self.model.label(p.index)}   — 펼칠 수 없음")
                item.setToolTip(p.error)
        self._fill_summary()
        self._mark_excluded()

    def _included_parts(self):
        return [p for p in (self.assy_parts_result or []) if p.index not in self.excluded]

    def _fill_summary(self):
        settings = self.bend_panel.settings()
        parts = self._included_parts()
        groups, total = assembly_calc.summarize(parts, settings.mat.code)
        lines = [f"<b>전체 {len(parts)}개</b> · 전개 {total.count}개 · "
                 f"펼칠 수 없음 {len(parts) - total.count}개"
                 + (f" · <span style='color:#d07030'>제외 {len(self.excluded)}개</span>" if self.excluded else ""),
                 f"<b>블랭크 면적 합계</b> {total.blank_area / 1e6:.4f} m²",
                 f"<b>블랭크 무게 합계</b> {total.weight_kg:.3f} kg "
                 f"(사각 원판 {total.rect_weight_kg:.3f} kg)",
                 f"<b>절단 길이 합계</b> {total.cut_length / 1000:.2f} m", "<b>두께별</b>"]
        for g in groups:
            lines.append(f"t{g.thickness:g} × {g.count}개 · {g.blank_area / 1e6:.4f} m² · "
                         f"{g.weight_kg:.3f} kg")
        lines.append(f"<span style='color:#999'>재질 {settings.mat.code} 기준 무게</span>")
        self.assy_summary.setText("<br>".join(lines))

    def show_quote(self, package=False):
        """견적 창. 아직 [전체 계산] 을 안 했으면 먼저 한다. package: 전체 분석 단추를 앞에 (수량 넣고 누름)."""
        from .quote_dialog import QuoteDialog
        if self.model is None:
            QMessageBox.information(self, "견적", "먼저 3D 도면을 여세요.")
            return
        if not self.assy_parts_result:
            self.calc_all()
            if not self.assy_parts_result:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dlg = QuoteDialog(self.model, self.assy_parts_result, self.bend_panel.settings(), self.excluded,
                              os.path.splitext(os.path.basename(self.model.path))[0], self,
                              history=self.history if self.history_box.isChecked() else None)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "견적", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        if package is True:
            dlg.setWindowTitle(dlg.windowTitle() + " — 전체 분석: 수량·생산량·수신을 넣고 [전체 분석 (한 번에)] 를 누르세요")
            dlg.pkg_btn.setFocus()
            dlg.pkg_btn.setDefault(True)
        dlg.exec()

    def show_die(self, tab=0):
        """금형 검토 창 (지금 부품). tab: 처음 보일 탭 (4 = 금형 공정도)."""
        from .die_dialog import DieDialog
        if self.result is None:
            QMessageBox.information(self, "금형 검토", "먼저 부품을 전개하세요.")
            return
        idx = max(self.solid_box.currentIndex(), 0)
        name = self.model.names[idx] if self.model and self.model.names else ""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dlg = DieDialog(self.result, self.bend_panel.settings(), name, self,
                            history=self.history if self.history_box.isChecked() else None,
                            source_path=self.model.path if self.model else "")
        finally:
            QApplication.restoreOverrideCursor()
        dlg.tabs.setCurrentIndex(tab if isinstance(tab, int) else 0)
        dlg.exec()

    def show_nesting(self):
        """철판 배치 창. 조립품이면 [전체 계산] 결과의 모든 부품, 아니면 지금 부품."""
        from .nest_dialog import NestDialog
        if self.model is None:
            QMessageBox.information(self, "철판 배치", "먼저 3D 도면을 여세요.")
            return
        if len(self.model.solids) > 1 and not self.assy_parts_result:
            ans = QMessageBox.question(
                self, "철판 배치",
                f"부품이 {len(self.model.solids)}개입니다. 모든 부품을 전개해서 배치할까요?\n"
                "[아니요] 를 누르면 지금 고른 부품만 배치합니다.",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.Yes:
                self.calc_all()
        if self.assy_parts_result and len(self.model.solids) > 1:
            items = [(p.index + 1, p.name, p.result) for p in self._included_parts() if p.ok]
        elif self.result is not None:
            idx = max(self.solid_box.currentIndex(), 0)
            items = [(idx + 1, self.model.names[idx] if self.model.names else
                      os.path.basename(self.model.path), self.result)]
        else:
            items = []
        if not items:
            QMessageBox.information(self, "철판 배치", "전개한 부품이 없습니다.")
            return
        st = self.bend_panel.settings()
        dlg = NestDialog(items, st.mat.code, st.mat.density, os.path.basename(self.model.path), self)
        dlg.exec()

    def save_bom(self):
        """BOM (부품표) 을 엑셀 또는 PDF 로. 아직 [전체 계산] 을 안 했으면 먼저 한다."""
        from . import bom
        if self.model is None:
            return
        if not self.assy_parts_result:
            self.calc_all()
            if not self.assy_parts_result:
                return
        base = os.path.splitext(self.model.path)[0] + "_BOM.xlsx"
        path, flt = QFileDialog.getSaveFileName(self, "BOM 저장", base, "엑셀 (*.xlsx);;PDF (*.pdf)")
        if not path:
            return
        st = self.bend_panel.settings()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            items = bom.build(self.model, self.assy_parts_result, st.mat.density, self.excluded, st.mat.code)
            rows = bom.build_tree(self.model, self.assy_parts_result, st.mat.density, self.excluded,
                                  st.mat.code, items=items)
            name = os.path.basename(self.model.path)
            if path.lower().endswith(".pdf"):
                bom.save_tree_pdf(rows, path, name, st.mat.code, st.mat.density)
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                bom.save_tree_xlsx(rows, path, name, st.mat.code, st.mat.density)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "BOM 저장 실패", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"BOM {len(items)} 품목을 저장했습니다: {path}", 8000)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_ai_bom(self):
        from . import bom
        from .ai_bom_dialog import AiBomDialog
        if self.model is None:
            return
        if not self.assy_parts_result:
            self.calc_all()
            if not self.assy_parts_result:
                return
        st = self.bend_panel.settings()
        items = bom.build(self.model, self.assy_parts_result, st.mat.density, self.excluded, st.mat.code)
        AiBomDialog(items, self.model.path, st.mat.code, st.mat.density, self).exec()

    def save_assembly_xlsx(self):
        if not self.assy_parts_result:
            return
        base = os.path.splitext(self.model.path)[0] + "_assembly.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "조립품 합계 엑셀", base, "엑셀 (*.xlsx)")
        if not path:
            return
        assembly_calc.save_xlsx(path, self.model, self._included_parts(),
                                self.bend_panel.settings().mat.code)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _hide_balloons(self, hide):
        v = self.assembly_view
        if hasattr(v, "btn_num"):
            v.btn_num.blockSignals(True)
            v.btn_num.setChecked(not hide)
            v.btn_num.blockSignals(False)
            v.set_balloons_visible(not hide)
        else:
            v.show_numbers = not hide
            v.update()
        self.all_balloons_box.setEnabled(not hide)

    def _balloons_toggled(self, on):
        if hasattr(self.assembly_view, "set_all_balloons"):
            self.assembly_view.set_all_balloons(on)

    def make_zip(self):
        """지금 연 3D 파일 전체를 압축. 다 되면 그 폴더를 열어 파일을 바로 끌어다 보낼 수 있게."""
        if self.model is None:
            return
        src = self.model.path
        base = os.path.splitext(src)[0] + ".zip"
        path, _ = QFileDialog.getSaveFileName(self, "ZIP 만들기", base, "압축 파일 (*.zip)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            loader.zip_file(src, path)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "ZIP 실패", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        a, b = os.path.getsize(src) / 1e6, os.path.getsize(path) / 1e6
        QMessageBox.information(self, "ZIP 만들기",
                                f"{os.path.basename(src)}  {a:,.1f} MB → {os.path.basename(path)}  {b:,.1f} MB\n\n"
                                "저장한 폴더를 엽니다. 이 .zip 파일을 보내면 됩니다.\n"
                                "(그래도 크면 문제 부품에서 오른쪽 단추 → '이 부품만 STEP 으로 저장')")
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def export_part_step(self, idx=None):
        """부품 하나만 STEP (또는 압축 .zip) 으로 — 큰 조립품에서 떼어 보내기."""
        if self.model is None:
            return
        if idx is None:
            idx = max(0, self.solid_box.currentIndex())
        name = self.model.names[idx] if self.model.names else f"part_{idx + 1}"
        safe = "".join(c if c not in '\\/:*?"<>|' else "_" for c in name)
        base = os.path.join(os.path.dirname(self.model.path),
                            f"{os.path.splitext(os.path.basename(self.model.path))[0]}_{idx + 1}_{safe}.zip")
        path, _ = QFileDialog.getSaveFileName(self, f"{idx + 1}번 부품만 저장", base,
                                              "압축 STEP (*.zip);;STEP (*.stp *.step)")
        if not path:
            return
        try:
            loader.save_step(self.model.raw_solids[idx], path, name)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        kb = os.path.getsize(path) / 1024
        self.statusBar().showMessage(f"{idx + 1}번 부품을 저장했습니다 ({kb:,.0f} KB): {path}", 10000)

    def set_excluded(self, idx, on):
        """부품을 전체 계산·철판 배치 합계에서 빼거나 다시 넣는다."""
        if on:
            self.excluded.add(idx)
        else:
            self.excluded.discard(idx)
        if idx == max(0, self.solid_box.currentIndex()):
            self.flat_view.set_excluded(on)
        self._mark_excluded()
        if self.assy_parts_result:
            self._fill_summary()

    def _exclude_current(self, on):
        if self.model is not None:
            self.set_excluded(max(0, self.solid_box.currentIndex()), on)

    def _mark_excluded(self):
        for i in range(self.part_list.count()):
            it = self.part_list.item(i)
            t = it.text().replace("  [제외]", "")
            it.setText(t + ("  [제외]" if i in self.excluded else ""))

    def _part_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        item = self.part_list.itemAt(pos)
        v = self.assembly_view
        m = QMenu(self)
        can_hide = hasattr(v, "hide_part")
        if item is not None:
            idx = self.part_list.row(item)
            if can_hide:
                if idx in v.hidden:
                    m.addAction("보이기", lambda: v.show_part(idx))
                else:
                    m.addAction("숨기기", lambda: v.hide_part(idx))
                m.addAction("이것만 보기", lambda: v.isolate(idx))
                m.addSeparator()
            m.addAction("이 부품만 STEP 으로 저장…", lambda: self.export_part_step(idx))
            if idx in self.excluded:
                m.addAction("다시 포함 (전체 계산·철판 배치)", lambda: self.set_excluded(idx, False))
            else:
                m.addAction("제외 (전체 계산·철판 배치에서 뺌)", lambda: self.set_excluded(idx, True))
        if can_hide:
            m.addAction("모두 보이기", v.show_all)
        m.exec(self.part_list.mapToGlobal(pos))

    def _mark_hidden(self):
        """숨긴 부품은 목록에서 흐리게."""
        hidden = self.assembly_view.hidden
        for i in range(self.part_list.count()):
            it = self.part_list.item(i)
            it.setForeground(QColor(150, 150, 150) if i in hidden else self.part_list.palette().text().color())
            f = it.font()
            f.setItalic(i in hidden)
            it.setFont(f)

    def select_part(self, idx):
        if self.model is not None and 0 <= idx < len(self.model.solids):
            self.solid_box.setCurrentIndex(idx)

    def current_solid(self):
        if self.model is None:
            return None
        return self.model.solids[max(0, self.solid_box.currentIndex())]

    # ---- 전개

    def run_unfold(self):
        solid = self.current_solid()
        if solid is None:
            return
        idx = max(0, self.solid_box.currentIndex())
        self.assembly_view.set_highlight(idx)
        self.part_list.blockSignals(True)
        self.part_list.setCurrentRow(idx)
        self.part_list.blockSignals(False)
        if self.use_gl:
            self.model_view.set_parts(mesh_parts([solid]), [solid_polylines(solid, iso=False)])
        else:
            self.model_view.set_solid(solid)
        thickness = None if self.t_auto.isChecked() else self.t_spin.value()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.result = unfold(solid, thickness=thickness, settings=self.bend_panel.settings(),
                                 mode=self.mode_box.currentData())
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

        self.dims = None
        if self.result is not None:
            try:
                self.dims = dimsmod.compute(self.result, self.bend_panel.settings().mat.density)
            except Exception:
                traceback.print_exc()
        self.flat_view.show_dims = self.dims_box.isChecked()
        self.flat_view.set_result(self.result, self.dims, excluded=idx in self.excluded)
        self._fill_table()
        self._fill_dims()
        self._update_actions()
        self.record_id = None
        if self.result is not None and self.history_box.isChecked():
            try:
                self.record_id = self.history.record(
                    self.model.path, self.result, self.bend_panel.settings(),
                    part_index=self.solid_box.currentIndex() + 1, part_count=len(self.model.solids),
                    part_name=self.model.names[self.solid_box.currentIndex()])
            except Exception:
                traceback.print_exc()
        if self.result is not None:
            r = self.result
            if self.t_auto.isChecked():
                self.t_spin.blockSignals(True)
                self.t_spin.setValue(r.thickness)
                self.t_spin.blockSignals(False)
            w, h = r.size
            m = report.ReportData("", self.model.path, r, self.bend_panel.settings()).metrics
            lines = [
                "<b>성형품 근사 전개</b>" if r.mode == "forming" else "<b>판금 정확 전개</b>",
                f"<b>전개 크기</b> {w:.2f} × {h:.2f} mm",
                f"<b>블랭크</b> {m.blank_area:,.0f} mm² · {m.weight_kg:.3f} kg · 수율 {m.yield_ratio:.0%}",
                f"<b>두께</b> {r.thickness:.3f} mm" + (" (자동 측정)" if thickness is None else ""),
                f"<b>절곡 조건</b> {r.settings_text}",
                f"<b>절곡</b> {len(r.bends)}곳",
                "<span style='color:#999'>UP = 전개도를 보는 쪽으로 세움, "
                "DOWN = 반대쪽으로 세움</span>",
            ]
            rec = self.model.recognized.get(idx, (0, 0))
            lines.insert(0, f"<b>{self.model.label(idx)}</b>")
            if rec[0]:
                lines.append(f"<span style='color:#999'>자유곡면으로 저장된 면 {rec[0]}개를 "
                             "평면·원통·원뿔로 되돌려 계산했습니다.</span>")
            for txt in r.rolled:
                lines.append(txt)
            if r.forming is not None and r.forming.flc0 > 0:
                split, marginal, wrinkle, top = r.forming.flc_summary
                col = "#e05050" if split > 0.001 else "#e0a040" if marginal > 0.001 else "#60c060"
                lines.append(f"<b>성형 한계</b> <span style='color:{col}'>최대 {top:.0%}</span> "
                             f"(FLC0 {r.forming.flc0:.3f}) · 주름 가능 {wrinkle:.1%} · "
                             "<a href='fld'>성형 한계도 보기</a>")
            for wmsg in r.warnings:
                lines.append(f"<span style='color:#e0a040'>⚠ {wmsg}</span>")
            self._set_info("<br>".join(lines))

    def _fill_dims(self):
        rows = self.dims.rows() if self.dims else []
        self.dim_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.dim_table.setItem(i, 0, QTableWidgetItem(k))
            self.dim_table.setItem(i, 1, QTableWidgetItem(v))

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
                            notes=self.notes_box.isChecked(), dims=self.dims_box.isChecked(),
                            density=self.bend_panel.settings().mat.density,
                            user_dims=self.flat_view.user_dims)
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))
            return
        self._note_export(path)
        self.statusBar().showMessage(f"저장했습니다: {path}", 8000)

    def _note_export(self, path):
        if self.record_id is not None:
            try:
                self.history.add_export(self.record_id, path)
            except Exception:
                traceback.print_exc()

    def show_history(self):
        HistoryDialog(self.history, open_source=self._open_part,
                      change_folder=self._change_history_folder, parent=self).exec()

    def _change_history_folder(self, folder):
        self.history.close()
        self.history = History(folder)
        self.settings.setValue("history_dir", folder)
        return self.history

    def _open_part(self, path, part_index):
        self.open_file(path)
        if self.model is not None and 1 <= part_index <= len(self.model.solids):
            self.solid_box.setCurrentIndex(part_index - 1)

    def _report_data(self):
        name = os.path.splitext(os.path.basename(self.model.path))[0]
        return report.ReportData(
            name, self.model.path, self.result, self.bend_panel.settings(), self.current_solid(),
            solid_index=self.solid_box.currentIndex() + 1, solid_count=len(self.model.solids),
            part_title=self.model.names[self.solid_box.currentIndex()],
            user_dims=list(self.flat_view.user_dims))

    def save_assembly_pdf(self):
        if self.model is None:
            return
        base = os.path.splitext(self.model.path)[0] + "_assembly.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "조립도 PDF 저장", base, "PDF (*.pdf)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            report.save_assembly_pdf(self.model, path, parts=self.assembly_parts,
                                     yaw=getattr(self.assembly_view, "yaw", None),
                                     pitch=getattr(self.assembly_view, "pitch", None))
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "조립도 저장 실패", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"조립도를 저장했습니다: {path}", 8000)
        if QMessageBox.question(self, "조립도", "저장했습니다. 지금 열어 볼까요?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def save_report(self, kind):
        if self.result is None:
            return
        base = self._default_dxf_name().replace("_flat.dxf", "_report")
        filt = "PDF (*.pdf)" if kind == "pdf" else "엑셀 (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "보고서 저장", f"{base}.{kind}", filt)
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            d = self._report_data()
            (report.save_pdf if kind == "pdf" else report.save_xlsx)(d, path)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "보고서 저장 실패", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._note_export(path)
        self.statusBar().showMessage(f"보고서를 저장했습니다: {path}", 8000)
        if QMessageBox.question(self, "보고서", "저장했습니다. 지금 열어 볼까요?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def batch(self):
        start = self.settings.value("last_dir", "")
        paths, _ = QFileDialog.getOpenFileNames(self, "전개할 파일 고르기", start, OPEN_FILTER)
        if not paths:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "DXF 를 저장할 폴더", os.path.dirname(paths[0]))
        if not out_dir:
            return
        thickness = None if self.t_auto.isChecked() else self.t_spin.value()
        with_reports = QMessageBox.question(
            self, "보고서", "DXF 와 함께 부품별 보고서(PDF·엑셀)와\n"
                           "전체 부품 목록(엑셀)도 만들까요?") == QMessageBox.Yes
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            text = batch_convert(paths, out_dir, self.bend_panel.settings(), thickness,
                                 self.notes_box.isChecked(), mode=self.mode_box.currentData(),
                                 reports=with_reports,
                                 history=self.history if self.history_box.isChecked() else None,
                                 progress=lambda: QApplication.processEvents())
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "한꺼번에 전개 결과", text)

    def toggle_big_3d(self):
        """3D 화면(부품 3D · 조립품 전체)을 큰 창으로 띄우거나, 큰 창이면 닫고 제자리로."""
        from PySide6.QtWidgets import QDialog
        if self._big is not None:
            self._big.close()
            return
        dlg = QDialog(self)
        name = os.path.basename(self.model.path) if self.model else ""
        dlg.setWindowTitle(f"3D 크게 보기 — {name}   (두 번 누르거나 Esc 로 닫기)")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        sizes = self.views_split.sizes()
        lay.addWidget(self.left_tabs)          # 원래 자리에서 옮겨 온다

        def back(_=None):
            self.views_split.insertWidget(0, self.left_tabs)
            self.views_split.setSizes(sizes)
            self.left_tabs.show()
            self._big = None

        dlg.finished.connect(back)
        self._big = dlg
        scr = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        dlg.setGeometry(scr)
        dlg.showMaximized()

    def show_help(self):
        from .changes import text as changes_text
        from . import company
        from PySide6.QtGui import QPixmap
        box = QMessageBox(self)
        box.setWindowTitle("도움말")
        box.setIconPixmap(QPixmap.fromImage(company.logo_image(48)))
        box.setText(HELP_TEXT.format(version=version_text(long=True)) + f"\n\n{company.MAKER}   {company.HOMEPAGE}"
                    + "\n\n최근 바뀐 것\n" + changes_text(limit=3))
        box.exec()

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


def batch_convert(paths, out_dir, settings, thickness, notes, mode=AUTO, reports=False,
                  progress=None, history=None):
    ok, failed, items = 0, [], []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            model = loader.load(path)
            for i, solid in enumerate(model.solids, 1):
                r = unfold(solid, thickness=thickness, settings=settings, mode=mode)
                suffix = f"_{i}" if len(model.solids) > 1 else ""
                base = os.path.join(out_dir, f"{name}{suffix}")
                dxf_export.save(r, base + "_flat.dxf", part_name=name, notes=notes,
                                density=settings.mat.density)
                if history is not None:
                    rid = history.record(path, r, settings, i, len(model.solids),
                                         part_name=model.names[i - 1])
                    history.add_export(rid, base + "_flat.dxf")
                if reports:
                    d = report.ReportData(name, path, r, settings, solid, i, len(model.solids),
                                          part_title=model.names[i - 1])
                    report.save_pdf(d, base + "_report.pdf")
                    report.save_xlsx(d, base + "_report.xlsx")
                    items.append(d)
                ok += 1
        except Exception as e:
            failed.append(f"{os.path.basename(path)}: {str(e).splitlines()[0]}")
        if progress:
            progress()
    text = f"DXF {ok}개를 만들었습니다.\n저장 위치: {out_dir}"
    if reports:
        # 조립품이면 번호 풍선이 달린 조립도도 함께
        for path in paths:
            try:
                model = loader.load(path)
                if len(model.solids) > 1:
                    name = os.path.splitext(os.path.basename(path))[0]
                    report.save_assembly_pdf(model, os.path.join(out_dir, f"{name}_assembly.pdf"))
            except Exception:
                pass
    if items:
        list_path = os.path.join(out_dir, "parts_list.xlsx")
        report.save_parts_list(items, list_path)
        text += f"\n보고서 {len(items)}건과 부품 목록(parts_list.xlsx)도 만들었습니다."
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
   전개한 부품은 [전개 기록] 에 자동으로 쌓입니다 (수치 + DXF 사본).
   기록 창에서 찾기, 메모, 엑셀로 내보내기, 원본 다시 열기를 할 수 있습니다.
   [보고서 PDF] · [보고서 엑셀] 은 전개도·치수·무게·절단 길이·절곡 표를 담은 보고서를 만듭니다.
     CUT  레이어 : 절단선 (외곽, 구멍)
     BEND 레이어 : 절곡선
     NOTE 레이어 : 절곡 번호·방향·각도 (가공기로 보낼 때 끄세요)

전개 길이 = 바깥 치수 합 − Σ 연신
연신 = 2·tan(θ/2)·(R + t) − θ·(R + K·t)

전개할 수 있는 형상: 두께가 일정한 판금 부품.
  · 어떤 각도의 절곡이든 (30°, 45°, 120°, 헤밍), 비스듬한 절곡선
  · 원통 절곡, 말아 만든 관, 원뿔(깔때기)·원뿔 절곡

자동차 부품처럼 자유곡면이 있는 성형품은 [전개 방식: 자동] 에서 저절로
"성형품 근사 전개" 로 바뀝니다. 블랭크 모양·크기·무게와 두께 변화 색 지도를
보여 줍니다 (파랑 = 두꺼워짐·주름, 빨강 = 얇아짐·터짐). 근사값이므로
금형 블랭크는 트라이아웃이나 성형 해석으로 확정하세요.
용접으로 붙인 조립품은 부품마다 따로 저장해서 여세요.
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
