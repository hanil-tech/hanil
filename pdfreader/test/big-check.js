//  큰 문서 시험(300·1000쪽, 스캔 300쪽) — node test/big-check.js <큰 PDF 폴더> <결과 폴더>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const dir = path.resolve(process.argv[2]);
const out = path.resolve(process.argv[3]);
fs.mkdirSync(out, { recursive: true });
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
const t0 = () => Date.now();
const sec = (t) => ((Date.now() - t) / 1000).toFixed(1) + '초';

(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1400, height: 900 } });
  page.on('pageerror', (e) => { fails++; console.log('   ⚠ ' + e.message); });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.evaluate(() => { window.print = () => { window.__printed = document.querySelectorAll('#printArea img').length; }; });
  const R = (f, a) => page.evaluate(f, a);
  const mem = () => R(() => performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) + 'MB' : '?');
  for (const [name, n] of [['글자300쪽.pdf', 300], ['스캔300쪽.pdf', 300], ['글자1000쪽.pdf', 1000]]) {
    console.log('── ' + name);
    let t = t0();
    await page.setInputFiles('#fOpen', path.join(dir, name));
    await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas', { timeout: 60000 });
    const open = Date.now() - t;
    ok(open < 8000 && await R(() => window.__pdfReader.cur.n) === n, '열기 → 첫 쪽 ' + sec(t) + ' (' + n + '쪽)');
    //  끝 쪽으로(End)
    t = t0();
    await page.click('#viewer'); await page.keyboard.press('End');
    await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="' + (n - 1) + '"] canvas', { timeout: 30000 });
    ok(Date.now() - t < 6000, '끝 쪽 그리기 ' + sec(t));
    //  쭉 굴리기 — 그려진 캔버스 수가 늘지 않아야(메모리)
    await page.keyboard.press('Home');
    for (let k = 0; k < 40; k++) { await page.mouse.wheel(0, 2500); await page.waitForTimeout(30); }
    await page.waitForTimeout(800);
    const cvs = await R(() => document.querySelectorAll('.doc:not([style*="none"]) .pg canvas').length);
    ok(cvs <= 30, '굴린 뒤 그려 둔 쪽 ' + cvs + '개 · 메모리 ' + await mem());
    //  가운데 쪽 이동
    t = t0();
    await page.fill('#pgIn', String(Math.floor(n / 2))); await page.press('#pgIn', 'Enter');
    await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="' + (Math.floor(n / 2) - 1) + '"] canvas', { timeout: 30000 });
    ok(true, n / 2 + '쪽 이동 ' + sec(t));
    //  찾기(글자 문서만)
    if (!/스캔/.test(name)) {
      t = t0();
      await page.keyboard.press('Control+f');
      await page.fill('#findIn', 'MARK-LAST-' + n);
      await page.waitForFunction(() => /\d+ \/ \d+/.test(document.querySelector('#findCnt').textContent), null, { timeout: 120000 });
      ok(await page.textContent('#findCnt') === '1 / 1' && await page.inputValue('#pgIn') === String(n - 2), '전체 찾기 ' + sec(t) + ' → ' + await page.inputValue('#pgIn') + '쪽');
      await page.keyboard.press('Escape');
    }
    //  쪽 그림 칸 — 맨 끝까지 내리기
    t = t0();
    await R(() => { const b = document.querySelector('#thumbs'); b.scrollTop = b.scrollHeight; });
    await page.waitForSelector('#thumbs .th[data-i="' + (n - 1) + '"] canvas', { timeout: 30000 });
    ok(true, '쪽 그림 끝까지 ' + sec(t));
    //  주석 하나 + 저장(만들기)
    t = t0();
    const len = await R(async () => {
      const A = window.__pdfReader, d = A.cur;
      A.EDIT.addObj ? 0 : 0;
      d.mod = true;
      const u = await A.buildPdf(d);
      return u.length;
    });
    ok(len > 1000, '저장용 PDF 만들기 ' + sec(t) + ' (' + (len / 1048576).toFixed(1) + 'MB)');
    //  인쇄 준비 4쪽 모아(글자 300쪽만 — 오래 걸림)
    if (name === '글자300쪽.pdf' || name === '스캔300쪽.pdf') {
      t = t0();
      await R(() => { window.__printed = null; });
      await page.keyboard.press('Control+p');
      await page.waitForSelector('#prNup');
      await page.selectOption('#prNup', '4');
      await page.check('input[name=pr][value=all]');
      await page.click('#mFoot button:first-child');
      await page.waitForFunction(() => window.__printed != null, null, { timeout: 600000 });
      ok(await R(() => window.__printed) === 75, '인쇄 준비 4쪽 모아 75장 ' + sec(t) + ' · 메모리 ' + await mem());
    }
    await page.screenshot({ path: path.join(out, name.replace('.pdf', '.png')) });
    await R(() => { window.__pdfReader.cur.mod = false; });
    await page.keyboard.press('Control+w');
    await page.waitForTimeout(300);
  }
  await b.close();
  console.log(fails ? '❌ 실패 ' + fails : '✅ 모두 통과');
  process.exit(fails ? 1 : 0);
})();
