"""성형 해석 설명: 그림 (색 지도) 만 보여 주지 않고, 문제 부위마다 어디에서 · 얼마나 · 왜 · 어떻게 고치는지를 글로.

1. 문제 부위 찾기 — 같은 성형성 존 (파단·파단 위험·과도 얇아짐·두꺼워짐·늘림 부족) 삼각형을 모서리로 이어
   덩어리로 묶고, 넓은 것부터 번호 ①②… 를 붙인다 (3D 그림에도 같은 번호).
2. 위치 이름 — 프레스 방향 높이와 면 기울기로 바닥 (펀치 면) · 펀치 R · 벽 · 다이 어깨 R · 플랜지 (누르개 면),
   사각 드로잉이면 귀 (모서리), 잘린 가장자리 (트림선·구멍) 에 닿으면 그것도 붙인다.
3. 원인 · 대책 — 존 × 위치별 현장 대책 (Marciniak·Duncan·Hu 「Mechanics of Sheet Metal Forming」, Schuler
   「Metal Forming Handbook」, AutoForm 「Formability」 판정 설명, 日本塑性加工学会 「プレス加工便覧」,
   AHSS Application Guidelines).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from . import formsim as fs

OK, WARN, NG = fs.OK, fs.WARN, fs.NG

# 위치 종류
BOTTOM, PUNCH_R, WALL, DIE_R, FLANGE, SURFACE = "bottom", "punch_r", "wall", "die_r", "flange", "surface"
REGION_NAMES = {BOTTOM: "바닥 (펀치 면)", PUNCH_R: "펀치 R (바닥 쪽 R)", WALL: "벽", DIE_R: "다이 어깨 R (플랜지 쪽 R)",
                FLANGE: "플랜지 (누르개 면)", SURFACE: "면"}
REGION_ORDER = [BOTTOM, PUNCH_R, WALL, DIE_R, FLANGE, SURFACE]

# 설명할 존 (번호, 가장 작은 넓이 비 — 이보다 작은 덩어리는 묶어 세지만 따로 번호를 주지 않음)
ISSUE_ZONES = [(0, 0.0005), (1, 0.001), (2, 0.001), (6, 0.004), (4, 0.05)]
MAX_ISSUES = 10

MEANING = {
    0: "성형 한계 곡선 (FLC) 을 넘게 늘어난 곳입니다. 실제 프레스에서 목이 생기거나 (네킹) 터집니다.",
    1: "아직 터지지는 않지만 한계의 80 % 를 넘어 여유가 20 % 도 안 되는 곳입니다. 소재 n·r 값 편차, 윤활 상태, "
       "누르개 힘 변동만으로 터질 수 있어 양산에서는 불량이 나기 쉽습니다.",
    2: f"두께가 {fs.THIN_MAX:.0%} 넘게 얇아지는 곳입니다. 터지지 않더라도 강도·강성이 떨어지고, 용접·도장·내식성 "
       "(도금층 손상) 에 문제가 생길 수 있어 보통 품질 기준에서 불합격으로 봅니다.",
    6: "재료가 둘레 방향으로 눌려 (압축) 두께가 5 % 넘게 두꺼워지는 곳입니다. 금형 면이 양쪽에서 잡아 주지 않으면 "
       "주름이 생기고, 다이 벽에 눌리는 곳이면 아이어닝 (훑기) 하중과 긁힘이 생깁니다.",
    4: "변형이 3 % 도 안 되는 곳입니다. 재료가 충분히 늘어나지 않아 가공 경화가 적고, 넓은 외판이면 손으로 누르면 "
       "들어가는 오일 캔·강성 부족, 스프링백 (형상 틀어짐), 면 굴곡 (서피스 결함) 이 생기기 쉽습니다.",
}

# (존, 위치) → (원인, [대책]) — 위치가 없으면 존의 기본값
CAUSE = {
    (0, PUNCH_R): ("펀치 R 에서는 재료가 펀치에 감기며 굽혀지는 동시에 벽의 당기는 힘을 다 받습니다 (굽힘 + 인장). "
                   "드로잉이 깊거나 펀치 R 이 작으면 이곳이 가장 먼저 터집니다 (컵 드로잉 파단의 대부분).",
                   ["펀치 R 을 키우기 (판 두께의 4~10 배, 적어도 4 t)",
                    "주름 누르개 힘을 줄이거나 다이 어깨 R 을 키워 재료가 더 잘 흘러 들어가게",
                    "다이 쪽 (플랜지) 윤활 좋게, 펀치 쪽은 마찰을 남겨 바닥이 붙잡히게",
                    "드로잉비가 크면 다단 드로잉 (재드로잉) 으로 나누기",
                    "블랭크를 작게 (필요 없는 플랜지 여유 줄이기)"]),
    (0, WALL): ("벽은 플랜지에서 끌려 들어오는 재료를 펀치가 당기는 길목이라 드로잉 힘을 그대로 받습니다. "
                "드로잉비가 한계 (LDR) 를 넘거나 플랜지가 잘 안 들어오면 벽이 늘어나 터집니다.",
                ["다단 드로잉으로 깊이 나누기 (첫 드로잉률 m 0.5~0.6)",
                 "누르개 힘·드로잉 비드를 줄이고 다이 어깨 R 키우기",
                 "n·r 값 큰 재질 (SPCE·DC04·DC06 급) 로"]),
    (0, DIE_R): ("다이 어깨 R 을 넘어가며 굽혔다 펴지면서 (굽힘-펴짐) 늘어나고, 마찰로 당기는 힘이 커집니다. "
                 "다이 R 이 작으면 이곳에서 터지거나 긁힙니다.",
                 ["다이 어깨 R 키우기 (판 두께의 5~10 배)", "다이 R 래핑·윤활", "누르개 힘 줄이기"]),
    (0, FLANGE): ("플랜지 (누르개 면) 가 늘어나며 터지는 곳 — 블랭크 모양이 맞지 않거나 볼록한 트림선을 따라 "
                  "재료가 바깥으로 늘어날 때 (스트레치 플랜지) 생깁니다.",
                  ["블랭크 모양을 전개 결과에 맞춰 다시 (이 곳의 재료 여유 늘리기)",
                   "트림을 성형 뒤로 (성형한 다음 자르기)", "누르개 힘 줄이기"]),
    (0, BOTTOM): ("바닥 (펀치 면) 이 크게 늘어나는 스트레치 성형입니다. 바닥에 볼록한 형상이 있거나 플랜지가 "
                  "꽉 잡혀 재료가 들어오지 못하면 바닥이 늘어나 터집니다.",
                  ["바닥 형상 (돌출·엠보) 높이 줄이거나 R 키우기",
                   "누르개 힘·락 비드를 줄여 플랜지 쪽 재료가 들어오게",
                   "펀치 윤활 좋게 (바닥에서 재료가 퍼지게)"]),
    (0, None): ("성형 한계를 넘게 늘어났습니다.",
                ["R 키우기", "깊이 나누기 (다단 드로잉)", "n 값 큰 재질로", "누르개 힘 줄이기"]),
    (2, None): ("얇아짐은 늘어남 (주 변형률 + 부 변형률) 이 큰 곳에서 생깁니다. 파단 위험 곳과 같은 원인이며 그보다 "
                "덜한 단계입니다.",
                ["파단 위험과 같은 대책 (R 키우기 · 누르개 힘 줄이기 · 윤활)",
                 "두께 기준이 엄하면 한 단계 두꺼운 소재로 검토"]),
    (6, FLANGE): ("드로잉에서 플랜지는 지름이 줄어들며 둘레 방향으로 눌립니다 (압축). 누르개가 잡아 주지 않으면 "
                  "플랜지 주름이 생깁니다.",
                  ["주름 누르개 힘 늘리기 (지금 계산한 면압보다 위로)", "드로잉 비드를 넣어 재료 흐름 조절",
                   "누르개 면 평탄도·평행도 확인 (틈이 두께보다 크면 주름)"]),
    (6, WALL): ("벽 위쪽 (다이 쪽) 으로 갈수록 플랜지에서 줄어든 재료가 들어와 두꺼워집니다. 다이 벽에 받쳐지는 "
                "드로잉 벽이면 정상 현상입니다.",
                ["다이 틈새를 두께 + 10 % 이상으로 (아이어닝·긁힘 막기)",
                 "받쳐 주는 면이 없는 벽 (경사 벽) 이면 주름 — 누르개 힘·비드 늘리기, 벽 각도 세우기"]),
    (6, DIE_R): ("다이 어깨 R 쪽은 플랜지에서 들어온 재료가 쌓여 두꺼워집니다. 정상 범위면 문제 없습니다.",
                 ["다이 틈새를 두께 + 10 % 이상으로", "두께가 많이 늘면 누르개 힘 늘리기"]),
    (6, BOTTOM): ("바닥 (펀치 면) 이 두꺼워지는 것은 받쳐 주는 면 없이 재료가 남는다는 뜻입니다 — 바닥 주름 · 꺼짐.",
                  ["바닥에 비드·형상을 넣어 늘려 주기", "패드 (역압) 로 바닥을 잡기", "블랭크를 줄이기"]),
    (6, None): ("둘레 방향 압축으로 두꺼워졌습니다. 금형이 양쪽에서 받쳐 주지 않으면 주름이 생깁니다.",
                ["주름 누르개 힘 · 드로잉 비드 늘리기", "남는 재료 (블랭크) 줄이기", "패드로 받치기"]),
    (4, None): ("넓고 평평하거나 얕은 면이라 재료가 거의 늘어나지 않습니다 (특히 자동차 외판 지붕·본네트 가운데).",
                ["드로잉 비드·락 비드를 넣어 플랜지를 잡고 면을 2~3 % 넘게 늘리기 (스트레치)",
                 "면에 약한 곡률 (크라운) 주기", "바인더 면 모양을 바꿔 가운데부터 닿게"]),
}
CAUSE[(1, PUNCH_R)] = CAUSE[(0, PUNCH_R)]
CAUSE[(1, WALL)] = CAUSE[(0, WALL)]
CAUSE[(1, DIE_R)] = CAUSE[(0, DIE_R)]
CAUSE[(1, FLANGE)] = CAUSE[(0, FLANGE)]
CAUSE[(1, BOTTOM)] = CAUSE[(0, BOTTOM)]
CAUSE[(1, None)] = CAUSE[(0, None)]
CORNER_CAUSE = ("사각 드로잉의 귀 (모서리) 는 원통 컵의 4 분의 1 처럼 재료가 둘레 방향으로 몰려 들어와, 곧은 변보다 "
                "훨씬 많이 늘어나고 (펀치 R 쪽) 두꺼워집니다 (플랜지 쪽). 귀 R 이 작고 깊을수록 심합니다 "
                f"(한 번에 깊이 ≤ {fs.BOX_HR:g} × 귀 R).")
CORNER_ACTIONS = [f"귀 R 키우기 (한 번에 깊이의 1/{fs.BOX_HR:g} 이상, 적어도 5 t)",
                  "귀 쪽 블랭크를 잘라내기 (코너 컷) — 귀로 몰리는 재료 줄이기",
                  "깊으면 재드로잉 (다단)", "귀 쪽만 누르개 힘을 낮추거나 비드를 곧은 변에만"]
EDGE_NOTE = ("잘린 가장자리 (트림선·구멍) 에 닿아 있습니다 — 펀칭한 가장자리는 버·미세 균열로 판 안쪽보다 먼저 "
             "터지므로 (가장자리 균열) 한 단계 더 조심하세요. 레이저·리밍으로 자르거나 버를 성형 안쪽으로.")

VIEW_HELP = {
    fs.VIEWS[0]: "성형성 존: 삼각형마다 성형 결과를 판정한 색입니다. 빨강 = 파단 (성형 한계 넘음), 주황 = 파단 위험 "
                 "(한계의 80 % 넘음), 노랑 = 두께 25 % 넘게 얇아짐, 초록 = 안전, 회색 = 늘림 부족 (3 % 안 됨, 외판이면 "
                 "강성·스프링백 주의), 하늘 = 압축 (2~5 % 두꺼워짐, 보통 괜찮음), 보라 = 두꺼워짐·주름 경향 (5 % 넘음). "
                 "동그라미 번호는 아래 '문제 부위' 표의 번호입니다.",
    fs.VIEWS[1]: "두께 변화 %: 처음 두께와 견준 두께 변화입니다. 빨강일수록 얇아짐, 초록 = 변화 없음, 파랑일수록 두꺼워짐 "
                 "(눈금 끝 ±20 %). 얇아지는 곳은 터짐 쪽, 두꺼워지는 곳은 주름 쪽을 봅니다.",
    fs.VIEWS[2]: "두께 mm: 성형 뒤 예상 두께입니다 (색은 두께 변화와 같음). 도면 최소 두께 기준과 바로 견주어 보세요.",
    fs.VIEWS[3]: "주 변형률: 가장 많이 늘어난 방향의 진변형률 ε1 입니다 (파랑 0 → 초록 → 노랑 → 빨강 = 1.2 × FLC0). "
                 "재료가 어디서 얼마나 늘어나는지 보여 주며, 늘림 부족 (회색) 곳은 거의 파랑입니다.",
    fs.VIEWS[4]: "성형 한계 비: (ε2, ε1) 점이 성형 한계 곡선 (FLC) 까지 간 정도입니다. 100 % = 한계 (빨강), "
                 "80 % 넘으면 파단 위험입니다. 같은 늘어남이라도 평면 변형 (ε2 ≈ 0) 쪽이 더 위험하게 나옵니다.",
    "FLD": "성형 한계도 (FLD): 가로 = 부 변형률 ε2, 세로 = 주 변형률 ε1, 점 하나가 삼각형 하나입니다. 곡선 (FLC) 위 "
           "점은 파단, 곡선 아래 띠 (20 %) 안은 파단 위험입니다. 점이 왼쪽 (ε2 < 0) 아래로 몰리면 드로잉 (플랜지 압축), "
           "오른쪽 위면 스트레치 (두 방향 늘림) 성형입니다.",
}

THICK_BINS = [(-1.0, -0.05, "두꺼워짐 5 % 넘음"), (-0.05, -0.02, "두꺼워짐 2~5 %"), (-0.02, 0.03, "거의 그대로 (−2 ~ +3 %)"),
              (0.03, 0.10, "얇아짐 3~10 %"), (0.10, 0.20, "얇아짐 10~20 %"), (0.20, fs.THIN_MAX, f"얇아짐 20~{fs.THIN_MAX:.0%}"),
              (fs.THIN_MAX, 10.0, f"얇아짐 {fs.THIN_MAX:.0%} 넘음")]


@dataclass
class Issue:
    no: int
    zone: int
    region: str                 # 위치 이름 (글)
    kind: str                   # 위치 종류 (BOTTOM …)
    corner: bool
    edge: bool
    area: float                 # mm²
    frac: float                 # 넓이 비
    count: int                  # 같은 존 같은 위치 덩어리 수 (이 번호에 묶인)
    center: tuple               # 모델 좌표 (x, y, z) mm
    thin_max: float             # 가장 많이 얇아짐 (+)
    thick_max: float            # 가장 많이 두꺼워짐 (+)
    risk_max: float
    e1_mean: float
    verdict: str
    value: str
    meaning: str
    cause: str
    actions: list
    tris: np.ndarray | None = None
    short: str = ""             # 위치 이름 (몇 곳 빼고)

    @property
    def zone_name(self):
        return fs.ZONES[self.zone][3]

    @property
    def mark(self):
        return circled(self.no)


@dataclass
class Explanation:
    verdict: str
    headline: str
    reasons: list = field(default_factory=list)       # 판정 이유 (글)
    issues: list = field(default_factory=list)
    regions: list = field(default_factory=list)       # [위치, 넓이 비, 평균 두께 변화, 최소 두께, 최대 두께, 최대 한계 비]
    thickness: list = field(default_factory=list)     # [구간, 넓이 비]
    process: list = field(default_factory=list)       # [항목, 값, 설명] — 드로잉비·귀·가장자리·하중
    advice: list = field(default_factory=list)        # 먼저 할 일 (순서대로)


def pct(f):
    return f"{f:.2%}" if f < 0.001 else f"{f:.1%}"


def circled(n):
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else f"({n})"


# ---------------------------------------------------------------- 위치

def _frame(fi):
    """(위 방향 zz, 수평 주축 a1, a2) — 위 = 열린 쪽 (paint_product 와 같은 방향)."""
    z0, _ = fs.press_direction(fi.V, fi.F)
    if z0 is None:
        return None, None, None
    zz = -z0
    P = fi.V - fi.V.mean(0)
    P = P - np.outer(P @ zz, zz)
    _, _, vt = np.linalg.svd(P[:: max(1, len(P) // 4000)], full_matrices=False)
    a1 = vt[0] - (vt[0] @ zz) * zz
    a1 /= max(np.linalg.norm(a1), 1e-12)
    return zz, a1, np.cross(zz, a1)


def regions(fa):
    """삼각형별 (위치 종류, 귀인가, 가장자리에 닿는가)."""
    from .forming import boundary_loops
    fi = fa.fi
    V, F = fi.V, fi.F
    m = len(F)
    kind = np.full(m, SURFACE, dtype=object)
    corner = np.zeros(m, bool)
    zz, a1, a2 = _frame(fi)
    nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
    if zz is not None:
        h = V @ zz
        lo, span = float(h.min()), float(np.ptp(h))
        depth_ok = span > 3 * fa.thickness
        hf = (h[F].mean(1) - lo) / max(span, 1e-9)
        c = np.abs(nrm @ zz)
        if depth_ok:
            flat, wall = c > 0.9, c < 0.4
            low = hf < 0.5
            kind[flat & low] = BOTTOM
            kind[flat & ~low] = FLANGE
            kind[wall] = WALL
            kind[~flat & ~wall & low] = PUNCH_R
            kind[~flat & ~wall & ~low] = DIE_R
            if fa.box:
                nh = nrm - np.outer(nrm @ zz, zz)
                nh /= np.maximum(np.linalg.norm(nh, axis=1), 1e-12)[:, None]
                corner = (~flat) & (np.maximum(np.abs(nh @ a1), np.abs(nh @ a2)) < 0.92)
                # 귀 둘레 (바닥·플랜지의 귀 쪽 포함): 두 주축 방향 모두 끝에서 3 × 귀 R 안
                C = V[F].mean(1) - V.mean(0)
                s1, s2 = C @ a1, C @ a2
                rho = 3 * fa.box[0]
                L1, L2 = float(np.max(np.abs((V - V.mean(0)) @ a1))), float(np.max(np.abs((V - V.mean(0)) @ a2)))
                corner |= (np.abs(s1) > L1 - rho) & (np.abs(s2) > L2 - rho)
    edge = np.zeros(m, bool)
    for lp in boundary_loops(F):
        on = np.zeros(len(V), bool)
        on[lp] = True
        edge |= on[F].any(1)
    return kind, corner, edge


def _side(fa, P, zz, a1, a2):
    """가운데에서 본 방향 (긴 쪽 · 짧은 쪽) 글."""
    if zz is None:
        return ""
    c = fa.fi.V.mean(0)
    d = P - c
    s1, s2 = float(d @ a1), float(d @ a2)
    L1 = float(np.ptp(fa.fi.V @ a1)) / 2
    L2 = float(np.ptp(fa.fi.V @ a2)) / 2
    parts = []
    if abs(s1) > 0.25 * L1:
        parts.append(f"긴 방향 {'+' if s1 > 0 else '−'} 쪽 끝" if abs(s1) > 0.7 * L1 else f"긴 방향 {'+' if s1 > 0 else '−'} 쪽")
    if abs(s2) > 0.25 * L2:
        parts.append(f"짧은 방향 {'+' if s2 > 0 else '−'} 쪽")
    return " · ".join(parts) if parts else "가운데"


# ---------------------------------------------------------------- 덩어리

def _components(F, sel):
    """sel 삼각형들을 모서리로 이은 덩어리 번호 (sel 아닌 것은 −1)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    idx = np.nonzero(sel)[0]
    lab = np.full(len(F), -1)
    if len(idx) == 0:
        return lab, 0
    E = np.sort(np.concatenate([F[idx][:, [0, 1]], F[idx][:, [1, 2]], F[idx][:, [2, 0]]]), axis=1)
    owner = np.tile(np.arange(len(idx)), 3)
    key = E[:, 0].astype(np.int64) * (int(F.max()) + 1) + E[:, 1]
    order = np.argsort(key, kind="stable")
    ks, os_ = key[order], owner[order]
    same = ks[1:] == ks[:-1]
    a, b = os_[:-1][same], os_[1:][same]
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(len(idx), len(idx)))
    n, sub = connected_components(g, directed=False)
    lab[idx] = sub
    return lab, n


