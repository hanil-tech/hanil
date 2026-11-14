//  팩스 보내기 점검 — 가짜 포털 + 가짜 CimFAX 장비 + 진짜 Ghostscript
//   cd fax/test && npm install && node send-check.js      (Ghostscript 필요: gs 또는 GHOSTSCRIPT=경로)
'use strict';
const fs = require('fs'), path = require('path'), os = require('os'), { execFileSync } = require('child_process');
const startPortal = require('./fake-portal'), startDevice = require('./fake-cimfax');
const cim = require('../portal/cimfax-client');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };
const wait = async (fn, ms) => { const end = Date.now() + (ms || 20000); while (Date.now() < end) { const v = await fn(); if (v) return v; await new Promise((r) => setTimeout(r, 150)); } return null; };

async function login(port, user) {
  const r = await fetch(`http://localhost:${port}/login`, { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `username=${user}&password=1234` });
  const c = (r.headers.get('set-cookie') || '').split(';')[0];
  return (url, opt) => fetch(`http://localhost:${port}${url}`, Object.assign({ redirect: 'manual' }, opt, { headers: Object.assign({ Cookie: c }, (opt || {}).headers) }));
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'faxsend-'));
  //  2쪽짜리 PDF
  fs.writeFileSync(path.join(tmp, 'a.ps'), '%!PS\n/Helvetica findfont 40 scalefont setfont 72 700 moveto (HANIL page 1) show showpage 72 700 moveto (page 2) show showpage\n');
  execFileSync(process.env.GHOSTSCRIPT || 'gs', ['-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite', '-sOutputFile=' + path.join(tmp, 'a.pdf'), path.join(tmp, 'a.ps')]);
  const pdf = fs.readFileSync(path.join(tmp, 'a.pdf'));

  //  0. 로그인 계산 — 표준 MD5 와 seed 0 이 같아야 한다
  ok(cim.md5Seeded(Buffer.from('hanil'), 0) === require('crypto').createHash('md5').update('hanil').digest('hex'), 'FaxGo MD5Code(seed 0) = 표준 MD5');
  ok(cim.cal128MD5('pw1234').length === 128 && cim.cal128MD5('pw1234').slice(0, 32) !== cim.cal128MD5('pw1234').slice(32, 64), 'cal128MD5: 서로 다른 MD5 4개 이어 붙임');

  const dev = startDevice({ portBase: 33001 });
  const device = { host: '127.0.0.1', user: 'hanil', password: 'pw1234', portBase: 33001, timeoutMs: 5000, ghostscript: process.env.GHOSTSCRIPT };
  const { srv, fax, port } = await startPortal({ inbox: path.join(tmp, 'in'), store: path.join(tmp, 'st'), port: 0, ctx: { device, sendBy: (u) => u.id !== 'nobody' } });
  fax.stop();
  const lee = await login(port, 'lee'), kim = await login(port, 'kim');

  //  1. 설정·권한
  let j = await (await lee('/api/fax/sendinfo')).json();
  ok(j.enabled && j.canSend && j.maxMB === 20, '보내기 켜짐');
  j = await (await kim('/api/fax/device/check')).json();
  ok(j.ok && j.device.serverName === 'HANIL-FAX' && j.device.ext === '801', '관리자 장비 점검: 로그인 성공 · 장비 이름 · 내선');
  let r = await lee('/api/fax/device/check');
  ok(r.status === 403, '장비 점검은 관리자만');
  r = await lee('/api/fax/send?to=', { method: 'POST', body: pdf });
  ok(r.status === 400, '번호 없으면 400');
  r = await lee('/api/fax/send?to=0212345678', { method: 'POST', body: Buffer.from('hello world') });
  ok(r.status === 400, 'PDF 가 아니면 400');

  //  2. 보내기 — 두 곳
  r = await lee('/api/fax/send?to=' + encodeURIComponent('02-1234-5678, 0311112222') + '&name=' + encodeURIComponent('대한상사') + '&file=' + encodeURIComponent('견적서.pdf'), { method: 'POST', body: pdf });
  j = await r.json();
  ok(j.ok && j.items.length === 2 && j.items[0].to === '02-1234-5678' && j.items[0].state === 'queued', '두 곳으로 접수 (번호마다 한 건)');
  const done = await wait(async () => { const x = await (await lee('/api/fax/sent')).json(); return x.items.every((s) => s.state === 'accepted') && x; });
  ok(!!done, '둘 다 장비 접수(accepted)');
  ok(dev.got.faxes.length === 2, '장비가 팩스 2건을 받음');
  const f = dev.got.faxes[0];
  const phone = f.header.subarray(96, 160).toString('utf16le').replace(/\0.*$/, '');
  ok(f.headSize === 1024 && f.bufSize === 1200 && f.fileLen === f.header.length + f.tiff.length, 'SENDFAX: HEADERSIZE 1024(장비 구조체) · BUFSIZE 1200 · FILELEN = 머리+TIFF');
  ok(f.header.readInt32LE(916) === 1 && !dev.got.rejected, '머리 1024 배치: 화질(+916) · 장비가 거부하지 않음');
  ok(phone === '02-1234-5678' && f.header.readInt32LE(160) === 2 && f.header.readInt32LE(24) === 5 && f.header.readInt32LE(28) === 2, '머리: 번호 · 쪽수 2 · 상태 5 · 우선순위 2');
  ok(f.header.readUInt16LE(176) === new Date().getUTCFullYear(), '머리: 보낸 시각(UTC)');
  const t = cim.tiffPages(f.tiff);
  ok(t.pages === 2 && t.width === 1728, '본문: 팩스 TIFF 2쪽 · 폭 1728');
  ok(f.user === 'hanil' && dev.got.logins.every((l) => l.ok), '장비 로그인 해시가 맞음');
  ok(done.items.some((s) => s.task_id === 101) && done.items.some((s) => s.task_id === 102), '작업번호를 받아 둠');
  const one = done.items.find((s) => s.task_id === 101);
  ok(one.pages === 2 && one.by === '이사원' && one.name === '대한상사' && one.history.some((h) => /작업번호 101/.test(h.action)), '기록: 쪽수 · 보낸 사람 · 받는 곳 · 작업번호');

  //  3. 상태 묻기
  await fax.send.poll();
  j = await (await lee('/api/fax/sent')).json();
  const s1 = j.items.find((s) => s.task_id === 101);
  ok(s1.device && s1.device.pageSent === 2 && s1.device.dialDone === 1 && s1.device.status === 0, '장비 상태: 보낸 쪽 2/2 · 다이얼 1회 · 상태코드');

  //  4. 보낸 원본 보기, 다른 사람 것은 안 보임
  r = await lee('/api/fax/sent/' + s1.id + '/file');
  ok(r.status === 200 && Buffer.from(await r.arrayBuffer()).equals(pdf), '보낸 원본 PDF 내려받기');
  const other = await login(port, 'kim');
  j = await (await other('/api/fax/sent')).json();
  ok(j.items.length === 2, '관리자는 모두 봄');

  //  4-2. 장비가 1088(FaxGo 배치)만 받는 경우 → 거부되면 1088 로 다시
  const dev2 = startDevice({ portBase: 35001, headerSizes: [1088] });
  const r2 = await cim.sendFax(Object.assign({}, device, { portBase: 35001 }), { phone: '0212345678', pages: 2, tiff: f.tiff });
  ok(r2.headerSize === 1088 && dev2.got.rejected === 1 && dev2.got.faxes.length === 1 && dev2.got.faxes[0].header.readInt32LE(980) === 1, '머리 크기를 거부하면 다른 배치(1088)로 한 번 더 → 접수');
  dev2.close();
  const dev3 = startDevice({ portBase: 36001, headerSizes: [999] });
  let e3 = '';
  try { await cim.sendFax(Object.assign({}, device, { portBase: 36001 }), { phone: '0212345678', pages: 2, tiff: f.tiff }); } catch (e) { e3 = e.message; }
  ok(/Header size is invalidate/.test(e3) && dev3.got.rejected === 2, '둘 다 거부하면 장비 오류 문구 그대로 실패');
  dev3.close();

  //  4-3. 보내기 취소 — 장비 접수 뒤: 장비에 멈춤(SEND_FAX_PAUSE → PAUSE_OK)
  {
    const lst = await (await lee('/api/fax/sent')).json();
    const acc = lst.items.find((x) => x.task_id === 102);
    r = await lee('/api/fax/sent/' + acc.id + '/cancel', { method: 'POST' });
    j = await r.json();
    ok(j.ok && j.item.state === 'canceled' && (dev.got.paused || []).includes(102), '보내기 취소 → 장비 작업 102 멈춤(PAUSE_OK) · 「취소됨」');
    dev.got.faxes.find((x) => x.taskId === 101).done = true;
    const acc1 = lst.items.find((x) => x.task_id === 101);
    r = await lee('/api/fax/sent/' + acc1.id + '/cancel', { method: 'POST' });
    ok(r.status === 409 && /이미 다 보냈/.test((await r.json()).error), '이미 다 보낸 팩스는 장비가 거절 → 이유 표시');
    const pr = await cim.pauseSend(device, 102);
    ok(pr.ok, '점검 도구용 pauseSend 도 PAUSE_OK');
    const rr = await cim.retrySend(device, 102, 3);
    ok(rr.ok && (dev.got.retried || []).includes(102), '다시 보내기(SEND_FAX_RETRY)');
  }

  //  4-4. 장비로 넘기기 전 취소 — 장비가 꺼져 있어 대기 중일 때
  {
    const off = await startPortal({ inbox: path.join(tmp, 'in'), store: path.join(tmp, 'st5'), port: 0, ctx: { device: Object.assign({}, device, { portBase: 39901, timeoutMs: 1000 }) } });
    off.fax.stop();
    const o = await login(off.port, 'lee');
    j = await (await o('/api/fax/send?to=0212345678', { method: 'POST', body: pdf })).json();
    const qid = j.items[0].id;
    const queued = await wait(async () => { const x = await (await o('/api/fax/sent')).json(); return x.items[0].state === 'queued' && x.items[0].tries >= 1 && x.items[0]; }, 30000);
    r = await o('/api/fax/sent/' + qid + '/cancel', { method: 'POST' });
    j = await r.json();
    ok(queued && j.ok && j.item.state === 'canceled' && !j.item.task_id, '장비로 넘기기 전 취소 → 바로 「취소됨」');
    await new Promise((q) => setTimeout(q, 300));
    j = await (await o('/api/fax/sent')).json();
    ok(j.items[0].state === 'canceled', '취소한 것은 일꾼이 다시 보내지 않음');
    r = await o('/api/fax/sent/' + qid + '/retry', { method: 'POST' });
    ok(r.status === 200, '넘기기 전 취소한 것은 「다시 보내기」 가능');
    off.srv.closeAllConnections(); off.srv.close();
  }

  //  5. 비밀번호가 틀리면 실패 + 다시 보내기
  fax.stop(); srv.closeAllConnections(); srv.close();
  const bad = await startPortal({ inbox: path.join(tmp, 'in'), store: path.join(tmp, 'st2'), port: 0, ctx: { device: Object.assign({}, device, { password: 'wrong' }) } });
  bad.fax.stop();
  const b = await login(bad.port, 'lee');
  j = await (await b('/api/fax/send?to=0212345678', { method: 'POST', body: pdf })).json();
  const failed = await wait(async () => { const x = await (await b('/api/fax/sent')).json(); return x.items[0].state === 'failed' && x.items[0]; });
  ok(failed && /비밀번호/.test(failed.error), '장비 비밀번호가 틀리면 「실패」 + 이유');
  r = await b('/api/fax/sent/' + failed.id + '/retry', { method: 'POST' });
  ok(r.status === 200, '실패한 것 다시 보내기 접수');
  bad.srv.closeAllConnections(); bad.srv.close();

  //  6. 시험 모드 — 장비로 안 보냄
  const before = dev.got.faxes.length;
  const dry = await startPortal({ inbox: path.join(tmp, 'in'), store: path.join(tmp, 'st3'), port: 0, ctx: { device: Object.assign({}, device, { dryRun: true }) } });
  dry.fax.stop();
  const d = await login(dry.port, 'lee');
  await d('/api/fax/send?to=0212345678', { method: 'POST', body: pdf });
  const dr = await wait(async () => { const x = await (await d('/api/fax/sent')).json(); return x.items[0].state === 'accepted' && x.items[0]; });
  ok(dr && dr.pages === 2 && dev.got.faxes.length === before, '시험 모드: 변환까지만 하고 장비로는 안 보냄');
  dry.srv.closeAllConnections(); dry.srv.close();

  //  7. 장비 설정이 없으면
  const none = await startPortal({ inbox: path.join(tmp, 'in'), store: path.join(tmp, 'st4'), port: 0 });
  none.fax.stop();
  const n = await login(none.port, 'lee');
  j = await (await n('/api/fax/sendinfo')).json();
  r = await n('/api/fax/send?to=0212345678', { method: 'POST', body: pdf });
  ok(!j.enabled && r.status === 503, '장비 설정이 없으면 보내기 꺼짐');
  none.srv.close();

  dev.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`\n✅ ${pass} · ❌ ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
