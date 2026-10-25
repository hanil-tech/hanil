"""부품 한 번에 분석: 도면에서 고른 부품 하나로 전개 → 성형 해석 → 금형 검토·공정 설계·공정도 → 금형 견적 (간략도) →
생산 견적서 → 원가계산서 → 생산 계획 → 품질 문서 (PFD·PFMEA·관리계획서) 를 한 폴더에, 첫 장은 한 쪽 요약.

  00_요약.pdf             핵심 숫자 한 쪽 (전개 크기·무게·성형 판정·금형 형식·톤수·금형비·단가·부하·양산 일정·AP H)
  01_전개도.dxf · 01_전개보고서.pdf/.xlsx
  02_성형해석.pdf/.xlsx
  03_금형검토.pdf/.xlsx     하중·설계 규칙·스트립·드로잉·자동 공정 설계·공정도
  04_금형공정도.pdf (.dxf — 순차 금형)
  05_생산견적서 · 05_금형견적서 (금형이 있으면, 간략도 포함)
  06_원가계산서 (양산 로트 기준, 수량별 단가표)
  07_생산계획 (설비 부하·인원·소재·금형→양산 일정)
  08_품질문서 (공정 흐름도·PFMEA·관리계획서)
"""
from __future__ import annotations

import datetime as _dt
import os
import re

from . import bendcalc as bc


def _safe(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s or "part").strip() or "part"


def make_quote(item, settings, rates, annual, cache=None, customer="", title=""):
    """부품 하나의 견적 (양산 로트 = 연간 ÷ 1 년 로트 수)."""
    from . import production as prod
    from . import quote as qt_
    lots = max(prod.params(rates)["lots_per_year"], 1)
    lot = max(int(annual / lots), 1)
    pc = qt_.part_cost(item, settings, rates, annual, cache, lot=lot)
    q = qt_.Quote(title or item.name, lot, annual, [pc], [], rates)
    q.customer = customer
    return q


