//  태양광 조각 시험 — 가짜 VPP 사이트 + 가짜 포털 (express 는 fax/test/node_modules 것을 씀)
'use strict';
const path = require('path'), fs = require('fs'), os = require('os'), http = require('http');
const NM = path.join(__dirname, '..', '..', 'fax', 'test', 'node_modules');
const express = require(path.join(NM, 'express')), session = require(path.join(NM, 'express-session'));
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('  ✅ ' + m); } else { fail++; console.log('  ❌ ' + m); } };

//  가짜 VPP — 2026-11-14 실제 응답 모양 그대로
const S = { plantSts: 'normal', iotSts: 'on', kw: 20.522, down: false, logins: 0 };
function fakeVpp() {
  const a = express(); a.use(express.json());
  const auth = (req, res, next) => (/sid=good/.test(req.headers.cookie || '') ? next() : res.status(401).json({ ok: false }));
  a.post('/tws/any/login', (req, res) => {
    if (S.down) return res.status(503).send('down');
    S.logins++;
    if (req.body.identity !== 'hanil@vppc.com' || req.body.password !== 'pw!') return res.json({ ok: false, result: 'BAD_CREDENTIAL' });
    res.setHeader('Set-Cookie', 'sid=good; Path=/; HttpOnly'); res.json({ ok: true });
  });
  a.post('/tws/ctx/logout', (req, res) => res.json({ ok: true }));
  a.get('/tws/stats/overview', auth, (req, res) => res.json({ qty: 1, normalQty: S.plantSts === 'normal' ? 1 : 0, faultQty: S.plantSts === 'fault' ? 1 : 0, checkQty: 0, offlineQty: 0, nomActPower: S.kw, daiPowYields: 128.6, totPowYields: 41955.9, totalCapacity: 400, monthPowYields: 15628.299999999997, monthAvgDevTime: 2.8 }));
  a.get('/tws/stats/power/plants', auth, (req, res) => res.json([{ tid: 307014619339008, tpk: 'AABGrSTnLC', name: '한일특장1호', capacity: 400, addr: '전북특별자치도 완주군 봉동읍 첨단산업3로 24', blocked: false, nomActPower: S.kw, daiPowYields: 128.6, totPowYields: 41955.9, daiDevTime: 0.3, powerFactor: 0.999, iotSts: S.iotSts, derRtuSts: 'on', plantSts: S.plantSts, previousPower: 1066.6, previousDevTime: 2.7 }]));
  return new Promise((r) => { const s = a.listen(0, () => r(s)); });
}

