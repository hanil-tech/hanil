"""금형 간략도: 견적용 금형 그림 (평면도 + 정면 단면의 판 쌓기 + 표제란).

평면도 — 아래 다이를 위에서 본 모습: 다이 세트 외곽(길이 × 폭), 가이드 포스트 4 개,
  순차 금형이면 스트립과 공정(S1 …)마다 그 공정까지 만든 부품 모양 (접힌 플랜지는 줄여서),
  단발·복합·트랜스퍼는 블랭크 모양 (트랜스퍼는 공정 수만큼 나란히).
정면도 — 판 두께 쌓기 (아래부터): 아래 다이 세트 · 다이 받침판 · 다이 플레이트 · [열림 높이] ·
  스트리퍼 · 펀치 플레이트 · 펀치 받침판 · 위 다이 세트, 가이드 포스트, 생크.
치수는 견적용 어림 (costing.die_quote 의 크기). 금형 설계 후 확정한다.
"""
from __future__ import annotations

import numpy as np

# 정면도 판 쌓기 비율 (전체 두께 T 에 대한), 아래부터
STACK = [("아래 다이 세트", 0.26), ("다이 받침판", 0.06), ("다이 플레이트", 0.10), ("열림 높이", 0.15),
         ("스트리퍼", 0.08), ("펀치 플레이트", 0.08), ("펀치 받침판", 0.05), ("위 다이 세트", 0.22)]
POST_D = 38.0
POST_INSET = 55.0


def _font(p, px, bold=False):
    f = p.font()
    f.setPixelSize(max(int(px), 6))
    f.setBold(bold)
    p.setFont(f)


