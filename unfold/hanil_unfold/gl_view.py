"""그래픽 카드(OpenGL)로 그리는 3D 화면.

부품을 삼각형 면으로 나눠 한 번만 그래픽 카드 메모리에 올려 두고, 돌리기·확대·이동은
변환 행렬만 바꿔 그래픽 카드가 다시 그린다. 그래서 부품이 수백 개, 면이 수천 개여도 부드럽다.

  · 면은 음영(조명)으로, 모서리는 선으로 그린다.
  · 고른 부품은 주황색으로 강조한다.
  · 부품을 누르면 그 부품을 고른다 (보이지 않는 화면에 부품마다 다른 색을 칠해 읽는 방식).
  · 번호 풍선은 화면이 멈췄을 때 한 번만 배치해 그 위에 겹쳐 그린다.

그래픽 카드가 OpenGL 2.1 을 지원하지 않으면 ok=False 가 되고, 화면은 예전 방식으로 돌아간다.
"""
from __future__ import annotations

import math
import os
import tempfile

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMatrix4x4, QOpenGLContext, QPainter, QPen, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFramebufferObject,
                              QOpenGLFramebufferObjectFormat, QOpenGLShaderProgram,
                              QOpenGLShader)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

GL_TRIANGLES, GL_LINES = 0x0004, 0x0001
GL_FLOAT = 0x1406
GL_DEPTH_TEST, GL_POLYGON_OFFSET_FILL = 0x0B71, 0x8037
GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT = 0x4000, 0x0100
GL_LEQUAL = 0x0203

VERT = """
#version 120
attribute vec3 pos;
attribute vec3 nrm;
uniform mat4 mvp;
uniform mat3 rot;
varying vec3 vn;
void main() {
    vn = rot * nrm;
    gl_Position = mvp * vec4(pos, 1.0);
}
"""
FRAG = """
#version 120
uniform vec4 color;
uniform float lit;
varying vec3 vn;
void main() {
    float d = abs(normalize(vn).z);
    float k = mix(1.0, 0.35 + 0.65 * d, lit);
    gl_FragColor = vec4(color.rgb * k, color.a);
}
"""


# ---------------------------------------------------------------- 메시 만들기

_STL = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])


def mesh_parts_cached(solids, cache_dir=""):
    """mesh_parts 결과를 보관 폴더에 npz 로 두고 다시 쓴다."""
    path = os.path.join(cache_dir, "mesh.npz") if cache_dir else ""
    if path and os.path.exists(path):
        try:
            z = np.load(path)
            offs = z["offs"]
            if len(offs) == len(solids) + 1:
                V, N = z["v"], z["n"]
                return [(V[a:b], N[a:b]) for a, b in zip(offs[:-1], offs[1:])]
        except Exception:
            pass
    meshes = mesh_parts(solids)
    if path:
        try:
            offs = np.cumsum([0] + [len(v) for v, _ in meshes])
            V = np.vstack([v for v, _ in meshes]) if meshes else np.zeros((0, 3), np.float32)
            N = np.vstack([n for _, n in meshes]) if meshes else np.zeros((0, 3), np.float32)
            os.makedirs(cache_dir, exist_ok=True)
            np.savez(path, v=V, n=N, offs=offs)
        except Exception:
            pass
    return meshes


