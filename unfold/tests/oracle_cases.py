"""정답 대조 시험 (oracle) 사례: 손으로 계산한 정답 (해석식) · 문헌 계산 예제와 프로그램 결과를 견준다.

SolidCraft 의 reference tests (tests/oracle — 해석값·FreeCAD 값과 부피·넓이 대조) 를 본떠, 판금 전개에 맞게
전개 길이 · 블랭크 넓이 · 절단 길이 · 무게와 금형 설계식의 문헌 예제를 정답으로 둔다.

case = (번호, 묶음, 이름, 정답 출처, 식 설명, 정답, 프로그램 값 함수, 허용 상대 오차)
`python tools/oracle_report.py` 가 docs/oracle.md 표를 만들고, tests/test_oracle.py 가 모두 통과하는지 본다.
"""
from __future__ import annotations

import math
import os

from models import drawn_cup, flat_length, funnel, profile_part, tube

from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import loader
from hanil_unfold import metrics as mt
from hanil_unfold.unfolder import unfold


def _solid(shape):
    return loader.list_solids(shape)[0]


def _long(r):
    return max(r.size)


def _sheet(steps, t, k, width=50.0):
    return lambda: _long(unfold(_solid(profile_part(steps, t, width)), k_factor=k))


def _din(steps, t, width=50.0):
    st = bc.BendSettings(method=bc.K_DIN, use_shop_table=False)
    return lambda: _long(unfold(_solid(profile_part(steps, t, width)), settings=st))


def _din_k(r, t):
    """DIN 6935 보정 계수 k = 0.65 + 0.5·log10(r/s) (r/s < 5), 그 위는 1 → 중립축 K = k/2 (독립 계산)."""
    k = 1.0 if r / t >= 5 else 0.65 + 0.5 * math.log10(r / t)
    return min(max(k, 0.0), 1.0) / 2


def _flat_din(steps, t):
    total = 0.0
    for s in steps:
        total += s[1] if s[0] == "L" else math.radians(abs(s[1])) * (s[2] + _din_k(s[2], t) * t)
    return total


SHEET = [
    ("L 90° R1 t1", [("L", 50), ("B", 90, 1.0), ("L", 30)], 1.0, 0.44),
    ("L 90° R2 t2", [("L", 60), ("B", 90, 2.0), ("L", 40)], 2.0, 0.44),
    ("L 45° R3 t1.6", [("L", 70), ("B", 45, 3.0), ("L", 35)], 1.6, 0.44),
    ("L 135° R1.6 t1.6", [("L", 40), ("B", 135, 1.6), ("L", 40)], 1.6, 0.44),
    ("L 150° R5 t3", [("L", 80), ("B", 150, 5.0), ("L", 30)], 3.0, 0.44),
    ("U 채널 R2 t2", [("L", 30), ("B", 90, 2.0), ("L", 60), ("B", 90, 2.0), ("L", 30)], 2.0, 0.44),
    ("Z 단 R2 t2", [("L", 40), ("B", 90, 2.0), ("L", 25), ("B", -90, 2.0), ("L", 40)], 2.0, 0.44),
    ("모자 (4 절곡) R1.2 t1.2", [("L", 20), ("B", -90, 1.2), ("L", 25), ("B", 90, 1.2), ("L", 40), ("B", 90, 1.2),
                             ("L", 25), ("B", -90, 1.2), ("L", 20)], 1.2, 0.44),
    ("큰 R (R/t 10) t1", [("L", 50), ("B", 90, 10.0), ("L", 50)], 1.0, 0.44),
    ("두꺼운 판 t6 R6", [("L", 100), ("B", 90, 6.0), ("L", 60)], 6.0, 0.44),
    ("K 0.33 · L 90° R2 t2", [("L", 60), ("B", 90, 2.0), ("L", 40)], 2.0, 0.33),
    ("K 0.50 · L 90° R2 t2", [("L", 60), ("B", 90, 2.0), ("L", 40)], 2.0, 0.50),
]
DIN = [("DIN r/s 0.5", 0.5), ("DIN r/s 1", 1.0), ("DIN r/s 2", 2.0), ("DIN r/s 4", 4.0), ("DIN r/s 6", 6.0)]


