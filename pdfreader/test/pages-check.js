//  구성·변환·글자 표시 시험 — node test/pages-check.js <시험 PDF 폴더> <결과 폴더>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const dir = path.resolve(process.argv[2]);
const out = path.resolve(process.argv[3]);
fs.mkdirSync(out, { recursive: true });
const html = path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html');
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
const py = (code, ...a) => execFileSync('python3', ['-c', code, ...a]).toString().trim();

(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = [];
  page.on('pageerror', (e) => { errs.push(e.message); console.log('   ⚠ ' + e.message); });
  await page.goto('file://' + html);
  const R = (f, a) => page.evaluate(f, a);
  const n = () => R(() => window.__pdfReader.cur.n);
  const save = async (name) => {
    const b64 = await R(async () => { const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); });
    const f = path.join(out, name); fs.writeFileSync(f, Buffer.from(b64, 'base64')); return f;
  };
  const waitDone = () => page.waitForFunction(() => /끝|되돌렸/.test(document.querySelector('#toast').textContent), null, { timeout: 30000 });
  await page.setInputFiles('#fOpen', path.join(dir, '설명서 50쪽.pdf'));
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas');
  await page.click('.rt[data-rt=org]');

  //  페이지 고르기(1·3쪽) → 회전
  await page.click('.th[data-i="0"]');
  await page.click('.th[data-i="2"]', { modifiers: ['Control'] });
  ok(await R(() => [...window.__pdfReader.cur.psel].join()) === '0,2', '페이지 칸에서 1·3쪽 고름(Ctrl)');
  await page.click('.mwrap button[data-menu=mPRot]');
  await page.click('.rmenu.on [data-cmd=pRotR]');
  await waitDone();
  let f = await save('회전.pdf');
  ok(py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print([p.rotation for p in r.pages[:4]])', f) === '[90, 0, 90, 0]', '1·3쪽 오른쪽 회전(저장됨)');
  //  삭제(2쪽)
  await page.click('.th[data-i="1"]');
  page.once('dialog', () => {});
  await page.click('#ribbon [data-cmd=pDel]');
  await page.waitForSelector('#modal.on'); await page.click('#mFoot button:first-child');
  await waitDone();
  ok(await n() === 49, '2쪽 삭제 → 49쪽');
  //  되돌리기
  await page.click('#ribbon [data-cmd=pUndo]');
  await waitDone();
  ok(await n() === 50, '되돌리기 → 50쪽');
  //  복사(5쪽) → 1쪽 뒤에 붙여넣기 (페이지 칸 Ctrl+C / Ctrl+V)
  await page.click('.th[data-i="4"]');
  await page.keyboard.press('Control+c');
  await page.click('.th[data-i="0"]');
  await R(() => { const dt = new DataTransfer(); document.querySelector('#thumbs').dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true })); });
  await waitDone();
  ok(await n() === 51, '페이지 칸 Ctrl+C·Ctrl+V → 51쪽');
  const t2 = await R(async () => { const d = window.__pdfReader.cur; const tc = await (await d.pdf.getPage(2)).getTextContent(); return tc.items.map((i) => i.str).join('').slice(0, 6); });
  ok(t2.startsWith('제 5 장'), '붙인 2쪽이 「제 5 장」: ' + t2);
  //  다른 문서로 붙여넣기
  await page.setInputFiles('#fOpen', path.join(dir, 'A-002 적재함.pdf'));
  await page.waitForFunction(() => window.__pdfReader.cur.name.includes('A-002'));
  await page.click('#ribbon [data-cmd=pPaste]');
  await waitDone();
  ok(await n() === 3, '다른 문서(A-002)에 붙여넣기 → 3쪽');
  //  자르기 — 1쪽 위쪽 절반만 남김
  await page.click('.rt[data-rt=view]'); await page.click('#ribbon [data-cmd=page]'); await page.click('#status [data-cmd=first]'); await page.click('.rt[data-rt=org]');
  await page.click('#ribbon [data-cmd=tCrop]');
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] .ov', { timeout: 5000 }).catch(async (e) => {
    console.log(await R(() => { const d = window.__pdfReader.cur; return JSON.stringify([window.__pdfReader.tool, d.name, d.cur, d.pages.map((p) => [!!p.canvas, !!p.ov, p.key]), [...document.querySelectorAll('.doc')].map((e) => e.style.display + ':' + e.children.length)]); }));
    throw e;
  });
  const bx = await (await page.$('.doc:not([style*="none"]) .pg[data-i="0"]')).boundingBox();
  await page.mouse.move(bx.x + 5, bx.y + 5); await page.mouse.down(); await page.mouse.move(bx.x + bx.width - 5, bx.y + bx.height / 2, { steps: 5 }); await page.mouse.up();
  await page.waitForSelector('#modal.on'); await page.click('#mFoot button:first-child');
  await waitDone();
  f = await save('자르기.pdf');
  const cb = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);p=r.pages[0];print(round(float(p.cropbox.height)),round(float(p.mediabox.height)))', f).split(' ').map(Number);
  ok(cb[0] < cb[1] * 0.6 && cb[0] > cb[1] * 0.4, '자르기 → 높이 ' + cb[0] + ' / ' + cb[1]);
  //  페이지 번호 · 워터마크
  await page.click('#ribbon [data-cmd=pNum]');
  await page.waitForSelector('#modal.on #mIn'); await page.keyboard.press('Enter');
  await waitDone();
  await page.click('#ribbon [data-cmd=pWm]');
  await page.waitForSelector('#modal.on #mIn'); await page.fill('#mIn', '대외비'); await page.keyboard.press('Enter');
  await waitDone();
  f = await save('번호·워터마크.pdf');
  const txt = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print(r.pages[2].extract_text()[-12:].replace(chr(10)," "))', f);
  ok(/3 \/ 3/.test(txt), '페이지 번호 「3 / 3」: ' + txt);
  execFileSync('pdftoppm', ['-r', '50', '-png', '-f', '2', '-l', '2', f, path.join(out, 'wm')]);
  ok(fs.readdirSync(out).some((x) => x.startsWith('wm')), '워터마크 페이지 그림(poppler)');

  //  글자 강조·밑줄·취소선 — 글자를 끌어 고름
  await page.click('.rt[data-rt=edit]');
  await page.click('#ribbon [data-cmd=mhl]');
  const sp = await page.$$('.doc:not([style*="none"]) .pg[data-i="1"] .textLayer span');
  await page.evaluate(() => { const s = document.querySelectorAll('.doc:not([style*="none"]) .pg[data-i="1"] .textLayer span'); const r = document.createRange(); r.setStart(s[0].firstChild, 0); r.setEnd(s[0].firstChild, s[0].textContent.length); getSelection().removeAllRanges(); getSelection().addRange(r); });
  await R(() => document.querySelector('#viewer').dispatchEvent(new MouseEvent('mouseup', { bubbles: true })));
  await page.waitForFunction(() => window.__pdfReader.cur.ed && window.__pdfReader.cur.ed.objs.some((o) => o.t === 'mark'));
  ok(true, '강조 표시(글자 고르기)');
  f = await save('강조.pdf');
  ok(/Highlight/.test(py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print([str(a.get_object()["/Subtype"]) for a in r.pages[1].get("/Annots",[])])', f)), '표준 Highlight 주석(QuadPoints)으로 저장');

  //  도형 돌리기·복사·붙여넣기
  await page.click('#ribbon [data-cmd=tRect]');
  const b1 = await (await page.$('.doc:not([style*="none"]) .pg[data-i="0"]')).boundingBox();
  await page.mouse.move(b1.x + 50, b1.y + 50); await page.mouse.down(); await page.mouse.move(b1.x + 250, b1.y + 100, { steps: 4 }); await page.mouse.up();
  const r0 = await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.t === 'rect'); return [o.w, o.h].map(Math.round); });
  await page.keyboard.press('Control+r');
  const r1 = await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.t === 'rect'); return [o.w, o.h].map(Math.round); });
  ok(r0[0] === r1[1] && r0[1] === r1[0], '도형 90° 회전(Ctrl+R) ' + r0 + ' → ' + r1);
  const c0 = await R(() => window.__pdfReader.cur.ed.objs.length);
  await page.keyboard.press('Control+c');
  await R(() => document.dispatchEvent(new ClipboardEvent('paste', { clipboardData: new DataTransfer(), bubbles: true })));
  await page.waitForTimeout(200);
  ok(await R(() => window.__pdfReader.cur.ed.objs.length) === c0 + 1, '도형 복사·붙여넣기');
  await page.keyboard.press('Control+x');
  ok(await R(() => window.__pdfReader.cur.ed.objs.length) === c0, '도형 잘라내기');
  //  스탬프
  await page.click('.mwrap button[data-cmd=tStamp] span');
  await page.click('.rmenu.stamps.on .stp:has-text("승인")');
  await page.mouse.click(b1.x + 300, b1.y + 300);
  ok(await R(() => window.__pdfReader.cur.ed.objs.some((o) => o.t === 'stamp' && o.sym === '승인')), '스탬프 「승인」');
  ok(await page.isVisible('#fmtTab'), '「형식」 노란 탭이 보임');
  await page.screenshot({ path: path.join(out, '3-구성.png') });

  //  변환: 이미지로 내보내기(모든 쪽 → ZIP)
  await page.keyboard.press('Escape'); await page.keyboard.press('Escape');
  await page.click('.rt[data-rt=conv]');
  await page.click('#ribbon [data-cmd=expImg]');
  await page.waitForSelector('#modal.on');
  await page.check('input[name=xr][value=all]');
  const dl = page.waitForEvent('download', { timeout: 60000 });
  await page.click('#mFoot button:first-child');
  const z = await dl;
  const zp = path.join(out, z.suggestedFilename()); await z.saveAs(zp);
  ok(py('import sys,zipfile;z=zipfile.ZipFile(sys.argv[1]);print(z.testzip() is None and len(z.namelist()))', zp) === '3', '이미지로 내보내기 ZIP 3장(파이썬이 열어 확인)');
  //  새 문서 · 이미지에서 PDF
  await page.click('#ribbon [data-cmd=newDoc]');
  await page.waitForFunction(() => window.__pdfReader.cur.name === '새 문서.pdf');
  ok(true, '새 문서(공백)');
  //  파일 메뉴 · 환경 설정
  await page.click('.rt.file');
  await page.waitForSelector('#bsPanel h1');
  ok((await page.textContent('#bsPanel')).includes('최근 파일') && (await page.textContent('#bsPanel')).includes('설명서 50쪽.pdf'), '파일 → 열기: 최근 파일 목록');
  await page.screenshot({ path: path.join(out, '4-파일메뉴.png') });
  await page.click('#backstage [data-cmd=settings]');
  await page.waitForSelector('.setwin');
  await page.click('.setcats button:has-text("주석 달기")');
  await page.fill('.setrow input[type=text]', '김설계');
  await page.screenshot({ path: path.join(out, '5-환경설정.png') });
  await page.click('.setfoot button:first-child');
  ok(await R(() => window.__pdfReader.EDIT.style.author) === '김설계', '환경 설정: 작성자 이름 저장');

  ok(errs.length === 0, '화면 오류 없음');
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
