"""AI BOM: 2D 도면 PDF 와 3D 조립품을 함께 Claude 에게 보여 주고, BOM 을 엑셀로 만든다.
도면 PDF 가 없으면 3D 목록과 부품 그림만으로 부품명·구분·규격·재질을 추정한다.

  1. 3D 에서 같은 부품끼리 묶은 목록(bom.build) 을 요약한다: 품번·수량·구분·두께·전개 크기·
     바깥 크기(작은 것부터)·무게.
  2. 도면 PDF 와 그 요약을 Claude (claude-opus-5-5) 에게 보내 도면의 부품표·표제란을 읽고,
     도면의 줄마다 어느 3D 품번인지 짝지어 정해진 JSON 형식으로 받는다 (output_config.format).
  3. 도면 값(품번·도번·이름·재질·규격·수량) 과 3D 값(두께·전개 크기·무게·그림) 을 한 줄에 모아
     엑셀로 저장한다. 수량이 다르거나 짝이 없는 줄은 빨갛게 표시한다.

API 키: 환경 변수 ANTHROPIC_API_KEY, 또는 화면에서 넣은 키 (이 PC 사용자 설정에 저장).
요금은 Anthropic API 사용량대로 나간다 (도면 몇 쪽이면 한 번에 대략 수십 원~수백 원).
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os

from . import version_text

MODEL = "claude-opus-5-5"
MAX_PDF_BYTES = 30 * 1024 * 1024          # 요청 한도 32 MB 안쪽

SCHEMA = {
    "type": "object",
    "properties": {
        "drawing": {
            "type": "object",
            "description": "도면 표제란",
            "properties": {
                "drawing_no": {"type": "string", "description": "도번 (없으면 빈 글)"},
                "title": {"type": "string", "description": "도면 이름"},
                "revision": {"type": "string"},
                "company": {"type": "string"},
                "date": {"type": "string"},
                "scale": {"type": "string"},
            },
            "required": ["drawing_no", "title", "revision", "company", "date", "scale"],
            "additionalProperties": False,
        },
        "items": {
            "type": "array",
            "description": "BOM 한 줄마다 하나 (도면 부품표 순서). 도면에 부품표가 없으면 3D 목록을 바탕으로 "
                           "도면에서 읽을 수 있는 이름·재질을 붙여 만든다.",
            "items": {
                "type": "object",
                "properties": {
                    "item_no": {"type": "string", "description": "도면의 품번 (풍선 번호)"},
                    "part_no": {"type": "string", "description": "부품 도번·품명 코드 (없으면 빈 글)"},
                    "name": {"type": "string", "description": "부품명"},
                    "material": {"type": "string", "description": "재질 (예: SPCC, SS400, SAPH440)"},
                    "spec": {"type": "string", "description": "규격·치수·두께 표기 (도면에 적힌 그대로)"},
                    "qty": {"type": "integer", "description": "도면의 수량 (없으면 0)"},
                    "kind": {"type": "string", "enum": ["제작품", "구매품", "표준품", "모름"],
                             "description": "볼트·너트·와셔·핀 같은 표준품, 사서 쓰는 구매품, 만드는 제작품"},
                    "matched_3d": {"type": "array", "items": {"type": "integer"},
                                   "description": "짝이 되는 3D 품번들 (3D 목록의 no). 없으면 빈 배열"},
                    "confidence": {"type": "string", "enum": ["높음", "보통", "낮음"],
                                   "description": "3D 와 짝지은 것이 얼마나 확실한가"},
                    "remark": {"type": "string", "description": "비고 (짝지은 근거, 도면과 3D 가 다른 점)"},
                },
                "required": ["item_no", "part_no", "name", "material", "spec", "qty", "kind",
                             "matched_3d", "confidence", "remark"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "array", "items": {"type": "string"},
                  "description": "전체에 대한 참고 (도면에서 못 읽은 것, 도면과 3D 가 크게 다른 점 등)"},
    },
    "required": ["drawing", "items", "notes"],
    "additionalProperties": False,
}

SYSTEM = (
    "당신은 판금·용접 제조 회사의 생산기술 담당자입니다. 2D 도면(PDF)의 부품표(BOM, Parts List)와 "
    "표제란을 정확히 읽고, 같은 조립품의 3D 모델에서 뽑은 부품 목록과 짝지어 BOM 을 만듭니다.\n"
    "- 도면에 적힌 글(품번·도번·부품명·재질·규격·수량)은 고치지 말고 적힌 그대로 옮기세요. "
    "읽을 수 없으면 빈 글로 두고 notes 에 적으세요. 지어내지 마세요.\n"
    "- 3D 와 짝짓기: 수량, 두께, 전개 크기·바깥 크기, 부품 이름, 구분(판금/성형품/기타)을 함께 보고 정하세요. "
    "확실하지 않으면 confidence 를 낮게 하고 remark 에 근거를 쓰세요. 한 3D 품번은 한 줄에만 넣으세요.\n"
    "- 3D 목록의 '기타' 는 판금이 아닌 부품(너트·부싱·핀 등)일 가능성이 큽니다.\n"
    "- 답은 한국어로."
)


def parts_summary(items):
    """bom.build 결과 → Claude 에게 줄 3D 요약 (JSON 으로 바꿀 수 있는 목록)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    out = []
    for it in items:
        try:
            b = Bnd_Box()
            BRepBndLib.AddOptimal_s(it.solid, b, False, False)
            mn, mx = b.CornerMin(), b.CornerMax()
            ext = sorted(round(v, 1) for v in (mx.X() - mn.X(), mx.Y() - mn.Y(), mx.Z() - mn.Z()))
        except Exception:
            ext = []
        out.append({
            "no": it.no, "name_in_3d": it.name, "qty": it.qty, "kind": it.kind,
            "thickness_mm": round(it.thickness, 2) if it.thickness else None,
            "flat_size_mm": [round(it.flat_w, 1), round(it.flat_h, 1)] if it.flat_w else None,
            "bbox_mm_sorted": ext, "weight_kg": round(it.weight, 3), "bends": it.bends,
            "assembly_numbers": it.numbers,
        })
    return out


