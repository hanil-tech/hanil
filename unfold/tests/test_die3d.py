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
            if h.axis != "z":
                continue
            r = (h.cb[0] if h.cb else h.d) / 2
            assert x0 + r <= h.x <= x0 + dx - r and y0 + r <= h.y <= y0 + dy - r
            if "펀치" in h.spec or "포스트" in h.spec or "부시" in h.spec or "생크" in h.spec:
                continue
            if h.kind == "와이어 시작":                       # 날 안쪽 (와이어 들어가는 구멍)
                assert all(die3d._dist(P, (h.x, h.y)) < -h.d for P in openings if die3d._inside(P, (h.x, h.y)))
                continue
            assert all(die3d._dist(P, (h.x, h.y)) > r for P in openings), (name, h.spec)
    # 옆면 아이볼트 탭은 세로 구멍·U 홈과 부딪히지 않음 (3D 범위)
    for name in die3d.PLATES:
        hs = a.plate(name).prims[0].holes
        for sh_ in [h for h in hs if h.axis != "z"]:
            y_in = sh_.y + (sh_.h if sh_.axis == "+y" else -sh_.h)
            ylo, yhi = sorted((sh_.y, y_in))
            for v in [h for h in hs if h.axis == "z"]:
                r = (v.cb[0] if v.cb else v.d) / 2
                hit = (abs(v.x - sh_.x) < r + sh_.d / 2 and ylo - r < v.y < yhi + r
                       and v.z0 < sh_.z0 + sh_.d / 2 and v.z0 + v.h > sh_.z0 - sh_.d / 2)
                assert not hit, (name, sh_.spec, v.spec)
    # 같은 판 구멍끼리 겹치지 않음
    for name in die3d.PLATES:
        hs = [h for h in a.plate(name).prims[0].holes if h.axis == "z"]
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
    assert all(n.isascii() for n in m.names)              # 한글은 STEP 에서 깨짐
    # 곡선 외곽은 B-스플라인 (면 수 적게) — 파일 작고 솔리드가 성함, 부피는 구멍 뺀 어림과 2 % 안
    import os

    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    assert os.path.getsize(p) < 8e6
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
    n_slot = sum(1 for n in die3d.PLATES for c in a.plate(n).prims[0].cuts if len(c) > 4 and c[4] == "slot")
    assert n_slot == 8                                    # 클램프 U 홈: 상·하형 세트 양 끝 2 개씩
    assert len(msp.query("LWPOLYLINE[layer=='CONTOUR']")) == len(die3d.PLATES) + n_slot
    n_holes = sum(len(a.plate(n).prims[0].holes) for n in die3d.PLATES)     # 옆면 탭도 원으로 (좌표표 자리)
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


def test_detail_parts(plate):
    """현장 상세: 블랭킹 펀치 고정 볼트, 스트립 가이드 볼트·핀, 스톱 블록 (하사점 0.5 틈), 와이어 시작 구멍."""
    _, _, a = plate
    names = [p.name for p in a.parts]
    for must in ("육각 구멍 붙이 볼트 M8 (펀치 고정)", "육각 구멍 붙이 볼트 M5 (스트립 가이드)", "다우얼 핀 (스트립 가이드)",
                 "스톱 블록", "육각 구멍 붙이 볼트 M8 (스톱 블록)"):
        assert any(n.startswith(must) for n in names), must
    punch = next(p for p in a.parts if p.name == "블랭킹 펀치").prims[0]
    taps = [h for h in punch.holes if h.kind == "탭"]
    assert len(taps) == 2
    assert all(-die3d._dist(punch.poly, (h.x, h.y)) >= 1.5 * 8 for h in taps)
    blk = next(p for p in a.parts if p.name == "스톱 블록").prims[0]
    top = blk.p[2] + blk.p[5]
    us = a.plate("상형 다이 세트").prims[0].p[2]
    travel = a.open_h - a.shut
    assert (us - travel) - top == pytest.approx(0.5)
    die = a.plate("다이 플레이트").prims[0]
    assert any(h.kind == "와이어 시작" for h in die.holes)
    assert sum(1 for h in die.holes if "스트립 가이드" in h.spec) >= 4


