"""보통 공차 (도면에 공차가 없는 치수): 일본 JIS B 0408 (금속 프레스 가공품) · 유럽 ISO 2768-1 (DIN ISO 2768).

JIS B 0408:1991 — 표 1 打抜き (펀칭·블랭킹 치수), 표 2 曲げ・絞り (굽힘·드로잉 치수), 등급 A · B · C.
  打抜き A·B·C 는 JIS B 0405 (= ISO 2768-1) 의 f·m·c, 曲げ・絞り 는 m·c·v 에 해당.
  도면에 따로 정하지 않으면 B 급을 흔히 쓴다.
ISO 2768-1 — 길이 치수 f (정밀) · m (중간) · c (거침) · v (아주 거침).
"""
from __future__ import annotations

# (구간 위 끝 mm, (A, B, C) ±mm)
JIS_PUNCH = [(6, (0.05, 0.1, 0.3)), (30, (0.1, 0.2, 0.5)), (120, (0.15, 0.3, 0.8)), (400, (0.2, 0.5, 1.2)),
             (1000, (0.3, 0.8, 2.0)), (2000, (0.5, 1.2, 3.0))]
JIS_BEND = [(6, (0.1, 0.3, 0.5)), (30, (0.2, 0.5, 1.0)), (120, (0.3, 0.8, 1.5)), (400, (0.5, 1.2, 2.5)),
            (1000, (0.8, 2.0, 4.0)), (2000, (1.2, 3.0, 6.0))]
# ISO 2768-1 (f, m, c, v); 0.5~3 구간의 v 는 규정 없음 (None)
ISO_2768 = [(3, (0.05, 0.1, 0.2, None)), (6, (0.05, 0.1, 0.3, 0.5)), (30, (0.1, 0.2, 0.5, 1.0)),
            (120, (0.15, 0.3, 0.8, 1.5)), (400, (0.2, 0.5, 1.2, 2.5)), (1000, (0.3, 0.8, 2.0, 4.0)),
            (2000, (0.5, 1.2, 3.0, 6.0)), (4000, (None, 2.0, 4.0, 8.0))]
JIS_CLASSES = "ABC"
ISO_CLASSES = "fmcv"


def _look(table, size, idx):
    for top, vals in table:
        if size <= top:
            return vals[idx]
    return table[-1][1][idx]


def jis(size, kind="punch", cls="B"):
    """JIS B 0408 보통 공차 ±mm. kind = 'punch' (打抜き) / 'bend' (曲げ・絞り)."""
    return _look(JIS_BEND if kind == "bend" else JIS_PUNCH, abs(size), JIS_CLASSES.index(cls))


def iso(size, cls="m"):
    """ISO 2768-1 보통 공차 ±mm (없으면 None)."""
    return _look(ISO_2768, abs(size), ISO_CLASSES.index(cls))


def text(size, kind="punch", cls="B"):
    """'±0.5 (JIS B 0408-B) · ±0.5 (ISO 2768-m)'"""
    j = jis(size, kind, cls)
    i = iso(size, "m" if kind == "punch" else "c")
    return f"±{j:g} (JIS B 0408-{cls}) · ±{i:g} (ISO 2768-{'m' if kind == 'punch' else 'c'})" if i else \
        f"±{j:g} (JIS B 0408-{cls})"


NOTE = "보통 공차: JIS B 0408 B 급 (打抜き·曲げ) / ISO 2768-m"
