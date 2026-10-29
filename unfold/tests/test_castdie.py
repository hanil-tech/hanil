"""주물 드로잉 금형 (castdie) 과 금형비 어림 (diecost)."""
import numpy as np
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import castdie, diecost, die3d, dieface, loader, tandem
from hanil_unfold.unfolder import unfold

ST = bc.BendSettings(material="SPCC")


@pytest.fixture(scope="module")
def pan():
    s = models.oil_pan()
    r = unfold(s, settings=ST, mode="forming")
    df = dieface.build(r.forming.V, r.forming.F, r.thickness)
    assert df is not None
    return s, r, df, castdie.design(df, r, ST)


def test_cast_die_parts_and_geometry(pan):
    """상형 다이 (FC300) · 펀치 · 누르개 (FCD) · 베이스, 가이드 · 쿠션 핀 · 밸런스 · 마모판 · 볼트 · 키, 펀치는 볼록 (제품 바닥이 꼭대기)."""
    s, r, df, a = pan
    names = [p.name for p in a.parts]
    for nm in ("하형 베이스", "드로우 펀치", "누르개 (블랭크 홀더)", "상형 다이", "가이드 포스트", "쿠션 핀", "밸런스 블록 (스토퍼)",
               "마모판 (누르개 안내)", "위치 키 (다우얼)"):
        assert any(n.startswith(nm) for n in names), nm
    pp = a.plate("드로우 펀치")
    pd = a.plate("상형 다이")
    assert "FCD" in pp.material and "FC300" in pd.material and pd.upper and not pp.prims[0].density == 0
    # 펀치 꼭대기 = 베이스 윗면 + 펀치 높이 = 깊이만큼 바인더 위
    pr = pp.prims[0]
    base = a.plate("하형 베이스").prims[0]
    depth = float(np.max(pr.grid["hz"])) - float(np.min(pr.grid["hz"]))
    assert depth == pytest.approx(110.0, abs=3.0)                            # 오일 팬 깊이 110 (두께 가운데 면)
    assert pr.p[2] == pytest.approx(base.p[2] + base.p[5], abs=0.5)           # 펀치가 베이스 위에
    assert pr.p[2] + pr.p[5] > base.p[2] + base.p[5] + depth                  # 꼭대기가 깊이보다 위 (누르개 두께 몫)
    # 상형: 열린 상태로 펀치 꼭대기보다 위, 형면 = 제품 + t
    assert pd.prims[0].p[2] > pr.p[2] + pr.p[5]
    assert float(np.max(pd.prims[0].grid["hz"])) - float(np.max(pr.grid["hz"])) == pytest.approx(
        r.thickness, abs=0.01)                                                # dz (열림) 는 따로
    assert all(c[3] == "적합" for c in a.checks), [c for c in a.checks if c[3] != "적합"]
    assert a.press["draw_kn"] > 100 and a.press["bhf_kn"] > 20
    assert a.press["beta"] < a.press["ldr"] and 1.0 < a.press["p_sie"] <= 2.5          # Siebel 면압 ≤ 표 값 (연강 2.5)
    assert a.press["draw_kn"] == pytest.approx(max(a.press["f_tab_kn"], a.press["f_sie_kn"]))
    assert sum(p.weight * p.qty for p in a.parts if "주물" in p.material) > 800
    assert all(len(_grid_or_none(p)) >= 0 for p in a.parts)


def _grid_or_none(p):
    return getattr(p.prims[0], "grid", None) or {}


def test_cast_die_solids_step(pan, tmp_path):
    from OCP.BRepCheck import BRepCheck_Analyzer
    _, _, _, a = pan
    for nm in ("하형 베이스", "드로우 펀치", "누르개 (블랭크 홀더)", "상형 다이"):
        sol = die3d._solid(a.plate(nm).prims[0])
        assert BRepCheck_Analyzer(sol).IsValid(), nm
    p = die3d.save_step(a, str(tmp_path / "cast.step"))
    m = loader.load(p, use_cache=False)
    assert len(m.solids) == sum(len(x.prims) for x in a.parts)


