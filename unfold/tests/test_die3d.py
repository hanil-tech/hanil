"""금형 3D 조립 (die3d): 부품 · 표준품 규격 · 가공 구멍 · 높이·행정 점검 · STEP (이름) · 조립도 · 가공도 · 파트리스트."""
import math

import numpy as np
import pytest

import models
from hanil_unfold import bendcalc as bc
from hanil_unfold import diecalc as dc
from hanil_unfold import die3d, diestd, loader
from hanil_unfold.unfolder import unfold


@pytest.fixture(scope="module")
def plate():
    st = bc.BendSettings(material="SPCC")
    s, _ = models.spline_plate(t=2.0, hole_d=12.0)
    r = unfold(s, settings=st)
    return r, st, die3d.build(r, st)


def test_parts_and_sizes(plate):
    r, st, a = plate
    names = [p.name for p in a.parts]
    for must in ("하형 다이 세트", "다이 플레이트", "스트리퍼 플레이트", "펀치 플레이트", "상형 다이 세트", "가이드 포스트",
                 "가이드 부시", "블랭킹 펀치", "피어싱 펀치 Ø12", "파일럿 핀", "다이 스프링", "스트리퍼 볼트", "스트립 가이드"):
        assert must in names
    assert a.kind.startswith("2 공정")                     # 구멍 있음 → 피어싱 → 블랭킹 (파일럿)
    assert [p.no for p in a.parts] == list(range(1, len(a.parts) + 1))
    die = a.plate("다이 플레이트")
    F = a.force_n
    assert die.prims[0].p[5] >= dc.die_plate_thickness(F) and die.prims[0].p[5] % 5 == 0
    assert len(die.prims[0].cuts) == 4                     # (블랭크 · 구멍) × (랜드 · 빠짐)
    assert next(p for p in a.parts if p.name == "가이드 포스트").qty == 4
    assert a.L > a.W > 0 and a.shut > 100
    assert any("절단력" in n for n in a.notes)
    assert all(p.weight >= 0 for p in a.parts) and a.plate("하형 다이 세트").weight > 10


def test_standard_lengths_and_checks(plate):
    _, _, a = plate
    for p in a.parts:
        if p.name.startswith("육각 구멍 붙이 볼트"):
            L = float(p.size.split("×")[1])
            assert L in diestd.SHCS_L
        if p.name.startswith("다우얼 핀"):
            assert float(p.size.split("×")[1]) in diestd.DOWEL_L
        if p.name == "스트리퍼 볼트":
            assert float(p.size.split("×")[1].split("(")[0]) in diestd.STRIPPER_L
    sp = a.spring
    assert sp.L in diestd.SPRING_L and sp.D in diestd.SPRING_D
    assert sp.defl_pct <= sp.limit_pct
    # 모든 점검 적합 (스프링 힘 · 휨 · 볼트 물림 · 머리 자리 · 펀치 응력·좌굴 · 다이 벽)
    bad = [c for c in a.checks if c[3] != "적합"]
    assert not bad, bad
    # 높이: 하사점 = 열림 − (열림 틈 + 스트리퍼 안 + 진입)
    assert a.open_h - a.shut == pytest.approx(max(10.0, 4 * 2.0) + die3d.RETRACT + die3d.ENTRY)


def test_holes_clear_of_cutting_edges(plate):
    _, _, a = plate
    die = a.plate("다이 플레이트").prims[0]
    openings = [c[0] for c in die.cuts if not c[1]]
    for name in die3d.PLATES:
        pr = a.plate(name).prims[0]
        x0, y0, _, dx, dy, _ = pr.p
        for h in pr.holes:
            r = (h.cb[0] if h.cb else h.d) / 2
            assert x0 + r <= h.x <= x0 + dx - r and y0 + r <= h.y <= y0 + dy - r
            if "펀치" in h.spec or "포스트" in h.spec or "부시" in h.spec or "생크" in h.spec:
                continue
            assert all(die3d._dist(P, (h.x, h.y)) > r for P in openings), (name, h.spec)
    # 같은 판 구멍끼리 겹치지 않음
    for name in die3d.PLATES:
        hs = a.plate(name).prims[0].holes
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                ri = (hs[i].cb[0] if hs[i].cb else hs[i].d) / 2
                rj = (hs[j].cb[0] if hs[j].cb else hs[j].d) / 2
                assert math.hypot(hs[i].x - hs[j].x, hs[i].y - hs[j].y) > ri + rj, (name, hs[i].spec, hs[j].spec)


