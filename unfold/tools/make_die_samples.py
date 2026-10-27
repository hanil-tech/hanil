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
from hanil_unfold import die3d, diedraw, loader, process  # noqa: E402
from hanil_unfold.unfolder import unfold  # noqa: E402

OUT = os.path.join(ROOT, "samples", "dies")


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
        sheets = diedraw.build(a, {"product": name.replace("die_", ""), "material": f"{mat} t{r.thickness:g}"})
        diedraw.save_pdf(sheets, os.path.join(OUT, name + "_도면집.pdf"))
        bad = [c[0] for c in a.checks if c[3] != "적합"]
        print(f"{name}: {a.kind} {a.L:.0f}×{a.W:.0f} 닫힌 높이 {a.shut:.1f} 부품 {len(a.parts)} 종 "
              f"{os.path.getsize(path) / 1e6:.1f} MB 검토 {bad}")


if __name__ == "__main__":
    main()
