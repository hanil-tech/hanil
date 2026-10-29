"""체결품 (볼트 · 너트 · 와셔) 자동 판별과 기본 제외, 뒤 스레드 파일 열기."""
import math

import pytest

import models
from hanil_unfold import assembly_calc, bendcalc as bc, hardware, loader


def _bolt(m=8.0, L=30.0):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    head = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), m * 0.8, 0.6 * m).Shape()
    shank = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -L), gp_Dir(0, 0, 1)), m / 2, L).Shape()
    return loader.list_solids(BRepAlgoAPI_Fuse(head, shank).Shape())[0]


@pytest.mark.parametrize("name, kind", [
    ("HEX BOLT M8X30 #11", "볼트·나사"), ("ISO 4762 M8 x 20", "볼트·나사"), ("socket head cap screw_am", "볼트·나사"),
    ("M8X20", "볼트·나사"), ("육각볼트 M10", "볼트·나사"), ("DIN 933 M8", "볼트·나사"), ("KS B 1002 M12", "볼트·나사"),
    ("hex nut gradeab_am", "너트"), ("NUT M8", "너트"), ("육각너트 M8", "너트"), ("ISO 4032 M10", "너트"),
    ("PLAIN WASHER M8", "와셔"), ("평와셔 8", "와셔"), ("DIN 125 A8.4", "와셔"), ("POP RIVET 4x8", "리벳"), ("리벳 Ø4", "리벳"),
    ("DOWEL PIN 6x20", "핀·링"), ("BEARING 6204", "부시·베어링"),
    # 판금 · 가공품: 체결품 말이 섞여도 아님
    ("SIDE PANEL", None), ("PIN BRACKET", None), ("핀 홀더 브래킷", None), ("BOLT HOLDER PLATE", None), ("부품 3", None),
    ("FLOOR PLATE", None), ("W1", None), ("", None),
])
def test_hardware_by_name(name, kind):
    assert hardware.by_name(name) == kind


def test_hardware_by_shape():
    """볼트 (작고 뭉툭한 회전체) 는 모양으로 잡고, 트레이 · 평판 · 작은 드로잉 컵 (얇은 판) 은 아님."""
    assert hardware.by_shape(_bolt()) == "환봉·체결품 (모양)"
    assert hardware.by_shape(_bolt(16.0, 120.0)) is None                       # 가장 긴 변 > 80
    assert hardware.by_shape(loader.list_solids(models.tray(40, 30, 10, 1.0))[0]) is None
    assert hardware.by_shape(loader.list_solids(models.drawn_cup(10, 15, 2, 1))[0]) is None
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    assert hardware.by_shape(BRepPrimAPI_MakeBox(50.0, 30.0, 1.6).Shape()) is None   # 평판 (얇음)
    assert hardware.classify("", _bolt()) == "환봉·체결품 (모양)" and hardware.classify("BOLT M8", None) == "볼트·나사"


def test_loader_marks_hardware_and_compute_all_skips(tmp_path):
    """조립 STEP: NUT M8 (이름) 과 BOSS (작은 환봉, 모양) 가 체결품 · 환봉으로 — compute_all 의 skip 은 전개하지 않고 '제외'."""
    path = models.nested_assembly_step(str(tmp_path / "nested.stp"))
    m = loader.load(path, use_cache=False)
    hw = m.hardware
    nuts = [i for i, n in enumerate(m.names) if n.startswith("NUT M8")]
    assert nuts and all(hw.get(i) == "너트" for i in nuts)
    assert all(hw.get(i) is None for i, n in enumerate(m.names) if n.startswith(("SIDE PANEL", "BRACKET", "FLOOR")))
    parts = assembly_calc.compute_all(m, bc.BendSettings(material="SPCC"), skip=set(hw))
    assert len(parts) == len(m.solids)
    for i in nuts:
        assert not parts[i].ok and parts[i].error.startswith("제외 (너트)")
    assert any(p.ok for p in parts)
    # 부품 하나짜리 파일은 보지 않음
    one = loader.load("samples/tray_t1.6.step", use_cache=False)
    assert one.hardware == {}


def test_app_opens_in_background_and_excludes_hardware(tmp_path):
    """창에서 열기: 뒤 스레드로 읽고, 체결품은 [제외: 너트] 로 표시되며 첫 부품은 체결품이 아닌 것."""
    from hanil_unfold.app import MainWindow
    path = models.nested_assembly_step(str(tmp_path / "nested2.stp"))
    w = MainWindow()
    w.settings.setValue("auto_exclude_hardware", "1")
    w.open_file(path)
    try:
        assert w.model is not None and w.model.path == path
        hw = w.model.hardware
        assert hw and w.excluded == set(hw)
        assert w.solid_box.currentIndex() not in w.excluded
        texts = [w.part_list.item(i).text() for i in range(w.part_list.count())]
        assert any(t.endswith("[제외: 너트]") for t in texts)
        w._toggle_auto_hardware(False)
        assert not w.excluded and not any("[제외" in w.part_list.item(i).text() for i in range(w.part_list.count()))
        w._toggle_auto_hardware(True)
        assert w.excluded == set(hw)
    finally:
        w.close()


def test_app_unfolds_forming_part_in_background(tmp_path):
    """부품 고르기: 성형품 (휀다) 전개를 뒤 스레드에서 돌려도 결과는 같은 자리에 (result · 3D 화면), 진행 창은 닫힘."""
    from hanil_unfold.app import MainWindow
    path = loader.save_step(loader.list_solids(models.dish())[0], str(tmp_path / "dish.step"), "dish")
    w = MainWindow()
    w.open_file(path)
    try:
        assert w.model is not None and w.result is not None and w.result.mode == "forming"
        assert not any(x.isVisible() for x in w.findChildren(__import__("PySide6.QtWidgets").QtWidgets.QProgressDialog))
    finally:
        w.close()
