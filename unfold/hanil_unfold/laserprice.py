"""레이저 절단 · 절곡 단가 뽑기 — 전개한 부품마다 (절단 길이 · 피어싱 수 · 절곡 수 · 길이 · 무게) 로 개당 단가.

  레이저: 시간 = 절단 길이 ÷ 두께별 속도 (costing.laser_speed, 6 kW 표를 [1 mm 속도] 로 비례) + 피어싱 (기본 초 + 두께 × 초/mm)
          + 올리고 내리기 초;  단가 = 시간 × 임률 (원/h) + 보조 가스 (원/분) + 준비 (분 × 임률 ÷ 로트)
  절곡:   [시간 × 임률] 절곡 1 회 초 × 절곡 수 × 임률 + 준비 ÷ 로트
          [회당 단가표] 1 회 기본 원 + 길이 1 m 당 원 + 두께 1 mm 당 원 — 업체 견적 관행 (회당 얼마) 에 맞춤
  재료:   사각 원판 무게 × 원/kg − 자투리 (사각 − 블랭크) × 고철 원/kg  (끄면 가공비만)
  그 위에 일반관리비 % · 이윤 %. 단가는 모두 예시값 — [단가] 칸에서 회사 값으로 바꾸면 QSettings 에 남는다."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

from . import costing as cs

DEFAULTS = {
    "lot": 100,                       # 로트 (준비 비용을 나눌 수량)
    "laser": {"rate": 80_000, "speed_1mm": 35.0, "pierce_sec": 0.5, "pierce_per_mm": 0.1, "load_sec": 20.0,
              "setup_min": 5.0, "gas_per_min": 300.0, "max_t": 25.0},
    "bend": {"mode": "time", "rate": 35_000, "sec_per_bend": 18.0, "setup_min": 10.0,
             "per_bend": 500.0, "per_m": 300.0, "per_mm_t": 150.0},
    "material": {"include": True, "price_kg": 0.0, "scrap_kg": 300.0},    # price_kg 0 = 재질 표 값
    "overhead_pct": 10.0,
    "profit_pct": 10.0,
}
NAMES = {
    ("lot",): "로트 (개)",
    ("laser", "rate"): "레이저 임률 (원/h)", ("laser", "speed_1mm"): "1 mm 절단 속도 (m/분)",
    ("laser", "pierce_sec"): "피어싱 기본 (초)", ("laser", "pierce_per_mm"): "피어싱 두께 1 mm 당 (초)",
    ("laser", "load_sec"): "올리고 내리기 (초/장)", ("laser", "setup_min"): "레이저 준비 (분/로트)",
    ("laser", "gas_per_min"): "보조 가스 (원/분)", ("laser", "max_t"): "레이저 최대 두께 (mm)",
    ("bend", "rate"): "절곡기 임률 (원/h)", ("bend", "sec_per_bend"): "절곡 1 회 (초)", ("bend", "setup_min"): "절곡 준비 (분/로트)",
    ("bend", "per_bend"): "절곡 1 회 기본 (원)", ("bend", "per_m"): "절곡 길이 1 m 당 (원)", ("bend", "per_mm_t"): "두께 1 mm 당 (원)",
    ("material", "price_kg"): "재료 (원/kg, 0 = 재질 표)", ("material", "scrap_kg"): "고철 회수 (원/kg)",
    ("overhead_pct",): "일반관리비 (%)", ("profit_pct",): "이윤 (%)",
}
BEND_MODES = [("time", "시간 × 임률"), ("table", "회당 단가표")]


def load(text: str | None) -> dict:
    r = copy.deepcopy(DEFAULTS)
    if text:
        try:
            saved = json.loads(text)
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(r.get(k), dict):
                    r[k].update(v)
                elif k in r:
                    r[k] = v
        except (ValueError, TypeError, AttributeError):
            pass
    return r


def dump(rates: dict) -> str:
    return json.dumps(rates, ensure_ascii=False)


def material_price(code: str, rates: dict) -> float:
    p = float((rates.get("material") or {}).get("price_kg") or 0)
    if p > 0:
        return p
    from .quote import MATERIAL_PRICE
    return float(MATERIAL_PRICE.get(code, 1300))


@dataclass
class PartPrice:
    no: int
    name: str
    qty: int                      # 세트당 개수
    thickness: float
    cut_m: float                  # 절단 길이 m
    pierce: int
    laser_sec: float
    laser_won: float              # 개당
    bends: int
    bend_m: float                 # 절곡 길이 합 m
    bend_sec: float
    bend_won: float               # 개당
    material_won: float           # 개당
    weight_kg: float              # 블랭크 무게
    rect_kg: float                # 사각 원판 무게
    sub: float = 0.0              # 가공 + 재료 (개당)
    unit: float = 0.0             # 일반관리비 · 이윤 포함 개당 단가
    notes: list = field(default_factory=list)

    @property
    def total(self):
        return self.unit * self.qty


def price_one(no, name, qty, result, metrics, code, rates, lot=None) -> PartPrice:
    """부품 하나의 개당 단가. result: UnfoldResult (절곡 길이), metrics: metrics.Metrics (절단 길이 · 피어싱 · 무게)."""
    L = rates.get("laser", {})
    B = rates.get("bend", {})
    M = rates.get("material", {})
    lot = max(int(lot or rates.get("lot") or 1), 1)
    t = float(result.thickness)
    notes = []
    # 레이저
    sp = cs.laser_speed({"speed_1mm": float(L.get("speed_1mm", 35.0))}, t)
    cut_m = metrics.cut_length / 1000.0
    pierce = int(metrics.pierce)
    laser_sec = cut_m / sp * 60.0 + pierce * (float(L.get("pierce_sec", 0.5)) + float(L.get("pierce_per_mm", 0.1)) * t) \
        + float(L.get("load_sec", 20.0))
    laser_won = laser_sec * float(L.get("rate", 80_000)) / 3600.0 + laser_sec / 60.0 * float(L.get("gas_per_min", 0.0)) \
        + float(L.get("setup_min", 0.0)) * float(L.get("rate", 80_000)) / 60.0 / lot
    if t > float(L.get("max_t", 25.0)):
        notes.append(f"두께 {t:g} > 레이저 최대 {L.get('max_t', 25.0):g} mm")
    # 절곡
    bends = list(getattr(result, "bends", []) or [])
    n_b = len(bends)
    bend_m = sum(float(b.length) for b in bends) / 1000.0
    if B.get("mode", "time") == "table":
        bend_sec = n_b * float(B.get("sec_per_bend", 18.0))
        bend_won = n_b * float(B.get("per_bend", 500.0)) + bend_m * float(B.get("per_m", 300.0)) \
            + n_b * t * float(B.get("per_mm_t", 150.0))
    else:
        bend_sec = n_b * float(B.get("sec_per_bend", 18.0))
        bend_won = bend_sec * float(B.get("rate", 35_000)) / 3600.0 \
            + (float(B.get("setup_min", 0.0)) * float(B.get("rate", 35_000)) / 60.0 / lot if n_b else 0.0)
    # 재료
    material_won = 0.0
    if M.get("include", True):
        p = material_price(code, rates)
        material_won = metrics.rect_weight_kg * p - max(metrics.rect_weight_kg - metrics.weight_kg, 0.0) * float(M.get("scrap_kg", 0.0))
    sub = laser_won + bend_won + material_won
    oh = sub * float(rates.get("overhead_pct", 0.0)) / 100.0
    unit = (sub + oh) * (1 + float(rates.get("profit_pct", 0.0)) / 100.0)
    return PartPrice(no, name, int(qty), t, cut_m, pierce, laser_sec, laser_won, n_b, bend_m, bend_sec, bend_won,
                     material_won, metrics.weight_kg, metrics.rect_weight_kg, sub, unit, notes)


def price_parts(model, parts, settings, excluded=(), rates=None, lot=None):
    """조립품 전체: 같은 부품은 묶어 (bom.build) 품번마다 한 줄. (줄 목록, 합계 dict)."""
    from . import bom
    rates = rates or copy.deepcopy(DEFAULTS)
    items = bom.build(model, parts, settings.mat.density, excluded, settings.mat.code)
    by_idx = {p.index: p for p in parts}
    rows = []
    for it in items:
        if it.excluded:
            continue
        p = by_idx.get(it.indices[0])
        if p is None or not p.ok or p.metrics is None or it.kind == "기타":
            continue
        rows.append(price_one(it.no, it.name, len(it.indices), p.result, p.metrics, settings.mat.code, rates, lot))
    tot = {"laser": sum(r.laser_won * r.qty for r in rows), "bend": sum(r.bend_won * r.qty for r in rows),
           "material": sum(r.material_won * r.qty for r in rows), "unit_sum": sum(r.total for r in rows),
           "parts": sum(r.qty for r in rows), "laser_sec": sum(r.laser_sec * r.qty for r in rows),
           "bends": sum(r.bends * r.qty for r in rows)}
    return rows, tot


HEAD = ["품번", "부품명", "세트당", "t", "절단 m", "피어싱", "레이저 초", "레이저 원/개", "절곡 수", "절곡 m", "절곡 원/개",
        "재료 원/개", "개당 단가", "세트 합계", "비고"]


def table_rows(rows):
    return [[r.no, r.name, r.qty, round(r.thickness, 2), round(r.cut_m, 2), r.pierce, round(r.laser_sec), round(r.laser_won),
             r.bends, round(r.bend_m, 2), round(r.bend_won), round(r.material_won), round(r.unit), round(r.total),
             " · ".join(r.notes)] for r in rows]


def save_xlsx(rows, tot, rates, path, name="", seams=None, weld_costs=None, weld_tot=None, weld_rates=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "레이저·절곡 단가"
    ws["A1"] = f"레이저 절단 · 절곡 단가 — {name}"
    ws["A1"].font = Font(bold=True, size=13)
    B = rates.get("bend", {})
    ws["A2"] = (f"로트 {rates.get('lot', 1)} 개 · 레이저 {rates['laser']['rate']:,} 원/h (1 mm {rates['laser']['speed_1mm']:g} m/분) · "
                f"절곡 {dict(BEND_MODES).get(B.get('mode', 'time'))} "
                + (f"{B.get('rate', 0):,} 원/h, 1 회 {B.get('sec_per_bend', 0):g} 초" if B.get("mode", "time") == "time"
                   else f"1 회 {B.get('per_bend', 0):,.0f} + m 당 {B.get('per_m', 0):,.0f} + mm 당 {B.get('per_mm_t', 0):,.0f} 원")
                + f" · 재료 {'포함' if rates['material'].get('include', True) else '제외'} · 관리비 {rates.get('overhead_pct', 0):g} % · 이윤 {rates.get('profit_pct', 0):g} %")
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")
    for j, h in enumerate(HEAD, 1):
        c = ws.cell(4, j, h)
        c.font, c.fill, c.alignment = hf, hfill, Alignment(horizontal="center")
    r = 5
    for row in table_rows(rows):
        for j, v in enumerate(row, 1):
            ws.cell(r, j, v)
        r += 1
    ws.cell(r, 1, "합계").font = Font(bold=True)
    ws.cell(r, 3, tot["parts"])
    ws.cell(r, 8, round(tot["laser"]))
    ws.cell(r, 11, round(tot["bend"]))
    ws.cell(r, 12, round(tot["material"]))
    ws.cell(r, 14, round(tot["unit_sum"])).font = Font(bold=True)
    for col, wd in zip("ABCDEFGHIJKLMNO", (6, 34, 7, 5, 8, 7, 9, 12, 8, 8, 11, 11, 11, 12, 30)):
        ws.column_dimensions[col].width = wd
    ws.freeze_panes = "C5"
    wr = wb.create_sheet("단가 기준")
    wr["A1"] = "항목"
    wr["B1"] = "값"
    k = 2
    for key, label in NAMES.items():
        v = rates
        for kk in key:
            v = v.get(kk) if isinstance(v, dict) else None
        wr.cell(k, 1, label)
        wr.cell(k, 2, v)
        k += 1
    wr.cell(k, 1, "절곡 계산 방식")
    wr.cell(k, 2, dict(BEND_MODES).get(B.get("mode", "time")))
    wr.cell(k + 1, 1, "재료비 포함")
    wr.cell(k + 1, 2, "예" if rates["material"].get("include", True) else "아니오")
    wr.column_dimensions["A"].width = 30
    wr.column_dimensions["B"].width = 16
    if seams is not None:
        from . import weldcalc as wc
        wt = wb.create_sheet("용접")
        wt["A1"] = f"용접 견적 — {name}"
        wt["A1"].font = Font(bold=True, size=13)
        wr_ = dict(wc.DEFAULTS)
        wr_.update(weld_rates or {})
        wt["A2"] = (f"임률 {wr_['rate']:,.0f} 원/h · 아크 타임 비율 {wr_['arc_ratio']:g} · 단속률 {wr_['intermittent']:g} · "
                    f"소모품 {wr_['consumable_per_m']:,.0f} 원/m · 사상 {wr_['grind_sec_per_m']:g} 초/m · 가접 {wr_['tack_sec']:g} 초 · "
                    f"준비 {wr_['setup_min']:g} 분/로트")
        head = ["부품 A", "부품 B", "종류", "길이 mm", "면", "t", "아크 초", "전체 초", "원", "비고"]
        for j, h in enumerate(head, 1):
            c = wt.cell(4, j, h)
            c.font, c.fill, c.alignment = hf, hfill, Alignment(horizontal="center")
        r = 5
        for c_ in (weld_costs or []):
            sm = c_.seam
            for j, v in enumerate([sm.name_a, sm.name_b, sm.kind, round(sm.length), sm.sides, sm.thickness, round(c_.arc_sec),
                                   round(c_.total_sec), round(c_.won), sm.note], 1):
                wt.cell(r, j, v)
            r += 1
        wtot = weld_tot or {}
        wt.cell(r, 1, "합계").font = Font(bold=True)
        wt.cell(r, 4, round(wtot.get("length_m", 0) * 1000))
        wt.cell(r, 7, round(wtot.get("arc_sec", 0)))
        wt.cell(r, 8, round(wtot.get("sec", 0)))
        wt.cell(r, 9, round(wtot.get("won", 0))).font = Font(bold=True)
        wt.cell(r + 1, 1, "준비 (분/로트 ÷ 로트)")
        wt.cell(r + 1, 9, round(wtot.get("setup", 0)))
        for col, wd in zip("ABCDEFGHIJ", (28, 28, 8, 10, 5, 6, 9, 9, 11, 34)):
            wt.column_dimensions[col].width = wd
        # 첫 시트 위에 세트 견적
        ws.cell(3, 1, "세트 견적").font = Font(bold=True)
        ws.cell(3, 2, f"부품 {tot['unit_sum']:,.0f} + 용접 {wtot.get('won', 0):,.0f} = {tot['unit_sum'] + wtot.get('won', 0):,.0f} 원")
    wb.save(path)
    return path
