//  바탕화면 달력 점검 — 가짜 포털 + 관문(리눅스 빌드) + 화면(Playwright)
//   cd deskcal && go build -o /tmp/hanil-cal . && cd test && npm i && node check.js
'use strict';
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const { chromium } = require('playwright');
const BIN = process.env.BIN || '/tmp/hanil-cal', PP = 3998, GP = 18851, G = 'http://127.0.0.1:' + GP, P = 'http://127.0.0.1:' + PP;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hcal-')), SHOT = process.env.SHOT || tmp;
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const procs = [];
function run(cmd, args, env) {
  const p = spawn(cmd, args, { env: Object.assign({}, process.env, env), stdio: ['ignore', 'pipe', 'pipe'] });
  p.out = ''; p.stdout.on('data', (b) => { p.out += b; }); p.stderr.on('data', (b) => { p.out += b; });
  procs.push(p); return p;
}
async function waitUp(u) { for (let i = 0; i < 50; i++) { try { await fetch(u); return; } catch (e) { await sleep(150); } } throw new Error('안 뜸 ' + u); }
const ymd = (t) => t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0');

(async () => {
  run('node', [path.join(__dirname, 'fake-portal.js')], { PORT: PP, STORE: path.join(tmp, 'store') });
  await waitUp(P + '/api/version');
  const gw = run(BIN, ['--url=' + P, '--port=' + GP], { LOCALAPPDATA: path.join(tmp, 'local') });
  await waitUp(G + '/__cal/ping');
  ok((await (await fetch(G + '/__cal/ping')).text()).startsWith('hanil-cal'), '관문 ping');

  //  관문이 막는 길
  let r = await fetch(G + '/api/appr/101/act', { method: 'POST' });
  ok(r.status === 403, '결재 승인(쓰기)은 관문이 막는다 → ' + r.status);
  r = await fetch(G + '/admin/secret', { redirect: 'manual' });
  ok(r.status === 302 && r.headers.get('location') === '/cal', '다른 포털 화면은 달력으로 돌린다');
  r = await fetch(G + '/api/apprdoc/list');
  ok(r.status === 401 && (await r.json()).login === true, '로그인 전 API → 401 login');
  r = await fetch(G + '/__cal/data', { method: 'PUT', headers: { Origin: 'http://evil.example' }, body: '{}' });
  ok(r.status === 403, '다른 사이트에서 메모를 덮어쓰지 못한다');

  const br = await chromium.launch();
  const pg = await br.newPage({ viewport: { width: 1400, height: 860 } });
  pg.on('dialog', (d) => d.accept());
  const errs = []; pg.on('pageerror', (e) => errs.push(e.message));
  await pg.goto(G + '/cal');
  await pg.waitForSelector('#banner.on.login', { timeout: 5000 });
  ok(true, '로그인 안내 띠가 보인다');
  await pg.screenshot({ path: path.join(SHOT, '0-login-needed.png') });

  //  로그인 — 포털 로그인 화면이 관문을 거쳐 나온다(next=/cal 심김)
  await pg.click('#bLogin');
  await pg.waitForSelector('#u');
  ok(await pg.$('input[name=next][value="/cal"]') !== null, '로그인 화면에 next=/cal 이 심겼다');
  await pg.fill('#u', 'kim'); await pg.fill('#p', 'wrong'); await pg.click('#go');
  await pg.waitForSelector('#err');
  ok(true, '틀린 비밀번호 → 포털의 오류가 그대로 보인다');
  await pg.fill('#u', 'kim'); await pg.fill('#p', '1234'); await pg.click('#go');
  await pg.waitForURL(G + '/cal');
  ok(true, '로그인하면 달력으로 돌아온다');

  //  🔔 결재 차례 알림(오늘 처음 켰고 남은 문서가 있다)
  await pg.waitForSelector('#alertDlg.on', { timeout: 8000 });
  ok((await pg.textContent('#aBig')).includes('1건'), '결재 차례 알림이 화면 가운데 뜬다: ' + (await pg.textContent('#aBig')));
  await pg.screenshot({ path: path.join(SHOT, '2-alert.png') });
  await pg.click('#aLater');
  await sleep(300);
  ok(/알림: 📄 결재할 문서가 1건/.test(gw.out), '윈도 알림(풍선)도 보냈다');

  ok(await pg.$('.chip.wait[data-doc="101"]') !== null, '결재할 문서가 기안일 칸에 보인다');
  ok(await pg.$('.chip.wait[data-doc="201"]') === null && await pg.$('[data-doc="201"]') !== null, '내 차례가 아닌 문서(앞사람 차례)는 「결재할 문서」 가 아니다');
  ok((await pg.textContent('#nWait')) === '1', '결재할 문서 = 문서의 my_turn 이 참인 것만(1건)');
  ok((await pg.textContent('#lTodo')).includes('납기 지난 발주') && !(await pg.textContent('#lTodo')).includes('po_overdue'), '포털 할 일 이름을 우리말로');
  await pg.hover('#lTodo [data-hidetodo="recon"]'.replace('"recon"', '"recon"'));
  await pg.click('#lTodo [data-hidetodo="recon"]');
  ok(!(await pg.textContent('#lTodo')).includes('대사'), '포털 할 일 항목 숨기기');
  //  📅 포털에 원래 있는 달력 — 스스로 찾아서 보인다
  await pg.waitForSelector('.chip.pc', { timeout: 10000 }).catch(() => {});
  const disc = await (await fetch(G + '/__cal/discover')).json();
  ok(disc.api === '/api/schedule/list' && disc.page === '/schedule', '포털 달력 API 를 스스로 찾았다: ' + disc.api);
  const t2 = new Date(); t2.setDate(t2.getDate() + 2);
  if (t2.getMonth() !== new Date().getMonth()) await pg.click('#next');
  await pg.waitForSelector(`.cell[data-d="${ymd(t2)}"] .chip.pc`, { timeout: 5000 });
  ok((await pg.textContent(`.cell[data-d="${ymd(t2)}"]`)).includes('15:00 📅 협력사 방문'), '포털 달력 일정이 달력에 나온다');
  if (t2.getMonth() !== new Date().getMonth()) await pg.click('#prev');
  r = await fetch(G + '/api/schedule/list');
  ok(r.status === 200, '찾은 포털 달력 주소는 관문이 통과시킨다');
  ok(await pg.$('.chip.ing[data-doc="90"]') !== null, '내가 올린 문서도 보인다');
  ok((await pg.textContent('#lMsg')).includes('견적서'), '쪽지가 옆 칸에 보인다');
  ok((await pg.textContent('#lTodo')).includes('안 읽은 메일 269'), '오늘 할 일이 옆 칸에 보인다');

  //  문서 보기 — 포털 인쇄 화면이 틀에 뜬다(X-Frame-Options 를 뗐다)
  await pg.click('.chip.wait[data-doc="101"]');
  const fr = await (await pg.waitForSelector('#dFrame')).contentFrame();
  await fr.waitForSelector('h2', { timeout: 5000 });
  ok((await fr.textContent('h2')).includes('#101'), '결재 문서 종이가 달력 안에 열린다');
  //  🌫 결재 문서를 보는 동안은 투명도 100%(바탕화면 모드인 척)
  await pg.click('#docDlg .x');
  await pg.evaluate(() => { window.__cal.S.desktop = true; });
  await pg.click('.chip.wait[data-doc="101"]');
  await sleep(300);
  ok(/창 명령: talpha 100/.test(gw.out), '결재 문서를 열면 투명도를 잠시 100%');
  await pg.click('#docDlg .x');
  await sleep(300);
  ok(/창 명령: talpha \n/.test(gw.out), '문서를 닫으면 투명도를 되돌린다');
  await pg.evaluate(() => { window.__cal.S.desktop = false; });
  await pg.click('.chip.wait[data-doc="101"]');
  await pg.click('#dOpen');
  await sleep(200);
  ok(/열기: http:\/\/127\.0\.0\.1:3998\/approval\?doc=101/.test(gw.out), '「포털에서 결재하기」 → 평소 브라우저로 결재 화면');

  //  📅 회사 일정 등록
  const t = new Date(), td = ymd(t);
  await pg.click('#addBtn');
  await pg.fill('#fTitle', '월간 안전 회의');
  await pg.fill('#fTime', '14:00');
  await pg.fill('#fPlace', '2층 회의실');
  await pg.click('#fColors span[data-c="#d93025"]');
  await pg.click('#evSave');
  await pg.waitForSelector('#evDlg', { state: 'hidden' });
  await pg.waitForSelector(`.cell[data-d="${td}"] .chip.co`);
  ok(true, '회사 일정을 올리면 오늘 칸에 나온다');
  //  내 일정(여러 날)
  await pg.click(`.cell[data-d="${td}"] .add`);
  await pg.fill('#fTitle', '연차');
  await pg.click('label:has(input[name=kind][value=private])');
  const end = new Date(t); end.setDate(end.getDate() + 2);
  await pg.fill('#fEnd', ymd(end));
  await pg.click('#evSave');
  await pg.waitForSelector('#evDlg', { state: 'hidden' });
  await pg.waitForSelector('.chip.pv', { state: 'attached', timeout: 5000 }).catch(() => {});
  ok((await pg.$$('.chip.pv')).length >= 1, '내 일정(여러 날)도 나온다');
  //  잘못된 값
  await pg.click('#addBtn'); await pg.click('#evSave');
  ok((await pg.textContent('#evErr')).includes('제목'), '제목 없이 저장하면 막는다');
  await pg.click('#evDlg [data-close]');

  //  다른 직원(이사원)에게는 회사 일정만 보인다 — 포털에 바로 묻는다
  const lg = await fetch(P + '/login', { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'username=lee&password=1234' });
  const ck = lg.headers.get('set-cookie').split(';')[0];
  const ev = await (await fetch(P + '/api/cal/events?from=2000-01-01&to=2100-01-01', { headers: { Cookie: ck } })).json();
  ok(ev.events.length === 1 && ev.events[0].title === '월간 안전 회의' && ev.events[0].ownerName === '김부장' && !ev.events[0].editable, '이사원: 회사 일정만 보이고 고칠 수 없다 ' + JSON.stringify(ev.events.map((e) => [e.title, e.kind, e.ownerName, e.editable])));
  const del = await fetch(P + '/api/cal/events/' + ev.events[0].id, { method: 'DELETE', headers: { Cookie: ck } });
  ok(del.status === 403, '남의 회사 일정은 못 지운다');

  //  일정 고치기
  await pg.click(`.cell[data-d="${td}"] .chip.co`);
  await pg.fill('#fTitle', '월간 안전 회의 (변경)');
  await pg.click('#evSave');
  await pg.waitForSelector('#evDlg', { state: 'hidden' });
  ok((await pg.textContent(`.cell[data-d="${td}"]`)).includes('(변경)'), '일정을 고친다');

  //  메모(이 PC)
  const box = await (await pg.$(`.cell[data-d="${td}"]`)).boundingBox();
  await pg.mouse.dblclick(box.x + box.width - 8, box.y + box.height - 8);
  await pg.waitForSelector('textarea[data-memo]');
  await pg.keyboard.type('거래처 전화하기');
  await pg.click('#ym');
  await sleep(800);
  const data = await (await fetch(G + '/__cal/data')).json();
  ok(data.notes && data.notes[td] && data.notes[td].t === '거래처 전화하기', '날짜 메모가 이 PC 에 저장된다');

  //  새 결재 차례 → 다시 알림
  await fetch(P + '/__test/wait', { method: 'POST' });
  await pg.evaluate(() => window.__cal.poll());
  await pg.waitForSelector('#alertDlg.on', { timeout: 5000 });
  ok((await pg.textContent('#aBig')).includes('2건') && !(await pg.textContent('#aList')).includes('업무일지'), '새 결재 문서가 오면 다시 크게 뜬다(내 차례 아닌 것은 빼고)');
  await pg.screenshot({ path: path.join(SHOT, '3-new-wait.png') });
  await pg.click('#aLater');

  //  🔴 휴일 자동 — 포털이 공공데이터포털에서 받아 온 것
  const ph = await pg.evaluate(() => window.__cal.holidays(2026));
  ok(ph['2026-11-06'] === '임시공휴일', '포털에서 받아 온 휴일(임시공휴일)을 쓴다 ' + JSON.stringify(ph).slice(0, 120));
  const ph27 = await pg.evaluate(() => window.__cal.holidays(2027));
  ok(ph27['2027-02-07'] === '설날', '포털에 그해 휴일이 없으면 스스로 계산한 것을 쓴다');

  //  🔴 회사 휴무일 — 「휴일로 표시」한 회사 일정은 빨간 날
  const hd = new Date(t); hd.setDate(hd.getDate() + 5);
  await pg.click('#addBtn');
  await pg.fill('#fTitle', '창립기념일');
  await pg.fill('#fStart', ymd(hd)); await pg.fill('#fEnd', ymd(hd));
  await pg.check('#fHol');
  await pg.click('#evSave');
  await pg.waitForSelector('#evDlg', { state: 'hidden' });
  if (hd.getMonth() !== t.getMonth()) await pg.click('#next');
  await pg.waitForSelector(`.cell.hol[data-d="${ymd(hd)}"] .hn`);
  ok((await pg.textContent(`.cell[data-d="${ymd(hd)}"] .hn`)).includes('창립기념일'), '회사 휴무일이 빨간 날로 표시된다');
  if (hd.getMonth() !== t.getMonth()) await pg.click('#prev');

  //  공휴일
  const hol = await pg.evaluate(() => { var c = window.__cal; c.PH[2026] = null; return c.holidays(2026); });
  ok(hol['2026-02-17'] === '설날' && hol['2026-03-02'] === '대체공휴일' && hol['2026-05-25'] === '대체공휴일' && !hol['2026-09-28'] && hol['2026-10-05'] === '대체공휴일' && hol['2026-08-17'] === '대체공휴일', '2026 공휴일·대체공휴일 ' + JSON.stringify(hol));
  const h25 = await pg.evaluate(() => window.__cal.holidays(2025));
  ok(h25['2025-05-06'] === '대체공휴일' && h25['2025-10-08'] === '대체공휴일' && h25['2025-03-03'] === '대체공휴일' && !h25['2025-05-07'], '2025 대체공휴일 ' + JSON.stringify(h25));

  await pg.screenshot({ path: path.join(SHOT, '1-calendar.png') });
  await pg.click('#setBtn'); await pg.selectOption('#sTheme', 'dark'); await pg.click('#sSave');
  await pg.screenshot({ path: path.join(SHOT, '4-dark.png') });

  //  ════ DesktopCal 기능 ════
  await pg.evaluate(() => { window.print = () => { window.__printed = (window.__printed || 0) + 1; }; });
  //  만년 음력 · 24절기
  const lu = await pg.evaluate(() => window.__cal.lunarOf('2026-02-17'));
  ok(lu && lu.m === 1 && lu.d === 1, '만년 음력: 2026-02-17 = 음력 1.1');
  ok(await pg.evaluate(() => window.__cal.termsOf(2026)['2026-02-04'] === '입춘' && window.__cal.termsOf(2026)['2026-12-22'] === '동지'), '24절기(입춘·동지)');
  ok(await pg.evaluate(() => window.__cal.solarOfLunar(2040, 1, 1)) === '2040-02-12', '표가 없는 해(2040)도 설날을 음력으로 계산');
  await pg.click('#setBtn'); await pg.click('#setTabs [data-tab=cal]'); await pg.check('#sTerms'); await pg.check('#sObs'); await pg.click('#sSave');
  ok((await pg.textContent('.cell[data-d="2026-11-07"] .tm')) === '입동', '달력 칸에 절기(입동)가 보인다');
  ok(/^\d+\.\d+$/.test((await pg.textContent('.cell[data-d="2026-11-05"] .lu')) || ''), '달력 칸에 음력이 보인다');

  //  메모 칸 배경색(중요한 날)
  await pg.dblclick(`.cell[data-d="${td}"] .dn`);
  await pg.waitForSelector('textarea[data-memo]');
  await pg.click('[data-mbg="#ffe3e3"]');
  await pg.click('#ym'); await sleep(500);
  ok(((await (await fetch(G + '/__cal/data')).json()).notes[td] || {}).bg === '#ffe3e3', '중요한 날 칸 배경색');

  //  할 일
  await pg.fill('#todoIn', '견적서 보내기 11/20'); await pg.press('#todoIn', 'Enter');
  ok((await pg.textContent('#lTd')).includes('견적서 보내기') && (await pg.textContent('#lTd')).includes('11/20'), '할 일 목록(날짜 붙이기)');
  await pg.click('#lTd input[type=checkbox]');
  ok(await pg.$('#lTd .todo.done') !== null, '할 일 끝내기');

  //  음력 기념일 — 오늘의 음력 날짜로 넣으면 오늘 칸에 나온다
  const tl = await pg.evaluate((d) => window.__cal.lunarOf(d), td);
  await pg.click('#setBtn'); await pg.click('#setTabs [data-tab=anv]');
  await pg.fill('#aTitle', '어머니 생신');
  await pg.selectOption('#aM', String(tl.m).padStart(2, '0')); await pg.selectOption('#aD', String(tl.d).padStart(2, '0'));
  await pg.check('#aLunar'); await pg.click('#aAdd');
  ok((await pg.textContent('#anvList')).includes('어머니 생신'), '기념일 넣기');
  await pg.click('#setDlg .x');
  ok((await pg.textContent(`.cell[data-d="${td}"]`)).includes('어머니 생신'), '음력 기념일이 그날 칸에 나온다');

  //  반복 일정(매주) · 미리 알림(하루 전 — 23:59 일정이면 지금이 알림 범위 안)
  await pg.click(`.cell[data-d="${td}"] .add`);
  await pg.fill('#fTitle', '주간 생산 회의'); await pg.fill('#fTime', '23:59');
  await pg.selectOption('#fRepeat', 'weekly'); await pg.selectOption('#fRemind', '1440');
  await pg.click('#evSave'); await pg.waitForSelector('#evDlg', { state: 'hidden' });
  const nw = new Date(t); nw.setDate(nw.getDate() + 7);
  if (nw.getMonth() !== t.getMonth()) await pg.click('#next');
  ok((await pg.textContent(`.cell[data-d="${ymd(nw)}"]`)).includes('주간 생산 회의'), '매주 반복 일정이 다음 주에도 나온다');
  if (nw.getMonth() !== t.getMonth()) await pg.click('#prev');
  await pg.evaluate(() => { window.__cal.poll(); });
  await pg.waitForSelector('#alertDlg.on', { timeout: 30000 });
  ok((await pg.textContent('#aBig')).includes('곧 일정'), '⏰ 일정 미리 알림이 화면에 뜬다');
  await pg.click('#aLater');

  //  구글 → 달력 / 달력 → 구글(구독 주소)
  await pg.click('#setBtn'); await pg.click('#setTabs [data-tab=google]');
  await pg.fill('#gUrl', P + '/__google.ics'); await pg.click('#gSave');
  await pg.waitForFunction(() => /연결됨/.test(document.querySelector('#gState').textContent), null, { timeout: 8000 });
  const tm1 = new Date(t); tm1.setDate(tm1.getDate() + 1);
  await pg.click('#fMake');
  await pg.waitForFunction(() => document.querySelector('#fUrl').value.length > 10);
  const feed = await pg.inputValue('#fUrl');
  ok(feed.startsWith('https://work.example.com/api/cal/feed/'), '구글로 보낼 구독 주소를 만든다');
  const ics = await (await fetch(P + feed.replace('https://work.example.com', ''))).text();
  ok(ics.includes('BEGIN:VCALENDAR') && ics.includes('월간 안전 회의') && ics.includes('RRULE:FREQ=WEEKLY'), '구독 주소(.ics)에 회사 일정·반복이 들어 있다');
  await pg.click('#setDlg .x');
  if (tm1.getMonth() !== t.getMonth()) await pg.click('#next');
  ok((await pg.textContent(`.cell[data-d="${ymd(tm1)}"]`)).includes('10:00 G 치과 예약'), '구글 일정(시각 한국 시간)이 달력에 나온다');
  if (tm1.getMonth() !== t.getMonth()) await pg.click('#prev');

  //  🌫 투명도
  await pg.click('#setBtn');
  await pg.$eval('#sAlpha', (el) => { el.value = '70'; el.dispatchEvent(new Event('input')); });
  await sleep(300);
  ok(/창 명령: alpha 70/.test(gw.out), '투명도 70% → 창에 바로');
  await pg.click('#setDlg .x');

  //  ↔ 크기 고르기 · 끌기(바탕화면 모드인 척)
  await pg.evaluate(() => { const S = window.__cal.S; S.desktop = true; S.pinned = true; window.__cal.draw(); });
  ok(await pg.isVisible('#rz .se') && await pg.isVisible('#alphaBox'), '크기 손잡이·머리줄 투명도 막대가 보인다');
  await pg.dispatchEvent('#rz .se', 'mousedown', { button: 0 });
  await pg.click('#setBtn'); await pg.selectOption('#sPos', 'left'); await pg.click('[data-size="80"]');
  await sleep(300);
  ok(/창 명령: drag 17/.test(gw.out) && /창 명령: size 80,left/.test(gw.out), '가장자리 끌기·크기 고르기 → 창에 바로');
  await pg.click('#setDlg .x');
  await pg.$eval('#alphaTop', (el) => { el.value = '60'; el.dispatchEvent(new Event('input')); });
  await sleep(300);
  ok(/창 명령: alpha 60/.test(gw.out), '머리줄 투명도 막대 → 창에 바로');
  await pg.evaluate(() => { const S = window.__cal.S; S.desktop = false; S.pinned = false; window.__cal.draw(); });

  //  🎨 색 바꾸기 · 🚀 시작프로그램
  await pg.evaluate(() => { window.__cal.S.desktop = true; });
  await pg.click('#setBtn');
  await pg.click('[data-preset="바다"]');
  ok((await pg.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--head').trim())) === '#0b4f7c', '색 묶음(바다) → 머리줄 색이 바뀐다');
  await pg.$eval('[data-ck="bg"]', (el) => { el.value = '#ffeecc'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok((await pg.evaluate(() => getComputedStyle(document.body).backgroundColor)) === 'rgb(255, 238, 204)', '배경색을 직접 고른다');
  await sleep(500);
  ok(((await (await fetch(G + '/__cal/data')).json()).prefs.colors || {}).bg === '#ffeecc', '고른 색이 저장된다(동기화 대상)');
  await pg.click('#sColorReset');
  ok((await pg.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--head').trim())) === '#1b2a4a', '색 원래대로');
  await pg.uncheck('#sAuto'); await sleep(400);
  const ini = require('fs').readFileSync(BIN + '.ini', 'utf8');
  ok(/AUTOSTART=0/.test(ini), '시작프로그램 끄기 → 설정 파일에 AUTOSTART=0');
  await pg.check('#sAuto'); await sleep(400);
  ok(/AUTOSTART=1/.test(require('fs').readFileSync(BIN + '.ini', 'utf8')), '시작프로그램 켜기 → AUTOSTART=1');
  await pg.click('#setDlg .x');
  await pg.evaluate(() => { window.__cal.S.desktop = false; });

  //  🔍 찾기
  await pg.fill('#q', '안전'); await pg.press('#q', 'Enter');
  await pg.waitForSelector('#viewDlg.on');
  ok(/🔍.*[1-9]/.test(await pg.textContent('#vTitle')), '찾기: ' + (await pg.textContent('#vTitle')));
  await pg.click('#viewDlg .x'); await pg.press('#q', 'Escape');

  //  🖨 인쇄
  await pg.click('#printBtn'); await pg.click('#pGo');
  await pg.waitForFunction(() => window.__printed >= 1, null, { timeout: 5000 });
  ok((await pg.$eval('#printArea', (e) => e.textContent)).includes('월간 안전 회의'), '인쇄(달력 모양)');

  //  📆 이번 주부터 4주 보기
  await pg.click('#setBtn'); await pg.selectOption('#sView', 'weeks'); await pg.selectOption('#sWeeks', '4'); await pg.click('#sSave');
  ok((await pg.$$('.cell')).length === 28, '이번 주부터 4주 보기');
  await pg.click('#setBtn'); await pg.selectOption('#sView', 'month'); await pg.click('#sSave');

  //  ☁ 클라우드 동기화 — PC 에서 적은 것이 포털에 올라가고, 폰(포털 /deskcal)에서 고친 것이 PC 로
  await sleep(1800);
  await pg.evaluate(() => window.__cal.syncNow());
  const lgk = await fetch(P + '/login', { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'username=kim&password=1234' });
  const ckk = lgk.headers.get('set-cookie').split(';')[0];
  const md = await (await fetch(P + '/api/cal/mydata', { headers: { Cookie: ckk } })).json();
  ok(md.rev > 0 && md.data.notes[td] && md.data.notes[td].t === '거래처 전화하기' && md.data.todos.length === 1 && md.data.annivs.length === 1, '☁ 메모·할 일·기념일이 포털에 올라갔다 (판 ' + md.rev + ')');
  const ph2 = await br.newPage({ viewport: { width: 390, height: 844 } });
  ph2.on('pageerror', (e) => errs.push('폰: ' + e.message));
  await ph2.goto(P + '/deskcal');
  await ph2.fill('#u', 'kim'); await ph2.fill('#p', '1234'); await ph2.click('#go');
  await ph2.waitForURL(P + '/deskcal');
  await ph2.waitForSelector(`.cell[data-d="${td}"] .memo`, { state: "attached" });
  ok((await ph2.textContent(`.cell[data-d="${td}"] .memo`)) === '거래처 전화하기', '📱 폰(포털 /deskcal)에서 PC 메모가 보인다');
  await ph2.screenshot({ path: path.join(SHOT, '5-phone.png') });
  const d2 = ymd(new Date(t.getFullYear(), t.getMonth(), t.getDate() === 1 ? 2 : 1));
  await sleep(1500); for (let i = 0; i < 3 && await ph2.$('#alertDlg.on'); i++) { await ph2.click('#aLater'); await sleep(300); }
  await ph2.dblclick(`.cell[data-d="${d2}"] .dn`);
  await ph2.keyboard.type('폰에서 적음');
  await ph2.click('#ym');
  await sleep(2500);
  await pg.evaluate(() => window.__cal.syncNow());
  await pg.waitForSelector(`.cell[data-d="${d2}"] .memo`, { timeout: 5000 });
  ok((await pg.textContent(`.cell[data-d="${d2}"] .memo`)) === '폰에서 적음', '☁ 폰에서 적은 메모가 PC 달력에 들어온다');
  //  🕘 되돌리기
  await pg.click('#setBtn'); await pg.click('#setTabs [data-tab=sync]'); await pg.click('#histBtn');
  await pg.waitForSelector('[data-rb]');
  const revBefore = await pg.evaluate(() => window.__cal.DATA().rev);
  await pg.click('[data-rb]');
  await pg.waitForFunction((r) => window.__cal.DATA().rev > r, revBefore, { timeout: 5000 });
  ok(await pg.$(`.cell[data-d="${d2}"] .memo`) === null, '🕘 지난 판으로 되돌리면 폰 메모 전 상태로');
  await pg.click('#setDlg .x').catch(() => {});
  await pg.screenshot({ path: path.join(SHOT, '6-full.png') });

  //  껐다 켜도 로그인이 이어진다(세션을 보관)
  gw.kill(); await sleep(400);
  run(BIN, ['--url=' + P, '--port=' + GP], { LOCALAPPDATA: path.join(tmp, 'local') });
  await waitUp(G + '/__cal/ping');
  r = await fetch(G + '/api/apprdoc/list');
  ok(r.status === 200, '다시 켜도 로그인이 남아 있다');
  await fetch(G + '/__cal/logout', { method: 'POST' });
  r = await fetch(G + '/api/apprdoc/list');
  ok(r.status === 401, '로그아웃하면 다시 로그인해야 한다');
  ok(errs.length === 0, '화면 스크립트 오류 없음 ' + errs.join(' | '));
  await br.close();
  console.log(`\n✅ ${pass} · ❌ ${fail}   (화면: ${SHOT})`);
  procs.forEach((p) => p.kill());
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); procs.forEach((p) => { console.error(p.out.slice(-2000)); p.kill(); }); process.exit(1); });
