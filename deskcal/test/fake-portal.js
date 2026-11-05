//  시험용 가짜 포털 — 로그인(폼) · 결재함 · 문서 인쇄 화면 · 오늘 할 일 · 쪽지함 + 진짜 calendar-route.js
//   PORT=3998 STORE=/tmp/x node fake-portal.js
//   /__test/wait  (POST) — 내 결재 차례 문서를 하나 더 넣는다(알림 시험)
'use strict';
const express = require('express'), session = require('express-session'), path = require('path');
const app = express();
app.use(session({ secret: 'check', resave: false, saveUninitialized: false }));
const USERS = { kim: { username: 'kim', name: '김부장', role: 'admin' }, lee: { username: 'lee', name: '이사원' } };
const today = new Date(), d = (n) => { const t = new Date(today); t.setDate(t.getDate() + n); return t.toISOString().slice(0, 10) + ' 09:30:00'; };
let waiting = [{ id: 101, title: '11월 자재 구매 품의', drafter_name: '박대리', created_at: d(-1), state: 'ing', kind_label: '구매품의' },
  { id: 201, title: '26.11.05 업무일지(관리부/임은혜)', drafter_name: '임은혜', created_at: d(0), state: 'ing' }];
const steps = {
  101: [{ role: '작성', name: '박대리', state: 'ok' }, { role: '결재', name: '김부장', state: '' }],
  201: [{ role: '작성', name: '임은혜', state: 'ok' }, { role: '검토', name: '이부장', state: '' }, { role: '결재', name: '김부장', state: '' }],
};
const myTurn = () => waiting.filter((x) => { const c = (steps[x.id] || []).find((s) => s.role !== '작성' && s.state !== 'ok'); return c && c.name === '김부장'; }).length;
const mine = [{ id: 90, title: '출장 신청 (창원)', drafter_name: '김부장', created_at: d(-3), state: 'ing' }];
const done = [{ id: 80, title: '10월 안전점검 결과', drafter_name: '김부장', created_at: d(-6), state: 'done' }];
let nextId = 102;

app.get('/', (req, res) => {
  if (req.session.user) return res.send('<h1>포털 첫 화면</h1>');
  res.send(`<!doctype html><meta charset=utf-8><body><h1>한일 포털 로그인</h1>${req.query.err ? '<p id=err>' + req.query.err + '</p>' : ''}
<form method="post" action="/login">${req.query.next ? '<input type=hidden name=next value="' + req.query.next + '">' : ''}<input name=username id=u><input name=password id=p type=password><button id=go>로그인</button></form></body>`);
});
app.post('/login', express.urlencoded({ extended: false }), (req, res) => {
  const u = USERS[req.body.username];
  if (!u || req.body.password !== '1234') return res.redirect('/?err=' + encodeURIComponent('아이디 또는 비밀번호가 틀립니다'));
  req.session.user = u;
  res.redirect(req.body.next || '/');
});
app.get('/logout', (req, res) => { req.session.destroy(() => res.redirect('/')); });
app.get('/api/version', (req, res) => res.json({ version: '15.80.0' }));
const need = (req, res, next) => (req.session.user ? next() : res.status(401).json({ ok: false, error: 'login' }));
app.get('/api/apprdoc/list', need, (req, res) => res.json({ waiting, mine, done }));
app.get('/api/appr/:id/print', (req, res) => {
  if (!req.session.user) return res.redirect('/');
  res.set('X-Frame-Options', 'DENY').send(`<!doctype html><meta charset=utf-8><body style="font-family:sans-serif;padding:30px"><h2>결재 문서 #${req.params.id}</h2><table border=1 cellpadding=8><tr><td>기안</td><td>검토</td><td>승인</td></tr><tr><td>박대리</td><td>✓</td><td></td></tr></table><p>종이 화면입니다.</p></body>`);
});
app.post('/api/appr/:id/act', need, (req, res) => res.json({ ok: true }));
//  ⚠ 진짜 포털처럼 이름 없이 열쇠만 준다
//  ⚠ 진짜 포털처럼 결재 수(appr)는 없다 — 결재 차례는 문서의 my_turn 으로만 안다
app.get('/api/my-today', need, (req, res) => res.json({ items: [{ key: 'po_overdue', n: 5 }, { key: 'mailbox', n: 269 }, { key: 'recon', n: 575 }] }));
app.get('/api/appr/:id(\\d+)', need, (req, res) => {
  const x = waiting.concat(mine, done).find((y) => y.id === +req.params.id);
  if (!x) return res.status(404).json({ ok: false });
  const c = (steps[x.id] || []).find((s) => s.role !== '작성' && s.state !== 'ok');
  res.json({ ok: true, doc: x, steps: steps[x.id] || [], body: '', my_turn: !!(c && c.name === req.session.user.name) });
});
//  🗓 포털에 원래 있는 달력 — 화면(/schedule)이 /api/schedule/list 를 부른다
app.get('/schedule', need, (req, res) => res.send('<html><body><div id=cal></div><script>fetch("/api/schedule/list?ym=" + ym).then(r=>r.json())</script></body></html>'));
app.get('/m', need, (req, res) => res.send('<html><body><a href="/schedule">일정</a><a href="/approval">결재</a></body></html>'));
app.get('/api/schedule/list', need, (req, res) => res.json({ ok: true, rows: [
  { seq: 7, subject: '협력사 방문 (대한정밀)', sdate: d(2).slice(0, 10), edate: d(2).slice(0, 10), stime: '15:00', writer_name: '총무팀' },
  { seq: 8, subject: '정기 설비 점검', sdate: d(3).slice(0, 10) + ' 00:00:00', edate: d(5).slice(0, 10) + ' 00:00:00', writer_name: '생산팀' }] }));