def _tube(R_out, t, k):
    return lambda: unfold(_solid(tube(R_out, t, 100)), k_factor=k).size[0]


def _cone(k):
    def run():
        r = unfold(_solid(funnel()), k_factor=k)
        return mt.compute(r, 7.85).blank_area
    return run


def _cone_exact(k, rb=40.0, rt=80.0, h=60.0, t=2.0):
    """두께 가운데 아닌 K 면의 원뿔대 넓이 π (r1 + r2) · 빗변. 끝면은 벽에 수직 (두껍게 만들기) 이라 같은 빗변 자리에서
    반지름이 (1 − K) t · cos α 만큼 작다 (α = 축과 벽 사이 반각의 여각 — cos α = h / 빗변)."""
    L = math.hypot(rt - rb, h)
    d = (1 - k) * t
    return math.pi * (rb + rt - 2 * d * (h / L)) * L


def _dxf(kind):
    def run():
        import tempfile

        import test_dxf2d as T
        from hanil_unfold import dxf2d
        with tempfile.TemporaryDirectory() as d:
            fd = dxf2d.read(T.drawing(d + "/o.dxf"))
        p = [p for p in fd.parts if not p.frame][0]
        return p.area if kind == "area" else p.cut_length
    return run


def _cup():
    st = bc.BendSettings(material="SPCC")
    r = unfold(_solid(drawn_cup()), settings=st, mode="forming")
    return math.sqrt(4 * r.forming.blank_area / math.pi)


def _cup_exact(R=50.0, H=50.0, rf=8.0, t=1.0):
    """원통 컵 (두께 가운데) 넓이가 같은 원판 지름 (체적 일정) — 파푸스로 정확한 넓이 (diecalc.cup_area 와 따로 계산)."""
    Rm = R - t / 2
    r = rf + t / 2
    h = H - t / 2
    a = math.pi * (Rm - r) ** 2 + (math.pi * r / 2) * 2 * math.pi * (Rm - r + 2 * r / math.pi) + 2 * math.pi * Rm * (h - r)
    return math.sqrt(4 * a / math.pi)


def _dxf_plate():
    import tempfile

    import test_dxf2d as T
    with tempfile.TemporaryDirectory() as d:
        m = loader.load(T.drawing(d + "/w.dxf"))
        st = bc.BendSettings(material="SPCC")
        return unfold(m.solids[0], settings=st), st


def _blank_force():
    r, st = _dxf_plate()
    return dc.review(r, st, strip=False).loads[0].force_n


def _weight():
    r, _ = _dxf_plate()
    return mt.compute(r, 7.85).weight_kg


def _cpk():
    from hanil_unfold import inspection as ip
    c = ip.Char(1, "블랭크", "길이", 10.0, 0.3, -0.3, values=[10.0, 10.1, 9.9, 10.05, 9.95])
    return ip.stats(c).cpk


def _rate():
    from hanil_unfold import costing as cs
    p = dict(price=300e6, years=10, hours=4000, interest_pct=4, area_m2=50, rent_m2=40000, power_kw=30, load=0.5,
             kwh=150, maint_pct=3, wage=30000, crew=1)
    return cs.machine_rate(p)[0]


def _flange_cup(d=100.0, h=40.0, r=6.0, fd=160.0, rf=5.0):
    """플랜지 컵 넓이 (파푸스, cup_area 와 따로): 바닥 원 + 바닥 R 1/4 원환 + 벽 + 플랜지 R 1/4 원환 + 플랜지 고리."""
    R = d / 2
    a = math.pi * (R - r) ** 2
    a += (math.pi * r / 2) * 2 * math.pi * (R - r + 2 * r / math.pi)
    a += math.pi * d * (h - r - rf)
    a += (math.pi * rf / 2) * 2 * math.pi * (R + rf - 2 * rf / math.pi)
    a += math.pi / 4 * (fd ** 2 - (d + 2 * rf) ** 2)
    return a


