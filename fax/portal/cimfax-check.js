//  📠 CimFAX 장비 점검 — 포털에 넣기 전에 장비와 말이 통하는지 한 번 확인
//
//   1) 로그인만:           node cimfax-check.js --host 192.168.0.50 --user hanil --pass 비밀번호
//   2) 대기열 보기:         node cimfax-check.js --host … --user … --pass … --queue
//   3) 시험 팩스 한 장:     node cimfax-check.js --host … --user … --pass … --send 0212345678 --file 시험.pdf
//   4) 보낸 것 상태:        node cimfax-check.js --host … --user … --pass … --status 101
//   (PDF 변환에 Ghostscript 가 필요. 찾지 못하면 --gs "C:\Program Files\gs\gs10.04.0\bin\gswin64c.exe")
'use strict';
const os = require('os'), path = require('path'), fs = require('fs');
const cim = require('./cimfax-client');

const a = {};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i];
  if (k.startsWith('--')) { const v = process.argv[i + 1]; if (!v || v.startsWith('--')) a[k.slice(2)] = true; else { a[k.slice(2)] = v; i++; } }
}
if (!a.host || !a.user) {
  console.log('쓰는 법: node cimfax-check.js --host 장비IP --user CimFAX계정 --pass 비밀번호 [--queue | --send 번호 --file 파일.pdf | --status 작업번호]');
  process.exit(1);
}
const dev = { host: a.host, user: a.user, password: a.pass === true ? '' : (a.pass || ''), ghostscript: a.gs, timeoutMs: 15000 };

(async () => {
  if (a.send) {
    if (!/^[0-9,*#-]*\d{3,}[0-9,*#-]*$/.test(String(a.send))) throw new Error('받는 팩스 번호를 숫자로 넣어 주세요 (예: --send 0212345678) — 지금 값: ' + a.send);
    if (!a.file || !fs.existsSync(a.file)) throw new Error('보낼 PDF 가 없습니다: ' + (a.file || '(--file 빠짐)'));
  }
  console.log('cimfax-client 판 ' + (cim.VERSION || '옛 판(1088 만 보냄) — 새 zip 으로 바꿔 주세요'));
  console.log('▶ 장비 ' + dev.host + ' 에 로그인 …');
  const c = await cim.login(dev, cim.PORT.cmd);
  c.close();
  console.log('✅ 로그인 성공 — 장비 이름 ' + c.info.serverName + ' · 장비 ID ' + c.info.serverId + ' · 권한 ' + c.info.permission + ' · 내선 ' + (c.info.ext || '-'));

  if (a.queue) {
    const r = await cim.sendStatus(dev, 'all in queue');
    console.log(r.ok ? '보낼 대기열 ' + r.items.length + '건' : '대기열 조회 실패: ' + r.raw);
    r.items.forEach((x) => console.log('  작업 ' + x.taskId + ' → ' + x.phone + ' · 상태 ' + x.status + ' · ' + x.pageSent + '/' + x.pageTotal + '쪽 · 다이얼 ' + x.dialDone + '/' + x.dialTotal));
  }

  if (a.send) {
    if (!a.file) throw new Error('--file 로 보낼 PDF 를 지정해 주세요');
    const tif = path.join(os.tmpdir(), 'cimfax-check-' + process.pid + '.tif');
    console.log('▶ 팩스 TIFF 로 바꾸는 중 …');
    const t = await cim.toFaxTiff(a.file, tif, { ghostscript: a.gs });
    console.log('  ' + t.pages + '쪽 · ' + Math.round(t.bytes / 1024) + 'KB');
    console.log('▶ ' + a.send + ' 로 보내는 중 …');
    const r = await cim.sendFax(dev, { phone: String(a.send), pages: t.pages, tiff: tif, onProgress: (p) => process.stdout.write('\r  ' + p + '%   '), onAttempt: (n) => console.log('  머리 ' + n + ' 바이트로 시도') });
    fs.unlinkSync(tif);
    console.log('\n✅ 장비가 받았습니다 — 작업번호 ' + r.taskId + ' · 머리 ' + r.headerSize + ' 바이트   (FaxBox 의 보낸 팩스·대기열에서도 보여야 합니다)');
    console.log('   잠시 뒤:  node cimfax-check.js --host ' + a.host + ' --user ' + a.user + ' --pass … --status ' + r.taskId);
  }

  if (a.status) {
    const r = await cim.sendStatus(dev, String(a.status));
    if (!r.ok) console.log('상태 조회 실패: ' + r.raw);
    else if (!r.items.length) console.log('작업 ' + a.status + ' 을(를) 찾지 못했습니다 (이미 끝나 기록으로 넘어갔을 수 있음)');
    r.items.forEach((x) => console.log('작업 ' + x.taskId + ' → ' + x.phone + ' · 상태코드 ' + x.status + ' · 보낸 쪽 ' + x.pageSent + '/' + x.pageTotal + ' · 다이얼 ' + x.dialDone + '/' + x.dialTotal));
  }
})().catch((e) => { console.error('❌ ' + e.message); process.exit(1); });
