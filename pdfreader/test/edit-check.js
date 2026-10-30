//  고치기 시험 — node test/edit-check.js <시험 PDF 폴더> <결과 폴더>
//   그리기·글상자·기호·그림 붙여 넣기·옮기기·지우기·되돌리기 → 저장 → 다른 프로그램(poppler pdftoppm·pypdf)으로 확인 → 다시 열어 고치기
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

(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = [];
  page.on('pageerror', (e) => { errs.push(e.message); console.log('   ⚠ ' + e.message); });
  await page.goto('file://' + html);
  const R = (f, a) => page.evaluate(f, a);
  await page.setInputFiles('#fOpen', path.join(dir, 'A-002 적재함.pdf'));
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas');
  await page.click('#ribbon [data-cmd=page]');   //  한 화면에 한 쪽이 다 보이게(누를 자리가 화면 안에)
  await page.waitForTimeout(300);
  await page.click('.rt[data-rt=edit]');
  const pg = await page.$('.doc:not([style*="none"]) .pg[data-i="0"]');
  const box = await pg.boundingBox();
  const at = (fx, fy) => [box.x + box.width * fx, box.y + box.height * fy];
  const dragOn = async (a, c, steps = 6) => { await page.mouse.move(...a); await page.mouse.down(); await page.mouse.move(...c, { steps }); await page.mouse.up(); };
  const count = () => R(() => window.__pdfReader.cur.ed.objs.length);

  await page.click('[data-cmd=tRect]');
  await dragOn(at(0.1, 0.45), at(0.4, 0.55));
  ok(await count() === 1, '사각형 그림');
  ok(await R(() => window.__pdfReader.tool) === 'edit', '그린 뒤 고르기 도구로');
  await page.click('[data-cmd=tEll]');
  await dragOn(at(0.5, 0.45), at(0.7, 0.55));
  await page.click('[data-cmd=tArrow]');
  await dragOn(at(0.1, 0.6), at(0.4, 0.66));
  await page.click('[data-cmd=tPen]');
  await page.mouse.move(...at(0.5, 0.6)); await page.mouse.down();
  for (let k = 0; k <= 20; k++) await page.mouse.move(...at(0.5 + k * 0.01, 0.6 + Math.sin(k / 3) * 0.02));
  await page.mouse.up();
  await page.click('[data-cmd=tHi]');
  await dragOn(at(0.08, 0.13), at(0.5, 0.16));
  await page.click('[data-cmd=tWhite]');
  await dragOn(at(0.6, 0.12), at(0.9, 0.17));
  //  글상자
  await page.click('[data-cmd=tText]');
  await page.mouse.click(...at(0.1, 0.72));
  await page.waitForSelector('.tedit');
  await page.keyboard.type('검사 완료 OK');
  await page.keyboard.press('Enter');
  await page.keyboard.type('한일특장 품질팀');
  await page.mouse.click(...at(0.9, 0.95));   //  밖을 누르면 끝
  //  기호(★ 고르기)
  await page.click('.symb span');
  await page.click('.sympop button:has-text("★")');
  await page.mouse.click(...at(0.6, 0.75));
  ok(await count() === 9 - 1, '도형 8개(사각형·원·화살표·펜·형광펜·가리기·글상자·기호) — ' + await count());
  //  그림 붙여 넣기(Ctrl+V 와 같은 paste 사건)
  const png = fs.readFileSync(path.join(__dirname, '..', '..', 'label', 'winres', 'icon.png')).toString('base64');
  await R((b64) => {
    const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    const dt = new DataTransfer(); dt.items.add(new File([u], 'shot.png', { type: 'image/png' }));
    document.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }));
  }, png);
  await page.waitForFunction(() => window.__pdfReader.cur.ed.objs.some((o) => o.t === 'image'));
  ok(true, '그림 붙여 넣기(Ctrl+V)');
  ok((await page.textContent('.dt.on')).startsWith('●'), '탭에 「고침」 표시 ●');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, '1-고치기.png') });

  //  옮기기 · 지우기 · 되돌리기
  const rect0 = await R(() => { const o = window.__pdfReader.cur.ed.objs[0]; return [o.x, o.y]; });
  const c = at(0.25, 0.45);   //  사각형 위 테두리 근처 안쪽
  await page.mouse.click(...at(0.25, 0.5));
  await dragOn(at(0.25, 0.5), at(0.3, 0.52));
  const rect1 = await R(() => { const o = window.__pdfReader.cur.ed.objs[0]; return [o.x, o.y]; });
  ok(rect1[0] > rect0[0] + 10, '사각형 끌어 옮김 ' + rect0.map(Math.round) + ' → ' + rect1.map(Math.round));
  await page.keyboard.press('Delete');
  ok(await count() === 8, 'Delete 로 지움');
  await page.keyboard.press('Control+z');
  ok(await count() === 9, 'Ctrl+Z 로 되살림');
  await page.keyboard.press('Control+z');
  const rect2 = await R(() => { const o = window.__pdfReader.cur.ed.objs[0]; return [o.x, o.y]; });
  ok(Math.abs(rect2[0] - rect0[0]) < 0.01, '한 번 더 Ctrl+Z → 옮기기 전 자리');
  await page.keyboard.press('Control+y');
  //  색 바꾸기(고른 것에)
  await page.mouse.click(...at(0.3, 0.52));
  await page.$eval('#eSc', (e) => { e.value = '#0050ff'; e.dispatchEvent(new Event('input')); });
  ok(await R(() => window.__pdfReader.cur.ed.objs[0].sc) === '#0050ff', '선 색 바꿈(고른 도형)');

  //  저장(바이트)
  const b64 = await R(async () => {
    const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur);
    let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  });
  const saved = path.join(out, '고친 파일.pdf');
  fs.writeFileSync(saved, Buffer.from(b64, 'base64'));
  ok(fs.statSync(saved).size > 1000, '저장 ' + fs.statSync(saved).size + ' 바이트');
  //  다른 프로그램으로 확인 — pypdf(주석 종류) · poppler(그림으로 그려 보기)
  const kinds = execFileSync('python3', ['-c', `
import sys; from pypdf import PdfReader
r=PdfReader(sys.argv[1]); a=[x.get_object() for x in r.pages[0].get('/Annots',[])]
print(','.join(sorted(str(x['/Subtype'])[1:] for x in a)))
print(r.metadata.get('/Producer'))`, saved]).toString().trim().split('\n');
  console.log('   주석: ' + kinds[0] + ' · 변환기: ' + kinds[1]);
  ok(kinds[0] === 'Circle,FreeText,FreeText,Ink,Line,Square,Square,Square,Stamp', '표준 주석 9개(Square·Circle·Line·Ink·FreeText·Stamp)');
  ok(/한일특장/.test(kinds[1]), 'PDF 변환기에 한일특장(주)');
  execFileSync('pdftoppm', ['-r', '60', '-png', '-f', '1', '-l', '1', saved, path.join(out, 'poppler')]);
  const pp = fs.readdirSync(out).find((f) => f.startsWith('poppler') && f.endsWith('.png'));
  ok(!!pp, 'poppler(다른 프로그램)로 그림 만들기: ' + pp);

  //  다시 열기 → 고칠 수 있게 가져오기(pdf.js 는 그 주석을 그리지 않음 → 두 번 안 그려짐)
  await page.evaluate(() => { window.__pdfReader.cur.mod = false; });
  await page.keyboard.press('Control+w');
  await page.setInputFiles('#fOpen', saved);
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('고친'));
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas');
  await page.click('[data-cmd=tSel]');
  await page.waitForFunction(() => window.__pdfReader.cur.ed && window.__pdfReader.cur.ed.loaded);
  const back = await R(() => window.__pdfReader.cur.ed.objs.map((o) => o.t).sort().join(','));
  ok(back === 'arrow,ellipse,hilite,image,pen,rect,sym,text,white', '다시 열면 9개 모두 고칠 수 있게 돌아옴: ' + back);
  const txt = await R(() => window.__pdfReader.cur.ed.objs.find((o) => o.t === 'text').text);
  ok(txt === '검사 완료 OK\n한일특장 품질팀', '글상자 글 그대로: ' + JSON.stringify(txt));
  ok(await R(() => window.__pdfReader.cur.ed.managed.size) === 9, 'pdf.js 는 그 9개를 숨김(겹쳐 그리지 않음)');
  //  다시 저장해도 늘지 않음(바꿔 씀)
  const n2 = await R(async () => { const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur); return u.length; });
  ok(Math.abs(n2 - fs.statSync(saved).size) < 3000, '다시 저장해도 크기 같음 ' + n2);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, '2-다시열기.png') });

  //  다른 프로그램이 넣은 주석 고치기
  const other = path.join(out, '다른앱주석.pdf');
  execFileSync('python3', [path.join(__dirname, 'other-annots.py'), path.join(dir, 'A-002 적재함.pdf'), other]);
  await page.setInputFiles('#fOpen', other);
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('다른앱'));
  await page.click('[data-cmd=tSel]');
  await page.waitForFunction(() => window.__pdfReader.cur.ed && window.__pdfReader.cur.ed.loaded);
  const ot = await R(() => window.__pdfReader.cur.ed.objs.map((o) => o.t + (o.text ? ':' + o.text : '')).sort().join(','));
  ok(ot === 'ellipse,line,rect,text:other app note', '다른 프로그램 주석 4개를 고칠 수 있게 가져옴: ' + ot);
  const rb = await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.t === 'rect'); return [o.x, o.y, o.w, o.h].map(Math.round); });
  ok(Math.abs(rb[0] - 100) <= 2 && Math.abs(rb[2] - 150) <= 3, '사각형 자리·크기 맞음 ' + rb);

  ok(errs.length === 0, '화면 오류 없음');
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
