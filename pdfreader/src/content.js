//  ✏️ 원래 글자 고치기 — 페이지 내용(content stream)에서 그 글자를 지우고 새 글자를 써 넣는다
//   · 내용을 낱말(토큰)로 읽고 그래픽 상태(cm·q·Q)와 글자 행렬(BT·Tm·Td·T*·Tf…)을 따라가며
//     글자 그리기(Tj·TJ·'·")가 시작하는 자리를 페이지 좌표로 구한다.
//   · 고칠 네모 안에서 시작하는 글자 그리기는 「글자 없이 같은 폭만큼 옮기기」([-폭] TJ)로 바꾼다
//     → 같은 줄의 뒤 글자들이 제자리에 남는다(폭은 글꼴의 Widths·W 로 계산).
//   ⚠ 폼(XObject) 안의 글자는 건드리지 않는다 — 못 찾으면 흰 상자로 덮는다(부르는 쪽이).
import { PDFName, PDFArray, PDFDict, PDFRef, PDFNumber, PDFRawStream, decodePDFRawStream } from 'pdf-lib';

const N = (s) => PDFName.of(s);
const WS = new Set([0, 9, 10, 12, 13, 32]);
const DELIM = new Set([40, 41, 60, 62, 91, 93, 123, 125, 47, 37]);

//  바이트 → 토큰 [{ k:'num'|'name'|'str'|'hex'|'['|']'|'<<'|'>>'|'op'|'img', v, s, e }]
export function tokenize(b) {
  const out = [];
  let i = 0;
  const n = b.length;
  while (i < n) {
    const c = b[i];
    if (WS.has(c)) { i++; continue; }
    if (c === 37) { while (i < n && b[i] !== 10 && b[i] !== 13) i++; continue; }
    const s = i;
    if (c === 40) {                                        //  ( 글 )
      let depth = 1; i++;
      const bytes = [];
      while (i < n && depth) {
        let ch = b[i];
        if (ch === 92) {
          i++; ch = b[i];
          const map = { 110: 10, 114: 13, 116: 9, 98: 8, 102: 12, 40: 40, 41: 41, 92: 92 };
          if (map[ch] != null) { bytes.push(map[ch]); i++; }
          else if (ch >= 48 && ch <= 55) { let v = 0, k = 0; while (k < 3 && b[i] >= 48 && b[i] <= 55) { v = v * 8 + b[i] - 48; i++; k++; } bytes.push(v & 255); }
          else if (ch === 13 || ch === 10) { i++; if (ch === 13 && b[i] === 10) i++; }
          else { bytes.push(ch); i++; }
          continue;
        }
        if (ch === 40) depth++;
        if (ch === 41 && --depth === 0) { i++; break; }
        bytes.push(ch); i++;
      }
      out.push({ k: 'str', v: bytes, s, e: i });
      continue;
    }
    if (c === 60 && b[i + 1] === 60) { out.push({ k: '<<', s, e: i + 2 }); i += 2; continue; }
    if (c === 62 && b[i + 1] === 62) { out.push({ k: '>>', s, e: i + 2 }); i += 2; continue; }
    if (c === 60) {                                        //  < 16진 >
      i++; let hex = '';
      while (i < n && b[i] !== 62) { if (!WS.has(b[i])) hex += String.fromCharCode(b[i]); i++; }
      i++;
      if (hex.length % 2) hex += '0';
      const bytes = [];
      for (let k = 0; k < hex.length; k += 2) bytes.push(parseInt(hex.slice(k, k + 2), 16));
      out.push({ k: 'str', v: bytes, s, e: i });
      continue;
    }
    if (c === 91 || c === 93) { out.push({ k: c === 91 ? '[' : ']', s, e: i + 1 }); i++; continue; }
    if (c === 47) {
      i++; let v = '';
      while (i < n && !WS.has(b[i]) && !DELIM.has(b[i])) { v += String.fromCharCode(b[i]); i++; }
      out.push({ k: 'name', v, s, e: i });
      continue;
    }
    let w = '';
    while (i < n && !WS.has(b[i]) && !DELIM.has(b[i])) { w += String.fromCharCode(b[i]); i++; }
    if (!w) { i++; continue; }
    if (/^[+-]?(\d+\.?\d*|\.\d+)$/.test(w)) { out.push({ k: 'num', v: parseFloat(w), s, e: i }); continue; }
    if (w === 'BI') {                                      //  인라인 그림 — EI 까지 통째로 건너뜀
      let j = i;
      while (j < n - 2) { if (WS.has(b[j]) && b[j + 1] === 69 && b[j + 2] === 73 && (j + 3 >= n || WS.has(b[j + 3]))) break; j++; }
      out.push({ k: 'img', s, e: j + 3 }); i = j + 3;
      continue;
    }
    out.push({ k: 'op', v: w, s, e: i });
  }
  return out;
}