def test_pressure_center_on_die_center(plate):
    _, _, a = plate
    assert abs(a.cop[0]) < 0.5


def test_spring_pick():
    sp = diestd.pick_spring(5000.0, 7.0, pocket_max=25.0)
    assert sp is not None
    assert sp.n * sp.rate * (sp.preload + 1.0) >= 5000.0 - 1e-6
    assert sp.preload + sp.stroke <= diestd.LIFE * diestd.SPRING_CLASS[sp.cls][2] * sp.L + 1e-9
    assert diestd.up_std(41, diestd.SHCS_L) == 45 and diestd.down_std(41, diestd.SHCS_L) == 40
    # Ø10 × 25 청색 = 16 N/mm (Lesjöfors) 기준
    assert diestd.spring_rate(10, 25, "중하중") == pytest.approx(16.0)


def test_step_names_and_reload(plate, tmp_path):
    _, _, a = plate
    p = die3d.save_step(a, str(tmp_path / "die.step"))
    m = loader.load(p, use_cache=False)
    n_solids = sum(len(x.prims) for x in a.parts)
    assert len(m.solids) == n_solids
    assert m.names[0] == "01 LOWER DIE SET" and any("PIERCE PUNCH" in n for n in m.names)
    # 곡선 외곽은 B-스플라인 (면 수 적게) — 파일 작고 솔리드가 성함, 부피는 구멍 뺀 어림과 2 % 안
    import os

    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    assert os.path.getsize(p) < 4e6
    assert all(BRepCheck_Analyzer(s_).IsValid() for s_ in m.solids)
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(m.solids[2], g)
    assert g.Mass() == pytest.approx(die3d._volume(a.plate("다이 플레이트").prims[0]), rel=0.02)


def test_drawing_and_parts_list(plate, tmp_path):
    _, _, a = plate
    img = die3d.render(a, 900, 450)
    assert not img.isNull()
    x = die3d.save_xlsx(a, str(tmp_path / "pl.xlsx"), "판")
    import openpyxl
    wb = openpyxl.load_workbook(x)
    assert wb.sheetnames[:5] == ["파트리스트", "조립도", "점검", "날 치수 · 프레스", "가공 구멍표"]
    ws = wb["파트리스트"]
    assert [c.value for c in ws[3]][:len(die3d.HEAD)] == die3d.HEAD
    assert ws.cell(4, 2).value == "하형 다이 세트"
    pdf = die3d.save_pdf(a, str(tmp_path / "as.pdf"), "판")
    assert open(pdf, "rb").read(4) == b"%PDF"


def test_plate_dxf(plate, tmp_path):
    import ezdxf
    _, _, a = plate
    p = die3d.save_dxf(a, str(tmp_path / "plates.dxf"))
    doc = ezdxf.readfile(p)
    msp = doc.modelspace()
    lay = {e.dxf.layer for e in msp}
    assert {"CONTOUR", "WIRE", "RELIEF", "TAP", "REAM", "CBORE", "TEXT"} <= lay
    assert len(msp.query("LWPOLYLINE[layer=='CONTOUR']")) == len(die3d.PLATES)
    n_holes = sum(len(a.plate(n).prims[0].holes) for n in die3d.PLATES)
    assert len(msp.query("CIRCLE[layer!='CBORE']")) == n_holes
    rows = die3d.hole_tables(a)
    assert len(rows) == len(die3d.PLATES) and all(isinstance(r[2], float) for _, rs in rows for r in rs)