def _majority(values, w):
    keys = list(dict.fromkeys(values.tolist()))
    tot = {k: float(w[values == k].sum()) for k in keys}
    return max(tot, key=tot.get)


def _issue_text(fa, zone, kind, corner, edge, thin_max, thick_max, risk_max, e1m):
    t = fa.thickness
    if zone in (0, 1):
        value = (f"한계 비 최대 {risk_max:.0%} · 얇아짐 최대 {thin_max:.1%} (두께 {t * (1 - thin_max):.2f} mm)")
    elif zone == 2:
        value = f"얇아짐 최대 {thin_max:.1%} (두께 {t * (1 - thin_max):.2f} mm, 기준 {fs.THIN_MAX:.0%})"
    elif zone == 6:
        value = f"두꺼워짐 최대 {thick_max:.1%} (두께 {t * (1 + thick_max):.2f} mm)"
    else:
        value = f"평균 주 변형률 {e1m:.1%} (기준 {fs.STRETCH_MIN:.0%})"
    cause, actions = CAUSE.get((zone, kind)) or CAUSE.get((zone, None)) or CAUSE[(2, None)]
    actions = list(actions)
    if corner and zone in (0, 1, 2, 6):
        cause = CORNER_CAUSE + " " + cause
        actions = CORNER_ACTIONS + [a for a in actions if a not in CORNER_ACTIONS]
    if edge and zone in (0, 1, 2):
        cause = cause + " " + EDGE_NOTE
    return value, MEANING[zone], cause, actions


