"""금형 3D 예제 STEP · 도면집 PDF 만들기: samples/ 의 부품 · 시험 모델을 전개해 die3d 로 금형을 짜고 samples/dies/ 에 저장.

    python tools/make_die_samples.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import models  # noqa: E402

from hanil_unfold import bendcalc as bc  # noqa: E402
from hanil_unfold import die3d, diedraw, loader, process, tandem  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402

OUT = os.path.join(ROOT, "samples", "dies")
OUT_T = os.path.join(ROOT, "samples", "tandem")


def cases():
    s, _ = models.spline_plate(t=2.0, hole_d=12.0)
    yield "die_spline_plate_t2_2stage", s, "SPCC", False
    m = loader.load(os.path.join(ROOT, "samples", "bracket_t2.step"), use_cache=False)
    yield "die_bracket_t2_2stage", m.solids[0], "SPCC", False
    yield "die_bracket_t2_progressive", m.solids[0], "SPCC", True
    s = models.profile_part([("L", 60), ("B", 90, 2.0), ("L", 40)], 1.6, 80)
    yield "die_angle_t1.6_blank", s, "SPCC", False
    s, _ = models.spline_plate(t=1.2, hole_d=8.0)
    yield "die_spline_plate_t1.2_SPFC590", s, "SPFC590", False


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, shape, mat, prog in cases():
        st = bc.BendSettings(material=mat)
        r = unfold(shape, settings=st)
        plan = process.progressive(r, st) if prog else None
        a = die3d.build(r, st, plan=plan)
        path = die3d.save_step(a, os.path.join(OUT, name + ".step"))
        sheets = diedraw.build(a, {"product": name.replace("die_", ""), "material": f"{mat} t{r.thickness:g}",
                                   "solid": shape, "result": r})
        diedraw.save_pdf(sheets, os.path.join(OUT, name + "_도면집.pdf"))
        bad = [c[0] for c in a.checks if c[3] != "적합"]
        print(f"{name}: {a.kind} {a.L:.0f}×{a.W:.0f} 닫힌 높이 {a.shut:.1f} 부품 {len(a.parts)} 종 "
              f"{os.path.getsize(path) / 1e6:.1f} MB 검토 {bad}")


def tandem_samples():
    """공정별 금형 1차 ~ 5차 예제 (구멍 있는 ㄷ 채널): 공정마다 STEP + 공정표 · 도면집 PDF."""
    os.makedirs(OUT_T, exist_ok=True)
    s = models.channel_holes()
    st = bc.BendSettings(material="SPCC")
    r = unfold(s, settings=st)
    F = tandem.Folder(r)
    ops = tandem.design(r, st, folder=F)
    out, notes = tandem.save_all(r, st, ops, os.path.join(OUT_T, "channel_t2"),
                                 {"product": "ㄷ 채널 (구멍 4)", "material": "SPCC t2", "solid": s, "result": r}, folder=F)
    for p in out:
        if p.endswith((".dxf", ".dwg", ".xlsx")):
            os.remove(p)                                  # 예제는 STEP · PDF 만 (저장소 크기)
    for op in ops:
        print(op.label, op.error or f"{op.die.L:.0f}×{op.die.W:.0f} 닫힌 {op.die.shut:.1f}")
    return ops, F, s, r


def cast_samples():
    """주물 드로잉 금형 예제 (오일 팬): STEP + 도면집 PDF + 부품표."""
    from hanil_unfold import castdie, dieface
    out_dir = os.path.join(ROOT, "samples", "castdie")
    os.makedirs(out_dir, exist_ok=True)
    s = models.oil_pan()
    st = bc.BendSettings(material="SPCC")
    r = unfold(s, settings=st, mode="forming")
    df = dieface.build(r.forming.V, r.forming.F, r.thickness)
    a = castdie.design(df, r, st)
    out = castdie.save_all(a, os.path.join(out_dir, "oil_pan_t1_드로우금형"),
                           {"product": "오일 팬 320×220×110", "material": "SPCC t1", "solid": s, "result": r})
    for p in out:
        if p.endswith((".dxf", ".dwg")):
            os.remove(p)
    print("castdie", a.L, a.W, a.shut, len(a.parts))
    return a


if __name__ == "__main__":
    main()
    tandem_samples()
    cast_samples()
