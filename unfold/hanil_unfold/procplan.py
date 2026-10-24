"""도면(3D)을 보고 금형 공정을 자동으로 짜는 규칙 (지식 기반 공정 설계).

1) 특징 읽기: 구멍이 바닥 판/어느 플랜지에 있는지, 절곡 시작선까지 거리, 맞은편 플랜지의 동축 구멍,
   서로 가까운 구멍, 헤밍·큰 각 절곡, 나란한 절곡, 성형품(자유곡면)과 성형 한계 위험.
2) 금형 형식: 부품 깊이·크기·생산량으로 순차 / 트랜스퍼 / 탠덤(단발) / 복합 / 금형 없이(레이저+절곡기).
3) 공정 순서 규칙 — 각 공정에 근거를 붙인다:
   R1  파일럿 구멍은 첫 공정에서 뚫고 다음 공정부터 위치를 잡는다.
   R2  구멍은 성형·절곡 전에 뚫는다 (펀치·다이가 평판에서 단순, 하중 작음).
   R3  절곡 시작선에서 3t 안의 구멍은 절곡 때 늘어나므로 절곡 뒤에 뚫는다 (문헌 2~4t).
   R4  맞은편 플랜지의 동축 구멍(위치 공차가 절곡을 건넘)은 절곡 뒤 캠 피어싱으로 한 번에.
   R5  가장자리 사이가 3t 미만인 구멍은 다이 벽이 약해 다른 공정으로 나눈다.
   R6  외곽(노칭·트림)은 절곡 전, 캐리어에서 떼는 분리는 마지막.
   R7  바깥(작은) 플랜지부터 접고, 크기가 같은 플랜지는 한 공정에서 (U 굽힘).
   R8  100° 넘는 절곡은 예비 굽힘 + 마무리, 150° 넘는 헤밍은 예비 헤밍(약 45°) + 눌러 접기.
   R9  자유곡면 성형품은 드로우(DR) → 트림·피어스(TR/PI) → 플랜지(FL) → 리스트라이크(RST)
       → 캠 피어스(CAM PI) (자동차 패널 금형 라인).
   R10 성형 한계를 넘는 곳이 있으면 예비 성형(DR 2공정) 또는 형상·재질 검토.
   R11 주름 가능 영역이 넓으면 드로우 비드·블랭크 홀더 압력 검토.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import bendcalc as bc
from . import diecalc as dc

RULES = {
    "R1": "파일럿 구멍은 첫 공정에서 뚫고 다음 공정부터 위치를 잡는다",
    "R2": "구멍은 성형·절곡 전 평판에서 뚫는다",
    "R3": "절곡 시작선에서 3t 안의 구멍은 늘어나므로 절곡 뒤에 뚫는다 (문헌 2~4t)",
    "R4": "맞은편 플랜지의 동축 구멍은 절곡 뒤 캠 피어싱으로 함께 (위치 공차)",
    "R5": "가장자리 사이 3t 미만의 구멍은 다이 벽이 약해 공정을 나눈다",
    "R6": "외곽 노칭·트림은 절곡 전, 분리는 마지막",
    "R7": "바깥(작은) 플랜지부터, 같은 크기 플랜지는 한 공정 (U 굽힘)",
    "R8": "100° 넘는 절곡은 예비 굽힘 + 마무리, 헤밍은 예비 헤밍 + 눌러 접기",
    "R9": "자유곡면 성형품: DR → TR/PI → FL → RST → CAM PI (자동차 패널 라인)",
    "R10": "성형 한계를 넘는 곳은 예비 성형(DR 2공정) 또는 형상·재질 검토",
    "R11": "주름 가능 영역이 넓으면 드로우 비드·블랭크 홀더 압력 검토",
    "T1": "깊거나 큰 부품은 트랜스퍼·탠덤, 얕고 작은 다특징 부품은 순차 금형",
    "T2": "생산량이 적으면 금형 대신 레이저 + 절곡기",
    "T3": "평판에 구멍만 있으면 복합 금형 (외곽·구멍 동심도)",
}

NEAR_BEND_T = 3.0       # R3
CLOSE_HOLES_T = 3.0     # R5


@dataclass
class HoleInfo:
    index: int              # NestPart.holes 순서
    label: str              # H1 … (diecalc 와 같은 번호)
    center: tuple
    size: float             # 지름 또는 짧은 변
    panel: str              # "바닥" 또는 "B3 플랜지"
    near_bend: tuple | None = None    # (절곡 번호, 시작선까지 거리)
    coaxial: str = ""       # 짝 구멍 이름
    after_bend: bool = False
    cam: bool = False
    group: int = 0          # 피어싱 공정 나눔 (0, 1 …)
    reason: str = ""


@dataclass
class Features:
    thickness: float
    material: str
    size: tuple
    holes: list
    bends: int
    parallel: bool
    big_angle: list         # 100° 넘는 절곡 번호
    hems: list              # 150° 넘는 절곡 번호
    forming: bool
    flc_split: float = 0.0
    flc_marginal: float = 0.0
    wrinkle: float = 0.0
    thinning: float = 0.0

    @property
    def max_dim(self):
        return max(self.size)


@dataclass
class Step:
    op: str
    detail: str
    rules: list = field(default_factory=list)
    force_n: float = 0.0


@dataclass
class Route:
    die_type: str
    die_reason: str
    steps: list
    features: Features
    notes: list = field(default_factory=list)
    ai: dict | None = None


def pair_names(hs):
    """구멍 이름들, 동축 짝은 한 번만 'H3↔H4'."""
    names = {h.label for h in hs}
    out = []
    for h in hs:
        if h.coaxial and h.coaxial in names:
            if h.label < h.coaxial:
                out.append(f"{h.label}↔{h.coaxial}")
        else:
            out.append(h.label)
    return ", ".join(out)


def _labels(result, holes):
    order = sorted(range(len(holes)), key=lambda i: (round(holes[i][:, 1].mean() - result.bbox[1], 1),
                                                     round(holes[i][:, 0].mean() - result.bbox[0], 1)))
    return {i: f"H{n}" for n, i in enumerate(order, 1)}


def features(result, settings: bc.BendSettings) -> Features:
    from .nesting import NestPart
    from .process import _folds, _inside_points
    t = result.thickness
    mat = settings.mat
    w, h = result.size
    fi = result.forming
    if fi is not None:
        split, marginal, wrinkle, _ = fi.flc_summary
        lo, hi = fi.thinning_range
        f = Features(t, mat.code, (w, h), [], 0, False, [], [], True, split, marginal, wrinkle, max(hi, 0))
        try:
            part = NestPart.from_result("p", result)
            lab = _labels(result, [np.asarray(x, float) for x in part.holes])
            for i, hh in enumerate(part.holes):
                c, dia, small = dc._hole_size(hh)
                f.holes.append(HoleInfo(i, lab[i], tuple(c), dia or small, "성형 면"))
        except ValueError:
            pass
        return f
    part = NestPart.from_result("p", result)
    holes = [np.asarray(x, float) for x in part.holes]
    lab = _labels(result, holes)
    res = max(max(w, h) / 300.0, 0.1)
    pts = _inside_points(part, 0.0, res)
    folds = _folds(result, 0.0, pts)
    parallel = bool(folds) and all(abs(folds[0].n[0] * g.n[1] - folds[0].n[1] * g.n[0]) < 0.02 for g in folds)
    infos = []
    for i, hh in enumerate(holes):
        c, dia, small = dc._hole_size(hh)
        on = [g for g in folds if float((c - g.a) @ g.n) > 0]
        # 가장 바깥(작은) 플랜지가 이 구멍이 있는 판
        panel = f"B{min(on, key=lambda g: g.size).number} 플랜지" if on else "바닥"
        near = None
        for b in result.bends:
            d = float(dc._seg_dist(hh, *b.line).min()) - b.allowance / 2
            if near is None or d < near[1]:
                near = (b.number, d)
        infos.append(HoleInfo(i, lab[i], tuple(c), dia or small, panel,
                              near if near and near[1] < 10 * t else None))
    # R4: 다른 플랜지에서 절곡선 방향 위치가 같은 같은 크기 구멍 = 동축
    if parallel:
        along = np.array([folds[0].n[1], -folds[0].n[0]])
        for a in infos:
            for b in infos:
                if a.index >= b.index or a.panel == b.panel or "플랜지" not in a.panel + b.panel:
                    continue
                if abs((np.array(a.center) - b.center) @ along) < 0.5 and abs(a.size - b.size) < 0.1:
                    a.coaxial, b.coaxial = b.label, a.label
    for hi_ in infos:
        if hi_.coaxial:
            hi_.after_bend, hi_.cam = True, True
            hi_.reason = "R4"
        elif hi_.near_bend and hi_.near_bend[1] < NEAR_BEND_T * t:
            hi_.after_bend = True
            hi_.cam = hi_.panel != "바닥"
            hi_.reason = "R3"
        else:
            hi_.reason = "R2"
    # R5: 가까운 구멍끼리 다른 공정 (탐욕 색칠)
    pre = [x for x in infos if not x.after_bend]
    for a in pre:
        used = set()
        for b in pre:
            if b is a or b.index > a.index:
                continue
            if dc._poly_dist(holes[a.index], holes[b.index]) < CLOSE_HOLES_T * t:
                used.add(b.group)
        g = 0
        while g in used:
            g += 1
        a.group = g
        if g:
            a.reason += ",R5"
    angles = {b.number: b.angle_deg for b in result.bends}
    return Features(t, mat.code, (w, h), infos, len(result.bends), parallel,
                    [n for n, a in angles.items() if 100 < a <= 150],
                    [n for n, a in angles.items() if a > 150], False)


def die_type(f: Features, qty: int):
    """(형식, 근거)."""
    if f.forming:
        if f.max_dim > 600:
            return "탠덤 라인 (공정별 단발 금형)", "큰 성형품 — 트랜스퍼 이송이 어려움 [T1]"
        if qty >= 100_000:
            return "트랜스퍼 금형", "성형 깊이가 있는 부품, 생산량 많음 [T1]"
        return "단발 금형 여러 대", "성형품, 생산량 적음 [T1]"
    if qty < 5_000:
        return "금형 없이 레이저 절단 + 절곡기", f"연 {qty:,} 개 — 금형비 회수 어려움 [T2]"
    if f.bends == 0:
        if f.max_dim <= 500 and qty >= 20_000:
            return "복합 금형 (블랭킹 + 피어싱 한 번에)", "평판 + 구멍, 외곽·구멍 위치가 한 번에 정해짐 [T3]"
        return "블랭킹 금형 + 피어싱 금형 (또는 레이저)", "평판, 크거나 생산량 보통 [T3]"
    if f.max_dim <= 400 and qty >= 100_000:
        return "순차(프로그레시브) 금형", f"작은 다특징 판금 ({f.max_dim:.0f} mm), 연 {qty:,} 개 [T1]"
    if qty >= 100_000:
        return "트랜스퍼 금형", f"전개 {f.max_dim:.0f} mm — 스트립으로 이송하기 큼 [T1]"
    return "단발 금형 (블랭킹·피어싱 + 절곡 금형)", f"연 {qty:,} 개 — 순차 금형비가 부담 [T1]"


def route(result, settings: bc.BendSettings, qty=100_000) -> Route:
    f = features(result, settings)
    t = f.thickness
    mat = settings.mat
    tau = dc.shear_strength(mat)
    kind, why = die_type(f, qty)
    steps, notes = [], []

    def hole_len(hs):
        return sum(math.pi * h.size for h in hs)

    if f.forming:
        if f.flc_split > 0.001:
            steps.append(Step("DR1 예비 성형", "성형 한계 넘는 곳을 두 번에 나눠 당김", ["R10"]))
        steps.append(Step("DR 드로우", f"블랭크 홀더·드로우 비드로 성형 (최대 얇아짐 {f.thinning:.0%})", ["R9"]))
        if f.wrinkle > 0.05:
            notes.append(f"주름 가능 영역 {f.wrinkle:.0%} — 드로우 비드·홀더 압력 검토 [R11]")
        steps.append(Step("TR/PI 트림·피어스", f"외곽 다듬기 + 구멍 {len(f.holes)}개", ["R9"],
                          hole_len(f.holes) * t * tau))
        steps.append(Step("FL 플랜지", "트림한 가장자리 세우기 (도면의 플랜지·헤밍 면)", ["R9"]))
        steps.append(Step("RST 리스트라이크", "작은 R·면 정밀도 바로잡기 (필요하면)", ["R9"]))
        steps.append(Step("CAM PI 캠 피어스", "옆 벽의 구멍 (있으면)", ["R9"]))
        if f.flc_split > 0.001:
            notes.append(f"성형 한계(FLC)를 넘는 곳 {f.flc_split:.1%} [R10]")
        return Route(kind, why, steps, f, notes)

    pre = [h for h in f.holes if not h.after_bend]
    post = [h for h in f.holes if h.after_bend]
    groups = sorted({h.group for h in pre})
    steps.append(Step("피어싱 1" if len(groups) > 1 else "피어싱",
                      "파일럿 + " + (", ".join(h.label for h in pre if h.group == 0) or "제품 구멍 없음"),
                      ["R1", "R2"], hole_len([h for h in pre if h.group == 0]) * t * tau))
    for g in groups[1:]:
        hs = [h for h in pre if h.group == g]
        steps.append(Step(f"피어싱 {g + 1}", ", ".join(h.label for h in hs) + " (가까운 구멍 나눔)", ["R5"],
                          hole_len(hs) * t * tau))
    steps.append(Step("노칭 · 외곽", "외곽 따내기 (캐리어 연결부 남김)", ["R6"]))
    if f.bends:
        steps.append(Step("절곡", f"{f.bends}곳 — 바깥 플랜지부터"
                          + (f", 예비 굽힘 B{', B'.join(map(str, f.big_angle))}" if f.big_angle else "")
                          + (f", 헤밍 B{', B'.join(map(str, f.hems))}" if f.hems else ""),
                          ["R7"] + (["R8"] if f.big_angle or f.hems else [])))
    if post:
        cam = [h for h in post if h.cam]
        flat = [h for h in post if not h.cam]
        if flat:
            steps.append(Step("후 피어싱", ", ".join(f"{h.label} (B{h.near_bend[0]} 에서 {h.near_bend[1]:.1f})"
                                                     for h in flat), ["R3"], hole_len(flat) * t * tau))
        if cam:
            steps.append(Step("캠 피어싱", pair_names(cam),
                              sorted({h.reason for h in cam}), hole_len(cam) * t * tau))
    steps.append(Step("분리", "캐리어에서 떼기 / 컷오프", ["R6"]))
    return Route(kind, why, steps, f, notes)


def route_rows(rt: Route):
    return [[f"{i}", s.op, s.detail, " ".join(s.rules)] for i, s in enumerate(rt.steps, 1)]


def hole_rows(rt: Route):
    out = []
    for h in rt.features.holes:
        when = "절곡 뒤 캠" if h.cam else "절곡 뒤" if h.after_bend else f"절곡 전 (피어싱 {h.group + 1})"
        near = f"B{h.near_bend[0]} {h.near_bend[1]:.1f}" if h.near_bend else "-"
        out.append([h.label, f"Ø{h.size:.1f}", h.panel, near, h.coaxial or "-", when, h.reason])
    return out


# ---------------------------------------------------------------- AI 검토 (도면 PDF)

AI_SCHEMA = {
    "type": "object",
    "properties": {
        "die_type": {"type": "string"},
        "die_reason": {"type": "string"},
        "steps": {"type": "array", "items": {
            "type": "object",
            "properties": {"op": {"type": "string"}, "detail": {"type": "string"},
                           "reason": {"type": "string"}},
            "required": ["op", "detail", "reason"], "additionalProperties": False}},
        "drawing_notes": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["die_type", "die_reason", "steps", "drawing_notes", "warnings"],
    "additionalProperties": False,
}

AI_SYSTEM = (
    "당신은 한국 프레스 금형 공정 설계자입니다. 프로그램이 3D 모델에서 읽은 특징과, 문헌 규칙으로 만든 "
    "공정 초안이 주어집니다. 도면 PDF 가 있으면 공차(위치도·동축도), 버링·탭·엠보·비드·헤밍 표시, "
    "버 방향, 재질·열처리·표면처리 주기를 읽어 공정 초안을 바로잡으세요. 규칙 번호(R1~R11, T1~T3)를 "
    "근거로 쓰고, 도면에서 읽은 근거는 '도면:' 으로 시작하세요. 모르는 것은 지어내지 말고 warnings 에 "
    "확인할 점으로 적으세요. 모든 글은 한국어로, 짧게."
)


def ai_review(rt: Route, pdf_path=None, qty=100_000, api_key=None, client=None, effort="high"):
    import base64
    import json

    from .ai_bom import MAX_PDF_BYTES, MODEL
    if client is None:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    f = rt.features
    data = {
        "material": f.material, "thickness_mm": f.thickness, "flat_size_mm": [round(x, 1) for x in f.size],
        "annual_qty": qty, "forming_part": f.forming, "bends": f.bends, "parallel_bends": f.parallel,
        "holes": [{"name": h.label, "size": round(h.size, 2), "panel": h.panel,
                   "near_bend": list(h.near_bend) if h.near_bend else None, "coaxial": h.coaxial}
                  for h in f.holes],
        "flc": {"split": f.flc_split, "marginal": f.flc_marginal, "wrinkle": f.wrinkle},
        "draft": {"die_type": rt.die_type, "steps": [[s.op, s.detail, s.rules] for s in rt.steps]},
        "rules": RULES,
    }
    content = []
    if pdf_path:
        with open(pdf_path, "rb") as fh:
            raw = fh.read()
        if len(raw) > MAX_PDF_BYTES:
            raise ValueError("PDF 가 너무 큽니다 (30 MB 이하).")
        content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                       "data": base64.standard_b64encode(raw).decode("ascii")}})
    content.append({"type": "text", "text": "3D 특징과 공정 초안:\n" + json.dumps(data, ensure_ascii=False)
                    + ("\n\n도면을 읽고 공정을 바로잡아 주세요." if pdf_path else
                       "\n\n도면은 없습니다. 특징만으로 공정 초안을 검토해 주세요.")})
    with client.beta.messages.stream(
        model=MODEL, max_tokens=16000, system=AI_SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": AI_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("AI 가 이 요청을 처리하지 않았습니다 (거절).")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    rt.ai = json.loads(text)
    return rt.ai
