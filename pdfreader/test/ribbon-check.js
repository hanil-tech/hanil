//  리본이 눌려 겹치거나 ▾ 목록이 잘리지 않나 — node test/ribbon-check.js <시험 PDF 폴더> [그림 폴더]
const { chromium } = require('playwright');
const path = require('path');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1920, height: 1000 } });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.setInputFiles('#fOpen', path.join(path.resolve(process.argv[2]), 'A-001 섀시 부품표.pdf'));
  await page.waitForSelector('.pg canvas');
  for (const tab of ['home', 'view', 'edit', 'org', 'conv']) {
    await page.click('.rt[data-rt=' + tab + ']');
    //  단추 글자가 단추 밖으로 넘치거나(잘림) 이웃 단추와 겹치면 안 된다
    const bad = await page.$$eval('#ribbon button', (bs) => {
      const out = [];
      const rs = bs.filter((x) => x.offsetParent).map((x) => [x, x.getBoundingClientRect()]);
      for (const [x, r] of rs) {
        const sp = x.querySelector('span');
        if (sp && sp.scrollWidth > x.clientWidth + 2) out.push('넘침:' + sp.textContent);
        for (const [y, q] of rs) if (x !== y && !x.contains(y) && !y.contains(x) && r.left < q.right - 1 && q.left < r.right - 1 && r.top < q.bottom - 1 && q.top < r.bottom - 1) out.push('겹침:' + x.textContent + '/' + y.textContent);
      }
      return [...new Set(out)];
    });
    ok(bad.length === 0, tab + ' 탭: 단추가 겹치거나 잘리지 않음 ' + bad.slice(0, 4).join(', '));
    //  무리 이름표(도구·보기·주석 …)가 리본 아래로 잘리지 않나
    const cut = await page.$$eval('#ribbon .cap', (cs) => { const rb = document.querySelector('#ribbon').getBoundingClientRect(); return cs.filter((c) => c.textContent && c.getBoundingClientRect().bottom > rb.bottom + 0.5).map((c) => c.textContent); });
    ok(cut.length === 0, tab + ' 탭: 무리 이름표가 다 보임 ' + cut.join(','));
  }
  await page.click('.rt[data-rt=home]');
  await page.click('.mwrap button[data-cmd=tStamp] span');
  const vis = await page.$$eval('.rmenu.stamps.on .stp', (xs) => xs.map((x) => { const r = x.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return e === x || x.contains(e); }));
  ok(vis.length === 12 && vis.every(Boolean), '스탬프 ▾ 목록 12개가 모두 보이고 누를 수 있음');
  if (process.argv[3]) await page.screenshot({ path: path.join(process.argv[3], 'ribbon.png') });
  await page.click('.rmenu.stamps.on .stp:has-text("검토")');
  ok(await page.evaluate(() => window.__pdfReader.tool) === 'stamp', '목록에서 「검토」 → 스탬프 도구');
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