def explain(fa) -> Explanation:
    """FormAnalysis → 설명."""
    if fa.mode != "forming" or fa.fi is None or fa.fi.V is None or fa.zone is None:
        return _explain_sheet(fa)
    fi = fa.fi
    F = fi.F
    V = fi.V
    w = fi._weights()                         # 판정 (zone_frac) 과 같은 넓이 가중
    total = 1.0
    prod_area = float(getattr(fi, "product_area", 0) or np.linalg.norm(fs._vector_area(V, F), axis=1).sum())
    e1, e2, th, rk = fa.fields
    kind, corner, edge = regions(fa)
    zz, a1, a2 = _frame(fi)
    centers = V[F].mean(1)
    ex = Explanation(verdict=fa.verdict, headline="")

    # 문제 부위 덩어리
    cand = []
    for z, min_frac in ISSUE_ZONES:
        if z in (0, 1, 2) and fa.zone_frac[z] <= 0.001:     # 판정에 안 들어가는 아주 작은 조각 (메시 끝)
            continue
        sel = fa.zone == z
        if not sel.any():
            continue
        lab, n = _components(F, sel)
        groups = {}
        for c in range(n):
            tri = np.nonzero(lab == c)[0]
            a = float(w[tri].sum())
            if a <= 0:
                continue
            k = _majority(kind[tri], w[tri])
            cr = bool(w[tri][corner[tri]].sum() > 0.4 * a)
            ed = bool(w[tri][edge[tri]].sum() > 0.3 * a)
            groups.setdefault(("corner" if cr else k, cr, ed), []).append((a, tri))
        for (k, cr, ed), parts in groups.items():
            parts.sort(key=lambda x: -x[0])
            a = sum(x[0] for x in parts)
            if a / total < min_frac and not (z in (0, 1, 2) and fa.zone_frac[z] > 0.001):
                continue
            tri = np.concatenate([x[1] for x in parts])
            if cr:
                k = _majority(kind[tri], w[tri] + 1e-30)
                if z in (0, 1, 2) and k == BOTTOM:      # 귀 바닥이 늘어나 터짐 = 귀 펀치 R 근처
                    k = PUNCH_R
            # 가장 심한 덩어리 (위치 점을 거기에)
            sev = rk if z in (0, 1) else th if z == 2 else -th if z == 6 else -e1
            big = max(parts, key=lambda x: float(sev[x[1]].max()))[1] if z != 4 else parts[0][1]
            # 위치 점 = 가장 나쁜 삼각형 (파단·위험은 한계 비, 얇아짐은 얇아짐, 두꺼워짐은 두꺼워짐)
            key = rk if z in (0, 1) else th if z == 2 else -th if z == 6 else -e1
            worst = big[int(np.argmax(key[big]))] if z != 4 else big[int(np.argmin(np.abs(
                np.linalg.norm(centers[big] - (centers[big] * w[big, None]).sum(0) / (w[big].sum() + 1e-30), axis=1))))]
            cand.append(dict(zone=z, kind=k, corner=cr, edge=ed, area=a * prod_area, frac=a / total, count=len(parts),
                             tris=tri, center=centers[worst],
                             thin_max=float(max(th[tri].max(), 0)), thick_max=float(max(-th[tri].min(), 0)),
                             risk_max=float(rk[tri].max()), e1m=float(np.average(e1[tri], weights=w[tri] + 1e-30))))
    rank = {z: i for i, (z, _) in enumerate(ISSUE_ZONES)}
    cand.sort(key=lambda c: (rank[c["zone"]], -c["area"]))
    for i, c in enumerate(cand[:MAX_ISSUES], 1):
        value, meaning, cause, actions = _issue_text(fa, c["zone"], c["kind"], c["corner"], c["edge"], c["thin_max"],
                                                     c["thick_max"], c["risk_max"], c["e1m"])
        name = REGION_NAMES[c["kind"]]
        if c["corner"]:
            name = "귀 (모서리) " + name
        if c["edge"]:
            name += " · 잘린 가장자리"
        side = _side(fa, c["center"], zz, a1, a2)
        if side:
            name += f" — {side}"
        if c["count"] > 1:
            name += f" ({c['count']} 곳, 위치는 가장 심한 곳)"
        ex.issues.append(Issue(i, c["zone"], name, c["kind"], c["corner"], c["edge"], c["area"], c["frac"], c["count"],
                               tuple(float(x) for x in c["center"]), c["thin_max"], c["thick_max"], c["risk_max"],
                               c["e1m"], fs.ZONES[c["zone"]][2], value, meaning, cause, actions, c["tris"]))

    # 위치별 표
    for k in REGION_ORDER:
        sel = (kind == k) & (w > 0)
        if not sel.any():
            continue
        a = float(w[sel].sum())
        ex.regions.append([REGION_NAMES[k], a / total, float(np.average(th[sel], weights=w[sel])),
                           fa.thickness * (1 - float(th[sel].max())), fa.thickness * (1 - float(th[sel].min())),
                           float(rk[sel].max())])
    if corner.any() and (w[corner] > 0).any():
        sel = corner & (w > 0)
        ex.regions.append(["귀 (모서리) 전체", float(w[sel].sum()) / total, float(np.average(th[sel], weights=w[sel])),
                           fa.thickness * (1 - float(th[sel].max())), fa.thickness * (1 - float(th[sel].min())),
                           float(rk[sel].max())])
    for lo, hi, name in THICK_BINS:
        sel = (th >= lo) & (th < hi)
        ex.thickness.append([name, float(w[sel].sum()) / total])

    _process(fa, ex)
    _reasons(fa, ex)
    return ex


