"""실행 진입점.

  python -m hanil_unfold [부품.stp]
      → 화면 프로그램 (파일을 주면 바로 연다. exe 아이콘에 끌어다 놓은 경우)
  python -m hanil_unfold convert 부품.stp [-o 전개.dxf] [-k 0.44] [-t 2.0]
      → 화면 없이 DXF 만들기 (여러 파일도 가능)
"""
import argparse
import os
import sys


def cli(argv):
    from . import bendcalc as bc
    from . import dxf_export, loader
    from .unfolder import unfold

    ap = argparse.ArgumentParser(prog="HanilUnfold", description="판금 STEP → 전개 DXF")
    ap.add_argument("files", nargs="+", help="STEP 파일")
    ap.add_argument("-o", "--output", help="저장할 DXF (파일 하나일 때) 또는 폴더")
    ap.add_argument("-k", "--k-factor", type=float, default=0.44, help="K 계수 (직접 입력 방식)")
    ap.add_argument("--method", choices=list(bc.METHOD_NAMES), default=bc.K_DIRECT,
                    help="direct=K 직접, material=재질별 K 표, din=DIN 6935")
    ap.add_argument("--material", choices=list(bc.MATERIAL_BY_CODE), default="SPCC")
    ap.add_argument("--process", choices=list(bc.PROCESS_NAMES), default=bc.AIR)
    ap.add_argument("--punch-r", type=float, help="상형 R. 주면 실제 R 로 다시 계산 (바깥 치수 유지)")
    ap.add_argument("--die-v", type=float, default=0.0, help="하형 V 폭 (없으면 8t)")
    ap.add_argument("--shop-table", help="회사 연신 표 JSON (없으면 기본 위치)")
    ap.add_argument("-t", "--thickness", type=float, help="두께 (없으면 자동 측정)")
    ap.add_argument("--no-notes", action="store_true", help="절곡 글씨 빼기")
    args = ap.parse_args(argv)

    settings = bc.BendSettings(
        method=args.method, k=args.k_factor, material=args.material, process=args.process,
        use_process_radius=args.punch_r is not None, punch_r=args.punch_r or 0.0,
        die_v=args.die_v, shop_table=bc.ShopTable.load(args.shop_table or bc.default_shop_table_path()))

    status = 0
    for path in args.files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            model = loader.load(path)
        except Exception as e:
            print(f"[실패] {path}\n{e}", file=sys.stderr)
            status = 1
            continue
        for i, solid in enumerate(model.solids, 1):
            suffix = f"_{i}" if len(model.solids) > 1 else ""
            if args.output and len(args.files) == 1 and len(model.solids) == 1 \
                    and not os.path.isdir(args.output):
                out = args.output
            else:
                folder = args.output if args.output and os.path.isdir(args.output) \
                    else os.path.dirname(os.path.abspath(path))
                out = os.path.join(folder, f"{name}{suffix}_flat.dxf")
            try:
                r = unfold(solid, thickness=args.thickness, settings=settings)
            except Exception as e:
                print(f"[실패] {path}{suffix}: {e}", file=sys.stderr)
                status = 1
                continue
            dxf_export.save(r, out, part_name=name, notes=not args.no_notes)
            w, h = r.size
            print(f"[완료] {out}  {w:.2f} x {h:.2f} mm, 두께 {r.thickness:.3f}, 절곡 {len(r.bends)}")
            for wmsg in r.warnings:
                print(f"       주의: {wmsg}")
    return status


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "convert":
        sys.exit(cli(sys.argv[2:]))
    from .app import main as gui
    gui()


if __name__ == "__main__":
    main()
