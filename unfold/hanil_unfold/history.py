"""전개 기록 — 전개한 부품을 계속 쌓아 둔다.

부품을 전개하면 수치(크기·블랭크 넓이·무게·절단 길이·절곡 수 등)와 DXF 사본을 보관함에 남긴다.
같은 날 같은 파일의 같은 부품을 다시 전개하면(K 계수를 바꿔 보는 등) 새 줄을 만들지 않고
최신 값으로 갱신한다. 다른 날 다시 전개하면 새 줄이 생겨 이력이 쌓인다.

저장 위치 (기본)
    %APPDATA%\\HanilUnfold\\기록\\history.sqlite     기록 데이터베이스
    %APPDATA%\\HanilUnfold\\기록\\보관함\\2026-10\\    DXF 사본 (월별 폴더)
    %APPDATA%\\HanilUnfold\\기록\\보관함\\2026-10\\견적\\  저장한 견적서·금형 견적서·금형 검토 사본

견적·금형 기록 (docs 표): 생산 견적서·금형 견적서·금형 검토를 저장할 때마다 한 줄 —
고객·수량·단가·합계·금형비·필요 톤수·사용 기계·공정수와 부품별 내용(JSON), 파일 사본.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass

from . import dxf_export, version_text
from . import metrics as mt

COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("created", "TEXT"),          # 처음 기록한 때
    ("updated", "TEXT"),          # 마지막으로 갱신한 때
    ("day", "TEXT"),              # 같은 날 묶음 기준 (YYYY-MM-DD)
    ("source_path", "TEXT"),
    ("source_name", "TEXT"),
    ("part_index", "INTEGER"),
    ("part_count", "INTEGER"),
    ("mode", "TEXT"),             # sheet / forming
    ("material", "TEXT"),
    ("thickness", "REAL"),
    ("settings", "TEXT"),
    ("width", "REAL"),
    ("height", "REAL"),
    ("blank_area", "REAL"),
    ("weight_kg", "REAL"),
    ("rect_weight_kg", "REAL"),
    ("yield_ratio", "REAL"),
    ("cut_length", "REAL"),
    ("pierce", "INTEGER"),
    ("bends", "INTEGER"),
    ("bend_summary", "TEXT"),     # "90°R2.0 ×2, 45°R3.0"
    ("warnings", "TEXT"),
    ("archive_dxf", "TEXT"),      # 보관함에 남긴 DXF
    ("exported", "TEXT"),         # 사용자가 따로 저장한 파일들 (; 로 구분)
    ("note", "TEXT"),
    ("app_version", "TEXT"),      # 계산한 프로그램 버전
]
FIELDS = [c for c, _ in COLUMNS]

DOC_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("created", "TEXT"),
    ("day", "TEXT"),
    ("kind", "TEXT"),             # 생산 견적 / 금형 견적 / 금형 검토
    ("source_path", "TEXT"),
    ("source_name", "TEXT"),
    ("title", "TEXT"),
    ("customer", "TEXT"),
    ("material", "TEXT"),
    ("sets", "INTEGER"),
    ("annual", "INTEGER"),
    ("unit_price", "REAL"),       # 세트 단가
    ("supply", "REAL"),           # 공급가액
    ("total", "REAL"),            # 부가세 포함 합계
    ("die_total", "REAL"),
    ("max_tonf", "REAL"),
    ("machines", "TEXT"),
    ("total_ops", "INTEGER"),
    ("parts", "INTEGER"),
    ("summary", "TEXT"),          # 한 줄 요약
    ("detail", "TEXT"),           # 부품별 JSON
    ("files", "TEXT"),            # 저장한 파일 (; 로)
    ("archived", "TEXT"),         # 보관함 사본 (; 로)
    ("note", "TEXT"),
    ("app_version", "TEXT"),
]
DOC_LABELS = {
    "id": "번호", "created": "일시", "kind": "종류", "source_name": "파일", "title": "제품", "customer": "수신",
    "material": "재질", "sets": "수량(세트)", "annual": "연간 생산량", "unit_price": "세트 단가", "supply": "공급가액",
    "total": "합계(VAT 포함)", "die_total": "금형비", "max_tonf": "최대 톤수(tf)", "machines": "사용 기계",
    "total_ops": "공정수", "parts": "자작 부품", "summary": "요약", "files": "저장한 파일", "archived": "보관 사본",
    "note": "메모", "app_version": "프로그램 버전", "source_path": "원본 경로",
}

# 화면·엑셀에 보일 이름
LABELS = {
    "id": "번호", "updated": "전개 일시", "source_name": "파일", "part_index": "부품",
    "mode": "전개 방식", "material": "재질", "thickness": "두께(mm)", "width": "가로(mm)",
    "height": "세로(mm)", "blank_area": "블랭크 넓이(mm²)", "weight_kg": "블랭크 무게(kg)",
    "rect_weight_kg": "사각 원판 무게(kg)", "yield_ratio": "수율", "cut_length": "절단 길이(mm)",
    "pierce": "피어싱", "bends": "절곡 수", "bend_summary": "절곡", "settings": "계산 조건",
    "warnings": "주의", "archive_dxf": "보관 DXF", "exported": "저장한 파일", "note": "메모",
    "source_path": "원본 경로", "created": "처음 기록", "app_version": "프로그램 버전",
}


def default_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return os.path.join(base, "HanilUnfold", "기록")


@dataclass
class Record:
    id: int
    data: dict

    def __getitem__(self, k):
        return self.data[k]


# ---------------------------------------------------------------- 견적·금형 기록

class _DocsMixin:
    """견적·금형 기록 (docs 표). History 가 물려받는다."""


    def add_doc(self, kind, files, source_path="", values=None, detail=None, archive=True,
                when: _dt.datetime | None = None) -> int:
        """견적서·금형 견적서·금형 검토 저장 한 번을 기록. values: DOC_COLUMNS 의 값들."""
        import json
        import shutil
        when = when or _dt.datetime.now()
        v = dict(values or {})
        v.update(created=when.isoformat(timespec="seconds"), day=when.date().isoformat(), kind=kind,
                 source_path=os.path.abspath(source_path) if source_path else "",
                 source_name=os.path.basename(source_path) if source_path else v.get("source_name", ""),
                 files=";".join(os.path.abspath(f) for f in files), app_version=version_text(),
                 detail=json.dumps(detail, ensure_ascii=False) if detail is not None else "")
        v = {k: x for k, x in v.items() if k in dict(DOC_COLUMNS)}
        keys = ", ".join(v)
        cur = self.db.execute(f"INSERT INTO docs ({keys}) VALUES ({', '.join('?' for _ in v)})", tuple(v.values()))
        rid = cur.lastrowid
        if archive:
            folder = os.path.join(self.archive_root, when.strftime("%Y-%m"), "견적")
            os.makedirs(folder, exist_ok=True)
            copies = []
            for f in files:
                if os.path.exists(f):
                    dst = os.path.join(folder, f"{rid:05d}_{os.path.basename(f)}")
                    shutil.copy2(f, dst)
                    copies.append(dst)
            self.db.execute("UPDATE docs SET archived=? WHERE id=?", (";".join(copies), rid))
        self.db.commit()
        return rid


    def search_docs(self, text="", kind="", date_from="", date_to="", limit=5000):
        sql = "SELECT * FROM docs WHERE 1=1"
        args = []
        for word in text.split():
            sql += " AND (source_name LIKE ? OR title LIKE ? OR customer LIKE ? OR note LIKE ? OR material LIKE ?)"
            args += [f"%{word}%"] * 5
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        if date_from:
            sql += " AND day >= ?"
            args.append(date_from)
        if date_to:
            sql += " AND day <= ?"
            args.append(date_to)
        sql += " ORDER BY created DESC, id DESC LIMIT ?"
        args.append(limit)
        return [Record(r["id"], dict(r)) for r in self.db.execute(sql, args)]


    def count_docs(self):
        return self.db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]


    def set_doc_note(self, rid, note):
        self.db.execute("UPDATE docs SET note=? WHERE id=?", (note, rid))
        self.db.commit()


    def delete_docs(self, ids, remove_files=True):
        for rid in ids:
            row = self.db.execute("SELECT archived FROM docs WHERE id=?", (rid,)).fetchone()
            if row and remove_files:
                for f in (row["archived"] or "").split(";"):
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            self.db.execute("DELETE FROM docs WHERE id=?", (rid,))
        self.db.commit()


    def export_docs_xlsx(self, path, records=None):
        import json

        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        records = self.search_docs() if records is None else records
        cols = ["id", "created", "kind", "title", "customer", "source_name", "material", "sets", "annual",
                "unit_price", "supply", "total", "die_total", "max_tonf", "machines", "total_ops", "parts",
                "summary", "note", "files", "archived", "app_version"]
        wb = Workbook()
        ws = wb.active
        ws.title = "견적·금형 기록"
        head_font = Font(name="맑은 고딕", bold=True, color="FFFFFF")
        fill = PatternFill("solid", fgColor="28405A")
        for j, c in enumerate(cols, 1):
            cell = ws.cell(1, j, DOC_LABELS.get(c, c))
            cell.font, cell.fill = head_font, fill
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[cell.column_letter].width = 32 if c in ("summary", "files", "archived", "machines") else 14
        for i, r in enumerate(records, 2):
            for j, c in enumerate(cols, 1):
                v = r.data.get(c)
                if c == "created" and v:
                    v = v.replace("T", " ")
                cell = ws.cell(i, j, v)
                if c in ("unit_price", "supply", "total", "die_total"):
                    cell.number_format = "#,##0"
                elif c == "max_tonf":
                    cell.number_format = "#,##0.0"
        ws.freeze_panes = "A2"
        # 부품별 (상세)
        w2 = wb.create_sheet("부품별")
        heads = ["기록 번호", "종류", "제품", "품번", "품명", "수량/세트", "재질", "공정 방식", "공정수", "공정",
                 "톤수(tf)", "기계", "자재비/개", "가공비/개", "금형비"]
        w2.append(heads)
        for c in w2[1]:
            c.font, c.fill = head_font, fill
        for r in records:
            try:
                parts = json.loads(r.data.get("detail") or "[]")
            except ValueError:
                parts = []
            for p in parts if isinstance(parts, list) else []:
                w2.append([r.id, r.data.get("kind"), r.data.get("title"), p.get("no"), p.get("name"), p.get("qty"),
                           p.get("spec"), p.get("method"), p.get("n_ops"), p.get("ops"), p.get("tonf"),
                           p.get("machines"), p.get("material"), p.get("process"), p.get("die")])
        from .company import stamp_workbook
        stamp_workbook(wb)
        wb.save(path)


from .items import _ItemsMixin, ensure_table as _ensure_items  # noqa: E402


class History(_DocsMixin, _ItemsMixin):
    def __init__(self, folder: str | None = None):
        self.folder = folder or default_dir()
        os.makedirs(self.folder, exist_ok=True)
        self.path = os.path.join(self.folder, "history.sqlite")
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        cols = ", ".join(f"{n} {t}" for n, t in COLUMNS)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS unfolds ({cols})")
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_key ON unfolds(source_path, part_index, day)")
        # 예전 버전에서 만든 기록 파일이면 새 칸을 덧붙인다
        have = {r[1] for r in self.db.execute("PRAGMA table_info(unfolds)")}
        for name, typ in COLUMNS:
            if name not in have:
                self.db.execute(f"ALTER TABLE unfolds ADD COLUMN {name} {typ}")
        cols = ", ".join(f"{n} {t}" for n, t in DOC_COLUMNS)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS docs ({cols})")
        have = {r[1] for r in self.db.execute("PRAGMA table_info(docs)")}
        for name, typ in DOC_COLUMNS:
            if name not in have:
                self.db.execute(f"ALTER TABLE docs ADD COLUMN {name} {typ}")
        self.db.commit()
        _ensure_items(self.db)          # 아이템 (견적 요청) 대장
        from . import calibration
        self.calib = calibration.Store(self.db)     # 실적 보정 기록

    def close(self):
        self.db.close()

    @property
    def archive_root(self):
        return os.path.join(self.folder, "보관함")

    # ---- 기록하기

    def record(self, source_path, result, settings, part_index=1, part_count=1,
               part_name=None, when: _dt.datetime | None = None, archive=True) -> int:
        """전개 결과를 기록하고 번호를 돌려준다. 같은 날 같은 부품이면 갱신."""
        when = when or _dt.datetime.now()
        stamp = when.isoformat(timespec="seconds")
        day = when.date().isoformat()
        source_path = os.path.abspath(source_path)
        name = part_name or os.path.splitext(os.path.basename(source_path))[0]
        mat = settings.mat
        m = mt.compute(result, mat.density)
        values = dict(
            updated=stamp, day=day, source_path=source_path,
            source_name=os.path.basename(source_path), part_index=part_index, part_count=part_count,
            mode=result.mode, material=mat.code, thickness=round(result.thickness, 4),
            settings=result.settings_text, width=m.width, height=m.height,
            blank_area=m.blank_area, weight_kg=m.weight_kg, rect_weight_kg=m.rect_weight_kg,
            yield_ratio=m.yield_ratio, cut_length=m.cut_length, pierce=m.pierce,
            bends=len(result.bends), bend_summary=bend_summary(result.bends),
            warnings=" / ".join(w for w in result.warnings if "근사 전개:" not in w),
            app_version=version_text(),
        )
        row = self.db.execute(
            "SELECT id FROM unfolds WHERE source_path=? AND part_index=? AND day=?",
            (source_path, part_index, day)).fetchone()
        if row:
            rid = row["id"]
            sets = ", ".join(f"{k}=?" for k in values)
            self.db.execute(f"UPDATE unfolds SET {sets} WHERE id=?", (*values.values(), rid))
        else:
            values["created"] = stamp
            keys = ", ".join(values)
            marks = ", ".join("?" for _ in values)
            cur = self.db.execute(f"INSERT INTO unfolds ({keys}) VALUES ({marks})", tuple(values.values()))
            rid = cur.lastrowid
        if archive:
            dxf = self._archive_path(rid, name, part_index, part_count, when)
            dxf_export.save(result, dxf, part_name=name, density=mat.density)
            self.db.execute("UPDATE unfolds SET archive_dxf=? WHERE id=?", (dxf, rid))
        self.db.commit()
        return rid

    def _archive_path(self, rid, name, part_index, part_count, when):
        folder = os.path.join(self.archive_root, when.strftime("%Y-%m"))
        os.makedirs(folder, exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]+', "_", name)
        suffix = f"_{part_index}" if part_count > 1 else ""
        return os.path.join(folder, f"{rid:05d}_{safe}{suffix}_flat.dxf")

    def add_export(self, rid: int, path: str):
        """사용자가 DXF·보고서를 따로 저장했으면 그 경로도 남긴다."""
        row = self.db.execute("SELECT exported FROM unfolds WHERE id=?", (rid,)).fetchone()
        if row is None:
            return
        items = [p for p in (row["exported"] or "").split(";") if p]
        path = os.path.abspath(path)
        if path not in items:
            items.append(path)
        self.db.execute("UPDATE unfolds SET exported=? WHERE id=?", (";".join(items), rid))
        self.db.commit()

    def set_note(self, rid: int, note: str):
        self.db.execute("UPDATE unfolds SET note=? WHERE id=?", (note, rid))
        self.db.commit()

    def delete(self, ids, remove_files=True):
        for rid in ids:
            row = self.db.execute("SELECT archive_dxf FROM unfolds WHERE id=?", (rid,)).fetchone()
            if row and remove_files and row["archive_dxf"] and os.path.exists(row["archive_dxf"]):
                try:
                    os.remove(row["archive_dxf"])
                except OSError:
                    pass
            self.db.execute("DELETE FROM unfolds WHERE id=?", (rid,))
        self.db.commit()

    # ---- 찾기

    def search(self, text: str = "", date_from: str = "", date_to: str = "", limit: int = 5000):
        """파일·부품·재질·메모에 text 가 들어간 기록 (최근 순)."""
        sql = "SELECT * FROM unfolds WHERE 1=1"
        args = []
        for word in text.split():
            sql += " AND (source_name LIKE ? OR material LIKE ? OR note LIKE ? OR settings LIKE ?)"
            args += [f"%{word}%"] * 4
        if date_from:
            sql += " AND day >= ?"
            args.append(date_from)
        if date_to:
            sql += " AND day <= ?"
            args.append(date_to)
        sql += " ORDER BY updated DESC, id DESC LIMIT ?"
        args.append(limit)
        return [Record(r["id"], dict(r)) for r in self.db.execute(sql, args)]

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM unfolds").fetchone()[0]

    # ---- 엑셀로

    def export_xlsx(self, path: str, records=None):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        records = self.search() if records is None else records
        cols = ["id", "updated", "source_name", "part_index", "mode", "material", "thickness",
                "width", "height", "blank_area", "weight_kg", "rect_weight_kg", "yield_ratio",
                "cut_length", "pierce", "bends", "bend_summary", "settings", "warnings", "note",
                "app_version", "archive_dxf", "source_path"]
        wb = Workbook()
        ws = wb.active
        ws.title = "전개 기록"
        head_font = Font(name="맑은 고딕", bold=True, color="FFFFFF")
        fill = PatternFill("solid", fgColor="28405A")
        for j, c in enumerate(cols, 1):
            cell = ws.cell(1, j, LABELS.get(c, c))
            cell.font, cell.fill = head_font, fill
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[cell.column_letter].width = 14
        for c in ("source_name", "bend_summary", "settings", "warnings", "archive_dxf", "source_path"):
            ws.column_dimensions[ws.cell(1, cols.index(c) + 1).column_letter].width = 32
        for i, r in enumerate(records, 2):
            for j, c in enumerate(cols, 1):
                v = r.data.get(c)
                if c == "mode":
                    v = "성형품(근사)" if v == "forming" else "판금"
                if c == "part_index" and (r.data.get("part_count") or 1) > 1:
                    v = f"{v}/{r.data['part_count']}"
                cell = ws.cell(i, j, round(v, 4) if isinstance(v, float) else v)
                if c == "yield_ratio":
                    cell.number_format = "0.0%"
                elif isinstance(v, float):
                    cell.number_format = "#,##0.000"
        n = len(records) + 1
        if records:
            ws.cell(n + 1, 1, "합계")
            for c in ("weight_kg", "rect_weight_kg", "cut_length", "blank_area"):
                col = ws.cell(1, cols.index(c) + 1).column_letter
                ws[f"{col}{n + 1}"] = f"=SUM({col}2:{col}{n})"
                ws[f"{col}{n + 1}"].number_format = "#,##0.000"
        ws.freeze_panes = "A2"
        from .company import stamp_workbook
        stamp_workbook(wb)
        wb.save(path)


def bend_summary(bends) -> str:
    """같은 각도·R 은 묶어서: '90.0°R2.00 ×2, 45.0°R3.00'."""
    groups = {}
    for b in bends:
        key = f"{b.angle_deg:.1f}°R{b.radius_text}"
        groups[key] = groups.get(key, 0) + 1
    return ", ".join(f"{k} ×{n}" if n > 1 else k for k, n in groups.items())
