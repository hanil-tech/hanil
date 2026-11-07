//  스냅샷: 끌면 그 부분 · 한 번 누르면 보이는 화면 전체 — node test/snap-check.js <시험 PDF 폴더> [그림 폴더]
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1500, height: 900 } });
  page.on('pageerror', (e) => { fails++; console.log('⚠ ' + e.message); });
  //  클립보드에 들어간 그림을 가로챈다
  await page.addInitScript(() => {
    window.__clips = [];
    Object.defineProperty(navigator, 'clipboard', { value: { write: async (items) => { for (const it of items) { const bl = await it.getType('image/png'); window.__clips.push(await new Promise((r) => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(bl); })); } }, writeText: async () => {} } });
  });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.setInputFiles('#fOpen', path.join(path.resolve(process.argv[2]), '설명서 50쪽.pdf'));
  await page.waitForSelector('.pg[data-i="0"] canvas');
  await page.click('.rt[data-rt=view]'); await page.click('#ribbon [data-cmd=two]'); await page.click('#ribbon [data-cmd=page]');
  await page.click('.rt[data-rt=home]');
  await page.click('#ribbon [data-cmd=tSnap]');
  await page.waitForSelector('.pg[data-i="0"] .ov');
  const bx = await (await page.$('.pg[data-i="0"]')).boundingBox();
  //  ① 한 번 누름 → 화면 전체
  await page.mouse.click(bx.x + bx.width / 2, bx.y + bx.height / 2);
  await page.waitForFunction(() => window.__clips.length === 1, null, { timeout: 20000 });
  const sz = await page.evaluate(async () => { const im = new Image(); im.src = window.__clips[0]; await im.decode(); const v = document.querySelector('#viewer'); return [im.width, im.height, v.clientWidth, v.clientHeight]; });
  ok(Math.abs(sz[0] / sz[1] - sz[2] / sz[3]) < 0.02 && sz[0] >= sz[2], '한 번 누름 → 보이는 화면 전체(두 페이지) ' + sz[0] + '×' + sz[1] + ' (화면 ' + sz[2] + '×' + sz[3] + ')');
  //  ② 끌기 → 그 부분
  await page.mouse.move(bx.x + 20, bx.y + 20); await page.mouse.down(); await page.mouse.move(bx.x + 220, bx.y + 120, { steps: 4 }); await page.mouse.up();
  await page.waitForFunction(() => window.__clips.length === 2, null, { timeout: 20000 });
  const s2 = await page.evaluate(async () => { const im = new Image(); im.src = window.__clips[1]; await im.decode(); return [im.width, im.height]; });
  ok(Math.abs(s2[0] / s2[1] - 2) < 0.1, '끌기 → 그 네모만 ' + s2.join('×'));
  //  ③ 페이지 밖 회색 바탕을 눌러도 화면 전체
  const vb = await (await page.$('#viewer')).boundingBox();
  await page.mouse.click(vb.x + 6, vb.y + vb.height - 8);
  await page.waitForFunction(() => window.__clips.length === 3, null, { timeout: 20000 });
  ok(true, '회색 바탕을 눌러도 화면 전체');
  if (process.argv[3]) fs.mkdirSync(process.argv[3], { recursive: true }), fs.writeFileSync(path.join(process.argv[3], 'snap-view.png'), Buffer.from((await page.evaluate(() => window.__clips[0])).split(',')[1], 'base64'));
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
