"""그래픽 카드(OpenGL)로 그리는 3D 화면 (조명·외곽선·단면·카메라는 SolidCraft 에서 옮김).

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
import time

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
GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA = 0x0BE2, 0x0302, 0x0303

# 셰이더: 조명(주광·보조광·하이라이트), 둥근 면 외곽선, 단면(잘린 안쪽은 빗금)은
# SolidCraft (https://github.com/tangency-labs/solidcraft, MIT OR Apache-2.0,
# Copyright (c) 2026 SolidCraft contributors) 의 assets/shaders/viewport.wgsl 을 GLSL 1.20 으로 옮겼다.
VERT = """
#version 120
attribute vec3 pos;
attribute vec3 nrm;
uniform mat4 mvp;
varying vec3 vn;
varying vec3 wp;
void main() {
    vn = nrm;
    wp = pos;
    gl_Position = mvp * vec4(pos, 1.0);
}
"""
FRAG = """
#version 120
uniform vec4 color;
uniform float lit;       // 0: 선 (조명 없음)
uniform vec3 back;       // 눈 쪽 방향 (월드)
uniform vec4 clip;       // 단면: 법선 xyz, 거리 w (법선 0 이면 단면 없음)
uniform vec4 cap;        // 잘린 안쪽 색
uniform float sil;       // 1: 외곽선
varying vec3 vn;
varying vec3 wp;
void main() {
    vec3 v = normalize(back);
    float ndv = 0.0;
    float fw = 0.0;
    if (lit > 0.5) {
        ndv = dot(normalize(vn), v);
        fw = fwidth(ndv);
    }
    if (length(clip.xyz) > 0.5 && dot(clip.xyz, wp) > clip.w) discard;
    if (lit < 0.5) { gl_FragColor = color; return; }
    if (!gl_FrontFacing && length(clip.xyz) > 0.5) {
        vec3 base = mix(color.rgb, cap.rgb, 0.35);
        float h = fract((gl_FragCoord.x + gl_FragCoord.y) / 9.0);
        gl_FragColor = vec4(h < 0.22 ? base * 0.6 : base, 1.0);
        return;
    }
    vec3 n = normalize(vn);
    if (dot(n, v) < 0.0) n = -n;
    vec3 key = normalize(v * 0.8 + vec3(-0.3, 0.2, 0.6));
    float diff = max(dot(n, key), 0.0);
    float fill = max(dot(n, v), 0.0);
    vec3 hv = normalize(key + v);
    float spec = pow(max(dot(n, hv), 0.0), 40.0) * 0.25;
    float k = 0.42 + 0.38 * diff + 0.25 * fill;
    vec3 c = min(color.rgb * k + vec3(spec), vec3(1.0));
    if (sil > 0.5 && fw > 1e-6) {
        float a = 1.0 - smoothstep(fw * 0.8, fw * 2.0, abs(ndv));
        c = mix(c, vec3(0.07, 0.08, 0.10), a);
    }
    gl_FragColor = vec4(c, color.a);
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


# ---------------------------------------------------------------- 카메라

# 표준 방향 (yaw, pitch). SolidCraft crates/render/src/camera.rs 의 StandardView 와 같다:
# yaw 0 은 +Y 쪽을 바라보는 정면, pitch 는 XY 평면 위 높이.
STANDARD_VIEWS = {
    "front": (0.0, 0.0), "back": (math.pi, 0.0),
    "right": (-math.pi / 2, 0.0), "left": (math.pi / 2, 0.0),
    "top": (0.0, math.pi / 2 - 1e-4), "bottom": (0.0, -math.pi / 2 + 1e-4),
    "iso": (-math.pi / 4, 0.6154797086703874),
}
VIEW_NAMES = [("맞춤", "fit"), ("등각", "iso"), ("정면", "front"), ("윗면", "top"), ("우측", "right"),
              ("좌측", "left"), ("뒷면", "back")]


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


class OrbitCamera:
    """대상점 둘레를 도는 카메라 (Z 가 위). 평행(fov 0) 또는 원근.

    SolidCraft 의 Camera (MIT OR Apache-2.0) 를 numpy 로 옮겼다: 기저·뷰·투영, 커서 쪽으로 확대,
    화면 픽셀만큼 이동, 끌기 회전."""

    def __init__(self):
        self.target = np.zeros(3)
        self.yaw, self.pitch = STANDARD_VIEWS["iso"]
        self.distance = 200.0
        self.fov = 0.0
        self.radius = 100.0

    def copy(self):
        c = OrbitCamera()
        c.target, c.yaw, c.pitch, c.distance, c.fov, c.radius = (
            self.target.copy(), self.yaw, self.pitch, self.distance, self.fov, self.radius)
        return c

    def back(self):
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        v = np.array([-math.sin(self.yaw) * cp, -math.cos(self.yaw) * cp, sp])
        return v / np.linalg.norm(v)

    def basis(self):
        b = self.back()
        r = np.array([math.cos(self.yaw), -math.sin(self.yaw), 0.0])
        u = np.cross(b, r)
        u /= np.linalg.norm(u)
        return r, u, b

    def eye(self):
        return self.target + self.back() * self.distance

    def half_height(self):
        return self.distance * math.tan(self.fov * 0.5) if self.fov > 0 else self.distance * 0.4

    def view(self):
        r, u, b = self.basis()
        e = self.eye()
        V = np.eye(4)
        V[0, :3], V[1, :3], V[2, :3] = r, u, b
        V[:3, 3] = [-r @ e, -u @ e, -b @ e]
        return V

    def proj(self, aspect):
        """OpenGL 식 투영 (깊이 -1..1)."""
        R = max(self.radius, 1e-3)
        if self.fov > 0:
            n = max(self.distance - 2 * R, self.distance * 1e-3, 1e-3)
            f = self.distance + 2 * R
            t = 1.0 / math.tan(self.fov * 0.5)
            return np.array([[t / aspect, 0, 0, 0], [0, t, 0, 0],
                             [0, 0, (f + n) / (n - f), 2 * f * n / (n - f)], [0, 0, -1, 0]])
        n, f = self.distance - 4 * R - 1, self.distance + 4 * R + 1
        h = self.half_height()
        w = h * aspect
        return np.array([[1 / w, 0, 0, 0], [0, 1 / h, 0, 0],
                         [0, 0, -2 / (f - n), -(f + n) / (f - n)], [0, 0, 0, 1]])

    def view_proj(self, aspect):
        return self.proj(aspect) @ self.view()

    def fit(self, center, radius):
        self.target = np.asarray(center, float).copy()
        self.radius = max(radius, 1e-3)
        if self.fov > 0:
            self.distance = radius / math.tan(self.fov * 0.5) * 1.15
        else:
            self.distance = radius / 0.4 * 1.08

    def fit_box(self, lo, hi, aspect):
        """지금 방향에서 상자(lo..hi)가 화면을 알맞게 채우도록 대상점과 거리를 맞춘다."""
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        self.radius = max(float(np.linalg.norm(hi - lo)) / 2, 1e-3)
        r, u, b = self.basis()
        C = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        cr, cu, cb = C @ r, C @ u, C @ b
        mid = (lo + hi) / 2
        self.target = mid + r * ((cr.max() + cr.min()) / 2 - mid @ r) + u * ((cu.max() + cu.min()) / 2 - mid @ u)
        hh = max((cu.max() - cu.min()) / 2, (cr.max() - cr.min()) / 2 / max(aspect, 1e-3), 1e-3) * 1.12
        if self.fov > 0:
            self.distance = hh / math.tan(self.fov * 0.5) + (cb.max() - cb.min()) / 2
        else:
            self.distance = hh / 0.4

    def plane_point(self, x, y, w, h):
        """화면 (x, y) 픽셀 아래, 대상점을 지나고 화면과 나란한 평면 위의 점."""
        r, u, _ = self.basis()
        hh = self.half_height()
        nx = x / max(w, 1) * 2 - 1
        ny = 1 - y / max(h, 1) * 2
        return self.target + r * (nx * hh * w / max(h, 1)) + u * (ny * hh)

    def zoom_at(self, factor, anchor=None):
        f = min(max(factor, 0.05), 20.0)
        nd = min(max(self.distance * f, 1e-3), 1e7)
        if anchor is not None:
            self.target = anchor + (self.target - anchor) * (nd / self.distance)
        self.distance = nd

    def pan(self, dx, dy, h):
        r, u, _ = self.basis()
        k = 2 * self.half_height() / max(h, 1)
        self.target = self.target - r * (dx * k) + u * (dy * k)

    def orbit(self, dx, dy):
        lim = math.pi / 2 - 1e-4
        self.yaw = (self.yaw + dx * 0.008) % (2 * math.pi)
        self.pitch = min(max(self.pitch + dy * 0.008, -lim), lim)


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
    """조립품 전체 또는 부품 하나를 그래픽 카드로 그린다.

    위쪽 단추: 맞춤·표준 방향(부드럽게 돌아감), 원근, 외곽선, 단면(축·위치), 투명(고른 부품만 또렷하게).
    마우스: 왼쪽 끌기 회전, 오른쪽(또는 Shift) 끌기 이동, 휠은 커서 쪽으로 확대, 두 번 누르면 큰 창 (맞춤은 [맞춤]·F).
    오른쪽 단추를 끌지 않고 누르면 메뉴 (그 부품 숨기기 · 이것만 보기 · 모두 보이기).
    """

    partClicked = Signal(int)
    hiddenChanged = Signal()
    enlargeRequested = Signal()           # 두 번 누름: 큰 창으로

    def __init__(self, balloons=True, hint=""):
        super().__init__()
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)                     # 계단 줄이기
        self.setFormat(fmt)
        self.balloons = balloons
        self.all_balloons = True              # False 면 고른 부품 번호만
        self.show_numbers = True              # False 면 번호 풍선을 모두 숨김
        self.hidden = set()                   # 숨긴 부품 번호들
        self.hint = hint
        self.ok = True
        self.parts = []                       # [(삼각형 v, n, 선분)]
        self.highlight = None
        self.cam = OrbitCamera()
        self.center = np.zeros(3)
        self.radius = 1.0
        self.lo = np.zeros(3)
        self.hi = np.ones(3)
        self.silhouette = True
        self.xray = False                     # 고른 부품 말고는 반투명
        self.section = None                   # None 또는 (축 0/1/2, 0..1 위치)
        self._drag = None
        self._moved = False
        self._dirty_gpu = False
        self._ranges = []
        self._balloon_cache = None
        self._anchors = []
        self._anim = None
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._step_anim)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.timeout.connect(self._end_motion)
        self.setMinimumSize(300, 300)
        self.setFocusPolicy(Qt.StrongFocus)
        self._build_controls()

    # ---- 위쪽 단추

    def _build_controls(self):
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSlider, QToolButton, QVBoxLayout, QWidget
        bar = QWidget(self)
        bar.setStyleSheet(
            "QToolButton{color:#ddd;background:rgba(40,44,52,210);border:1px solid #556;"
            "border-radius:3px;padding:1px 4px;} QToolButton:checked{background:#c06a10;color:white;}"
            "QComboBox{color:#ddd;background:rgba(40,44,52,210);} QSlider{min-width:90px;}")
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(6, 6, 6, 0)
        rows.setSpacing(3)
        # 첫 줄: 방향, 둘째 줄: 보기 방식 (좁은 화면에서도 다 보이게)
        lay = QHBoxLayout()
        lay.setSpacing(3)
        rows.addLayout(lay)
        for label, key in VIEW_NAMES:
            b = QToolButton(bar)
            b.setText(label)
            b.clicked.connect(lambda _=False, k=key: self.go_view(k))
            lay.addWidget(b)
        lay.addStretch()
        lay = QHBoxLayout()
        lay.setSpacing(3)
        rows.addLayout(lay)

        def toggle(label, tip, slot, on=False):
            b = QToolButton(bar)
            b.setText(label)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setChecked(on)
            b.toggled.connect(slot)
            lay.addWidget(b)
            return b

        self.btn_num = toggle("번호", "부품 번호 풍선 보이기 / 숨기기", self.set_balloons_visible, True)
        self.btn_num.setVisible(self.balloons)
        def button(label, tip, slot):
            b = QToolButton(bar)
            b.setText(label)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            b.setVisible(self.balloons)       # 조립품 화면에서만
            lay.addWidget(b)
            return b

        button("숨기기", "고른 부품을 숨깁니다 (H)", lambda: self.hide_part(self.highlight))
        button("이것만", "고른 부품만 보이고 나머지는 숨깁니다", lambda: self.isolate(self.highlight))
        button("모두 보이기", "숨긴 부품을 다시 모두 보입니다 (Shift+H)", self.show_all)
        self.btn_persp = toggle("원근", "원근(가까운 것이 크게) / 평행 보기", self.set_perspective)
        self.btn_sil = toggle("외곽선", "둥근 면이 돌아가는 가장자리에 선", self.set_silhouette, True)
        self.btn_xray = toggle("투명", "고른 부품만 또렷하게, 나머지는 반투명", self.set_xray)
        self.btn_sec = toggle("단면", "평면으로 잘라 속을 봅니다 (잘린 면은 빗금)", self._section_toggled)
        self.sec_axis = QComboBox(bar)
        self.sec_axis.addItems(["X", "Y", "Z"])
        self.sec_axis.setCurrentIndex(2)
        self.sec_axis.currentIndexChanged.connect(self._section_changed)
        self.sec_pos = QSlider(Qt.Horizontal, bar)
        self.sec_pos.setRange(0, 1000)
        self.sec_pos.setValue(500)
        self.sec_pos.valueChanged.connect(self._section_changed)
        for w in (self.sec_axis, self.sec_pos):
            w.setVisible(False)
            lay.addWidget(w)
        lay.addStretch()
        self._bar = bar

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._bar.setGeometry(0, 0, self.width(), 58)

    def set_perspective(self, on):
        c = self.cam
        target_h = c.half_height()
        c.fov = 0.6 if on else 0.0
        # 같은 크기로 보이게 거리를 맞춘다
        c.distance = target_h / math.tan(c.fov * 0.5) if on else target_h / 0.4
        self.cam.radius = self.radius
        self._changed()

    # ---- 부품 숨기기

    def set_hidden(self, idxs):
        self.hidden = {i for i in idxs if 0 <= i < len(self.parts)}
        self._balloon_cache = None
        self.update()
        self.hiddenChanged.emit()

    def hide_part(self, idx):
        if idx is not None:
            self.set_hidden(self.hidden | {idx})

    def show_part(self, idx):
        self.set_hidden(self.hidden - {idx})

    def isolate(self, idx):
        if idx is not None:
            self.set_hidden(set(range(len(self.parts))) - {idx})

    def show_all(self):
        self.set_hidden(set())

    def set_balloons_visible(self, on):
        self.show_numbers = on
        self.update()

    def set_silhouette(self, on):
        self.silhouette = on
        self.update()

    def set_xray(self, on):
        self.xray = on
        self.update()

    def _section_toggled(self, on):
        self.sec_axis.setVisible(on)
        self.sec_pos.setVisible(on)
        self._section_changed()

    def _section_changed(self, *_):
        self.section = (self.sec_axis.currentIndex(), self.sec_pos.value() / 1000) \
            if self.btn_sec.isChecked() else None
        self.update()

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
            self.lo, self.hi = P.min(0), P.max(0)
            self.center = (self.lo + self.hi) / 2
            self.radius = float(np.linalg.norm(self.hi - self.lo)) / 2 or 1.0
        self.cam.fit_box(self.lo, self.hi, self._aspect())
        self.hidden = set()
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

    # 예전 화면과 같은 이름 (조립도 PDF 가 묻는다): 이 화면의 방향은 따로 쓰지 않는다
    yaw = None
    pitch = None

    # ---- 카메라 움직임

    def go_view(self, key):
        """표준 방향 또는 맞춤으로 부드럽게 (SolidCraft 의 CameraAnim 과 같은 ease-in-out)."""
        to = self.cam.copy()
        if key != "fit":
            to.yaw, to.pitch = STANDARD_VIEWS[key]
        to.fit_box(self.lo, self.hi, self._aspect())
        # 가까운 쪽으로 돈다
        d = (to.yaw - self.cam.yaw + math.pi) % (2 * math.pi) - math.pi
        to.yaw = self.cam.yaw + d
        self._anim = (self.cam.copy(), to, time.perf_counter(), 0.35)
        self._drag = ("anim", None)
        self._anim_timer.start()

    def _step_anim(self):
        if self._anim is None:
            self._anim_timer.stop()
            return
        a, b, t0, dur = self._anim
        t = ease_in_out((time.perf_counter() - t0) / dur)
        c = self.cam
        c.target = a.target + (b.target - a.target) * t
        c.yaw = a.yaw + (b.yaw - a.yaw) * t
        c.pitch = a.pitch + (b.pitch - a.pitch) * t
        c.distance = a.distance * (b.distance / a.distance) ** t
        if t >= 1.0:
            self._anim = None
            self._anim_timer.stop()
            self._drag = None
            self._balloon_cache = None
        self.update()

    def _changed(self):
        self._balloon_cache = None
        self.update()

    def _end_motion(self):
        if self._drag is not None and self._drag[0] == "wheel":
            self._drag = None
        self.update()

    def _aspect(self):
        return max(self.width(), 1) / max(self.height(), 1)

    def _matrices(self):
        w, h = max(self.width(), 1), max(self.height(), 1)
        self.cam.radius = self.radius
        return self.cam.view_proj(w / h)

    def project(self, pts):
        """3D 점들 → 화면 좌표 (픽셀)."""
        mvp = self._matrices()
        hp = np.c_[pts, np.ones(len(pts))] @ mvp.T
        wv = np.where(np.abs(hp[:, 3]) < 1e-12, 1e-12, hp[:, 3])
        x = (hp[:, 0] / wv + 1) * 0.5 * self.width()
        y = (1 - hp[:, 1] / wv) * 0.5 * self.height()
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
            self.u = {n: self.prog.uniformLocation(n)
                      for n in ("mvp", "color", "lit", "back", "clip", "cap", "sil")}
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

    def _clip_plane(self):
        if self.section is None:
            return (0.0, 0.0, 0.0, 0.0)
        axis, t = self.section
        n = [0.0, 0.0, 0.0]
        n[axis] = 1.0
        d = float(self.lo[axis] + (self.hi[axis] - self.lo[axis]) * t)
        return (n[0], n[1], n[2], d)

    def _draw_scene(self, mvp, id_mode=False):
        from PySide6.QtGui import QVector3D, QVector4D
        f = self.f
        p = self.prog
        u = self.u
        p.bind()
        self.vbo.bind()
        loc_pos, loc_nrm = p.attributeLocation("pos"), p.attributeLocation("nrm")
        p.enableAttributeArray(loc_pos)
        p.setAttributeBuffer(loc_pos, GL_FLOAT, 0, 3, 24)
        if loc_nrm >= 0:
            p.enableAttributeArray(loc_nrm)
            p.setAttributeBuffer(loc_nrm, GL_FLOAT, 12, 3, 24)
        p.setUniformValue(u["mvp"], QMatrix4x4(*mvp.astype(float).ravel().tolist()))
        b = self.cam.back()
        p.setUniformValue(u["back"], QVector3D(*b))
        p.setUniformValue(u["clip"], QVector4D(*self._clip_plane()))
        p.setUniformValue(u["cap"], QVector4D(0.85, 0.35, 0.25, 1.0))
        p.setUniformValue(u["sil"], 1.0 if (self.silhouette and not id_mode) else 0.0)

        hot = QColor(255, 140, 0)
        base = QColor(150, 175, 205)
        dim = self.highlight is not None
        see_through = self.xray and self.highlight is not None and not id_mode

        def tri(i, c, alpha=1.0):
            t0, tn, _, _ = self._ranges[i]
            if tn and i not in self.hidden:
                col = QColor(c)
                col.setAlphaF(alpha)
                p.setUniformValue(u["color"], col)
                f.glDrawArrays(GL_TRIANGLES, t0, tn)

        f.glEnable(GL_POLYGON_OFFSET_FILL)
        f.glPolygonOffset(1.0, 1.0)
        for i in range(len(self._ranges)):
            if id_mode:
                p.setUniformValue(u["lit"], 0.0)
                tri(i, QColor((i + 1) & 255, ((i + 1) >> 8) & 255, 0))
            elif see_through and i != self.highlight:
                continue
            else:
                p.setUniformValue(u["lit"], 1.0)
                tri(i, hot if i == self.highlight else (QColor(120, 135, 155) if dim else base))
        f.glDisable(GL_POLYGON_OFFSET_FILL)
        if not id_mode:
            p.setUniformValue(u["lit"], 0.0)
            for i, (_, _, l0, ln) in enumerate(self._ranges):
                if ln and i not in self.hidden and not (see_through and i != self.highlight):
                    p.setUniformValue(u["color"], QColor(90, 40, 0) if i == self.highlight
                                      else QColor(25, 30, 40))
                    f.glDrawArrays(GL_LINES, l0, ln)
            if see_through:
                # 나머지 부품은 반투명 (깊이는 쓰지 않아 뒤가 비친다)
                f.glEnable(GL_BLEND)
                f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                f.glDepthMask(False)
                p.setUniformValue(u["lit"], 1.0)
                for i in range(len(self._ranges)):
                    if i != self.highlight:
                        tri(i, QColor(150, 175, 205), 0.18)
                f.glDepthMask(True)
                f.glDisable(GL_BLEND)
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
        self._draw_scene(self._matrices())
        f.glDisable(GL_DEPTH_TEST)
        self._overlay()

    # ---- 겹쳐 그리기 (번호 풍선, 축 표시, 안내 글)

    def _overlay_text(self, text):
        p = QPainter(self)
        p.setPen(QColor(150, 150, 150))
        p.drawText(self.rect(), Qt.AlignCenter, text)
        p.end()

    def _overlay(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.balloons and self.show_numbers and len(self.parts) > 1 and self._drag is None:
            self._paint_balloons(p)
        self._paint_axes(p)
        p.setPen(QColor(150, 150, 150))
        p.drawText(70, self.height() - 8, self.hint)
        p.end()

    def _paint_axes(self, p):
        """왼쪽 아래 X·Y·Z 방향 표시."""
        r, u, _ = self.cam.basis()
        o = QPointF(34, self.height() - 34)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        for axis, col, name in ((np.array([1, 0, 0]), QColor(230, 80, 70), "X"),
                                (np.array([0, 1, 0]), QColor(90, 200, 90), "Y"),
                                (np.array([0, 0, 1]), QColor(90, 140, 240), "Z")):
            e = o + QPointF(axis @ r * 22, -(axis @ u) * 22)
            p.setPen(QPen(col, 2))
            p.drawLine(o, e)
            p.drawText(e + QPointF(2, 4), name)

    def _camera_key(self):
        c = self.cam
        return (round(c.yaw, 4), round(c.pitch, 4), round(c.distance, 4), round(c.fov, 3),
                tuple(np.round(c.target, 3)), self.width(), self.height(), self.highlight,
                self.all_balloons, tuple(sorted(self.hidden)))

    def _paint_balloons(self, p):
        from .drawing import _spread_balloons
        key = self._camera_key()
        if self._balloon_cache is None or self._balloon_cache[0] != key:
            fpx = max(9, min(13, int(self.height() / 50)))
            r = fpx * 0.95
            anchors = []
            for idx, cand in enumerate(self._anchors):
                if not len(cand) or idx in self.hidden:
                    continue
                if not self.all_balloons and idx != self.highlight:
                    continue
                s = self.project(cand)
                c = (s.min(0) + s.max(0)) / 2
                anchors.append((idx, s[np.argmin(np.linalg.norm(s - c, axis=1))]))
            pos = _spread_balloons([a for _, a in anchors], r, QRectF(0, 60, self.width(), self.height() - 60))
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
        if self._balloon_cache and self.show_numbers:
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
            self._draw_scene(self._matrices(), id_mode=True)
            f.glDisable(GL_DEPTH_TEST)
            img = fbo.toImage()
            fbo.release()
            c = QColor(img.pixel(int(x * ratio), int(y * ratio)))
            idx = c.red() + (c.green() << 8) - 1
            return idx if 0 <= idx < len(self.parts) else None
        finally:
            self.doneCurrent()

    # ---- 마우스·건반

    def mousePressEvent(self, ev):
        self._anim = None
        self._drag = (ev.position(), ev.button())
        self._moved = False

    def mouseMoveEvent(self, ev):
        if self._drag is None or self._drag[0] in ("wheel", "anim"):
            return
        d = ev.position() - self._drag[0]
        if abs(d.x()) + abs(d.y()) > 2:
            self._moved = True
        self._drag = (ev.position(), self._drag[1])
        if self._drag[1] in (Qt.RightButton, Qt.MiddleButton) or ev.modifiers() & Qt.ShiftModifier:
            self.cam.pan(d.x(), d.y(), self.height())
        else:
            self.cam.orbit(d.x(), d.y())
        self.update()

    def mouseReleaseEvent(self, ev):
        clicked = self._drag is not None and not self._moved
        button = self._drag[1] if self._drag is not None else None
        self._drag = None
        if clicked and button == Qt.RightButton:
            # 오른쪽 단추를 끌지 않고 눌렀다 떼면 메뉴 (끌면 화면 이동)
            self._context_menu(ev.position())
        elif clicked:
            idx = self.pick(ev.position().x(), ev.position().y())
            if idx is not None:
                self.partClicked.emit(idx)
        self.update()

    def _context_menu(self, pos):
        self.build_menu(pos).exec(self.mapToGlobal(pos.toPoint()))

    def build_menu(self, pos):
        """오른쪽 단추 메뉴 (pos 아래 부품 기준)."""
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        if self.balloons and self.parts:
            idx = self.pick(pos.x(), pos.y())
            if idx is not None:
                self.partClicked.emit(idx)        # 누른 부품을 고른다
                m.addAction(f"{idx + 1}번 숨기기", lambda: self.hide_part(idx))
                m.addAction(f"{idx + 1}번만 보기", lambda: self.isolate(idx))
                m.addSeparator()
            act = m.addAction("모두 보이기", self.show_all)
            act.setEnabled(bool(self.hidden))
            if self.hidden:
                sub = m.addMenu(f"숨긴 부품 보이기 ({len(self.hidden)}개)")
                for i in sorted(self.hidden)[:40]:
                    sub.addAction(f"{i + 1}번", lambda i=i: self.show_part(i))
            m.addSeparator()
        m.addAction("맞춤", lambda: self.go_view("fit"))
        m.addAction("크게 보기", self.enlargeRequested.emit)
        return m

    def wheelEvent(self, ev):
        # 커서 아래 점이 그 자리에 머물도록 확대 (SolidCraft 의 zoom_at)
        pos = ev.position()
        anchor = self.cam.plane_point(pos.x(), pos.y(), self.width(), self.height())
        self.cam.zoom_at(0.87 ** (ev.angleDelta().y() / 120), anchor)
        self._drag = ("wheel", None)
        self.update()
        self._settle.start(250)

    def mouseDoubleClickEvent(self, _):
        self.enlargeRequested.emit()

    def keyPressEvent(self, ev):
        keys = {Qt.Key_F: "fit", Qt.Key_0: "iso", Qt.Key_1: "front", Qt.Key_7: "top",
                Qt.Key_3: "right", Qt.Key_4: "left", Qt.Key_9: "back"}
        if ev.key() == Qt.Key_H and self.balloons:
            if ev.modifiers() & Qt.ShiftModifier:
                self.show_all()
            else:
                self.hide_part(self.highlight)
        elif ev.key() in keys:
            self.go_view(keys[ev.key()])
        else:
            super().keyPressEvent(ev)
