import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models import nested_assembly_step  # noqa: E402

from hanil_unfold import assembly_calc, loader  # noqa: E402
from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import quote as q  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402


@pytest.fixture(scope="module")
def assy(tmp_path_factory):
    path = tmp_path_factory.mktemp("q") / "truck.step"
    nested_assembly_step(str(path))
    m = loader.load(str(path), use_cache=False)
    st = bc.BendSettings(material="SPCC")
    return m, assembly_calc.compute_all(m, st), st


def test_korean_amount():
    assert q.korean_amount(0) == "영"
    assert q.korean_amount(1_038_400) == "일백삼만팔천사백"
    assert q.korean_amount(33_528_000) == "삼천삼백오십이만팔천"
    assert q.korean_amount(1_0000_0000) == "일억"
    assert q.korean_amount(2_0005_0010) == "이억오만십" or q.korean_amount(2_0005_0010) == "이억오만일십"


def test_rates_load_merges_saved():
    r = q.load_rates('{"material": {"SPCC": 999}, "profit_pct": 5, "supplier": {"전화": "02"}}')
    assert r["material"]["SPCC"] == 999 and r["material"]["SUS304"] == q.MATERIAL_PRICE["SUS304"]
    assert r["profit_pct"] == 5 and r["supplier"]["전화"] == "02" and r["supplier"]["주소"] == ""
    assert q.load_rates("깨진 글")["profit_pct"] == q.DEFAULT_RATES["profit_pct"]


def test_quote_low_volume_laser(assy):
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=10, annual=1000, title="TRUCK")
    names = {p.name: p for p in qt.parts}
    assert {"SIDE PANEL", "BRACKET", "FLOOR PLATE", "BOSS"} <= set(names)
    assert {s.name for s in qt.subs} >= {"NUT M8"}
    panel = names["SIDE PANEL"]
    assert "레이저" in panel.method and panel.ops[0] == "레이저 절단"
    assert panel.n_ops == 1 + sum(o.startswith("절곡") for o in panel.ops) == 5     # 트레이: 절곡 4
    assert panel.qty == 2 and panel.die_cost == 0
    # 재료비 = 소요 kg × 단가 − 스크랩
    assert panel.material == pytest.approx(panel.gross_kg * 1300 - (panel.gross_kg - panel.weight) * 300, rel=0.05)
    assert names["BOSS"].method == "기계 가공"
    # 합계 관계
    assert qt.manufacturing == pytest.approx(qt.material + qt.process + qt.sub_total)
    assert qt.unit_price >= qt.manufacturing * 1.21 - 10
    assert qt.supply == qt.unit_price * 10
    assert qt.total == qt.supply + qt.vat
    assert qt.total_ops == sum(p.n_ops for p in qt.parts)


def test_quote_high_volume_dies_and_overrides(assy):
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=1000, annual=300_000)
    panel = next(p for p in qt.parts if p.name == "SIDE PANEL")
    assert "순차" in panel.method and panel.die is not None and panel.die_cost > 0
    assert qt.supply == qt.unit_price * 1000 + qt.die_total
    before = qt.unit_price
    qt.amortize_die = True
    assert qt.unit_price > before and qt.supply == qt.unit_price * 1000
    panel.process_override = 0.0
    panel.material_override = 123.0
    assert panel.process_cost == 0 and panel.unit == 123.0
    qt.subs[0].unit_price = 100
    assert qt.sub_total == pytest.approx(100 * qt.subs[0].qty)


