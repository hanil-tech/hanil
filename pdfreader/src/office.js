//  📄 Word·Excel 로 내보내기 — 프로그램 없이 docx·xlsx(=XML 묶음 ZIP)를 직접 만든다
//   Word 「글자로」: 줄마다 문단(왼쪽 여백·줄 간격·글자 크기를 원래와 비슷하게) → Word 에서 고칠 수 있음
//   Word 「모양 그대로」: 쪽마다 그림 한 장 → 보기는 원래와 똑같고 고치지는 못함
//   Excel: 쪽마다 시트 하나 · 글자 조각을 줄(y)·칸(x)으로 맞춰 표로 → 숫자는 숫자 칸
const X = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');
const enc = new TextEncoder();

//  글자 조각 → 줄들 [{ y, h, items:[{x, w, s, h}] }] (화면 좌표, 위에서 아래로)
export function lines(tc, vp) {
  const its = [];
  for (const it of tc.items) {
    if (!it.str || !it.str.trim()) continue;
    const [a, b, c, d, e, f] = it.transform;
    if (Math.abs(b) > Math.abs(a) * 0.3) continue;              //  세로·기운 글자는 건너뜀(표 맞추기용)
    const h = it.height || Math.hypot(c, d) || 10;
    const [x0, y0] = vp.convertToViewportPoint(e, f), [x1] = vp.convertToViewportPoint(e + it.width, f);
    its.push({ x: Math.min(x0, x1), w: Math.abs(x1 - x0), y: y0, h, s: it.str });
  }
  its.sort((p, q) => p.y - q.y || p.x - q.x);
  const out = [];
  for (const it of its) {
    const L = out[out.length - 1];
    if (L && Math.abs(L.y - it.y) < Math.max(L.h, it.h) * 0.45) { L.items.push(it); L.h = Math.max(L.h, it.h); }
    else out.push({ y: it.y, h: it.h, items: [it] });
  }
  for (const L of out) L.items.sort((p, q) => p.x - q.x);
  return out;
}
const lineText = (L) => {
  let s = '', end = -Infinity;
  for (const it of L.items) { if (s && it.x - end > it.h * 0.25 && !/\s$/.test(s)) s += ' '; s += it.s; end = it.x + it.w; }
  return s;
};

// ───────── Word ─────────
const ctypes = (img) => '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
  + (img ? '<Default Extension="jpeg" ContentType="image/jpeg"/>' : '') + '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>';
const rootRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>';
const core = (title, maker) => '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>' + X(title) + '</dc:title><dc:creator>' + X(maker) + '</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">' + new Date().toISOString().slice(0, 19) + 'Z</dcterms:created></cp:coreProperties>';
const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"';
const tw = (pt) => Math.max(0, Math.round(pt * 20));
const sect = (w, h, margin) => '<w:sectPr><w:pgSz w:w="' + tw(w) + '" w:h="' + tw(h) + '"' + (w > h ? ' w:orient="landscape"' : '') + '/><w:pgMar w:top="' + tw(margin) + '" w:right="' + tw(margin) + '" w:bottom="' + tw(margin) + '" w:left="' + tw(margin) + '" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>';
const run = (t, pt) => '<w:r><w:rPr><w:rFonts w:ascii="맑은 고딕" w:eastAsia="맑은 고딕" w:hAnsi="맑은 고딕"/><w:sz w:val="' + Math.max(8, Math.round(pt * 2)) + '"/></w:rPr><w:t xml:space="preserve">' + X(t) + '</w:t></w:r>';
const pageBreak = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>';