SYSTEM_3D = (
    "당신은 판금·용접 제조 회사의 생산기술 담당자입니다. 도면 없이 조립품 3D 모델에서 뽑은 부품 목록과 "
    "부품마다의 3D 그림만 보고 BOM 을 만듭니다.\n"
    "- 3D 목록의 줄마다 BOM 한 줄을 만드세요 (같은 순서, item_no 는 1 부터, matched_3d 는 그 줄의 3D 품번 하나).\n"
    "- name: 모양·크기·두께를 보고 현장에서 부르는 한국어 부품명 (예: 브래킷, 보강판, 사이드 패널, 부싱, 핀, "
    "너트, 와셔). 3D 이름이 '부품 N' 같은 뜻 없는 이름이 아니면 그 이름을 살리세요.\n"
    "- kind: 판금·성형품은 대개 제작품, 너트·볼트·와셔·핀은 표준품, 부싱·축 같은 가공품은 제작품 또는 구매품.\n"
    "- spec: 판금은 'PL t두께 × 가로 × 세로 (전개)', 표준품은 'M8 너트' 처럼 추정 규격, 봉·관은 '지름 × 길이'.\n"
    "- material: 지정 재질이 주어지면 판금에 그것을, 표준품은 비우거나 'SWCH' 같은 일반 재질 추정.\n"
    "- part_no 는 빈 글로. 모두 추정이므로 confidence 를 솔직하게, remark 에 근거를 짧게.\n"
    "- drawing 칸은 title 에 조립품 이름(파일 이름에서) 만 넣고 나머지는 빈 글로.\n"
    "- 답은 한국어로."
)

MAX_IMAGES = 80        # 그림을 함께 보낼 품목 수 (넘으면 숫자만)


def _png_b64(qimage):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    qimage.save(buf, "PNG")
    return base64.standard_b64encode(bytes(ba)).decode("ascii")


