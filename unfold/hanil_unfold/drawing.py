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


def paint_dimensions(p: QPainter, result, tf: FlatTransform, theme: Theme, dims=None,
                     line_width=0.8, chains_on=True, holes_on=True):
    """치수선: 절곡선까지 연속 치수(안쪽), 전체 길이(바깥쪽), 구멍 번호·지름.

    dims 가 없으면 전체 가로·세로만 그린다. chains_on=False 면 연속 치수를 빼고 전체 크기만,
    holes_on=False 면 구멍 번호·지름을 뺀다.
    """
    x0, y0, x1, y1 = result.bbox
    w, h = x1 - x0, y1 - y0
    fm = p.fontMetrics()
    gap = fm.height() * 1.3
    p.setPen(QPen(theme.dim, line_width))
    chains = {c.axis: c for c in (dims.chains if dims and chains_on else [])}

    # 가로 (아래): 연속 치수가 있으면 안쪽 줄, 전체는 바깥 줄
    level = 1
    if "x" in chains:
        c = chains["x"]
        for a_, b_ in zip(c.positions[:-1], c.positions[1:]):
            _hdim(p, tf.pt((x0 + a_, y0)), tf.pt((x0 + b_, y0)), gap * level, f"{b_ - a_:.2f}", fm)
        level += 1
    _hdim(p, tf.pt((x0, y0)), tf.pt((x1, y0)), gap * level, f"{w:.2f}", fm)

    # 세로 (오른쪽)
    level = 1
    if "y" in chains:
        c = chains["y"]
        for a_, b_ in zip(c.positions[:-1], c.positions[1:]):
            _vdim(p, tf.pt((x1, y0 + a_)), tf.pt((x1, y0 + b_)), gap * level, f"{b_ - a_:.2f}", fm)
        level += 1
    _vdim(p, tf.pt((x1, y0)), tf.pt((x1, y1)), gap * level, f"{h:.2f}", fm)

    # 구멍 번호와 지름
    if dims and holes_on:
        for hole in dims.holes:
            c = tf.pt((x0 + hole.center[0], y0 + hole.center[1]))
            txt = f"{hole.label} Ø{hole.diameter:.1f}" if hole.diameter else \
                f"{hole.label} {hole.size[0]:.1f}×{hole.size[1]:.1f}"
            r = (hole.diameter / 2 if hole.diameter else max(hole.size) / 2) * tf.scale
            p.drawText(QPointF(c.x() + r * 0.75 + 2, c.y() - r * 0.75 - 2), txt)


def _hdim(p, a: QPointF, b: QPointF, off, txt, fm):
    if abs(b.x() - a.x()) < 1:
        return
    y = max(a.y(), b.y()) + off
    p.drawLine(QPointF(a.x(), a.y() + 3), QPointF(a.x(), y + 3))
    p.drawLine(QPointF(b.x(), b.y() + 3), QPointF(b.x(), y + 3))
    _arrow_line(p, QPointF(a.x(), y), QPointF(b.x(), y), fm.height() * 0.35)
    tw = fm.horizontalAdvance(txt)
    if tw > abs(b.x() - a.x()) - 4:          # 좁으면 글씨를 조금 위로 비켜 쓴다
        p.drawText(QPointF((a.x() + b.x()) / 2 - tw / 2, y - fm.height() * 0.9), txt)
    else:
        p.drawText(QPointF((a.x() + b.x()) / 2 - tw / 2, y - 3), txt)


def _vdim(p, a: QPointF, b: QPointF, off, txt, fm):
    if abs(b.y() - a.y()) < 1:
        return
    x = max(a.x(), b.x()) + off
    p.drawLine(QPointF(a.x() + 3, a.y()), QPointF(x + 3, a.y()))
    p.drawLine(QPointF(b.x() + 3, b.y()), QPointF(x + 3, b.y()))
    _arrow_line(p, QPointF(x, a.y()), QPointF(x, b.y()), fm.height() * 0.35)
    p.save()
    p.translate(x - 3, (a.y() + b.y()) / 2 + fm.horizontalAdvance(txt) / 2)
    p.rotate(-90)
    p.drawText(QPointF(0, 0), txt)
    p.restore()


def paint_summary(p: QPainter, lines, x, y, theme: Theme):
    """전개도 구석의 요약 상자 (두께·크기·면적·무게·절단 길이)."""
    fm = p.fontMetrics()
    w = max(fm.horizontalAdvance(t) for t in lines) + 16
    h = fm.height() * len(lines) + 10
    bg = QColor(theme.bg)
    bg.setAlpha(225)
    p.setPen(QPen(theme.dim, 0.8))
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
    p.setBrush(Qt.NoBrush)
    p.setPen(theme.text)
    for i, t in enumerate(lines):
        p.drawText(QPointF(x + 8, y + 5 + fm.ascent() + i * fm.height()), t)
    return QRectF(x, y, w, h)


