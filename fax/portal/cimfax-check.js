//  📠 CimFAX 장비 점검 — 포털에 넣기 전에 장비와 말이 통하는지 한 번 확인
//
//   1) 로그인만:           node cimfax-check.js --host 192.168.0.50 --user hanil --pass 비밀번호
//   2) 대기열 보기:         node cimfax-check.js --host … --user … --pass … --queue
//   3) 시험 팩스 한 장:     node cimfax-check.js --host … --user … --pass … --send 0212345678 --file 시험.pdf
//   4) 보낸 것 상태:        node cimfax-check.js --host … --user … --pass … --status 101
//   4-1) 보내기 취소(멈춤):  node cimfax-check.js --host … --user … --pass … --cancel 3501        (대기·다시 거는 중인 것)
//   4-2) 다시 보내기:        node cimfax-check.js --host … --user … --pass … --resume 3501
//   4-3) 장비의 보낸 기록:   node cimfax-check.js --host … --user … --pass … --history [--days 7] [--type send|recv] [--qyuser 계정]
//   5) 받은 팩스 목록:      node cimfax-check.js --host … --user … --pass … --inbox            (장비에 저장된 것, 오래된 것부터)
//   6) 받은 팩스 내보내기:  node cimfax-check.js --host … --user … --pass … --export 폴더 [--days 90] [--pdf-only]
//        장비에 저장된 받은 팩스를 폴더에 PDF(+원본 TIFF)로 저장. 이름은 FaxBox 내보내기와 같은 모양:
//        20261113093015_From_0212345678_To_admin.pdf   — 다시 돌리면 이어서 새 것만 받는다.
//        처음부터 전부(날짜 제한 없이) 다시 훑으려면 --from 0 (이미 받은 것은 .cimfax-index 로 건너뜀)
//        --until 작업번호 : 그 번호까지만 (포털이 이미 받아 둔 것과 겹치지 않게 — 포털이 처음 받은 작업번호 - 1)
//        장비 안의 팩스는 지우거나 바꾸지 않는다 (읽기만).
//   비밀번호 대신 --pass-file ~/.cimfax-pass (첫 줄이 비밀번호, chmod 600) 도 된다 — 예약 작업용
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
  console.log('쓰는 법: node cimfax-check.js --host 장비IP --user CimFAX계정 --pass 비밀번호 [--queue | --send 번호 --file 파일.pdf | --status 작업번호 | --cancel 작업번호 | --resume 작업번호 | --inbox | --export 폴더 [--days 90]]');
  process.exit(1);
}
//  비밀번호: --pass 값, 또는 --pass-file 파일(첫 줄), 또는 환경 변수 CIMFAX_PASS — 예약 작업(cron)에 비밀번호를 적지 않게
let pw = a.pass === true ? '' : (a.pass || '');
if (!pw && a['pass-file']) {
  try { pw = fs.readFileSync(String(a['pass-file']), 'utf8').split(/\r?\n/)[0]; } catch (e) { console.error('❌ 비밀번호 파일을 읽지 못했습니다: ' + a['pass-file']); process.exit(1); }
}
if (!pw && process.env.CIMFAX_PASS) pw = process.env.CIMFAX_PASS;
const dev = { host: a.host, user: a.user, password: pw, ghostscript: a.gs, timeoutMs: 15000 };