def analyze(pdf_path, items, api_key=None, client=None, effort="high", images=True,
            source_name="", material=""):
    """도면 PDF(없으면 None) + 3D 목록 → SCHEMA 모양의 dict. client 를 주면 그것을 쓴다 (시험용).

    PDF 가 없으면 3D 목록과 부품 그림만으로 이름·구분·규격을 추정한다."""
    import anthropic

    if client is None:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    summary = json.dumps(parts_summary(items), ensure_ascii=False)
    if pdf_path:
        with open(pdf_path, "rb") as f:
            data = f.read()
        if len(data) > MAX_PDF_BYTES:
            raise ValueError(f"PDF 가 너무 큽니다 ({len(data) / 1e6:.0f} MB). 30 MB 이하로 나눠 주세요.")
        system = SYSTEM
        content = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.standard_b64encode(data).decode("ascii")}},
            {"type": "text", "text": "다음은 같은 조립품의 3D 모델에서 같은 부품끼리 묶은 목록입니다 "
                                     "(no = 3D 품번, 크기는 mm, 무게는 kg):\n" + summary +
                                     "\n\n도면의 부품표와 표제란을 읽고, 3D 목록과 짝지어 BOM 을 만들어 주세요."},
        ]
    else:
        system = SYSTEM_3D
        content = []
        if images and len(items) <= MAX_IMAGES:
            from . import bom
            for it in items:
                content.append({"type": "text", "text": f"3D 품번 {it.no} ({it.name}, {it.qty}개, {it.kind}):"})
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                            "data": _png_b64(bom.thumb(it, 320, 200))}})
        content.append({"type": "text", "text":
                        f"조립품: {source_name or '(이름 없음)'}. 판금 지정 재질: {material or '(없음)'}.\n"
                        "도면은 없습니다. 다음은 3D 모델에서 같은 부품끼리 묶은 목록입니다 "
                        "(no = 3D 품번, 크기는 mm, 무게는 kg, kind 는 프로그램이 나눈 판금/성형품/기타):\n"
                        + summary + "\n\n이 목록으로 BOM 을 만들어 주세요."})
    # 응답이 길 수 있어 스트리밍으로 받는다. 정책 거절 시 서버가 다른 모델로 다시 시도.
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("AI 가 이 요청을 처리하지 않았습니다 (거절). 파일을 확인해 주세요.")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("AI 답이 너무 길어 잘렸습니다. 부품을 나눠서 다시 해 주세요.")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return json.loads(text)


def merge(ai, items):
    """AI 결과와 3D 목록을 한 줄씩 모은다 → (rows, unmatched_3d_items)."""
    by_no = {it.no: it for it in items}
    used = set()
    rows = []
    for a in ai.get("items", []):
        matched = [by_no[n] for n in a.get("matched_3d", []) if n in by_no and n not in used]
        used.update(m.no for m in matched)
        qty3d = sum(m.qty for m in matched)
        rows.append({"ai": a, "parts": matched, "qty3d": qty3d,
                     "qty_ok": bool(matched) and (a.get("qty", 0) in (0, qty3d))})
    unmatched = [it for it in items if it.no not in used]
    return rows, unmatched


