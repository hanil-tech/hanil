"""절곡 연신(굽힘 공제) 계산.

현장에서 말하는 "연신" 은 90° 한 번 접을 때 바깥 치수 합에서 빼는 길이, 곧 굽힘 공제(BD)다.

    바깥 치수 합 − Σ 연신 = 전개 길이

연신은 재질, 두께, 실제 절곡 R(상형 R 과 하형 V 폭으로 정해짐), 가공 방식에 따라 달라진다.
이 모듈은 아래 문헌의 공식과 표로 값을 계산하고, 회사에서 시험 절곡으로 잰 값이 있으면 그것을 먼저 쓴다.

참고 문헌
---------
[1] K 계수 표 (에어·바텀·코이닝, 연질·중간·경질)
    Machinery's Handbook 계열의 일반 K 계수 표. 여러 판금 실무서·The Fabricator 기사에 같은 값이 실려 있다.
        반지름           연질   중간   경질
      에어 벤딩
        0 ~ t           0.33   0.38   0.40
        t ~ 3t          0.40   0.43   0.45
        3t 초과          0.50   0.50   0.50
      바텀 벤딩
        0 ~ t           0.42   0.44   0.46
        t ~ 3t          0.46   0.47   0.48
        3t 초과          0.50   0.50   0.50
      코이닝
        0 ~ t           0.38   0.41   0.44
        t ~ 3t          0.44   0.46   0.47
        3t 초과          0.50   0.50   0.50

[2] DIN 6935 (Kaltbiegen von Flacherzeugnissen aus Stahl) 의 보정 계수
        k = 0.65 + 0.5·log10(r/s)   (r/s < 5),   r/s ≥ 5 이면 k = 1
    k 는 두께 절반 기준이라, 중립축 K 계수 = k / 2.
    (r/s = 5 에서 중립축이 두께 가운데로 온다는 실무 기준과 맞물린다.)

[3] 에어 벤딩의 자연 절곡 반지름 ("20% 규칙", The Fabricator 절곡 연재)
    상형 R 이 작으면 판은 상형을 따라가지 않고 하형 V 폭에 비례하는 반지름으로 휜다.
        냉간압연 연강(인장강도 60 ksi ≈ 414 MPa)  V 폭의 15~17 %  (기준 16 %)
        스테인리스 304                            V 폭의 20~22 %  (기준 21 %)
        알루미늄 5052-H32                         V 폭의 약 11~13 %
    다른 재질은 16 % × (인장강도 / 414 MPa) 로 어림한다.
    실제 반지름 = max(상형 R, 자연 반지름)

모든 값은 출발점이다. 문헌도 "시험 절곡으로 확인하라" 고 한다.
회사 연신 표(현장 측정값)를 넣으면 그 값이 우선한다.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field

# ---------------------------------------------------------------- 재질

SOFT, MEDIUM, HARD = "soft", "medium", "hard"
GROUP_NAMES = {SOFT: "연질", MEDIUM: "중간", HARD: "경질"}


@dataclass
class Material:
    code: str
    name: str
    group: str            # K 계수 표 [1] 의 분류
    tensile_mpa: float    # 대표 인장강도 (자연 반지름 어림에 사용)
    air_ratio: float      # 에어 벤딩 자연 반지름 / V 폭  [3]
    note: str = ""
    density: float = 7.85  # g/cm³ (무게 계산용)
    n: float = 0.20        # 가공 경화 지수 (성형품 원스텝 해석·성형 한계)
    r: float = 1.0         # 수직 이방성 (랭크포드 값)
    flc0: float = 0.0      # 평면 변형 성형 한계 (진변형률). 0 이면 Keeler 식
    yield_mpa: float = 0.0  # 항복 강도 (0 = diecalc.YIELD_E 대표값)
    e_gpa: float = 0.0      # 탄성 계수 (0 = 대표값)
    dr: float = 0.0         # 면내 이방성 Δr = (r0 − 2 r45 + r90) / 2 (귀 생김)
    source: str = "대표값"   # "대표값" / "밀시트 실측"

    def flc0_for(self, t):
        from .forming import keeler_flc0
        return self.flc0 if self.flc0 > 0 else keeler_flc0(t, self.n)


def _ratio(tensile_mpa):
    return round(0.16 * tensile_mpa / 414.0, 3)


# 대표 인장강도는 각 규격의 하한~일반 납품값 사이에서 고른 어림값이다.
MATERIALS = [
    Material("SPCC", "냉간압연강판 SPCC", MEDIUM, 414, 0.16, "[3] 냉연 연강 기준값 16%", n=0.19, r=1.3),
    Material("SPHC", "열간압연강판 SPHC (산세 포함)", MEDIUM, 400, 0.15, "[3] 열연 산세 14~16%", n=0.18, r=1.0),
    Material("SECC", "전기아연도금강판 SECC", MEDIUM, 414, 0.16, "SPCC 와 같은 소지 철판", n=0.19, r=1.3),
    Material("SGCC", "용융아연도금강판 SGCC", MEDIUM, 414, 0.16, "SPCC 와 같은 소지 철판으로 어림", n=0.18, r=1.2),
    Material("SS275", "일반구조용 SS275 (구 SS400)", MEDIUM, 450, _ratio(450), "[3] 인장강도 비례 어림", n=0.17, r=1.0),
    Material("SAPH440", "자동차 열연 SAPH440", MEDIUM, 440, _ratio(440), "자동차용, 인장강도 비례 어림", n=0.16, r=0.9),
    Material("SGARC440", "자동차 합금화용융아연 SGARC440", MEDIUM, 440, _ratio(440), "자동차용, 인장강도 비례 어림", n=0.17, r=1.1),
    Material("SPFC440", "자동차 고장력 냉연 SPFC440 (JSC440W 급)", MEDIUM, 440, _ratio(440), "차체 일반 고장력강",
             n=0.20, r=1.2),
    Material("SPFC590", "자동차 고장력 냉연 SPFC590", HARD, 590, _ratio(590), "고장력강, 스프링백 큼", n=0.15, r=0.9),
    Material("SPFC780", "자동차 초고장력 냉연 SPFC780 (DP780 급)", HARD, 780, _ratio(780), "멤버·필라 보강, 스프링백 큼",
             n=0.13, r=0.9),
    Material("SPFC980", "자동차 초고장력 냉연 SPFC980", HARD, 980, _ratio(980), "초고장력강, R 을 크게·스프링백 큼", n=0.08, r=0.8),
    Material("SPFC1180", "자동차 초고장력 냉연 SPFC1180 (DP·CP 1180 급)", HARD, 1180, _ratio(1180),
             "범퍼 빔·실 보강, 성형 거의 굽힘만 · R 크게", n=0.06, r=0.8),
    Material("SUS304", "스테인리스 SUS304", HARD, 600, 0.21, "[3] 20~22%", density=7.93, n=0.45, r=1.0, flc0=0.40),
    Material("SUS430", "스테인리스 SUS430", HARD, 480, _ratio(480), "[3] 인장강도 비례 어림", density=7.7, n=0.20, r=1.2, flc0=0.22),
    Material("AL5052", "알루미늄 AL5052-H32", MEDIUM, 230, 0.12, "[3] 11~13% · n 은 5052-O 값(H32 는 더 낮음)", density=2.68,
             n=0.13, r=0.7, flc0=0.18),
    Material("AL1050", "알루미늄 AL1050-H24 (연질)", SOFT, 120, _ratio(120), "[3] 인장강도 비례 어림", density=2.71, n=0.10, r=0.6, flc0=0.20),
    Material("AL6061", "알루미늄 AL6061-T6", HARD, 310, _ratio(310), "T6 는 균열 주의, R 을 크게", density=2.7, n=0.05, r=0.7, flc0=0.08),
    Material("C1100", "동판 C1100 (1/2H)", SOFT, 270, _ratio(270), "[3] 인장강도 비례 어림", density=8.94, n=0.30, r=0.9, flc0=0.30),
    Material("C2600", "황동 C2600", MEDIUM, 350, _ratio(350), "[3] 인장강도 비례 어림", density=8.53, n=0.40, r=0.9, flc0=0.35),
]
MATERIAL_BY_CODE = {m.code: m for m in MATERIALS}

# 밀시트 (소재 검사 증명서) 실측값 — 넣은 것만 대표값 대신 쓴다
MILL_KEYS = [("ys", "항복 강도 YS (MPa)"), ("ts", "인장 강도 TS (MPa)"), ("el", "연신율 El (%)"),
             ("n", "가공 경화 지수 n"), ("r0", "r 값 0°"), ("r45", "r 값 45°"), ("r90", "r 값 90°"),
             ("e", "탄성 계수 E (GPa)")]


def r_mean(r0, r45, r90):
    """평균 r̄ = (r0 + 2 r45 + r90) / 4,  면내 이방성 Δr = (r0 − 2 r45 + r90) / 2 (ISO 10113)."""
    return (r0 + 2 * r45 + r90) / 4, (r0 - 2 * r45 + r90) / 2


def with_mill(m: Material, mill: dict) -> Material:
    """밀시트 값으로 바꾼 재질. mill: {ys, ts, el, n, r0, r45, r90, e} (빈 값·0 은 대표값)."""
    import dataclasses
    v = {k: float(x) for k, x in (mill or {}).items() if x not in (None, "") and float(x) > 0}
    if not v:
        return m
    kw = {"source": "밀시트 실측"}
    if "ts" in v:
        kw["tensile_mpa"] = v["ts"]
        kw["air_ratio"] = _ratio(v["ts"]) if m.air_ratio == _ratio(m.tensile_mpa) else m.air_ratio * v["ts"] / m.tensile_mpa
    if "ys" in v:
        kw["yield_mpa"] = v["ys"]
    if "n" in v:
        kw["n"] = v["n"]
    if "e" in v:
        kw["e_gpa"] = v["e"]
    rs = [v.get(k) for k in ("r0", "r45", "r90")]
    if all(rs):
        kw["r"], kw["dr"] = r_mean(*rs)
    elif any(rs):
        kw["r"] = sum(x for x in rs if x) / sum(1 for x in rs if x)
    return dataclasses.replace(m, **kw)

# ---------------------------------------------------------------- K 계수

AIR, BOTTOM, COIN = "air", "bottom", "coin"
PROCESS_NAMES = {AIR: "에어 벤딩", BOTTOM: "바텀 벤딩", COIN: "코이닝"}

# [1]  (r ≤ t, t < r ≤ 3t, r > 3t) 순서
K_TABLE = {
    AIR:    {SOFT: (0.33, 0.40, 0.50), MEDIUM: (0.38, 0.43, 0.50), HARD: (0.40, 0.45, 0.50)},
    BOTTOM: {SOFT: (0.42, 0.46, 0.50), MEDIUM: (0.44, 0.47, 0.50), HARD: (0.46, 0.48, 0.50)},
    COIN:   {SOFT: (0.38, 0.44, 0.50), MEDIUM: (0.41, 0.46, 0.50), HARD: (0.44, 0.47, 0.50)},
}


# 계단 없는 K: 표의 세 구간 값을 구간 대표점 R/t = 0.7 (0~t), √3 (t~3t), 5 (3t 넘음 → 0.5) 에 두고
# log(R/t) 로 이어 붙인다. 표 (계단) 는 R/t 가 1·3 을 넘는 순간 K 가 0.05~0.07 뛰어 90° 한 번에 0.1 t 넘게
# 펼친 길이가 튄다 — 실제 굽힘은 R/t 에 따라 이어서 변한다 (DIN 6935 의 log 식과 같은 꼴, r/s 5 에서 0.5).
K_ANCHORS = (0.7, math.sqrt(3.0), 5.0)


def k_smooth(group: str, r: float, t: float, process: str = AIR) -> float:
    lo, mid, hi = K_TABLE[process][group]
    if t <= 0:
        return 0.5
    x = max(r / t, 1e-6)
    (x0, x1, x2), (k0, k1, k2) = K_ANCHORS, (lo, mid, hi)
    if x <= x0:
        return k0
    if x >= x2:
        return k2
    lx = math.log(x)
    if x <= x1:
        a = (lx - math.log(x0)) / (math.log(x1) - math.log(x0))
        return k0 + (k1 - k0) * a
    a = (lx - math.log(x1)) / (math.log(x2) - math.log(x1))
    return k1 + (k2 - k1) * a


def k_from_test(flat_len, leg_a, leg_b, angle_deg, r, t):
    """시험 절곡으로 K: 자른 길이 L 을 접어 바깥 치수 (가상 꼭짓점까지) a, b 를 재면
    연신 BD = a + b − L, BA = 2 tan(θ/2)(R + t) − BD, K = (BA/θ − R)/t. (K, 이 각도 BD, 90° BD)."""
    th = math.radians(angle_deg)
    bd = leg_a + leg_b - flat_len
    ba = 2 * math.tan(th / 2) * (r + t) - bd
    k = (ba / th - r) / t
    return k, bd, bend_deduction(math.pi / 2, r, k, t)


def k_from_table(group: str, r: float, t: float, process: str = AIR) -> float:
    lo, mid, hi = K_TABLE[process][group]
    eps = 1e-6 * max(1.0, t)      # 3D 모델에서 잰 값의 미세한 오차로 구간이 바뀌지 않게
    if r <= t + eps:
        return lo
    if r <= 3 * t + eps:
        return mid
    return hi


def k_din6935(r: float, t: float) -> float:
    """DIN 6935 보정 계수로 구한 중립축 K (= k/2)."""
    if t <= 0:
        return 0.5
    ratio = r / t
    if ratio >= 5:
        return 0.5
    # r 이 0 에 가까우면 로그가 발산하므로 공식이 쓰이는 범위(r/s ≥ 0.1) 안으로 묶는다.
    k = 0.65 + 0.5 * math.log10(max(ratio, 0.1))
    return max(0.0, min(1.0, k)) / 2


# ---------------------------------------------------------------- 기본 식

def bend_allowance(theta: float, r: float, k: float, t: float) -> float:
    """펼친 절곡부 길이 (theta: 라디안)."""
    return theta * (r + k * t)


def outside_setback(theta: float, r: float, t: float) -> float:
    return math.tan(theta / 2) * (r + t)


def bend_deduction(theta: float, r: float, k: float, t: float) -> float:
    """연신(굽힘 공제): 바깥 치수 합에서 빼는 길이."""
    return 2 * outside_setback(theta, r, t) - bend_allowance(theta, r, k, t)


def k_from_deduction90(bd: float, r: float, t: float) -> float:
    """90° 연신값에서 K 계수를 거꾸로 구한다 (다른 각도에 같은 K 를 쓴다)."""
    return ((2 * (r + t) - bd) / (math.pi / 2) - r) / t


def default_die_v(t: float) -> float:
    """하형 V 폭을 따로 정하지 않았을 때: 두께의 8배 (일반적인 다이 선택 기준)."""
    return 8 * t


# ---------------------------------------------------------------- 회사 연신 표

@dataclass
class ShopEntry:
    material: str
    thickness: float
    punch_r: float
    deduction90: float
    die_v: float = 0.0       # 0 이면 V 폭과 상관없이
    note: str = ""


@dataclass
class ShopTable:
    entries: list = field(default_factory=list)
    path: str = ""

    def find(self, material, t, punch_r, die_v):
        best = None
        for e in self.entries:
            if e.material != material or abs(e.thickness - t) > 0.005 or abs(e.punch_r - punch_r) > 0.005:
                continue
            if e.die_v and die_v and abs(e.die_v - die_v) > 0.05:
                continue
            # V 폭까지 맞는 항목을 우선
            if best is None or (e.die_v and not best.die_v):
                best = e
        return best

    def k_points(self, material, settings=None):
        """이 재질의 측정값 → [(R/t, K)] (실제 R: 에어 벤딩이면 상형 R 과 자연 R (V 폭) 중 큰 것)."""
        pts = []
        mat = MATERIAL_BY_CODE.get(material)
        process = settings.process if settings is not None else AIR
        ratio = (settings.mat.air_ratio if settings is not None and settings.material == material
                 else mat.air_ratio if mat else 0.16)
        for e in self.entries:
            if e.material != material or e.thickness <= 0:
                continue
            r = e.punch_r
            if process == AIR:
                r = max(r, ratio * (e.die_v or default_die_v(e.thickness)))
            k = k_from_deduction90(e.deduction90, r, e.thickness)
            if 0.05 < k < 0.7:
                pts.append((r / e.thickness, k))
        pts.sort()
        return pts

    def set(self, entry: ShopEntry):
        for i, e in enumerate(self.entries):
            if (e.material == entry.material and abs(e.thickness - entry.thickness) < 0.005
                    and abs(e.punch_r - entry.punch_r) < 0.005 and abs(e.die_v - entry.die_v) < 0.05):
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def remove(self, material, t, punch_r, die_v=0.0):
        self.entries = [e for e in self.entries if not (
            e.material == material and abs(e.thickness - t) < 0.005
            and abs(e.punch_r - punch_r) < 0.005 and abs(e.die_v - die_v) < 0.05)]

    @classmethod
    def load(cls, path):
        table = cls(path=path)
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            table.entries = [ShopEntry(**e) for e in data.get("entries", [])]
        return table

    def save(self, path=None):
        path = path or self.path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"entries": [asdict(e) for e in self.entries]}, f, ensure_ascii=False, indent=1)


def default_shop_table_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return os.path.join(base, "HanilUnfold", "연신표.json")


# ---------------------------------------------------------------- 절곡 조건

K_DIRECT, K_MATERIAL, K_DIN = "direct", "material", "din"
METHOD_NAMES = {
    K_DIRECT: "K 계수 직접 입력",
    K_MATERIAL: "재질별 K 표 (문헌 [1])",
    K_DIN: "DIN 6935 공식 (문헌 [2])",
}


@dataclass
class BendCalc:
    """절곡 하나의 계산 결과."""
    model_r: float        # 3D 모델의 안쪽 R
    r: float              # 계산에 쓴 안쪽 R
    k: float
    allowance: float      # 펼친 절곡부 길이 (BA)
    deduction: float      # 이 각도의 연신 (BD)
    deduction90: float    # 같은 조건 90° 연신
    flat_width: float     # 전개도에서 절곡부가 차지하는 폭
    source: str


@dataclass
class BendSettings:
    method: str = K_DIRECT
    k: float = 0.44
    material: str = "SPCC"
    process: str = AIR
    use_process_radius: bool = False   # True: 상형 R·V 폭으로 실제 R 을 정해 다시 계산
    punch_r: float = 0.0               # 상형 R (0 = 모델 R 사용)
    die_v: float = 0.0                 # 하형 V 폭 (0 = 두께의 8배)
    use_shop_table: bool = True
    shop_table: ShopTable | None = None
    mill: dict = field(default_factory=dict)   # 밀시트 실측값 (MILL_KEYS)

    @property
    def mat(self) -> Material:
        base = MATERIAL_BY_CODE.get(self.material, MATERIALS[0])
        return with_mill(base, self.mill) if self.mill else base

    def actual_radius(self, model_r: float, t: float) -> tuple:
        """(실제 안쪽 R, 설명)"""
        if not self.use_process_radius:
            return model_r, "모델 R"
        punch = self.punch_r if self.punch_r > 0 else model_r
        if self.process != AIR:
            return punch, "상형 R" if self.punch_r > 0 else "모델 R"
        v = self.die_v if self.die_v > 0 else default_die_v(t)
        natural = self.mat.air_ratio * v
        if natural > punch:
            return natural, f"자연 R (V{v:g}×{self.mat.air_ratio:.0%})"
        return punch, "상형 R" if self.punch_r > 0 else "모델 R"

    def k_for(self, r: float, t: float) -> tuple:
        """(K, 출처)"""
        if self.use_shop_table and self.shop_table is not None and self.method != K_DIRECT:
            punch = self.punch_r if (self.use_process_radius and self.punch_r > 0) else r
            v = self.die_v if self.die_v > 0 else 0.0
            e = self.shop_table.find(self.material, t, punch, v)
            if e is not None:
                return k_from_deduction90(e.deduction90, r, t), "회사 연신 표"
            pts = self.shop_table.k_points(self.material, self)
            if pts:                                          # 같은 재질 측정값을 R/t 로 이어 씀
                k = interp_k(pts, r / max(t, 1e-9), lambda x: self._formula_k(x * t, t)[0])
                return k, f"회사 연신 표 보간 ({len(pts)} 점)"
        return self._formula_k(r, t)

    def _formula_k(self, r, t):
        """(K, 출처) — 표·식."""
        if self.method == K_MATERIAL:
            return (k_smooth(self.mat.group, r, t, self.process),
                    f"K 표 {GROUP_NAMES[self.mat.group]}·{PROCESS_NAMES[self.process]} (R/t {r / max(t, 1e-9):.2f} 이어 붙임)")
        if self.method == K_DIN:
            return k_din6935(r, t), "DIN 6935"
        return self.k, "직접 입력"

    def resolve(self, theta: float, model_r: float, t: float) -> BendCalc:
        r, r_src = self.actual_radius(model_r, t)
        # 거의 접힌 헤밍(150° 초과)은 바깥 치수(꼭짓점)가 정해지지 않아 모델 R 그대로 쓴다.
        if theta > math.radians(150):
            r, r_src = model_r, "모델 R (헤밍)"
        k, k_src = self.k_for(r, t)
        ba = bend_allowance(theta, r, k, t)
        # 실제 R 이 모델과 다르면, 설계한 바깥 치수가 유지되도록 양쪽 플랜지 길이가 줄거나 는다.
        width = ba - 2 * math.tan(theta / 2) * (r - model_r)
        return BendCalc(
            model_r=model_r, r=r, k=k, allowance=ba,
            deduction=bend_deduction(theta, r, k, t) if theta < math.pi - 1e-6 else float("nan"),
            deduction90=bend_deduction(math.pi / 2, r, k, t),
            flat_width=width, source=f"{r_src}, {k_src}")

    def describe(self) -> str:
        parts = [METHOD_NAMES[self.method]]
        if self.method == K_DIRECT:
            parts.append(f"K={self.k:.3f}")
        else:
            parts.append(f"{self.mat.code} {PROCESS_NAMES[self.process]}")
        if self.use_process_radius:
            parts.append(f"상형 R{self.punch_r:g}" if self.punch_r > 0 else "상형 R=모델 R")
            parts.append(f"V{self.die_v:g}" if self.die_v > 0 else "V=8t")
        return ", ".join(parts)


def interp_k(pts, x, formula):
    """측정점 [(R/t, K)] 로 R/t = x 의 K. 측정점 사이는 log(R/t) 로 이어 붙이고, 바깥은 가장 가까운 측정점에서
    식 formula(x) 와 벌어진 만큼 식을 옮겨 쓴다 (측정이 식보다 0.03 크면 바깥도 0.03 크게)."""
    ux, uk = [], []
    for a, b in sorted((max(p[0], 1e-6), p[1]) for p in pts):
        if ux and abs(math.log(a) - math.log(ux[-1])) < 1e-6:
            uk[-1].append(b)
        else:
            ux.append(a)
            uk.append([b])
    uk = [sum(v) / len(v) for v in uk]
    x = max(x, 1e-6)
    for i in range(len(ux) - 1):
        if ux[i] <= x <= ux[i + 1]:
            a = (math.log(x) - math.log(ux[i])) / max(math.log(ux[i + 1]) - math.log(ux[i]), 1e-12)
            return uk[i] + (uk[i + 1] - uk[i]) * a
    j = 0 if x < ux[0] else len(ux) - 1
    return min(max(formula(x) + (uk[j] - formula(ux[j])), 0.15), 0.55)


def accuracy_notes(settings: "BendSettings", bends, t) -> list:
    """전개 정확도 알림: K 직접 입력이 R/t 에 맞지 않을 때, 에어 벤딩의 실제 R 이 모델 R 과 다를 때."""
    out = []
    if not bends or t <= 0:
        return out
    if settings.method == K_DIRECT:
        worst = None
        for b in bends:
            km = k_smooth(settings.mat.group, b.inner_radius, t, settings.process)
            dl = math.radians(b.angle_deg) * (settings.k - km) * t
            if worst is None or abs(dl) > abs(worst[0]):
                worst = (dl, b, km)
        dl, b, km = worst
        if abs(dl) > 0.1:
            out.append(f"정확도: K {settings.k:g} 고정 — B{b.number} R/t {b.inner_radius / t:.2f} 에서 재질 K 는 약 {km:.2f} "
                       f"(펼친 길이 절곡 하나에 {dl:+.2f} mm). [계산 방법] 을 [재질별] 또는 [DIN 6935] 로, "
                       "더 정확하게는 시험 절곡으로 연신 표를 채우세요.")
    if settings.process == AIR and not settings.use_process_radius:
        v = settings.die_v if settings.die_v > 0 else default_die_v(t)
        nat = settings.mat.air_ratio * v
        small = [b for b in bends if b.inner_radius + 0.3 * t < nat and b.angle_deg < 150]
        if small:
            b = min(small, key=lambda x: x.inner_radius)
            dl = sum(2 * math.tan(math.radians(x.angle_deg) / 2) * (nat - x.inner_radius)
                     - math.radians(x.angle_deg) * (nat - x.inner_radius) for x in small)
            out.append(f"정확도: 에어 벤딩 V{v:g} 의 실제 안쪽 R 은 약 {nat:.1f} (V × {settings.mat.air_ratio:.0%}) — "
                       f"모델 R {b.inner_radius:g} 보다 큼 ({len(small)} 곳). 바깥 치수를 맞추려면 펼친 길이가 약 "
                       f"{-dl:+.2f} mm 달라집니다: [상형 R · 하형 V 로 실제 R 계산] 을 켜세요.")
    return out


def deduction_table(settings: BendSettings, thicknesses, punch_rs):
    """연신 표: 두께 × 상형 R 마다 (90° 연신, 실제 R, K, 출처)."""
    rows = []
    for t in thicknesses:
        row = []
        for pr in punch_rs:
            s = BendSettings(**{**settings.__dict__, "use_process_radius": True, "punch_r": pr})
            c = s.resolve(math.pi / 2, pr, t)
            row.append(c)
        rows.append(row)
    return rows


STANDARD_THICKNESSES = [0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 1.6, 2.0, 2.3, 2.5, 3.0, 3.2, 4.0, 4.5, 5.0, 6.0]
STANDARD_PUNCH_R = [0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0]
