"""실행 진입점.

  python -m hanil_unfold [부품.stp]
      → 화면 프로그램 (파일을 주면 바로 연다. exe 아이콘에 끌어다 놓은 경우)
  python -m hanil_unfold convert 부품.stp [-o 전개.dxf] [-k 0.44] [-t 2.0]
      → 화면 없이 DXF 만들기 (여러 파일도 가능)
  python -m hanil_unfold nest 부품.stp [더.stp] --sheet 1219x2438 [--qty 2] [-o 폴더]
      → 모든 부품을 전개해 철판에 배치 (두께별), 배치 DXF·PDF
  python -m hanil_unfold bom 조립품.stp [-o BOM.xlsx | BOM.pdf]
      → 같은 부품끼리 묶은 BOM
  python -m hanil_unfold ai-bom 조립품.stp [도면.pdf] [-o AI_BOM.xlsx]
      → 도면 PDF 와 3D 를 AI(Claude)로 맞춰 본 BOM (ANTHROPIC_API_KEY 필요)
"""
import argparse
import os
import sys
import traceback


def cli(argv):
    from . import bendcalc as bc
    from . import dxf_export, loader, report
    from .unfolder import MODE_NAMES, unfold

    from . import version_text
    ap = argparse.ArgumentParser(prog="HanilUnfold", description="판금 STEP → 전개 DXF")
    ap.add_argument("--version", action="version", version=f"한일 판금 전개 {version_text(long=True)}")
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
    ap.add_argument("--no-dims", action="store_true", help="DXF 에 치수(DIM 레이어) 빼기")
    ap.add_argument("--mode", choices=list(MODE_NAMES), default="auto",
                    help="auto=판금이면 정확·곡면이면 근사, sheet=판금, forming=성형품 근사")
    ap.add_argument("--no-history", action="store_true", help="전개 기록에 남기지 않기")
    ap.add_argument("--history-dir", help="전개 기록 폴더 (없으면 기본 위치)")
    ap.add_argument("--report", default="", help="보고서 형식: pdf, xlsx, pdf,xlsx  (여러 부품이면 parts_list.xlsx 도)")
    args = ap.parse_args(argv)

    settings = bc.BendSettings(
        method=args.method, k=args.k_factor, material=args.material, process=args.process,
        use_process_radius=args.punch_r is not None, punch_r=args.punch_r or 0.0,
        die_v=args.die_v, shop_table=bc.ShopTable.load(args.shop_table or bc.default_shop_table_path()))

    kinds = {k.strip() for k in args.report.split(",") if k.strip()}
    history = None
    if not args.no_history:
        from .history import History
        history = History(args.history_dir)
    log_dir = args.output if args.output and os.path.isdir(args.output) else os.getcwd()
    log_path = os.path.join(log_dir, "convert_errors.log")

    def log_error(where):
        # 화면 없는 exe 는 오류를 볼 곳이 없으므로 파일로 남긴다.
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{where}]\n{traceback.format_exc()}\n")

    items = []
    status = 0
    for path in args.files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            model = loader.load(path)
        except Exception as e:
            print(f"[실패] {path}\n{e}", file=sys.stderr)
            log_error(path)
            status = 1
            continue
        if "pdf" in kinds and len(model.solids) > 1:
            folder = args.output if args.output and os.path.isdir(args.output) \
                else os.path.dirname(os.path.abspath(path))
            try:
                report.save_assembly_pdf(model, os.path.join(folder, f"{name}_assembly.pdf"))
            except Exception:
                log_error(f"{path} 조립도")
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
                r = unfold(solid, thickness=args.thickness, settings=settings, mode=args.mode)
            except Exception as e:
                print(f"[실패] {path}{suffix}: {e}", file=sys.stderr)
                log_error(f"{path}{suffix}")
                status = 1
                continue
            dxf_export.save(r, out, part_name=name, notes=not args.no_notes,
                            dims=not args.no_dims, density=settings.mat.density)
            if history is not None:
                rid = history.record(path, r, settings, i, len(model.solids),
                                     part_name=model.names[i - 1])
                history.add_export(rid, out)
            if kinds:
                d = report.ReportData(name, path, r, settings, solid, i, len(model.solids),
                                      part_title=model.names[i - 1])
                base = os.path.splitext(out)[0].removesuffix("_flat")
                if "pdf" in kinds:
                    report.save_pdf(d, base + "_report.pdf")
                if "xlsx" in kinds:
                    report.save_xlsx(d, base + "_report.xlsx")
                items.append(d)
            w, h = r.size
            print(f"[완료] {out}  {w:.2f} x {h:.2f} mm, 두께 {r.thickness:.3f}, 절곡 {len(r.bends)}")
            for wmsg in r.warnings:
                print(f"       주의: {wmsg}")
    if len(items) > 1:
        folder = os.path.dirname(os.path.splitext(items[0].source_path)[0])
        if args.output and os.path.isdir(args.output):
            folder = args.output
        report.save_parts_list(items, os.path.join(folder, "parts_list.xlsx"))
    return status