def test_cast_die_section_and_contours(pan):
    """단면 A-A: 상형 (위) · 누르개 (쿠션 위) · 펀치 · 베이스 네 몸체가 잘림, 펀치 등고선 · 실루엣."""
    from hanil_unfold import diedraw, dieview
    s, r, df, a = pan
    cache = {}
    sh = diedraw.section_sheet(a, {"product": "pan"}, "X", cache, y_cut=0.0)
    hatch = sum(1 for e in sh.ents if e[0] == "line" and e[5] == "HATCH")
    assert hatch > 100
    pr = a.plate("드로우 펀치").prims[0]
    top = castdie.grid_lines(pr, dieview.TOP[0], dieview.TOP[1])
    front = castdie.grid_lines(pr, dieview.FRONT[0], dieview.FRONT[1])
    assert len(top) >= 5 and len(front) >= 1
    sil = front[-1]
    assert np.ptp(sil[:, 1]) == pytest.approx(110.0, abs=5.0)                 # 실루엣 높이 = 깊이
    psh = diedraw.shape_part_sheet(a.plate("드로우 펀치"), a, {"product": "pan"}, "X")
    texts = [e[3] for e in psh.ents if e[0] == "text"]
    assert "우측면도" in texts and any("주물 FCD550" in t for t in texts)


def test_cast_die_cost_and_xlsx(pan, tmp_path):
    from openpyxl import load_workbook
    _, _, _, a = pan
    lines, tot = diecost.estimate(a)
    names = [n for n, _, _ in lines]
    assert "주물 FC300 (윗형 · 아랫형)" in names and "주물 FCD550 (펀치 · 누르개)" in names and "형면 NC 가공" in names
    assert 5e6 < tot < 1e8
    p = castdie.save_xlsx(a, str(tmp_path / "c.xlsx"), "pan")
    wb = load_workbook(p)
    assert "금형비" in wb.sheetnames and wb["금형비"].cell(4, 1).value == "설계 (주물 · 대형)"
    wl = wb["하중-행정"]
    rows = [[wl.cell(i, j).value for j in range(1, 7)] for i in range(4, 4 + len(a.loads.h))]
    assert rows[0][0] == 0 and rows[-1][0] == pytest.approx(a.loads.h[-1], abs=0.1)
    assert all(r_[5] >= r_[4] for r_ in rows)                                           # 프레스 능력 ≥ 하중 × 안전율 (모든 깊이)


def test_draw_loads_cylinder_matches_diecalc():
    """같은 둘레 원통: castdie.draw_loads 의 교재 식 · Siebel 면압 · 다이 R 권장이 diecalc (원통 컵 공정 계산) 와 같은 값."""
    mat = ST.mat
    t, d, D0 = 1.0, 100.0, 200.0
    A_blank = np.pi / 4 * D0 ** 2
    A_ring = np.pi / 4 * (D0 ** 2 - (d + 2 * 5.0) ** 2)
    ld = castdie.draw_loads(np.pi * d, A_blank, A_ring, t, mat, 60.0, 5.0)
    assert ld.d_eq == pytest.approx(d) and ld.D0 == pytest.approx(D0) and ld.beta == pytest.approx(2.0)
    from hanil_unfold import diecalc as dc
    assert ld.f_tab == pytest.approx(np.pi * d * t * mat.tensile_mpa * dc.force_k(0.5))
    assert ld.p_sie == pytest.approx(dc.siebel_holder_pressure(2.0, d, t, mat))
    assert ld.bhf == pytest.approx(ld.p_sie * A_ring)
    assert ld.f_sie == pytest.approx(dc.siebel_force(d, D0, t, mat) + 2 * castdie.MU * ld.bhf)
    assert ld.r_die_rec == pytest.approx(dc.die_radius(D0, d, t))
    # 하중 - 행정: 드로잉력 꼭대기 = 두 식 중 큰 값, 누르개 힘은 깊이에 따라 줄어듦, 프레스는 모든 깊이에서 능력 ≥ 하중 × 안전율
    assert ld.fd.max() == pytest.approx(ld.f_draw) and ld.fn[0] == pytest.approx(ld.bhf) and ld.fn[-1] < ld.fn[0]
    assert ld.ok and ld.cap is not None and np.all(ld.cap >= (ld.fd + ld.fn) * 1.3 - 1e-6)
    assert 0.0 < ld.h[ld.i_peak] < 30.0