(async () => {
  const vs = await fakeVpp();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'solar-'));
  const passFile = path.join(dir, 'pass'); fs.writeFileSync(passFile, 'hanil@vppc.com\npw!\n', { mode: 0o600 });
  const notes = [];
  const app = express();
  app.use(session({ secret: 't', resave: false, saveUninitialized: false }));
  app.get('/login/:who', (req, res) => { req.session.user = req.params.who === 'kim' ? { username: 'kim', role: 'admin' } : { username: 'lee' }; res.send('ok'); });
  const sol = require('../solar-route')(app, { base: 'http://127.0.0.1:' + vs.address().port + '/tws', passFile, dir: path.join(dir, 'data'), firstDelayMs: 999999, everyMin: 999, notify: async (m) => notes.push(m) });
  const ps = await new Promise((r) => { const s = app.listen(0, () => r(s)); });
  const P = 'http://127.0.0.1:' + ps.address().port;
  const login = async (w) => { const r = await fetch(P + '/login/' + w); return r.headers.get('set-cookie').split(';')[0]; };
  const kim = await login('kim'), lee = await login('lee');
  const get = (u, c, o) => fetch(P + u, Object.assign({ headers: c ? { Cookie: c } : {}, redirect: 'manual' }, o || {}));

  console.log('▶ 로그인 안 하면');
  ok((await get('/api/solar/latest')).status === 401, 'API 401');
  ok((await get('/solar')).status === 302, '화면은 로그인으로 보냄');

  console.log('▶ 처음 (아직 자료 없음)');
  let L = await (await get('/api/solar/latest', lee)).json();
  ok(L.at === null && L.admin === false, '빈 자료 · 직원은 admin=false');
  ok((await get('/api/solar/refresh', lee, { method: 'POST' })).status === 403, '직원은 지금 가져오기 못 함');

  console.log('▶ 가져오기');
  L = await (await get('/api/solar/refresh', kim, { method: 'POST' })).json();
  ok(L.overview && L.overview.nowKw === 20.522 && L.overview.monthKwh === 15628.3, '요약: 지금 20.522kW · 이번 달 15628.3kWh (소수 정리)');
  ok(L.plants.length === 1 && L.plants[0].name === '한일특장1호' && L.plants[0].id === '307014619339008', '발전소 1곳 (큰 번호 그대로)');
  ok(L.plants[0].yesterdayKwh === 1066.6 && L.plants[0].todayHours === 0.3, '어제 1066.6kWh · 오늘 발전시간 0.3h');
  ok(L.alerts.length === 0 && notes.length === 0, '정상 — 알림 없음');
  const T = await (await get('/api/solar/today', lee)).json();
  ok(T.rows.length === 1 && T.rows[0].kw === 20.522, '오늘 기록 1줄');
  const D = await (await get('/api/solar/daily?days=3', lee)).json();
  ok(D.days.length === 3 && D.days[2].kwh === 128.6 && D.days[1].kwh === 1066.6 && D.days[1].hours === 2.7, '날짜별: 오늘 128.6 · 어제 1066.6 (2.7h)');

  console.log('▶ 고장 → 복귀');
  S.plantSts = 'fault'; S.iotSts = 'off';
  L = await sol.collect();
  ok(L.alerts.length === 1 && /고장/.test(L.alerts[0]) && /IoT 통신 끊김/.test(L.alerts[0]), '경고: ' + L.alerts[0]);
  ok(notes.length === 1 && /⚠️/.test(notes[0]), '알림 1번');
  await sol.collect();
  ok(notes.length === 1, '같은 고장이면 다시 안 알림');
  S.plantSts = 'normal'; S.iotSts = 'on';
  await sol.collect();
  ok(notes.length === 2 && /정상으로/.test(notes[1]), '복귀 알림');

  console.log('▶ 사이트가 죽으면');
  S.down = true;
  for (let i = 0; i < 4; i++) await sol.collect();
  L = await (await get('/api/solar/latest', lee)).json();
  ok(L.error && L.overview && L.overview.nowKw === 20.522, '마지막 값은 그대로 + 오류 표시');
  ok(notes.filter((n) => /3번 연속/.test(n)).length === 1, '3번째 실패에 한 번만 알림');
  S.down = false; S.kw = 50;
  L = await sol.collect();
  ok(!L.error && L.overview.nowKw === 50 && /다시 연결/.test(notes[notes.length - 1]), '다시 연결 알림 · 새 값');

  console.log('▶ 비밀번호 틀림');
  fs.writeFileSync(passFile, 'hanil@vppc.com\nwrong\n');
  L = await sol.collect();
  ok(/BAD_CREDENTIAL/.test(L.error || ''), '이유가 보임: ' + L.error);

  console.log('▶ 다시 켜도 이어짐');
  sol.stop();
  const app2 = express(); app2.use(session({ secret: 't', resave: false, saveUninitialized: false }));
  const sol2 = require('../solar-route')(app2, { passFile, dir: path.join(dir, 'data'), firstDelayMs: 999999 });
  ok(sol2.latest() && sol2.latest().overview.nowKw === 50, '저장한 마지막 값을 읽음');
  sol2.stop();

  console.log('▶ 화면');
  const h = await (await get('/solar', lee)).text();
  ok(/태양광 발전/.test(h) && /api\/solar\/latest/.test(h), '화면 내려줌');

  console.log('▶ server.js 패치');
  const sv = path.join(dir, 'server.js');
  fs.writeFileSync(sv, "const app = require('express')();\nfunction nopsPush(){}\n\n  require('./faxbox')(app, { x: 1 });\napp.listen(1);\n");
  const { execFileSync } = require('child_process');
  const run = (...a) => execFileSync(process.execPath, [path.join(__dirname, '..', 'patch-portal-solar.js'), sv, ...a], { encoding: 'utf8' });
  run('--notify', 'kim');
  let s = fs.readFileSync(sv, 'utf8');
  ok(/  try \{ require\("[^"]*\/solar-route\.js"\)[^\n]*nopsPush\("kim"[^\n]*\n  require\('\.\/faxbox'\)/.test(s), 'faxbox 줄 바로 앞에 같은 들여쓰기로 (조각은 포털 밖 절대경로)');
  execFileSync(process.execPath, ['--check', sv]); ok(true, 'node --check 통과');
  ok(/이미 들어/.test(run()), '두 번 넣지 않음');
  run('--undo');
  ok(!fs.readFileSync(sv, 'utf8').includes('solar-route'), '--undo 로 빠짐');
  //  업그레이드로 server.js 가 새로 깔린 상황: 다시 넣어도 그대로 한 번만
  fs.writeFileSync(sv, "const app = require('express')();\n  require('./faxbox')(app, { v: 2 });\n");
  run(); run();
  ok((fs.readFileSync(sv, 'utf8').match(/solar-route/g) || []).length === 1, '새 server.js 에 다시 한 번만 들어감');
  //  넣으면 문법이 깨지는 모양이면 원래대로
  const bad = "const app = require('express')();\nconst x =\n  require('./faxbox')(app);\n";
  fs.writeFileSync(sv, bad);
  let threw = false; try { run(); } catch (e) { threw = /원래대로/.test(String(e.stdout)); }
  ok(threw && fs.readFileSync(sv, 'utf8') === bad, '문법이 깨지면 원래대로 돌려놓음');

  console.log('\n' + (fail ? '❌' : '✅') + ' ' + pass + '개 통과, ' + fail + '개 실패');
  vs.close(); ps.close(); fs.rmSync(dir, { recursive: true, force: true });
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
