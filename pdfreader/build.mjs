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
    + '<script>window.PDF_CMAPS=' + JSON.stringify(cmaps) + ';window.PDF_FONTS=' + JSON.stringify(fonts) + ';</script>')
  .replace('<!--APP-->', () => '<script>' + safe(app) + '</script>');
const file = path.join(out, 'hanil-pdf-reader.html');
fs.writeFileSync(file, html);
console.log('PDF 리더 v' + ver + '  ' + file + '  ' + Math.round(fs.statSync(file).size / 1024) + 'KB (화면 ' + Math.round(app.length / 1024) + 'KB)');