app.get('/api/deskmsg', need, (req, res) => res.json({ ok: true, n: 1, items: [
  { kind: 'dm', key: 'dm:7:55', title: '박대리', text: '견적서 보내드렸습니다', cid: 7 },
  { kind: 'notice', key: 'n:3', title: '공지', text: '11/14 소방 훈련', url: '/notice/3' }] }));
app.get('/admin/secret', need, (req, res) => res.send('관리자 화면'));
app.post('/__test/wait', (req, res) => {
  waiting = waiting.concat([{ id: nextId, title: '긴급 외주 가공 품의 #' + nextId, drafter_name: '최과장', created_at: d(0), state: 'ing' }]);
  steps[nextId] = [{ role: '작성', name: '최과장', state: 'ok' }, { role: '결재', name: '김부장', state: '' }];
  nextId++;
  res.json({ ok: true, n: waiting.length });
});
//  가짜 구글 캘린더 비공개 주소(.ics)
app.get('/__google.ics', (req, res) => {
  const t = new Date(), ds = (n) => { const x = new Date(t); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10).replace(/-/g, ''); };
  res.type('text/calendar').send(['BEGIN:VCALENDAR', 'BEGIN:VEVENT', 'UID:g1', 'SUMMARY:치과 예약', 'DTSTART:' + ds(1) + 'T010000Z', 'DTEND:' + ds(1) + 'T020000Z', 'END:VEVENT',
    'BEGIN:VEVENT', 'UID:g2', 'SUMMARY:헬스장', 'DTSTART;VALUE=DATE:' + ds(0), 'DTEND;VALUE=DATE:' + ds(1), 'RRULE:FREQ=WEEKLY;COUNT=4', 'END:VEVENT', 'END:VCALENDAR'].join('\r\n'));
});
//  가짜 공공데이터포털(특일 정보) — 2026 에 「임시공휴일」 하나를 더 넣어 둔다(포털에서 받아 온 것인지 보려고)
app.get('/__datago', (req, res) => {
  if (req.query.serviceKey !== 'TESTKEY') return res.json({ response: { header: { resultCode: '30', resultMsg: 'SERVICE KEY IS NOT REGISTERED' } } });
  const y = req.query.solYear;
  const item = y === '2026' ? [{ dateName: '1월1일', isHoliday: 'Y', locdate: 20260101 }, { dateName: '임시공휴일', isHoliday: 'Y', locdate: 20261106 }, { dateName: '설날', isHoliday: 'Y', locdate: 20260217 }] : [];
  res.json({ response: { header: { resultCode: '00' }, body: { items: item.length ? { item } : '', totalCount: item.length } } });
});
require(path.join(__dirname, '..', 'portal', 'calendar-route.js'))(app, { dir: process.env.STORE, holidayKey: 'TESTKEY', holidayURL: 'http://127.0.0.1:' + (+process.env.PORT || 3998) + '/__datago',
  page: path.join(__dirname, '..', 'page.html'), icsAny: true, publicURL: 'https://work.example.com' });
app.listen(+process.env.PORT || 3998, () => console.log('fake portal ready'));