//  pages: [{ w, h, lines }] (글자로) 또는 [{ w, h, jpeg: Uint8Array }] (모양 그대로)
export function docx(pages, { title = '', maker = '' } = {}) {
  const files = [], rels = [], img = pages.some((p) => p.jpeg);
  let body = '';
  const margin = img ? 0 : 36;
  pages.forEach((p, k) => {
    if (k) body += pageBreak;
    if (p.jpeg) {
      const id = 'rIdImg' + (k + 1), cx = Math.round(p.w * 12700), cy = Math.round(p.h * 12700);
      rels.push('<Relationship Id="' + id + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/p' + (k + 1) + '.jpeg"/>');
      files.push({ name: 'word/media/p' + (k + 1) + '.jpeg', data: p.jpeg });
      body += '<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="' + cx + '" cy="' + cy + '"/><wp:docPr id="' + (k + 1) + '" name="쪽 ' + (k + 1) + '"/>'
        + '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="' + (k + 1) + '" name="p' + (k + 1) + '.jpeg"/><pic:cNvPicPr/></pic:nvPicPr>'
        + '<pic:blipFill><a:blip r:embed="' + id + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + cx + '" cy="' + cy + '"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>';
    } else {
      let prevBottom = margin;
      if (!p.lines.length) body += '<w:p/>';
      for (const L of p.lines) {
        const top = L.y - L.h;
        const before = Math.max(0, top - prevBottom);
        const left = Math.max(0, L.items[0].x - margin);
        body += '<w:p><w:pPr><w:spacing w:before="' + tw(before) + '" w:after="0" w:line="' + tw(L.h * 1.15) + '" w:lineRule="exact"/><w:ind w:left="' + tw(left) + '"/></w:pPr>' + run(lineText(L), L.h) + '</w:p>';
        prevBottom = L.y + L.h * 0.15;
      }
    }
  });
  const first = pages[0] || { w: 595, h: 842 };
  files.push({ name: '[Content_Types].xml', data: enc.encode(ctypes(img)) });
  files.push({ name: '_rels/.rels', data: enc.encode(rootRels) });
  files.push({ name: 'docProps/core.xml', data: enc.encode(core(title, maker)) });
  files.push({ name: 'word/_rels/document.xml.rels', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels.join('') + '</Relationships>') });
  files.push({ name: 'word/document.xml', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ' + W_NS + '><w:body>' + body + sect(first.w, first.h, margin) + '</w:body></w:document>') });
  return files.sort((a, b) => (b.name === '[Content_Types].xml') - (a.name === '[Content_Types].xml'));
}

// ───────── Excel ─────────
//  줄마다 글자 조각의 왼쪽 끝을 모아 칸(열)을 정한다 — 표 PDF 면 표 모양 그대로
export function table(ls) {
  const xs = [];
  for (const L of ls) for (const it of L.items) xs.push(it.x);
  xs.sort((a, b) => a - b);
  const cols = [];
  for (const x of xs) { if (!cols.length || x - cols[cols.length - 1].x > 6) cols.push({ x, n: 1 }); else cols[cols.length - 1].n++; }
  const colOf = (x) => { let k = 0; for (let j = 0; j < cols.length; j++) if (cols[j].x <= x + 3) k = j; return k; };
  return ls.map((L) => {
    const row = [];
    for (const it of L.items) { const c = colOf(it.x); row[c] = row[c] ? row[c] + ' ' + it.s.trim() : it.s.trim(); }
    return row;
  });
}
const colName = (n) => { let s = ''; n++; while (n) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; };
export function xlsx(sheets, { title = '', maker = '' } = {}) {
  const files = [];
  const ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    + sheets.map((_, k) => '<Override PartName="/xl/worksheets/sheet' + (k + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>').join('') + '</Types>';
  files.push({ name: '[Content_Types].xml', data: enc.encode(ct) });
  files.push({ name: '_rels/.rels', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>') });
  files.push({ name: 'docProps/core.xml', data: enc.encode(core(title, maker)) });
  files.push({ name: 'xl/workbook.xml', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
    + sheets.map((s, k) => '<sheet name="' + X(s.name.slice(0, 31)) + '" sheetId="' + (k + 1) + '" r:id="rId' + (k + 1) + '"/>').join('') + '</sheets></workbook>') });
  files.push({ name: 'xl/_rels/workbook.xml.rels', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + sheets.map((_, k) => '<Relationship Id="rId' + (k + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' + (k + 1) + '.xml"/>').join('')
    + '<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>') });
  files.push({ name: 'xl/styles.xml', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="10"/><name val="맑은 고딕"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>') });
  sheets.forEach((s, k) => {
    const widths = [];
    const rows = s.rows.map((row, r) => '<row r="' + (r + 1) + '">' + row.map((v, c) => {
      if (v == null || v === '') return '';
      widths[c] = Math.max(widths[c] || 6, Math.min(60, [...String(v)].reduce((a, ch) => a + (ch.charCodeAt(0) > 255 ? 2 : 1), 0) + 2));
      const ref = colName(c) + (r + 1), num = String(v).replace(/,/g, '');
      if (/^-?\d+(\.\d+)?$/.test(num) && num.length < 16 && !/^0\d/.test(num)) return '<c r="' + ref + '"><v>' + num + '</v></c>';
      return '<c r="' + ref + '" t="inlineStr"><is><t xml:space="preserve">' + X(v) + '</t></is></c>';
    }).join('') + '</row>').join('');
    const cols = widths.length ? '<cols>' + widths.map((w, c) => '<col min="' + (c + 1) + '" max="' + (c + 1) + '" width="' + (w || 8) + '" customWidth="1"/>').join('') + '</cols>' : '';
    files.push({ name: 'xl/worksheets/sheet' + (k + 1) + '.xml', data: enc.encode('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + cols + '<sheetData>' + rows + '</sheetData></worksheet>') });
  });
  return files;
}
