//  🔄 라벨 발행기 자동 업데이트 점검 — 판 정보 읽기 → 받기(크기·SHA-256) → 「쉴 때」 POST /__label/update → 새 판 띄우기
//   cd label && go build -o /tmp/hanil-label . && node test-update.js
//   ⚠ 리눅스에서는 「새 판 exe」 대신 작은 셸 스크립트를 받아 띄운다(띄워졌는지 표시 파일로 본다)
'use strict';
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path'), crypto = require('crypto'), http = require('http');
const BIN = process.env.BIN || '/tmp/hanil-label', RP = 3995, GP = 18839, G = 'http://127.0.0.1:' + GP;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hlab-up-')), MARK = path.join(tmp, 'updated.txt');
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const exe = Buffer.from('#!/bin/sh\necho "$@" > ' + MARK + '\n');
const manifest = { version: '9.9.9', file: 'hanil-label-v9.9.9.exe', size: exe.length, sha256: crypto.createHash('sha256').update(exe).digest('hex'), notes: '시험' };
const rel = http.createServer((q, s) => {
  if (q.url.startsWith('/hanil-label.json')) return s.end(JSON.stringify(manifest));
  if (q.url === '/hanil-label-v9.9.9.exe') return s.end(exe);
  s.statusCode = 404; s.end();
}).listen(RP);
(async () => {
  const gw = spawn(BIN, ['--url=http://127.0.0.1:1', '--port=' + GP, '--browser=/bin/true', '--updateurl=http://127.0.0.1:' + RP + '/'],
    { env: Object.assign({}, process.env, { LOCALAPPDATA: path.join(tmp, 'local'), HANILLABEL_UPDATE_TEST: '1' }) });
  let v = '';
  for (let i = 0; i < 60 && v !== '9.9.9'; i++) { await sleep(250); try { v = await (await fetch(G + '/__label/updstate')).text(); } catch (e) {} }
  ok(v === '9.9.9', '새 판을 받아 두었다(크기·SHA-256 맞음)');
  const got = path.join(tmp, 'local', 'HanilLabel', 'update', 'hanil-label-v9.9.9.exe');
  fs.chmodSync(got, 0o755);
  ok(!fs.existsSync(MARK), '받기만 하고 바로 바꾸지는 않는다(키오스크가 쉴 때까지)');
  const r = await fetch(G + '/__label/update', { method: 'POST' });
  for (let i = 0; i < 20 && !fs.existsSync(MARK); i++) await sleep(200);
  ok(r.status === 200 && fs.existsSync(MARK) && fs.readFileSync(MARK, 'utf8').includes('--update'), '쉴 때 부르면 새 판을 「--update」 로 띄운다');
  gw.kill(); rel.close();
  console.log(`\n✅ ${pass} · ❌ ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
