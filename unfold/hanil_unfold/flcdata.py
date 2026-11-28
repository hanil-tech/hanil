"""재질별 실측 성형 한계 곡선 (FLC) 저장·읽기: 소재 업체의 ISO 12004-2 시험 성적 (ε2, ε1) 점들.

설정 (QSettings "form/flc/<재질 코드>") 에 JSON 으로: {"unit": "true"|"eng"|"pct", "points": [[ε2, ε1], ...]}.
  true — 진변형률 (그대로)   eng — 공칭 변형률 (ln(1+e))   pct — 공칭 % (ln(1+e/100))
읽으면 forming.MEASURED_FLC 에 진변형률로 넣는다. 있으면 성형 해석·FLD 가 Keeler 식 대신 쓴다.
"""
from __future__ import annotations

import json
import math

from . import forming

UNITS = {"true": "진변형률", "eng": "공칭 변형률 (0.25)", "pct": "공칭 % (25)"}


def to_true(points, unit):
    def f(v):
        v = float(v)
        return v if unit == "true" else math.log(1 + v) if unit == "eng" else math.log(1 + v / 100)
    pts = sorted((f(a), f(b)) for a, b in points)
    return [p for i, p in enumerate(pts) if i == 0 or abs(p[0] - pts[i - 1][0]) > 1e-9]


def parse(text, unit="true"):
    """붙여 넣은 글 (줄마다 'ε2 ε1', 쉼표·탭) → 진변형률 점들."""
    pts = []
    for line in (text or "").replace(";", "\n").splitlines():
        parts = [x for x in line.replace(",", " ").replace("\t", " ").split() if x]
        if len(parts) >= 2:
            try:
                pts.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return to_true(pts, unit)


def check(points):
    """(괜찮은가, 알림)"""
    if len(points) < 3:
        return False, "점이 3 개 넘어야 합니다 (왼쪽·가운데·오른쪽)"
    if not any(x < 0 for x, _ in points) or not any(x > 0 for x, _ in points):
        return False, "부 변형률 ε2 가 음수인 점과 양수인 점이 다 있어야 합니다"
    if any(y <= 0 or y > 1.5 for _, y in points):
        return False, "주 변형률 ε1 이 0 ~ 1.5 (진변형률) 밖 — 단위를 확인하세요"
    return True, ""


def load(settings):
    """설정 → forming.MEASURED_FLC (앱 시작·창 닫을 때)."""
    forming.MEASURED_FLC.clear()
    try:
        settings.beginGroup("form/flc")
        keys = list(settings.childKeys())
        settings.endGroup()
    except Exception:
        return
    for code in keys:
        try:
            d = json.loads(settings.value(f"form/flc/{code}", "") or "{}")
            pts = to_true(d.get("points", []), d.get("unit", "true"))
        except (ValueError, TypeError):
            continue
        if check(pts)[0]:
            forming.MEASURED_FLC[code] = pts


def save(settings, code, points):
    """points: 진변형률 점들 (parse 결과). 빈 목록이면 지움."""
    if points:
        settings.setValue(f"form/flc/{code}", json.dumps({"unit": "true", "points": [list(p) for p in points]}))
    else:
        settings.remove(f"form/flc/{code}")
    load(settings)
