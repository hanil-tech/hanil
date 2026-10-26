"""성형 과정 3D 그림: 블랭크 (평판) 가 펀치 깊이에 따라 제품이 되는 모습과, 어느 행정에서 어디가 먼저 터지고
어디가 먼저 주름지는지.

원스텝 해석이 주는 것은 처음 (블랭크) 과 끝 (제품) 뿐이라, 가운데는 다음 두 가정으로 그린다.
  · 변형 — 비례 변형 경로: 행정 s (0~1) 에서 ε(s) = s · ε(끝) (원스텝 역해석이 깔고 있는 가정). 파단·위험·주름은
    그 변형으로 성형성 존을 다시 매겨, 삼각형마다 처음 FLC 에 닿는 s (터지기 시작), 한계 80 % 에 닿는 s,
    압축으로 5 % 두꺼워지는 s (주름 시작) 를 구한다.
  · 모양 — 블랭크를 제품 위 (누르개 높이) 에 맞춰 놓고 (2D 정렬: Kabsch), 펀치가 s × 깊이만큼 내려가며 그보다 깊은
    곳은 펀치 높이로, 이미 닿은 곳은 제품 높이로; 평면 위치는 블랭크에서 제품으로 s 만큼 옮긴다.
실제 금형 접촉 순서·다단 공정을 계산한 것이 아니다 — 어디가 먼저 한계에 가까워지는지 보는 그림.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import formsim as fs

STEPS = 100


@dataclass
class Onset:
    kind: str              # "crack" / "risk" / "wrinkle"
    s: float               # 행정 비 (0~1)
    tri: int
    point: tuple           # 제품 (끝) 위 점
    depth: float           # 그때 펀치 깊이 mm
    region: str = ""

    @property
    def label(self):
        return {"crack": "터지기 시작", "risk": "파단 위험 시작", "wrinkle": "주름 시작"}[self.kind]


@dataclass
class Process:
    fa: object
    frame: tuple           # (xx, yy, zz) — zz 위 (열린 쪽)
    U3: np.ndarray         # 블랭크 꼭짓점을 제품 좌표계에 놓은 것 (n, 3)
    Vf: np.ndarray         # 제품 꼭짓점 (n, 3)
    hmax: float
    depth: float
    s_crack: np.ndarray    # 삼각형마다 FLC 에 닿는 행정 비 (닿지 않으면 inf)
    s_risk: np.ndarray
    s_wrinkle: np.ndarray
    onsets: list = field(default_factory=list)


def _frame(fi):
    z0, _ = fs.press_direction(fi.V, fi.F)
    if z0 is None:                                   # 뚜렷한 프레스 방향이 없으면 가장 납작한 방향
        P = fi.V - fi.V.mean(0)
        _, _, vt = np.linalg.svd(P[:: max(1, len(P) // 4000)], full_matrices=False)
        zz = vt[2]
    else:
        zz = -z0
    xx = np.cross([0, 1.0, 0] if abs(zz[1]) < 0.9 else [1.0, 0, 0], zz)
    xx /= np.linalg.norm(xx)
    return xx, np.cross(zz, xx), zz


def _kabsch2(A, B):
    """A (n,2) 를 B 에 가장 잘 맞추는 회전 (뒤집기 허용) + 이동 → 맞춘 A, 잔차."""
    best = None
    for flip in (1.0, -1.0):
        A2 = A * np.array([1.0, flip])
        ca, cb = A2.mean(0), B.mean(0)
        H = (A2 - ca).T @ (B - cb)
        U, _, Vt = np.linalg.svd(H)
        R = (U @ Vt).T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = (U @ Vt).T
        out = (A2 - ca) @ R.T + cb
        res = float(np.mean(np.sum((out - B) ** 2, axis=1)))
        if best is None or res < best[1]:
            best = (out, res)
    return best


def build(fa) -> Process | None:
    fi = fa.fi
    if fi is None or fi.V is None or not fa.fields:
        return None
    xx, yy, zz = _frame(fi)
    V = fi.V
    P = np.column_stack([V @ xx, V @ yy])
    h = V @ zz
    hmax, hmin = float(h.max()), float(h.min())
    Ua, _ = _kabsch2(np.asarray(fi.U, float), P)
    U3 = np.outer(Ua[:, 0], xx) + np.outer(Ua[:, 1], yy) + hmax * zz
    e1, e2, th, rk = fa.fields
    S = np.linspace(1.0 / STEPS, 1.0, STEPS)
    from .forming import flc_risk
    mat = getattr(fi, "material", None)
    m = len(e1)
    s_crack = np.full(m, np.inf)
    s_risk = np.full(m, np.inf)
    s_wr = np.full(m, np.inf)
    for s in S[::-1]:                                 # 거꾸로 돌며 덮어쓰면 가장 작은 s 가 남음
        if fi.flc0 > 0:
            r = flc_risk(s * e1, s * e2, fi.flc0, mat)
            s_crack = np.where(r >= 1.0, s, s_crack)
            s_risk = np.where(r >= 1 - fs.MARGIN, s, s_risk)
        thick = -s * (e1 + e2)
        s_wr = np.where((thick > 0.05) & (e2 < 0), s, s_wr)
    pr = Process(fa, (xx, yy, zz), U3, V.copy(), hmax, hmax - hmin, s_crack, s_risk, s_wr)
    pr.onsets = _onsets(pr)
    return pr


def _onsets(pr):
    fa = pr.fa
    fi = fa.fi
    centers = fi.V[fi.F].mean(1)
    w = fi._weights()
    try:
        from .formexplain import REGION_NAMES, regions
        kind, corner, edge = regions(fa)
    except Exception:
        kind = corner = edge = None
    out = []
    for k, arr in (("crack", pr.s_crack), ("risk", pr.s_risk), ("wrinkle", pr.s_wrinkle)):
        ok = np.isfinite(arr) & (w > 0)
        if not ok.any():
            continue
        s0 = float(arr[ok].min())
        cand = np.nonzero(ok & (arr <= s0 + 1e-9))[0]
        # 같은 행정에 여럿이면 그때 가장 심한 (한계 비 / 두꺼워짐 큰) 곳
        e1, e2, th, rk = fa.fields
        key = rk[cand] if k != "wrinkle" else -th[cand]
        ti = int(cand[int(np.argmax(key))])
        reg = ""
        if kind is not None:
            reg = ("귀 (모서리) " if corner[ti] else "") + REGION_NAMES[kind[ti]] + (" · 잘린 가장자리" if edge[ti] else "")
        out.append(Onset(k, s0, ti, tuple(float(x) for x in centers[ti]), s0 * pr.depth, reg))
    return out


def stage_vertices(pr: Process, s):
    s = min(max(float(s), 0.0), 1.0)
    xx, yy, zz = pr.frame
    Vf, U3 = pr.Vf, pr.U3
    pf = np.column_stack([Vf @ xx, Vf @ yy])
    pu = np.column_stack([U3 @ xx, U3 @ yy])
    pin = (1 - s) * pu + s * pf
    h = np.maximum(Vf @ zz, pr.hmax - s * pr.depth)
    return np.outer(pin[:, 0], xx) + np.outer(pin[:, 1], yy) + np.outer(h, zz)


def stage_zones(pr: Process, s):
    from .forming import flc_risk
    fa = pr.fa
    fi = fa.fi
    e1, e2, _, _ = fa.fields
    e1s, e2s = s * e1, s * e2
    th = 1 - np.exp(-(e1s + e2s))
    rk = flc_risk(e1s, e2s, fi.flc0, getattr(fi, "material", None)) if fi.flc0 > 0 else np.zeros(len(e1))
    return fs.zones(fi, (e1s, e2s, th, rk)), th


def summary(pr: Process):
    """[글] — 언제 (행정 %, 펀치 깊이) · 어디서."""
    out = []
    names = {o.kind: o for o in pr.onsets}
    for k in ("crack", "risk", "wrinkle"):
        o = names.get(k)
        if o is None:
            out.append({"crack": "끝까지 터지지 않음 (FLC 안)", "risk": "끝까지 파단 위험 (한계 80 %) 에 닿지 않음",
                        "wrinkle": "5 % 넘게 두꺼워지는 곳 없음 (주름 경향 낮음)"}[k])
        else:
            out.append(f"{o.label}: 행정 {o.s:.0%} (펀치 깊이 {o.depth:.0f} / {pr.depth:.0f} mm) — {o.region} "
                       f"(X {o.point[0]:.0f}, Y {o.point[1]:.0f}, Z {o.point[2]:.0f})")
    return out


# ---------------------------------------------------------------- 그리기

def _view(W, az, el):
    a, e = math.radians(az), -math.radians(el)
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]])
    W = W @ Rz.T
    W = np.column_stack([W[:, 0], W[:, 2], -W[:, 1]]) @ Rx.T
    W[:, 2] *= -1
    return W


def paint_stage(p, rect, pr: Process, s, az=-35.0, el=30.0, title=True):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    from .report import _font
    fa = pr.fa
    F = fa.fi.F
    xx, yy, zz = pr.frame
    M = np.column_stack([xx, yy, zz])
    c0 = pr.Vf.mean(0)
    Vs = stage_vertices(pr, s)
    W = _view((Vs - c0) @ M, az, el)
    # 크기: 처음·끝을 함께 넣어 움직여도 크기가 그대로
    both = np.vstack([_view((pr.U3 - c0) @ M, az, el)[:, :2], _view((pr.Vf - c0) @ M, az, el)[:, :2]])
    lo, hi = both.min(0), both.max(0)
    top = rect.top() + (30 if title else 6)
    legend_h = 52 if title else 0
    area = QRectF(rect.left() + 10, top, rect.width() - 20, rect.bottom() - top - legend_h - 6)
    sc = min(area.width() / max(hi[0] - lo[0], 1e-9), area.height() / max(hi[1] - lo[1], 1e-9)) * 0.94
    cx, cy = area.center().x(), area.center().y()
    mid = (lo + hi) / 2
    X = cx + (W[:, 0] - mid[0]) * sc
    Y = cy - (W[:, 1] - mid[1]) * sc
    z, _ = stage_zones(pr, s)
    pal = np.array([zn[1] for zn in fs.ZONES], float)
    cols = pal[z]
    nrm = np.cross(W[F[:, 1]] - W[F[:, 0]], W[F[:, 2]] - W[F[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    shade = 0.45 + 0.55 * np.abs(nrm @ np.array([0.3, 0.5, 0.81]))
    order = np.argsort(W[F].mean(1)[:, 2])
    p.save()
    p.fillRect(rect, QColor(255, 255, 255))
    for i in order:
        c = cols[i] * shade[i]
        q = QColor(int(min(c[0], 255)), int(min(c[1], 255)), int(min(c[2], 255)))
        p.setBrush(q)
        p.setPen(QPen(q, 0.6))
        tri = F[i]
        p.drawPolygon(QPolygonF([QPointF(X[tri[0]], Y[tri[0]]), QPointF(X[tri[1]], Y[tri[1]]),
                                 QPointF(X[tri[2]], Y[tri[2]])]))
    # 시작 자리 표시 (그 행정을 지났으면)
    p.setFont(_font(9, True))
    for o in pr.onsets:
        if o.kind == "risk" or s + 1e-9 < o.s:
            continue
        tri = F[o.tri]
        px, py = float(X[tri].mean()), float(Y[tri].mean())
        col = QColor(220, 30, 30) if o.kind == "crack" else QColor(140, 70, 200)
        p.setPen(QPen(col, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(px, py), 14, 14)
        txt = f"{o.label} ({o.s:.0%})"
        p.setPen(QColor(255, 255, 255))
        fm_w = 8 * len(txt) + 10
        p.fillRect(QRectF(px + 16, py - 22, fm_w, 20), col)
        p.drawText(QRectF(px + 16, py - 22, fm_w, 20), Qt.AlignCenter, txt)
    if title:
        p.setPen(QColor(30, 30, 30))
        p.setFont(_font(12, True))
        p.drawText(QRectF(rect.left(), rect.top() + 4, rect.width(), 24), Qt.AlignCenter,
                   f"성형 과정 — 행정 {s:.0%} (펀치 깊이 {s * pr.depth:.0f} / {pr.depth:.0f} mm)")
        p.setFont(_font(9))
        n = len(fs.ZONES)
        bw = min(150.0, (rect.width() - 20) / 4)
        for k, zn in enumerate(fs.ZONES):
            col_, row_ = k % 4, k // 4
            xb = rect.left() + (rect.width() - bw * 4) / 2 + col_ * bw
            yb = rect.bottom() - legend_h + 22 * row_
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*zn[1]))
            p.drawRect(QRectF(xb + 2, yb + 4, 14, 14))
            p.setPen(QColor(40, 40, 40))
            p.drawText(QRectF(xb + 20, yb, bw - 22, 22), Qt.AlignLeft | Qt.AlignVCenter, zn[3])
        del n
    p.restore()


def render_stage(pr: Process, s, w=900, h=680, az=-35.0, el=30.0):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint_stage(p, QRectF(0, 0, w, h), pr, s, az, el)
    p.end()
    return img


def save_gif(pr: Process, path, frames=30, w=640, h=480, az=-35.0, el=30.0, ms=120):
    """움직이는 그림 (GIF): 행정 0 → 100 %, 끝에서 잠깐 멈춤."""
    from PIL import Image
    imgs = []
    for k in range(frames + 1):
        q = render_stage(pr, k / frames, w, h, az, el)
        buf = q.bits().tobytes() if hasattr(q.bits(), "tobytes") else bytes(q.constBits())
        im = Image.frombuffer("RGBA", (q.width(), q.height()), buf, "raw", "BGRA", q.bytesPerLine(), 1)
        imgs.append(im.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=128))
    imgs += [imgs[-1]] * 8
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=ms, loop=0, optimize=False)
    return path
