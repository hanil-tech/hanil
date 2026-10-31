//  상용 편집기 기능 시험 — node test/pro-check.js <시험 PDF 폴더> <결과 폴더>
//   구름·다각형·꺾은선·설명선·측정(축척)·링크 → 저장(pypdf 로 종류 확인) → 다시 열기
//   교정(찾아서 → 적용, 글자가 정말 사라졌나) · 평탄화 · 머리글/바닥글·Bates · 책갈피 · 문서 속성 · 결합 · 분할 · 비교 · 인쇄 범위 · 주석 목록
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
  const page = await b.newPage({ viewport: { width: 1600, height: 950 }, acceptDownloads: true });
  const errs = [];
  page.on('pageerror', (e) => { errs.push(e.message); console.log('   ⚠ ' + e.message); });
  await page.goto('file://' + path.join(__dirname, '..', 'out', 'hanil-pdf-reader.html'));
  const R = (f, a) => page.evaluate(f, a);
  const save = async (name) => {
    const b64 = await R(async () => { const u = await window.__pdfReader.buildPdf(window.__pdfReader.cur); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); });
    const f = path.join(out, name); fs.writeFileSync(f, Buffer.from(b64, 'base64')); return f;
  };
  const okModal = async () => { await page.waitForSelector('#modal.on'); await page.click('#mFoot button:first-child'); };
  const done = () => page.waitForFunction(() => /끝|굳혔|바꿨|나눴/.test(document.querySelector('#toast').textContent), null, { timeout: 30000 });
  await page.setInputFiles('#fOpen', path.join(dir, 'A-002 적재함.pdf'));
  await page.waitForSelector('.pg[data-i="0"] canvas');
  await page.click('.rt[data-rt=view]'); await page.click('#ribbon [data-cmd=page]');
  await page.click('.rt[data-rt=edit]');
  const bx = await (await page.$('.pg[data-i="0"]')).boundingBox();
  const at = (fx, fy) => [bx.x + bx.width * fx, bx.y + bx.height * fy];
  const n = () => R(() => window.__pdfReader.cur.ed.objs.length);

  //  구름(꼭짓점 4개 → 두 번 누름)
  await page.click('#ribbon [data-cmd=tCloud]');
  await page.waitForSelector('.pg[data-i="0"] .ov');
  for (const [x, y] of [[0.1, 0.3], [0.4, 0.3], [0.4, 0.45]]) await page.mouse.click(...at(x, y));
  await page.mouse.dblclick(...at(0.1, 0.45));
  ok(await R(() => { const o = window.__pdfReader.cur.ed.objs.at(-1); return o.t === 'poly' && o.kind === 'cloud' && o.vs.length === 4; }), '구름: 꼭짓점 4개');
  //  꺾은선(Enter 로 끝)
  await page.click('#ribbon [data-cmd=tPolyline]');
  for (const [x, y] of [[0.5, 0.3], [0.6, 0.4], [0.7, 0.3]]) await page.mouse.click(...at(x, y));
  await page.keyboard.press('Enter');
  ok(await R(() => { const o = window.__pdfReader.cur.ed.objs.at(-1); return o.kind === 'polyline' && o.vs.length === 3; }), '꺾은선: 꼭짓점 3개(Enter)');
  //  설명선
  await page.click('#ribbon [data-cmd=tCallout]');
  await page.mouse.move(...at(0.2, 0.6)); await page.mouse.down(); await page.mouse.move(...at(0.35, 0.5), { steps: 4 }); await page.mouse.up();
  await page.waitForSelector('.tedit');
  await page.keyboard.type('볼트 교체 필요');
  await page.mouse.click(...at(0.95, 0.97));
  ok(await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.t === 'callout'); return o && o.text === '볼트 교체 필요'; }), '설명선: 글 「볼트 교체 필요」');
  //  거리 측정 + 축척
  await page.click('#ribbon [data-cmd=tMDist]');
  await page.mouse.move(...at(0.1, 0.75)); await page.mouse.down(); await page.mouse.move(...at(0.5, 0.75), { steps: 4 }); await page.mouse.up();
  const lab1 = await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.meas === 'dist'); return window.__pdfReader.EDIT.measLabel(o); });
  await page.click('#ribbon [data-cmd=mScale]');
  await page.waitForSelector('#modal.on #mIn'); await page.fill('#mIn', '1000'); await page.keyboard.press('Enter');
  const lab2 = await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.meas === 'dist'); return window.__pdfReader.EDIT.measLabel(o); });
  ok(/mm/.test(lab1) && lab2.startsWith('1,000 mm'), '거리: ' + lab1 + ' → 실제 길이 1000mm 로 축척 맞춤: ' + lab2);
  //  면적
  await page.click('#ribbon [data-cmd=tMArea]');
  for (const [x, y] of [[0.55, 0.6], [0.75, 0.6], [0.75, 0.8]]) await page.mouse.click(...at(x, y));
  await page.mouse.dblclick(...at(0.55, 0.8));
  ok(await R(() => { const o = window.__pdfReader.cur.ed.objs.find((x) => x.meas === 'area'); return o && /m²|mm²/.test(window.__pdfReader.EDIT.measLabel(o)); }), '면적: ' + await R(() => window.__pdfReader.EDIT.measLabel(window.__pdfReader.cur.ed.objs.find((x) => x.meas === 'area'))));
  //  링크(쪽 2)
  await page.click('#ribbon [data-cmd=tLink]');
  await page.mouse.move(...at(0.6, 0.88)); await page.mouse.down(); await page.mouse.move(...at(0.8, 0.93), { steps: 3 }); await page.mouse.up();
  await page.waitForSelector('#modal.on #mIn'); await page.fill('#mIn', '2'); await page.keyboard.press('Enter');
  ok(await R(() => window.__pdfReader.cur.ed.objs.some((o) => o.t === 'link' && o.page === 1)), '링크: 2쪽으로');
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, '1-새도형.png') });
  let f = await save('새도형.pdf');
  const kinds = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print(",".join(sorted(str(a.get_object()["/Subtype"])[1:]+("/"+str(a.get_object().get("/IT","")))[1:] if a.get_object().get("/IT") else str(a.get_object()["/Subtype"])[1:] for a in r.pages[0]["/Annots"])))', f);
  console.log('   주석: ' + kinds);
  ok(/Polygon/.test(kinds) && /PolyLine/.test(kinds) && /FreeTextCallout/.test(kinds) && /LineDimension/.test(kinds) && /PolygonDimension/.test(kinds) && /Link/.test(kinds), '표준 주석: Polygon(구름)·PolyLine·FreeText(설명선)·Line(거리)·Polygon(면적)·Link');
  execFileSync('pdftoppm', ['-r', '60', '-png', '-f', '1', '-l', '1', f, path.join(out, 'poppler-new')]);
  //  다시 열기
  await R(() => { window.__pdfReader.cur.mod = false; });
  await page.keyboard.press('Control+w');
  await page.setInputFiles('#fOpen', f);
  await page.waitForFunction(() => window.__pdfReader.cur && window.__pdfReader.cur.name.includes('새도형'));
  await page.click('.rt[data-rt=review]');
  await page.click('#ribbon [data-cmd=rvList]');
  await page.waitForSelector('#comments .cmr');
  const cl = await page.$$eval('#comments .cmr b', (x) => x.map((e) => e.textContent).sort().join(','));
  ok(cl === '거리,구름,꺾은선,링크,면적,설명선', '다시 열면 주석 목록에 6개: ' + cl);
  const back = await R(() => window.__pdfReader.cur.ed.objs.find((o) => o.t === 'callout').text);
  ok(back === '볼트 교체 필요', '설명선 글 그대로');
  //  주석 요약 CSV
  const dl = page.waitForEvent('download'); await page.click('#ribbon [data-cmd=rvCsv]'); const csv = fs.readFileSync(await (await dl).path(), 'utf8');
  ok(csv.split('\r\n').length === 7 && csv.includes('설명선'), '주석 요약(CSV) 6줄');
  //  평탄화 → 주석이 페이지 내용으로(링크만 남음)
  await page.click('#ribbon [data-cmd=flatten]'); await okModal(); await done();
  f = await save('평탄화.pdf');
  ok(py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print(",".join(str(a.get_object()["/Subtype"])[1:] for a in r.pages[0].get("/Annots",[])))', f) === 'Link', '평탄화: 주석이 페이지에 굳고 링크만 남음');
  execFileSync('pdftoppm', ['-r', '60', '-png', '-f', '1', '-l', '1', f, path.join(out, 'poppler-flat')]);

  //  교정: 「브래킷」 찾아 표시 → 적용 → 그 쪽 글자에 없어야
  await page.setInputFiles('#fOpen', path.join(dir, 'A-001 섀시 부품표.pdf'));
  await page.waitForFunction(() => window.__pdfReader.cur.name.includes('A-001'));
  await page.click('.rt[data-rt=prot]');
  await page.click('#ribbon [data-cmd=rdFind]');
  await page.waitForSelector('#modal.on #mIn'); await page.fill('#mIn', '40396607-5'); await page.keyboard.press('Enter');
  await page.waitForFunction(() => window.__pdfReader.cur.ed && window.__pdfReader.cur.ed.objs.filter((o) => o.t === 'redact').length >= 2);
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(out, '2-교정표시.png') });
  await page.click('#ribbon [data-cmd=rdApply]'); await okModal(); await done();
  f = await save('교정.pdf');
  const txt = py('import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print("|".join((p.extract_text() or "").replace("\\n"," ") for p in r.pages))', f);
  ok(!/40396607\s*-\s*5/.test(txt), '교정 적용: 「40396607-5」가 파일 글자에서 사라짐(그 쪽은 그림이 됨)');
  execFileSync('pdftoppm', ['-r', '60', '-png', '-f', '1', '-l', '1', f, path.join(out, 'poppler-redact')]);

  //  머리글·바닥글 + Bates · 문서 속성 · 책갈피
  await page.click('.rt[data-rt=org]');
  await page.click('#ribbon [data-cmd=pHF]');
  await page.waitForSelector('#hftl'); await page.fill('#hftl', '한일특장(주) 설계팀'); await okModal(); await done();
  await page.click('#ribbon [data-cmd=pBates]'); await page.waitForSelector('#hfprefix'); await page.fill('#hfprefix', 'HN-'); await okModal(); await done();
  await page.click('.rt[data-rt=prot]');
  await page.click('#ribbon [data-cmd=propsEdit]'); await page.waitForSelector('#mpT'); await page.fill('#mpT', '섀시 부품표 (교정본)'); await page.fill('#mpA', '김설계'); await okModal();
  await page.click('.rt[data-rt=bm]');
  await page.click('#ribbon [data-cmd=bmAuto]'); await page.waitForTimeout(800);
  f = await save('머리글·책갈피.pdf');
  const info = py(`import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print(r.metadata.title,"|",r.metadata.author,"|",len(r.outline),"|",len(r.pages[1].images))`, f);
  console.log('   ' + info);
  ok(info.startsWith('섀시 부품표 (교정본) | 김설계 | 3'), '문서 속성(제목·작성자) · 책갈피 3개(쪽마다)');
  execFileSync('pdftoppm', ['-r', '70', '-png', '-f', '2', '-l', '2', f, path.join(out, 'poppler-hf')]);
  ok(fs.readdirSync(out).some((x) => x.startsWith('poppler-hf')), '머리글·바닥글·Bates 페이지 그림');

  //  결합 · 분할 · 비교
  await page.click('.rt[data-rt=conv]');
  await page.click('#ribbon [data-cmd=combine]'); await page.waitForSelector('#cbList .cbrow'); await okModal();
  await page.waitForFunction(() => /^결합/.test(window.__pdfReader.cur.name));
  const tot = await R(() => window.__pdfReader.docs.filter((d) => !/^결합/.test(d.name)).reduce((a, d) => a + d.n, 0));
  ok(await R(() => window.__pdfReader.cur.n) === tot, '파일 결합: 열린 문서 ' + tot + '쪽 → 하나로');
  const dl2 = page.waitForEvent('download'); await page.click('#ribbon [data-cmd=split]'); await page.waitForSelector('#modal.on #mIn'); await page.fill('#mIn', '2'); await page.keyboard.press('Enter');
  const z = await dl2; const zp = path.join(out, 'split.zip'); await z.saveAs(zp);
  ok(py('import sys,zipfile;print(len(zipfile.ZipFile(sys.argv[1]).namelist()))', zp) === String(Math.ceil(tot / 2)), '문서 분할: 2쪽마다 → ' + Math.ceil(tot / 2) + '개');
  //  비교: A-001 원본 ↔ 교정본(번호 -5 가 빠진 쪽)
  fs.copyFileSync(path.join(dir, 'A-001 섀시 부품표.pdf'), path.join(out, '원본.pdf'));
  await page.setInputFiles('#fOpen', path.join(out, '원본.pdf'));
  await page.setInputFiles('#fOpen', path.join(out, '교정.pdf'));
  await page.click('.dt:has-text("원본.pdf")');
  await page.click('.rt[data-rt=review]');
  await page.click('#ribbon [data-cmd=compare]');
  await page.waitForSelector('#cmpSel');
  const opt = await page.$$eval('#cmpSel option', (os) => os.find((o) => o.textContent.includes('교정.pdf')).value);
  await page.selectOption('#cmpSel', opt); await okModal();
  await page.waitForFunction(() => /다른 곳/.test(document.querySelector('#sstat').textContent));
  const cmp = await page.textContent('#sstat');
  ok(/다른 곳 [1-9]/.test(cmp), '문서 비교: ' + cmp.split('\n')[1]);
  await page.screenshot({ path: path.join(out, '3-비교.png') });

  ok(errs.length === 0, '화면 오류 없음');
  await b.close();
  console.log(fails ? '\n❌ ' + fails + '개 실패' : '\n모두 통과');
  process.exit(fails ? 1 : 0);
})();
