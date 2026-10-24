"""제작사 표기와 로고 (화면 아래, 도움말, PDF·엑셀 보고서).

로고: 회사 로고(HANIL_A_화이트.ai)를 PNG 로 바꿔 넣었다.
  hanil_unfold\\logo.png        흰 바탕용 (원본 모양 그대로 검은색)
  hanil_unfold\\logo_white.png  어두운 바탕용 (원본 흰색)
%APPDATA%\\HanilUnfold\\logo.png 가 있으면 그것을 먼저 쓴다 (로고를 바꿀 때).
파일이 하나도 없으면 간단한 표식(파란 네모에 H)을 그린다.
"""
from __future__ import annotations

import os

NAME = "한일특장(주)"
MAKER = f"제작사 : {NAME}"


def user_logo_path() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "HanilUnfold", "logo.png")


def logo_path(white=False) -> str:
    here = os.path.dirname(__file__)
    for p in (user_logo_path(), os.path.join(here, "logo_white.png" if white else "logo.png")):
        if os.path.exists(p):
            return p
    return ""


def logo_image(height_px: int = 64, white=False):
    """로고 QImage (높이 height_px, 투명 바탕). white=True 는 어두운 바탕용."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath

    path = logo_path(white)
    if path:
        img = QImage(path)
        if not img.isNull():
            return img.scaledToHeight(height_px, Qt.SmoothTransformation)
    h = height_px
    img = QImage(h, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    box = QPainterPath()
    box.addRoundedRect(QRectF(0.5, 0.5, h - 1, h - 1), h * 0.18, h * 0.18)
    p.fillPath(box, QColor(31, 78, 140))
    p.fillRect(QRectF(h * 0.18, h * 0.76, h * 0.64, h * 0.08), QColor(240, 140, 30))
    f = QFont()
    f.setFamilies(["Arial", "Malgun Gothic", "Sans Serif"])
    f.setBold(True)
    f.setPixelSize(int(h * 0.62))
    p.setFont(f)
    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(0, -h * 0.05, h, h * 0.86), Qt.AlignCenter, "H")
    p.end()
    return img


def paint_brand(p, rect, font, color=None, align_right=True):
    """rect 안에 [로고] 제작사 : 한일특장(주) 를 그리고, 쓴 너비를 돌려준다."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor

    h = rect.height()
    img = logo_image(max(16, int(h * 4)))       # 인쇄용으로 넉넉한 해상도
    lw = h * img.width() / max(img.height(), 1)
    p.save()
    p.setFont(font)
    p.setPen(color or QColor(40, 40, 40))
    tw = p.fontMetrics().horizontalAdvance(MAKER) + h * 0.4
    total = lw + tw
    x = rect.right() - total if align_right else rect.left()
    p.drawImage(QRectF(x, rect.top(), lw, h), img)
    p.drawText(QRectF(x + lw + h * 0.3, rect.top(), tw, h), Qt.AlignLeft | Qt.AlignVCenter, MAKER)
    p.restore()
    return total