def test_normal_offset_vertical_component():
    """높이장 법선 오프셋의 수직 성분 t·√(1 + |∇h|²): 30° 경사면은 t / cos 30°, 평탄부 가장자리는 t 그대로."""
    gx = np.arange(0.0, 101.0, 5.0)
    gy = np.arange(0.0, 51.0, 5.0)
    GX, GY = np.meshgrid(gx, gy)
    H = np.where(GX <= 50, np.tan(np.radians(30.0)) * GX, np.tan(np.radians(30.0)) * 50)   # 경사 → 평탄부
    sl = castdie._edge_slope(H, gx, gy)
    f = np.sqrt(1 + sl ** 2)
    assert f[5, 4] == pytest.approx(1 / np.cos(np.radians(30.0)), abs=1e-6)              # 경사 한가운데
    assert f[5, 10] == pytest.approx(1.0) and f[5, 15] == pytest.approx(1.0)              # 평탄부 가장자리 · 안
    assert f[5, 0] == pytest.approx(1 / np.cos(np.radians(30.0)), abs=1e-6)              # 격자 끝 (한쪽 차분)


def test_tandem_die_cost():
    """공정별 금형 금형비: 공정마다 어림 + 합, 캠 공정은 가공 배수 1.6."""
    r = unfold(models.channel_holes(), settings=ST)
    ops = tandem.design(r, ST)
    tot = diecost.total(ops)
    assert 1e7 < tot < 1e8
    cam = next(op for op in ops if op.kind == tandem.CAM)
    lines, _ = diecost.estimate(cam.die)
    mach = next(x for x in lines if x[0].startswith("가공"))
    assert "× 1.6" in mach[1]
    sh = tandem.line_sheets(tandem.Folder(r), ops, {"product": "ch"}, "HD")
    texts = [e[3] for e in sh[0].ents if e[0] == "text"]
    assert any("금형비 어림 합" in t for t in texts) and "금형비 만원" in texts


def test_offset_poly_and_pocket_bosses():
    """진짜 오프셋 (OCC): 오목한 ㄱ 자도 스스로 가로지르지 않음 · 넓이가 맞음. 빈 곳은 구멍 둘레를 보스로 남김."""
    from hanil_unfold import unfoldcheck
    L = np.array([[0, 0], [100, 0], [100, 60], [60, 60], [60, 100], [0, 100]], float)      # ㄱ 자, 넓이 8400
    for d in (5.0, -5.0, 20.0, -20.0):
        o = castdie.offset_poly(L, d)
        assert len(o) >= 3 and unfoldcheck.crossings([o]) == 0
    assert abs(castdie._area2(castdie.offset_poly(L, -5.0))) == pytest.approx(8400 - 360 * 5 + 2 * 25 - 25 + 25, rel=0.03)
    assert abs(castdie._area2(castdie.offset_poly(L, 5.0))) > 8400 + 360 * 5 - 50
    # 빈 곳 (네모) 과 피할 구멍: 구멍 둘레 ±r 는 어느 빈 곳에도 들어가지 않음
    cuts = castdie._pockets(0, 600, 0, 600, 0, 100, avoid=[(300, 300, 40)])
    assert cuts and all(not (c[0][:, 0].min() < 300 < c[0][:, 0].max() and c[0][:, 1].min() < 300 < c[0][:, 1].max())
                        for c in cuts)
    assert all(np.ptp(c[0], 0).min() >= 40 for c in cuts)
    area = lambda cs: sum(abs(castdie._area2(c[0])) for c in cs)                 # noqa: E731
    assert area(cuts) < area(castdie._pockets(0, 600, 0, 600, 0, 100))            # 보스만큼 빈 곳이 줄어듦


def test_section_by_edges_fallback():
    """교집합이 빈 결과일 때 교선으로 단면 고리를 잇는 길: 상자 (가운데 구멍) 단면 = 바깥 1 + 구멍 1."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from hanil_unfold import dieview
    box = BRepPrimAPI_MakeBox(gp_Pnt(-100, -50, 0), 200.0, 100.0, 60.0).Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, -60, 30), gp_Dir(0, 1, 0)), 15.0, 120.0).Shape()   # y 방향 관통 구멍
    sol = BRepAlgoAPI_Cut(box, hole).Shape()
    pln = gp_Pln(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0), gp_Dir(1, 0, 0)))
    face = BRepBuilderAPI_MakeFace(pln, -500, 500, -500, 500).Face()
    secs = dieview._section_by_edges(sol, face)
    assert len(secs) == 1 and len(secs[0][1]) == 1
    outer, holes = secs[0]
    assert np.ptp(outer, 0) == pytest.approx([200.0, 60.0], abs=0.5) and np.ptp(holes[0], 0) == pytest.approx([30.0, 30.0], abs=0.5)