def _process(fa, ex):
    if fa.ldr:
        beta, lim = fa.ldr
        ex.process.append(["드로잉비 β (블랭크 둘레 / 제품 둘레)", f"{beta:.2f} (한계 LDR {lim:.2f})",
                           "β 가 LDR 보다 크면 한 번에 당기지 못하고 벽·펀치 R 이 터집니다 — 재드로잉으로 나누세요."
                           if beta > lim else "한 번에 드로잉할 수 있는 범위입니다."])
    if fa.box:
        r, depth, hr = fa.box
        ex.process.append(["사각 드로잉 깊이 / 귀 R", f"{depth:.0f} / {r:g} = {hr:.1f} 배 (한계 {fs.BOX_HR:g})",
                           "귀가 원통 컵처럼 가장 어렵습니다. 한계를 넘으면 귀 R 을 키우거나 다단 드로잉."
                           if hr > fs.BOX_HR else "귀 R 대비 깊이가 한 번 드로잉 범위입니다."])
    if fa.edge and fa.edge[0] > 0.02:
        worst, where, lim = fa.edge
        txt = (f"{worst:.0%} / HER {lim:.0%}" if lim else f"{worst:.0%} (HER 값 없음)")
        note = ("잘린 가장자리가 둘레로 늘어나는 양입니다. 구멍 확장률 (HER) 에 가까우면 펀칭 가장자리부터 갈라집니다 — "
                "레이저·리밍 절단, 버를 안쪽으로, 플랜지 높이 줄이기.")
        if fa.edge_pt is not None:
            note += f" 가장 큰 곳: X {fa.edge_pt[0]:.0f}, Y {fa.edge_pt[1]:.0f}, Z {fa.edge_pt[2]:.0f}."
        ex.process.append([f"가장자리 늘림 ({where})", txt, note])
    for name, f, note in fa.loads:
        ex.process.append([name, f"{f / 1000:,.0f} kN ({f / fs.dc.TON:,.1f} tf)", note])
    ex.process.append(["권장 프레스", f"{fa.press_tonf:,.0f} tf", "하중 합 × 1.3 (여유 30 %) — 크랭크 프레스는 "
                       "하사점 앞 행정에서 능력이 떨어지므로 견적 화면의 능력 곡선도 보세요."])


