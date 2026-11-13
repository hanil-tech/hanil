//  받은 팩스 조각 점검 — 가짜 포털 + 가짜 FaxBox 내보내기 폴더
//   cd fax/test && npm install && npm test
'use strict';
const fs = require('fs'), path = require('path'), os = require('os');
const start = require('./fake-portal');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('✅', m); } else { fail++; console.log('❌', m); } };

const PDF = (n) => Buffer.from('%PDF-1.4\n% fax ' + n + '\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n');
const TIF = Buffer.from([0x49, 0x49, 0x2a, 0x00, 8, 0, 0, 0, 0, 0]);
const OLD = (Date.now() - 60 * 86400000) / 1000, AGO = (Date.now() - 60000) / 1000;
function put(root, rel, buf, t) {
  const p = path.join(root, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, buf);
  if (t) fs.utimesSync(p, t, t);
  return p;
}

async function login(port, user) {
  const r = await fetch(`http://localhost:${port}/login`, { method: 'POST', redirect: 'manual', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `username=${user}&password=1234` });
  const c = (r.headers.get('set-cookie') || '').split(';')[0];
  return (url, opt) => fetch(`http://localhost:${port}${url}`, Object.assign({ redirect: 'manual' }, opt, { headers: Object.assign({ Cookie: c, 'Content-Type': 'application/json' }, (opt || {}).headers) }));
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'faxcheck-'));
  const inbox = path.join(tmp, 'inbox'), store = path.join(tmp, 'store');
  fs.mkdirSync(inbox);
  //  FaxBox 가 내보낸 모양 그대로
  put(inbox, '20261112093015_From_0212345678_To_hanil.pdf', PDF(1), AGO);
  put(inbox, '대한상사/20261112101500_From_0551234567_To_hanil.pdf', PDF(2), AGO);
  put(inbox, 'unknow/20261112110000_From__To_public_PdfErr.tif', TIF, AGO);
  put(inbox, '20260901080000_From_021111_To_hanil.pdf', PDF(3), OLD);           //  60일 전 → 건너뜀
  put(inbox, 'x_CvrtTemp.tif', TIF, AGO);                                        //  변환 중 임시 → 건너뜀
  put(inbox, '_포털등록/20261111000000_From_1_To_2.pdf', PDF(4), AGO);           //  이미 옮긴 것 → 건너뜀
  put(inbox, 'copy/20261112093015_From_0212345678_To_hanil.pdf', PDF(1), AGO);   //  같은 내용 두 번 → 하나만
  put(inbox, '20261112120000_From_0312223333_To_hanil.pdf', PDF(5));             //  지금 막 쓰는 중 → 아직

  const { srv, fax, notified, port } = await start({ inbox, store, port: 0, ctx: { route: { from: { '대한상사': 'lee' }, to: { public: 'kim' } } } });
  fax.stop();

  //  1. 로그인
  let r = await fetch(`http://localhost:${port}/api/fax`);
  ok(r.status === 401, '로그인 없이 /api/fax → 401');
  r = await fetch(`http://localhost:${port}/fax`, { redirect: 'manual' });
  ok(r.status === 302 && /next=%2Ffax/.test(r.headers.get('location')), '로그인 없이 /fax → 로그인 화면으로');

  //  2. 폴더 살피기 — 한 번 보고, 두 번째에 크기가 그대로면 등록
  await fax.scan();
  ok(fax.db().faxes.length === 0, '처음 본 파일은 바로 등록하지 않음(다 써졌는지 한 번 더 확인)');
  await fax.scan();
  const kim = await login(port, 'kim'), lee = await login(port, 'lee');
  let j = await (await kim('/api/fax?status=all')).json();
  ok(j.ok && j.items.length === 3, '등록 3건 (오래된 것·임시·옮긴 것·중복·쓰는 중 제외) → ' + j.items.length);
  ok(j.counts.new === 3, '셋 다 「안 봄」');
  const byFrom = Object.fromEntries(j.items.map((f) => [f.from_name || f.from || f.to, f]));
  const a = byFrom['0212345678'], b = byFrom['대한상사'], c = byFrom['public'];
  ok(a && a.to === 'hanil' && new Date(a.received_at).getHours() === 9 && new Date(a.received_at).getMinutes() === 30, '파일 이름에서 보낸 번호·받은 계정·시각을 읽음');
  ok(b && b.from === '0551234567' && b.from_name === '대한상사', '하위 폴더 이름 = 보낸 곳 이름');
  ok(b && b.assignee === 'lee', '보낸 곳으로 담당자 자동 지정');
  ok(c && c.ext === 'tif' && c.assignee === 'kim' && c.from === '', 'PDF 변환 실패본(TIF)도 등록 · 받은 계정으로 담당 지정');
  ok(j.items[0].received_at >= j.items[1].received_at, '최근 것부터');
  ok(!('sha256' in j.items[0]), '내부 값(sha256)은 내보내지 않음');
  ok(notified.length === 3 && notified[0].url.startsWith('/fax#'), '새 팩스마다 알림 함수 호출');

  //  3. 쓰는 중이던 파일이 다 써지면 등록
  fs.utimesSync(path.join(inbox, '20261112120000_From_0312223333_To_hanil.pdf'), AGO, AGO);
  await fax.scan(); await fax.scan();
  j = await (await kim('/api/fax/count')).json();
  ok(j.new === 4, '다 써진 뒤 등록 → 안 봄 4');

  //  4. 파일 보기 → 「확인」
  r = await lee('/api/fax/' + a.id + '/file');
  const body = Buffer.from(await r.arrayBuffer());
  ok(r.status === 200 && r.headers.get('content-type') === 'application/pdf' && /^inline/.test(r.headers.get('content-disposition')), 'PDF 는 화면에 바로');
  ok(body.equals(PDF(1)), '내용이 원본과 같음');
  ok(/%ED%8C%A9%EC%8A%A4_20261112_0930_0212345678\.pdf/.test(r.headers.get('content-disposition')), '받는 이름: 팩스_날짜_시각_보낸곳.pdf');
  j = await (await kim('/api/fax/' + a.id)).json();
  ok(j.fax.status === 'seen' && j.fax.history.some((h) => h.by === '이사원' && h.action === '열어 봄'), '열면 「확인」 + 누가 봤는지 기록');
  r = await kim('/api/fax/' + c.id + '/file');
  ok(r.headers.get('content-type') === 'image/tiff' && /^attachment/.test(r.headers.get('content-disposition')), 'TIF 는 내려받기');

  //  5. 처리
  r = await lee('/api/fax/' + a.id, { method: 'PUT', body: JSON.stringify({ status: 'done', memo: '견적 회신함', assignee: '이사원' }) });
  j = await r.json();
  ok(j.ok && j.fax.status === 'done' && j.fax.memo === '견적 회신함' && j.fax.assignee === '이사원', '처리 완료 · 메모 · 담당 저장');
  r = await lee('/api/fax/' + a.id, { method: 'PUT', body: JSON.stringify({ status: 'zzz' }) });
  ok(r.status === 400, '이상한 상태 → 400');
  j = await (await kim('/api/fax?status=done')).json();
  ok(j.items.length === 1 && j.items[0].id === a.id, '「처리 완료」 칸에 보임');
  j = await (await kim('/api/fax?q=' + encodeURIComponent('견적'))).json();
  ok(j.items.length === 1, '메모로 찾기');
  r = await kim('/api/fax/zz/file');
  ok(r.status === 404, '이상한 번호 → 404');

  //  6. 관리자
  r = await lee('/api/fax/' + b.id, { method: 'DELETE' });
  ok(r.status === 403, '직원은 숨기기 못함');
  r = await lee('/api/fax/admin/status');
  ok(r.status === 403, '직원은 관리 상태 못 봄');
  j = await (await kim('/api/fax/admin/status')).json();
  ok(j.ok && j.inboxes[0].ok === true && j.total === 4, '관리 상태: 폴더 읽힘 · 총 4건');
  r = await kim('/api/fax/' + b.id, { method: 'DELETE' });
  ok(r.status === 200, '관리자는 숨기기');
  r = await kim('/api/fax/' + b.id);
  ok(r.status === 404, '숨긴 팩스는 안 보임');

  //  7. 페이지
  r = await kim('/fax');
  ok(r.status === 200 && /받은 팩스/.test(await r.text()), '/fax 화면');
  srv.close();

  //  8. 다시 켜도 그대로 · 다시 등록하지 않음
  const again = await start({ inbox, store, port: 0 });
  again.fax.stop();
  await again.fax.scan(); await again.fax.scan();
  ok(again.fax.db().faxes.length === 4 && again.notified.length === 0, '포털을 다시 켜도 기록 유지 · 중복 등록 없음');
  again.srv.close();

  //  9. after: 'move' — 등록한 원본을 _포털등록 으로 옮김
  const inbox2 = path.join(tmp, 'inbox2');
  put(inbox2, '대한상사/20261113080000_From_0551234567_To_hanil.pdf', PDF(9), AGO);
  const mv = await start({ inbox: inbox2, store: path.join(tmp, 'store2'), port: 0, ctx: { after: 'move' } });
  mv.fax.stop();
  await mv.fax.scan(); await mv.fax.scan();
  ok(fs.existsSync(path.join(inbox2, '_포털등록', '대한상사', '20261113080000_From_0551234567_To_hanil.pdf')) && !fs.existsSync(path.join(inbox2, '대한상사', '20261113080000_From_0551234567_To_hanil.pdf')), "after:'move' → 원본을 _포털등록 으로 옮김");
  await mv.fax.scan(); await mv.fax.scan();
  ok(mv.fax.db().faxes.length === 1, '옮긴 뒤 다시 등록하지 않음');
  mv.srv.close();

  //  10. 폴더가 없을 때
  const bad = await start({ inbox: path.join(tmp, 'nope'), store: path.join(tmp, 'store3'), port: 0 });
  bad.fax.stop();
  await bad.fax.scan();
  const k3 = await login(bad.port, 'kim');
  j = await (await k3('/api/fax/admin/status')).json();
  ok(j.inboxes[0].ok === false && j.inboxes[0].error === '폴더가 없습니다', '폴더가 없으면 관리 상태에 알려 줌');
  bad.srv.close();

  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`\n✅ ${pass} · ❌ ${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