def mesh_parts(solids, deflection=None):
    """부품마다 (삼각형 꼭짓점 (n,3), 삼각형 법선 (n,3)). 무거운 일은 C++ 가 한다.

    BRepMesh 로 나누고, 이진 STL 로 써서 numpy 로 바로 읽는다 (파이썬 반복문 없이)."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    from OCP.TopoDS import TopoDS_Compound

    comp = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(comp)
    for s in solids:
        b.Add(comp, s)
    if deflection is None:
        box = Bnd_Box()
        BRepBndLib.Add_s(comp, box)
        diag = box.CornerMin().Distance(box.CornerMax()) if not box.IsVoid() else 100.0
        deflection = max(diag / 2000.0, 0.02)
    BRepMesh_IncrementalMesh(comp, deflection, False, 0.5, True)

    out = []
    fd, tmp = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    w = StlAPI_Writer()
    w.ASCIIMode = False
    try:
        for s in solids:
            try:
                w.Write(s, tmp)
                a = np.fromfile(tmp, dtype=_STL, offset=84)
            except Exception:
                a = np.zeros(0, dtype=_STL)
            v = a["v"].reshape(-1, 3).astype(np.float32)
            n = a["n"]
            # STL 법선이 비어 있으면 직접 구한다
            if len(a) and not np.any(n):
                t = a["v"]
                n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
                n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            n = np.repeat(n, 3, axis=0).astype(np.float32)
            out.append((v, n))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return out


def lines_to_segments(polylines):
    """[(k,3) 배열] → 선분 끝점 (2m, 3)."""
    segs = [np.repeat(p, 2, axis=0)[1:-1] for p in polylines if len(p) > 1]
    return np.vstack(segs).astype(np.float32) if segs else np.zeros((0, 3), np.float32)


# ---------------------------------------------------------------- 화면

def gl_available() -> bool:
    """OpenGL 2.1 이상을 쓸 수 있는지 (프로그램 시작 때 한 번)."""
    if os.environ.get("HANIL_NO_GL"):
        return False
    try:
        ctx = QOpenGLContext()
        if not ctx.create():
            return False
        fmt = ctx.format()
        return (fmt.majorVersion(), fmt.minorVersion()) >= (2, 1) and not ctx.isOpenGLES()
    except Exception:
        return False


class GLView(QOpenGLWidget):
    """조립품 전체 또는 부품 하나를 그래픽 카드로 그린다."""

    partClicked = Signal(int)

    def __init__(self, balloons=True, hint=""):
        super().__init__()
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)                     # 계단 줄이기
        self.setFormat(fmt)
        self.balloons = balloons
        self.all_balloons = True              # False 면 고른 부품 번호만
        self.hint = hint
        self.ok = True
        self.parts = []                       # [(삼각형 v, n, 선분)]
        self.highlight = None
        self.yaw, self.pitch = math.radians(-35), math.radians(25)
        self.zoom = 1.0
        self.pan = np.zeros(2)
        self.center = np.zeros(3)
        self.extent = 1.0
        self._drag = None
        self._moved = False
        self._dirty_gpu = False
        self._ranges = []
        self._balloon_cache = None            # (카메라 키, [(idx, 중심, 반지름, 끈 끝)])
        self._anchors = []                    # 부품마다 풍선 끈을 붙일 후보 점들
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self.update)
        self.setMinimumSize(300, 300)
        self.setMouseTracking(False)

    # ---- 자료

    def set_parts(self, meshes, edge_lines):
        """meshes: mesh_parts() 결과, edge_lines: 부품마다 선 목록."""
        self.parts = []
        pts = []
        self._anchors = []
        for (v, n), lines in zip(meshes, edge_lines):
            segs = lines_to_segments(lines)
            self.parts.append((v, n, segs))
            if len(v):
                pts.append(v[:: max(1, len(v) // 2000)])
            elif len(segs):
                pts.append(segs)
            cand = v if len(v) else segs
            step = max(1, len(cand) // 64)
            self._anchors.append(cand[::step] if len(cand) else np.zeros((0, 3), np.float32))
        if pts:
            P = np.vstack(pts)
            lo, hi = P.min(0), P.max(0)
            self.center = (lo + hi) / 2
            self.extent = float(np.linalg.norm(hi - lo)) or 1.0
        self.zoom, self.pan = 1.0, np.zeros(2)
        self._dirty_gpu = True
        self._balloon_cache = None
        self.update()

    def set_all_balloons(self, on):
        self.all_balloons = on
        self._balloon_cache = None
        self.update()

    def set_highlight(self, idx):
        self.highlight = idx
        self._balloon_cache = None
        self.update()

    # ---- 카메라

    def _rotation(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        view = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])   # z 축이 위로
        return rx @ view @ rz

    def _matrices(self):
        """(4x4 mvp, 3x3 rot, 화면 투영 함수)."""
        R = self._rotation()
        w, h = max(self.width(), 1), max(self.height(), 1)
        half = self.extent * 0.55 / self.zoom
        sx, sy = (half * w / h, half) if w >= h else (half, half * h / w)
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = -R @ self.center
        P = np.diag([1 / sx, 1 / sy, -1 / (self.extent * 2), 1.0])
        T = np.eye(4)
        T[0, 3] = 2 * self.pan[0] / w
        T[1, 3] = -2 * self.pan[1] / h
        mvp = T @ P @ M
        return mvp, R

    def project(self, pts):
        """3D 점들 → 화면 좌표 (픽셀)."""
        mvp, _ = self._matrices()
        hpts = np.c_[pts, np.ones(len(pts))] @ mvp.T
        x = (hpts[:, 0] + 1) * 0.5 * self.width()
        y = (1 - hpts[:, 1]) * 0.5 * self.height()
        return np.c_[x, y]

    # ---- OpenGL

    def initializeGL(self):
        try:
            ctx = QOpenGLContext.currentContext()
            if ctx is None or (ctx.format().majorVersion(), ctx.format().minorVersion()) < (2, 1):
                raise RuntimeError("OpenGL 2.1 미만")
            self.f = ctx.functions()
            self.prog = QOpenGLShaderProgram(self)
            ok = (self.prog.addShaderFromSourceCode(QOpenGLShader.Vertex, VERT)
                  and self.prog.addShaderFromSourceCode(QOpenGLShader.Fragment, FRAG)
                  and self.prog.link())
            if not ok:
                raise RuntimeError(self.prog.log())
            # 이름 대신 번호로 넘겨야 PySide6 가 float 값을 받는다
            self.u = {n: self.prog.uniformLocation(n) for n in ("mvp", "rot", "color", "lit")}
            self.vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
            self.vbo.create()
            self._dirty_gpu = True
        except Exception as e:
            self.ok = False
            self.error = str(e)

    def _upload(self):
        """모든 부품의 삼각형과 선분을 버퍼 하나에 [위치, 법선] 으로 올린다."""
        chunks, self._ranges = [], []
        start = 0
        zero = np.zeros(3, np.float32)
        for v, n, segs in self.parts:
            tri = np.hstack([v, n]) if len(v) else np.zeros((0, 6), np.float32)
            ln = np.hstack([segs, np.tile(zero, (len(segs), 1))]) if len(segs) else np.zeros((0, 6), np.float32)
            chunks += [tri, ln]
            self._ranges.append((start, len(tri), start + len(tri), len(ln)))
            start += len(tri) + len(ln)
        data = np.ascontiguousarray(np.vstack(chunks) if chunks else np.zeros((0, 6)), dtype=np.float32)
        self.vbo.bind()
        self.vbo.allocate(data.tobytes(), data.nbytes)
        self.vbo.release()
        self._dirty_gpu = False

    def _draw_scene(self, mvp, R, id_mode=False):
        f = self.f
        p = self.prog
        p.bind()
        self.vbo.bind()
        loc_pos, loc_nrm = p.attributeLocation("pos"), p.attributeLocation("nrm")
        p.enableAttributeArray(loc_pos)
        p.setAttributeBuffer(loc_pos, GL_FLOAT, 0, 3, 24)
        if loc_nrm >= 0:
            p.enableAttributeArray(loc_nrm)
            p.setAttributeBuffer(loc_nrm, GL_FLOAT, 12, 3, 24)
        from PySide6.QtGui import QMatrix3x3
        u = self.u
        p.setUniformValue(u["mvp"], QMatrix4x4(*mvp.astype(float).ravel().tolist()))
        p.setUniformValue(u["rot"], QMatrix3x3(R.astype(float).ravel().tolist()))

        hot = QColor(255, 140, 0)
        base = QColor(150, 175, 205)
        dim = self.highlight is not None
        f.glEnable(GL_POLYGON_OFFSET_FILL)
        f.glPolygonOffset(1.0, 1.0)
        for i, (t0, tn, l0, ln) in enumerate(self._ranges):
            if id_mode:
                c = QColor((i + 1) & 255, ((i + 1) >> 8) & 255, 0)
                p.setUniformValue(u["lit"], 0.0)
            else:
                c = hot if i == self.highlight else (QColor(120, 135, 155) if dim else base)
                p.setUniformValue(u["lit"], 1.0)
            p.setUniformValue(u["color"], c)
            if tn:
                f.glDrawArrays(GL_TRIANGLES, t0, tn)
        f.glDisable(GL_POLYGON_OFFSET_FILL)
        if not id_mode:
            p.setUniformValue(u["lit"], 0.0)
            for i, (t0, tn, l0, ln) in enumerate(self._ranges):
                if ln:
                    p.setUniformValue(u["color"], QColor(90, 40, 0) if i == self.highlight
                                      else QColor(25, 30, 40))
                    f.glDrawArrays(GL_LINES, l0, ln)
        p.disableAttributeArray(loc_pos)
        if loc_nrm >= 0:
            p.disableAttributeArray(loc_nrm)
        self.vbo.release()
        p.release()

    def paintGL(self):
        if not self.ok:
            return
        f = self.f
        if self._dirty_gpu:
            self._upload()
        f.glClearColor(0.125, 0.133, 0.149, 1.0)
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not self.parts:
            self._overlay_text("3D 형상")
            return
        f.glEnable(GL_DEPTH_TEST)
        f.glDepthFunc(GL_LEQUAL)
        mvp, R = self._matrices()
        self._draw_scene(mvp, R)
        f.glDisable(GL_DEPTH_TEST)
        self._overlay()

    # ---- 겹쳐 그리기 (번호 풍선, 안내 글)

    def _overlay_text(self, text):
        p = QPainter(self)
        p.setPen(QColor(150, 150, 150))
        p.drawText(self.rect(), Qt.AlignCenter, text)
        p.end()

    def _overlay(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.balloons and len(self.parts) > 1 and self._drag is None:
            self._paint_balloons(p)
        p.setPen(QColor(150, 150, 150))
        p.drawText(8, self.height() - 8, self.hint)
        p.end()

    def _camera_key(self):
        return (round(self.yaw, 4), round(self.pitch, 4), round(self.zoom, 4),
                round(float(self.pan[0]), 1), round(float(self.pan[1]), 1),
                self.width(), self.height(), self.highlight)

    def _paint_balloons(self, p):
        from .drawing import _spread_balloons
        key = self._camera_key()
        if self._balloon_cache is None or self._balloon_cache[0] != key:
            fpx = max(9, min(13, int(self.height() / 50)))
            r = fpx * 0.95
            anchors = []
            for idx, cand in enumerate(self._anchors):
                if not len(cand):
                    continue
                if not self.all_balloons and idx != self.highlight:
                    continue
                s = self.project(cand)
                c = (s.min(0) + s.max(0)) / 2
                anchors.append((idx, s[np.argmin(np.linalg.norm(s - c, axis=1))]))
            pos = _spread_balloons([a for _, a in anchors], r, QRectF(self.rect()))
            self._balloon_cache = (key, [(i, a, b, r, fpx) for (i, a), b in zip(anchors, pos)])
        f = QFont(self.font())
        for idx, a, b, r, fpx in self._balloon_cache[1]:
            f.setPixelSize(fpx)
            f.setBold(True)
            p.setFont(f)
            hot = idx == self.highlight
            col = QColor(255, 150, 40) if hot else QColor(210, 215, 225)
            p.setPen(QPen(col, 0.8))
            if np.linalg.norm(b - a) > r:
                d = (a - b) / np.linalg.norm(a - b)
                p.drawLine(QPointF(*(b + d * r)), QPointF(*a))
            p.setBrush(QColor(255, 236, 200) if hot else QColor(32, 34, 38, 220))
            p.drawEllipse(QPointF(*b), r, r)
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(150, 60, 0) if hot else col)
            txt = str(idx + 1)
            fm = p.fontMetrics()
            p.drawText(QPointF(b[0] - fm.horizontalAdvance(txt) / 2, b[1] + fm.ascent() / 2 - 1), txt)

    # ---- 고르기

    def pick(self, x, y):
        """(x, y) 픽셀에 보이는 부품 번호 (없으면 None)."""
        if not self.ok or not self.parts:
            return None
        # 풍선을 먼저
        if self._balloon_cache:
            for idx, a, b, r, _ in self._balloon_cache[1]:
                if math.hypot(x - b[0], y - b[1]) <= r * 1.2:
                    return idx
        self.makeCurrent()
        try:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Depth)
            ratio = self.devicePixelRatioF()
            fbo = QOpenGLFramebufferObject(int(self.width() * ratio), int(self.height() * ratio), fmt)
            fbo.bind()
            f = self.f
            f.glViewport(0, 0, fbo.width(), fbo.height())
            f.glClearColor(0, 0, 0, 1)
            f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            f.glEnable(GL_DEPTH_TEST)
            mvp, R = self._matrices()
            self._draw_scene(mvp, R, id_mode=True)
            f.glDisable(GL_DEPTH_TEST)
            img = fbo.toImage()
            fbo.release()
            c = QColor(img.pixel(int(x * ratio), int(y * ratio)))
            idx = c.red() + (c.green() << 8) - 1
            return idx if 0 <= idx < len(self.parts) else None
        finally:
            self.doneCurrent()

    # ---- 마우스

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
            self.pan += np.array([d.x(), d.y()])
        else:
            self.yaw += d.x() * 0.01
            self.pitch = max(-1.55, min(1.55, self.pitch + d.y() * 0.01))
        self.update()

    def mouseReleaseEvent(self, ev):
        clicked = self._drag is not None and not self._moved
        self._drag = None
        if clicked:
            idx = self.pick(ev.position().x(), ev.position().y())
            if idx is not None:
                self.partClicked.emit(idx)
        self.update()

    def wheelEvent(self, ev):
        self.zoom *= 1.15 ** (ev.angleDelta().y() / 120)
        # 휠을 굴리는 동안은 풍선을 숨기고, 멈추면 다시 배치
        self._drag = ("wheel", None)
        self.update()
        self._settle.start(250)
        QTimer.singleShot(260, self._end_wheel)

    def _end_wheel(self):
        if self._drag == ("wheel", None):
            self._drag = None
            self.update()

    def mouseDoubleClickEvent(self, _):
        self.zoom, self.pan = 1.0, np.zeros(2)
        self.update()