def test_drawing_set(plate, tmp_path):
    """도면집: 표지 · 조립도 · 스트립 배치도 · 부품도 (표제란, 척도, 구멍표) → PDF · DXF."""
    import ezdxf

    from hanil_unfold import diedraw
    _, _, a = plate
    sheets = diedraw.build(a, {"product": "판", "material": "SPCC t2"})
    titles = [s.title for s in sheets]
    assert titles[:3] == ["금형 설계 도면집", "금형 조립도", "스트립 배치도"]
    for nm in ("다이 플레이트", "펀치 플레이트", "블랭킹 펀치", "스트립 가이드", "스톱 블록"):
        assert nm in titles
    die = sheets[titles.index("다이 플레이트")]
    texts = [e[3] for e in die.ents if e[0] == "text"]
    assert "도번" in texts and "척도" in texts and die.scale in texts
    assert any(t.startswith("W1") for t in texts)                 # 와이어 날 기호
    assert any("H7" in t for t in texts) and any("M10 탭" in t for t in texts)
    pdf = diedraw.save_pdf(sheets, str(tmp_path / "set.pdf"))
    assert open(pdf, "rb").read(4) == b"%PDF"
    dx = diedraw.save_dxf(sheets, str(tmp_path / "set.dxf"))
    doc = ezdxf.readfile(dx)
    assert not doc.audit().errors
    assert {"FRAME", "OUTLINE", "HIDDEN", "CENTER", "DIM", "WIRE", "TEXT"} <= {e.dxf.layer for e in doc.modelspace()}
    assert not diedraw.render(sheets[1], 800).isNull()


def test_dialog_saves_all(plate, tmp_path, monkeypatch):
    """[금형 3D · 도면집 · 가공도 · 파트리스트…]: 여섯 파일 (STEP · 조립도 PDF · 파트리스트 · 가공 DXF · 도면집 PDF · DXF)."""
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

    from hanil_unfold import die_dialog
    r, st, _ = plate
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "판_금형.step"), ""))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("m (보통)", True))
    shown = {}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.setdefault("msg", a[2]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.setdefault("err", a[2]))
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda *a, **k: True)
    monkeypatch.setattr(die_dialog.DieDialog, "_dwg_converter", lambda self: "")
    from hanil_unfold import drawfmt
    monkeypatch.setattr(drawfmt, "find_dwg_writer", lambda user_path="": None)
    dlg = die_dialog.DieDialog(r, st, "판.step")
    dlg.save_die3d()
    assert "err" not in shown, shown.get("err")
    assert "DWG: 변환기" in shown["msg"]                      # 변환기 없으면 DXF 만 — 알림
    for suf in (".step", "_조립도.pdf", "_파트리스트.xlsx", "_가공도.dxf", "_도면집.pdf", "_도면집.dxf", "_도면집_2D.step"):
        assert (tmp_path / ("판_금형" + suf)).exists(), suf
    dlg.close()


def test_round_parts_real_shapes(plate):
    """둥근 표준품: 볼트 머리 육각 구멍 · 스프링·부시 속 빔 · 포스트 끝 모따기 — 솔리드가 성하고 부피가 맞음."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    _, _, a = plate

    def vol(s_):
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(s_, g)
        return g.Mass()
    bolt = next(p for p in a.parts if p.name.startswith("육각 구멍 붙이 볼트")).prims[0]
    assert bolt.socket is not None and bolt.stack
    s_ = die3d._solid(bolt)
    assert BRepCheck_Analyzer(s_).IsValid()
    assert vol(s_) == pytest.approx(die3d._volume(bolt), rel=0.03)
    sp = a.plate("다이 스프링").prims[0]
    assert sp.bore > 0
    full = math.pi * sp.p[3] ** 2 * sp.p[4]
    assert vol(die3d._solid(sp)) < 0.8 * full                  # 속이 빔
    post = a.plate("가이드 포스트").prims[0]
    assert len(post.stack) >= 2                                 # 몸통 + 끝 모따기
    assert a.plate("가이드 부시").prims[0].bore == pytest.approx(post.p[3], abs=0.6)


def test_clamp_slots_eye_taps_guide_checks(plate):
    """다이 세트 클램프 U 홈 (양 끝) · 옆면 아이볼트 탭 · 가이드 포스트 물림 점검."""
    _, _, a = plate
    for nm in ("하형 다이 세트", "상형 다이 세트"):
        shoe = a.plate(nm).prims[0]
        slots = [c for c in shoe.cuts if len(c) > 4 and c[4] == "slot"]
        assert len(slots) == 4
        assert any(h.axis != "z" for h in shoe.holes)
    assert any("아이볼트" in n for n in a.notes) and any("U 홈" in n or "클램프" in n for n in a.notes)
    rows = {r[0]: r for r in a.checks}
    g = [r for k, r in rows.items() if "가이드 포스트" in k]
    assert len(g) >= 2 and all(r[3] == "적합" for r in g)


def test_step_assembly_colors(plate, tmp_path):
    """STEP: DIE ASSEMBLY → LOWER DIE · UPPER DIE 조립 구조, 부품마다 색."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    _, _, a = plate
    p = die3d.save_step(a, str(tmp_path / "die.step"))
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    rd = STEPCAFControl_Reader()
    rd.SetNameMode(True)
    rd.SetColorMode(True)
    assert rd.ReadFile(p) == IFSelect_RetDone and rd.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    free = TDF_LabelSequence()
    st.GetFreeShapes(free)
    assert free.Length() == 1

    def nm(lab):
        n = TDataStd_Name()
        return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else ""
    root = free.Value(1)
    assert nm(root) == "DIE ASSEMBLY"
    comps = TDF_LabelSequence()
    st.GetComponents_s(root, comps, False)
    assert sorted(nm(comps.Value(i)) for i in range(1, comps.Length() + 1)) == ["LOWER DIE", "UPPER DIE"]
    cols = TDF_LabelSequence()
    ct.GetColors(cols)
    assert cols.Length() >= 4                                    # 재질·스프링별 색


