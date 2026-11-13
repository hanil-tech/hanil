//  한일 팩스(독립 프로그램) 점검 — 진짜 hanil-fax.js + 가짜 CimFAX 장비 + 진짜 Ghostscript
//   cd fax/test && node app-check.js
'use strict';
const fs = require('fs'), path = require('path'), os = require('os'), crypto = require('crypto'), { execFileSync } = require('child_process');
const startDevice = require('./fake-cimfax');
const hf = require('../app/hanil-fax');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };
const user = (name, pw, admin) => { const salt = crypto.randomBytes(8).toString('hex'); return { name, admin, salt, hash: hf.hashPw(pw, salt) }; };
const utc = (ms) => new Date(ms).toISOString().slice(0, 19).replace('T', ' ');

async function login(port, id, pw) {
  const r = await fetch(`http://localhost:${port}/login`, { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `username=${id}&password=${encodeURIComponent(pw)}&next=/fax` });
  const c = (r.headers.get('set-cookie') || '').split(';')[0];
  const get = (url, opt) => fetch(`http://localhost:${port}${url}`, Object.assign({ redirect: 'manual' }, opt, { headers: Object.assign({ Cookie: c }, (opt || {}).headers) }));
  get.cookie = c; get.status = r.status; get.location = r.headers.get('location');
  return get;
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hanilfax-'));
  const gs = process.env.GHOSTSCRIPT || 'gs';
  const mk = (name, text, pages) => {
    const ps = path.join(tmp, name + '.ps');
    fs.writeFileSync(ps, '%!PS\n/Helvetica findfont 40 scalefont setfont\n' + Array.from({ length: pages }, (_, i) => `72 700 moveto (${text} p${i + 1}) show showpage`).join('\n') + '\n');
    execFileSync(gs, ['-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=tiffg32d', '-r204x196', '-sPAPERSIZE=a4', '-sOutputFile=' + path.join(tmp, name + '.tif'), ps]);
    return fs.readFileSync(path.join(tmp, name + '.tif'));
  };
  const now = Date.now();
  const inbox = [
    { taskId: 7, time: utc(now - 40 * 86400000), cid: '0211110000', file: '0000000A', tiff: mk('old', 'OLD', 1) },
    { taskId: 8, time: utc(now - 3600000), cid: '0551234567', file: '1A2B3C4D', receiver: 'public', tiff: mk('a', 'QUOTE', 2) },
    { taskId: 9, time: utc(now - 600000), cid: '0313510938', file: '1A2B3C4E', tiff: mk('b', 'ORDER', 1) },
  ];
  const dev = startDevice({ portBase: 37001, inbox });
  const users = { kim: user('김부장', 'kimpw123', true), lee: user('이사원', 'leepw123', false) };
  const cfg = { device: { host: '127.0.0.1', user: 'hanil', password: 'pw1234', portBase: 37001, timeoutMs: 5000 }, receive: 'device', users, dir: path.join(tmp, 'store') };
  let app = await hf.start({ port: 0, quiet: true, cfg });
  app.fax.stop();
  const P = app.port;

  //  1. 로그인
  let r = await fetch(`http://localhost:${P}/`);
  ok(r.status === 200 && /한일 팩스/.test(await r.text()), '첫 화면 = 로그인');
  r = await fetch(`http://localhost:${P}/fax`, { redirect: 'manual' });
  ok(r.status === 302 && /next=%2Ffax/.test(r.headers.get('location')), '로그인 없이 /fax → 로그인으로');
  r = await fetch(`http://localhost:${P}/api/fax`);
  ok(r.status === 401, '로그인 없이 API → 401');
  const bad = await login(P, 'kim', 'wrong');
  ok(bad.status === 200 && !bad.cookie.startsWith('hfsid='), '틀린 비밀번호 → 로그인 안 됨');
  const kim = await login(P, 'kim', 'kimpw123');
  ok(kim.status === 302 && kim.location === '/fax' && kim.cookie.startsWith('hfsid='), '맞는 비밀번호 → /fax 로');
  let j = await (await kim('/api/fax/me')).json();
  ok(j.ok && j.admin && j.standalone && j.name === '김부장', '내 정보: 관리자 · 독립 프로그램');
  r = await kim('/fax');
  ok(r.status === 200 && /받기/.test(await r.text()), '/fax 화면');

  //  2. 장비에서 받기
  await app.fax.pollDevice();
  j = await (await kim('/api/fax?status=all')).json();
  ok(j.items.length === 2, '받은 팩스 2건 (40일 전 것은 건너뜀) → ' + j.items.length);
  ok(dev.got.downloads === 2, '장비에서 파일 2개 내려받음');
  const fb = j.items.find((f) => f.from === '0313510938'), fa = j.items.find((f) => f.from === '0551234567');
  ok(fb && fa && fa.ext === 'pdf' && fa.pages === 2 && fa.to === 'public', 'PDF 로 바꿈 · 쪽수 2 · 받은 계정');
  ok(Math.abs(fb.received_at - (now - 600000)) < 2000, '받은 시각(UTC → 그대로 시각값)');
  ok(j.items[0].id === fb.id, '최근 것부터');
  r = await kim('/api/fax/' + fa.id + '/file');
  const pdf = Buffer.from(await r.arrayBuffer());
  ok(r.headers.get('content-type') === 'application/pdf' && pdf.toString('latin1', 0, 5) === '%PDF-', '보기 = PDF');
  fs.writeFileSync(path.join(tmp, 'got.pdf'), pdf);
  const png = path.join(tmp, 'got.png');
  execFileSync(gs, ['-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pnggray', '-r20', '-dFirstPage=1', '-dLastPage=1', '-sOutputFile=' + png, path.join(tmp, 'got.pdf')]);
  ok(fs.statSync(png).size > 300, 'PDF 가 Ghostscript 로 그려짐 (깨지지 않음)');
  r = await kim('/api/fax/' + fa.id + '/file?orig=1');
  ok(Buffer.from(await r.arrayBuffer()).equals(inbox[1].tiff), '원본 TIFF 그대로 내려받기');
  j = await (await kim('/api/fax/' + fa.id)).json();
  ok(j.fax.status === 'seen', '열면 「확인」');
  const calls = dev.got.newFaxCalls;
  await app.fax.pollDevice();
  j = await (await kim('/api/fax?status=all')).json();
  ok(j.items.length === 2 && dev.got.downloads === 2 && dev.got.newFaxCalls === calls + 1, '다시 물어도 중복 없음 (마지막 작업번호부터)');
  inbox.push({ taskId: 10, time: utc(Date.now()), cid: '0629998888', file: '1A2B3C4F', tiff: mk('c', 'NEW', 1) });
  r = await kim('/api/fax/admin/poll', { method: 'POST' });
  j = await r.json();
  ok(j.ok && j.total === 3 && j.device.lastTask === 10, '관리자 「↻ 받기」 → 새 팩스 1건 더');

  //  3. 보내기
  const lee = await login(P, 'lee', 'leepw123');
  r = await lee('/api/fax/admin/poll', { method: 'POST' });
  ok(r.status === 403, '직원은 「받기」 단추 못 씀');
  fs.writeFileSync(path.join(tmp, 'q.ps'), '%!PS\n/Helvetica findfont 40 scalefont setfont 72 700 moveto (SEND) show showpage\n');
  execFileSync(gs, ['-q', '-dNOPAUSE', '-dBATCH', '-sDEVICE=pdfwrite', '-sOutputFile=' + path.join(tmp, 'q.pdf'), path.join(tmp, 'q.ps')]);
  r = await lee('/api/fax/send?to=0313510938&name=' + encodeURIComponent('대한상사'), { method: 'POST', body: fs.readFileSync(path.join(tmp, 'q.pdf')) });
  j = await r.json();
  ok(j.ok && j.items.length === 1, '직원 보내기 접수');
  let sent = null;
  for (let i = 0; i < 100 && !sent; i++) { const x = await (await lee('/api/fax/sent')).json(); if (x.items[0].state === 'accepted' || x.items[0].state === 'failed') sent = x.items[0]; else await new Promise((q) => setTimeout(q, 150)); }
  ok(sent && sent.state === 'accepted' && dev.got.faxes.length === 1 && dev.got.faxes[0].headSize === 1024, '장비 접수 (머리 1024) → 작업번호 ' + (sent && sent.task_id));
  j = await (await kim('/api/fax/sent')).json();
  ok(j.items.length === 1, '보낸 목록: 모두 보기(기본)');

  //  4. 다시 켜도 그대로
  app.srv.closeAllConnections(); app.srv.close();
  app = await hf.start({ port: 0, quiet: true, cfg });
  app.fax.stop();
  const kim2 = (url, opt) => fetch(`http://localhost:${app.port}${url}`, Object.assign({}, opt, { headers: { Cookie: kim.cookie } }));
  await new Promise((q) => setTimeout(q, 700));
  j = await (await kim2('/api/fax?status=all')).json();
  ok(j.ok && j.items.length === 3, '다시 켜도 로그인 유지 · 받은 팩스 3건 그대로');
  await app.fax.pollDevice();
  ok(dev.got.downloads === 3, '다시 켠 뒤에도 다시 내려받지 않음');

  //  5. 지운 직원은 바로 막힘
  delete users.lee;
  r = await fetch(`http://localhost:${app.port}/api/fax`, { headers: { Cookie: lee.cookie } });
  ok(r.status === 401, '지운 직원은 로그인 상태여도 막힘');

  //  6. 로그인 잠금 (10분에 5번)
  for (let i = 0; i < 5; i++) await login(app.port, 'kim', 'nope');
  const locked = await login(app.port, 'kim', 'kimpw123');
  ok(!locked.cookie.startsWith('hfsid='), '5번 틀리면 맞는 비밀번호도 잠시 막힘');

  app.srv.closeAllConnections(); app.srv.close(); dev.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`\n✅ ${pass} · ❌ ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
