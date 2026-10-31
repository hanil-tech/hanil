//  자동 업데이트 화면 — 윈도우 프로그램 흉내(HANIL_HOST)로 알림 띠·다시 시작·환경 설정 확인 — node test/update-check.js
const { chromium } = require('playwright');
const path = require('path');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1400, height: 900 } });
  page.on('pageerror', (e) => { fails++; console.log('⚠ ' + e.message); });
  await page.addInitScript(() => {
    window.__log = [];
    let R = null, auto = true;
    window.HANIL_HOST = {
      name: 'windows',
      ready: (r) => { R = r; },
      updateState: async () => ({ auto, version: '1.6.0', ready: '', notes: '' }),
      setAutoUpdate: async (on) => { auto = on; window.__log.push('auto:' + on); },
      updateCheck: async () => { window.__log.push('check'); setTimeout(() => window.HANIL_HOST.updateMsg('지금 판(v1.6.0)이 가장 새 판입니다.'), 100); },
      updateMsg: (m) => R && R.updateMsg(m),
      updated: (i) => R && R.updated(i),
      restart: async () => window.__log.push('restart'),
    };
  });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.waitForTimeout(300);
  //  새 판을 받았다는 알림 → 띠 → 다시 시작
  await page.evaluate(() => window.HANIL_HOST.updated({ version: '1.7.0', notes: '고침 몇 가지' }));
  await page.waitForSelector('#updBar');
  ok(/v1\.7\.0/.test(await page.textContent('#updBar')), '알림 띠: 「새 판 v1.7.0 을 받아 두었습니다」');
  await page.click('#updBar button:has-text("지금 다시 시작")');
  await page.waitForTimeout(200);
  ok((await page.evaluate(() => window.__log)).includes('restart'), '「지금 다시 시작」 → 프로그램에 다시 시작 요청');
  await page.evaluate(() => window.HANIL_HOST.updated({ version: '1.7.0' }));
  ok(await page.$$eval('#updBar', (e) => e.length) === 1, '알림이 두 번 와도 띠는 하나');
  await page.click('#updBar button.x');
  //  도움말 → 업데이트 확인
  await page.click('.rt[data-rt=help]');
  await page.click('#ribbon [data-cmd=updCheck]');
  await page.waitForFunction(() => /가장 새 판/.test(document.querySelector('#toast').textContent));
  ok(true, '도움말 → 업데이트 확인 → 「가장 새 판입니다」');
  //  환경 설정 → 정보·업데이트 → 자동 업데이트 끄기
  await page.click('#ribbon [data-cmd=settings]');
  await page.click('.setcats button:has-text("정보")');
  await page.waitForSelector('.setrow:has-text("자동 업데이트") input');
  ok(await page.isChecked('.setrow:has-text("자동 업데이트") input'), '환경 설정: 자동 업데이트 켜져 있음');
  await page.uncheck('.setrow:has-text("자동 업데이트") input');
  await page.click('.setbtn:has-text("지금 업데이트 확인")');
  await page.waitForFunction(() => /가장 새 판/.test(document.querySelector('#updMsg').textContent));
  ok((await page.evaluate(() => window.__log)).includes('auto:false'), '자동 업데이트 끄기 · 지금 확인 결과가 설정 창에');
  await page.screenshot({ path: require('os').tmpdir() + '/update.png' });
  await b.close();
  console.log(fails ? '❌ 실패 ' + fails : '모두 통과');
  process.exit(fails ? 1 : 0);
})();