def _arrow_line(p, a: QPointF, b: QPointF, s=6.0):
    p.drawLine(a, b)
    d = b - a
    L = math.hypot(d.x(), d.y())
    if L < 1e-6:
        return
    ux, uy = d.x() / L, d.y() / L
    s = min(s, L / 3)
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


def _iso_lines(solid, count=7, samples=40, max_faces=25):
    """곡면에 등매개변수선을 몇 줄 그어 모양이 보이게 한다 (면 밖으로 나간 부분은 자른다)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    # 곡면이 많으면 느려지므로 넓은 곡면 몇 개에만 긋는다
    faces = []
    exp = TopExp_Explorer(solid, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        exp.Next()
        if BRepAdaptor_Surface(face, True).GetType() in (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone):
            continue
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, g)
        faces.append((g.Mass(), face))
    faces.sort(key=lambda t: -t[0])
    count, samples = min(count, 5), min(samples, 24)
    out = []
    for _, face in faces[:max_faces]:
        surf = BRepAdaptor_Surface(face, True)
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


def _spread_balloons(anchors, r, rect: QRectF, iterations=150):
    """겹치는 풍선을 서로 밀어 낸다. 처음 자리는 부품 위(끈 없음).

    numpy 로 한꺼번에 계산한다 (풍선이 수백 개여도 빠르게)."""
    if not anchors:
        return []
    P = np.array(anchors, float).copy()
    A = P.copy()
    n = len(P)
    gap = 2.3 * r
    lo = np.array([rect.left() + r, rect.top() + r])
    hi = np.array([rect.right() - r, rect.bottom() - r])
    # 같은 자리에 겹친 풍선은 조금씩 다른 방향으로 흩어 둔다
    ang = np.arange(n) * 2.399963
    P += np.c_[np.cos(ang), np.sin(ang)] * 1e-3 * r
    eye = np.eye(n, dtype=bool)
    for _ in range(iterations):
        D = P[:, None, :] - P[None, :, :]
        dist = np.linalg.norm(D, axis=2)
        close = (dist < gap) & ~eye
        if not close.any():
            break
        safe = np.where(dist < 1e-9, 1.0, dist)
        push = np.where(close[..., None], D / safe[..., None] * (gap - dist)[..., None] * 0.5, 0.0)
        P += push.sum(axis=1)
        P += (A - P) * 0.02          # 원래 자리로 조금씩 (끈이 너무 길어지지 않게)
        P = np.clip(P, lo, hi)
    return list(P)


# ---------------------------------------------------------------- 철판 배치

_PART_COLORS = [QColor(c) for c in ("#5b8ff9", "#5ad8a6", "#f6bd16", "#e8684a", "#6dc8ec", "#9270ca",
                                    "#ff9d4d", "#269a99", "#ff99c3", "#a0b04a")]


class _Flat:
    """paint_flat 에 넘길 도형 묶음 (절곡 글씨·두께 지도 없이)."""

    def __init__(self, entities):
        self.entities, self.bends, self.forming = entities, [], None


def sheet_shapes(nest_result, sheet):
    """철판 한 장의 부품마다 (부품 번호, 도형, 윤곽들, 중심) — 그릴 때 한 번만 계산해 둔다."""
    from .metrics import loops
    out = []
    for pl in sheet.placements:
        ents = pl.entities(nest_result.parts)
        # 외곽이 끊긴 부품은 색칠하지 않는다 (구멍만 칠해지므로)
        lps = loops(ents) if nest_result.parts[pl.part].outer is not None else []
        out.append((pl.part, ents, lps, pl.center(nest_result.parts)))
    return out


def paint_sheet(p: QPainter, nest_result, sheet, rect: QRectF, theme: Theme, shapes=None,
                line_scale=1.0, font_px=None):
    """철판 한 장: 테두리, 여유선, 부품(색칠·번호). 철판 왼쪽 아래가 (0, 0)."""
    p.setRenderHint(QPainter.Antialiasing)
    W, H = sheet.width, sheet.height
    s = 0.96 * min(rect.width() / W, rect.height() / H)
    tf = FlatTransform(s, rect.center().x() - s * W / 2, rect.center().y() + s * H / 2)
    sheet_poly = QPolygonF([tf.pt(q) for q in ((0, 0), (W, 0), (W, H), (0, H))])
    p.setPen(QPen(QColor(200, 60, 60), 1.6 * line_scale))
    p.setBrush(QColor(60, 64, 72) if theme is DARK else QColor(245, 245, 245))
    p.drawPolygon(sheet_poly)
    m = nest_result.margin
    if m > 0:
        p.setPen(QPen(QColor(200, 60, 60, 120), 0.8 * line_scale, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF([tf.pt(q) for q in ((m, m), (W - m, m), (W - m, H - m), (m, H - m))]))
    shapes = shapes if shapes is not None else sheet_shapes(nest_result, sheet)
    for part, ents, lps, _ in shapes:
        col = QColor(_PART_COLORS[part % len(_PART_COLORS)])
        col.setAlpha(110 if theme is DARK else 70)
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for lp in lps:
            path.addPolygon(QPolygonF([tf.pt(q) for q in lp]))
            path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        paint_flat(p, _Flat(ents), tf, theme, strain=False, labels=False, line_scale=line_scale * 0.7)
    f = QFont(p.font())
    f.setPixelSize(int(font_px or max(9, min(16, s * 40))))
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    p.setPen(theme.text if theme is DARK else QColor(20, 20, 20))
    for part, _, _, c in shapes:
        txt = nest_result.parts[part].label
        q = tf.pt(c)
        p.drawText(QPointF(q.x() - fm.horizontalAdvance(txt) / 2, q.y() + fm.ascent() / 2 - 1), txt)
    return tf


# ---------------------------------------------------------------- 사용자가 찍은 치수

def snap_points(result):
    """전개도에서 치수를 찍을 때 붙을 점들 (끝점·가운데·원 중심·사분점, 바깥 상자 네 귀퉁이) → numpy (n, 2).

    모서리가 둥근 판도 바깥 상자 귀퉁이에 붙으면 전체 크기를 바로 잴 수 있다."""
    x0, y0, x1, y1 = result.bbox
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for e in result.entities:
        if isinstance(e, Line):
            pts += [e.p1, e.p2, ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)]
        elif isinstance(e, Polyline):
            q = e.points
            step = max(1, len(q) // 40)
            pts += list(q[::step]) + [q[-1]]
        elif isinstance(e, Arc):
            cx, cy = e.center
            pts.append(e.center)
            if e.full:
                pts += [(cx + e.radius, cy), (cx - e.radius, cy), (cx, cy + e.radius), (cx, cy - e.radius)]
            else:
                for a in (e.start_deg, e.end_deg, (e.start_deg + ((e.end_deg - e.start_deg) % 360) / 2)):
                    pts.append((cx + e.radius * math.cos(math.radians(a)), cy + e.radius * math.sin(math.radians(a))))
    return np.array(pts, float) if pts else np.zeros((0, 2))


def dim_text(p1, p2):
    dx, dy = abs(p2[0] - p1[0]), abs(p2[1] - p1[1])
    L = math.hypot(dx, dy)
    if dx < 1e-6 or dy < 1e-6:
        return f"{L:.2f}"
    return f"{L:.2f}  (X {dx:.2f} · Y {dy:.2f})"


def paint_user_dims(p: QPainter, dims, tf: FlatTransform, theme: Theme, preview=None, line_width=1.2,
                    color=None, hot=None):
    """찍은 치수: 두 점 사이 화살표 선 + 길이 글씨 (글씨는 바탕을 칠해 잘 보이게). hot: 강조할 번호."""
    base_col = color or QColor(255, 120, 200)
    items = list(dims) + ([preview] if preview else [])
    fm = p.fontMetrics()
    for k, (a, b) in enumerate(items):
        A, B = tf.pt(a), tf.pt(b)
        is_prev = preview is not None and k == len(items) - 1
        col = QColor(255, 220, 60) if k == hot else base_col
        pen = QPen(col, line_width * (2 if k == hot else 1), Qt.DashLine if is_prev else Qt.SolidLine)
        p.setPen(pen)
        _arrow_line(p, A, B, 7 * line_width)          # 선 + 양 끝 화살표
        for c in (A, B):
            p.drawEllipse(c, 2.5, 2.5)
        txt = dim_text(a, b) + ("   [Delete 지우기]" if k == hot else "")
        m = QPointF((A.x() + B.x()) / 2, (A.y() + B.y()) / 2)
        w, h = fm.horizontalAdvance(txt) + 8, fm.height() + 2
        box = QRectF(m.x() - w / 2, m.y() - h - 4, w, h)
        p.fillRect(box, QColor(30, 30, 30, 200) if theme is DARK else QColor(255, 255, 255, 220))
        p.drawText(box, Qt.AlignCenter, txt)
