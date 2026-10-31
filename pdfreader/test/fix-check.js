//  고친 버그가 다시 생기지 않나 — node test/fix-check.js <make-fix.py 폴더> <결과 폴더>
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const dir = path.resolve(process.argv[2]);
const out = path.resolve(process.argv[3]);
fs.mkdirSync(out, { recursive: true });
let fails = 0;
const ok = (c, m) => { console.log((c ? '✅ ' : '❌ ') + m); if (!c) fails++; };
const py = (code, ...a) => execFileSync('python3', ['-c', code, ...a]).toString().trim();

(async () => {
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 1400, height: 900 } });
  page.on('pageerror', (e) => { fails++; console.log('   ⚠ ' + e.message); });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  const R = (f, a) => page.evaluate(f, a);
  const save = async (name) => {
    const b64 = await R(async () => { const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); });
    const f = path.join(out, name); fs.writeFileSync(f, Buffer.from(b64, 'base64')); return f;
  };
  const open = async (name) => { await page.setInputFiles('#fOpen', path.join(dir, name)); await page.waitForFunction((n) => window.__pdfReader.cur && window.__pdfReader.cur.name === n, name); await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] canvas'); };
  const done = () => page.waitForFunction(() => /끝/.test(document.querySelector('#toast').textContent), null, { timeout: 30000 });

  //  ① 시작 화면 — 큰 단추·최근 파일
  ok(await page.isVisible('.start .stbtns button[data-cmd=open]'), '시작 화면: 「PDF 열기」 큰 단추');
  //  ② 지운 쪽의 글자가 파일 안에 남지 않음
  await open('비밀3쪽.pdf');
  await page.click('.th[data-i="1"]');
  await page.click('#ribbon [data-cmd=pDel]');
  await page.waitForSelector('#modal.on'); await page.click('#mFoot button:first-child');
  await done();
  let f = await save('쪽삭제.pdf');
  const leak = py(`import sys,re,zlib
b=open(sys.argv[1],'rb').read(); found=b'SECRET' in b
for m in re.finditer(rb'stream\\r?\\n(.*?)endstream', b, re.S):
    try: found = found or b'SECRET' in zlib.decompress(m.group(1))
    except Exception: pass
print(found)`, f);
  ok(leak === 'False' && py('import sys;from pypdf import PdfReader;print(len(PdfReader(sys.argv[1]).pages))', f) === '2', '쪽 삭제: 지운 쪽의 「SECRET」이 파일 어디에도 없음(2쪽)');
  //  ③ 두 번 빨리 눌러도 한 번만(겹치지 않음)
  await R(() => { window.__pdfReader.cur.mod = false; });
  //  ④ 다른 사람이 단 주석 — 손대지 않으면 그대로, 고쳐도 메모·작성자·답글 유지
  await open('검토주석.pdf');
  await R(async () => { await window.__pdfReader.EDIT.ensureLoaded(window.__pdfReader.cur); });
  await page.click('#ribbon [data-cmd=pRotR]').catch(() => {});
  await done();
  f = await save('주석그대로.pdf');
  const chk = `import sys
from pypdf import PdfReader
a=PdfReader(sys.argv[1]).pages[0]['/Annots']
sq=[x.get_object() for x in a if x.get_object()['/Subtype']=='/Square'][0]
rp=[x.get_object() for x in a if x.get_object()['/Subtype']=='/Text'][0]
print(sq.get('/Contents'),'|',sq.get('/T'),'|',rp['/IRT'].get_object().get('/NM'),'|',list(sq.get('/C')))`;
  let r = py(chk, f);
  console.log('   ' + r);
  ok(/^reviewer comment KIM \| Kim Reviewer \| sq-1/.test(r), '쪽 회전 뒤에도 남의 주석: 메모·작성자·답글 그대로');
  await R(() => { const d = window.__pdfReader.cur; const o = d.ed.objs.find((x) => x.t === 'rect'); o.sc = '#00ff00'; d.mod = true; });
  f = await save('주석고침.pdf');
  r = py(chk, f);
  console.log('   ' + r);
  ok(/^reviewer comment KIM \| Kim Reviewer \| sq-1 \| \[0(\.0)?, 1(\.0)?, 0(\.0)?\]/.test(r), '남의 주석 색을 바꿔도: 메모·작성자·답글(IRT) 유지, 색은 초록');
  await R(() => { window.__pdfReader.cur.mod = false; });
  //  ⑤ 한 TJ 안의 두 칸 — 앞 칸만 고치면 뒤 칸은 남는다
  await open('표TJ.pdf');
  await page.waitForSelector('.doc:not([style*="none"]) .pg[data-i="0"] .textLayer span');
  const items = await R(() => [...document.querySelectorAll('.doc:not([style*="none"]) .pg[data-i="0"] .textLayer span')].map((s) => s.textContent));
  console.log('   글자 조각: ' + JSON.stringify(items));
  await page.click('.rt[data-rt=home]');
  await page.click('#ribbon [data-cmd=tTEdit]');
  await page.locator('.doc:not([style*="none"]) .pg[data-i="0"] .textLayer span', { hasText: /^Qty/ }).first().click();
  await page.waitForSelector('.tedit-in');
  await page.fill('.tedit-in', items.some((x) => /Price/.test(x) && !/Qty/.test(x)) ? 'Amount' : 'Amount     Price');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(200);
  f = await save('TJ고침.pdf');
  const t = py('import sys;from pypdf import PdfReader;print(PdfReader(sys.argv[1]).pages[0].extract_text().replace(chr(10)," | "))', f);
  console.log('   ' + t);
  ok(/Amount/.test(t) && /Price/.test(t) && !/Qty/.test(t) && /Other line/.test(t), '글자 고치기: 「Qty」만 바뀌고 같은 줄 「Price」·다른 줄은 그대로');
  execFileSync('pdftoppm', ['-r', '60', '-png', f, path.join(out, 'tj')]);
  await R(() => { window.__pdfReader.cur.mod = false; });
  //  ⑥ 확인 창이 다른 창에 밀려나면 「예」가 아니라 취소
  const before = await R(() => window.__pdfReader.cur.n);
  await page.click('.th[data-i="0"]');
  await page.click('#ribbon [data-cmd=pDel]').catch(() => {});
  await page.waitForTimeout(200);
  //  깨진 파일을 열어 「열 수 없음」 창이 확인 창을 밀어냄
  await page.setInputFiles('#fOpen', { name: '깨짐.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 broken') });
  await page.waitForFunction(() => /열 수 없음/.test(document.querySelector('#mTitle').textContent));
  await page.click('#mFoot button:first-child');
  await page.waitForTimeout(500);
  ok(await R(() => window.__pdfReader.cur.n) === before, '밀려난 「지울까요?」 창은 지우지 않음');
  await b.close();
  console.log(fails ? '❌ 실패 ' + fails : '모두 통과');
  process.exit(fails ? 1 : 0);
})();
