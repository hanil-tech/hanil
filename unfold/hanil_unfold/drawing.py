"""전개도와 3D 선 모델 그리기. 화면, PDF, 엑셀 그림이 같은 코드를 쓴다."""
from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from .unfolder import Arc, Line, Polyline


class Theme:
    def __init__(self, dark=True):
        if dark:
            self.bg = QColor(32, 34, 38)
            self.cut = QColor(235, 235, 235)
            self.bend = QColor(255, 200, 40)
            self.note = QColor(120, 220, 120)
            self.edge3d = QColor(150, 200, 255)
            self.text = QColor(200, 200, 200)
            self.dim = QColor(140, 190, 255)
        else:  # 인쇄용
            self.bg = QColor(255, 255, 255)
            self.cut = QColor(0, 0, 0)
            self.bend = QColor(210, 120, 0)
            self.note = QColor(0, 120, 40)
            self.edge3d = QColor(30, 70, 140)
            self.text = QColor(40, 40, 40)
            self.dim = QColor(30, 80, 170)


DARK, LIGHT = Theme(True), Theme(False)


# ---------------------------------------------------------------- 두께 변화 색

THIN_LIMIT = 0.20   # 색 눈금 끝 (±20 %)


def thinning_color(x: float) -> QColor:
    """두께 감소율 → 색. 파랑(두꺼워짐·주름) ─ 초록(변화 없음) ─ 빨강(얇아짐·터짐)."""
    v = max(-1.0, min(1.0, x / THIN_LIMIT))
    if v >= 0:
        a, b = (70, 170, 90), (220, 50, 40)
    else:
        a, b, v = (70, 170, 90), (40, 90, 220), -v
    return QColor(*(int(a[i] + (b[i] - a[i]) * v) for i in range(3)))


def paint_legend(p: QPainter, rect: QRectF, theme: Theme):
    n = 40
    w = rect.width() / n
    for i in range(n):
        x = -THIN_LIMIT + 2 * THIN_LIMIT * (i + 0.5) / n
        p.fillRect(QRectF(rect.left() + i * w, rect.top(), w + 0.5, rect.height()), thinning_color(x))
    p.setPen(theme.text)
    f = QFont(p.font())
    p.setFont(f)
    y = rect.bottom() + p.fontMetrics().height()
    p.drawText(QPointF(rect.left(), y), f"두꺼워짐 {THIN_LIMIT:.0%}")
    txt = f"얇아짐 {THIN_LIMIT:.0%}"
    p.drawText(QPointF(rect.right() - p.fontMetrics().horizontalAdvance(txt), y), txt)
    mid = "0"
    p.drawText(QPointF(rect.center().x() - p.fontMetrics().horizontalAdvance(mid) / 2, y), mid)


# ---------------------------------------------------------------- 전개도

class FlatTransform:
    def __init__(self, scale, ox, oy):
        self.scale, self.ox, self.oy = scale, ox, oy

    def pt(self, p):
        return QPointF(self.ox + self.scale * p[0], self.oy - self.scale * p[1])

    @classmethod
    def fit(cls, result, rect: QRectF, margin=0.85):
        x0, y0, x1, y1 = result.bbox
        w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        s = margin * min(rect.width() / w, rect.height() / h)
        return cls(s, rect.center().x() - s * (x0 + x1) / 2, rect.center().y() + s * (y0 + y1) / 2)