def test_progressive_die_uses_strip():
    from hanil_unfold import process as pr
    st = bc.BendSettings(material="SPCC")
    r = unfold(models.profile_part([("L", 40), ("B", 90, 2.0), ("L", 25)], 1.6, 30), settings=st)
    plan = pr.progressive(r, st)
    a = die3d.build(r, st, plan=plan)
    assert a.kind.startswith("순차")
    die = next(p for p in a.parts if p.name == "다이 플레이트")
    assert die.prims[0].p[3] >= len(plan.stations) * plan.pitch
    assert "블랭킹 펀치" not in [p.name for p in a.parts]


def test_edge_sizes_wear_allowance(plate):
    """피어싱: 펀치 = 최소 + xΔ, 다이 = 펀치 + 2c / 블랭킹: 다이 = 최대 − xΔ, 펀치 = 다이 − 2c."""
    r, st, a = plate
    t = r.thickness
    c = dc.clearance_pct(st.mat, t) / 100 * t
    pierce = next(e for e in a.edges if e[0] == "피어싱")
    T = diestd.general_tol(12.0, "m")
    assert T == 0.2
    x = diestd.wear_x(t, 2 * T)
    assert x == 0.75                                       # t 2, Δ 0.4 (0.20 ~ 0.42)
    dp = 12.0 - T + x * 2 * T
    assert float(pierce[6][1:]) == pytest.approx(dp, abs=2e-3)
    assert float(pierce[5][1:]) == pytest.approx(dp + 2 * c, abs=2e-3)
    blank = next(e for e in a.edges if e[0].startswith("블랭킹"))
    L = float(blank[1].split("×")[0])
    Tb = diestd.general_tol(L, "m")
    xb = diestd.wear_x(t, 2 * Tb)
    assert float(blank[5].split("×")[0]) == pytest.approx(L + Tb - xb * 2 * Tb, abs=0.02)
    assert float(blank[6].split("×")[0]) == pytest.approx(L + Tb - xb * 2 * Tb - 2 * c, abs=0.02)
    # 파일럿 = 뚫린 구멍 (피어싱 펀치) − 0.05
    pil = next(p for p in a.parts if p.name == "파일럿 핀")
    assert pil.prims[0].p[3] * 2 == pytest.approx(dp - 0.05, abs=2e-3)


def test_press_load_energy_and_bolts(plate):
    r, st, a = plate
    pr = a.press
    assert pr["total_kn"] == pytest.approx(pr["cut_kn"] + pr["spring_kn"])
    assert pr["spring_kn"] > 0
    assert pr["need_tf"] == pytest.approx(pr["total_kn"] * 1000 * 1.3 / dc.TON)
    assert pr["ok"] and pr["machine"]
    # 에너지 = F t k (연강 0.45)
    assert pr["energy_j"] == pytest.approx(a.force_n * r.thickness * die3d.penetration(st.mat) / 1000)
    assert 0.3 < a.usage["ratio"] < 1.0
    # 상형 볼트 인장 점검이 있고 적합
    assert any(c[0].startswith("상형 볼트 인장") and c[3] == "적합" for c in a.checks)


def test_small_press_flags_and_more_bolts():
    st = bc.BendSettings(material="SPFC780")
    s, _ = models.spline_plate(t=3.2, hole_d=5.0)
    r = unfold(s, settings=st)
    small = [{"name": "프레스 30톤", "kind": "프레스", "capacity": 30, "stroke": 100}]
    a = die3d.build(r, st, machines=small)
    assert not a.press["ok"] and "전단각" in a.press["shear_note"]
    assert any(c[0] == "프레스" and c[3] == "검토" for c in a.checks)
    nb = next(p for p in a.parts if p.name.startswith("육각 구멍 붙이 볼트") and "상형" in p.name).qty
    assert nb > 4                                          # 스트리핑 힘이 커서 볼트를 늘림
    assert any(c[0].startswith("상형 볼트 인장") and c[3] == "적합" for c in a.checks)
    assert any("Ø5 압축 응력" in c[0] and c[3] == "검토" for c in a.checks)   # d / t 1.6 고장력강
