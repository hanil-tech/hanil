"""강건성 해석 (AutoForm Sigma 비슷하게): 소재·두께·마찰이 흩어질 때 성형 결과가 얼마나 흔들리나.

원스텝 (막) 변형률은 제품 모양으로 정해지므로 그대로 두고, 흩어지는 값으로 드로잉 보정 (drawcorr: 장력·인장 굽힘·
아이어닝) 과 성형 한계 (FLC: 두께·n) 를 다시 계산한다 — 한 번에 1 초 안팎이라 수십 번 돌릴 수 있다.
  흩어지는 값 (균등 분포, 라틴 하이퍼큐브):  두께 ± (기본 5 %) · n ± 10 % · r̄ ± 10 % · 인장강도 ± 5 % (항복도 같은 비)
                                             · 드로잉 효율 η_F ± 10 % (마찰·누르개 힘)
  결과: 삼각형마다 파단 확률 (한계 비 ≥ 1 인 표본 비) · 위험 확률 (≥ 0.8) · 한계 비 평균·표준 편차,
        표본마다 최대 한계 비·최대 얇아짐, 공정 능력 Cpk = (한계 − 평균) / 3σ (≥ 1.33 안정, 1 ~ 1.33 주의, < 1 불안정),
        어느 값이 가장 크게 흔드나 (최대 한계 비를 값들로 선형 회귀한 표준화 계수)
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc

PARAMS = [("t", "두께", 0.05), ("n", "n 값", 0.10), ("r", "r̄ 값", 0.10), ("ts", "인장강도", 0.05),
          ("eta", "드로잉 효율 η_F (마찰·누르개)", 0.10)]
THIN_LIMIT = 0.25          # formsim.THIN_MAX 와 같은 과도 얇아짐 한계


@dataclass
class Robust:
    n: int
    params: list                       # [(키, 이름, ± 비)]
    samples: np.ndarray                # (n, k) 값들의 비 (1 = 기준)
    risk_max: np.ndarray               # 표본별 최대 한계 비 (99.5 % 넓이)
    thin_max: np.ndarray               # 표본별 최대 얇아짐
    fail_area: np.ndarray              # 표본별 파단 넓이 비
    p_fail: np.ndarray                 # 삼각형별 파단 확률
    p_marg: np.ndarray                 # 삼각형별 위험 (≥ 0.8) 확률
    risk_mean: np.ndarray
    risk_std: np.ndarray
    nominal: dict = field(default_factory=dict)
    sens: list = field(default_factory=list)      # [(이름, 표준화 계수)] 큰 것부터
    seconds: float = 0.0

    def cpk(self, values, limit):
        mu, sd = float(np.mean(values)), float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        return (limit - mu) / (3 * sd) if sd > 1e-12 else float("inf")

    @property
    def cpk_risk(self):
        return self.cpk(self.risk_max, 1.0)

    @property
    def cpk_thin(self):
        return self.cpk(self.thin_max, THIN_LIMIT)

    @property
    def verdict(self):
        c = min(self.cpk_risk, self.cpk_thin)
        return "안정" if c >= 1.33 else "주의" if c >= 1.0 else "불안정"

    def rows(self):
        out = []
        for i in range(self.n):
            vals = [f"{self.samples[i, j] * 100 - 100:+.1f} %" for j in range(len(self.params))]
            out.append([i + 1] + vals + [round(float(self.risk_max[i]), 3), round(float(self.thin_max[i]) * 100, 1),
                                         round(float(self.fail_area[i]) * 100, 2)])
        return out

    def head(self):
        return ["표본"] + [nm for _, nm, _ in self.params] + ["최대 한계 비", "최대 얇아짐 %", "파단 넓이 %"]

    def summary(self):
        lines = [f"표본 {self.n} 개 ({self.seconds:.1f} 초) — 판정 {self.verdict}: 최대 한계 비 평균 "
                 f"{np.mean(self.risk_max):.3f} · σ {np.std(self.risk_max, ddof=1):.3f} · 범위 "
                 f"{self.risk_max.min():.3f} ~ {self.risk_max.max():.3f} → Cpk {_fmt(self.cpk_risk)} (한계 1.0)",
                 f"최대 얇아짐 평균 {np.mean(self.thin_max):.1%} · 범위 {self.thin_max.min():.1%} ~ {self.thin_max.max():.1%}"
                 f" → Cpk {_fmt(self.cpk_thin)} (한계 {THIN_LIMIT:.0%})",
                 f"파단이 생긴 표본 {int((self.fail_area > 1e-3).sum())} / {self.n} · 파단 확률 10 % 넘는 넓이 "
                 f"{self._area_frac(self.p_fail > 0.1):.2%}"]
        if self.sens:
            lines.append("가장 크게 흔드는 값: " + " · ".join(f"{nm} {c:+.2f}" for nm, c in self.sens[:3])
                         + " (최대 한계 비에 대한 표준화 회귀 계수 — + 는 값이 클수록 위험)")
        return lines

    def _area_frac(self, mask):
        w = self.nominal.get("w")
        if w is None:
            return float(np.mean(mask))
        return float(w[mask].sum())


def _fmt(c):
    return "∞" if not math.isfinite(c) else f"{c:.2f}"


def _lhs(n, k, rng):
    """라틴 하이퍼큐브 (−1 ~ 1)."""
    u = (np.argsort(rng.random((k, n)), axis=1).T + rng.random((n, k))) / n
    return 2 * u - 1


def _wq(x, w, q):
    o = np.argsort(x)
    c = np.cumsum(w[o])
    return float(x[o][min(np.searchsorted(c, q * c[-1]), len(o) - 1)])


def run(result, settings: bc.BendSettings, n=24, seed=1, scatter=None, progress=None) -> Robust:
    """전개 결과 (성형 모드) 의 강건성 해석. scatter: {키: ± 비} 로 기본 흩어짐을 바꿈."""
    import time

    from . import drawcorr
    from .forming import flc_risk
    fi = result.forming
    if fi is None or fi.V is None:
        raise ValueError("성형 해석 (3D 성형품) 결과에서만 강건성 해석을 합니다")
    t0 = time.time()
    mat = settings.mat
    t = result.thickness
    sc = dict((k, s) for k, _, s in PARAMS)
    sc.update(scatter or {})
    params = [(k, nm, sc[k]) for k, nm, _ in PARAMS]
    base_major, base_minor = fi.membrane if fi.membrane is not None else (fi.major, fi.minor)
    use_corr = fi.membrane is not None
    w = fi._weights()
    keep = np.ones(len(fi.F), bool)
    if getattr(fi, "filled", None) is not None:
        keep &= ~fi.filled
    rng = np.random.default_rng(seed)
    X = _lhs(n, len(params), rng)
    S = 1 + X * np.array([s for _, _, s in params])
    risks = np.zeros((n, len(fi.F)))
    risk_max = np.zeros(n)
    thin_max = np.zeros(n)
    fail_area = np.zeros(n)
    eta0 = drawcorr.ETA_F
    try:
        for i in range(n):
            f = dict(zip([k for k, _, _ in params], S[i]))
            m2 = dataclasses.replace(mat, n=mat.n * f["n"], r=mat.r * f["r"], tensile_mpa=mat.tensile_mpa * f["ts"],
                                     yield_mpa=mat.yield_mpa * f["ts"] if getattr(mat, "yield_mpa", 0) else 0)
            t2 = t * f["t"]
            e1, e2 = base_major, base_minor
            if use_corr:
                drawcorr.ETA_F = eta0 * f["eta"]
                try:
                    e1, e2, _ = drawcorr.correct(fi.V, fi.F, fi.U, base_major, base_minor, t2, m2)
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    pass
            flc0 = m2.flc0_for(t2) if fi.flc0 > 0 else 0.0
            rk = flc_risk(e1, e2, flc0, mat.code) if flc0 > 0 else np.zeros(len(e1))
            th = 1 - np.exp(-(e1 + e2))
            risks[i] = rk
            risk_max[i] = _wq(rk[keep], w[keep], 0.995)
            thin_max[i] = _wq(th[keep], w[keep], 0.995)
            fail_area[i] = float(w[(rk >= 1.0) & keep].sum())
            if progress:
                progress(i + 1, n)
    finally:
        drawcorr.ETA_F = eta0
    p_fail = (risks >= 1.0).mean(0)
    p_marg = (risks >= 0.8).mean(0)
    rob = Robust(n, params, S, risk_max, thin_max, fail_area, p_fail, p_marg, risks.mean(0), risks.std(0),
                 nominal=dict(w=w), seconds=time.time() - t0)
    # 민감도: 표준화 회귀 (값의 −1 ~ 1 → 최대 한계 비)
    if n > len(params) + 2 and np.std(risk_max) > 1e-9:
        A = np.column_stack([X, np.ones(n)])
        coef, *_ = np.linalg.lstsq(A, risk_max, rcond=None)
        std_c = coef[:-1] * X.std(0) / np.std(risk_max)
        rob.sens = sorted(((nm, float(c)) for (_, nm, _), c in zip(params, std_c)), key=lambda kv: -abs(kv[1]))
    return rob


ROBUST_VIEWS = ["파단 확률", "위험 확률 (한계 80 %)", "한계 비 흩어짐 σ"]


def colors(rob: Robust, view):
    """삼각형 색 · 범례 (formsim 그림 꼴)."""
    stops = np.array([(40, 90, 220), (60, 170, 90), (240, 220, 40), (220, 30, 30)], float)
    if view == ROBUST_VIEWS[2]:
        top = max(float(np.quantile(rob.risk_std, 0.99)), 0.02)
        v = np.clip(rob.risk_std / top, 0, 1)
        leg_vals = [f"σ {top * k / 3:.3f}" for k in range(4)]
    else:
        p = rob.p_fail if view == ROBUST_VIEWS[0] else rob.p_marg
        v = np.clip(p / 0.5, 0, 1)                     # 50 % 이상은 빨강
        leg_vals = [f"{50 * k / 3:.0f} %" + (" 이상" if k == 3 else "") for k in range(4)]
    pos = v * 3
    i = np.minimum(pos.astype(int), 2)
    f = (pos - i)[:, None]
    cols = stops[i] * (1 - f) + stops[i + 1] * f
    return cols, [(lv, tuple(stops[k])) for k, lv in enumerate(leg_vals)]
