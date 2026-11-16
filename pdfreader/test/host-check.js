//  윈도우 프로그램과 같은 모양으로 띄워 본다 — node test/host-check.js <시험 PDF 폴더>
//   (main.go 처럼 <head> 바로 뒤에 host.js 를 넣고, /file 로 파일을 내주고, 프로그램 함수(host…)는 흉내)
//   확인: HANIL_HOST 가 살아 있나 · 두 번 눌러 넘어온 파일(hostPending)이 열리나 · 업데이트 확인이 프로그램 쪽으로 가나
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const dir = path.resolve(process.argv[2]);
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
(async () => {
  const TOKEN = 'T'.repeat(32);
  const html = fs.readFileSync(path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, '..', 'win', 'app', 'host.js'), 'utf8').replace(/__TOKEN__/g, TOKEN);
  const page0 = html.replace('<head>', '<head><script>' + js + '</script>');
  const srv = http.createServer((q, r) => {
    const u = new URL(q.url, 'http://x');
    if (u.searchParams.get('t') !== TOKEN) { r.writeHead(403); return r.end(); }
    if (u.pathname === '/') { r.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); return r.end(page0); }
    if (u.pathname === '/file') { const p = u.searchParams.get('path'); if (!fs.existsSync(p)) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'content-type': 'application/pdf' }); return r.end(fs.readFileSync(p)); }
    r.writeHead(404); r.end();
  }).listen(0, '127.0.0.1');
  await new Promise((res) => srv.on('listening', res));
  const port = srv.address().port;
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1300, height: 850 } });
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  const want = path.join(dir, '설명서 50쪽.pdf');
  //  프로그램 함수 흉내(go-webview2 의 Bind 처럼 Promise 를 돌려줌)
  await page.addInitScript((f) => {
    window.__calls = [];
    const P = (v) => (...a) => { window.__calls.push(a); return Promise.resolve(typeof v === 'function' ? v(...a) : v); };
    Object.assign(window, { hostPending: P([f]), hostFirstRun: P(false), hostTitle: P(null), hostUpdateState: P({ auto: true, version: '1', ready: '', notes: '' }), hostUpdateCheck: P(() => { window.__upd = true; }), hostDrives: P([]) });
  }, want);
  await page.goto('http://127.0.0.1:' + port + '/?t=' + TOKEN);
  await page.waitForTimeout(500);
  ok(await page.evaluate(() => !!window.HANIL_HOST && window.HANIL_HOST.name === 'windows'), 'HANIL_HOST 살아 있음' + (errs.length ? ' — 오류: ' + errs.join(' | ') : ''));
  const opened = await page.waitForFunction(() => window.__pdfReader.docs.some((d) => d.name === '설명서 50쪽.pdf'), null, { timeout: 15000 }).then(() => true, () => false);
  ok(opened, '두 번 눌러 넘어온 파일이 열림(hostPending → /file)');
  await page.click('.rt[data-rt=help]');
  await page.click('#ribbon [data-cmd=updCheck]');
  await page.waitForTimeout(300);
  ok(await page.evaluate(() => !!window.__upd), '업데이트 확인 → 프로그램 쪽(hostUpdateCheck)으로 감');
  ok(!/브라우저판/.test(await page.textContent('#stMaker')), '아래 줄에 「브라우저판」이 아님');
  await b.close(); srv.close();
  console.log(fails ? '❌ 실패 ' + fails : '모두 통과');
  process.exit(fails ? 1 : 0);
})();