def nest_cli(argv):
    from . import bendcalc as bc
    from . import loader, nesting, report
    from .unfolder import unfold

    ap = argparse.ArgumentParser(prog="HanilUnfold nest", description="STEP 부품을 전개해 철판에 배치")
    ap.add_argument("files", nargs="+", help="STEP 파일")
    ap.add_argument("--sheet", default="1219x2438", help="철판 크기 (예: 1219x2438, 1524*3048)")
    ap.add_argument("--gap", type=float, default=5.0, help="부품 간격 mm")
    ap.add_argument("--margin", type=float, default=10.0, help="가장자리 여유 mm")
    ap.add_argument("--rotate", choices=list(nesting.ROTATIONS), default="free",
                    help="free=90° 씩, 45=45° 씩, grain=180° 만, none=돌리지 않음")
    ap.add_argument("--qty", type=int, default=1, help="부품마다 수량")
    ap.add_argument("--tries", type=int, default=1, help="놓는 순서를 바꿔 해 볼 횟수 (1~3)")
    ap.add_argument("--material", choices=list(bc.MATERIAL_BY_CODE), default="SPCC")
    ap.add_argument("-o", "--output", help="저장할 폴더")
    args = ap.parse_args(argv)
    size = nesting.parse_size(args.sheet)
    if size is None:
        print(f"철판 크기를 읽지 못했습니다: {args.sheet}", file=sys.stderr)
        return 2
    settings = bc.BendSettings(method=bc.K_MATERIAL, material=args.material)
    parts = []
    status = 0
    for path in args.files:
        try:
            model = loader.load(path)
        except Exception as e:
            print(f"[실패] {path}\n{e}", file=sys.stderr)
            status = 1
            continue
        for i, solid in enumerate(model.solids):
            try:
                r = unfold(solid, settings=settings)
                parts.append(nesting.NestPart.from_result(model.names[i], r, args.qty, args.material,
                                                          len(parts) + 1))
            except Exception as e:
                print(f"[건너뜀] {path} {i + 1}: {str(e).splitlines()[0]}", file=sys.stderr)
    if not parts:
        return 1
    results = nesting.nest_by_thickness(parts, size[0], size[1], gap=args.gap, margin=args.margin,
                                        rotations=args.rotate, tries=args.tries)
    folder = args.output or os.path.dirname(os.path.abspath(args.files[0]))
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.files[0]))[0]
    base = os.path.join(folder, f"{stem}_nesting_{size[0]:g}x{size[1]:g}")
    nesting.save_dxf(results, base + ".dxf")
    report.save_nesting_pdf(results, base + ".pdf", os.path.basename(args.files[0]),
                            settings.mat.density)
    for r in results:
        print("\n".join(r.summary_lines(settings.mat.density)) + "\n")
    print(f"[완료] {base}.dxf, {base}.pdf")
    return status


