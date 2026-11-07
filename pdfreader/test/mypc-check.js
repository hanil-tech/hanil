//  윈도우 프로그램 흉내(HANIL_HOST)로 파일 → 열기 → 내 PC(드라이브·폴더) 확인 — node test/mypc-check.js
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const page = await b.newPage({ viewport: { width: 1300, height: 800 } });
  page.on('pageerror', (e) => console.log('ERR', e.message));
  await page.addInitScript(() => {
    const FS = { 'C:\\': [{ name: 'Users', dir: true, path: 'C:\\Users' }, { name: '도면', dir: true, path: 'C:\\도면' }], 'C:\\도면': [{ name: 'A-001.pdf', dir: false, path: 'C:\\도면\\A-001.pdf' }, { name: '하위', dir: true, path: 'C:\\도면\\하위' }], 'C:\\도면\\하위': [] };
    window.__opened = [];
    window.HANIL_HOST = {
      drives: async () => [{ name: '바탕 화면', path: 'C:\\Users\\a\\Desktop', icon: '🖥' }, { name: '로컬 디스크 (C:)', path: 'C:\\', icon: '💽' }, { name: 'DATA (D:)', path: 'D:\\', icon: '💽' }],
      listDir: async (p) => FS[p] || [],
      openPath: (p) => window.__opened.push(p),
    };
  });
  await page.goto('file://' + require('path').join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.click('.rt.file');
  await page.waitForSelector('#bsPanel h1');
  const t = await page.textContent('#bsPanel');
  console.log(/URL/.test(t) ? '❌ URL 칸 남음' : '✅ URL 칸 없음', t.includes('로컬 디스크 (C:)') && t.includes('DATA (D:)') ? '✅ C: D: 보임' : '❌ 드라이브 없음');
  await page.click('.bsitem:has-text("로컬 디스크 (C:)")');
  await page.click('.bslist .bsitem:has-text("도면")');
  await page.waitForSelector('.bslist .bsitem:has-text("A-001.pdf")');
  console.log('✅ C: → 도면 폴더 → PDF 보임:', await page.textContent('.bshead span'));
  await page.click('.bslist .bsitem:has-text("하위")');
  await page.waitForSelector('.bslist .bsnone');
  await page.click('.bslist .bsitem:has-text("위 폴더")');
  await page.waitForSelector('.bslist .bsitem:has-text("A-001.pdf")');
  console.log('✅ 위 폴더로 돌아옴:', await page.textContent('.bshead span'));
  await page.screenshot({ path: require('os').tmpdir() + '/mypc.png' });
  await page.click('.bslist .bsitem:has-text("A-001.pdf")');
  console.log(JSON.stringify(await page.evaluate(() => window.__opened)) === '["C:\\\\도면\\\\A-001.pdf"]' ? '✅ PDF 누르면 열기' : '❌ 열기', await page.evaluate(() => window.__opened));
  await b.close();
})();