def _reasons(fa, ex):
    fr = fa.zone_frac
    r = ex.reasons
    if fr[0] > 0.001:
        r.append(f"파단 존이 {fr[0]:.1%} 있습니다 → 부적합 (0.1 % 만 넘어도 실제로 터짐).")
    if fr[1] > 0.001:
        r.append(f"파단 위험 존이 {fr[1]:.1%} — 양산 편차로 터질 수 있음 (주의).")
    if fr[2] > 0.001:
        r.append(f"두께 {fs.THIN_MAX:.0%} 넘게 얇아지는 곳 {fr[2]:.1%} (최소 {fa.t_min:.2f} mm) (주의).")
    if fr[6] > 0.02:
        r.append(f"5 % 넘게 두꺼워지는 곳 {fr[6]:.1%} — 받쳐 주지 않는 면이면 주름 (주의).")
    if fa.ldr and fa.ldr[0] > fa.ldr[1]:
        r.append(f"드로잉비 {fa.ldr[0]:.2f} > 한계 {fa.ldr[1]:.2f} — 한 번에 못 당김, 다단 드로잉 필요 (주의).")
    if fa.box_ng:
        r.append(f"사각 드로잉 깊이가 귀 R 의 {fa.box[2]:.1f} 배 > {fs.BOX_HR:g} 배 — 다단 드로잉 필요 (주의).")
    if fa.edge_verdict != OK:
        r.append(f"잘린 가장자리 늘림 {fa.edge[0]:.0%} — 구멍 확장률 한계 근처·넘음 ({fa.edge_verdict}).")
    if fr[4] > 0.5:
        r.append(f"늘림 부족 {fr[4]:.0%} — 터질 걱정은 없지만 외판이면 강성·스프링백 확인 (판정에는 넣지 않음).")
    if not r:
        r.append("파단·파단 위험·과도 얇아짐·주름이 기준 넘는 곳이 없습니다.")
    bad = [i for i in ex.issues if i.zone in (0, 1, 2)]
    for i in bad:
        i.short = re.sub(r" \(\d+ 곳.*?\)$", "", i.region)
    if fa.verdict == NG:
        ex.headline = (f"부적합 — {bad[0].short} 에서 터집니다 ({bad[0].value})." if bad
                       else "부적합 — 아래 이유를 보세요.")
    elif fa.verdict == WARN:
        ex.headline = (f"주의 — {bad[0].short} 이 한계 근처입니다 ({bad[0].value})." if bad
                       else "주의 — 한 번에 성형하기 어렵거나 주름·가장자리 문제가 있습니다.")
    else:
        ex.headline = (f"적합 — 가장 많이 얇아지는 곳 {max(fa.thin_hi, 0):.0%} · 가장 큰 한계 비 {fa.risk_top:.0%} "
                       "로 여유가 있습니다.")
    seen = []
    for i in ex.issues:
        if i.zone == 4:
            continue
        for a in i.actions[:2]:
            if a not in seen:
                seen.append(a)
    if fa.ldr and fa.ldr[0] > fa.ldr[1] or fa.box_ng:
        seen.insert(0, "다단 드로잉 (재드로잉) 공정으로 나누기 — 금형 검토의 '자동 공정 설계' 참고")
    ex.advice = seen[:6]