def bom_cli(argv):
    from . import assembly_calc, bom, loader
    from . import bendcalc as bc
    ap = argparse.ArgumentParser(prog="HanilUnfold bom", description="조립품 STEP → BOM (엑셀·PDF)")
    ap.add_argument("file", help="STEP / IGES 조립품")
    ap.add_argument("--material", choices=list(bc.MATERIAL_BY_CODE), default="SPCC")
    ap.add_argument("-o", "--output", help="저장할 .xlsx 또는 .pdf (없으면 도면 옆 _BOM.xlsx)")
    args = ap.parse_args(argv)
    st = bc.BendSettings(method=bc.K_MATERIAL, material=args.material)
    model = loader.load(args.file)
    parts = assembly_calc.compute_all(model, st)
    items = bom.build(model, parts, st.mat.density, material=st.mat.code)
    rows = bom.build_tree(model, parts, st.mat.density, material=st.mat.code, items=items)
    out = args.output or os.path.splitext(args.file)[0] + "_BOM.xlsx"
    name = os.path.basename(args.file)
    if out.lower().endswith(".pdf"):
        bom.save_tree_pdf(rows, out, name, st.mat.code, st.mat.density)
    else:
        bom.save_tree_xlsx(rows, out, name, st.mat.code, st.mat.density)
    print(f"[완료] {out}  {len(items)} 품목, {sum(i.qty for i in items)} 개")
    return 0


def ai_bom_cli(argv):
    from . import ai_bom, assembly_calc, bom, loader
    from . import bendcalc as bc
    ap = argparse.ArgumentParser(prog="HanilUnfold ai-bom",
                                 description="2D 도면 PDF + 3D → AI(Claude) 분석 BOM 엑셀 (ANTHROPIC_API_KEY 필요)")
    ap.add_argument("model", help="3D STEP / IGES")
    ap.add_argument("pdf", nargs="?", default=None, help="2D 도면 PDF (없으면 3D 와 부품 그림만으로)")
    ap.add_argument("--no-images", action="store_true", help="도면이 없을 때 부품 그림을 보내지 않기")
    ap.add_argument("--material", choices=list(bc.MATERIAL_BY_CODE), default="SPCC")
    ap.add_argument("-o", "--output", help="저장할 .xlsx")
    args = ap.parse_args(argv)
    st = bc.BendSettings(method=bc.K_MATERIAL, material=args.material)
    model = loader.load(args.model)
    items = bom.build(model, assembly_calc.compute_all(model, st), st.mat.density, material=st.mat.code)
    if not args.pdf:
        from . import report
        report.ensure_gui()          # 부품 그림을 그리려면
    ai = ai_bom.analyze(args.pdf, items, images=not args.no_images,
                        source_name=os.path.basename(args.model), material=st.mat.code)
    out = args.output or os.path.splitext(args.model)[0] + "_AI_BOM.xlsx"
    rows, unmatched = ai_bom.save_xlsx(ai, items, out, os.path.basename(args.model),
                                       os.path.basename(args.pdf) if args.pdf else "", st.mat.code,
                                       st.mat.density)
    print(f"[완료] {out}  BOM {len(rows)} 줄, 3D 에만 {len(unmatched)} 품목")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V", "version"):
        from . import version_text
        text = f"한일 판금 전개 {version_text(long=True)}"
        if sys.stdout is not None:
            print(text)
        else:   # 화면 없는 exe: 현재 폴더에 적어 둔다
            with open("version.txt", "w", encoding="utf-8") as f:
                f.write(text + "\n")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "convert":
        sys.exit(cli(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "ai-bom":
        sys.exit(ai_bom_cli(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "bom":
        sys.exit(bom_cli(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "nest":
        sys.exit(nest_cli(sys.argv[2:]))
    from .app import main as gui
    gui()


if __name__ == "__main__":
    main()