def test_tonnage_and_machine_choice(assy):
    from hanil_unfold import costing as cs
    from hanil_unfold import diecalc as dc
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=1000, annual=300_000)
    panel = next(p for p in qt.parts if p.name == "SIDE PANEL")
    # 순차 금형: 한 프레스 = 공정 힘의 합, 그 × 1.3 이상인 가장 작은 프레스
    total = sum(o.tonf for o in panel.opc)
    assert panel.need_tonf == pytest.approx(total)
    from hanil_unfold import bom
    item = next(it for it in bom.build(m, parts, st.mat.density, (), st.mat.code) if it.name == "SIDE PANEL")
    rep = dc.review(item.result, st, strip=False)
    assert total >= (rep.loads[0].force_n + rep.loads[1].force_n) / dc.TON
    press = [x for x in rates["costing"]["machines"] if x["kind"] == cs.PRESS]
    need = total * 1.3
    expect = min((x for x in press if x["capacity"] >= need), key=lambda x: x["capacity"])
    assert panel.machines == [expect["name"]]
    # 저 생산량: 레이저 + 절곡기, 절곡마다 절곡기 톤수
    low = q.build(m, parts, st, rates, sets=10, annual=1000)
    lp = next(p for p in low.parts if p.name == "SIDE PANEL")
    kinds = [o.kind for o in lp.opc]
    assert kinds[0] == cs.LASER and kinds[1:] == [cs.BRAKE] * 4
    assert all(o.tonf > 0 and o.machine.startswith("절곡기") for o in lp.opc[1:])
    # 임률을 두 배로 → 가공비 두 배 (준비 포함)
    r2 = q.load_rates(None)
    for x in r2["costing"]["machines"]:
        x["rate"] *= 2
    lp2 = next(p for p in q.build(m, parts, st, r2, sets=10, annual=1000).parts if p.name == "SIDE PANEL")
    assert lp2.process == pytest.approx(2 * lp.process)
    # 기계가 모자라면 표시
    r3 = q.load_rates(None)
    r3["costing"]["machines"] = [x for x in r3["costing"]["machines"] if x["kind"] != cs.PRESS] + [
        {"name": "작은 프레스", "kind": cs.PRESS, "capacity": 1, "rate": 10000, "spm": 30, "setup_min": 0}]
    hp = next(p for p in q.build(m, parts, st, r3, sets=10, annual=300_000).parts if p.name == "SIDE PANEL")
    assert any("⚠" in o.note for o in hp.opc)


def test_die_quote_parts(assy):
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=1000, annual=300_000)
    d = next(p.die for p in qt.parts if p.name == "SIDE PANEL")
    names = [x[0] for x in d.lines]
    assert names[:7] == ["설계", "다이 세트·플레이트", "인서트 (SKD11)", "열처리", "가공 (와이어·MCT·연삭)",
                         "표준 부품", "조립·트라이"]
    sub = sum(x[2] for x in d.lines[:7])
    assert d.cost == pytest.approx(sub * 1.1 * 1.1)
    rates["costing"]["die"]["machining_per_station"] *= 2
    d2 = next(p.die for p in q.build(m, parts, st, rates, sets=1000, annual=300_000).parts if p.name == "SIDE PANEL")
    assert d2.cost > d.cost
    supply, vat, total = q.die_total_with_vat(qt)
    assert supply == pytest.approx(qt.die_total) and total == supply + vat


