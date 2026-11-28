"""금형비 어림 — 설계한 금형 (die3d.DieAssy) 의 부품표에서: 재료 (무게 × kg 단가), 표준품 (개수 × 단가), 가공, 열처리,
설계, 조립·트라이, 간접비·이윤. 단가는 costing.DEFAULT_DIE (견적 단가 창에서 고치는 값) 와 아래 표준품 단가표 — 모두 예시값이라
업체 견적으로 맞출 것. 주물 금형 (castdie) 은 주물 무게 × FC/FCD 단가 + 발포 모형 + 형면 NC 시간.
"""
from __future__ import annotations

import math
import re

from . import costing as cs

# 표준품 단가 (원/개, 예시) — 이름에 들어 있는 말로 고름
STD_PRICE = [
    ("캠 슬라이더", 450_000), ("캠 드라이버", 150_000), ("가스 스프링", 120_000), ("가이드 포스트", 60_000),
    ("가이드 부시", 45_000), ("다이 스프링", 12_000), ("스트리퍼 볼트", 4_000), ("패드 볼트", 4_000),
    ("파일럿", 25_000), ("피어싱 펀치", 30_000), ("캠 피어싱 펀치", 35_000), ("다우얼", 2_500), ("게이지 핀", 2_500),
    ("네스트 핀", 2_500), ("쿠션 핀", 35_000), ("마모판", 25_000), ("밸런스 블록", 40_000), ("볼트", 1_500),
]
MACH_FACTOR = {"캠": 1.6, "후 피어싱": 1.2, "드로우": 1.8, "드로잉": 1.8, "성형": 1.8, "U 굽힘": 1.4, "각도": 1.3, "마무리": 1.2,
               "헤밍": 1.3, "절곡": 1.3, "블랭킹": 1.0, "피어싱": 1.0}      # 앞에 있는 것부터 맞춤 (캠 피어싱 → 캠)


def _std_price(name):
    for key, p in STD_PRICE:
        if key in name:
            return p
    return 5_000


def _kind_factor(kind):
    for key, f in MACH_FACTOR.items():
        if key in kind:
            return f
    return 1.0


def estimate(assy, rates=None):
    """[(항목, 근거, 원)], 합계 (원). assy.cast 가 True 면 주물 금형 꼴로."""
    d = dict(cs.DEFAULT_DIE)
    if rates:
        d.update(rates)
    lines = []
    steel = tool = cast_fc = cast_fcd = 0.0
    std_sum, std_n = 0.0, 0
    nc_m2 = 0.0
    for p in assy.parts:
        kg = p.weight * p.qty
        m = p.material
        if p.std:
            std_sum += _std_price(p.name) * p.qty
            std_n += p.qty
        elif "FCD" in m:
            cast_fcd += kg
        elif "FC3" in m or "FC2" in m and getattr(assy, "cast", False) or "주물" in m:
            cast_fc += kg
        elif any(k in m for k in ("SKD", "SKH", "SKS", "HRC 5", "HRC 6")):
            tool += kg
        else:
            steel += kg
        nc_m2 += getattr(p, "face_m2", 0.0)
    cast = bool(cast_fc or cast_fcd) or getattr(assy, "cast", False)
    kf = _kind_factor(getattr(assy, "kind", ""))
    if cast:
        lines.append(("설계 (주물 · 대형)", f"{d['design_per_station']:,} × 1.5", d["design_per_station"] * 1.5))
    else:
        lines.append(("설계", f"공정 1 × {d['design_per_station']:,}", d["design_per_station"]))
    if steel:
        lines.append(("강재 (다이 세트 · 판)", f"{steel:,.1f} kg × {d['steel_kg']:,}", steel * d["steel_kg"]))
    if tool:
        lines.append(("공구강 (SKD11 · SKH51)", f"{tool:,.1f} kg × {d['insert_steel_kg']:,}", tool * d["insert_steel_kg"]))
        lines.append(("열처리", f"{tool:,.1f} kg × {d['heat_kg']:,}", tool * d["heat_kg"]))
    if cast_fc:
        lines.append(("주물 FC300 (윗형 · 아랫형)", f"{cast_fc:,.0f} kg × {d['cast_kg']:,}", cast_fc * d["cast_kg"]))
    if cast_fcd:
        lines.append(("주물 FCD550 (펀치 · 누르개)", f"{cast_fcd:,.0f} kg × {d['cast_fcd_kg']:,}", cast_fcd * d["cast_fcd_kg"]))
    if cast_fc or cast_fcd:
        lines.append(("발포 모형", f"{cast_fc + cast_fcd:,.0f} kg × {d['pattern_kg']:,}", (cast_fc + cast_fcd) * d["pattern_kg"]))
    if nc_m2:
        h = d.get("nc_hours_m2", 40) * nc_m2
        lines.append(("형면 NC 가공", f"{d.get('nc_hours_m2', 40):g} h/m² × {nc_m2:.2f} m² = {h:,.0f} h × {d.get('nc_rate', 90000):,}",
                      h * d.get("nc_rate", 90000)))
        lines.append(("형면 화염 경화 · 사상", f"{nc_m2:.2f} m² × 1,000,000", nc_m2 * 1_000_000))
    mach = d["machining_per_station"] * kf * (1.3 if cast else 1.0)
    lines.append(("가공 (와이어 · MCT · 연삭)", f"{d['machining_per_station']:,} × {kf:g}" + (" × 1.3 (대형)" if cast else ""), mach))
    lines.append(("표준 부품", f"{std_n} 개 (단가표)", std_sum))
    asm = (d["assembly_base"] + d["assembly_per_station"]) * (kf if kf > 1 else 1.0) * (1.5 if cast else 1.0)
    lines.append(("조립 · 트라이", f"({d['assembly_base']:,} + {d['assembly_per_station']:,})"
                  + (f" × {kf:g}" if kf > 1 else "") + (" × 1.5 (대형)" if cast else ""), asm))
    sub = sum(x[2] for x in lines)
    oh = sub * d["overhead_pct"] / 100
    pr = (sub + oh) * d["profit_pct"] / 100
    lines.append(("간접비", f"{d['overhead_pct']:g} %", oh))
    lines.append(("이윤", f"{d['profit_pct']:g} %", pr))
    return lines, sub + oh + pr


def won(v):
    return f"{v:,.0f} 원"


def summary_line(assy, rates=None):
    lines, total = estimate(assy, rates)
    big = sorted(lines[:-2], key=lambda x: -x[2])[:3]
    return f"금형비 어림 {total / 1e4:,.0f} 만원 (" + " · ".join(f"{n} {v / 1e4:,.0f}" for n, _, v in big) + " …)"


def rates_from_settings():
    """견적 단가 창 (QSettings) 의 금형 단가 — 없으면 기본값."""
    try:
        from PySide6.QtCore import QSettings

        from . import quote as qt_
        return qt_.load_rates(QSettings("Hanil", "SheetUnfold").value("quote_rates", ""))["costing"]["die"]
    except Exception:  # noqa: BLE001
        return dict(cs.DEFAULT_DIE)


def parse_won(s):
    return float(re.sub(r"[^\d.]", "", s) or 0)


def total(ops, rates=None):
    """공정별 금형 전체 합 (못 만든 공정은 뺌)."""
    return sum(estimate(op.die, rates)[1] for op in ops if op.die is not None)


def rough_ceil(v):
    """보고용 반올림: 만 원 단위."""
    return math.ceil(v / 10_000) * 10_000