def save_xlsx(ai, items, path, source_3d="", source_pdf="", material="", density=7.85):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, PatternFill

    from . import bom, company
    from .report import _add_image, _xl_font, _xl_styles

    st = _xl_styles()
    red = PatternFill("solid", fgColor="FDE2E1")
    rows, unmatched = merge(ai, items)
    wb = Workbook()
    ws = wb.active
    ws.title = "AI BOM"
    ws.cell(1, 1, "BOM (도면 + 3D, AI 분석)" if source_pdf else "BOM (3D, AI 분석)").font = st["title"]
    ws.row_dimensions[1].height = 34
    tmps = [_add_image(ws, company.logo_image(96), "M1", 100)]
    ws.cell(1, 15, company.MAKER).font = _xl_font(st["val"], bold=True)
    ws.cell(1, 15).hyperlink = company.HOMEPAGE
    d = ai.get("drawing", {})
    info = [("도번 / 도면 이름", f"{d.get('drawing_no', '')}  {d.get('title', '')}".strip()),
            ("개정 / 날짜", f"{d.get('revision', '')}  {d.get('date', '')}".strip()),
            ("도면 PDF", source_pdf or "(없음 — 3D 와 부품 그림만으로 AI 가 추정)"), ("3D", source_3d),
            ("만든 때", f"{_dt.datetime.now():%Y-%m-%d %H:%M}  ·  AI {MODEL}  ·  한일 판금 전개 {version_text()}")]
    for i, (k, v) in enumerate(info, 2):
        ws.cell(i, 1, k).font = st["key"]
        ws.cell(i, 3, v).font = st["val"]
    head = ["품번", "도번", "부품명", "모양 (3D)", "재질", "규격", "구분", "수량 (도면)", "수량 (3D)",
            "두께 (mm)", "전개 크기 (mm)", "개당 무게 (kg)", "합계 무게 (kg)", "3D 품번", "조립도 번호",
            "신뢰도", "비고"]
    widths = [7, 16, 26, 16, 11, 18, 8, 9, 9, 9, 17, 11, 11, 9, 16, 7, 44]
    r0 = 2 + len(info) + 1
    for j, (h, w) in enumerate(zip(head, widths), 1):
        c = ws.cell(r0, j, h)
        c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
        ws.column_dimensions[c.column_letter].width = w
    fmt = {8: "0", 9: "0", 10: "0.0#", 12: "0.000", 13: "0.000"}
    for k, row in enumerate(rows):
        a, ps = row["ai"], row["parts"]
        p0 = ps[0] if ps else None
        size = f"{p0.flat_w:.1f} × {p0.flat_h:.1f}" if p0 is not None and p0.flat_w else ""
        vals = [a["item_no"], a["part_no"], a["name"], None, a["material"] or (material if p0 and p0.kind != "기타" else ""),
                a["spec"], a["kind"], a["qty"] or None, row["qty3d"] or None,
                round(p0.thickness, 2) if p0 is not None and p0.thickness else None, size,
                p0.weight if p0 is not None else None,
                sum(p.total_weight for p in ps) if ps else None,
                ", ".join(str(p.no) for p in ps), bom.compress([i + 1 for p in ps for i in p.indices]),
                a["confidence"], a["remark"]]
        r = r0 + 1 + k
        for j, v in enumerate(vals, 1):
            c = ws.cell(r, j, v)
            c.font, c.border = st["val"], st["border"]
            c.alignment = Alignment(vertical="center", wrap_text=j in (3, 6, 15, 17))
            if j in fmt:
                c.number_format = fmt[j]
            if not row["qty_ok"] and j in (8, 9):
                c.fill = red
        ws.row_dimensions[r].height = 60
        if p0 is not None:
            tmps.append(_add_image(ws, bom.thumb(p0), f"D{r}", 112))
    ws.freeze_panes = ws.cell(r0 + 1, 4)
    r = r0 + 2 + len(rows)
    ws.cell(r, 1, "빨간 칸 = 도면 수량과 3D 수량이 다르거나, 짝지은 3D 부품이 없음. "
                  "AI 가 읽은 값이므로 도면과 한 번 맞춰 보세요.").font = st["key"]

    # 3D 에만 있는 부품
    wu = wb.create_sheet("3D 에만 있음")
    head2 = ["3D 품번", "부품명 (3D)", "모양", "수량", "구분", "두께 (mm)", "전개 크기 (mm)", "개당 무게 (kg)",
             "조립도 번호"]
    for j, h in enumerate(head2, 1):
        c = wu.cell(1, j, h)
        c.font, c.fill, c.alignment, c.border = st["head"], st["head_fill"], st["center"], st["border"]
        wu.column_dimensions[c.column_letter].width = [9, 26, 16, 7, 9, 9, 17, 12, 20][j - 1]
    for k, it in enumerate(unmatched, 2):
        size = f"{it.flat_w:.1f} × {it.flat_h:.1f}" if it.flat_w else ""
        vals = [it.no, it.name, None, it.qty, it.kind, round(it.thickness, 2) if it.thickness else None,
                size, it.weight, it.numbers]
        for j, v in enumerate(vals, 1):
            c = wu.cell(k, j, v)
            c.font, c.border = st["val"], st["border"]
            c.alignment = Alignment(vertical="center")
        wu.row_dimensions[k].height = 60
        tmps.append(_add_image(wu, bom.thumb(it), f"C{k}", 112))

    # 도면 정보와 참고
    wn = wb.create_sheet("도면 정보")
    wn.column_dimensions["A"].width = 18
    wn.column_dimensions["B"].width = 90
    labels = {"drawing_no": "도번", "title": "도면 이름", "revision": "개정", "company": "회사",
              "date": "날짜", "scale": "척도"}
    r = 1
    for key, lab in labels.items():
        wn.cell(r, 1, lab).font = st["key"]
        wn.cell(r, 2, d.get(key, "")).font = st["val"]
        r += 1
    r += 1
    wn.cell(r, 1, "AI 참고").font = _xl_font(st["val"], bold=True)
    for n in ai.get("notes", []):
        r += 1
        wn.cell(r, 2, n).alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(path)
    for t in tmps:
        try:
            os.remove(t)
        except OSError:
            pass
    return rows, unmatched