def run(result, settings: bc.BendSettings, name, folder, annual=100_000, rates=None, customer="", solid=None,
        source_path="", progress=None, report_data=None):
    """파일들을 folder 에 만들고 (파일 목록, 요약 dict) 를 돌려준다."""
    from . import costsheet as cst
    from . import diecalc as dc
    from . import die_dialog as dd
    from . import dxf_export, formsim, report
    from . import process as pr
    from . import procplan as pp
    from . import production as prod
    from . import quote as qt_
    from . import qualitydocs as qd
    from .die_cost_dialog import part_item

    rates = rates or qt_.load_rates(None)
    os.makedirs(folder, exist_ok=True)
    title = _safe(os.path.splitext(name)[0])
    files = []
    summ = {}

    def step(t):
        if progress:
            progress(t)

    def out(fn):
        f = os.path.join(folder, fn.format(title))
        files.append(f)
        return f

    mat = settings.mat
    # 1. 전개
    step("전개도 · 전개 보고서")
    dxf_export.save(result, out("01_{}_전개도.dxf"), part_name=title, density=mat.density)
    d = report_data or report.ReportData(title, source_path, result, settings, solid)
    report.save_pdf(d, out("01_{}_전개보고서.pdf"))
    report.save_xlsx(d, out("01_{}_전개보고서.xlsx"))
    m = d.metrics
    w, h = result.size
    summ.update({"부품": title, "재질·두께": f"{mat.code} t{result.thickness:g}",
                 "전개 방식": "성형품 근사 (원스텝)" if result.mode == "forming" else "판금 정확 전개",
                 "전개 크기": f"{w:,.1f} × {h:,.1f} mm", "블랭크": f"{m.blank_area:,.0f} mm² · {m.weight_kg:.3f} kg · "
                 f"수율 {m.yield_ratio:.0%}", "절곡": f"{len(result.bends)} 곳"})
    # 2. 성형 해석
    step("성형 해석")
    fa = formsim.analyze(result, settings)
    formsim.save_pdf(fa, out("02_{}_성형해석.pdf"), title)
    formsim.save_xlsx(fa, out("02_{}_성형해석.xlsx"), title)
    if fa.mode == "forming":
        fr = fa.zone_frac
        body = (f"파단 {fr[0]:.1%} · 위험 {fr[1]:.1%} · 두꺼워짐 {fr[6]:.1%} · "
                f"두께 {fa.t_min:.2f}~{fa.t_max:.2f} mm")
    elif fa.bends:
        body = f"절곡 균열 위험도 최대 {fa.risk_top:.0%} (최소 R {fa.bends[0].r_min:.2f})"
    else:
        body = "평판"
    summ["성형 해석"] = f"{fa.verdict} — {body}"
    if fa.explain is not None:                 # 어디가 문제이고 무엇부터 할지 (자세한 것은 02 성형 해석의 설명 쪽)
        ex = fa.explain
        summ["성형 설명"] = ex.headline.split(" — ", 1)[-1] + (f" → {ex.advice[0]}" if ex.advice else "")
    # 3. 금형 검토 · 공정 설계 · 공정도
    step("금형 검토 · 자동 공정 설계 · 공정도")
    rep = dc.review(result, settings)
    strip_img = dd.render_strip(result, rep.strip) if rep.strip is not None else None
    rt = pp.route(result, settings, annual)
    draw = None
    if result.forming is not None and rep.blank_d:
        g = round(rep.blank_d * 0.6, 1)
        t = result.thickness
        try:
            draw = dc.draw_plan(g, round(g * 0.5, 1), max(4 * t, 1.0), t, mat, 0.0, max(4 * t, 1.0),
                                max(1.0, 0.03 * g * 0.5))
        except (ValueError, ZeroDivisionError):
            draw = None
    try:
        if draw is not None:
            plan = pr.drawing(result, settings, draw, max(4 * result.thickness, 1.0), round(rep.blank_d * 0.3, 1))
        else:
            plan = pr.progressive(result, settings)
    except Exception:
        plan = None
    dd.save_pdf(rep, out("03_{}_금형검토.pdf"), title, strip_img, draw, rt, plan)
    dd.save_xlsx(rep, out("03_{}_금형검토.xlsx"), title, strip_img, draw, rt, plan)
    if plan is not None:
        pr.save_pdf(plan, out("04_{}_금형공정도.pdf"), title, route=rt)
        if plan.kind == "progressive":
            pr.save_dxf(plan, out("04_{}_금형공정도.dxf"), title)
    summ["금형 형식"] = f"{rt.die_type} — {rt.die_reason}"
    summ["공정"] = " → ".join(s.op for s in rt.steps)
    # 4. 견적 · 금형 견적
    step("생산 견적서 · 금형 견적서")
    item = part_item(result, title, mat.density)
    cache = {}
    q = make_quote(item, settings, rates, annual, cache, customer, title)
    pc = q.parts[0]
    qt_.save_xlsx(q, out("05_{}_생산견적서.xlsx"))
    qt_.save_pdf(q, out("05_{}_생산견적서.pdf"))
    summ["필요 톤수"] = f"{pc.need_tonf:,.1f} tf · 기계 {', '.join(pc.machines) or '-'}"
    if q.dies:
        qt_.save_die_xlsx(q, out("05_{}_금형견적서.xlsx"))
        qt_.save_die_pdf(q, out("05_{}_금형견적서.pdf"))
        dq = q.dies[0]
        body = f"주물 {dq.cast_kg:,.0f} kg ({dq.reason})" if dq.structure == "주물" else "강판 다이 세트"
        summ["금형비"] = f"{dq.cost:,.0f} 원 (VAT 별도) · {dq.stations} 공정" + (f" × {dq.sets} 벌" if dq.sets > 1 else "") \
            + f" · {body}"
    else:
        summ["금형비"] = "금형 없음 (레이저 + 절곡기)"
    # 5. 원가계산서
    step("원가계산서 (수량별 단가)")
    cs_ = cst.compute(q)

    def builder(a):
        return make_quote(item, settings, rates, a, cache, customer, title)
    qty = cst.qty_table(builder, cs_.p, q)
    cst.save_xlsx(cs_, q, out("06_{}_원가계산서.xlsx"), qty, title)
    cst.save_pdf(cs_, q, out("06_{}_원가계산서.pdf"), qty, title)
    summ["판매 단가"] = f"{cs_.set_price:,.0f} 원/개 (원가계산서, 연 {annual:,} 개 · 로트 {q.sets:,}) · 견적서 {q.unit_price:,.0f} 원"
    # 6. 생산 계획
    step("생산 계획 (설비 부하·일정)")
    pl = prod.plan(q)
    prod.save_xlsx(pl, out("07_{}_생산계획.xlsx"), title)
    prod.save_pdf(pl, out("07_{}_생산계획.pdf"), title)
    top = pl.machines[0] if pl.machines else None
    summ["설비 부하"] = (f"{top.name} {top.load:.0%}" + (f" — {top.units} 대 필요" if top.load > 1 else "")
                     if top else "-") + f" · 인원 {pl.headcount:.1f} 명"
    if pl.phases:
        summ["양산 일정"] = f"수주 후 {pl.sop_week:.0f} 주 ({pl.week_date(pl.sop_week).isoformat()} 무렵)"
    # 7. 품질 문서
    step("품질 문서 (PFD·PFMEA·관리계획서)")
    docs = [qd.build(pc, result, settings, customer, "", fa=fa)]
    qd.save_xlsx(docs, out("08_{}_품질문서.xlsx"), title)
    qd.save_pdf(docs, out("08_{}_품질문서.pdf"), title)
    nh = sum(f.ap == "H" for f in docs[0].fmea)
    summ["PFMEA"] = f"{len(docs[0].fmea)} 줄 · 조치 우선순위 H {nh} · M {sum(f.ap == 'M' for f in docs[0].fmea)}"
    # 0. 요약
    step("요약")
    f0 = os.path.join(folder, f"00_{title}_요약.pdf")
    save_summary_pdf(summ, d, fa, f0, title, [os.path.basename(f) for f in files])
    files.insert(0, f0)
    return files, summ


