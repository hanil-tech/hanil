//  🔄 자동 업데이트 점검 — 판 정보(json) → 받기(크기·SHA-256) → 화면이 한가할 때 새 판 띄우기
//   cd deskcal && go build -o /tmp/hanil-cal . && cd test && node update-check.js
//   ⚠ 리눅스에서는 「새 판 exe」 대신 작은 셸 스크립트를 받아 띄운다(띄워졌는지 표시 파일로 본다)
'use strict';
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path'), crypto = require('crypto'), http = require('http');
const { chromium } = require('playwright');
const BIN = process.env.BIN || '/tmp/hanil-cal', RP = 3996, GP = 18852, G = 'http://127.0.0.1:' + GP;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hcal-up-')), MARK = path.join(tmp, 'updated.txt');
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

//  가짜 저장소(release/) — 새 판 9.9.9
const exe = Buffer.from('#!/bin/sh\necho "$@" > ' + MARK + '\n');
const sha = crypto.createHash('sha256').update(exe).digest('hex');
let manifest = { version: '9.9.9', file: 'hanil-cal-v9.9.9.exe', size: exe.length, sha256: sha, notes: '시험 판' };
const rel = http.createServer((q, s) => {
  if (q.url.startsWith('/hanil-cal.json')) return s.end(JSON.stringify(manifest));
  if (q.url === '/hanil-cal-v9.9.9.exe') return s.end(exe);
  //  달력이 붙을 포털(없어도 된다 — 연결 안 됨으로 뜬다)
  s.statusCode = 404; s.end();
}).listen(RP);

(async () => {
  const gw = spawn(BIN, ['--url=http://127.0.0.1:1', '--port=' + GP, '--updateurl=http://127.0.0.1:' + RP + '/'],
    { env: Object.assign({}, process.env, { LOCALAPPDATA: path.join(tmp, 'local'), HANILCAL_UPDATE_TEST: '1' }) });
  let out = ''; gw.stdout.on('data', (b) => { out += b; }); gw.stderr.on('data', (b) => { out += b; });
  for (let i = 0; i < 40; i++) { try { await fetch(G + '/__cal/ping'); break; } catch (e) { await sleep(150); } }
  //  받아 둘 때까지
  let st = {};
  for (let i = 0; i < 40 && !st.update; i++) { await sleep(250); st = await (await fetch(G + '/__cal/state')).json(); }
  ok(st.update === '9.9.9', '새 판 정보를 읽고 받아 두었다(크기·SHA-256 맞음)');
  const got = path.join(tmp, 'local', 'HanilCal', 'update', 'hanil-cal-v9.9.9.exe');
  ok(fs.existsSync(got) && fs.readFileSync(got).equals(exe), '받은 파일이 원본과 같다');
  fs.chmodSync(got, 0o755);

  const br = await chromium.launch();
  const pg = await br.newPage();
  await pg.goto(G + '/cal');
  //  메모를 적는 중이면 바꾸지 않는다
  await pg.waitForSelector('.cell');
  await pg.dblclick('.cell .dn');
  await pg.evaluate(() => window.__cal.poll());
  await sleep(6500);
  ok(!fs.existsSync(MARK) && await pg.$('textarea[data-memo]') !== null, '메모를 적는 중에는 바꾸지 않는다(안내가 떠 있었어도 5초 뒤 미룬다)');
  await pg.click('#ym');
  await pg.evaluate(() => window.__cal.poll());
  await pg.waitForFunction(() => /새 판 v9\.9\.9/.test(document.querySelector('#banner').textContent), null, { timeout: 5000 });
  ok(true, '한가해지면 「새 판으로 바꿉니다」 안내');
  for (let i = 0; i < 40 && !fs.existsSync(MARK); i++) await sleep(250);
  ok(fs.existsSync(MARK) && fs.readFileSync(MARK, 'utf8').includes('--update'), '5초 뒤 받은 새 판을 「--update」 로 띄웠다(새 판이 스스로 설치·재시작)');
  await br.close();

  //  검사값이 틀린 판은 받지 않는다
  gw.kill();
  manifest = Object.assign({}, manifest, { version: '9.9.10', sha256: '0'.repeat(64) });
  const gw2 = spawn(BIN, ['--url=http://127.0.0.1:1', '--port=' + GP, '--updateurl=http://127.0.0.1:' + RP + '/'],
    { env: Object.assign({}, process.env, { LOCALAPPDATA: path.join(tmp, 'local2'), HANILCAL_UPDATE_TEST: '1' }) });
  for (let i = 0; i < 40; i++) { try { await fetch(G + '/__cal/ping'); break; } catch (e) { await sleep(150); } }
  await sleep(2500);
  st = await (await fetch(G + '/__cal/state')).json();
  ok(!st.update, '검사값(SHA-256)이 틀린 파일은 받지 않는다');
  const log = fs.readFileSync(path.join(tmp, 'local2', 'HanilCal', 'hanil-cal.log'), 'utf8');
  ok(/받은 파일이 맞지 않습니다/.test(log), '기록에 까닭이 남는다');
  gw2.kill(); rel.close();
  console.log(`\n✅ ${pass} · ❌ ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