def _explain_sheet(fa):
    """판금 (절곡) 부품 설명: 절곡마다 균열 판정 이유 · 대책, 스프링백 보정 읽는 법."""
    ex = Explanation(verdict=fa.verdict, headline="")
    t = fa.thickness
    for i, c in enumerate([c for c in fa.bends if c.verdict != OK], 1):
        e = 1 / (2 * c.radius / t + 1) if t > 0 else 0
        value = f"안쪽 R {c.radius:.2f} (R/t {c.radius / t:.2f}) · 바깥 면 늘어남 {e:.0%} · 최소 R 대비 {c.risk:.0%}"
        meaning = ("절곡 바깥 면이 재질 굽힘 한계보다 더 늘어나 갈라집니다 (바깥 면 균열)." if c.verdict == NG else
                   "최소 R 의 80 % 넘게 근접 — 압연 방향과 나란히 접거나 소재 편차가 있으면 갈라질 수 있습니다.")
        cause = (f"바깥 면 늘어남 e = 1/(2R/t + 1) 은 R/t 로만 정해집니다. {fa.material} 의 최소 R 은 R/t {c.r_min / t:g} "
                 f"({c.r_min:.2f} mm) — 이보다 작게 접으면 균열이 납니다 (90°, 압연 방향과 직각).")
        actions = [f"안쪽 R 을 {c.r_min:.2f} mm 이상으로 (상형 R·다이 V 폭 키우기)",
                   "압연 방향과 직각으로 접히게 블랭크 배치 (나란하면 R 을 1.5~2 배)",
                   "버 쪽이 절곡 안쪽이 되게 (버가 바깥이면 갈라짐 시작점)", "연성 좋은 재질·소둔 재로"]
        ex.issues.append(Issue(i, 0 if c.verdict == NG else 1, f"절곡 B{c.no} ({c.angle:.0f}°)", "bend", False, False,
                               0.0, 0.0, 1, (math.nan,) * 3, 0.0, 0.0, c.risk, c.strain, c.verdict, value, meaning,
                               cause, actions))
    if fa.bends:
        bad = [c for c in fa.bends if c.verdict == NG]
        warn = [c for c in fa.bends if c.verdict == WARN]
        if bad:
            ex.reasons.append(f"절곡 {', '.join(f'B{c.no}' for c in bad)} 의 안쪽 R 이 최소 R 보다 작음 → 부적합.")
        if warn:
            ex.reasons.append(f"절곡 {', '.join(f'B{c.no}' for c in warn)} 이 최소 R 근처 (주의).")
        if not ex.reasons:
            ex.reasons.append(f"모든 절곡의 안쪽 R 이 최소 R ({fa.bends[0].r_min:.2f} mm) 이상입니다.")
        sb = [c for c in fa.bends if math.isfinite(c.die_angle)]
        if sb:
            c = max(sb, key=lambda c: abs(c.die_angle - c.angle))
            ex.process.append(["스프링백 (가장 큰 곳)", f"B{c.no}: {c.angle:.1f}° → 보정 없이 {c.after:.1f}°",
                               f"금형에서 {c.die_angle:.1f}° 로 접어야 도면 각이 나옵니다 (오버 벤딩 · 바텀 · "
                               "코이닝으로 줄일 수 있음). R/t 가 크고 강도가 높을수록 많이 돌아갑니다."])
        names = ", ".join(i.region.split(" ")[1] for i in ex.issues if i.verdict == NG)
        ex.headline = {NG: f"부적합 — 절곡 {names} 의 바깥 면이 갈라집니다." if ex.issues else "부적합",
                       WARN: f"주의 — {ex.issues[0].region} 이 최소 R 근처입니다." if ex.issues else "주의",
                       OK: "적합 — 모든 절곡이 균열 없이 접힙니다."}[fa.verdict]
    else:
        ex.headline = "평판 부품 — 성형 판정할 곳이 없습니다."
        ex.reasons.append("절곡·성형이 없습니다.")
    for name, f, note in fa.loads:
        ex.process.append([name, f"{f / 1000:,.1f} kN ({f / fs.dc.TON:,.2f} tf)", note])
    ex.advice = list(dict.fromkeys(a for i in ex.issues for a in i.actions[:2]))[:5]
    return ex


