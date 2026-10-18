//  🧊 3D 도면 보기 — 만들기
//   node build.mjs  →  out/portal/viewer3d/   포털에 올릴 폴더(index.html · viewer.js · occt-import-js.js · occt-import-js.wasm)
//                      out/hanil-3d-viewer.html  PC 단독 한 장(엔진을 글자로 품음 — 인터넷·서버 없이 열린다)
//                      ../android/app/src/main/assets/viewer3d/  폰 앱 안(포털용 폴더와 같은 것)
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, 'out');
const portal = path.join(out, 'portal', 'viewer3d');
const app = path.join(here, '..', 'android', 'app', 'src', 'main', 'assets', 'viewer3d');
const occtDir = path.join(here, 'node_modules', 'occt-import-js', 'dist');
const ver = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8')).version;

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(portal, { recursive: true });

const r = await build({
  entryPoints: [path.join(here, 'src', 'main.js')],
  bundle: true, minify: true, format: 'iife', target: ['chrome90', 'safari14'],
  write: false, legalComments: 'none',
});
const js = r.outputFiles[0].text;

//  📐 2D(DWG·DXF) 엔진 — 따로 묶는다(DWG 를 열 때만 받는다)
//   ⚠ LibreDWG 의 SVG 변환기는 요소 하나(표 TABLE 등)에서 터지면 **도면 전체**를 못 그린다 →
//     묶으면서 요소마다 감싸, 못 그리는 것만 건너뛰고 센다(window.__dwgSkip).
const patchDwg = {
  name: 'patch-libredwg-svg',
  setup(b) {
    b.onLoad({ filter: /libredwg-web[\\/]dist[\\/]libredwg-web\.js$/ }, async (a) => {
      let src = fs.readFileSync(a.path, 'utf8');
      const hook = '  entityToBoundsAndElement(entity) {\n';
      if (!src.includes(hook)) throw new Error('LibreDWG SVG 변환기 모양이 바뀌었습니다 — build.mjs 의 손질을 고치세요');
      src = src.replace(hook, () => '  entityToBoundsAndElement(entity) {\n    try { return this.__e2b(entity); } catch (e) { globalThis.__dwgSkip = (globalThis.__dwgSkip || 0) + 1; return null; }\n  }\n  __e2b(entity) {\n');
      return { contents: src, loader: 'js' };
    });
  },
};
const rd = await build({
  entryPoints: [path.join(here, 'src', 'dwg.js')],
  bundle: true, minify: true, format: 'iife', target: ['chrome90', 'safari14'],
  write: false, legalComments: 'none', plugins: [patchDwg],
  define: { 'import.meta.url': 'location.href' },
  external: ['module'],            //  ⚠ 엔진 안의 node 전용 갈래(import("module")) — 브라우저에서는 안 탄다
  logLevel: 'error',
});
const dwgJs = rd.outputFiles[0].text;
const dwgWasm = fs.readFileSync(path.join(here, 'node_modules', '@mlightcad', 'libredwg-web', 'wasm', 'libredwg-web.wasm'));
const occtJs = fs.readFileSync(path.join(occtDir, 'occt-import-js.js'), 'utf8');
const wasm = fs.readFileSync(path.join(occtDir, 'occt-import-js.wasm'));
const html = fs.readFileSync(path.join(here, 'src', 'index.html'), 'utf8').replace('<title>', '<meta name="hanil-viewer3d" content="' + ver + '"><title>');

//  ① 포털·앱용 — 파일을 나눠 둔다(엔진 7MB 는 브라우저가 한 번 받아 두고 다시 쓴다)
fs.writeFileSync(path.join(portal, 'viewer.js'), js);
fs.writeFileSync(path.join(portal, 'occt-import-js.js'), occtJs);
fs.writeFileSync(path.join(portal, 'occt-import-js.wasm'), wasm);
fs.writeFileSync(path.join(portal, 'index.html'), html
  .replace('<!--OCCT-->', () => '<script src="occt-import-js.js"></script>')
  .replace('<!--VIEWER-->', () => '<script src="viewer.js?v=' + ver + '"></script>'));
for (const f of ['license.occt-import-js.txt', 'license.occt.txt']) fs.copyFileSync(path.join(occtDir, f), path.join(portal, f));
fs.writeFileSync(path.join(portal, 'dwg.js'), dwgJs);
fs.writeFileSync(path.join(portal, 'libredwg-web.wasm'), dwgWasm);
fs.writeFileSync(path.join(portal, 'license.libredwg.txt'), 'DWG·DXF 읽기: LibreDWG (GPL-3.0) · @mlightcad/libredwg-web (GPL-3.0)\nhttps://www.gnu.org/software/libredwg/ · https://github.com/mlightcad/libredwg-web\n');

//  ② PC 단독 한 장 — ⚠ </script> 가 글 안에 있으면 HTML 이 거기서 끊긴다 → 쪼개 둔다
//     ⚠ replace 에 글을 그대로 주면 $' $& 같은 글자를 특수 기호로 먹는다(three.js 안에 있다) → 함수로 넘긴다
const safe = (s) => s.replace(/<\/script/gi, '<\\/script');
fs.writeFileSync(path.join(out, 'hanil-3d-viewer.html'), html
  .replace('<!--OCCT-->', () => '<script>' + safe(occtJs) + '</script>\n<script>window.OCCT_WASM_B64="' + wasm.toString('base64') + '";</script>')
  .replace('<!--VIEWER-->', () => '<script>window.DWG_WASM_B64="' + dwgWasm.toString('base64') + '";</script>\n<script>' + safe(dwgJs) + '</script>\n<script>' + safe(js) + '</script>'));

//  ③ 폰 앱 안 — 포털용 폴더와 같다
fs.rmSync(app, { recursive: true, force: true });
fs.cpSync(portal, app, { recursive: true });

const kb = (p) => Math.round(fs.statSync(p).size / 1024) + 'KB';
console.log('viewer3d v' + ver);
console.log('  포털용  ' + portal + '  (viewer.js ' + kb(path.join(portal, 'viewer.js')) + ' · 3D 엔진 ' + kb(path.join(portal, 'occt-import-js.wasm')) + ' · 2D 엔진 ' + kb(path.join(portal, 'libredwg-web.wasm')) + ')');
console.log('  단독판  ' + path.join(out, 'hanil-3d-viewer.html') + '  ' + kb(path.join(out, 'hanil-3d-viewer.html')));
console.log('  앱 안   ' + app);