def test_outputs(assy, tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    m, parts, st = assy
    qt = q.build(m, parts, st, q.load_rates(None), sets=5, annual=300_000, title="TRUCK")
    qt.customer = "고객사"
    q.save_xlsx(qt, str(tmp_path / "q.xlsx"))
    q.save_pdf(qt, str(tmp_path / "q.pdf"))
    q.save_die_xlsx(qt, str(tmp_path / "d.xlsx"))
    q.save_die_pdf(qt, str(tmp_path / "d.pdf"))
    import openpyxl
    wb = openpyxl.load_workbook(tmp_path / "q.xlsx")
    assert wb.sheetnames == ["견적서", "산출 근거", "공정별", "기계·임률", "단가표"]
    ws = wb["견적서"]
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    assert any("일금" in t and q.korean_amount(qt.total) in t for t in texts)
    assert any("고객사" in t for t in texts)
    assert any("tf" in t for t in texts)
    assert wb["공정별"].max_row > len(qt.parts)
    wd = openpyxl.load_workbook(tmp_path / "d.xlsx")
    assert wd.sheetnames == ["금형 견적서", "금형 산출 근거", "금형 단가", "금형 간략도"]
    assert len(wd["금형 간략도"]._images) == len(qt.dies)
    assert (tmp_path / "q.pdf").stat().st_size > 5000 and (tmp_path / "d.pdf").stat().st_size > 3000


def test_saved_machines_survive_load():
    import json
    r = q.load_rates(None)
    r["costing"]["machines"] = [{"name": "우리 프레스 150", "kind": "프레스", "capacity": 150, "rate": 1, "spm": 20}]
    r["costing"]["die"]["design_per_station"] = 1
    back = q.load_rates(json.dumps(r, ensure_ascii=False))
    assert back["costing"]["machines"][0]["name"] == "우리 프레스 150"
    assert back["costing"]["die"]["design_per_station"] == 1
    assert back["costing"]["die"]["heat_kg"] == q.DEFAULT_RATES["costing"]["die"]["heat_kg"]


def test_dialog_save_all_records_latest_customer(assy, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    QApplication.instance() or QApplication([])
    from hanil_unfold import quote_dialog as qd
    from hanil_unfold.history import History
    m, parts, st = assy
    monkeypatch.setattr(qd.QDesktopServices, "openUrl", staticmethod(lambda *a: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "T_견적서.xlsx"), "")))
    h = History(str(tmp_path / "기록"))
    dlg = qd.QuoteDialog(m, parts, st, (), "TRUCK", history=h)
    dlg.annual.setValue(300_000)
    dlg.customer.setText("마바상사")          # 고친 뒤 다시 계산 없이 바로 저장
    dlg.save_all()
    rows = h.search_docs()
    assert {r.data["kind"] for r in rows} == {"생산 견적", "금형 견적"}
    assert all(r.data["customer"] == "마바상사" for r in rows)
    assert (tmp_path / "T_견적서.pdf").exists() and (tmp_path / "T_금형견적서.xlsx").exists()


def test_full_analysis_package(assy, tmp_path):
    import openpyxl
    from hanil_unfold import package
    m, parts, st = assy
    qt = q.build(m, parts, st, q.load_rates(None), sets=10, annual=300_000, title="TRUCK/BOX")
    steps = []
    files = package.run(qt, m, parts, st, str(tmp_path / "out"), progress=steps.append)
    names = [os.path.basename(f) for f in files]
    assert names == ["01_TRUCK_BOX_BOM.xlsx", "02_TRUCK_BOX_자재비.xlsx", "03_TRUCK_BOX_공정도.pdf",
                     "04_TRUCK_BOX_생산견적서.xlsx", "04_TRUCK_BOX_생산견적서.pdf",
                     "05_TRUCK_BOX_금형견적서.xlsx", "05_TRUCK_BOX_금형견적서.pdf",
                     "06_TRUCK_BOX_생산계획.xlsx", "06_TRUCK_BOX_생산계획.pdf",
                     "07_TRUCK_BOX_원가계산서.xlsx", "07_TRUCK_BOX_원가계산서.pdf",
                     "08_TRUCK_BOX_품질문서.xlsx", "08_TRUCK_BOX_품질문서.pdf"]
    assert all(os.path.getsize(f) > 1000 for f in files) and len(steps) == 8
    wb = openpyxl.load_workbook(files[1])
    assert wb.sheetnames == ["요약", "부품별 자재비", "재질별 소요량", "부자재"]
    ws = wb["부품별 자재비"]
    total = sum(ws.cell(r, 10).value for r in range(2, ws.max_row + 1))
    assert total == pytest.approx(qt.material, abs=len(qt.parts))
    pdf = open(files[2], "rb").read()
    assert pdf.count(b"/Type /Page") >= 1 + len(qt.parts)          # 차례 + 부품마다
    # 금형이 필요 없으면 금형 견적서는 안 만든다
    low = q.build(m, parts, st, q.load_rates(None), sets=10, annual=1000, title="T")
    names = [os.path.basename(f) for f in package.run(low, m, parts, st, str(tmp_path / "low"))]
    assert not any("금형견적서" in n for n in names) and len(names) == 11


