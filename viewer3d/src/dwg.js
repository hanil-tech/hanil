//  📐 DWG · DXF 읽기 — LibreDWG(WASM) 로 읽어 SVG 로 바꾼다(글자는 브라우저 글꼴로 — 한글도 그대로)
//   ⚠ 엔진이 커서(약 9.5MB) **DWG 를 열 때만** 불러온다. 3D(STEP) 만 보는 사람은 안 받는다.
//   ⚠ DWG 는 AutoCAD 전용 형식이라 아주 새 판·특수 객체는 일부 안 보일 수 있다(그때 알려 준다).
import { LibreDwg, Dwg_File_Type, createModule } from '@mlightcad/libredwg-web';

let libP = null;
function lib() {
  if (libP) return libP;
  const opt = {};
  if (window.DWG_WASM_B64) {                 //  PC 단독판 — 엔진을 글자로 품고 있다
    const bin = atob(window.DWG_WASM_B64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    opt.wasmBinary = u8;
    window.DWG_WASM_B64 = null;
  } else {
    const base = (window.HANIL_DWG_BASE || '');
    opt.locateFile = (f) => base + f;        //  포털·앱 — 같은 자리의 libredwg-web.wasm
  }
  libP = createModule(opt).then((m) => LibreDwg.createByWasmInstance(m));
  return libP;
}

window.HanilDwg = {
  async toSvg(u8, kind) {
    const L = await lib();
    const buf = u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength);
    const dwg = L.dwg_read_data(buf, kind === 'dxf' ? Dwg_File_Type.DXF : Dwg_File_Type.DWG);
    if (!dwg) throw new Error('도면을 읽지 못했습니다(판이 너무 새것이거나 깨진 파일)');
    let db;
    try { db = L.convert(dwg); } finally { try { L.dwg_free(dwg); } catch (e) { /* */ } }
    const svg = L.dwg_to_svg(db);
    const ents = (db && db.entities && db.entities.length) || 0;
    const layers = (db && db.tables && db.tables.LAYER && db.tables.LAYER.entries) ? db.tables.LAYER.entries.map((l) => l.name) : [];
    return { svg, ents, layers };
  },
};