(async () => {
  if (a.send) {
    if (!/^[0-9,*#-]*\d{3,}[0-9,*#-]*$/.test(String(a.send))) throw new Error('받는 팩스 번호를 숫자로 넣어 주세요 (예: --send 0212345678) — 지금 값: ' + a.send);
    if (!a.file || !fs.existsSync(a.file)) throw new Error('보낼 PDF 가 없습니다: ' + (a.file || '(--file 빠짐)'));
  }
  if (!a.quiet) console.log('cimfax-client 판 ' + (cim.VERSION || '옛 판(1088 만 보냄) — 새 zip 으로 바꿔 주세요'));
  if (!a.quiet) console.log('▶ 장비 ' + dev.host + ' 에 로그인 …');
  const c = await cim.login(dev, cim.PORT.cmd);
  c.close();
  if (!a.quiet) console.log('✅ 로그인 성공 — 장비 이름 ' + c.info.serverName + ' · 장비 ID ' + c.info.serverId + ' · 권한 ' + c.info.permission + ' · 내선 ' + (c.info.ext || '-'));

  if (a.queue) {
    const r = await cim.sendStatus(dev, 'all in queue');
    console.log(r.ok ? '보낼 대기열 ' + r.items.length + '건' : '대기열 조회 실패: ' + r.raw);
    r.items.forEach((x) => console.log('  작업 ' + x.taskId + ' → ' + x.phone + ' · ' + cim.statusText(x.status) + ' · ' + x.pageSent + '/' + x.pageTotal + '쪽 · 다이얼 ' + x.dialDone + '/' + x.dialTotal));
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
    r.items.forEach((x) => console.log('작업 ' + x.taskId + ' → ' + x.phone + ' · ' + cim.statusText(x.status) + ' · 보낸 쪽 ' + x.pageSent + '/' + x.pageTotal + ' · 다이얼 ' + x.dialDone + '/' + x.dialTotal));
  }

  if (a.cancel) {
    const id = Number(a.cancel);
    if (!id) throw new Error('--cancel 뒤에 작업번호를 넣어 주세요');
    const r = await cim.pauseSend(dev, id);
    console.log(r.ok ? '✅ 작업 ' + id + ' 보내기를 멈췄습니다 (다시 보내려면 --resume ' + id + ')' : '❌ 멈추지 못했습니다 — 장비 답: ' + r.feedback + '  (이미 다 보냈거나 없는 작업일 수 있음)');
  }
  if (a.resume) {
    const id = Number(a.resume);
    const r = await cim.retrySend(dev, id, a.retries);
    console.log(r.ok ? '✅ 작업 ' + id + ' 을(를) 다시 보내기 대기열에 넣었습니다' : '❌ 다시 보내기 실패 — 장비 답: ' + r.feedback);
  }

  if (a.history) {
    const days = Number(a.days) || 7;
    const pad = (n) => String(n).padStart(2, '0');
    const fmt = (ms) => { const d = new Date(ms); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); };
    const r = await cim.sendHistory(dev, { from: Date.now() - days * 86400000, type: a.type === true ? '' : a.type, user: a.qyuser === true ? '' : a.qyuser });
    if (!r.ok) console.log('보낸 기록 조회 실패 — 장비 답: ' + r.raw);
    else {
      r.items.forEach((x) => console.log('  작업 ' + x.taskId + ' · ' + (x.at ? fmt(x.at) : '-') + ' → ' + x.phone + ' · ' + cim.statusText(x.status) + ' · ' + x.pageSent + '/' + x.pageTotal + '쪽 · 다이얼 ' + x.dialDone + '/' + x.dialTotal + (x.sender ? ' · 보낸 계정 ' + x.sender : '') + (x.remark ? ' · 비고 ' + x.remark : '')));
      console.log('장비의 보낸 기록 ' + r.items.length + '건 (최근 ' + days + '일' + (a.type && a.type !== true ? ', 종류 ' + a.type : '') + ')');
    }
  }

  //  ── 장비에 저장된 받은 팩스 ──
  if (a.inbox || a.export) {
    const outDir = a.export && a.export !== true ? path.resolve(String(a.export)) : null;
    if (a.export && !outDir) throw new Error('--export 뒤에 저장할 폴더를 넣어 주세요');
    const since = a.days ? Date.now() - Number(a.days) * 86400000 : 0;
    const mark = outDir && path.join(outDir, '.cimfax-last-task');
    if (outDir) fs.mkdirSync(outDir, { recursive: true });
    let last = 0;
    if (mark && fs.existsSync(mark)) last = Number(fs.readFileSync(mark, 'utf8')) || 0;
    if (a.from !== undefined) last = Number(a.from) || 0;
    if (last && !a.quiet) console.log('▶ 작업번호 ' + last + ' 다음부터 (처음부터 다시 받으려면 --from 0)');
    const pad = (n) => String(n).padStart(2, '0');
    const stamp = (ms) => { const d = new Date(ms); return '' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds()); };
    const clean = (s) => String(s || '').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40);
    let seen = 0, saved = 0, skipped = 0, failed = 0, reachedUntil = false, progress = 0;
    for (;;) {
      const list = await cim.listNewFaxes(dev, last, 500, (it) => {
        progress++;
        if (!a.quiet && progress % 50 === 0) process.stderr.write('  … ' + progress + '건 읽음 (작업 ' + it.taskId + ', ' + it.timeRaw.slice(0, 10) + ', 남은 ' + (it.left - 1) + '건)\n');
      });
      if (!list.length) break;
      for (const it of list) {
        if (a.until && it.taskId > Number(a.until)) { reachedUntil = true; break; }
        seen++;
        last = it.taskId;
        //  발신번호가 없는 회선이면 장비가 번호가 아닌 값을 준다 → '모름'
        if (it.cid && !/^[0-9+\-() ,*#]+$/.test(it.cid)) { it.cidRaw = it.cid; it.cid = ''; }
        //  보낸 곳 = 상대 팩스기가 알려 준 팩스 ID(SENDER, FaxBox 의 「발신자 이름」) — 발신번호가 없으면 이것을 쓴다
        const tsi = String(it.sender || '').replace(/[\u0000-\u001f\u007f]/g, '').trim();
        if (!it.cid && tsi) it.cid = tsi;
        const when = new Date(it.receivedAt);
        const label = '작업 ' + it.taskId + ' · ' + when.getFullYear() + '-' + pad(when.getMonth() + 1) + '-' + pad(when.getDate()) + ' ' + pad(when.getHours()) + ':' + pad(when.getMinutes()) +
          ' · 보낸 곳 ' + (it.cid || '모름') + ' · 받은 계정 ' + (it.receiver || '-') + (it.remark ? ' · 비고 ' + it.remark : '');
        if (!outDir) { console.log('  ' + label + ' · 파일 ' + it.file + ' · 남은 ' + (it.left - 1)); continue; }
        if (since && it.receivedAt < since) { skipped++; continue; }
        //  FaxBox 내보내기와 같은 이름 (포털 팩스 기능이 이 폴더를 그대로 읽을 수 있게). 같은 이름이 이미 다른 팩스면 끝에 작업번호
        let base = stamp(it.receivedAt) + '_From_' + clean(it.cid || 'unknown') + '_To_' + clean(it.receiver || dev.user);
        const have = (b) => fs.existsSync(path.join(outDir, b + '.pdf')) || fs.existsSync(path.join(outDir, b + '.tif'));
        const idx = path.join(outDir, '.cimfax-index');
        const done = fs.existsSync(idx) ? fs.readFileSync(idx, 'utf8') : '';
        if (new RegExp('^' + it.taskId + '\\t', 'm').test(done)) { skipped++; continue; }   //  이미 받은 작업
        if (have(base)) base += '_' + it.taskId;
        try {
          const tif = await cim.downloadFax(dev, it.file);
          let pages = 0, pdfOk = false;
          try { const r = cim.tiffToPdf(tif); fs.writeFileSync(path.join(outDir, base + '.pdf'), r.pdf); pages = r.pages; pdfOk = true; } catch (e) { /* TIFF 로만 */ }
          if (!pdfOk || !a['pdf-only']) fs.writeFileSync(path.join(outDir, base + '.tif'), tif);
          saved++;
          fs.appendFileSync(idx, it.taskId + '\t' + base + '\n');
          console.log((a.quiet ? new Date().toLocaleString('ko-KR') + ' ' : '') + '  ✅ ' + label + (pages ? ' · ' + pages + '쪽' : '') + (pdfOk ? '' : ' · (PDF 변환 실패 — TIFF 로 저장)'));
        } catch (e) {
          failed++;
          console.log('  ❌ ' + label + ' — ' + e.message);
        }
        if (!failed) fs.writeFileSync(mark, String(last));   //  실패가 있으면 다음에 그 자리부터 다시
      }
      if (reachedUntil || list[list.length - 1].left <= 1) break;
    }
    if (!outDir) console.log(seen ? '장비에 저장된 받은 팩스 ' + seen + '건 (작업번호 ' + (a.from || 0) + ' 다음부터' + (a.until ? ' ' + a.until + ' 까지' : '') + ')' : '장비에 저장된 받은 팩스가 없습니다 (이 계정으로 볼 수 있는 것 기준)');
    else if (a.quiet && !saved && !failed) { /* 새 것 없음 */ }
    else console.log('\n📁 ' + outDir + '\n   새로 저장 ' + saved + '건 · 건너뜀 ' + skipped + '건' + (failed ? ' · 실패 ' + failed + '건 (다시 돌리면 이어서 받습니다)' : '') + ' · 마지막 작업번호 ' + last);
  }
})().catch((e) => { console.error('❌ ' + e.message); process.exit(1); });