def test_die_sketch(assy):
    from hanil_unfold import diesketch
    m, parts, st = assy
    qt = q.build(m, parts, st, q.load_rates(None), sets=100, annual=300_000)
    prog = next(d for d in qt.dies if "순차" in d.die_type)
    assert prog.plan is not None and prog.press_tonf > 0
    # 금형 길이 = 공정 수 × 피치 + 여유 (간략도와 금형비가 같은 크기)
    mg = q.load_rates(None)["costing"]["die"]["margin"]
    assert prog.size[0] == pytest.approx(len(prog.plan.stations) * prog.plan.pitch + 2 * mg)
    assert prog.size[1] == pytest.approx(prog.plan.strip_width + 2 * mg)
    img = diesketch.render(prog, 800, 500)
    assert img.width() == 800
    comp = next(d for d in qt.dies if "복합" in d.die_type)
    assert comp.plan is None and comp.outline is not None
    diesketch.render(comp, 800, 500)


def test_large_die_switches_to_casting():
    """대형 금형: 공정 하나 몸체 긴 변이 1000 mm 를 넘으면 주물 (FC300·FCD) 로 계산한다."""
    from models import drawn_cup, tray
    from hanil_unfold import costing as cs, procplan as pp
    from hanil_unfold.die_cost_dialog import part_item
    st = bc.BendSettings(material="SPCC")
    out = {}
    for key, shape in (("small", tray()), ("big", drawn_cup(300, 150, 20, 1.6))):
        r = unfold(loader.list_solids(shape)[0], settings=st)
        it = part_item(r, key, 7.85)
        rt = pp.route(r, st, 100_000)
        out[key] = cs.die_quote(it, rt.die_type, [s.op for s in rt.steps], cs.default_costing(), st)
    small, big = out["small"], out["big"]
    assert small.structure == "강판" and small.cast_kg == 0
    assert big.structure == "주물" and big.cast_kg > 1000 and "1,000" in big.reason
    names = [x[0] for x in big.lines]
    assert any("FC300" in n for n in names) and any("FCD" in n for n in names)
    assert any("모형" in n for n in names) and any("NC" in n for n in names)
    # 무게 × 단가: 주물 줄 금액 = kg × 원/kg
    fc = next(x for x in big.lines if "FC300" in x[0])
    assert fc[2] == pytest.approx(float(fc[1].split("=")[-1].split("kg")[0].replace(",", "")) * 3000, rel=0.01)
    # 직접 고르기: 강판 고정이면 큰 금형도 강판, 주물 고정이면 작은 금형도 주물
    c = cs.default_costing()
    c["die"]["structure"] = 1
    r = unfold(loader.list_solids(drawn_cup(300, 150, 20, 1.6))[0], settings=st)
    rt = pp.route(r, st, 100_000)
    assert cs.die_quote(part_item(r, "b", 7.85), rt.die_type, [s.op for s in rt.steps], c, st).structure == "강판"


def test_die_cost_dialog_and_maker_stamp(tmp_path):
    from openpyxl import load_workbook
    from models import drawn_cup
    from hanil_unfold import company
    from hanil_unfold import quote as q
    from hanil_unfold.die_cost_dialog import DieCostDialog
    st = bc.BendSettings(material="SPCC")
    r = unfold(loader.list_solids(drawn_cup(300, 150, 20, 1.6))[0], settings=st)
    dlg = DieCostDialog(r, st, "big_cup.step")
    assert dlg.q.dies and dlg.q.dies[0].structure == "주물"
    assert "주물" in dlg.text.toPlainText()
    x = str(tmp_path / "d.xlsx")
    q.save_die_xlsx(dlg.q, x)
    wb = load_workbook(x)
    assert wb.properties.creator == company.NAME
    assert company.MAKER in wb.worksheets[0].oddFooter.center.text
    q.save_die_pdf(dlg.q, str(tmp_path / "d.pdf"))
    dlg.close()
    assert not company.splash_pixmap("1.0").isNull()