def paint_flat(p: QPainter, result, tf: FlatTransform, theme: Theme, strain=True,
               labels=True, line_scale=1.0):
    p.setRenderHint(QPainter.Antialiasing)
    fi = result.forming
    if fi is not None and strain:
        th = fi.thinning
        # 이웃 삼각형 사이에 틈이 비치지 않게 같은 색 선으로 테두리를 함께 칠한다.
        for tri, x in zip(fi.F, th):
            poly = QPolygonF([tf.pt(fi.U[i]) for i in tri])
            col = thinning_color(float(x))
            p.setPen(QPen(col, 0.8 * line_scale))
            p.setBrush(col)
            p.drawPolygon(poly)
        p.setBrush(Qt.NoBrush)

    cut = QPen(theme.cut, 1.4 * line_scale)
    bend = QPen(theme.bend, 1.2 * line_scale, Qt.DashLine)
    for e in result.entities:
        p.setPen(bend if e.layer == "BEND" else cut)
        if isinstance(e, Line):
            p.drawLine(tf.pt(e.p1), tf.pt(e.p2))
        elif isinstance(e, Polyline):
            path = QPainterPath(tf.pt(e.points[0]))
            for q in e.points[1:]:
                path.lineTo(tf.pt(q))
            p.drawPath(path)
        elif isinstance(e, Arc):
            c = tf.pt(e.center)
            rr = e.radius * tf.scale
            rect = QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr)
            if e.full:
                p.drawEllipse(rect)
            else:
                span = (e.end_deg - e.start_deg) % 360
                p.drawArc(rect, int(e.start_deg * 16), int(span * 16))

    if labels:
        p.setPen(theme.note)
        for b in result.bends:
            m = tf.pt(((b.line[0][0] + b.line[1][0]) / 2, (b.line[0][1] + b.line[1][1]) / 2))
            p.drawText(m + QPointF(4, -4), f"B{b.number}")


def paint_dimensions(p: QPainter, result, tf: FlatTransform, theme: Theme):
    """전체 가로·세로 치수선."""
    x0, y0, x1, y1 = result.bbox
    w, h = x1 - x0, y1 - y0
    fm = p.fontMetrics()
    gap = fm.height() * 1.2
    p.setPen(QPen(theme.dim, 0.8))
    # 가로 (아래)
    a, b = tf.pt((x0, y0)), tf.pt((x1, y0))
    y = a.y() + gap
    p.drawLine(QPointF(a.x(), a.y() + 3), QPointF(a.x(), y + 3))
    p.drawLine(QPointF(b.x(), b.y() + 3), QPointF(b.x(), y + 3))
    _arrow_line(p, QPointF(a.x(), y), QPointF(b.x(), y))
    txt = f"{w:.2f}"
    p.drawText(QPointF((a.x() + b.x()) / 2 - fm.horizontalAdvance(txt) / 2, y - 3), txt)
    # 세로 (오른쪽)
    c, d = tf.pt((x1, y0)), tf.pt((x1, y1))
    x = c.x() + gap
    p.drawLine(QPointF(c.x() + 3, c.y()), QPointF(x + 3, c.y()))
    p.drawLine(QPointF(d.x() + 3, d.y()), QPointF(x + 3, d.y()))
    _arrow_line(p, QPointF(x, c.y()), QPointF(x, d.y()))
    txt = f"{h:.2f}"
    p.save()
    p.translate(x - 3, (c.y() + d.y()) / 2 + fm.horizontalAdvance(txt) / 2)
    p.rotate(-90)
    p.drawText(QPointF(0, 0), txt)
    p.restore()


def _arrow_line(p, a: QPointF, b: QPointF):
    p.drawLine(a, b)
    d = b - a
    L = math.hypot(d.x(), d.y())
    if L < 1e-6:
        return
    ux, uy = d.x() / L, d.y() / L
    s = 6
    for tip, sgn in ((a, 1), (b, -1)):
        for side in (1, -1):
            p.drawLine(tip, QPointF(tip.x() + sgn * s * ux - side * s * 0.35 * uy,
                                    tip.y() + sgn * s * uy + side * s * 0.35 * ux))


# ---------------------------------------------------------------- 3D 선 모델

def solid_polylines(solid, samples=24, iso=True):
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
            q = c.Value(a + (b - a) * i / n)
            pts.append((q.X(), q.Y(), q.Z()))
        out.append(np.array(pts))
    if iso:
        out += _iso_lines(solid)
    return out