# ---------------------------------------------------------------- 글 내보내기

ISSUE_HEAD = ["번호", "존", "위치", "넓이 비", "값", "판정"]


def issue_rows(ex):
    return [[i.mark, i.zone_name, i.region, i.frac if i.frac else "—", i.value, i.verdict] for i in ex.issues]


REGION_HEAD = ["위치", "넓이 비", "평균 두께 변화 (+ 얇아짐)", "최소 두께 mm", "최대 두께 mm", "최대 한계 비"]


def html(fa, ex=None) -> str:
    """설명 탭용 HTML."""
    ex = ex or fa.explain
    if ex is None:
        return "<p>설명을 만들지 못했습니다.</p>"
    col = {OK: "#2a8c3c", WARN: "#c87f00", NG: "#d22828"}
    out = [f"<h3 style='color:{col[ex.verdict]}'>{ex.headline}</h3>", "<p><b>판정 이유</b></p><ul>"]
    out += [f"<li>{r}</li>" for r in ex.reasons]
    out.append("</ul>")
    if ex.advice:
        out.append("<p><b>먼저 해 볼 대책</b></p><ol>" + "".join(f"<li>{a}</li>" for a in ex.advice) + "</ol>")
    if ex.issues:
        out.append("<p><b>문제 부위</b> (번호는 3D 그림의 동그라미 번호)</p>")
        for i in ex.issues:
            rgb = fs.ZONES[i.zone][1]
            pos = (f" · 모델 좌표 X {i.center[0]:.0f}, Y {i.center[1]:.0f}, Z {i.center[2]:.0f}"
                   if math.isfinite(i.center[0]) else "")
            area = f" · 넓이 {i.area:,.0f} mm² ({pct(i.frac)})" if i.frac else ""
            out.append(
                f"<table width='100%' cellspacing=0 cellpadding=4 style='margin-bottom:6px; border:1px solid #ccc'>"
                f"<tr><td style='background:rgb{rgb}; color:white' width=40><b style='font-size:15px'>{i.mark}</b></td>"
                f"<td style='background:#f3f5f9'><b>{i.zone_name}</b> — {i.region}{area}{pos}<br>"
                f"<span style='color:{col[i.verdict]}'><b>{i.value}</b></span></td></tr>"
                f"<tr><td></td><td><b>뜻</b>: {i.meaning}<br><b>원인</b>: {i.cause}<br><b>대책</b>:<ul>"
                + "".join(f"<li>{a}</li>" for a in i.actions) + "</ul></td></tr></table>")
    if ex.regions:
        out.append("<p><b>위치별 두께</b></p><table border=1 cellspacing=0 cellpadding=3><tr>"
                   + "".join(f"<th>{h}</th>" for h in REGION_HEAD) + "</tr>")
        for r in ex.regions:
            out.append(f"<tr><td>{r[0]}</td><td>{r[1]:.1%}</td><td>{r[2]:+.1%}</td><td>{r[3]:.2f}</td>"
                       f"<td>{r[4]:.2f}</td><td>{r[5]:.0%}</td></tr>")
        out.append("</table>")
    if ex.thickness:
        out.append("<p><b>두께 변화 분포</b> (넓이 비)</p><table border=1 cellspacing=0 cellpadding=3>")
        for name, f in ex.thickness:
            bar = "█" * int(round(f * 40))
            out.append(f"<tr><td>{name}</td><td align=right>{f:.1%}</td><td style='color:#1f4e8c'>{bar}</td></tr>")
        out.append("</table>")
    if ex.process:
        out.append("<p><b>공정 · 하중</b></p><table border=1 cellspacing=0 cellpadding=3>"
                   "<tr><th>항목</th><th>값</th><th>설명</th></tr>")
        out += [f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in ex.process]
        out.append("</table>")
    if fa.mode == "forming":
        out.append("<p><b>그림 읽는 법</b></p><ul>" + "".join(f"<li>{v}</li>" for v in VIEW_HELP.values()) + "</ul>")
    out.append("<p style='color:#888'>" + "<br>".join(fs.NOTES) + "</p>")
    return "".join(out)