const mul = (a, b) => [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]];

//  글꼴 정보 — 코드 크기(1·2 바이트)와 폭(1000 단위)
function fontInfo(doc, res, name, cache) {
  if (cache.has(name)) return cache.get(name);
  const ctx = doc.context;
  const lk = (v) => (v instanceof PDFRef ? ctx.lookup(v) : v);
  const num = (v, d) => { v = lk(v); return v instanceof PDFNumber ? v.asNumber() : d; };
  let info = { two: false, w: () => 500 };
  try {
    const fonts = lk(res && res.get(N('Font')));
    const f = fonts instanceof PDFDict ? lk(fonts.get(N(name))) : null;
    if (f instanceof PDFDict) {
      const sub = String(f.get(N('Subtype')) || '');
      if (sub === '/Type0') {
        const desc = lk(f.get(N('DescendantFonts'))), df = desc instanceof PDFArray ? lk(desc.get(0)) : null;
        const dw = df ? num(df.get(N('DW')), 1000) : 1000, map = new Map();
        const W = df ? lk(df.get(N('W'))) : null;
        if (W instanceof PDFArray) {
          const a = W.asArray().map(lk);
          for (let k = 0; k < a.length;) {
            const c0 = num(a[k], 0);
            if (a[k + 1] instanceof PDFArray) { a[k + 1].asArray().forEach((x, j) => map.set(c0 + j, num(x, dw))); k += 2; }
            else { const c1 = num(a[k + 1], c0), w = num(a[k + 2], dw); for (let c = c0; c <= c1; c++) map.set(c, w); k += 3; }
          }
        }
        info = { two: true, w: (code) => (map.has(code) ? map.get(code) : dw) };
      } else {
        const fc = num(f.get(N('FirstChar')), 0), Wd = lk(f.get(N('Widths')));
        const arr = Wd instanceof PDFArray ? Wd.asArray().map((x) => num(x, 0)) : null;
        const desc = lk(f.get(N('FontDescriptor')));
        const miss = desc instanceof PDFDict ? num(desc.get(N('MissingWidth')), 500) : 500;
        info = { two: false, w: (code) => (arr && code - fc >= 0 && code - fc < arr.length ? arr[code - fc] : miss) };
      }
    }
  } catch {}
  cache.set(name, info);
  return info;
}

