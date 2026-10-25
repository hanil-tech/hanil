"""공정별 힘(톤수) → 사용 기계 → 공정 시간 × 기계 임률, 그리고 금형 견적.

기계 목록·임률·금형 단가는 사용자가 [견적 → 기계·임률 / 금형 단가] 에서 바꾼다 (아래는 예시값).

톤수
  · 전단 (블랭킹·노칭·트림·피어싱·분리)  P = L·t·τ,  τ = 인장강도 × 0.8
  · 굽힘 (에어)                           F = 1.33·σb·L·t²/V  (바텀 ×2, 코이닝 ×5)
  · 드로우 (자유곡면 성형품, 어림)         F = 블랭크 둘레 × t × σb × 0.7 + 블랭크 홀더 (그 30 %)
  · 순차·트랜스퍼 금형은 모든 공정을 한 프레스에서 → 공정 힘의 합, 단발(탠덤)은 공정마다
  · 기계 선택: 필요 톤수 × 여유 (기본 1.3) 이상인 가장 작은 기계, 절곡기는 절곡 길이 ≤ 기계 길이
시간
  · 프레스: 1 타 = 60 / SPM 초 (순차·트랜스퍼는 부품당 1 타, 단발은 공정마다 1 타)
  · 절곡기: 절곡 1 회 초 (손 다루기 포함)
  · 레이저: 절단 길이 / 속도(두께별) + 피어싱 시간
  · 준비(금형 교환·세팅) 분 × 임률 ÷ 로트 수량
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc

PRESS, BRAKE, LASER, MACHINING = "프레스", "절곡기", "레이저", "가공기"

# 예시 기계 (회사 기계로 바꿀 것). capacity: 프레스·절곡기 톤, 레이저 최대 두께 mm
DEFAULT_MACHINES = [
    {"name": "프레스 60톤", "kind": PRESS, "capacity": 60, "length": 0, "rate": 40000, "spm": 35, "setup_min": 30},
    {"name": "프레스 110톤", "kind": PRESS, "capacity": 110, "length": 0, "rate": 50000, "spm": 30, "setup_min": 40},
    {"name": "프레스 200톤", "kind": PRESS, "capacity": 200, "length": 0, "rate": 70000, "spm": 22, "setup_min": 60},
    {"name": "프레스 300톤", "kind": PRESS, "capacity": 300, "length": 0, "rate": 90000, "spm": 18, "setup_min": 60},
    {"name": "프레스 500톤", "kind": PRESS, "capacity": 500, "length": 0, "rate": 130000, "spm": 12, "setup_min": 90},
    {"name": "프레스 800톤", "kind": PRESS, "capacity": 800, "length": 0, "rate": 200000, "spm": 10, "setup_min": 120},
    {"name": "절곡기 100톤 3m", "kind": BRAKE, "capacity": 100, "length": 3100, "rate": 35000, "spm": 0,
     "setup_min": 10, "sec_per_op": 18},
    {"name": "절곡기 220톤 4m", "kind": BRAKE, "capacity": 220, "length": 4100, "rate": 45000, "spm": 0,
     "setup_min": 15, "sec_per_op": 25},
    {"name": "절곡기 400톤 6m", "kind": BRAKE, "capacity": 400, "length": 6100, "rate": 70000, "spm": 0,
     "setup_min": 20, "sec_per_op": 40},
    {"name": "파이버 레이저 6kW", "kind": LASER, "capacity": 25, "length": 0, "rate": 80000, "spm": 0,
     "setup_min": 5, "speed_1mm": 35},
    {"name": "선반·MCT", "kind": MACHINING, "capacity": 0, "length": 0, "rate": 45000, "spm": 0,
     "setup_min": 30, "sec_per_kg": 240},
]

# 금형 견적 단가 (예시값)
DEFAULT_DIE = {
    "design_per_station": 400_000,      # 설계 (공정당)
    "steel_kg": 2_800,                  # 다이 세트·플레이트 (SM45C·SS) 원/kg
    "insert_kg_per_station": 15,        # 펀치·다이 인서트 (SKD11) kg/공정
    "insert_steel_kg": 12_000,          # SKD11 원/kg
    "heat_kg": 3_500,                   # 열처리 원/kg (인서트)
    "machining_per_station": 1_500_000,  # 와이어컷·MCT·연삭 (공정당)
    "std_parts_base": 600_000,          # 가이드 포스트·부시·볼트 (금형 1 벌)
    "std_parts_per_station": 250_000,   # 펀치·스프링·리프터 (공정당)
    "assembly_base": 1_000_000,         # 조립·트라이 (1 벌)
    "assembly_per_station": 250_000,
    "drawing_factor": 1.8,              # 드로우·성형 공정은 가공·트라이가 더 듦 (배수)
    "plate_thickness": 320,             # 다이 세트 전체 두께 mm (윗형 + 아랫형)
    "margin": 90,                       # 스트립·부품 둘레 여유 mm
    "overhead_pct": 10.0,
    "profit_pct": 10.0,
}

SAFETY = 1.3


def default_costing():
    return {"machines": copy.deepcopy(DEFAULT_MACHINES), "die": dict(DEFAULT_DIE), "safety": SAFETY}


@dataclass
class OpCost:
    op: str
    kind: str              # 프레스 / 절곡기 / 레이저 / 가공기
    force_n: float         # 공정 힘 (N)
    machine: str = ""
    seconds: float = 0.0   # 부품당
    cost: float = 0.0      # 원/개 (준비 포함)
    note: str = ""

    @property
    def tonf(self):
        return self.force_n / dc.TON


def pick(machines, kind, need_ton=0.0, length=0.0):
    """조건에 맞는 가장 작은 기계 (없으면 가장 큰 것, 주의 표시용 False)."""
    cands = [m for m in machines if m["kind"] == kind]
    if not cands:
        return None, False
    ok = [m for m in cands if m["capacity"] >= need_ton and (not length or not m.get("length")
                                                               or m["length"] >= length)]
    if ok:
        return min(ok, key=lambda m: (m["capacity"], m.get("length", 0))), True
    return max(cands, key=lambda m: (m["capacity"], m.get("length", 0))), False


# 6 kW 파이버 레이저 연강 절단 속도 어림 (m/분): 얇은 판은 질소·공기 고속, 5 mm 넘으면 산소 절단.
# 제조사 표 (IPG·machinemfg O2 표 6 mm 1.4~3.2, 10 mm 0.75~2.1, 20 mm 0.4~0.75) 와 현장 예
# (6 kW 3 mm 약 15 m/분) 의 가운데. 기계마다 다르므로 [1 mm 속도] 로 비례 조정.
LASER_6KW = [(0.5, 45.0), (1, 35.0), (2, 22.0), (3, 14.0), (4, 7.0), (5, 3.6), (6, 2.6), (8, 2.0),
             (10, 1.5), (12, 1.2), (16, 0.85), (20, 0.6), (25, 0.45)]


def laser_speed(m, t):
    """m/분. 6 kW 표를 두께로 (로그) 보간하고, 기계의 1 mm 속도 / 35 로 비례."""
    xs = [math.log(a) for a, _ in LASER_6KW]
    ys = [math.log(b) for _, b in LASER_6KW]
    v = math.exp(float(np.interp(math.log(max(t, 0.5)), xs, ys)))
    return v * m.get("speed_1mm", 35) / 35.0


def _setup_cost(m, lot):
    return m.get("setup_min", 0) * m["rate"] / 60 / max(lot, 1)


def op_costs(item, settings: bc.BendSettings, method, ops, cut_len, pierce, costing, lot):
    """부품 하나의 공정별 힘·기계·시간·비용 목록."""
    mat = settings.mat
    t = item.thickness or 0.0
    tau = dc.shear_strength(mat)
    machines = costing["machines"]
    sf = costing.get("safety", SAFETY)
    r = item.result
    out = []
    if r is None or method == "기계 가공":
        m, ok = pick(machines, MACHINING)
        sec = item.weight * (m.get("sec_per_kg", 240) if m else 240)
        cost = (sec * m["rate"] / 3600 + _setup_cost(m, lot)) if m else 0.0
        out.append(OpCost("기계 가공", MACHINING, 0.0, m["name"] if m else "-", sec, cost,
                          "무게 비례 어림 — 확인"))
        return out
    bends = list(r.bends)
    v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)

    def bend_n(b):
        return dc.bend_force(mat, b.length, t, v, settings.process)

    if "레이저" in method:
        m, ok = pick(machines, LASER, t)
        if m:
            sp = laser_speed(m, t)
            sec = cut_len / 1000 / sp * 60 + pierce * (0.5 + 0.1 * t) + 20     # + 올리고 내리기 20 초
            out.append(OpCost("레이저 절단", LASER, 0.0, m["name"], sec,
                              sec * m["rate"] / 3600 + _setup_cost(m, lot),
                              f"{cut_len / 1000:.2f} m @ {sp:.1f} m/분, 피어싱 {pierce}" + ("" if ok else " ⚠ 두께 초과")))
        for b in bends:
            f = bend_n(b)
            m, ok = pick(machines, BRAKE, f / dc.TON * sf, b.length)
            sec = m.get("sec_per_op", 20) if m else 20
            out.append(OpCost(f"절곡 B{b.number}", BRAKE, f, m["name"] if m else "-", sec,
                              (sec * m["rate"] / 3600 + _setup_cost(m, lot)) if m else 0.0,
                              f"길이 {b.length:.0f} · {f / dc.TON:.1f} tf" + ("" if ok else " ⚠ 용량 초과")))
        return out

    # 금형: 공정별 힘
    rep = dc.review(r, settings, strip=False)
    blank_n = rep.loads[0].force_n
    pierce_n = rep.loads[1].force_n
    strip_n = 0.10 * (blank_n + pierce_n)
    n_pierce = max(sum("피어싱" in o or "PI" in o for o in ops), 1)
    bend_total = sum(bend_n(b) for b in bends)
    n_bend = max(sum(o.startswith("절곡") or "예비 굽힘" in o for o in ops), 1)
    forming = r.forming is not None
    draw_n = 0.0
    if forming:
        draw_n = rep.loads[0].length * t * mat.tensile_mpa * 0.7 * 1.3     # + 홀더 30 %
    forces = []
    for o in ops:
        if o.startswith("DR"):
            f = draw_n
        elif "피어싱" in o or "PI" in o:
            f = pierce_n / n_pierce + (strip_n / 2 if "1" in o or o == "피어싱" else 0)
        elif "노칭" in o or "외곽" in o or "트림" in o or "TR" in o or "블랭킹" in o:
            f = blank_n + strip_n / 2
        elif o.startswith("절곡") or "굽힘" in o:
            f = bend_total / n_bend
        elif o.startswith("FL") or o.startswith("RST"):
            f = 0.3 * draw_n
        elif "분리" in o:
            f = 0.05 * blank_n
        else:
            f = 0.0
        forces.append(f)
    one_press = "순차" in method or "트랜스퍼" in method or "복합" in method
    if one_press:
        total = sum(forces)
        m, ok = pick(machines, PRESS, total / dc.TON * sf)
        spm = (m.get("spm") or 20) if m else 20
        if "트랜스퍼" in method:
            spm *= 0.6
        sec = 60 / spm
        cost = (sec * m["rate"] / 3600 + _setup_cost(m, lot)) if m else 0.0
        for i, (o, f) in enumerate(zip(ops, forces)):
            out.append(OpCost(o, PRESS, f, m["name"] if m else "-", sec if i == 0 else 0.0,
                              cost if i == 0 else 0.0,
                              (f"한 프레스에서 전 공정 합 {total / dc.TON:.1f} tf × {sf:g}" + ("" if ok else " ⚠ 용량 초과"))
                              if i == 0 else "같은 프레스"))
    else:
        for o, f in zip(ops, forces):
            m, ok = pick(machines, PRESS, f / dc.TON * sf)
            spm = (m.get("spm") or 20) if m else 20
            sec = 60 / spm * 1.5            # 단발: 넣고 빼기 포함
            out.append(OpCost(o, PRESS, f, m["name"] if m else "-", sec,
                              (sec * m["rate"] / 3600 + _setup_cost(m, lot)) if m else 0.0,
                              "" if ok else "⚠ 용량 초과"))
    return out


# ---------------------------------------------------------------- 금형 견적

@dataclass
class DieQuote:
    part_no: int
    part_name: str
    die_type: str
    stations: int
    size: tuple              # (길이, 폭, 두께) mm
    lines: list = field(default_factory=list)      # (항목, 산식, 금액)
    sets: int = 1            # 금형 벌 수 (단발 탠덤은 공정마다 한 벌)
    ops: list = field(default_factory=list)        # 공정 이름
    plan: object = None      # 순차 금형이면 process.ProcessPlan (간략도의 스트립)
    outline: object = None   # 전개 외곽 (간략도의 블랭크)
    holes: list = field(default_factory=list)     # 전개 구멍들
    press_tonf: float = 0.0
    steel_kg: float = 0.0
    insert_kg: float = 0.0

    @property
    def cost(self):
        return sum(x[2] for x in self.lines)


def die_quote(item, method, ops, costing, settings: bc.BendSettings, plan=None, press_tonf=0.0):
    """금형 1 벌(순차·복합·트랜스퍼) 또는 공정별 단발 금형들의 합.
    plan: 순차 금형의 스트립 공정도 (있으면 금형 길이·폭을 실제 피치·스트립 폭으로)."""
    d = costing["die"]
    r = item.result
    if r is None or "레이저" in method or method == "기계 가공":
        return None
    w, h = r.size
    t = r.thickness
    n = max(len([o for o in ops if "분리" not in o]), 1)
    forming = any(o.startswith("DR") or o.startswith("FL") or o.startswith("RST") for o in ops)
    k_form = d["drawing_factor"] if forming else 1.0
    mg = d["margin"]
    if "순차" in method and plan is not None:
        L = len(plan.stations) * plan.pitch + 2 * mg
        W = plan.strip_width + 2 * mg
        sets = 1
    elif "순차" in method:
        pitch = max(w, h) + 2 * t
        L = n * pitch + 2 * mg
        W = min(w, h) + 2 * mg + 40          # 캐리어 몫
        sets = 1
    elif "복합" in method:
        L, W, sets = w + 2 * mg, h + 2 * mg, 1
    elif "트랜스퍼" in method:
        L, W, sets = n * (max(w, h) + 2 * mg), min(w, h) + 2 * mg, 1
    else:   # 단발 (탠덤): 공정마다 한 벌
        L, W, sets = w + 2 * mg, h + 2 * mg, n
    T = d["plate_thickness"]
    steel_kg = L * W * T * 7.85e-6 * 0.55 * (sets if sets > 1 else 1)     # 빈 곳 빼고 55 %
    insert_kg = d["insert_kg_per_station"] * n * max(t / 2, 0.6)
    lines = [
        ("설계", f"{n} 공정 × {d['design_per_station']:,}", n * d["design_per_station"] * (1 if sets == 1 else 1.2)),
        ("다이 세트·플레이트", f"{L:.0f}×{W:.0f}×{T:.0f} mm{' × ' + str(sets) + ' 벌' if sets > 1 else ''} ≈ "
                           f"{steel_kg:,.0f} kg × {d['steel_kg']:,}", steel_kg * d["steel_kg"]),
        ("인서트 (SKD11)", f"{insert_kg:,.0f} kg × {d['insert_steel_kg']:,}", insert_kg * d["insert_steel_kg"]),
        ("열처리", f"{insert_kg:,.0f} kg × {d['heat_kg']:,}", insert_kg * d["heat_kg"]),
        ("가공 (와이어·MCT·연삭)", f"{n} 공정 × {d['machining_per_station']:,}" + (f" × {k_form:g}" if k_form != 1 else ""),
         n * d["machining_per_station"] * k_form),
        ("표준 부품", f"{sets} 벌 × {d['std_parts_base']:,} + {n} × {d['std_parts_per_station']:,}",
         sets * d["std_parts_base"] + n * d["std_parts_per_station"]),
        ("조립·트라이", f"{sets} × {d['assembly_base']:,} + {n} × {d['assembly_per_station']:,}"
                     + (f" × {k_form:g}" if k_form != 1 else ""),
         (sets * d["assembly_base"] + n * d["assembly_per_station"]) * k_form),
    ]
    sub = sum(x[2] for x in lines)
    oh = sub * d["overhead_pct"] / 100
    pf = (sub + oh) * d["profit_pct"] / 100
    lines += [(f"일반관리비 {d['overhead_pct']:g} %", "", oh), (f"이윤 {d['profit_pct']:g} %", "", pf)]
    outline, holes = None, []
    try:
        from .nesting import NestPart
        np_ = NestPart.from_result("p", r)
        outline, holes = np_.outer, list(np_.holes)
    except ValueError:
        pass
    return DieQuote(item.no, item.name, method, n, (L, W, T), lines, sets, list(ops), plan, outline, holes,
                    press_tonf, steel_kg, insert_kg)


DIE_NAMES = {
    "design_per_station": "설계 (원/공정)", "steel_kg": "다이 세트 강재 (원/kg)",
    "insert_kg_per_station": "인서트 무게 (kg/공정, t2 기준)", "insert_steel_kg": "SKD11 (원/kg)",
    "heat_kg": "열처리 (원/kg)", "machining_per_station": "가공 (원/공정)", "std_parts_base": "표준 부품 (원/벌)",
    "std_parts_per_station": "표준 부품 (원/공정)", "assembly_base": "조립·트라이 (원/벌)",
    "assembly_per_station": "조립·트라이 (원/공정)", "drawing_factor": "성형 공정 배수",
    "plate_thickness": "다이 세트 두께 (mm)", "margin": "둘레 여유 (mm)", "overhead_pct": "일반관리비 (%)",
    "profit_pct": "이윤 (%)",
}

MACHINE_COLS = [("name", "기계 이름"), ("kind", "종류"), ("capacity", "용량 (톤 / 레이저 최대 t)"),
                ("length", "길이 mm (절곡기)"), ("rate", "임률 원/시간"), ("spm", "SPM (프레스)"),
                ("setup_min", "준비 분"), ("sec_per_op", "1 회 초 (절곡기)"), ("speed_1mm", "1 mm 속도 m/분 (레이저)"),
                ("sec_per_kg", "초/kg (가공기)")]
