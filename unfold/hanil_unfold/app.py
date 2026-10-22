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
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QUrl
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout,
                               QWidget)

from . import __version__, dxf_export, loader
from . import report
from .bend_panel import BendPanel
from .drawing import DARK, FlatTransform, paint_flat, paint_legend, solid_polylines, view_rotation
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

        tf = FlatTransform(self.scale, self.offset.x(), self.offset.y())
        f = QFont(self.font())
        f.setPointSize(9)
        p.setFont(f)
        paint_flat(p, r, tf, DARK)
        if r.forming is not None:
            paint_legend(p, QRectF(self.width() - 280, self.height() - 50, 260, 12), DARK)

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
        self.act_pdf = QAction("보고서 PDF", self, triggered=lambda: self.save_report("pdf"))
        self.act_xlsx = QAction("보고서 엑셀", self, triggered=lambda: self.save_report("xlsx"))
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addAction(self.act_pdf)
        tb.addAction(self.act_xlsx)
        tb.addAction(self.act_batch)
        tb.addSeparator()

        tb.addWidget(QLabel(" 전개 방식 "))
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

    def _mode_changed(self, _):
        self.settings.setValue("mode", self.mode_box.currentData())
        self.run_unfold()

    def _thickness_mode(self, auto):
        self.t_spin.setEnabled(not auto)
        self.run_unfold()

    def _update_actions(self):
        for act in (self.act_save, self.act_pdf, self.act_xlsx):
            act.setEnabled(self.result is not None)
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
            rec = (self.model.recognized or [])
            idx = max(0, self.solid_box.currentIndex())
            if idx < len(rec) and rec[idx][0]:
                lines.append(f"<span style='color:#999'>자유곡면으로 저장된 면 {rec[idx][0]}개를 "
                             "평면·원통·원뿔로 되돌려 계산했습니다.</span>")
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

    def _report_data(self):
        name = os.path.splitext(os.path.basename(self.model.path))[0]
        return report.ReportData(
            name, self.model.path, self.result, self.bend_panel.settings(), self.current_solid(),
            solid_index=self.solid_box.currentIndex() + 1, solid_count=len(self.model.solids))

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
                                 progress=lambda: QApplication.processEvents())
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "한꺼번에 전개 결과", text)

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


def batch_convert(paths, out_dir, settings, thickness, notes, mode=AUTO, reports=False,
                  progress=None):
    ok, failed, items = 0, [], []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            model = loader.load(path)
            for i, solid in enumerate(model.solids, 1):
                r = unfold(solid, thickness=thickness, settings=settings, mode=mode)
                suffix = f"_{i}" if len(model.solids) > 1 else ""
                base = os.path.join(out_dir, f"{name}{suffix}")
                dxf_export.save(r, base + "_flat.dxf", part_name=name, notes=notes)
                if reports:
                    d = report.ReportData(name, path, r, settings, solid, i, len(model.solids))
                    report.save_pdf(d, base + "_report.pdf")
                    report.save_xlsx(d, base + "_report.xlsx")
                    items.append(d)
                ok += 1
        except Exception as e:
            failed.append(f"{os.path.basename(path)}: {str(e).splitlines()[0]}")
        if progress:
            progress()
    text = f"DXF {ok}개를 만들었습니다.\n저장 위치: {out_dir}"
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