//  page: pdf-lib PDFPage · rects: [[x0,y0,x1,y1]] (페이지 좌표) → 지운 글자 그리기 수
export function eraseTextIn(doc, page, rects) {
  const ctx = doc.context;
  const lk = (v) => (v instanceof PDFRef ? ctx.lookup(v) : v);
  page.node.normalize();
  const contents = page.node.Contents();
  if (!contents) return 0;
  const parts = [];
  for (const r of contents.asArray()) {
    const st = lk(r);
    if (!(st instanceof PDFRawStream)) continue;
    let bytes;
    try { bytes = st.dict.get(N('Filter')) ? decodePDFRawStream(st).decode() : st.getContents(); } catch { return 0; }
    parts.push(bytes);
  }
  const len = parts.reduce((a, p) => a + p.length + 1, 0);
  const src = new Uint8Array(len);
  let o = 0;
  for (const p of parts) { src.set(p, o); o += p.length; src[o++] = 10; }
  const toks = tokenize(src);
  const res = page.node.Resources();
  const cache = new Map();
  let ctm = [1, 0, 0, 1, 0, 0];
  const stack = [];
  let Tm = [1, 0, 0, 1, 0, 0], Tlm = [1, 0, 0, 1, 0, 0];
  let font = null, fs = 1, Tc = 0, Tw = 0, Th = 1, TL = 0, Ts = 0;
  const repl = [];                                         //  [s, e, 바꿀 글]
  let args = [], argStart = -1;
  const inRect = (x, y) => rects.some(([x0, y0, x1, y1]) => x >= x0 && x <= x1 && y >= y0 && y <= y1);
  const advance = (codes) => {
    //  글자들의 폭(글자 공간) — Tc·Tw 포함
    const fi = font ? fontInfo(doc, res, font, cache) : { two: false, w: () => 500 };
    let tx = 0;
    const b = codes;
    for (let k = 0; k < b.length; k += fi.two ? 2 : 1) {
      const code = fi.two ? (b[k] << 8) | (b[k + 1] || 0) : b[k];
      tx += (fi.w(code) / 1000) * fs + Tc + (!fi.two && code === 32 ? Tw : 0);
    }
    return tx * Th;
  };
  const show = (arr, opS, opE, prefix) => {
    //  arr: [바이트[] | 숫자] · 시작 자리를 보고, 지울지 정한 뒤 글자 행렬을 민다
    const M = mul([1, 0, 0, 1, 0, Ts], mul(Tm, ctm));
    const x = M[4], y = M[5];
    let total = 0;
    for (const a of arr) total += Array.isArray(a) ? advance(a) : (-a / 1000) * fs * Th;
    if (inRect(x, y)) {
      const units = fs * Th ? (-total / (fs * Th)) * 1000 : 0;
      repl.push([opS, opE, prefix + '[' + (Math.round(units * 1000) / 1000) + '] TJ']);
    }
    Tm = mul([1, 0, 0, 1, total, 0], Tm);
  };
  for (let k = 0; k < toks.length; k++) {
    const t = toks[k];
    if (t.k !== 'op') {
      if (argStart < 0) argStart = t.s;
      if (t.k === '[') {                                   //  배열은 통째로 하나의 값
        const arr = [];
        k++;
        while (k < toks.length && toks[k].k !== ']') { const u = toks[k]; if (u.k === 'num') arr.push(u.v); else if (u.k === 'str') arr.push(u.v); k++; }
        args.push(arr);
      } else if (t.k === '<<') {
        let depth = 1; k++;
        while (k < toks.length && depth) { if (toks[k].k === '<<') depth++; else if (toks[k].k === '>>') depth--; k++; }
        k--; args.push(null);
      } else args.push(t.k === 'num' || t.k === 'str' || t.k === 'name' ? t.v : null);
      continue;
    }
    const op = t.v, A = args, opS = argStart < 0 ? t.s : argStart, opE = t.e;
    args = []; argStart = -1;
    switch (op) {
      case 'q': stack.push(ctm); break;
      case 'Q': ctm = stack.pop() || [1, 0, 0, 1, 0, 0]; break;
      case 'cm': if (A.length >= 6) ctm = mul(A.slice(-6), ctm); break;
      case 'BT': Tm = [1, 0, 0, 1, 0, 0]; Tlm = Tm; break;
      case 'Tf': font = A[0]; fs = A[1] || 1; break;
      case 'Tc': Tc = A[0] || 0; break;
      case 'Tw': Tw = A[0] || 0; break;
      case 'Tz': Th = (A[0] || 100) / 100; break;
      case 'TL': TL = A[0] || 0; break;
      case 'Ts': Ts = A[0] || 0; break;
      case 'Td': Tlm = mul([1, 0, 0, 1, A[0] || 0, A[1] || 0], Tlm); Tm = Tlm; break;
      case 'TD': TL = -(A[1] || 0); Tlm = mul([1, 0, 0, 1, A[0] || 0, A[1] || 0], Tlm); Tm = Tlm; break;
      case 'Tm': if (A.length >= 6) { Tlm = A.slice(-6); Tm = Tlm; } break;
      case 'T*': Tlm = mul([1, 0, 0, 1, 0, -TL], Tlm); Tm = Tlm; break;
      case 'Tj': if (Array.isArray(A[0])) show([A[0]], opS, opE, ''); break;
      case 'TJ': if (Array.isArray(A[0])) show(A[0], opS, opE, ''); break;
      case "'": Tlm = mul([1, 0, 0, 1, 0, -TL], Tlm); Tm = Tlm; if (Array.isArray(A[0])) show([A[0]], opS, opE, 'T* '); break;
      case '"': Tw = A[0] || 0; Tc = A[1] || 0; Tlm = mul([1, 0, 0, 1, 0, -TL], Tlm); Tm = Tlm; if (Array.isArray(A[2])) show([A[2]], opS, opE, A[0] + ' Tw ' + A[1] + ' Tc T* '); break;
      default: break;
    }
  }
  if (!repl.length) return 0;
  //  바꾼 내용으로 새 내용 하나(압축)
  const pieces = [];
  let last = 0;
  const lat = (a, b) => { let s = ''; for (let k = a; k < b; k += 0x8000) s += String.fromCharCode.apply(null, src.subarray(k, Math.min(b, k + 0x8000))); return s; };
  for (const [s, e, r] of repl) { pieces.push(lat(last, s), ' ' + r + ' '); last = e; }
  pieces.push(lat(last, src.length));
  const text = pieces.join('');
  const bytes = new Uint8Array(text.length);
  for (let k = 0; k < text.length; k++) bytes[k] = text.charCodeAt(k) & 255;
  const ref = ctx.register(ctx.flateStream(bytes));
  page.node.set(N('Contents'), ctx.obj([ref]));
  return repl.length;
}
