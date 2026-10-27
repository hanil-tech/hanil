"""금형 표준 부품 규격 (볼트 · 카운터보어 · 다우얼 핀 · 스트리퍼 볼트 · 다이 스프링) 과 고르기.

값은 공개된 규격 발췌·업체 카탈로그에서 옮긴 일반값 — 발주 전에 쓰는 업체 표로 확인한다.
  육각 구멍 붙이 볼트 (JIS B 1176 / ISO 4762): 머리 dk · 높이 k = d (Mikipulley JIS B 1176 발췌)
  카운터보어 (볼트 구멍 d1 · 자리 D · 깊이): 금형 업체 표의 일반값 (MISUMI 기술 자료 꼴)
  스트리퍼 볼트 (ISO 7379 어깨 볼트): 어깨 Ø8/M6 · Ø10/M8 · Ø12/M10 · Ø16/M12
  다우얼 핀 (ISO 8734 m6): 구멍 H7 리머
  다이 스프링 (ISO 10243 각 단면 코일): 녹 (경하중) · 청 (중하중) · 적 (중강) · 황 (극중) —
    Ø10 × 25 의 스프링 상수 (Lesjöfors) 를 닮은꼴 (k ∝ D² / L) 로 넓힘, 최대 휨 (자유 길이의 %) 은 업체마다 다름
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# 육각 구멍 붙이 볼트: d → (머리 dk, 머리 높이 k, 볼트 구멍 d1, 카운터보어 D, 카운터보어 깊이, 탭 드릴)
SHCS = {5: (8.5, 5, 5.5, 9.5, 5.4, 4.2), 6: (10, 6, 6.6, 11, 6.5, 5.0), 8: (13, 8, 9, 14, 8.6, 6.8),
        10: (16, 10, 11, 17.5, 10.8, 8.5), 12: (18, 12, 14, 20, 13, 10.2), 16: (24, 16, 18, 26, 17.5, 14.0)}
SHCS_L = (10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140, 150)
ENGAGE = 1.5          # 강에 탭 — 물림 깊이 ≥ 1.5 d

# 스트리퍼 볼트 (ISO 7379): 어깨 Ø → (나사 M, 머리 dk, 머리 높이 k, 나사 길이)
STRIPPER = {8: (6, 13, 5.5, 11), 10: (8, 16, 7, 13), 12: (10, 18, 9, 16), 16: (12, 24, 11, 18)}
STRIPPER_L = (10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120)

# 다우얼 핀 (ISO 8734 m6)
DOWEL_L = (10, 12, 16, 20, 24, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100)

# 다이 스프링 (ISO 10243): 구멍 Ø (바깥) → 로드 Ø (안)
SPRING_D = {10: 5, 12.5: 6.3, 16: 8, 20: 10, 25: 12.5, 32: 16, 40: 20, 50: 25, 63: 38}
SPRING_L = (25, 32, 38, 44, 51, 64, 76, 89, 102, 115, 127, 152, 178, 203, 254, 305)
# 등급: (색, Ø10 × 25 상수 N/mm, 최대 휨 % 자유 길이)
SPRING_CLASS = {"경하중": ("녹색", 10.0, 0.35), "중하중": ("청색", 16.0, 0.30),
                "중강하중": ("적색", 25.0, 0.25), "극중하중": ("황색", 36.8, 0.20)}
LIFE = 0.8            # 오래 쓰기 (100 만 번 넘게): 최대 휨의 80 % 까지만


def up_std(x, series):
    """규격 길이에서 x 이상 가장 짧은 것 (없으면 가장 긴 것)."""
    for v in series:
        if v >= x - 1e-9:
            return float(v)
    return float(series[-1])


def down_std(x, series):
    """규격 길이에서 x 이하 가장 긴 것 (없으면 가장 짧은 것)."""
    best = series[0]
    for v in series:
        if v <= x + 1e-9:
            best = v
    return float(best)


def bolt_for(plate_long):
    return 6 if plate_long < 160 else 8 if plate_long < 300 else 10 if plate_long < 500 else 12


def stripper_for(force_per_bolt_n):
    """스트리퍼 볼트 어깨 Ø — 나사 골 단면이 스프링 힘 몫을 넉넉히 (인장 100 MPa 이하)."""
    for ds, (m, *_rest) in STRIPPER.items():
        if force_per_bolt_n <= 100 * math.pi / 4 * (0.8 * m) ** 2:
            return ds
    return 16


def spring_rate(D, L, cls):
    """스프링 상수 [N/mm] — Ø10 × 25 기준 상수에서 닮은꼴 비 (D/10)² · (25/L)."""
    return SPRING_CLASS[cls][1] * (D / 10.0) ** 2 * (25.0 / L)


@dataclass
class SpringPick:
    D: float
    L: float
    cls: str
    n: int
    rate: float          # 한 개 N/mm
    preload: float       # 끼울 때 눌림 mm
    stroke: float        # 일 행정 (스트리퍼 움직임 + 재연마 여유) mm
    pocket: float        # 펀치 플레이트 안 자리 깊이 (= 끼운 길이 − 스프링 사이)
    installed: float     # 끼운 길이 mm

    @property
    def color(self):
        return SPRING_CLASS[self.cls][0]

    @property
    def f_pre(self):
        return self.n * self.rate * self.preload

    @property
    def f_max(self):
        return self.n * self.rate * (self.preload + self.stroke)

    @property
    def defl_pct(self):
        return 100 * (self.preload + self.stroke) / self.L

    @property
    def limit_pct(self):
        return 100 * LIFE * SPRING_CLASS[self.cls][2]

    def label(self):
        return f"Ø{self.D:g} × {self.L:g} {self.cls} ({self.color})"


def pick_spring(force_n, stroke, pocket_max, sgap_range=(15.0, 45.0), d_max=50.0, n_range=(4, 24), lag=1.0):
    """펀치가 판에서 빠질 때 (하사점에서 진입 + t 올라감 = 끼움 눌림 + lag) 힘 ≥ 스트리핑 힘,
    끝 휨 ≤ 오래 쓰기 한계, 스프링 사이 (스트리퍼 ↔ 펀치 플레이트) 가 범위 안.
    스프링은 펀치 플레이트 자리 (깊이 ≤ pocket_max, 받침판에 닿음) 에 들어감. 개수 적고 짧은 것부터."""
    best = None
    for n in range(n_range[0], n_range[1] + 1, 2):
        for D in [d for d in SPRING_D if d <= d_max]:
            for cls in SPRING_CLASS:
                for L in SPRING_L:
                    k = spring_rate(D, L, cls)
                    s0 = max(force_n / (n * k) - lag, 1.0)
                    allow = LIFE * SPRING_CLASS[cls][2] * L
                    if s0 + stroke > allow:
                        continue
                    inst = L - s0
                    pocket = min(pocket_max, inst - sgap_range[0])
                    sgap = inst - pocket
                    if pocket < 0.3 * inst or not (sgap_range[0] - 1e-6 <= sgap <= sgap_range[1]) or sgap < stroke + 3:
                        continue
                    cand = SpringPick(D, float(L), cls, n, k, s0, stroke, pocket, inst)
                    # 개수 → 지름 (작은 것) → 길이 순
                    key = (n, D, L)
                    if best is None or key < best[0]:
                        best = (key, cand)
            if best is not None and best[0][0] == n:
                break
        if best is not None:
            return best[1]
    return None


def strongest_spring(stroke, pocket_max, n, sgap_max=60.0):
    """힘을 못 맞출 때: n 개로 펀치가 빠질 때 힘이 가장 큰 것 (끝 휨은 한계 안) — 판정은 '검토' 로."""
    best = None
    for D in SPRING_D:
        for cls in SPRING_CLASS:
            for L in SPRING_L:
                k = spring_rate(D, L, cls)
                s0 = LIFE * SPRING_CLASS[cls][2] * L - stroke
                if s0 < 1.0:
                    continue
                inst = L - s0
                pocket = min(pocket_max, inst - 15.0)
                sgap = inst - pocket
                if pocket < 0.3 * inst or sgap > sgap_max or sgap < stroke + 3:
                    continue
                f = n * k * s0
                if best is None or f > best[0]:
                    best = (f, SpringPick(D, float(L), cls, n, k, s0, stroke, pocket, inst))
    return best[1] if best else None
