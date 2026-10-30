//  📕 PDF 리더 — 만들기
//   node build.mjs  →  out/hanil-pdf-reader.html  PC 단독 한 장(엔진·일꾼·글꼴 표를 모두 품음 — 인터넷·서버 없이 열린다)
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, 'out');
const dist = path.join(here, 'node_modules', 'pdfjs-dist');
const ver = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8')).version;
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const r = await build({
  entryPoints: [path.join(here, 'src', 'app.js')],
  bundle: true, minify: !process.env.DEV, format: 'iife', target: ['chrome92', 'edge92', 'firefox115', 'safari15'],
  write: false, legalComments: 'none',
  define: { 'import.meta.url': 'location.href' },   //  ⚠ 엔진 안의 node 전용 갈래에서만 쓴다
  logLevel: 'error',
});
const app = r.outputFiles[0].text;
//  ⚠ 일꾼은 보통 스크립트(iife)로 — file:// 에서는 모듈 일꾼(type:module)을 blob 으로 못 띄운다(크롬: 출처 없음)
const rw = await build({
  entryPoints: [path.join(dist, 'legacy', 'build', 'pdf.worker.mjs')],
  bundle: true, minify: true, format: 'iife', target: ['chrome92', 'edge92', 'firefox115', 'safari15'],
  write: false, legalComments: 'none', logLevel: 'error',
});
const workerJs = rw.outputFiles[0].text;

//  양식 채우기 칸(pdf.js 의 annotationLayer 모양) — pdf_viewer.css 에서 필요한 규칙만
const pvCss = fs.readFileSync(path.join(dist, 'web', 'pdf_viewer.css'), 'utf8');
const formCss = (() => {
  const out = []; let depth = 0, start = 0;
  for (let i = 0; i < pvCss.length; i++) {
    if (pvCss[i] === '{') depth++;
    else if (pvCss[i] === '}' && --depth === 0) { const b = pvCss.slice(start, i + 1); const sel = b.split('{')[0]; if (sel.includes('annotationLayer') || sel.trim().startsWith(':root')) out.push(b.trim()); start = i + 1; }
  }
  return out.join('\n');
})();
//  한글 글꼴(나눔고딕, OFL) — 글자 고치기·양식 칸을 PDF 에 「진짜 글자」로 넣을 때(쓰는 글자만 골라 넣음)
//  ⚠ 이 TTF 에는 글꼴 제작 도구(VTT)가 남긴 빈 표 TSI0~TSI5 가 있어 브라우저(OTS)가 거부한다 → 그 표들만 빼고 다시 묶는다
const stripTables = (buf, drop) => {
  const n = buf.readUInt16BE(4), recs = [];
  for (let k = 0; k < n; k++) { const o = 12 + k * 16; recs.push({ tag: buf.toString('latin1', o, o + 4), sum: buf.readUInt32BE(o + 4), off: buf.readUInt32BE(o + 8), len: buf.readUInt32BE(o + 12) }); }
  const keep = recs.filter((r) => !drop.test(r.tag));
  const head = Buffer.alloc(12 + keep.length * 16);
  buf.copy(head, 0, 0, 4);
  head.writeUInt16BE(keep.length, 4);
  let es = 0; while ((1 << (es + 1)) <= keep.length) es++;
  head.writeUInt16BE((1 << es) * 16, 6); head.writeUInt16BE(es, 8); head.writeUInt16BE(keep.length * 16 - (1 << es) * 16, 10);
  const bodies = []; let off = head.length;
  keep.forEach((r, k) => {
    const o = 12 + k * 16, data = buf.subarray(r.off, r.off + r.len), pad = (4 - (r.len % 4)) % 4;
    head.write(r.tag, o, 'latin1'); head.writeUInt32BE(r.sum, o + 4); head.writeUInt32BE(off, o + 8); head.writeUInt32BE(r.len, o + 12);
    bodies.push(data, Buffer.alloc(pad)); off += r.len + pad;
  });
  return Buffer.concat([head, ...bodies]);
};
const nanum = stripTables(fs.readFileSync(path.join(here, 'node_modules', '@kfonts', 'nanum-gothic', 'src', 'NanumGothic.ttf')), /^TSI/);