def _iso_lines(solid, count=7, samples=40):
    """곡면에 등매개변수선을 몇 줄 그어 모양이 보이게 한다 (면 밖으로 나간 부분은 자른다)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    out = []
    exp = TopExp_Explorer(solid, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        exp.Next()
        surf = BRepAdaptor_Surface(face, True)
        if surf.GetType() in (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone):
            continue
        u0, u1 = surf.FirstUParameter(), surf.LastUParameter()
        v0, v1 = surf.FirstVParameter(), surf.LastVParameter()
        for direction in (0, 1):
            for i in range(1, count + 1):
                c = i / (count + 1)
                run = []
                for j in range(samples + 1):
                    s = j / samples
                    u = u0 + (u1 - u0) * (c if direction else s)
                    v = v0 + (v1 - v0) * (s if direction else c)
                    state = BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State()
                    if state in (TopAbs_IN, TopAbs_ON):
                        q = surf.Value(u, v)
                        run.append((q.X(), q.Y(), q.Z()))
                    else:
                        if len(run) > 1:
                            out.append(np.array(run))
                        run = []
                if len(run) > 1:
                    out.append(np.array(run))
    return out


def view_rotation(yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    # 화면 x = 오른쪽, 화면 y = 위, z 축이 위로 오게
    view = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
    return rx @ view @ rz


def paint_model(p: QPainter, lines, rect: QRectF, theme: Theme, yaw=math.radians(-35),
                pitch=math.radians(25), zoom=1.0, line_width=1.2):
    if not lines:
        return
    p.setRenderHint(QPainter.Antialiasing)
    allp = np.vstack(lines)
    lo, hi = allp.min(0), allp.max(0)
    center = (lo + hi) / 2
    R = view_rotation(yaw, pitch)
    proj = [(pts - center) @ R.T for pts in lines]
    q = np.vstack(proj)
    span = np.maximum(q.max(0) - q.min(0), 1e-9)
    s = 0.9 * min(rect.width() / span[0], rect.height() / span[1]) * zoom
    mid = (q.max(0) + q.min(0)) / 2
    cx, cy = rect.center().x() - s * mid[0], rect.center().y() + s * mid[1]
    p.setPen(QPen(theme.edge3d, line_width))
    for qq in proj:
        path = QPainterPath(QPointF(cx + s * qq[0, 0], cy - s * qq[0, 1]))
        for x, y, _z in qq[1:]:
            path.lineTo(cx + s * x, cy - s * y)
        p.drawPath(path)


# ---------------------------------------------------------------- 조립품 전체 + 번호 풍선

def assembly_polylines(solids, samples=10):
    """부품마다 선 목록. 곡면 등매개변수선은 빼서 부품이 많아도 빠르게."""
    return [solid_polylines(s, samples=samples, iso=False) for s in solids]


def paint_assembly(p: QPainter, parts, rect: QRectF, theme: Theme, highlight=None,
                   yaw=math.radians(-35), pitch=math.radians(25), zoom=1.0, pan=(0.0, 0.0),
                   balloons=True, font_px=None, line_width=1.0):
    """조립품 전체를 그리고 부품 번호 풍선을 붙인다.

    parts: assembly_polylines() 결과. highlight: 강조할 부품 번호(0부터).
    돌려주는 값: [(부품 번호, 풍선 중심 QPointF, 반지름)] — 눌러서 고를 때 쓴다.
    """
    p.setRenderHint(QPainter.Antialiasing)
    allp = [pts for lines in parts for pts in lines]
    if not allp:
        return []
    stack = np.vstack(allp)
    lo, hi = stack.min(0), stack.max(0)
    center = (lo + hi) / 2
    R = view_rotation(yaw, pitch)
    q = (stack - center) @ R.T
    span = np.maximum(q.max(0) - q.min(0), 1e-9)
    margin = 0.80 if balloons else 0.92
    s = margin * min(rect.width() / span[0], rect.height() / span[1]) * zoom
    mid = (q.max(0) + q.min(0)) / 2
    cx = rect.center().x() - s * mid[0] + pan[0]
    cy = rect.center().y() + s * mid[1] + pan[1]

    def scr(v):
        return cx + s * v[0], cy - s * v[1]

    dim = QColor(theme.edge3d)
    dim.setAlpha(110 if highlight is not None else 200)
    hot = QColor(255, 140, 0) if theme is DARK else QColor(220, 90, 0)
    anchors = []
    for idx, lines in enumerate(parts):
        is_hot = idx == highlight
        p.setPen(QPen(hot if is_hot else dim, line_width * (2.0 if is_hot else 1.0)))
        pts2 = []
        for pts in lines:
            qq = (pts - center) @ R.T
            path = QPainterPath(QPointF(*scr(qq[0])))
            for v in qq[1:]:
                path.lineTo(*scr(v))
            p.drawPath(path)
            pts2.append(qq[:, :2])
        if pts2:
            P = np.vstack(pts2)
            c = (P.min(0) + P.max(0)) / 2
            # 풍선 끈은 부품 위의 점에 붙인다 (ㄱ자 부품은 상자 가운데가 허공일 수 있다)
            a = P[np.argmin(np.linalg.norm(P - c, axis=1))]
            anchors.append((idx, np.array(scr(a))))

    if not balloons:
        return []
    fpx = font_px or max(9, min(14, int(rect.height() / 45)))
    f = QFont(p.font())
    f.setPixelSize(fpx)
    f.setBold(True)
    p.setFont(f)
    r = fpx * 0.95
    pos = _spread_balloons([a for _, a in anchors], r, rect)
    out = []
    for (idx, a), b in zip(anchors, pos):
        is_hot = idx == highlight
        col = hot if is_hot else theme.text
        p.setPen(QPen(col, 0.8))
        if np.linalg.norm(b - a) > r:
            d = (a - b) / np.linalg.norm(a - b)
            p.drawLine(QPointF(*(b + d * r)), QPointF(*a))
            p.drawEllipse(QPointF(*a), 1.5, 1.5)
        p.setBrush(QColor(255, 236, 200) if is_hot else theme.bg)
        p.drawEllipse(QPointF(*b), r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(150, 60, 0) if is_hot else col)
        txt = str(idx + 1)
        fm = p.fontMetrics()
        p.drawText(QPointF(b[0] - fm.horizontalAdvance(txt) / 2, b[1] + fm.ascent() / 2 - 1), txt)
        out.append((idx, QPointF(*b), r))
    return out


def _spread_balloons(anchors, r, rect: QRectF, iterations=80):
    """겹치는 풍선을 서로 밀어 낸다. 처음 자리는 부품 위(끈 없음)."""
    if not anchors:
        return []
    P = np.array(anchors, float).copy()
    A = P.copy()
    gap = 2.3 * r
    lo = np.array([rect.left() + r, rect.top() + r])
    hi = np.array([rect.right() - r, rect.bottom() - r])
    for _ in range(iterations):
        moved = False
        D = P[:, None, :] - P[None, :, :]
        dist = np.linalg.norm(D, axis=2) + np.eye(len(P)) * 1e9
        close = dist < gap
        if close.any():
            push = np.zeros_like(P)
            ii, jj = np.nonzero(close)
            for i, j in zip(ii, jj):
                d = D[i, j]
                n = np.linalg.norm(d)
                if n < 1e-6:
                    d, n = np.array([1.0, 0.3]) * (1 if i < j else -1), 1.0
                push[i] += d / n * (gap - dist[i, j]) * 0.5
            P += push
            moved = True
        # 원래 자리로 조금씩 당긴다 (끈이 너무 길어지지 않게)
        P += (A - P) * 0.02
        P = np.clip(P, lo, hi)
        if not moved:
            break
    return list(P)