def save_summary_pdf(summ, d, fa, path, title, names):
    from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

    from . import formsim, report
    from .report import _brand, _font, ensure_gui, version_text
    ensure_gui()
    pdf = QPdfWriter(path)
    pdf.setResolution(300)
    pdf.setPageLayout(QPageLayout(QPageSize(QPageSize.A3), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))
    pdf.setTitle(f"부품 분석 요약 - {title}")
    pdf.setCreator(f"한일 판금 전개 {version_text()}")
    k = 300 / 25.4
    W, H, m = 420.0, 297.0, 12.0

    def R(x, y, w, h):
        return QRectF(x * k, y * k, w * k, h * k)

    p = QPainter(pdf)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(20, 20, 20))
    p.setFont(_font(18, True))
    p.drawText(R(m, m, W - 2 * m, 10), Qt.AlignLeft | Qt.AlignVCenter, f"부품 분석 요약 — {title}")
    p.setFont(_font(8))
    _brand(p, R(m, m + 2, W - 2 * m, 6))
    p.setPen(QPen(QColor(20, 20, 20), 0.4 * k))
    p.drawLine(QPointF(m * k, (m + 11) * k), QPointF((W - m) * k, (m + 11) * k))
    y0 = m + 16
    # 왼쪽: 그림 (전개도 · 3D 또는 성형 해석)
    try:
        p.drawImage(R(m, y0, 190, 119), report.render_flat_image(d, 1600, 1000))
    except Exception:
        pass
    try:
        img = formsim.render_product(fa, formsim.VIEWS[0], 1200, 900) if fa.mode == "forming" \
            else report.render_model_image(d, 1200, 900)
        p.drawImage(R(m + 30, y0 + 124, 130, 97), img)
    except Exception:
        pass
    # 오른쪽: 표
    x = m + 200
    y = y0
    p.setFont(_font(10))
    for key, val in summ.items():
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(31, 78, 140))
        p.drawRect(R(x, y, 42, 9.5))
        p.setPen(QColor(255, 255, 255))
        p.setFont(_font(9.5, True))
        p.drawText(R(x + 2, y, 40, 9.5), Qt.AlignLeft | Qt.AlignVCenter, key)
        p.setPen(QColor(25, 25, 25))
        col = {"적합": QColor(40, 140, 60), "주의": QColor(200, 130, 0), "부적합": QColor(210, 40, 40)}
        if key == "성형 해석":
            p.setPen(col.get(val.split(" ")[0], QColor(25, 25, 25)))
        p.setFont(_font(9.5))
        p.drawText(R(x + 45, y, W - m - x - 45, 9.5), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, val)
        p.setPen(QPen(QColor(210, 214, 222), 0.2 * k))
        p.drawLine(QPointF(x * k, (y + 9.8) * k), QPointF((W - m) * k, (y + 9.8) * k))
        y += 10.4
    y += 4
    p.setPen(QColor(31, 78, 140))
    p.setFont(_font(10, True))
    p.drawText(R(x, y, 150, 6), Qt.AlignLeft | Qt.AlignVCenter, "이 폴더의 파일")
    y += 7
    p.setPen(QColor(60, 60, 60))
    p.setFont(_font(8))
    for n in names:
        if y > H - m - 8:
            break
        p.drawText(R(x + 2, y, W - m - x, 4.6), Qt.AlignLeft | Qt.AlignVCenter, n)
        y += 4.6
    p.setFont(_font(8))
    p.setPen(QColor(120, 120, 120))
    p.drawText(R(m, H - m - 5, W - 2 * m, 5), Qt.AlignLeft | Qt.AlignVCenter,
               f"{_dt.datetime.now():%Y-%m-%d %H:%M} · 한일 판금 전개 {version_text()} · 금형·단가·일정은 견적용 초안 — "
               "확정 전에 검토하세요.")
    p.end()
