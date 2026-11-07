//  실제 크로미움으로 단독 HTML 을 file:// 로 열어 확인 — node test/ui-check.js <시험 PDF 폴더> [그림 저장 폴더]
//   (시험 PDF 는 test/make-pdfs.py 로 만든다)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const dir = path.resolve(process.argv[2]);
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null;
const html = path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };

(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1600, height: 950 } });
  const errs = [];
  page.on('pageerror', (e) => { errs.push(e.message); console.log('   ⚠ ' + e.message); });
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto('file://' + html);
  const shot = async (n) => shots && page.screenshot({ path: path.join(shots, n + '.png') });
  await shot('0-빈화면');

  //  ① 열기 — 한글 CID 글꼴(글꼴 표 필요)
  await page.setInputFiles('#fOpen', [path.join(dir, 'A-001 섀시 부품표.pdf'), path.join(dir, '설명서 50쪽.pdf')]);
  await page.waitForFunction(() => window.__pdfReader.docs.length === 2);
  await page.waitForSelector('.doc:not([style*="none"]) .pg .textLayer span');
  ok(await page.$$eval('.dt', (e) => e.length) === 2, '두 문서가 탭으로 열림');
  ok((await page.textContent('#pgCnt')).includes('50'), '설명서 50쪽 — 쪽 수');
  //  한글이 실제로 글자 층에 있나(글꼴 표가 없으면 빈 글자)
  const t1 = await page.$$eval('.doc:not([style*="none"]) .pg[data-i="0"] .textLayer span', (s) => s.map((x) => x.textContent).join(''));
  ok(t1.includes('유압 실린더'), '한글 글자 읽힘(CMap): ' + t1.slice(0, 30));
  //  캔버스에 뭔가 그려졌나
  const inked = await page.evaluate(() => {
    const c = document.querySelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas');
    const x = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let dark = 0; for (let i = 0; i < x.length; i += 4) if (x[i] < 128) dark++;
    return dark;
  });
  ok(inked > 1000, '페이지가 그려짐(어두운 점 ' + inked + ')');
  await page.waitForTimeout(600);
  await shot('1-설명서');

  //  ② 책갈피 · 문서 안 고리
  await page.click('.ltabs button[data-lt=outline]');
  await page.waitForSelector('.ol');
  ok(await page.$$eval('.ol', (e) => e.length) === 50, '책갈피 50개');
  await page.locator('.ol').nth(9).click();
  await page.waitForTimeout(400);
  ok(await page.inputValue('#pgIn') === '10', '책갈피 → 10쪽');
  await page.click('[data-cmd=first]');
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] .lnk');
  await page.click('.doc:not([style*="none"]) .pg[data-i="0"] .lnk');
  await page.waitForTimeout(400);
  ok(await page.inputValue('#pgIn') === '34', '문서 안 고리 → 34쪽');
  await page.click('[data-cmd=back]');
  await page.waitForTimeout(300);
  ok(await page.inputValue('#pgIn') === '1', '이전 보기 → 1쪽');

  //  ③ 찾기(Ctrl+F)
  await page.keyboard.press('Control+f');
  await page.fill('#findIn', '40396607-5');
  await page.waitForFunction(() => /\d+ \/ \d+/.test(document.querySelector('#findCnt').textContent), null, { timeout: 15000 });
  ok(await page.textContent('#findCnt') === '1 / 1', '찾기: 1 / 1 — ' + await page.textContent('#findCnt'));
  await page.waitForSelector('.hl.cur');
  ok(await page.inputValue('#pgIn') === '34', '찾은 자리 34쪽으로 감');
  await shot('2-찾기');
  await page.keyboard.press('Escape');
  ok(await page.$$eval('.hl', (e) => e.length) === 0, 'Esc → 칠한 것 지움');

  //  ④ 확대·맞춤·회전
  await page.click('[data-cmd=zoomIn]');
  const z1 = await page.evaluate(() => window.__pdfReader.cur.zoom);
  await page.selectOption('#zoomSel', '2');
  ok(await page.evaluate(() => window.__pdfReader.cur.zoom) === 2, '200% (확대 단추 뒤 ' + z1.toFixed(2) + ')');
  ok(await page.inputValue('#pgIn') === '34', '확대해도 같은 쪽(34)');
  await page.click('.rt[data-rt=view]');
  await page.click('.mwrap button[data-menu=mVRot]'); await page.click('.rmenu.on [data-cmd=rotR]');
  await page.waitForTimeout(500);
  const pg = await page.$eval('.doc:not([style*="none"]) .pg[data-i="33"]', (e) => [e.offsetWidth, e.offsetHeight]);
  ok(pg[0] > pg[1], '오른쪽으로 돌리기 → 가로가 더 김 ' + pg);
  await page.click('.mwrap button[data-menu=mVRot]'); await page.click('.rmenu.on [data-cmd=rotL]');
  await page.click('#ribbon [data-cmd=two]');
  await page.waitForTimeout(400);
  await shot('3-두페이지');
  await page.click('#ribbon [data-cmd=one]');
  await page.click('#ribbon [data-cmd=page]');

  //  ⑤ 폴더 검색 — 스크린샷의 그 화면
  const fc = page.waitForEvent('filechooser');
  await page.selectOption('#where', 'folder');
  await (await fc).setFiles(dir);
  await page.waitForFunction(() => /PDF \d+개/.test(document.querySelector('#where2').textContent));
  console.log('   ' + await page.textContent('#where2'));
  await page.fill('#sq', '40396607-5');
  await page.click('#sGo');
  await page.waitForFunction(() => /완료/.test(document.querySelector('#sstat').textContent), null, { timeout: 60000 });
  const st = await page.textContent('#sstat');
  console.log('   ' + st.replace(/\n/g, ' | '));
  ok(/발견: 7 문서, 9 항목/.test(st), '폴더 검색: 7 문서 9 항목');
  const names = await page.$$eval('.rd .rh span', (e) => e.map((x) => x.textContent));
  for (const n of ['A-003 조각난 번호', 'A-004 전각', 'D-깊은 곳', 'C-007', '설명서 50쪽'])
    ok(names.some((x) => x.includes(n)), '결과에 ' + n);
  ok(names.some((x) => x.includes('찾지 못하는 문서 (3)')), '암호·깨짐·스캔 3개를 따로 알림');
  ok(/글자가 없는\(스캔한 그림\) PDF 1개/.test(st) && /열지 못한 PDF 2개/.test(st), '스캔 1 · 못 연 것 2');
  await shot('4-폴더검색');

  //  결과 누르기 → 그 문서가 열리고 그 자리가 칠해짐
  const item = await page.$$('.rd .ri');
  const ix = (await page.$$eval('.rd', (ds) => ds.map((d) => d.querySelector('.rh span').textContent))).findIndex((x) => x.includes('A-003'));
  const g = (await page.$$('.rd'))[ix];
  const its = await g.$$('.ri');
  await its[1].click();
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('A-003'));
  await page.waitForSelector('.doc:not([style*="none"]) .hl.cur');
  const nh = await page.$$eval('.doc:not([style*="none"]) .hl', (e) => new Set(e.map((x) => x.dataset.k)).size);
  ok(nh === 2, '결과 누름 → A-003 열림, 두 군데 칠함(조각난 것·띄어 쓴 것)');
  ok(await page.$eval('.doc:not([style*="none"]) .hl.cur', (e) => e.dataset.k) === '1', '누른 그 자리(두 번째)가 강조됨');
  await shot('5-결과누름');

  //  하위 폴더 빼기
  await page.click('#sOpt');
  await page.uncheck('#oSub');
  await page.click('#sGo');
  await page.waitForFunction(() => /완료/.test(document.querySelector('#sstat').textContent));
  ok(/발견: 5 문서, 7 항목/.test(await page.textContent('#sstat')), '하위 폴더 빼면 5 문서 7 항목 — ' + (await page.textContent('#sstat')).split('\n')[0]);
  //  띄어쓰기 무시 끄기
  await page.check('#oSub');
  await page.uncheck('#oSpace');
  await page.click('#sGo');
  await page.waitForFunction(() => /완료/.test(document.querySelector('#sstat').textContent));
  ok(/발견: 7 문서, 8 항목/.test(await page.textContent('#sstat')), '띄어쓰기 무시 끄면 8 항목(띄어 쓴 하나 빠짐) — ' + (await page.textContent('#sstat')).split('\n')[0]);
  await page.check('#oSpace');

  //  목록 저장
  const dl = page.waitForEvent('download');
  await page.click('#sCsv');
  const d = await dl;
  const csv = fs.readFileSync(await d.path(), 'utf8');
  ok(csv.split('\r\n').length === 9 && csv.includes('A-001'), '목록 저장(CSV) ' + d.suggestedFilename());

  //  ⑥ 속성 · 암호 문서
  ok((await page.textContent('#pProps')).includes('한일특장 설계팀'), '속성: 작성자');
  await page.setInputFiles('#fOpen', path.join(dir, 'B-100 암호.pdf'));
  await page.waitForSelector('#modal.on #mIn');
  await page.fill('#mIn', '0000'); await page.keyboard.press('Enter');
  await page.waitForFunction(() => /틀렸/.test(document.querySelector('#mBody').textContent));
  ok(true, '틀린 암호 → 다시 물음');
  await page.fill('#mIn', '1234'); await page.keyboard.press('Enter');
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('암호'));
  ok(true, '맞는 암호 → 열림');
  //  깨진 파일
  await page.setInputFiles('#fOpen', path.join(dir, '깨진 파일.pdf'));
  await page.waitForSelector('#modal.on');
  ok((await page.textContent('#mBody')).includes('깨졌'), '깨진 파일 → 까닭 알림');
  await page.keyboard.press('Escape');

  //  ⑦ A3 가로 · 페이지 맞춤 · 너비 맞춤 · 닫기
  await page.setInputFiles('#fOpen', path.join(dir, 'A3 가로 도면.pdf'));
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('A3'));
  ok((await page.textContent('#pProps')).includes('A3 가로'), '속성: A3 가로 알아봄');
  await page.keyboard.press('Control+w');
  ok(await page.$$eval('.dt', (e) => e.length) === 4, 'Ctrl+W 닫기');

  //  인쇄 준비(그림 만들기)까지
  await page.evaluate(() => { window.print = () => { window.__printed = document.querySelectorAll('#printArea img').length; }; });
  await page.click('.dt:nth-child(2)');   //  설명서
  await page.keyboard.press('Control+p');
  await page.waitForSelector('#modal.on input[name=pr]');   //  인쇄할 쪽 고르기 → 모든 쪽
  await page.click('#mFoot button:first-child');
  await page.waitForFunction(() => window.__printed, null, { timeout: 60000 });
  ok(await page.evaluate(() => window.__printed) === 50, '인쇄: 50쪽 그림 준비');

  ok(errs.length === 0, '화면 오류 없음 ' + errs.slice(0, 3).join(' / '));
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
