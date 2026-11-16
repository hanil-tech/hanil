//  양식 필드 만들기·채우기 · 원래 글자 고치기 — node test/form-check.js <시험 PDF 폴더> <결과 폴더>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const dir = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
fs.mkdirSync(out, { recursive: true });
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
const py = (code, ...a) => execFileSync('python3', ['-c', code, ...a]).toString().trim();
(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1500, height: 950 } });
  page.on('pageerror', (e) => { fails++; console.log('⚠ ' + e.message); });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  const R = (f, a) => page.evaluate(f, a);
  const save = async (name) => {
    const b64 = await R(async () => { const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); });
    const f = path.join(out, name); fs.writeFileSync(f, Buffer.from(b64, 'base64')); return f;
  };
  const okModal = async () => { await page.waitForSelector('#modal.on'); await page.click('#mFoot button:first-child'); };

  //  ── 원래 글자 고치기 ──
  await page.setInputFiles('#fOpen', path.join(dir, 'A-001 섀시 부품표.pdf'));
  await page.waitForSelector('.pg[data-i="0"] .textLayer span');
  await page.click('.rt[data-rt=home]');
  await page.click('#ribbon [data-cmd=tTEdit]');
  const span = page.locator('.pg[data-i="0"] .textLayer span', { hasText: '브래킷 0' }).first();
  await span.click();
  await page.waitForSelector('.tedit-in');
  await page.fill('.tedit-in', '브라켓 영(수정)');
  await page.keyboard.press('Enter');
  ok(await R(() => window.__pdfReader.cur.ed.objs.some((o) => o.t === 'tedit' && o.text === '브라켓 영(수정)')), '글자 고치기: 「브래킷 0」 → 「브라켓 영(수정)」');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, '1-글자고치기.png'), clip: { x: 200, y: 150, width: 1000, height: 400 } });
  let f = await save('글자고침.pdf');
  const t = py('import sys;from pypdf import PdfReader;print(PdfReader(sys.argv[1]).pages[0].extract_text().replace(chr(10)," | "))', f);
  console.log('   ' + t);
  ok(t.includes('브라켓 영(수정)') && !t.includes('브래킷 0') && t.includes('브래킷 1') && t.includes('40396607'), '저장한 PDF: 새 글자는 진짜 글자, 원래 「브래킷 0」은 지워짐, 옆 글자들은 그대로');
  execFileSync('pdftoppm', ['-r', '80', '-png', '-f', '1', '-l', '1', f, path.join(out, 'poppler-tedit')]);
  const miss = await R(() => window.__pdfReader.cur.lastEraseMiss);
  ok(miss === 0, '원래 글자를 내용에서 찾아 지움(흰 상자로 덮지 않음)');

  //  ── 양식 필드 만들기 ──
  await page.click('.rt[data-rt=form]');
  await page.click('#ribbon [data-cmd=page]').catch(() => {});
  const bx = await (await page.$('.pg[data-i="0"]')).boundingBox();
  const at = (fx, fy) => [bx.x + bx.width * fx, bx.y + Math.min(bx.height, 800) * fy];
  const drag = async (a, c) => { await page.mouse.move(...a); await page.mouse.down(); await page.mouse.move(...c, { steps: 4 }); await page.mouse.up(); };
  await page.click('#ribbon [data-cmd=fText]');
  await drag(at(0.1, 0.6), at(0.4, 0.63));
  await page.waitForSelector('#fdName'); await page.fill('#fdName', '담당자'); await okModal();
  await page.click('#ribbon [data-cmd=fCheck]');
  await page.mouse.click(...at(0.5, 0.615)); await page.waitForSelector('#fdName'); await page.fill('#fdName', '확인함'); await okModal();
  await page.click('#ribbon [data-cmd=fCombo]');
  await drag(at(0.6, 0.6), at(0.85, 0.63)); await page.waitForSelector('#fdOpts'); await page.fill('#fdName', '결과'); await page.fill('#fdOpts', '합격, 불합격, 보류'); await okModal();
  for (const [x, v] of [[0.1, '예'], [0.2, '아니오']]) { await page.click('#ribbon [data-cmd=fRadio]'); await page.mouse.click(...at(x, 0.7)); await page.waitForSelector('#fdVal'); await page.fill('#fdName', '동의'); await page.fill('#fdVal', v); await okModal(); }
  await page.click('#ribbon [data-cmd=fSig]'); await drag(at(0.55, 0.68), at(0.85, 0.75)); await page.waitForSelector('#fdName'); await page.fill('#fdName', '서명'); await okModal();
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, '2-필드만들기.png') });
  f = await save('양식.pdf');
  const fl = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);fs=r.get_fields();print(sorted((k,str(v.get("/FT"))) for k,v in fs.items()))', f);
  console.log('   ' + fl);
  ok(/'결과', '\/Ch'/.test(fl) && /'담당자', '\/Tx'/.test(fl) && /'동의', '\/Btn'/.test(fl) && /'확인함', '\/Btn'/.test(fl) && /'서명', '\/Sig'/.test(fl), '표준 양식 필드 5개(텍스트·확인란·드롭다운·라디오·서명) — pypdf 로 읽힘');
  const t2 = py('import sys;from pypdf import PdfReader;print(PdfReader(sys.argv[1]).pages[0].extract_text().replace(chr(10)," | "))', f);
  ok(t2.includes('브라켓 영(수정)'), '글자 고침도 함께 저장됨');

  //  ── 다시 열어 채우기 ──
  await R(() => { for (const d of window.__pdfReader.docs) d.mod = false; });
  await page.keyboard.press('Control+w');
  await page.setInputFiles('#fOpen', f);
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name === '양식.pdf');
  await page.click('.rt[data-rt=home]'); await page.click('#ribbon [data-cmd=hand]');
  await page.waitForSelector('.pg[data-i="0"] .annotationLayer input', { timeout: 15000 });
  await page.fill('.pg[data-i="0"] .annotationLayer input[type=text]', '김설계 (한일특장)');
  await page.check('.pg[data-i="0"] .annotationLayer input[type=checkbox]');
  await page.selectOption('.pg[data-i="0"] .annotationLayer select', '불합격');
  await page.locator('.pg[data-i="0"] .annotationLayer input[type=radio]').nth(1).check();
  await page.click('.pg[data-i="0"]', { position: { x: 30, y: 30 } });
  ok(await R(() => window.__pdfReader.cur.formDirty && window.__pdfReader.cur.mod), '양식 채우면 「고침」 표시');
  await page.screenshot({ path: path.join(out, '3-양식채우기.png') });
  f = await save('양식-채움.pdf');
  const vals = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print({k:str(v.get("/V")) for k,v in r.get_fields().items()})', f);
  console.log('   ' + vals);
  ok(/'담당자': '김설계 \(한일특장\)'/.test(vals) && /'결과': '불합격'/.test(vals) && /'확인함': '\/(Yes|On)'/.test(vals) && /'동의': '\/(아니오|.*)'/.test(vals) && !/'동의': 'None'/.test(vals), '채운 값이 PDF 에 저장됨(텍스트·드롭다운·확인란·라디오)');
  execFileSync('pdftoppm', ['-r', '80', '-png', '-f', '1', '-l', '1', f, path.join(out, 'poppler-form')]);
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