def test_production_plan_and_costsheet(assy, tmp_path):
    from hanil_unfold import costsheet as cst
    from hanil_unfold import production as prod
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=8000, annual=100_000, title="TRUCK")
    pl = prod.plan(qt)
    p = pl.p
    avail = p["days"] * p["shifts"] * p["shift_hours"]
    assert pl.machines and all(ml.available == avail for ml in pl.machines)
    # 부하 = (개수 × 사이클 ÷ OEE + 준비) ÷ 가능 시간
    ml = pl.machines[0]
    assert ml.load == pytest.approx(ml.total / avail)
    pc = next(pc for pc in qt.parts if any(o.machine == ml.name and o.seconds for o in pc.opc))
    flow = next(f for f in pl.flows if f.no == pc.no)
    assert flow.pieces == pytest.approx(100_000 * pc.qty * (1 + p["defect_pct"] / 100), abs=1)
    assert pl.headcount > 0
    assert pl.phases and pl.phases[-1].name.startswith("양산") and pl.sop_week > 4
    # 생산량을 크게 늘리면 부하가 넘쳐 대수가 늘어난다
    big = prod.plan(q.build(m, parts, st, rates, sets=8000, annual=5_000_000, title="TRUCK"))
    assert big.overloaded and big.overloaded[0].units >= 2 and any("대 필요" in n for n in big.notes)
    # 원가계산서: 재료비 + 가공비 = 견적과 같고, 노무비 + 경비 = 가공비
    cs_ = cst.compute(qt)
    for ps, pc in zip(cs_.parts, qt.parts):
        assert ps.material == pytest.approx(pc.material, rel=1e-6)
        assert ps.labor + ps.expense == pytest.approx(pc.process_cost)
        assert ps.price >= ps.manufacturing
    assert cs_.set_price > 0
    sens = cst.sensitivity(qt)
    assert sens[0][1] < sens[2][1] < sens[4][1]               # 철강값이 오르면 단가도 오른다
    yrs = cst.year_table(cs_)
    assert yrs[1][1] == pytest.approx(yrs[0][1] * 0.97)
    qty = cst.qty_table(lambda a: q.build(m, parts, st, rates, sets=max(a // 12, 1), annual=a, title="T"),
                        {"qty_list": "1000,100000"}, qt)
    assert qty[0][1] > qty[1][1]                              # 적게 만들면 비싸다
    for mod, args in ((prod, (pl,)), (cst, (cs_, qt))):
        mod.save_xlsx(*args, str(tmp_path / f"{mod.__name__}.xlsx"))
        mod.save_pdf(*args, str(tmp_path / f"{mod.__name__}.pdf"))
        assert os.path.getsize(tmp_path / f"{mod.__name__}.pdf") > 5000


def test_quality_docs_and_items(assy, tmp_path):
    from openpyxl import load_workbook

    from hanil_unfold import bom
    from hanil_unfold import qualitydocs as qd
    from hanil_unfold.history import History
    m, parts, st = assy
    rates = q.load_rates(None)
    qt = q.build(m, parts, st, rates, sets=8000, annual=100_000, title="TRUCK")
    items = {it.no: it for it in bom.build(m, parts, st.mat.density, (), st.mat.code)}
    docs = [qd.build(pc, items[pc.no].result, st, "고객") for pc in qt.parts]
    d = docs[0]
    names = [s.name for s in d.pfd]
    assert names[:3] == ["원자재 입고", "수입검사", "자재 보관"] and names[-3:] == ["최종 검사", "포장", "출하"]
    assert len(d.pfd) == 6 + len(qt.parts[0].opc)
    assert all(1 <= f.s <= 10 and 1 <= f.o <= 10 and 1 <= f.d <= 10 for f in d.fmea)
    assert all(f.ap in "HML" and f.rpn == f.s * f.o * f.d for f in d.fmea)
    assert qd.action_priority(9, 5, 3) == "H" and qd.action_priority(3, 2, 2) == "L"
    assert any(c.special == "◇" for c in d.cp)
    x = str(tmp_path / "qd.xlsx")
    qd.save_xlsx(docs, x)
    assert load_workbook(x).sheetnames == ["공정 흐름도", "PFMEA", "관리계획서"]
    qd.save_pdf(docs, str(tmp_path / "qd.pdf"))
    # 아이템 대장: 등록 → 견적 리비전 R0, R1 → 수주
    h = History(str(tmp_path / "h"))
    rid = h.add_item({"customer": "A사", "part_no": "123", "part_name": "BOX", "annual": 100000})
    assert h.get_item(rid).data["status"] == "접수"
    assert h.add_revision(rid, qt.unit_price, qt.die_total, 100000) == "R0"
    assert h.add_revision(rid, qt.unit_price * 0.95, qt.die_total, 100000) == "R1"
    it = h.get_item(rid).data
    assert it["status"] == "제출" and it["unit_price"] == pytest.approx(qt.unit_price * 0.95)
    h.update_item(rid, {"status": "수주"})
    h.add_revision(rid, 1, 1)
    assert h.get_item(rid).data["status"] == "수주"               # 수주·실주는 리비전으로 안 바뀜
    stats, rate = h.item_stats()
    assert stats["수주"][0] == 1 and rate == 1.0
    h.export_items_xlsx(str(tmp_path / "items.xlsx"))
    assert load_workbook(str(tmp_path / "items.xlsx")).sheetnames == ["아이템 대장", "견적 리비전"]


def test_quote_dialog_new_tabs(assy):
    from hanil_unfold.quote_dialog import QuoteDialog
    m, parts, st = assy
    dlg = QuoteDialog(m, parts, st, title="TRUCK")
    tabs = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
    assert {"생산 견적", "원가계산서", "품질 문서"} <= set(tabs)
    assert dlg.t_load.rowCount() > 0 and dlg.t_cost.rowCount() > 10 and dlg.t_fmea.rowCount() > 0
    dlg.close()


def test_part_package_one_part(tmp_path):
    """부품 하나 한 번에 분석: 전개·성형 해석·금형·견적·원가·생산·품질 파일과 요약."""
    from models import tray
    from hanil_unfold import part_package as ppk
    st = bc.BendSettings(material="SPCC")
    sol = loader.list_solids(tray())[0]
    r = unfold(sol, settings=st)
    steps = []
    files, summ = ppk.run(r, st, "tray.step", str(tmp_path / "pkg"), 100_000, customer="A사", solid=sol,
                          progress=steps.append)
    names = [os.path.basename(f) for f in files]
    assert names[0] == "00_tray_요약.pdf"
    for want in ("01_tray_전개도.dxf", "01_tray_전개보고서.pdf", "02_tray_성형해석.pdf", "03_tray_금형검토.xlsx",
                 "04_tray_금형공정도.pdf", "04_tray_금형공정도.dxf", "05_tray_생산견적서.pdf", "05_tray_금형견적서.pdf",
                 "06_tray_원가계산서.xlsx", "07_tray_생산계획.pdf", "08_tray_품질문서.xlsx"):
        assert want in names, want
    assert all(os.path.getsize(f) > 1000 for f in files)
    assert len(steps) == 8
    for k in ("전개 크기", "성형 해석", "금형 형식", "금형비", "판매 단가", "설비 부하", "양산 일정", "PFMEA"):
        assert k in summ
    assert "순차" in summ["금형 형식"] and summ["성형 해석"].startswith("적합")


def test_part_package_dialog(assy, tmp_path):
    from hanil_unfold.part_package_dialog import PartPackageDialog
    m, parts, st = assy
    seen = []

    def select(i):
        seen.append(i)
        return parts[i].result, m.solids[i], m.names[i]
    dlg = PartPackageDialog(m, 0, select, lambda: st)
    assert dlg.part.count() == len(m.solids) and seen == [0]
    dlg.part.setCurrentIndex(1)
    assert seen == [0, 1]
    dlg.close()


def test_rates_keep_production_costsheet_and_machine_rate():
    import json
    from hanil_unfold import costing as cs
    r = q.load_rates(json.dumps({"production": {"oee": 0.6}, "costsheet": {"cr_pct": 2.0},
                                 "rate_calc": {"프레스 60톤": {"price": 1e8}}}))
    assert r["production"]["oee"] == 0.6 and r["costsheet"]["cr_pct"] == 2.0
    assert r["rate_calc"]["프레스 60톤"]["price"] == 1e8
    total, rows = cs.machine_rate({"price": 3.6e8, "years": 10, "hours": 3600, "interest_pct": 5, "area_m2": 0,
                                   "power_kw": 0, "maint_pct": 0, "wage": 30000, "crew": 1})
    # 감가상각 10,000 + 이자 (1.8 억 × 5 % ÷ 3600 = 2,500) + 사람 30,000
    assert total == pytest.approx(10000 + 2500 + 30000)
    assert rows[0][1] == pytest.approx(10000)