//  글꼴 표(CMap) — 한글·한자 PDF 가운데 글꼴을 품지 않은 것을 읽는 데 필요(KSC·UniKS·Adobe-Korea1 …) · 기본 글꼴 14가지
const pack = (dir, filter) => {
  const o = {};
  for (const f of fs.readdirSync(dir).sort()) if (filter(f)) o[f.replace(/\.bcmap$/, '')] = fs.readFileSync(path.join(dir, f)).toString('base64');
  return o;
};
const cmaps = pack(path.join(dist, 'cmaps'), (f) => f.endsWith('.bcmap'));
const fonts = pack(path.join(dist, 'standard_fonts'), (f) => /\.(pfb|ttf)$/.test(f));

//  ⚠ </script> 가 글 안에 있으면 HTML 이 거기서 끊긴다 → 쪼개 둔다 · replace 에는 함수로 넘긴다($& 등)
const safe = (s) => s.replace(/<\/script/gi, '<\\/script');
const html = fs.readFileSync(path.join(here, 'src', 'index.html'), 'utf8')
  .replace('<title>', () => '<meta name="hanil-pdf" content="v' + ver + '"><title>')
  .replace('<!--ENGINE-->', () => '<script id="pdfworker" type="text/plain">' + safe(workerJs) + '</script>\n'
    + '<style>' + formCss + '</style>'
    + '<script id="hanilfont" type="text/plain">' + nanum.toString('base64') + '</script>'
    + '<script>window.HANIL_ICON="data:image/png;base64,' + fs.readFileSync(path.join(here, 'assets', 'icon-128.png')).toString('base64') + '";</script>'
    + '<script>window.PDF_CMAPS=' + JSON.stringify(cmaps) + ';window.PDF_FONTS=' + JSON.stringify(fonts) + ';</script>')
  .replace('<!--APP-->', () => '<script>' + safe(app) + '</script>');
const file = path.join(out, 'hanil-pdf-reader.html');
fs.writeFileSync(file, html);
//  ③ 크롬 확장(MV3) — ⚠ 확장 화면은 HTML 안 스크립트를 막는다 → 파일로 나눈다
const ext = path.join(out, 'chrome');
fs.mkdirSync(path.join(ext, 'icons'), { recursive: true });
fs.writeFileSync(path.join(ext, 'app.js'), app);
fs.writeFileSync(path.join(ext, 'pdf.worker.js'), workerJs);
fs.writeFileSync(path.join(ext, 'font.js'), 'window.HANIL_FONT_B64="' + nanum.toString('base64') + '";');
fs.writeFileSync(path.join(ext, 'data.js'), 'window.HANIL_ICON="icons/128.png";window.HANIL_EXT=true;window.PDF_WORKER_URL="pdf.worker.js";window.PDF_CMAPS=' + JSON.stringify(cmaps) + ';window.PDF_FONTS=' + JSON.stringify(fonts) + ';');
fs.writeFileSync(path.join(ext, 'viewer.html'), fs.readFileSync(path.join(here, 'src', 'index.html'), 'utf8')
  .replace('<title>', () => '<meta name="hanil-pdf" content="v' + ver + '"><title>')
  .replace('<!--ENGINE-->', () => '<style>' + formCss + '</style><script src="data.js"></script><script src="font.js"></script>')
  .replace('<!--APP-->', () => '<script src="app.js"></script>'));
fs.copyFileSync(path.join(here, 'src', 'chrome', 'background.js'), path.join(ext, 'background.js'));
for (const n of [16, 32, 48, 128]) fs.copyFileSync(path.join(here, 'assets', 'icon-' + n + '.png'), path.join(ext, 'icons', n + '.png'));
const icons = { 16: 'icons/16.png', 32: 'icons/32.png', 48: 'icons/48.png', 128: 'icons/128.png' };
fs.writeFileSync(path.join(ext, 'manifest.json'), JSON.stringify({
  manifest_version: 3, name: '한일 PDF 리더', version: ver, author: '한일특장(주)',
  description: '크롬에서 PDF 를 한일 PDF 리더로 — 보기·폴더 검색·주석 고치기·페이지 구성. 제작: 한일특장(주)',
  icons, action: { default_title: '한일 PDF 리더 열기', default_icon: icons },
  background: { service_worker: 'background.js' },
  permissions: ['declarativeNetRequest', 'contextMenus', 'tabs'],
  host_permissions: ['<all_urls>'],
  web_accessible_resources: [{ resources: ['viewer.html'], matches: ['<all_urls>'] }],
  content_security_policy: { extension_pages: "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'" },
}, null, 2));

console.log('PDF 리더 v' + ver + '  ' + file + '  ' + Math.round(fs.statSync(file).size / 1024) + 'KB (화면 ' + Math.round(app.length / 1024) + 'KB)');
