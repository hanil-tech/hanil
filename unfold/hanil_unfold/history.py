"""전개 기록 — 전개한 부품을 계속 쌓아 둔다.

부품을 전개하면 수치(크기·블랭크 넓이·무게·절단 길이·절곡 수 등)와 DXF 사본을 보관함에 남긴다.
같은 날 같은 파일의 같은 부품을 다시 전개하면(K 계수를 바꿔 보는 등) 새 줄을 만들지 않고
최신 값으로 갱신한다. 다른 날 다시 전개하면 새 줄이 생겨 이력이 쌓인다.

저장 위치 (기본)
    %APPDATA%\\HanilUnfold\\기록\\history.sqlite     기록 데이터베이스
    %APPDATA%\\HanilUnfold\\기록\\보관함\\2026-10\\    DXF 사본 (월별 폴더)
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass

from . import dxf_export
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
]
FIELDS = [c for c, _ in COLUMNS]

# 화면·엑셀에 보일 이름
LABELS = {
    "id": "번호", "updated": "전개 일시", "source_name": "파일", "part_index": "부품",
    "mode": "전개 방식", "material": "재질", "thickness": "두께(mm)", "width": "가로(mm)",
    "height": "세로(mm)", "blank_area": "블랭크 넓이(mm²)", "weight_kg": "블랭크 무게(kg)",
    "rect_weight_kg": "사각 원판 무게(kg)", "yield_ratio": "수율", "cut_length": "절단 길이(mm)",
    "pierce": "피어싱", "bends": "절곡 수", "bend_summary": "절곡", "settings": "계산 조건",
    "warnings": "주의", "archive_dxf": "보관 DXF", "exported": "저장한 파일", "note": "메모",
    "source_path": "원본 경로", "created": "처음 기록",
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


class History:
    def __init__(self, folder: str | None = None):
        self.folder = folder or default_dir()
        os.makedirs(self.folder, exist_ok=True)
        self.path = os.path.join(self.folder, "history.sqlite")
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        cols = ", ".join(f"{n} {t}" for n, t in COLUMNS)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS unfolds ({cols})")
        self.db.execute("CREATE INDEX IF NOT EXISTS ix_key ON unfolds(source_path, part_index, day)")
        self.db.commit()

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
            dxf_export.save(result, dxf, part_name=name)
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
                "archive_dxf", "source_path"]
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
        wb.save(path)


def bend_summary(bends) -> str:
    """같은 각도·R 은 묶어서: '90.0°R2.00 ×2, 45.0°R3.00'."""
    groups = {}
    for b in bends:
        key = f"{b.angle_deg:.1f}°R{b.radius_text}"
        groups[key] = groups.get(key, 0) + 1
    return ", ".join(f"{k} ×{n}" if n > 1 else k for k, n in groups.items())
