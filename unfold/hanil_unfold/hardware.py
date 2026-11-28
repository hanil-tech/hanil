"""체결품 · 구매품 자동 판별 — 볼트 · 너트 · 와셔 · 리벳 · 핀 같은 것은 판금이 아니므로 열 때 알아서 제외한다.

이름 (STEP 제품 이름: 영문 · 한글 · KS/ISO/DIN/JIS 번호) 으로 먼저 보고, 이름이 없거나 '부품 N' 이면 모양으로 본다:
작고 (가장 긴 변 ≤ SIZE_MAX), 뭉툭하며 (상자 채움률 ≥ FILL_MIN, 가장 짧은 변 ≥ 가운데 변 × CHUNKY), 겉이 대부분
원통 · 원뿔 · 도넛면 (≥ ROUND_MIN) 인 솔리드 — 볼트 · 너트 · 핀 · 부시가 여기에 든다. 얇은 판 (판금) 은 채움률이 낮거나
가장 짧은 변이 두께라서 걸리지 않고, 작은 드로잉 컵은 속이 비어 채움률이 낮아 걸리지 않는다."""
from __future__ import annotations

import re

SIZE_MAX = 80.0       # 가장 긴 변 (mm) — 이보다 크면 모양으로는 체결품이라 보지 않음
FILL_MIN = 0.30       # 부피 ÷ 상자 부피
CHUNKY = 0.20         # 가장 짧은 변 ÷ 가운데 변
ROUND_MIN = 0.40      # 원통 · 원뿔 · 도넛 면 넓이 몫

# (이름 정규식, 종류). 앞에서부터 맞춰 첫 번째 것
NAME_RULES = [
    (r"\b(hex(agon)?\s*)?(bolt|screw|cap\s*screw|machine\s*screw|set\s*screw|tapping|self[- ]tap|stud|bolts?)\b", "볼트·나사"),
    (r"\b(nut|nuts|lock\s*nut|hex\s*nut|wing\s*nut|nylock)\b", "너트"),
    (r"\b(washer|washers|spring\s*washer|lock\s*washer)\b", "와셔"),
    (r"\b(rivet|rivets|pop\s*rivet|blind\s*rivet)\b", "리벳"),
    (r"\b(dowel|pin|pins|cotter|split\s*pin|roll\s*pin|spring\s*pin|circlip|snap\s*ring|e[- ]?ring|retaining\s*ring)\b", "핀·링"),
    (r"\b(bearing|bush(ing)?|grommet|o[- ]?ring|spacer|standoff|insert|anchor)\b", "부시·베어링"),
    (r"(볼트|나사|스크류|스크루|스터드|육각렌치|렌치볼트|접시머리|둥근머리|탭핑|태핑)", "볼트·나사"),
    (r"(너트|넛트|락너트|캡너트)", "너트"),
    (r"(와셔|와샤|워셔|평와|스프링와)", "와셔"),
    (r"(리벳|리베트|리벳트)", "리벳"),
    (r"(핀|다우얼|스냅링|멈춤링|분할핀|스프링핀|이링|씨링)", "핀·링"),
    (r"(베어링|부싱|부시|스페이서|오링|그로밋)", "부시·베어링"),
    # 표준 번호: ISO 4014/4017/4762 (볼트) · 4032/4035/7040 (너트) · 7089/7090/7092 (와셔), DIN 931/933/912 · 934/985 · 125/127,
    # KS B 1002 (볼트) · 1012 (너트) · 1326 (와셔), JIS B 1180 · 1181 · 1256
    (r"\b(iso\s*(4014|4015|4016|4017|4018|4762|7045|7046|7047|10642|14579|14580|14583|1207|1580|7380))\b", "볼트·나사"),
    (r"\b(iso\s*(4032|4033|4034|4035|7040|7041|7042|10511|10512))\b", "너트"),
    (r"\b(iso\s*(7089|7090|7091|7092|7093|7094|10673))\b", "와셔"),
    (r"\b(din\s*(931|933|912|7984|7991|963|964|84|85|7985|6912|7500|571|603|444))\b", "볼트·나사"),
    (r"\b(din\s*(934|985|982|439|936|6923|6924|6925|315|1587))\b", "너트"),
    (r"\b(din\s*(125|126|127|433|440|6796|6797|6798|7980|9021))\b", "와셔"),
    (r"\b(din\s*(660|661|7337|7338|7339|7340))\b", "리벳"),
    (r"\b(ks\s*b\s*(1002|1003|1004|1005|1007|1021|1023|1028|1101|1102|1111|1112))\b", "볼트·나사"),
    (r"\b(ks\s*b\s*(1012|1013|1015|1016|1017|1018))\b", "너트"),
    (r"\b(ks\s*b\s*(1326|1324|1327|1328))\b", "와셔"),
    (r"\b(jis\s*b\s*(1180|1176|1177|1178|1111|1122))\b", "볼트·나사"),
    (r"\b(jis\s*b\s*(1181|1182|1183|1185|1190|1199))\b", "너트"),
    (r"\b(jis\s*b\s*(1256|1251|1252))\b", "와셔"),
    # 솔리드웍스 Toolbox 식 이름 (…_am, _ai 접미) · 나사 호칭만 있는 이름 "M8X20", "M10 x 30"
    (r"\b(socket\s*head|pan\s*head|flat\s*head|button\s*head|countersunk|hex\s*head|csk)\b", "볼트·나사"),
    (r"^\s*m\s*\d+(\.\d+)?\s*[x×*]\s*\d+", "볼트·나사"),
]
_RULES = [(re.compile(p, re.I), k) for p, k in NAME_RULES]
# 이런 말이 들어 있으면 판금 · 가공품 쪽 (핀 브래킷, 볼트 홀더 처럼 체결품 말이 섞여도 체결품이 아님)
SHEET_WORDS = re.compile(r"(bracket|brkt|panel|plate|cover|frame|holder|housing|box|door|floor|side|roof|gusset|channel|"
                         r"angle|beam|rail|stiffener|support|guard|lid|tray|duct|hopper|chute|"
                         r"브래킷|브라켓|브라캣|판넬|패널|플레이트|커버|프레임|홀더|하우징|바닥|측판|천장|도어|문짝|거셋|"
                         r"찬넬|채널|앵글|빔|레일|보강|받침|가드|덮개|트레이|덕트|호퍼|슈트)", re.I)