def paint_die(p, rect, dq, fp=14.0):
    """rect(QRectF) 안에 금형 간략도. dq: costing.DieQuote."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPen, QPolygonF

    L, W, T = dq.size
    lw = max(1.0, fp / 12)
    title_h = fp * 5.2
    body = QRectF(rect.left(), rect.top(), rect.width(), rect.height() - title_h - fp * 0.5)
    plan_r = QRectF(body.left(), body.top(), body.width() * 0.60, body.height())
    sec_r = QRectF(body.left() + body.width() * 0.63, body.top(), body.width() * 0.37, body.height())
    ink = QColor(30, 50, 90)

    # ---- 평면도
    _font(p, fp, True)
    p.setPen(QColor(20, 20, 20))
    p.drawText(QRectF(plan_r.left(), plan_r.top(), plan_r.width(), fp * 1.5), Qt.AlignLeft | Qt.AlignVCenter,
               "평면도 (아래 다이, 위에서 봄)")
    top = plan_r.top() + fp * 2.0
    avail_w, avail_h = plan_r.width() - fp * 4, plan_r.height() - fp * 6
    sc = min(avail_w / L, avail_h / W)
    ox = plan_r.left() + fp * 2 + (avail_w - L * sc) / 2
    oy = top + fp * 1.5 + (avail_h - W * sc) / 2 + W * sc       # 아래 왼쪽 = (0, 0)

    def pt(x, y):
        return QPointF(ox + x * sc, oy - y * sc)

    p.setPen(QPen(ink, lw * 1.6))
    p.setBrush(QColor(232, 235, 240))
    p.drawRect(QRectF(pt(0, W), pt(L, 0)))
    p.setBrush(QColor(255, 255, 255))
    for x, y in ((POST_INSET, POST_INSET), (L - POST_INSET, POST_INSET), (POST_INSET, W - POST_INSET),
                 (L - POST_INSET, W - POST_INSET)):
        p.drawEllipse(pt(x, y), POST_D / 2 * sc, POST_D / 2 * sc)
    mg = (L - (len(dq.plan.stations) * dq.plan.pitch if dq.plan is not None else 0)) / 2 if dq.plan else 0

    if dq.plan is not None:
        from .process import CUTOFF, fold_points
        pl = dq.plan
        x0, y0, x1, y1 = pl.bbox
        tab_x, tab_w, tab_len = pl.tab
        yc0 = y0 - tab_len - pl.carrier
        sw = pl.strip_width
        ys = (W - sw) / 2                                   # 다이 위 스트립 아래 끝
        p.setPen(QPen(QColor(120, 130, 150), lw, Qt.DashLine))
        p.setBrush(QColor(210, 222, 240, 120))
        p.drawRect(QRectF(QPointF(ox - fp, pt(0, ys + sw).y()), QPointF(pt(L, 0).x() + fp, pt(0, ys).y())))
        cx0 = (x0 + x1) / 2
        done = {}
        _font(p, fp * 0.8, True)
        for i, s in enumerate(pl.stations):
            for num, ang in s.bends:
                done[num] = ang
            cx = mg + (i + 0.5) * pl.pitch
            p.setPen(QPen(QColor(170, 170, 170), lw * 0.7, Qt.DashDotLine))
            p.drawLine(pt(cx, ys - 5), pt(cx, ys + sw + 5))
            p.setPen(QColor(20, 20, 20))
            q = pt(cx, ys + sw)
            p.drawText(QRectF(q.x() - pl.pitch * sc / 2, q.y() - fp * 1.4, pl.pitch * sc, fp * 1.3),
                       Qt.AlignCenter, f"S{s.no}")
            if s.kind == CUTOFF:
                continue
            O = fold_points(pl.outer, pl.folds, done)
            poly = QPolygonF([pt(cx + (a - cx0), ys + (b - yc0)) for a, b in O])
            p.setPen(QPen(ink, lw * 1.2))
            p.setBrush(QColor(190, 205, 232))
            p.drawPolygon(poly)
            made = {h for st_ in pl.stations[:i + 1] for h in st_.holes}
            p.setBrush(QColor(255, 255, 255))
            for k_, hh in enumerate(pl.holes):
                if k_ in made:
                    H_ = fold_points(hh, pl.folds, done)
                    p.drawPolygon(QPolygonF([pt(cx + (a - cx0), ys + (b - yc0)) for a, b in H_]))
            if s.holes or s.kind in ("노칭",) or s.bends:
                p.setPen(QPen(QColor(220, 50, 50), lw * 1.6))
                p.setBrush(Qt.NoBrush)
                p.drawRect(QRectF(pt(cx - pl.pitch * 0.45, ys + sw - 2), pt(cx + pl.pitch * 0.45, ys + 2)))
        p.setPen(QColor(200, 40, 40))
        _font(p, fp * 0.85)
        q = pt(L, ys + sw / 2)
        p.drawText(QRectF(q.x() + 2, q.y() - fp, fp * 4, fp * 2), Qt.AlignLeft | Qt.AlignVCenter, "이송 →")
    elif dq.outline is not None:
        O = np.asarray(dq.outline, float)
        mid = (O.min(0) + O.max(0)) / 2
        O = O - mid
        HS = [np.asarray(hh, float) - mid for hh in dq.holes]
        n = max(dq.stations, 1) if "트랜스퍼" in dq.die_type else 1
        step = L / n
        for i in range(n):
            c = np.array([step * (i + 0.5), W / 2])
            p.setPen(QPen(ink, lw * 1.2))
            p.setBrush(QColor(190, 205, 232))
            p.drawPolygon(QPolygonF([pt(*(c + v)) for v in O]))
            p.setBrush(QColor(255, 255, 255))
            for hh in HS:
                p.drawPolygon(QPolygonF([pt(*(c + v)) for v in hh]))
            if n > 1:
                _font(p, fp * 0.8, True)
                p.setPen(QColor(20, 20, 20))
                q = pt(c[0], W)
                p.drawText(QRectF(q.x() - step * sc / 2, q.y() + 2, step * sc, fp * 1.3), Qt.AlignCenter,
                           dq.ops[i] if i < len(dq.ops) else f"S{i + 1}")

    # 치수
    p.setPen(QPen(QColor(200, 40, 40), lw))
    _font(p, fp * 0.9)
    a, b = pt(0, 0), pt(L, 0)
    yy = a.y() + fp * 1.2
    p.drawLine(QPointF(a.x(), yy), QPointF(b.x(), yy))
    for x_ in (a.x(), b.x()):
        p.drawLine(QPointF(x_, yy - fp * 0.4), QPointF(x_, yy + fp * 0.4))
    p.drawText(QRectF(a.x(), yy, b.x() - a.x(), fp * 1.4), Qt.AlignCenter, f"{L:,.0f}")
    c0, c1 = pt(0, 0), pt(0, W)
    xx = c0.x() - fp * 1.2
    p.drawLine(QPointF(xx, c0.y()), QPointF(xx, c1.y()))
    p.save()
    p.translate(xx - fp * 0.3, (c0.y() + c1.y()) / 2)
    p.rotate(-90)
    p.drawText(QRectF(-fp * 4, -fp * 1.3, fp * 8, fp * 1.2), Qt.AlignCenter, f"{W:,.0f}")
    p.restore()

    # ---- 정면도 (판 쌓기)
    _font(p, fp, True)
    p.setPen(QColor(20, 20, 20))
    p.drawText(QRectF(sec_r.left(), sec_r.top(), sec_r.width(), fp * 1.5), Qt.AlignLeft | Qt.AlignVCenter,
               "정면도 (판 쌓기, 닫힌 높이)")
    label_w = fp * 9
    aw, ah = sec_r.width() - label_w - fp * 2, sec_r.height() - fp * 6
    s2 = min(aw / L, ah / (T * 1.12))
    sx0 = sec_r.left() + fp
    sy0 = sec_r.top() + fp * 2.5 + T * 1.12 * s2              # 바닥
    y = 0.0
    p.setPen(QPen(ink, lw))
    last_label = None                     # 얇은 판 글씨가 겹치지 않게 (아래부터 쌓으며 위로 밀기)
    for name, k in STACK:
        h = k * T
        r = QRectF(sx0, sy0 - (y + h) * s2, L * s2, h * s2)
        if name == "열림 높이":
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(150, 150, 150), lw, Qt.DashLine))
            # 펀치 (공정마다 하나)
            n = len(dq.plan.stations) if dq.plan is not None else max(dq.stations, 1)
            p.setPen(QPen(ink, lw))
            p.setBrush(QColor(150, 160, 175))
            pw = min(L / max(n, 1) * 0.35, 40)
            for i in range(n):
                cx = (i + 0.5) * L / n
                p.drawRect(QRectF(sx0 + (cx - pw / 2) * s2, sy0 - (y + h) * s2, pw * s2, h * 0.7 * s2))
            p.setPen(QPen(QColor(200, 60, 60), lw * 1.2))
            p.drawLine(QPointF(sx0 - fp * 0.5, sy0 - (y + h * 0.02) * s2),
                       QPointF(sx0 + L * s2 + fp * 0.5, sy0 - (y + h * 0.02) * s2))      # 스트립
            p.setPen(QPen(ink, lw))
        else:
            p.setBrush(QColor(205, 212, 225) if "세트" in name else QColor(225, 230, 238))
            p.drawRect(r)
        _font(p, fp * 0.72)
        p.setPen(QColor(40, 40, 40))
        cy = r.center().y()
        if last_label is not None and cy > last_label - fp * 0.95:
            cy = last_label - fp * 0.95
        last_label = cy
        p.drawText(QRectF(sx0 + L * s2 + fp * 0.6, cy - fp * 0.6, label_w, fp * 1.2),
                   Qt.AlignLeft | Qt.AlignVCenter, f"{name} {h:.0f}")
        p.setPen(QPen(ink, lw))
        y += h
    # 가이드 포스트 · 생크
    p.setBrush(QColor(255, 255, 255))
    for x in (POST_INSET, L - POST_INSET):
        p.drawRect(QRectF(sx0 + (x - POST_D / 2) * s2, sy0 - T * 0.93 * s2, POST_D * s2, T * 0.68 * s2))
    p.setBrush(QColor(205, 212, 225))
    p.drawRect(QRectF(sx0 + (L / 2 - 30) * s2, sy0 - (T + T * 0.1) * s2, 60 * s2, T * 0.1 * s2))
    _font(p, fp * 0.72)
    p.setPen(QColor(40, 40, 40))
    p.drawText(QRectF(sx0 + (L / 2 + 34) * s2, sy0 - (T * 1.1) * s2, label_w, T * 0.1 * s2),
               Qt.AlignLeft | Qt.AlignVCenter, "생크")
    p.setPen(QPen(QColor(200, 40, 40), lw))
    _font(p, fp * 0.85)
    xx = sx0 - fp * 0.6
    p.drawLine(QPointF(xx, sy0), QPointF(xx, sy0 - T * s2))
    p.save()
    p.translate(xx - fp * 0.2, sy0 - T * s2 / 2)
    p.rotate(-90)
    p.drawText(QRectF(-fp * 5, -fp * 1.3, fp * 10, fp * 1.2), Qt.AlignCenter, f"닫힌 높이 {T:,.0f}")
    p.restore()

    # ---- 표제란
    tr = QRectF(rect.left(), rect.bottom() - title_h, rect.width(), title_h)
    p.setPen(QPen(QColor(60, 60, 60), lw))
    p.setBrush(QColor(246, 248, 252))
    p.drawRect(tr)
    cells = [("부품", f"{dq.part_no}. {dq.part_name}"), ("금형 형식", dq.die_type),
             ("크기 (길이×폭×닫힌 높이)", f"{L:,.0f} × {W:,.0f} × {T:,.0f} mm"),
             ("공정", f"{dq.stations} 공정" + (f" × {dq.sets} 벌" if dq.sets > 1 else "")),
             ("필요 프레스", f"{dq.press_tonf:,.0f} tf 이상" if dq.press_tonf else "-"),
             ("무게 어림", f"다이 세트 {dq.steel_kg:,.0f} kg · 인서트 {dq.insert_kg:,.0f} kg"),
             ("금형비 (VAT 별도)", f"{dq.cost:,.0f} 원"), ("비고", "견적용 간략도 — 금형 설계 후 확정")]
    cols = 4
    cw = tr.width() / cols
    ch = title_h / 2
    for i, (k, v) in enumerate(cells):
        r = QRectF(tr.left() + (i % cols) * cw, tr.top() + (i // cols) * ch, cw, ch)
        p.setPen(QPen(QColor(180, 180, 180), lw * 0.6))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        _font(p, fp * 0.7)
        p.setPen(QColor(100, 100, 100))
        p.drawText(r.adjusted(fp * 0.4, fp * 0.15, 0, 0), Qt.AlignLeft | Qt.AlignTop, k)
        _font(p, fp * 0.88, True)
        p.setPen(QColor(20, 20, 20))
        p.drawText(r.adjusted(fp * 0.4, 0, -fp * 0.3, -fp * 0.2), Qt.AlignLeft | Qt.AlignBottom, v)


def render(dq, w=1600, h=1000):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from .report import ensure_gui
    ensure_gui()
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint_die(p, QRectF(16, 12, w - 32, h - 24), dq, 18.0)
    p.end()
    return img