def text_lines(fa, ex=None):
    """엑셀·PDF 용 (머리, 글) 줄 목록. 머리 = 'h' (제목) / 'i' (문제 부위 제목) / '' (본문)."""
    ex = ex or fa.explain
    if ex is None:
        return []
    L = [("h", ex.headline), ("h", "판정 이유")]
    L += [("", "• " + r) for r in ex.reasons]
    if ex.advice:
        L.append(("h", "먼저 해 볼 대책"))
        L += [("", f"{k}. {a}") for k, a in enumerate(ex.advice, 1)]
    if ex.issues:
        L.append(("h", "문제 부위 (번호 = 그림의 동그라미 번호)"))
        for i in ex.issues:
            pos = (f" · X {i.center[0]:.0f}, Y {i.center[1]:.0f}, Z {i.center[2]:.0f}" if math.isfinite(i.center[0])
                   else "")
            area = f" · {pct(i.frac)}" if i.frac else ""
            L.append(("i", f"{i.mark} {i.zone_name} — {i.region}{area}{pos} · {i.value}"))
            L.append(("", "뜻: " + i.meaning))
            L.append(("", "원인: " + i.cause))
            L.append(("", "대책: " + " / ".join(i.actions)))
    if ex.process:
        L.append(("h", "공정 · 하중"))
        L += [("", f"{a}: {b} — {c}") for a, b, c in ex.process]
    if fa.mode == "forming":
        L.append(("h", "그림 읽는 법"))
        L += [("", v) for v in VIEW_HELP.values()]
    return L


def marks(ex):
    """3D 그림에 찍을 (번호 글, 3D 점, RGB)."""
    if ex is None:
        return []
    return [(str(i.no), np.array(i.center), fs.ZONES[i.zone][1]) for i in ex.issues if math.isfinite(i.center[0])]
