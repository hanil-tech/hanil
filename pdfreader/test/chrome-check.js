//  크롬 확장 시험 — node test/chrome-check.js <시험 PDF 폴더> [그림 폴더]
//   확장을 넣은 크로미움 → 작은 웹 서버의 PDF(.pdf 주소 · 주소에 .pdf 없이 Content-Type 만) → 이 리더로 열리나
const { chromium } = require('playwright');
const http = require('http');
const path = require('path');
const fs = require('fs');
const os = require('os');
const dir = path.resolve(process.argv[2]);
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null;
const ext = path.join(__dirname, '..', 'out', 'chrome');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };

(async () => {
  const pdf = fs.readFileSync(path.join(dir, 'A-001 섀시 부품표.pdf'));
  const srv = http.createServer((q, r) => {
    if (q.url.startsWith('/doc/a.pdf') || q.url.startsWith('/download')) { r.writeHead(200, { 'Content-Type': 'application/pdf' }); r.end(pdf); }
    else { r.writeHead(404); r.end(); }
  }).listen(0);
  const port = srv.address().port;
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'hpdf-'));
  const ctx = await chromium.launchPersistentContext(prof, { channel: 'chromium', headless: true, args: ['--disable-extensions-except=' + ext, '--load-extension=' + ext] });
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent('serviceworker');
  ok(/chrome-extension:\/\//.test(sw.url()), '확장이 들어감: ' + sw.url().split('/')[2]);
  await new Promise((r) => setTimeout(r, 800));
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  await page.goto('http://127.0.0.1:' + port + '/doc/a.pdf?x=1&y=2').catch(() => {});
  await page.waitForURL(/viewer\.html/, { timeout: 15000 }).catch(() => {});
  ok(/^chrome-extension:\/\/.*viewer\.html\?src=/.test(page.url()), '.pdf 주소 → 리더로 바뀜');
  await page.waitForFunction(() => window.__pdfReader && window.__pdfReader.cur && window.__pdfReader.cur.n === 3, null, { timeout: 20000 }).catch(() => {});
  ok(await page.evaluate(() => window.__pdfReader && window.__pdfReader.cur && window.__pdfReader.cur.name), '리더에 문서가 열림: ' + await page.evaluate(() => window.__pdfReader && window.__pdfReader.cur && window.__pdfReader.cur.name));
  await page.waitForSelector('.pg[data-i="0"] .textLayer span', { timeout: 15000 }).catch(() => {});
  const t = await page.$$eval('.pg[data-i="0"] .textLayer span', (s) => s.map((x) => x.textContent).join('')).catch(() => '');
  ok(t.includes('부품 목록'), '한글 글자(확장 안에서 글꼴 표·일꾼) : ' + t.slice(0, 20));
  if (shots) await page.screenshot({ path: path.join(shots, '6-크롬확장.png') });
  //  주소에 .pdf 가 없는 내려받기(서버가 application/pdf 로만 알려 줌)
  const p2 = await ctx.newPage();
  await p2.goto('http://127.0.0.1:' + port + '/download?id=7').catch(() => {});
  await p2.waitForURL(/viewer\.html/, { timeout: 8000 }).catch(() => {});
  ok(/viewer\.html/.test(p2.url()), 'Content-Type 만 PDF 인 주소도 리더로 (크롬 128+) — ' + p2.url().slice(0, 60));
  //  hanilraw=1 은 크롬 기본 뷰어
  const p3 = await ctx.newPage();
  await p3.goto('http://127.0.0.1:' + port + '/doc/a.pdf?hanilraw=1').catch(() => {});
  await p3.waitForTimeout(800);
  ok(!/viewer\.html/.test(p3.url()), '?hanilraw=1 → 그대로(크롬 기본)');
  ok(errs.length === 0, '화면 오류 없음 ' + errs.join(' / '));
  await ctx.close(); srv.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
