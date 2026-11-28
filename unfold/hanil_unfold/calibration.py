"""실적 보정: 프로그램 예측값과 현장에서 잰 실제 값을 쌓아 보정 계수를 구하고, 다음 계산부터 곱한다.

종류 (kind)       예측 → 실측                         묶음 (key)          쓰는 곳
  springback     스프링백 각 (°, 되돌아간 양)          재질 코드           diecalc.springback (금형 보정 각·성형 해석)
  thinning       최대 얇아짐 (%)                      재질 코드           formsim.fields (두께·성형성 존)
  tonnage        프레스 하중 (tf, 여유 빼고)           금형 형식 / 전체    formsim·diecalc 권장 프레스, 견적 프레스 고르기
  cycle          1 타·1 회 시간 (초)                  기계 이름 / 전체    견적의 공정 시간 (가공비)
  die_cost       금형비 (원)                          금형 구조 / 전체    금형 견적 (보정 줄로 따로)

보정 계수 k: 원점을 지나는 최소 제곱 k = Σ(예측·실측) / Σ(예측²) — 큰 값에 무게가 더 실린다 (사이클·금형비는 큰 건이 중요).
  기록 3 개 이상일 때만 쓴다. 비 (실측/예측) 의 평균·표준편차로 95 % 범위 (t 분포) 와 흩어짐 (CV) 을 같이 보인다.
  같은 묶음 (재질·기계) 기록이 3 개 안 되면, 스프링백·얇아짐은 쓰지 않고 (재질마다 다름) 나머지는 전체 계수를 쓴다.
기록은 기록 파일 history.sqlite 의 calib 표 (PC 안 파일).
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from dataclasses import dataclass

KINDS = {
    "springback": ("스프링백", "°", "재질"),
    "thinning": ("최대 얇아짐", "%", "재질"),
    "tonnage": ("프레스 하중", "tf", "금형 형식"),
    "cycle": ("공정 시간 (1 타·1 회)", "초", "기계"),
    "die_cost": ("금형비", "원", "금형 구조"),
}
PER_KEY_ONLY = {"springback", "thinning"}       # 다른 재질 계수를 빌려 쓰지 않음
MIN_N = 3
K_RANGE = (0.3, 3.0)                            # 이 밖이면 입력 실수로 보고 쓰지 않음
ALL = "*"

COLUMNS = [("id", "INTEGER PRIMARY KEY AUTOINCREMENT"), ("created", "TEXT"), ("kind", "TEXT"), ("key", "TEXT"),
           ("part", "TEXT"), ("predicted", "REAL"), ("actual", "REAL"), ("condition", "TEXT"), ("note", "TEXT"),
           ("used", "INTEGER")]


def ensure_table(db):
    db.execute(f"CREATE TABLE IF NOT EXISTS calib ({', '.join(f'{n} {t}' for n, t in COLUMNS)})")
    db.execute("CREATE TABLE IF NOT EXISTS calib_on (kind TEXT PRIMARY KEY, used INTEGER)")
    have = {r[1] for r in db.execute("PRAGMA table_info(calib)")}
    for n, t in COLUMNS:
        if n not in have:
            db.execute(f"ALTER TABLE calib ADD COLUMN {n} {t}")
    db.commit()


@dataclass
class Rec:
    id: int
    created: str
    kind: str
    key: str
    part: str
    predicted: float
    actual: float
    condition: str = ""
    note: str = ""
    used: bool = True

    @property
    def ratio(self):
        return self.actual / self.predicted if self.predicted else float("nan")


@dataclass
class Fit:
    kind: str
    key: str
    n: int
    k: float | None            # 쓰는 계수 (None = 못 씀)
    mean: float                # 비 평균
    sd: float
    lo: float                  # 95 % 범위
    hi: float
    status: str

    @property
    def cv(self):
        return self.sd / self.mean if self.mean else float("nan")


_T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 15: 2.13,
        20: 2.09, 30: 2.04}


def _t95(df):
    if df <= 0:
        return float("nan")
    keys = sorted(_T95)
    for k in keys:
        if df <= k:
            return _T95[k]
    return 1.96


def fit(recs, kind, key) -> Fit:
    rs = [r for r in recs if r.used and r.note != "실측 대기" and r.predicted and r.predicted > 0
          and r.actual is not None and r.actual >= 0]
    n = len(rs)
    if not n:
        return Fit(kind, key, 0, None, float("nan"), float("nan"), float("nan"), float("nan"), "기록 없음")
    ratios = [r.ratio for r in rs]
    mean = sum(ratios) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in ratios) / (n - 1)) if n > 1 else 0.0
    half = _t95(n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
    k = sum(r.predicted * r.actual for r in rs) / sum(r.predicted ** 2 for r in rs)
    if n < MIN_N:
        return Fit(kind, key, n, None, mean, sd, mean - half, mean + half, f"기록 {n} 개 — {MIN_N} 개부터 씀")
    if not (K_RANGE[0] <= k <= K_RANGE[1]):
        return Fit(kind, key, n, None, mean, sd, mean - half, mean + half, f"계수 {k:.2f} 가 범위 밖 — 입력 확인")
    return Fit(kind, key, n, k, mean, sd, mean - half, mean + half, "씀")


class Store:
    """History.db 위의 보정 기록."""

    def __init__(self, db):
        self.db = db
        ensure_table(db)

    def add(self, kind, key, part, predicted, actual, condition="", note="", when=None) -> int:
        when = (when or _dt.datetime.now()).isoformat(timespec="seconds")
        if isinstance(condition, dict):
            condition = json.dumps(condition, ensure_ascii=False)
        cur = self.db.execute("INSERT INTO calib (created, kind, key, part, predicted, actual, condition, note, used) "
                              "VALUES (?,?,?,?,?,?,?,?,1)",
                              (when, kind, key or ALL, part, float(predicted), float(actual), condition, note))
        self.db.commit()
        return cur.lastrowid

    def records(self, kind=None, key=None):
        sql, args = "SELECT * FROM calib", []
        cond = []
        if kind:
            cond.append("kind=?")
            args.append(kind)
        if key:
            cond.append("key=?")
            args.append(key)
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        sql += " ORDER BY created, id"
        return [Rec(r["id"], r["created"], r["kind"], r["key"], r["part"] or "", r["predicted"], r["actual"],
                    r["condition"] or "", r["note"] or "", bool(r["used"])) for r in self.db.execute(sql, args)]

    def update(self, rid, **kw):
        ok = {k: v for k, v in kw.items() if k in ("key", "part", "predicted", "actual", "note", "used")}
        if not ok:
            return
        self.db.execute(f"UPDATE calib SET {', '.join(f'{k}=?' for k in ok)} WHERE id=?",
                        tuple(int(v) if k == "used" else v for k, v in ok.items()) + (rid,))
        self.db.commit()

    def delete(self, rid):
        self.db.execute("DELETE FROM calib WHERE id=?", (rid,))
        self.db.commit()

    def enabled(self, kind) -> bool:
        r = self.db.execute("SELECT used FROM calib_on WHERE kind=?", (kind,)).fetchone()
        return bool(r[0]) if r else True

    def set_enabled(self, kind, on):
        self.db.execute("INSERT OR REPLACE INTO calib_on (kind, used) VALUES (?, ?)", (kind, int(bool(on))))
        self.db.commit()

    def fits(self, kind):
        """[(묶음 key, Fit)] — 묶음별과 전체 (*)."""
        recs = self.records(kind)
        keys = sorted({r.key for r in recs if r.key != ALL})
        out = [(k, fit([r for r in recs if r.key == k], kind, k)) for k in keys]
        out.append((ALL, fit(recs, kind, ALL)))
        return out


# ---------------------------------------------------------------- 계산에 쓰는 계수

ACTIVE: dict = {}          # kind → {key: k}


def load(store: Store | None):
    """앱 시작·보정 창 닫을 때: 켜진 종류의 계수를 메모리에."""
    ACTIVE.clear()
    if store is None:
        return
    for kind in KINDS:
        if not store.enabled(kind):
            continue
        ks = {key: f.k for key, f in store.fits(kind) if f.k is not None}
        if ks:
            ACTIVE[kind] = ks


def factor(kind, key=None):
    """(계수, 설명) — 없으면 (1.0, "")."""
    ks = ACTIVE.get(kind)
    if not ks:
        return 1.0, ""
    if key is not None and key in ks:
        return ks[key], f"실적 보정 ×{ks[key]:.2f} ({key})"
    if kind not in PER_KEY_ONLY and ALL in ks:
        return ks[ALL], f"실적 보정 ×{ks[ALL]:.2f} (전체)"
    return 1.0, ""


def die_key(structure, method):
    """금형비 묶음: '강판 순차' · '주물 단발' …"""
    kind = next((w for w in ("순차", "트랜스퍼", "복합", "단발") if w in (method or "")), "단발")
    return f"{structure or '강판'} {kind}"


def summary():
    """지금 쓰는 계수 한 줄."""
    parts = []
    for kind, ks in ACTIVE.items():
        name = KINDS[kind][0]
        parts.append(name + " " + ", ".join(f"{'전체' if k == ALL else k} ×{v:.2f}" for k, v in ks.items()))
    return " · ".join(parts)


def save_xlsx(store: Store, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    from .company import stamp_workbook
    wb = Workbook()
    hf, hfill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F4E8C")
    ws = wb.active
    ws.title = "보정 계수"
    head = ["종류", "묶음", "기록 수", "보정 계수 k", "비 평균", "표준편차", "95 % 하한", "95 % 상한", "CV", "상태", "켜짐"]
    for j, h in enumerate(head, 1):
        c = ws.cell(1, j, h)
        c.font, c.fill = hf, hfill
    r = 2
    for kind, (name, unit, _) in KINDS.items():
        for key, f in store.fits(kind):
            vals = [f"{name} ({unit})", "전체" if key == ALL else key, f.n, f.k, f.mean, f.sd, f.lo, f.hi, f.cv,
                    f.status, "켜짐" if store.enabled(kind) else "꺼짐"]
            for j, v in enumerate(vals, 1):
                c = ws.cell(r, j, None if isinstance(v, float) and math.isnan(v) else v)
                if isinstance(v, float):
                    c.number_format = "0.000"
            r += 1
    ws2 = wb.create_sheet("기록")
    head = ["번호", "날짜", "종류", "묶음", "부품", "예측", "실측", "실측/예측", "조건", "메모", "씀"]
    for j, h in enumerate(head, 1):
        c = ws2.cell(1, j, h)
        c.font, c.fill = hf, hfill
    for i, rec in enumerate(store.records(), 2):
        for j, v in enumerate([rec.id, rec.created, KINDS.get(rec.kind, (rec.kind,))[0], rec.key, rec.part,
                               rec.predicted, rec.actual, rec.ratio, rec.condition, rec.note,
                               "예" if rec.used else "아니오"], 1):
            ws2.cell(i, j, v)
    for w_ in (ws, ws2):
        for col in "ABCDEFGHIJK":
            w_.column_dimensions[col].width = 14
    stamp_workbook(wb)
    wb.save(path)


# ---------------------------------------------------------------- 지금 부품에서 예측값 뽑기

def predictions(kind, result, settings, name=""):
    """보정 창의 [지금 부품 예측값] — [(묶음 key, 조건 글, 예측값)]. 실측 칸은 사람이 채운다.
    계산은 보정 계수를 빼고 (원래 예측) 한다."""
    from . import bendcalc as bc
    from . import diecalc as dc
    from . import formsim as fs
    saved = dict(ACTIVE)
    ACTIVE.clear()
    try:
        mat = settings.mat
        t = result.thickness
        out = []
        if kind == "springback":
            v = settings.die_v if settings.die_v > 0 else bc.default_die_v(t)
            for b in result.bends:
                if b.angle_deg < 1:
                    continue
                r = b.inner_radius
                if settings.process == bc.AIR:
                    r = max(r, mat.air_ratio * v)
                after, _, _ = dc.springback(mat, r, t, b.angle_deg)
                out.append((mat.code, f"B{b.number} {b.angle_deg:.0f}° R{r:.1f} t{t:g} V{v:g}", b.angle_deg - after))
        elif kind == "thinning":
            fa = fs.analyze(result, settings)
            if fa.mode == "forming":
                ex = fa.explain
                spots = [i for i in (ex.issues if ex else []) if i.zone in (0, 1, 2)][:3]
                for i in spots:
                    out.append((mat.code, f"{i.mark} {i.short or i.region} t{t:g}", 100 * i.thin_max))
                out.append((mat.code, f"제품 전체 최대 t{t:g}", 100 * max(fa.thin_hi, 0)))
        elif kind == "tonnage":
            fa = fs.analyze(result, settings)
            if fa.mode == "forming":
                tot = sum(f for nm, f, _ in fa.loads if not nm.startswith("굽힘"))
                out.append(("드로잉" if fa.ldr else "성형", f"{name} 하중 합 (여유 빼고)", tot / dc.TON))
            else:
                rep = dc.review(result, settings, strip=False)
                out.append(("전단·굽힘", f"{name} 전단 합 (여유 빼고)", rep.total_n / dc.TON))
        return out
    finally:
        ACTIVE.clear()
        ACTIVE.update(saved)
