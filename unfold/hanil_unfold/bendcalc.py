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


def _ratio(tensile_mpa):
    return round(0.16 * tensile_mpa / 414.0, 3)


# 대표 인장강도는 각 규격의 하한~일반 납품값 사이에서 고른 어림값이다.
MATERIALS = [
    Material("SPCC", "냉간압연강판 SPCC", MEDIUM, 414, 0.16, "[3] 냉연 연강 기준값 16%"),
    Material("SPHC", "열간압연강판 SPHC (산세 포함)", MEDIUM, 400, 0.15, "[3] 열연 산세 14~16%"),
    Material("SECC", "전기아연도금강판 SECC", MEDIUM, 414, 0.16, "SPCC 와 같은 소지 철판"),
    Material("SGCC", "용융아연도금강판 SGCC", MEDIUM, 414, 0.16, "SPCC 와 같은 소지 철판으로 어림"),
    Material("SS275", "일반구조용 SS275 (구 SS400)", MEDIUM, 450, _ratio(450), "[3] 인장강도 비례 어림"),
    Material("SUS304", "스테인리스 SUS304", HARD, 600, 0.21, "[3] 20~22%"),
    Material("SUS430", "스테인리스 SUS430", HARD, 480, _ratio(480), "[3] 인장강도 비례 어림"),
    Material("AL5052", "알루미늄 AL5052-H32", MEDIUM, 230, 0.12, "[3] 11~13%"),
    Material("AL1050", "알루미늄 AL1050-H24 (연질)", SOFT, 120, _ratio(120), "[3] 인장강도 비례 어림"),
    Material("AL6061", "알루미늄 AL6061-T6", HARD, 310, _ratio(310), "T6 는 균열 주의, R 을 크게"),
    Material("C1100", "동판 C1100 (1/2H)", SOFT, 270, _ratio(270), "[3] 인장강도 비례 어림"),
    Material("C2600", "황동 C2600", MEDIUM, 350, _ratio(350), "[3] 인장강도 비례 어림"),
]
MATERIAL_BY_CODE = {m.code: m for m in MATERIALS}

# ---------------------------------------------------------------- K 계수

AIR, BOTTOM, COIN = "air", "bottom", "coin"
PROCESS_NAMES = {AIR: "에어 벤딩", BOTTOM: "바텀 벤딩", COIN: "코이닝"}

# [1]  (r ≤ t, t < r ≤ 3t, r > 3t) 순서
K_TABLE = {
    AIR:    {SOFT: (0.33, 0.40, 0.50), MEDIUM: (0.38, 0.43, 0.50), HARD: (0.40, 0.45, 0.50)},
    BOTTOM: {SOFT: (0.42, 0.46, 0.50), MEDIUM: (0.44, 0.47, 0.50), HARD: (0.46, 0.48, 0.50)},
    COIN:   {SOFT: (0.38, 0.44, 0.50), MEDIUM: (0.41, 0.46, 0.50), HARD: (0.44, 0.47, 0.50)},
}


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

    @property
    def mat(self) -> Material:
        return MATERIAL_BY_CODE.get(self.material, MATERIALS[0])

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
        if self.method == K_MATERIAL:
            return (k_from_table(self.mat.group, r, t, self.process),
                    f"K 표 {GROUP_NAMES[self.mat.group]}·{PROCESS_NAMES[self.process]}")
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
