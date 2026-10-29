import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import models  # noqa: E402
from test_bom import FakeClient  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import loader  # noqa: E402
from hanil_unfold import process as pr  # noqa: E402
from hanil_unfold import procplan as pp  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402


@pytest.fixture(scope="module")
def channel():
    """ㄷ자 (웹 60, 벽 30, 두께 2, 폭 60): 두 벽 동축 Ø8, 웹에 가까운 Ø6 둘, 절곡 옆 Ø5."""
    ch = models.profile_part([("L", 30), ("B", 90, 2), ("L", 60), ("B", 90, 2), ("L", 30)], 2.0, 60)
    sh = models.drill(ch, 15, 0, 30, 8, axis=(0, 1, 0))
    sh = models.drill(sh, 0, 25, 20, 6, axis=(1, 0, 0))
    sh = models.drill(sh, 0, 34, 20, 6, axis=(1, 0, 0))
    sh = models.drill(sh, 0, 57, 45, 5, axis=(1, 0, 0))
    return unfold(loader.list_solids(sh)[0])


def by_size(rt):
    return {round(h.size): [x for x in rt.features.holes if round(x.size) == round(h.size)]
            for h in rt.features.holes}


def test_hole_rules(channel):
    rt = pp.route(channel, bc.BendSettings(), 300_000)
    holes = by_size(rt)
    coax = holes[8]
    assert len(coax) == 2 and all(h.cam and h.reason == "R4" for h in coax)
    assert coax[0].coaxial == coax[1].label and "플랜지" in coax[0].panel
    near = holes[5][0]
    assert near.after_bend and near.reason == "R3" and near.near_bend[1] < 3 * 2.0
    close = holes[6]
    assert sorted(h.group for h in close) == [0, 1]          # R5 로 나뉨
    assert all(not h.after_bend for h in close)
    ops = [s.op for s in rt.steps]
    assert ops == ["피어싱 1", "피어싱 2", "노칭 · 외곽", "절곡", "후 피어싱", "캠 피어싱", "분리"]
    assert "↔" in rt.steps[5].detail and rt.steps[5].detail.count("↔") == 1


def test_die_type_by_quantity_and_shape(channel):
    st = bc.BendSettings()
    assert "레이저" in pp.route(channel, st, 1000).die_type
    assert "단발" in pp.route(channel, st, 50_000).die_type
    assert "순차" in pp.route(channel, st, 300_000).die_type
    flat = unfold(loader.list_solids(models.drill(models.profile_part([("L", 80)], 2.0, 50), 40, 0, 25, 10))[0])
    assert "복합" in pp.route(flat, st, 50_000).die_type
    dish = unfold(loader.list_solids(models.dish())[0])
    rt = pp.route(dish, st, 300_000)
    assert rt.features.forming and rt.die_type == "트랜스퍼 금형"
    assert [s.op.split()[0] for s in rt.steps][:4] == ["DR", "TR/PI", "FL", "RST"]


def test_strip_follows_rules(channel):
    plan = pr.progressive(channel, bc.BendSettings())
    kinds = [(s.kind, s.title) for s in plan.stations]
    assert [t for _, t in kinds] == ["피어싱 1", "피어싱 2", "노칭 (외곽)", "절곡", "후 피어싱", "캠 피어싱",
                                      "분리 (컷오프)"]
    pierced = [h for s in plan.stations for h in s.holes]
    assert sorted(pierced) == list(range(len(plan.holes)))      # 모든 구멍을 한 번씩


def test_ai_review_uses_draft_and_pdf(channel, tmp_path):
    rt = pp.route(channel, bc.BendSettings(), 300_000)
    answer = {"die_type": "순차 금형", "die_reason": "R1", "steps": [{"op": "피어싱", "detail": "H1", "reason": "R2"}],
              "drawing_notes": ["위치도 0.1"], "warnings": []}
    fc = FakeClient(answer)
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    out = pp.ai_review(rt, str(pdf), 300_000, client=fc)
    assert out == answer and rt.ai == answer
    content = fc.kw["messages"][0]["content"]
    assert content[0]["type"] == "document"
    assert "캠 피어싱" in content[-1]["text"] and "R4" in content[-1]["text"]
    assert fc.kw["output_config"]["format"]["schema"] == pp.AI_SCHEMA


def test_route_page_in_pdf(channel, tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    rt = pp.route(channel, bc.BendSettings(), 300_000)
    plan = pr.progressive(channel, bc.BendSettings())
    out = tmp_path / "p.pdf"
    pr.save_pdf(plan, str(out), "ch", route=rt)
    assert out.read_bytes().count(b"/Type /Page") >= 3      # 쪽 2 + 쪽 목록


def test_die_review_excel_and_pdf(channel, tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from hanil_unfold import diecalc as dc
    from hanil_unfold import die_dialog as dd
    st = bc.BendSettings()
    rep = dc.review(channel, st)
    img = dd.render_strip(channel, rep.strip)
    plan = dc.draw_plan(100, 50, 6, 2.0, st.mat)
    rt = pp.route(channel, st, 300_000)
    pplan = pr.progressive(channel, st)
    dd.save_xlsx(rep, str(tmp_path / "d.xlsx"), "ch", img, plan, rt, pplan)
    dd.save_pdf(rep, str(tmp_path / "d.pdf"), "ch", img, plan, rt, pplan)
    import openpyxl
    wb = openpyxl.load_workbook(tmp_path / "d.xlsx")
    assert wb.sheetnames == ["하중", "설계 규칙", "스트립", "원통 드로잉", "자동 공정 설계", "금형 공정도"]
    assert (tmp_path / "d.pdf").read_bytes().count(b"/Type /Page") >= 5      # 4 쪽 + 목록