def test_hlr_section_hatch(plate):
    """숨은선 지운 입체도 · 단면 고리 · 빗금."""
    from hanil_unfold import dieview
    _, _, a = plate
    dp = die3d._solid(a.plate("다이 플레이트").prims[0])
    vis, hid = dieview.hlr([dp], hidden=True)
    assert len(vis) > 20 and len(hid) > 0
    secs = dieview.section(dp, 0.0)
    assert secs
    pr = a.plate("다이 플레이트").prims[0]
    xs = np.vstack([o for o, _ in secs])
    assert xs[:, 1].min() == pytest.approx(pr.p[2], abs=0.01)
    assert xs[:, 1].max() == pytest.approx(pr.p[2] + pr.p[5], abs=0.01)
    sq = [np.array([[0, 0], [10, 0], [10, 10], [0, 10]], float)]
    hs = dieview.hatch(sq, 1.0)
    assert hs and all(-1e-9 <= c <= 10 + 1e-9 for p_, q_ in hs for c in (*p_, *q_))
    ring = sq + [np.array([[3, 3], [7, 3], [7, 7], [3, 7]], float)]
    mid = [(p_ + q_) / 2 for p_, q_ in dieview.hatch(ring, 0.5)]
    assert not any(3.2 < m[0] < 6.8 and 3.2 < m[1] < 6.8 for m in mid)   # 구멍 안은 빗금 없음


def test_3d_sheets(plate):
    """도면집에 입체 조립도·분해도 · 단면도 A-A (빗금), 조립도 평면도에 A-A 표시."""
    from hanil_unfold import diedraw
    _, _, a = plate
    sheets = diedraw.build(a, {"product": "판", "material": "SPCC t2"})
    titles = [s.title for s in sheets]
    assert titles[4:7] == ["금형 3면도 (평면 · 정면 · 우측면)", "입체 조립도 · 분해도", "단면도 A-A"]
    iso = sheets[5]
    assert sum(1 for e in iso.ents if e[0] == "circle") > len(a.parts)        # 풍선
    sec = sheets[6]
    assert sum(1 for e in sec.ents if e[0] == "line" and e[5] == "HATCH") > 100
    assert any(e[0] == "text" and e[3] == "A" for e in sheets[1].ents)


def test_three_view_sheets(plate):
    """3각법 3면도: 금형 (평면 · 정면 · 우측면, 숨은선) · 제품 3면도 (3D 가 있으면) · 부품도마다 우측면도."""
    from hanil_unfold import diedraw
    r, _, a = plate
    s, _ = models.spline_plate(t=2.0, hole_d=12.0)
    sheets = diedraw.build(a, {"product": "판", "material": "SPCC t2", "solid": s, "result": r})
    titles = [x.title for x in sheets]
    assert "제품 3면도 (평면 · 정면 · 우측면)" in titles
    ortho = sheets[titles.index("금형 3면도 (평면 · 정면 · 우측면)")]
    texts = [e[3] for e in ortho.ents if e[0] == "text"]
    for nm in ("평면도", "정면도", "우측면도"):
        assert nm in texts
    assert sum(1 for e in ortho.ents if e[0] == "poly" and e[3] == "HIDDEN") > 50      # 숨은선
    assert sum(1 for e in ortho.ents if e[0] == "poly" and e[3] == "OUTLINE") > 50
    assert f"{a.L:g}" in texts or any(t.startswith(f"{a.L:.0f}") for t in texts)         # 바깥 치수 (L)
    die = sheets[titles.index("다이 플레이트")]
    assert "우측면도" in [e[3] for e in die.ents if e[0] == "text"]
