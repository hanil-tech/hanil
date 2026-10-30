//  전자 서명 — node test/sign-check.js <시험 PDF 폴더> <결과 폴더> <pfx 폴더(new.pfx·legacy.pfx, 암호 1234)>
//   서명 → openssl cms 로 따로 검사 · 이 리더의 검사 · 한 바이트 바꾸면 깨짐으로 나오나 · 다시 열면 서명 표시
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const dir = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]), certs = path.resolve(process.argv[4]);
fs.mkdirSync(out, { recursive: true });
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1500, height: 950 } });
  page.on('pageerror', (e) => { fails++; console.log('⚠ ' + e.message); });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  await page.setInputFiles('#fOpen', path.join(dir, 'A-001 섀시 부품표.pdf'));
  await page.waitForSelector('.pg canvas');
  for (const name of ['new.pfx', 'legacy.pfx']) {
    const pfx = fs.readFileSync(path.join(certs, name)).toString('base64');
    const r = await page.evaluate(async (pfx) => {
      const u = Uint8Array.from(atob(pfx), (c) => c.charCodeAt(0));
      const R = window.__pdfReader, d = R.cur;
      const id = R.SIGN.readPfx(u, '1234');
      const bytes = await R.buildPdf(d);
      const signed = await R.SIGN.signPdf(bytes, id, { page: 0, rect: [380, 40, 570, 98], reason: '승인', location: '한일특장(주)' });
      const v = await R.SIGN.verifyPdf(signed);
      const bad = signed.slice(); const k = 200; bad[k] = bad[k] === 32 ? 33 : 32;
      const v2 = await R.SIGN.verifyPdf(bad);
      let s = ''; for (let i = 0; i < signed.length; i += 0x8000) s += String.fromCharCode.apply(null, signed.subarray(i, i + 0x8000));
      return { cn: id.cn, v, v2, b64: btoa(s) };
    }, pfx);
    const f = path.join(out, '서명-' + name + '.pdf');
    fs.writeFileSync(f, Buffer.from(r.b64, 'base64'));
    ok(r.v.length === 1 && r.v[0].ok && r.v[0].cn === '김설계', name + ': 서명함 · 이 리더 검사 ✅ (' + r.cn + ')');
    ok(r.v2.length === 1 && !r.v2[0].ok, name + ': 한 바이트 바꾸면 ❌ — ' + r.v2[0].why);
    //  openssl 로 따로 — ByteRange 대로 자른 내용과 Contents 의 PKCS#7
    const buf = fs.readFileSync(f), txt = buf.toString('latin1');
    const m = /\/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]/.exec(txt);
    const [o1, l1, o2, l2] = m.slice(1).map(Number);
    fs.writeFileSync(path.join(out, 'data.bin'), Buffer.concat([buf.subarray(o1, o1 + l1), buf.subarray(o2, o2 + l2)]));
    const hex = txt.slice(o1 + l1 + 1, o2 - 1).replace(/0+$/, '');
    fs.writeFileSync(path.join(out, 'sig.der'), Buffer.from(hex.length % 2 ? hex + '0' : hex, 'hex'));
    let res = '';
    try { res = execFileSync('openssl', ['cms', '-verify', '-binary', '-inform', 'DER', '-in', path.join(out, 'sig.der'), '-content', path.join(out, 'data.bin'), '-noverify', '-out', '/dev/null'], { stdio: ['ignore', 'pipe', 'pipe'] }).toString(); res = 'ok'; } catch (e) { res = (e.stderr || '').toString(); }
    ok(res === 'ok', name + ': openssl cms -verify 통과 ' + (res === 'ok' ? '' : res.slice(0, 200)));
    ok(o2 + l2 === buf.length, name + ': 서명이 파일 끝까지 덮음(ByteRange)');
  }
  //  다시 열면 속성 창에 ✅
  await page.setInputFiles('#fOpen', path.join(out, '서명-new.pfx.pdf'));
  await page.waitForFunction(() => window.__pdfReader.cur.name.startsWith('서명-new') && window.__pdfReader.cur.sigs);
  ok((await page.textContent('#pProps')).includes('✅ 김설계'), '다시 열면 「전자 서명 ✅ 김설계」');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, '서명.png') });
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