def _m310():
    import dataclasses
    return dataclasses.replace(bc.MATERIAL_BY_CODE["SPCC"], tensile_mpa=310, r=1.0)


def cases():
    out = []
    n = 0
    for name, steps, t, k in SHEET:
        n += 1
        out.append((n, "판금 전개 (K 직접)", name, "해석", "Σ 직선 + Σ θ (R + K t)", flat_length(steps, t, k),
                    _sheet(steps, t, k), 1e-6))
    for name, rt in DIN:
        n += 1
        t = 2.0
        steps = [("L", 60), ("B", 90, rt * t), ("L", 40)]
        out.append((n, "판금 전개 (DIN 6935)", name, "DIN 6935 식", "k = 0.65 + 0.5 log10(r/s) (r/s ≥ 5 → 1), K = k/2",
                    _flat_din(steps, t), _din(steps, t), 1e-6))
    for R_out, t in ((30.0, 2.0), (100.0, 3.0)):
        n += 1
        out.append((n, "말기 (원통)", f"관 R{R_out:g} t{t:g}", "해석", "2π (Ri + K t)", 2 * math.pi * (R_out - t + 0.44 * t),
                    _tube(R_out, t, 0.44), 1e-6))
    for k in (0.3, 0.5):
        n += 1
        out.append((n, "말기 (원뿔)", f"깔때기 K{k:g}", "해석", "π (r1 + r2 − 2 (1−K) t cos α) · 빗변", _cone_exact(k),
                    _cone(k), 1e-3))
    n += 1
    out.append((n, "2D 도면 (DXF)", "블랭크 넓이 (R 모서리·구멍·장공)", "해석", "사각 − 모서리 (4−π)R² − 원 − 장공",
                200 * 100 - (4 - math.pi) * 100 - 2 * math.pi * 25 - (40 * 20 + math.pi * 100), _dxf("area"), 1e-9))
    n += 1
    out.append((n, "2D 도면 (DXF)", "절단 길이", "해석", "직선 + 2πR + 구멍 둘레 + 장공 둘레",
                2 * (180 + 80) + 2 * math.pi * 10 + 2 * 2 * math.pi * 5 + 2 * 40 + 2 * math.pi * 10, _dxf("len"), 1e-9))
    n += 1
    out.append((n, "성형품 (원스텝)", "원통 컵 블랭크 지름 Ø100 H50", "해석 (체적 일정)", "넓이가 같은 원판 √(4A/π)",
                _cup_exact(), _cup, 0.03))
    n += 1
    out.append((n, "금형 설계 (문헌 예제)", "Siebel 누르개 면압", "4ming Forming Handbook", "β 2 · d 100 · s 1 · Rm 310",
                1.16, lambda: dc.siebel_holder_pressure(2, 100, 1, _m310()), 0.01))
    n += 1
    out.append((n, "금형 설계 (문헌 예제)", "Oehler·Kaiser 다이 R", "4ming / Oehler·Kaiser", "D 200 · d 100 · s 1",
                5.25, lambda: dc.die_radius(200, 100, 1), 1e-9))
    n += 1
    out.append((n, "금형 설계 (문헌 예제)", "드로잉 틈새 최대", "4ming 「Ziehspalt」", "s 1 · β 2 → t √β",
                1.41, lambda: dc.draw_gap(1.0, 2.0, _m310())[1], 0.005))
    n += 1
    out.append((n, "금형 설계 (교재)", "V 굽힘력 C = 1 + 4t/V", "Schuler·DIN 식", "SPCC 414 · L 100 · t 2 · V 16",
                (1 + 8 / 16) * 414 * 100 * 4 / 16, lambda: dc.bend_force(bc.MATERIAL_BY_CODE["SPCC"], 100, 2, 16), 1e-9))
    n += 1
    out.append((n, "금형 설계 (교재)", "블랭킹력 F = L · t · τ", "해석", "외곽 2(180+80) + 2π·10 · t 1.6 · τ 0.8·414",
                (2 * (180 + 80) + 2 * math.pi * 10) * 1.6 * 0.8 * 414, _blank_force, 1e-4))
    n += 1
    out.append((n, "드로잉 블랭크", "플랜지 컵 넓이 (d100 h40 R6 플랜지 Ø160 R5)", "해석 (파푸스)",
                "바닥 + 1/4 원환 + 벽 + 1/4 원환 + 고리", _flange_cup(), lambda: dc.cup_area(100, 40, 6, 160, 5), 1e-12))
    n += 1
    out.append((n, "무게", "DXF 평판 SPCC t1.6", "해석", "넓이 × t × 7.85 g/cm³", _ex_area() * 1.6 * 7.85e-6,
                _weight, 1e-5))
    n += 1
    out.append((n, "성형 한계", "Keeler FLC0 (t 0.8, n 0.18)", "MetalForming 2019 예제", "(23.3 + 14.13 t) · n/0.21 → 약 30 %",
                0.30, lambda: math.exp(__import__("hanil_unfold.forming", fromlist=["x"]).keeler_flc0(0.8, 0.18)) - 1, 0.02))
    n += 1
    out.append((n, "품질", "Cpk (10 ± 0.3, 5 개)", "해석", "μ 10, s = √(0.00625) → 0.3 / 3s", 0.3 / (3 * math.sqrt(0.00625)),
                _cpk, 1e-9))
    n += 1
    out.append((n, "공차", "JIS B 0408 打抜き B 급 30~120", "MISUMI 普通公差", "±0.3", 0.3,
                lambda: __import__("hanil_unfold.tolerances", fromlist=["x"]).jis(100, "punch", "B"), 1e-12))
    n += 1
    out.append((n, "공차", "ISO 2768-m 120~400", "ISO 2768-1 표", "±0.5", 0.5,
                lambda: __import__("hanil_unfold.tolerances", fromlist=["x"]).iso(200, "m"), 1e-12))
    n += 1
    out.append((n, "원가", "기계 임률 (3 억 · 10 년 · 4000 h …)", "Maschinenstundensatz 정의",
                "3억/10/4000 + 3억/2·4%/4000 + 50·4만/4000 + 30·0.5·150 + 3억·3%/4000 + 3만",
                300e6 / 10 / 4000 + 300e6 / 2 * 0.04 / 4000 + 50 * 40000 / 4000 + 30 * 0.5 * 150 + 300e6 * 0.03 / 4000 + 30000,
                _rate, 1e-12))
    for name, c in _sc_ref().items():
        n += 1
        w, h = c["flat_size_mm"]
        out.append((n, "SolidCraft 교차 확인", name, "SolidCraft 0.23 sheet.flat_pattern",
                    f"그 STEP 을 열어 전개한 가로 × 세로 ({w:.4f} × {h:.4f}), K {c['k_factor']:g}", w * h,
                    _sc_flat(name, c["k_factor"]), 1e-6))
    return out


SC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "solidcraft")


def _sc_ref():
    import json
    with open(os.path.join(SC_DIR, "reference.json"), encoding="utf-8") as f:
        return json.load(f)["cases"]


def _sc_flat(name, k):
    def run():
        m = loader.load(os.path.join(SC_DIR, name + ".step"), use_cache=False)
        w, h = unfold(m.solids[0], k_factor=k).size
        return w * h
    return run


def _ex_area():
    return 200 * 100 - (4 - math.pi) * 100 - 2 * math.pi * 25 - (40 * 20 + math.pi * 100)


def run_all():
    """[(case…, 프로그램 값, 상대 오차, 통과)]"""
    rows = []
    for c in cases():
        got = c[6]()
        err = abs(got - c[5]) / abs(c[5]) if c[5] else abs(got)
        rows.append(c + (got, err, err <= c[7]))
    return rows