def by_name(name: str) -> str | None:
    """이름으로 본 체결품 종류 (아니면 None)."""
    if not name:
        return None
    n = re.sub(r"\s*#\d+$", "", name)                 # 같은 부품 #2, #3
    n = n.replace("_", " ").replace("-", " ")
    if SHEET_WORDS.search(n):
        return None
    for rx, kind in _RULES:
        if rx.search(n):
            return kind
    return None


def by_shape(solid) -> str | None:
    """모양으로 본 체결품 · 환봉 (아니면 None). 작은 뭉툭한 회전체."""
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepGProp import BRepGProp
        from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_SurfaceOfRevolution, GeomAbs_Torus
        from OCP.GProp import GProp_GProps
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box, False)                 # 느슨한 상자 (빠름) — 크면 바로 아님
        if box.IsVoid():
            return None
        lo, hi = box.CornerMin(), box.CornerMax()
        if max(hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z()) > 1.5 * SIZE_MAX + 10:
            return None
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(solid, box, False, False)   # 작은 것만 정확한 상자
        lo, hi = box.CornerMin(), box.CornerMax()
        dims = sorted([hi.X() - lo.X(), hi.Y() - lo.Y(), hi.Z() - lo.Z()])
        if dims[2] > SIZE_MAX or dims[0] <= 0:
            return None
        if dims[0] < CHUNKY * dims[1]:
            return None
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, g)
        vol = abs(g.Mass())
        if vol < FILL_MIN * dims[0] * dims[1] * dims[2]:
            return None
        round_a = total = 0.0
        exp = TopExp_Explorer(solid, TopAbs_FACE)
        while exp.More():
            f = TopoDS.Face(exp.Current())
            exp.Next()
            fg = GProp_GProps()
            BRepGProp.SurfaceProperties_s(f, fg)
            a = abs(fg.Mass())
            total += a
            if BRepAdaptor_Surface(f).GetType() in (GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Torus,
                                                    GeomAbs_SurfaceOfRevolution):
                round_a += a
        if total <= 0 or round_a < ROUND_MIN * total:
            return None
        return "환봉·체결품 (모양)"
    except Exception:  # noqa: BLE001
        return None


def classify(name: str, solid=None) -> str | None:
    """이름 → 모양 차례로. 돌려주는 값은 종류 글 (제외 표시용) 또는 None."""
    k = by_name(name)
    if k or solid is None:
        return k
    return by_shape(solid)


def find(names, solids) -> dict:
    """부품 번호 → 종류. names 가 '부품 N' 이면 이름은 안 본다."""
    out = {}
    for i, s in enumerate(solids):
        n = names[i] if names and i < len(names) else ""
        if re.fullmatch(r"부품 \d+", n or ""):
            n = ""
        k = classify(n, s)
        if k:
            out[i] = k
    return out
