//  ✏️ 고치기 — 사각형·원·선·화살표·펜·형광펜·글상자·기호·이미지·가리기
//   ⭐ PDF 표준 주석으로 저장한다(Square·Circle·Line·Ink·FreeText·Stamp + 모양(AP)) →
//      Acrobat·PDF-XChange 같은 상용 프로그램에서도 그대로 보이고 옮기고 지울 수 있다.
//   ⭐ 거꾸로, 상용 프로그램이 넣은 같은 종류의 주석도 열어서 고칠 수 있다(pdf-lib 로 읽음).
//      고칠 수 있게 가져온 주석은 pdf.js 가 그리지 않게 숨기고(modifiedIds) 우리 겹(SVG)이 그린다.
//   좌표: 페이지를 「제 방향·배율 1」로 본 화면 좌표(왼쪽 위 0,0 · 아래로 +, 단위 pt). 저장할 때 PDF 좌표로 바꾼다.
import {
  PDFDocument, PDFName, PDFArray, PDFDict, PDFRef, PDFHexString, PDFString, PDFNumber, PDFRawStream, decodePDFRawStream,
} from 'pdf-lib';

export const EDIT_TOOLS = ['edit', 'rect', 'ellipse', 'line', 'arrow', 'pen', 'hilite', 'white', 'text', 'type', 'under', 'sym', 'stamp', 'note', 'snap', 'crop', 'erase', 'mhl', 'mul', 'mso',
  'polygon', 'polyline', 'cloud', 'mdist', 'mperim', 'marea', 'callout', 'link', 'redact'];
//  글자 위에 긋는 표시(강조·밑줄·취소선) — 글자를 끌어 고르면 그 줄들에 생긴다
export const MARK_TOOLS = { mhl: ['hl', '#ffeb3b'], mul: ['ul', '#1a73e8'], mso: ['so', '#e5262e'] };
//  스탬프 — 빨간 테두리 도장(날짜 도장은 오늘 날짜)
export const STAMPS = ['승인', '검토', '확인', '반려', '보류', '수정', '완료', '기밀', '사본', '원본', '긴급', '날짜'];
export const SYMBOLS = ['✔', '✘', '○', '◎', '△', '□', '☆', '★', '●', '※', '→', '←', '↑', '↓', '①', '②', '③', '④', '⑤', 'OK', 'NG', '확인', '수정', '삭제', '검토', '승인'];
const BOX = new Set(['rect', 'ellipse', 'hilite', 'white', 'text', 'sym', 'image', 'stamp', 'note', 'link', 'redact', 'callout']);
const PIC = new Set(['text', 'sym', 'image', 'stamp', 'note']);     //  속 그림이 있는 것 — 90° 돌리면 그림도 돈다(o.r)
const dims0 = (o) => ((o.r || 0) % 180 ? [o.h, o.w] : [o.w, o.h]);
const today = () => { const t = new Date(); return t.getFullYear() + '.' + String(t.getMonth() + 1).padStart(2, '0') + '.' + String(t.getDate()).padStart(2, '0'); };
const FONT = '"Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif';
const PAD = 3, LH = 1.3, K = 4;           //  글상자 안쪽 여백 · 줄 간격 · 글·기호를 그림으로 만들 때 배율
const N = (s) => PDFName.of(s);
const SVGNS = 'http://www.w3.org/2000/svg';
export const AUTHOR = '한일특장(주)';

let A = null;                              //  화면(app.js)이 넘겨 주는 것들
export function initEdit(api) { A = api; }

export const style = { sc: '#e5262e', fc: '', lw: 2, op: 1, fs: 14, sym: '✔', stamp: '승인' };
let sel = null;                            //  { d, id }
let drag = null;
let clip = null;

export function ed(d) {
  return d.ed || (d.ed = { objs: [], undo: [], redo: [], loaded: false, loading: null, managed: new Set(), imgs: new Map(), seq: 1 });
}
const byId = (d, id) => d.ed && d.ed.objs.find((o) => o.id === id);
export const selected = () => (sel && sel.d === A.cur() ? byId(sel.d, sel.id) : null);

//  pdf.js 가 그리지 않을 주석(우리가 가져와 고치는 것) — 문서를 열 때 한 번 붙인다
export function attachDoc(d) {
  const st = d.pdf.annotationStorage;
  Object.defineProperty(st, 'modifiedIds', {
    configurable: true,
    get: () => { const ids = d.ed ? d.ed.managed : new Set(); return { ids, hash: [...ids].join(',') }; },
  });
}

// ───────────────────────── 모양 계산 ─────────────────────────
export function bbox(o) {
  if (o.t === 'callout') return [Math.min(o.x, o.ax), Math.min(o.y, o.ay), Math.max(o.x + o.w, o.ax), Math.max(o.y + o.h, o.ay)];
  if (o.t === 'poly') { const xs = o.vs.map((v) => v[0]), ys = o.vs.map((v) => v[1]); return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]; }
  if (BOX.has(o.t)) return [o.x, o.y, o.x + o.w, o.y + o.h];
  if (o.t === 'mark') { let a = Infinity, b = Infinity, c = -Infinity, e = -Infinity; for (const [x, y, w, h] of o.rects) { a = Math.min(a, x); b = Math.min(b, y); c = Math.max(c, x + w); e = Math.max(e, y + h); } return [a, b, c, e]; }
  let pts;
  if (o.t === 'pen') pts = o.pts.flat(); else pts = [[o.x1, o.y1], [o.x2, o.y2]];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return [x0, y0, x1, y1];
}
function arrowHead(o) {
  const L = Math.max(7, o.lw * 4), ang = Math.atan2(o.y2 - o.y1, o.x2 - o.x1), a = Math.PI / 7;
  return [[o.x2 - L * Math.cos(ang - a), o.y2 - L * Math.sin(ang - a)], [o.x2, o.y2], [o.x2 - L * Math.cos(ang + a), o.y2 - L * Math.sin(ang + a)]];
}
let mctx = null;
function measure(font) { mctx = mctx || document.createElement('canvas').getContext('2d'); mctx.font = font; return mctx; }
//  글상자: 줄 나눔(너비 안에서) — 한글은 글자 단위, 영어는 낱말 단위로
export function layoutText(o) {
  const c = measure(o.fs + 'px ' + FONT);
  const [W0] = dims0(o);
  const maxW = o.auto ? 420 : Math.max(10, W0 - PAD * 2);
  const lines = [];
  for (const para of String(o.text || '').split('\n')) {
    let line = '';
    for (const ch of para) {
      const t = line + ch;
      if (c.measureText(t).width > maxW && line) {
        const sp = line.lastIndexOf(' ');
        if (sp > 0 && /\w/.test(ch)) { lines.push(line.slice(0, sp)); line = line.slice(sp + 1) + ch; }
        else { lines.push(line); line = ch; }
      } else line = t;
    }
    lines.push(line);
  }
  let w = 0;
  for (const l of lines) w = Math.max(w, c.measureText(l).width);
  const nW = o.auto ? Math.max(30, Math.ceil(w + PAD * 2 + 2)) : W0, nH = Math.ceil(lines.length * o.fs * LH + PAD * 2);
  if ((o.r || 0) % 180) { o.w = nH; o.h = nW; } else { o.w = nW; o.h = nH; }
  return lines;
}
//  글상자·기호는 그림으로 만들어 쓴다 — 화면·인쇄·저장(PDF 모양)이 똑같고, 한글 글꼴을 PDF 에 넣지 않아도 된다
const rasterCache = new Map();
export function raster(o) {
  const [w0, h0] = dims0(o);
  const key = JSON.stringify([o.t, o.text, o.sym, Math.round(w0 * 10), Math.round(h0 * 10), o.fs, o.sc, o.fc, o.lw]);
  let r = rasterCache.get(key);
  if (r) return r;
  const W = Math.max(1, Math.round(w0 * K)), H = Math.max(1, Math.round(h0 * K));
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d');
  c.scale(K, K);
  o = { ...o, w: w0, h: h0, r: 0 };
  if (o.fc && o.t !== 'note') { c.fillStyle = o.fc; c.fillRect(0, 0, o.w, o.h); }
  c.fillStyle = o.sc || '#000';
  c.textBaseline = 'top';
  if (o.t === 'stamp') {
    const lw = Math.max(1.5, Math.min(o.w, o.h) * 0.07), rr = Math.min(o.w, o.h) * 0.18;
    c.strokeStyle = o.sc || '#e5262e'; c.lineWidth = lw;
    c.beginPath(); c.roundRect ? c.roundRect(lw / 2, lw / 2, o.w - lw, o.h - lw, rr) : c.rect(lw / 2, lw / 2, o.w - lw, o.h - lw); c.stroke();
    c.font = '700 100px ' + FONT;
    const mw = c.measureText(o.sym).width || 100;
    const fs = Math.min(o.h * 0.62, (o.w - lw * 4) * 0.9 * 100 / mw);
    c.font = '700 ' + fs + 'px ' + FONT; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillStyle = o.sc || '#e5262e';
    c.fillText(o.sym, o.w / 2, o.h / 2 + fs * 0.05);
  } else if (o.t === 'note') {
    const s = Math.min(o.w, o.h);
    c.fillStyle = o.fc || '#ffd84d'; c.strokeStyle = '#8a6d00'; c.lineWidth = s * 0.06;
    c.beginPath(); c.moveTo(s * 0.08, s * 0.08); c.lineTo(s * 0.92, s * 0.08); c.lineTo(s * 0.92, s * 0.68); c.lineTo(s * 0.68, s * 0.92); c.lineTo(s * 0.08, s * 0.92); c.closePath(); c.fill(); c.stroke();
    c.beginPath(); c.moveTo(s * 0.92, s * 0.68); c.lineTo(s * 0.68, s * 0.68); c.lineTo(s * 0.68, s * 0.92); c.stroke();
    c.lineWidth = s * 0.05; c.beginPath();
    for (const y of [0.3, 0.45, 0.6]) { c.moveTo(s * 0.22, s * y); c.lineTo(s * (y > 0.5 ? 0.55 : 0.78), s * y); }
    c.stroke();
  } else if (o.t === 'sym') {
    c.font = '100px ' + FONT;
    const mw = c.measureText(o.sym).width || 100;
    const fs = Math.min(o.h * 0.86, o.w * 0.92 * 100 / mw);
    c.font = fs + 'px ' + FONT;
    c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(o.sym, o.w / 2, o.h / 2 + fs * 0.04);
  } else {
    c.font = o.fs + 'px ' + FONT;
    const lines = layoutText({ ...o, auto: false });
    lines.forEach((l, k) => c.fillText(l, PAD, PAD + k * o.fs * LH + o.fs * (LH - 1) / 2));
  }
  r = { canvas: cv, url: cv.toDataURL('image/png') };
  if (rasterCache.size > 300) rasterCache.clear();
  rasterCache.set(key, r);
  return r;
}

// ───────────────────────── 화면 겹(SVG) ─────────────────────────
const sv = (tag, attrs = {}) => { const e = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v); return e; };
function rotMatrix(r, W, H) {
  if (r === 90) return [0, 1, -1, 0, H, 0];
  if (r === 180) return [-1, 0, 0, -1, W, H];
  if (r === 270) return [0, -1, 1, 0, 0, W];
  return null;
}
// ───────────────────────── 새 도형(구름·다각형·측정·설명선·링크·교정) — 「그리기 조각」 하나로 화면·인쇄·저장을 함께 ─────────────────────────
//  prims(o) → [{ k:'path', seg:[['M',x,y],['L',x,y],['C',…],['Z']], stroke, fill, lw, dash, op } | { k:'img', canvas, x, y, w, h, r }]
export const NEW_TYPES = new Set(['poly', 'callout', 'link', 'redact']);
export const POLY_TOOLS = { polygon: 'polygon', polyline: 'polyline', cloud: 'cloud', mperim: 'polyline', marea: 'polygon' };
const MM_PER_PT = 25.4 / 72;
export function measValue(o) {
  const k = MM_PER_PT * (o.ratio || 1);
  if (o.meas === 'dist') return Math.hypot(o.x2 - o.x1, o.y2 - o.y1) * k;
  if (o.meas === 'perim') { let L = 0; for (let i = 1; i < o.vs.length; i++) L += Math.hypot(o.vs[i][0] - o.vs[i - 1][0], o.vs[i][1] - o.vs[i - 1][1]); return L * k; }
  if (o.meas === 'area') { let s = 0; const v = o.vs; for (let i = 0; i < v.length; i++) { const a = v[i], b = v[(i + 1) % v.length]; s += a[0] * b[1] - b[0] * a[1]; } return Math.abs(s / 2) * k * k; }
  return 0;
}
const nf = (v, d = 1) => v.toLocaleString('ko-KR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
export function measLabel(o) {
  const v = measValue(o), sc = (o.ratio || 1) === 1 ? '' : '  (1:' + nf(o.ratio, 2) + ')';
  if (o.meas === 'area') return (v >= 1e6 ? nf(v / 1e6, 3) + ' m²' : nf(v, 0) + ' mm²') + sc;
  return (v >= 10000 ? nf(v / 1000, 3) + ' m' : nf(v, 1) + ' mm') + sc;
}
function labelPrim(o, x, y) {
  const lo = { t: 'text', text: measLabel(o), fs: Math.max(7, Math.min(14, (o.fs || 14) * 0.75)), sc: o.sc || '#000', fc: '#ffffff', auto: true, r: 0 };
  layoutText(lo);
  return { k: 'img', canvas: raster(lo).canvas, url: raster(lo).url, x: x - lo.w / 2, y: y - lo.h / 2, w: lo.w, h: lo.h };
}
//  구름 테두리 — 변을 따라 바깥으로 볼록한 반원들
function cloudSeg(vs, lw) {
  let area = 0;
  for (let i = 0; i < vs.length; i++) { const a = vs[i], b = vs[(i + 1) % vs.length]; area += a[0] * b[1] - b[0] * a[1]; }
  const out = area > 0 ? -1 : 1;              //  화면 좌표(아래로 +)에서 바깥쪽
  const r = Math.max(5, lw * 3.5);
  const seg = [['M', vs[0][0], vs[0][1]]];
  for (let i = 0; i < vs.length; i++) {
    const a = vs[i], b = vs[(i + 1) % vs.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (L < 0.1) continue;
    const n = Math.max(1, Math.round(L / (r * 2))), ux = (b[0] - a[0]) / L, uy = (b[1] - a[1]) / L;
    const nx = -uy * out, ny = ux * out;
    for (let k = 0; k < n; k++) {
      const p0 = [a[0] + ux * L * k / n, a[1] + uy * L * k / n], p1 = [a[0] + ux * L * (k + 1) / n, a[1] + uy * L * (k + 1) / n];
      const h = L / n * 0.66;
      seg.push(['C', p0[0] + nx * h, p0[1] + ny * h, p1[0] + nx * h, p1[1] + ny * h, p1[0], p1[1]]);
    }
  }
  seg.push(['Z']);
  return seg;
}
function calloutAttach(o) {
  //  상자 테두리에서 고리점에 가장 가까운 변의 가운데
  const cx = o.x + o.w / 2, cy = o.y + o.h / 2, dx = o.ax - cx, dy = o.ay - cy;
  if (Math.abs(dx) * o.h > Math.abs(dy) * o.w) return [dx > 0 ? o.x + o.w : o.x, cy];
  return [cx, dy > 0 ? o.y + o.h : o.y];
}
export function prims(o, editing = false) {
  const P = [];
  const st = { stroke: o.sc || '', fill: o.fc || '', lw: o.lw || 0, op: o.op < 1 ? o.op : 1 };
  if (o.t === 'poly') {
    const closed = o.kind !== 'polyline';
    const seg = o.kind === 'cloud' ? cloudSeg(o.vs, o.lw || 1) : [['M', ...o.vs[0]], ...o.vs.slice(1).map((v) => ['L', ...v]), ...(closed ? [['Z']] : [])];
    P.push({ k: 'path', seg, ...st, fill: closed ? st.fill : '', stroke: st.stroke || '#000', lw: st.lw || 1 });
    if (o.meas && o.vs.length > 1) {
      let lx, ly;
      if (o.meas === 'area') { lx = o.vs.reduce((a, v) => a + v[0], 0) / o.vs.length; ly = o.vs.reduce((a, v) => a + v[1], 0) / o.vs.length; }
      else { const v = o.vs[o.vs.length - 1]; lx = v[0]; ly = v[1] - 10; }
      P.push(labelPrim(o, lx, ly));
    }
  } else if (o.t === 'callout') {
    const [ex, ey] = calloutAttach(o);
    P.push({ k: 'path', seg: [['M', ex, ey], ['L', o.ax, o.ay]], stroke: o.sc || '#000', lw: o.lw || 1, op: st.op });
    const head = arrowHead({ x1: ex, y1: ey, x2: o.ax, y2: o.ay, lw: o.lw || 1 });
    P.push({ k: 'path', seg: [['M', ...head[0]], ['L', ...head[1]], ['L', ...head[2]]], stroke: o.sc || '#000', lw: o.lw || 1, op: st.op });
    P.push({ k: 'path', seg: [['M', o.x, o.y], ['L', o.x + o.w, o.y], ['L', o.x + o.w, o.y + o.h], ['L', o.x, o.y + o.h], ['Z']], stroke: o.sc || '#000', fill: o.fc || '#ffffff', lw: o.lw || 1, op: st.op });
    const to = { t: 'text', text: o.text || '', fs: o.fs, sc: o.tc || o.sc || '#000', fc: '', w: o.w, h: o.h, auto: false, r: 0 };
    const rr = raster(to);
    P.push({ k: 'img', canvas: rr.canvas, url: rr.url, x: o.x, y: o.y, w: o.w, h: o.h });
  } else if (o.t === 'link') {
    if (editing) P.push({ k: 'path', seg: [['M', o.x, o.y], ['L', o.x + o.w, o.y], ['L', o.x + o.w, o.y + o.h], ['L', o.x, o.y + o.h], ['Z']], stroke: '#1a73e8', fill: 'rgba(26,115,232,0.08)', lw: 1, dash: [3, 2], screenOnly: true });
  } else if (o.t === 'redact') {
    P.push({ k: 'path', seg: [['M', o.x, o.y], ['L', o.x + o.w, o.y], ['L', o.x + o.w, o.y + o.h], ['L', o.x, o.y + o.h], ['Z']], stroke: '#e5262e', fill: editing ? 'rgba(229,38,46,0.12)' : '', lw: 1.5 });
  }
  if (o.t === 'line' && o.meas === 'dist') P.push(labelPrim(o, (o.x1 + o.x2) / 2, (o.y1 + o.y2) / 2 - 8));
  return P;
}
const segD = (seg) => seg.map(([c, ...v]) => c + v.map((n) => Math.round(n * 100) / 100).join(' ')).join(' ');
export function primsSvg(P, s) {
  const out = [];
  for (const p of P) {
    if (p.k === 'path') out.push(sv('path', { d: segD(p.seg), stroke: p.stroke || 'none', fill: p.fill || 'none', 'stroke-width': p.stroke ? p.lw : 0, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'stroke-dasharray': p.dash ? p.dash.map((x) => x / s).join(' ') : null, opacity: p.op < 1 ? p.op : null }));
    else out.push(sv('image', { href: p.url, x: p.x, y: p.y, width: p.w, height: p.h, preserveAspectRatio: 'none' }));
  }
  return out;
}
export function primsCanvas(ctx, P) {
  for (const p of P) {
    if (p.screenOnly) continue;
    ctx.save();
    if (p.k === 'path') {
      ctx.globalAlpha = p.op < 1 ? p.op : 1;
      ctx.beginPath();
      for (const [c, ...v] of p.seg) { if (c === 'M') ctx.moveTo(...v); else if (c === 'L') ctx.lineTo(...v); else if (c === 'C') ctx.bezierCurveTo(...v); else ctx.closePath(); }
      if (p.fill) { ctx.fillStyle = p.fill; ctx.fill(); }
      if (p.stroke && p.lw > 0) { ctx.strokeStyle = p.stroke; ctx.lineWidth = p.lw; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.setLineDash(p.dash || []); ctx.stroke(); }
    } else ctx.drawImage(p.canvas, p.x, p.y, p.w, p.h);
    ctx.restore();
  }
}
//  PDF 모양(AP) 명령 — 화면 좌표 그대로(Matrix 가 돌린다)
function primsOps(ctx, P, res, refs) {
  let ops = '', n = 0;
  for (const p of P) {
    if (p.screenOnly) continue;
    if (p.k === 'path') {
      ops += 'q\n';
      if (p.op < 1) { res.ExtGState = res.ExtGState || {}; const g = 'GP' + n++; res.ExtGState[g] = { Type: 'ExtGState', CA: p.op, ca: p.op }; ops += '/' + g + ' gs\n'; }
      const fill = p.fill && /^#/.test(p.fill) ? p.fill : '';
      if (p.stroke) ops += rgb(p.stroke).map(f3).join(' ') + ' RG ' + f3(p.lw) + ' w 1 J 1 j\n';
      if (fill) ops += rgb(fill).map(f3).join(' ') + ' rg\n';
      if (p.dash) ops += '[' + p.dash.join(' ') + '] 0 d\n';
      for (const [c, ...v] of p.seg) ops += (c === 'Z' ? 'h' : v.map(f3).join(' ') + ' ' + { M: 'm', L: 'l', C: 'c' }[c]) + '\n';
      ops += (fill ? (p.stroke && p.lw > 0 ? 'B' : 'f') : (p.stroke && p.lw > 0 ? 'S' : 'n')) + '\nQ\n';
    } else {
      const im = rgbaXObject(ctx, canvasPixels(p.canvas, p.canvas.width, p.canvas.height), p.canvas.width, p.canvas.height, refs);
      res.XObject = res.XObject || {};
      const nm = 'IP' + n++;
      res.XObject[nm] = im;
      ops += 'q ' + [p.w, 0, 0, -p.h, p.x, p.y + p.h].map(f3).join(' ') + ' cm /' + nm + ' Do Q\n';
    }
  }
  return ops;
}
function primsBox(P) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of P) {
    if (p.k === 'path') for (const [c, ...v] of p.seg) for (let k = 0; k + 1 < v.length; k += 2) { x0 = Math.min(x0, v[k]); y0 = Math.min(y0, v[k + 1]); x1 = Math.max(x1, v[k]); y1 = Math.max(y1, v[k + 1]); }
    else { x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y); x1 = Math.max(x1, p.x + p.w); y1 = Math.max(y1, p.y + p.h); }
  }
  return [x0, y0, x1, y1];
}

function shapeEls(o, s, editing) {
  const out = [];
  if (o.snap) return [sv('rect', { x: o.x, y: o.y, width: o.w, height: o.h, fill: 'rgba(26,115,232,.08)', stroke: '#1a73e8', 'stroke-width': 1 / s, 'stroke-dasharray': 4 / s })];
  if (NEW_TYPES.has(o.t)) return primsSvg(prims(o, editing), s);
  const st = { stroke: o.sc || 'none', 'stroke-width': o.sc ? o.lw : 0, fill: o.fc || 'none', opacity: o.op < 1 ? o.op : null };
  if (o.t === 'mark') {
    for (const [x, y, w, h] of o.rects) {
      if (o.kind === 'hl') { const e = sv('rect', { x, y, width: w, height: h, fill: o.sc, opacity: o.op < 1 ? o.op : 0.45 }); e.style.mixBlendMode = 'multiply'; out.push(e); }
      else { const yy = o.kind === 'ul' ? y + h * 0.93 : y + h * 0.55; out.push(sv('line', { x1: x, y1: yy, x2: x + w, y2: yy, stroke: o.sc, 'stroke-width': Math.max(0.8, h * 0.07), opacity: o.op < 1 ? o.op : null })); }
    }
    return out;
  }
  if (o.t === 'rect' || o.t === 'white' || o.t === 'hilite') {
    const e = sv('rect', { x: o.x, y: o.y, width: Math.max(0, o.w), height: Math.max(0, o.h), ...st });
    if (o.t === 'hilite') e.style.mixBlendMode = 'multiply';
    out.push(e);
    if (o.t === 'white' && editing) out.push(sv('rect', { x: o.x, y: o.y, width: o.w, height: o.h, fill: 'none', stroke: '#999', 'stroke-width': 1 / s, 'stroke-dasharray': 4 / s }));
  } else if (o.t === 'ellipse') {
    out.push(sv('ellipse', { cx: o.x + o.w / 2, cy: o.y + o.h / 2, rx: Math.max(0, o.w / 2), ry: Math.max(0, o.h / 2), ...st }));
  } else if (o.t === 'line' || o.t === 'arrow') {
    out.push(sv('line', { x1: o.x1, y1: o.y1, x2: o.x2, y2: o.y2, stroke: o.sc || '#000', 'stroke-width': o.lw, 'stroke-linecap': 'round', opacity: st.opacity }));
    if (o.t === 'arrow') out.push(sv('polyline', { points: arrowHead(o).map((p) => p.join(',')).join(' '), fill: 'none', stroke: o.sc || '#000', 'stroke-width': o.lw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', opacity: st.opacity }));
    if (o.meas) out.push(...primsSvg(prims(o), s));
  } else if (o.t === 'pen') {
    for (const pts of o.pts) out.push(sv('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: 'none', stroke: o.sc || '#000', 'stroke-width': o.lw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', opacity: st.opacity }));
  } else if (PIC.has(o.t)) {
    let url;
    if (o.t === 'image') { const d = A.docOf(o); const im = d && d.ed.imgs.get(o.img); url = im && im.url; }
    else url = raster(o).url;
    const [w0, h0] = dims0(o), cx = o.x + o.w / 2, cy = o.y + o.h / 2;
    out.push(sv('image', { href: url, x: cx - w0 / 2, y: cy - h0 / 2, width: w0, height: h0, preserveAspectRatio: 'none', opacity: st.opacity, transform: o.r ? 'rotate(' + o.r + ' ' + cx + ' ' + cy + ')' : null }));
    if (editing && (o.t === 'text' || o.t === 'sym') && !o.fc) out.push(sv('rect', { x: o.x, y: o.y, width: o.w, height: o.h, fill: 'none', stroke: '#9ab', 'stroke-width': 1 / s, 'stroke-dasharray': 3 / s }));
    if (o.t === 'note' && o.text) { const t = sv('title'); t.textContent = o.text; out.push(t); }
  }
  return out;
}
function hitEl(o, s) {
  if (o.t === 'poly') return sv('path', { d: segD([['M', ...o.vs[0]], ...o.vs.slice(1).map((v) => ['L', ...v]), ...(o.kind !== 'polyline' ? [['Z']] : [])]), fill: o.kind !== 'polyline' ? 'transparent' : 'none', stroke: 'transparent', 'stroke-width': Math.max(o.lw, 9 / s), class: 'hit' });
  if (o.t === 'callout') { const g = sv('g', { class: 'hit' }); g.append(sv('rect', { x: o.x, y: o.y, width: o.w, height: o.h, fill: 'transparent' }), sv('line', { x1: o.ax, y1: o.ay, x2: calloutAttach(o)[0], y2: calloutAttach(o)[1], stroke: 'transparent', 'stroke-width': 9 / s })); return g; }
  if (BOX.has(o.t)) return sv('rect', { x: o.x, y: o.y, width: Math.max(1, o.w), height: Math.max(1, o.h), fill: 'transparent', class: 'hit' });
  if (o.t === 'mark') { const g = sv('g', { class: 'hit' }); for (const [x, y, w, h] of o.rects) g.append(sv('rect', { x, y, width: w, height: h, fill: 'transparent' })); return g; }
  const w = Math.max(o.lw, 9 / s);
  if (o.t === 'pen') { const g = sv('g', { class: 'hit' }); for (const pts of o.pts) g.append(sv('polyline', { points: pts.map((p) => p.join(',')).join(' '), fill: 'none', stroke: 'transparent', 'stroke-width': w })); return g; }
  return sv('line', { x1: o.x1, y1: o.y1, x2: o.x2, y2: o.y2, stroke: 'transparent', 'stroke-width': w, class: 'hit' });
}
const HANDLES = { nw: [0, 0], n: [0.5, 0], ne: [1, 0], e: [1, 0.5], se: [1, 1], s: [0.5, 1], sw: [0, 1], w: [0, 0.5] };

export function isEditTool() { return EDIT_TOOLS.includes(A.tool()); }

export function drawOverlay(d, i) {
  const p = d.pages[i];
  if (!p.canvas) return;
  const objs = d.ed ? d.ed.objs.filter((o) => o.p === i) : [];
  const editing = isEditTool() && d === A.cur();
  if (!objs.length && !editing) { if (p.ov) { p.ov.remove(); p.ov = null; } return; }
  let svg = p.ov;
  if (!svg || !svg.isConnected) {
    svg = sv('svg', { class: 'ov' });
    svg.addEventListener('pointerdown', (e) => onDown(d, i, e));
    svg.addEventListener('pointermove', (e) => onMove(d, i, e));
    svg.addEventListener('pointerup', (e) => onUp(d, i, e));
    svg.addEventListener('pointercancel', (e) => onUp(d, i, e));
    svg.addEventListener('dblclick', (e) => {
      if (poly) { finishPoly(); return; }
      const g = e.target.closest('[data-id]'); const o = g && byId(d, g.dataset.id);
      if (o && (o.t === 'text' || o.t === 'callout')) editText(d, o);
      if (o && o.t === 'note') editNote(d, o);
      if (o && o.t === 'link') editLink(d, o);
    });
    p.div.append(svg);
    p.ov = svg;
  }
  const s = A.scaleOf(d), W = p.w * s, H = p.h * s;
  svg.setAttribute('viewBox', '0 0 ' + p.w + ' ' + p.h);
  svg.style.width = W + 'px'; svg.style.height = H + 'px';
  const m = rotMatrix(d.rot, W, H);
  svg.style.transform = m ? 'matrix(' + m.join(',') + ')' : '';
  svg.textContent = '';
  for (const o of objs) {
    const g = sv('g', { 'data-id': o.id });
    for (const e of shapeEls(o, s, editing)) g.append(e);
    if (editing) g.append(hitEl(o, s));
    svg.append(g);
  }
  const so = selected();
  if (editing && so && so.p === i && !(drag && drag.mode === 'create')) {
    const [x0, y0, x1, y1] = bbox(so);
    const hs = 7 / s, g = sv('g', { class: 'sel' });
    g.append(sv('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'none', stroke: '#1a73e8', 'stroke-width': 1 / s, 'stroke-dasharray': 4 / s, 'pointer-events': 'none' }));
    const hand = (hx, hy, name) => g.append(sv('rect', { x: hx - hs / 2, y: hy - hs / 2, width: hs, height: hs, fill: '#fff', stroke: '#1a73e8', 'stroke-width': 1.2 / s, 'data-h': name, class: 'hd hd-' + name }));
    if (so.t === 'line' || so.t === 'arrow') { hand(so.x1, so.y1, 'p1'); hand(so.x2, so.y2, 'p2'); }
    else if (so.t === 'poly') so.vs.forEach((v, k) => hand(v[0], v[1], 'v' + k));
    else if (so.t === 'callout') { for (const [n, [fx, fy]] of Object.entries(HANDLES)) hand(so.x + so.w * fx, so.y + so.h * fy, n); hand(so.ax, so.ay, 'a'); }
    else for (const [n, [fx, fy]] of Object.entries(HANDLES)) hand(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy, n);
    svg.append(g);
  }
}
export function redrawAll(d) { if (d) for (let i = 0; i < d.n; i++) if (d.pages[i].canvas || d.pages[i].ov) drawOverlay(d, i); }
function redrawPage(d, i) { drawOverlay(d, i); }

//  화면 위치 → 페이지 좌표(제 방향·배율 1)
function toView(d, i, e) {
  const p = d.pages[i], r = p.div.getBoundingClientRect(), s = A.scaleOf(d);
  const lx = e.clientX - r.left, ly = e.clientY - r.top, W = p.w * s, H = p.h * s;
  if (d.rot === 90) return [ly / s, (H - lx) / s];
  if (d.rot === 180) return [(W - lx) / s, (H - ly) / s];
  if (d.rot === 270) return [(W - ly) / s, lx / s];
  return [lx / s, ly / s];
}

// ───────────────────────── 되돌리기 ─────────────────────────
const snap = (d) => JSON.stringify(d.ed.objs);
function pushUndo(d, before) {
  const E = d.ed;
  E.undo.push(before);
  if (E.undo.length > 200) E.undo.shift();
  E.redo = [];
  modified(d);
}
function modified(d) { d.mod = true; A.onModified(d); }
export function undo(redo = false) {
  const d = A.cur(); if (!d || !d.ed) return;
  const E = d.ed, from = redo ? E.redo : E.undo, to = redo ? E.undo : E.redo;
  if (!from.length) return A.toast(redo ? '다시 할 것이 없습니다' : '되돌릴 것이 없습니다');
  to.push(snap(d));
  E.objs = JSON.parse(from.pop());
  sel = null;
  modified(d);
  redrawAll(d); syncControls();
}

// ───────────────────────── 마우스 ─────────────────────────
function newObj(d, t, i, [x, y]) {
  const E = ed(d);
  const o = { id: 'o' + (E.seq++), p: i, t, sc: style.sc, fc: style.fc, lw: style.lw, op: style.op, fs: style.fs };
  if (t === 'hilite') Object.assign(o, { sc: '', fc: style.fc && style.fc !== '#ffffff' ? style.fc : '#ffeb3b', lw: 0, op: 0.4 });
  if (t === 'white') Object.assign(o, { sc: '', fc: '#ffffff', lw: 0, op: 1 });
  if (t === 'text') Object.assign(o, { text: '', auto: true, fc: style.fc, sc: style.sc });
  if (t === 'type') Object.assign(o, { t: 'text', text: '', auto: true, fc: '', sc: style.sc === '#e5262e' ? '#1a1a1a' : style.sc });
  if (t === 'under') Object.assign(o, { t: 'line', under: true, lw: Math.max(1, Math.min(style.lw, 2)) });
  if (t === 'sym') o.sym = style.sym;
  if (t === 'stamp') Object.assign(o, { sym: style.stamp === '날짜' ? today() : style.stamp, sc: '#e5262e', fc: '', lw: 0 });
  if (t === 'note') Object.assign(o, { text: '', fc: '#ffd84d', sc: '', lw: 0 });
  if (t === 'snap' || t === 'crop') Object.assign(o, { snap: t });
  if (POLY_TOOLS[t]) Object.assign(o, { t: 'poly', kind: POLY_TOOLS[t], vs: [[x, y], [x, y]], fc: t === 'marea' ? '' : style.fc,
    ...(t === 'mperim' ? { meas: 'perim', ratio: E.ratio || 1 } : t === 'marea' ? { meas: 'area', ratio: E.ratio || 1 } : {}) });
  if (t === 'mdist') Object.assign(o, { t: 'line', meas: 'dist', ratio: E.ratio || 1, lw: Math.min(style.lw, 1.5) });
  if (t === 'callout') Object.assign(o, { ax: x, ay: y, x: x + 30, y: y - 50, w: 140, h: 30, text: '', fc: '#ffffff', tc: style.sc, lw: Math.min(style.lw, 1.5) });
  if (t === 'link') Object.assign(o, { sc: '#1a73e8', fc: '', lw: 0 });
  if (t === 'redact') Object.assign(o, { sc: '#e5262e', fc: '', lw: 1.5 });
  if (o.t === 'line' || o.t === 'arrow') Object.assign(o, { x1: x, y1: y, x2: x, y2: y });
  else if (o.t === 'poly' || o.t === 'callout') { /* 위에서 */ }
  else if (t === 'pen') o.pts = [[[x, y]]];
  else if (!('x1' in o)) Object.assign(o, { x, y, w: 0, h: 0 });
  if (t === 'snap' || t === 'crop') o.t = 'rect';
  return o;
}
function onDown(d, i, e) {
  if (e.button !== 0 || !isEditTool()) return;
  e.preventDefault(); e.stopPropagation();
  A.focus();
  const tool = A.tool(), pt = toView(d, i, e), E = ed(d);
  if (MARK_TOOLS[tool]) return;                         //  글자 고르기는 글자 층이 받는다
  //  구름·다각형·꺾은선·둘레·면적: 누를 때마다 꼭짓점, 두 번 누르거나 Enter 로 끝
  if (POLY_TOOLS[tool]) {
    //  ⚠ 두 번 누름은 직접 잰다 — 누를 때마다 겹을 다시 그려 브라우저의 dblclick 이 안 올 때가 있다
    const now = performance.now(), tol = 5 / A.scaleOf(d);
    if (poly && poly.d === d && poly.i === i) {
      if (poly.last && now - poly.last.t < 450 && Math.hypot(pt[0] - poly.last.x, pt[1] - poly.last.y) < tol) { finishPoly(); return; }
      poly.last = { t: now, x: pt[0], y: pt[1] };
      const o = poly.o; o.vs[o.vs.length - 1] = pt; o.vs.push([...pt]); redrawPage(d, i); return;
    }
    if (poly) finishPoly();
    const before = snap(d), o = newObj(d, tool, i, pt);
    E.objs.push(o); sel = { d, id: o.id };
    poly = { d, i, o, before, last: { t: now, x: pt[0], y: pt[1] } };
    redrawPage(d, i);
    return;
  }
  if (tool === 'erase') {
    const g = e.target.closest('[data-id]'), o = g && byId(d, g.dataset.id);
    if (o) { const before = snap(d); E.objs = E.objs.filter((x) => x !== o); if (sel && sel.id === o.id) sel = null; pushUndo(d, before); drawOverlay(d, i); }
    return;
  }
  if (tool === 'edit') {
    const hd = e.target.closest('[data-h]'), g = e.target.closest('[data-id]');
    const so = selected();
    if (hd && so) drag = { mode: 'resize', h: hd.dataset.h, o: so, orig: JSON.parse(JSON.stringify(so)), start: pt, before: snap(d) };
    else if (g) {
      const o = byId(d, g.dataset.id);
      select(d, o);
      drag = { mode: 'move', o, orig: JSON.parse(JSON.stringify(o)), start: pt, before: snap(d) };
    } else { select(null); return; }
  } else {
    const before = snap(d);
    const o = newObj(d, tool, i, pt);
    E.objs.push(o);
    sel = { d, id: o.id };
    drag = { mode: 'create', o, start: pt, before };
  }
  drag.page = i;
  e.target.setPointerCapture && d.pages[i].ov.setPointerCapture(e.pointerId);
  redrawPage(d, i);
}
let poly = null;                      //  그리는 중인 다각형 { d, i, o, before }
export function finishPoly(cancel = false, keepTool = false) {
  const P = poly; if (!P) return false;
  poly = null;
  const o = P.o, d = P.d;
  o.vs.pop();
  o.vs = o.vs.filter((v, k) => !k || Math.hypot(v[0] - o.vs[k - 1][0], v[1] - o.vs[k - 1][1]) > 1.5);
  const need = o.kind === 'polyline' ? 2 : 3;
  if (cancel || o.vs.length < need) { d.ed.objs = d.ed.objs.filter((x) => x !== o); sel = null; drawOverlay(d, P.i); if (!cancel) A.toast('꼭짓점을 ' + need + '개 이상 찍으세요'); return true; }
  pushUndo(d, P.before);
  if (!keepTool) A.setTool('edit');
  select(d, o);
  return true;
}
function onMove(d, i, e) {
  if (poly && poly.d === d && poly.i === i) {
    let [x, y] = toView(d, i, e);
    const o = poly.o, prev = o.vs[o.vs.length - 2];
    if (e.shiftKey && prev) { const a = Math.round(Math.atan2(y - prev[1], x - prev[0]) / (Math.PI / 4)) * Math.PI / 4, L = Math.hypot(x - prev[0], y - prev[1]); x = prev[0] + L * Math.cos(a); y = prev[1] + L * Math.sin(a); }
    o.vs[o.vs.length - 1] = [x, y];
    redrawPage(d, i);
    return;
  }
  if (!drag || drag.page !== i) return;
  const [x, y] = toView(d, i, e), o = drag.o, [sx, sy] = drag.start, dx = x - sx, dy = y - sy;
  drag.moved = drag.moved || Math.abs(dx) + Math.abs(dy) > 1;
  if (drag.mode === 'create') {
    if (o.t === 'pen') o.pts[0].push([x, y]);
    else if (o.t === 'line' || o.t === 'arrow') {
      let X = x, Y = y;
      if (o.under) Y = sy;
      else if (e.shiftKey) { const a = Math.round(Math.atan2(y - sy, x - sx) / (Math.PI / 4)) * Math.PI / 4, L = Math.hypot(x - sx, y - sy); X = sx + L * Math.cos(a); Y = sy + L * Math.sin(a); }
      o.x2 = X; o.y2 = Y;
    } else {
      let w = dx, h = dy;
      if (o.t === 'callout') { o.x = x; o.y = y - 15; redrawPage(d, i); return; }
      if (e.shiftKey || o.t === 'sym' || o.t === 'note') { const m = Math.max(Math.abs(w), Math.abs(h)); w = Math.sign(w || 1) * m; h = Math.sign(h || 1) * m; }
      o.x = Math.min(sx, sx + w); o.y = Math.min(sy, sy + h); o.w = Math.abs(w); o.h = Math.abs(h);
      if (o.t === 'text') o.auto = false;
    }
  } else if (drag.mode === 'move') {
    moveTo(o, drag.orig, dx, dy);
  } else if (drag.mode === 'resize') {
    resize(o, drag.orig, drag.h, x, y, e.shiftKey);
  }
  redrawPage(d, i);
}
function moveTo(o, orig, dx, dy) {
  if (o.t === 'callout') { o.x = orig.x + dx; o.y = orig.y + dy; o.ax = orig.ax + dx; o.ay = orig.ay + dy; return; }
  if (o.t === 'poly') { o.vs = orig.vs.map(([x, y]) => [x + dx, y + dy]); return; }
  if (BOX.has(o.t)) { o.x = orig.x + dx; o.y = orig.y + dy; }
  else if (o.t === 'mark') o.rects = orig.rects.map(([x, y, w, h]) => [x + dx, y + dy, w, h]);
  else if (o.t === 'pen') o.pts = orig.pts.map((s) => s.map(([x, y]) => [x + dx, y + dy]));
  else { o.x1 = orig.x1 + dx; o.y1 = orig.y1 + dy; o.x2 = orig.x2 + dx; o.y2 = orig.y2 + dy; }
}
function resize(o, orig, h, x, y, free) {
  if (h === 'p1') { o.x1 = x; o.y1 = y; return; }
  if (h === 'p2') { o.x2 = x; o.y2 = y; return; }
  if (h[0] === 'v') { o.vs[+h.slice(1)] = [x, y]; return; }
  if (h === 'a') { o.ax = x; o.ay = y; return; }
  let [x0, y0, x1, y1] = orig.t === 'callout' ? [orig.x, orig.y, orig.x + orig.w, orig.y + orig.h] : bbox(orig);
  if (h.includes('w')) x0 = x; if (h.includes('e')) x1 = x;
  if (h.includes('n')) y0 = y; if (h.includes('s')) y1 = y;
  //  그림·기호는 모서리를 끌면 비율 유지(Shift 를 누르면 자유롭게)
  const [ox0, oy0, ox1, oy1] = orig.t === 'callout' ? [orig.x, orig.y, orig.x + orig.w, orig.y + orig.h] : bbox(orig);
  if ((orig.t === 'image' || orig.t === 'sym' || orig.t === 'stamp' || orig.t === 'note') && h.length === 2 && !free) {
    const r = (ox1 - ox0) / Math.max(1e-6, oy1 - oy0);
    const w = Math.abs(x1 - x0), hh = Math.abs(y1 - y0);
    if (w / r > hh) { const nh = w / r; if (h.includes('n')) y0 = y1 - nh * Math.sign(y1 - y0 || 1); else y1 = y0 + nh * Math.sign(y1 - y0 || 1); }
    else { const nw = hh * r; if (h.includes('w')) x0 = x1 - nw * Math.sign(x1 - x0 || 1); else x1 = x0 + nw * Math.sign(x1 - x0 || 1); }
  }
  const nx = Math.min(x0, x1), ny = Math.min(y0, y1), nw = Math.max(1, Math.abs(x1 - x0)), nh = Math.max(1, Math.abs(y1 - y0));
  if (BOX.has(o.t)) {
    Object.assign(o, { x: nx, y: ny, w: nw, h: nh });
    if (o.t === 'text') { o.auto = false; layoutText(o); }
  } else if (o.t === 'mark') {
    const sx = nw / Math.max(1e-6, ox1 - ox0), sy = nh / Math.max(1e-6, oy1 - oy0);
    o.rects = orig.rects.map(([x, y, w, h]) => [nx + (x - ox0) * sx, ny + (y - oy0) * sy, w * sx, h * sy]);
  } else if (o.t === 'pen') {
    const sx = nw / Math.max(1e-6, ox1 - ox0), sy = nh / Math.max(1e-6, oy1 - oy0);
    o.pts = orig.pts.map((s) => s.map(([px, py]) => [nx + (px - ox0) * sx, ny + (py - oy0) * sy]));
  }
}
function onUp(d, i, e) {
  if (!drag || drag.page !== i) return;
  const dr = drag; drag = null;
  const o = dr.o;
  if (dr.mode === 'create' && o.snap) {
    //  📷 스냅샷 — 그 네모 안을 그림으로 복사(도형은 남기지 않음)
    d.ed.objs = d.ed.objs.filter((x) => x !== o); sel = null;
    redrawPage(d, i);
    if (o.w > 4 && o.h > 4) (o.snap === 'crop' ? A.cropBox : A.snapshot)(d, i, [o.x, o.y, o.w, o.h]);
    else if (o.snap === 'snap') A.snapshotView(d);           //  끌지 않고 한 번 누르면 → 보이는 화면 전체
    return;
  }
  if (dr.mode === 'create') {
    //  끌지 않고 누르기만 했으면 알맞은 크기로
    const [x0, y0, x1, y1] = bbox(o), small = x1 - x0 < 4 && y1 - y0 < 4;
    if (small) {
      const [x, y] = dr.start;
      if (o.t === 'pen') { if (o.pts[0].length < 2) o.pts[0].push([x + 0.5, y + 0.5]); }
      else if (o.t === 'line' || o.t === 'arrow') { o.x2 = x + 80; o.y2 = y; }
      else if (o.t === 'sym') Object.assign(o, { x: x - 14, y: y - 14, w: 28, h: 28 });
      else if (o.t === 'stamp') Object.assign(o, { x: x - 45, y: y - 18, w: o.sym.length > 3 ? 110 : 90, h: 36 });
      else if (o.t === 'note') Object.assign(o, { x: x - 10, y: y - 10, w: 20, h: 20 });
      else if (o.t === 'callout') Object.assign(o, { x: x + 30, y: y - 50 });
      else if (o.t === 'text') Object.assign(o, { x, y, auto: true });
      else Object.assign(o, { x: x - 40, y: y - 25, w: 80, h: 50 });
    }
    if (o.t === 'text') layoutText(o);
    pushUndo(d, dr.before);
    if (o.t !== 'pen') A.setTool('edit');
    select(d, o);
    if (o.t === 'text') editText(d, o, dr.before);
    if (o.t === 'note') editNote(d, o, dr.before);
    if (o.t === 'callout') editText(d, o, dr.before);
    if (o.t === 'link') editLink(d, o, dr.before);
  } else if (dr.moved) pushUndo(d, dr.before);
  redrawPage(d, i);
}
export function select(d, o) {
  const old = sel;
  sel = d && o ? { d, id: o.id } : null;
  if (old && old.d.ed) { const oo = byId(old.d, old.id); if (oo) drawOverlay(old.d, oo.p); }
  if (d && o) drawOverlay(d, o.p);
  syncControls();
}

// ───────────────────────── 글상자 고치기 ─────────────────────────
function editText(d, o, beforeCreate = null) {
  const p = d.pages[o.p];
  if (!p.ov) return;
  const g = p.ov.querySelector('[data-id="' + o.id + '"]');
  const s = A.scaleOf(d);
  const before = beforeCreate || snap(d);
  const ta = document.createElement('textarea');
  ta.className = 'tedit';
  ta.value = o.text || '';
  Object.assign(ta.style, { fontSize: o.fs * s + 'px', lineHeight: LH, padding: PAD * s + 'px', color: o.sc || '#000', background: o.fc || 'rgba(255,255,255,.85)', fontFamily: FONT });
  const place = () => {
    const pr = p.div.getBoundingClientRect();
    const r = g && g.isConnected ? g.getBoundingClientRect() : null;
    const left = r && o.t !== 'callout' ? r.left - pr.left : o.x * s, top = r && o.t !== 'callout' ? r.top - pr.top : o.y * s;
    Object.assign(ta.style, { left: left + 'px', top: top + 'px', width: Math.max(60, o.w * s + 4) + 'px', height: Math.max(o.fs * s * LH + PAD * 2 * s, o.h * s + 2) + 'px' });
  };
  place();
  p.div.append(ta);
  ta.focus();
  ta.addEventListener('input', () => { o.text = ta.value; layoutText(o); place(); });
  ta.addEventListener('keydown', (e) => {
    e.stopPropagation();
    if (e.key === 'Escape' || (e.key === 'Enter' && (e.ctrlKey || e.metaKey))) { e.preventDefault(); ta.blur(); }
  });
  ta.addEventListener('blur', () => {
    ta.remove();
    o.text = ta.value.replace(/\s+$/, '');
    if (!o.text && o.t !== 'callout') { d.ed.objs = d.ed.objs.filter((x) => x !== o); sel = null; }
    else layoutText(o);
    if (snap(d) !== before) pushUndo(d, before);
    redrawPage(d, o.p); syncControls();
  });
}

//  스티커 메모 — 내용은 창에서 고친다(다른 프로그램에서는 메모 아이콘을 누르면 이 글이 뜬다)
async function editNote(d, o, beforeCreate = null) {
  const before = beforeCreate || snap(d);
  const v = await A.ask('스티커 메모', '메모 내용을 적으세요.', { input: 'text', value: o.text || '', ok: '확인' });
  if (v == null) { if (beforeCreate && !o.text) { d.ed.objs = d.ed.objs.filter((x) => x !== o); sel = null; drawOverlay(d, o.p); } return; }
  o.text = v;
  if (snap(d) !== before) pushUndo(d, before);
  drawOverlay(d, o.p);
}

//  글자를 고른 범위 → 페이지마다 줄 네모들 → 강조·밑줄·취소선
export async function markFromSelection(d, kind) {
  const selc = getSelection();
  if (!selc || selc.isCollapsed || !selc.rangeCount) return false;
  const rng = selc.getRangeAt(0);
  const rects = [...rng.getClientRects()].filter((r) => r.width > 0.5 && r.height > 0.5);
  if (!rects.length) return false;
  if (!(await ensureLoaded(d))) return false;
  const [k, color] = MARK_TOOLS[kind];
  const before = snap(d), E = d.ed, s = A.scaleOf(d);
  let made = 0;
  for (let i = 0; i < d.n; i++) {
    const p = d.pages[i];
    if (!p.canvas) continue;
    const pr = p.div.getBoundingClientRect();
    const mine = [];
    for (const r of rects) {
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      if (cx < pr.left || cx > pr.right || cy < pr.top || cy > pr.bottom) continue;
      //  화면 → 페이지 좌표(네 귀퉁이를 돌려 다시 네모로)
      const pts = [[r.left, r.top], [r.right, r.bottom]].map(([X, Y]) => toView(d, i, { clientX: X, clientY: Y }));
      const x = Math.min(pts[0][0], pts[1][0]), y = Math.min(pts[0][1], pts[1][1]);
      mine.push([x, y, Math.abs(pts[1][0] - pts[0][0]), Math.abs(pts[1][1] - pts[0][1])]);
    }
    //  같은 줄에 겹친 네모는 합친다
    mine.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
    const merged = [];
    for (const r of mine) {
      const m = merged[merged.length - 1];
      if (m && Math.abs(m[1] - r[1]) < r[3] * 0.5 && r[0] <= m[0] + m[2] + 2) { const x2 = Math.max(m[0] + m[2], r[0] + r[2]); m[3] = Math.max(m[3], r[3]); m[2] = x2 - m[0]; }
      else merged.push([...r]);
    }
    if (!merged.length) continue;
    E.objs.push({ id: 'o' + (E.seq++), p: i, t: 'mark', kind: k, rects: merged, sc: style.markColor && style.markColor[k] || color, fc: '', lw: 1, op: k === 'hl' ? 0.45 : 1, fs: 14 });
    made++;
    drawOverlay(d, i);
  }
  if (made) { pushUndo(d, before); selc.removeAllRanges(); }
  void s;
  return made > 0;
}

//  🔗 링크 — 웹 주소 또는 이 문서의 쪽
async function editLink(d, o, beforeCreate = null) {
  const before = beforeCreate || snap(d);
  const v = await A.ask('링크', '누르면 갈 곳 — <b>웹 주소</b>(https://…) 또는 이 문서의 <b>쪽 번호</b>(예: 12)', { input: 'text', value: o.url || (o.page != null ? String(o.page + 1) : 'https://'), ok: '확인' });
  if (v == null || !v.trim() || v.trim() === 'https://') { if (beforeCreate) { d.ed.objs = d.ed.objs.filter((x) => x !== o); sel = null; drawOverlay(d, o.p); } return; }
  const t = v.trim();
  if (/^\d+$/.test(t)) { o.page = Math.max(0, Math.min(d.n - 1, +t - 1)); delete o.url; }
  else { o.url = /^[a-z]+:/i.test(t) ? t : 'https://' + t; delete o.page; }
  pushUndo(d, before); drawOverlay(d, o.p);
}
//  📏 축척 — 「1 : N」 · 선(거리 측정)을 하나 고르고 부르면 그 선의 실제 길이로 맞춘다
export async function setScale(d) {
  if (!(await ensureLoaded(d))) return;
  const E = d.ed, o = selected();
  if (o && o.meas === 'dist') {
    const cur = measValue(o);
    const v = await A.ask('축척 맞추기', '고른 선의 <b>실제 길이(mm)</b>를 넣으세요. 지금: ' + measLabel(o), { input: 'text', value: String(Math.round(cur)), ok: '맞추기' });
    if (!v) return;
    const real = parseFloat(v.replace(/,/g, ''));
    if (!(real > 0)) return A.toast('숫자를 넣으세요');
    E.ratio = real / (cur / (o.ratio || 1));
  } else {
    const v = await A.ask('축척', '도면 축척 <b>1 : N</b> 의 N 을 넣으세요(실물 크기면 1).<br><small>거리 측정 선을 하나 고르고 부르면, 그 선의 실제 길이로 맞출 수 있습니다.</small>', { input: 'text', value: String(E.ratio || 1), ok: '확인' });
    if (!v) return;
    const n = parseFloat(v.replace(/^1\s*:\s*/, ''));
    if (!(n > 0)) return A.toast('숫자를 넣으세요');
    E.ratio = n;
  }
  //  이 문서의 모든 측정에 새 축척
  const before = snap(d);
  for (const x of E.objs) if (x.meas) x.ratio = E.ratio;
  pushUndo(d, before); redrawAll(d);
  A.toast('축척 1 : ' + (Math.round(E.ratio * 100) / 100));
}

// ───────────────────────── 돌리기 ─────────────────────────
//  고른 도형을 90° 돌린다(dir 1: 오른쪽 · -1: 왼쪽) — 가운데를 축으로
export function rotateSel(dir) {
  const d = A.cur(), o = selected(); if (!o) return A.toast('돌릴 도형을 먼저 고르세요(주석 선택)');
  if (o.t === 'mark') return A.toast('글자 표시(강조·밑줄)는 글자를 따라가므로 돌리지 않습니다');
  if (o.t === 'callout') return A.toast('설명선은 꼬리 끝(◇)을 끌어 방향을 바꾸세요');
  const before = snap(d);
  const [x0, y0, x1, y1] = bbox(o), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const rp = ([x, y]) => (dir > 0 ? [cx - (y - cy), cy + (x - cx)] : [cx + (y - cy), cy - (x - cx)]);
  if (o.t === 'pen') o.pts = o.pts.map((s) => s.map(rp));
  else if (o.t === 'poly') o.vs = o.vs.map(rp);
  else if (o.t === 'line' || o.t === 'arrow') { [o.x1, o.y1] = rp([o.x1, o.y1]); [o.x2, o.y2] = rp([o.x2, o.y2]); }
  else {
    const w = o.w, h = o.h;
    Object.assign(o, { x: cx - h / 2, y: cy - w / 2, w: h, h: w });
    if (PIC.has(o.t)) o.r = ((o.r || 0) + (dir > 0 ? 90 : 270)) % 360;
  }
  pushUndo(d, before); drawOverlay(d, o.p);
}

// ───────────────────────── 고르기·지우기·복사 ─────────────────────────
export function copySel(cut = false) {
  const d = A.cur(), o = selected();
  if (!o) return false;
  clip = { objs: [JSON.parse(JSON.stringify(o))], d };
  if (cut) delSel(); else A.toast('복사했습니다 — Ctrl+V 로 붙여 넣기');
  return true;
}
export function hasClip() { return !!clip; }
export async function pasteClip() {
  const d = A.cur(); if (!d || !clip) return false;
  if (!(await ensureLoaded(d))) return true;
  const page = clip.d === d ? clip.objs[0].p : d.cur - 1;
  const objs = clip.objs.map((o) => { const c = JSON.parse(JSON.stringify(o)); if (clip.d === d) moveTo(c, JSON.parse(JSON.stringify(o)), 12, 12); return c; });
  if (clip.d !== d) for (const o of objs) if (o.t === 'image') { const im = clip.d.ed && clip.d.ed.imgs.get(o.img); if (im) d.ed.imgs.set(o.img, im); }
  clip.objs = objs;
  addObjs(d, objs, page, snap(d));
  A.setTool('edit');
  return true;
}
//  스냅샷 그림을 붙여 넣을 수 있게(같은 창 안에서)
export function setClipImage(blob) { clip = null; lastSnap = blob; }
let lastSnap = null;
export function delSel() {
  const d = A.cur(), o = selected(); if (!o) return;
  const before = snap(d);
  d.ed.objs = d.ed.objs.filter((x) => x !== o);
  sel = null;
  pushUndo(d, before); drawOverlay(d, o.p); syncControls();
}
function addObjs(d, objs, page, before) {
  const E = ed(d);
  let last = null;
  for (const src of objs) {
    const o = JSON.parse(JSON.stringify(src));
    o.id = 'o' + (E.seq++); o.p = page; delete o.src;
    E.objs.push(o); last = o;
  }
  pushUndo(d, before);
  if (last) select(d, last);
  drawOverlay(d, page);
}
export function dupSel() {
  const d = A.cur(), o = selected(); if (!o) return;
  const c = JSON.parse(JSON.stringify(o)); moveTo(c, JSON.parse(JSON.stringify(o)), 12, 12);
  addObjs(d, [c], o.p, snap(d));
}
//  키보드 — 다룬 키면 true
export function onKey(e) {
  const d = A.cur(); if (!d) return false;
  if (poly && (e.key === 'Enter' || e.key === 'Escape')) { e.preventDefault(); finishPoly(e.key === 'Escape' && poly.o.vs.length <= 2); return true; }
  const k = e.key, c = e.ctrlKey || e.metaKey;
  if (c && !e.shiftKey && (k === 'z' || k === 'Z') && d.ed && (d.ed.undo.length || isEditTool())) { e.preventDefault(); undo(false); return true; }
  if (c && ((k === 'y' || k === 'Y') || (e.shiftKey && (k === 'z' || k === 'Z'))) && d.ed) { e.preventDefault(); undo(true); return true; }
  const o = selected();
  if (!o || !isEditTool()) return false;
  if (k === 'Delete' || k === 'Backspace') { e.preventDefault(); delSel(); return true; }
  if (k === 'Escape') { select(null); return true; }
  if (c && (k === 'c' || k === 'C')) { copySel(false); return true; }
  if (c && (k === 'x' || k === 'X')) { copySel(true); return true; }
  if (c && (k === 'r' || k === 'R')) { e.preventDefault(); rotateSel(e.shiftKey ? -1 : 1); return true; }
  if (c && (k === 'd' || k === 'D')) { e.preventDefault(); dupSel(); return true; }
  const step = e.shiftKey ? 10 : 1;
  const mv = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[k];
  if (mv) {
    e.preventDefault();
    const before = snap(d);
    moveTo(o, JSON.parse(JSON.stringify(o)), mv[0], mv[1]);
    pushUndo(d, before); drawOverlay(d, o.p);
    return true;
  }
  if (k === 'Enter' && o.t === 'text') { e.preventDefault(); editText(d, o); return true; }
  return false;
}
//  붙여 넣기 — 그림(캡처·복사한 이미지) 또는 복사해 둔 도형
export async function onPaste(e) {
  const t = e.target;
  if (t && /^(INPUT|TEXTAREA)$/.test(t.tagName)) return;
  const d = A.cur();
  const items = [...((e.clipboardData && e.clipboardData.items) || [])];
  const img = items.find((it) => it.kind === 'file' && it.type.startsWith('image/'));
  if (img) {
    e.preventDefault();
    if (!d) return A.toast('먼저 PDF 를 여세요');
    await addImage(d, img.getAsFile());
    return;
  }
  if (A.pagePaste && A.pagePaste(e)) return;          //  페이지 그림 칸에서는 페이지 붙여 넣기
  if (clip && d) { e.preventDefault(); await pasteClip(); return; }
  if (lastSnap && d) { e.preventDefault(); await addImage(d, lastSnap); }
}

// ───────────────────────── 이미지 넣기 ─────────────────────────
function jpegComps(b) {
  for (let i = 2; i < b.length - 9;) {
    if (b[i] !== 0xff) return 0;
    const m = b[i + 1];
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return b[i + 9];
    i += 2 + ((b[i + 2] << 8) | b[i + 3]);
  }
  return 0;
}
async function registerImg(E, blob, id = null) {
  id = id || 'i' + (E.seq++) + '_' + Date.now().toString(36);
  const url = URL.createObjectURL(blob);
  const el = new Image();
  el.src = url;
  await el.decode();
  const rec = { blob, url, el, nw: el.naturalWidth, nh: el.naturalHeight, mime: blob.type };
  if (blob.type === 'image/jpeg') { const b = new Uint8Array(await blob.arrayBuffer()); if (jpegComps(b) === 3) rec.jpeg = b; }
  E.imgs.set(id, rec);
  return id;
}
//  아주 큰 사진은 줄인다(긴 변 3000px) · PNG·JPEG 가 아니면 PNG 로
async function normImage(file) {
  const ok = file.type === 'image/png' || file.type === 'image/jpeg';
  const bmp = await createImageBitmap(file);
  const big = Math.max(bmp.width, bmp.height) > 3000;
  if (ok && !big) { bmp.close && bmp.close(); return file; }
  const sc = big ? 3000 / Math.max(bmp.width, bmp.height) : 1;
  const cv = document.createElement('canvas');
  cv.width = Math.round(bmp.width * sc); cv.height = Math.round(bmp.height * sc);
  cv.getContext('2d').drawImage(bmp, 0, 0, cv.width, cv.height);
  const type = file.type === 'image/jpeg' ? 'image/jpeg' : 'image/png';
  return await new Promise((r) => cv.toBlob(r, type, 0.92));
}
export async function addImage(d, file, at = null) {
  if (!(await ensureLoaded(d))) return;
  let blob;
  try { blob = await normImage(file); } catch { return A.toast('그림을 읽지 못했습니다'); }
  const E = d.ed, id = await registerImg(E, blob);
  const im = E.imgs.get(id);
  const i = at ? at.i : d.cur - 1, p = d.pages[i];
  //  크기: 그림 그대로(96dpi → pt), 페이지의 반을 넘으면 줄임
  let w = im.nw * 0.75, h = im.nh * 0.75;
  const f = Math.min(1, p.w * 0.5 / w, p.h * 0.5 / h);
  w *= f; h *= f;
  const [cx, cy] = at ? [at.x, at.y] : A.visibleCenter(d, i);
  const before = snap(d);
  const o = { id: 'o' + (E.seq++), p: i, t: 'image', img: id, x: cx - w / 2, y: cy - h / 2, w, h, sc: '', fc: '', lw: 0, op: 1, fs: 14 };
  E.objs.push(o);
  pushUndo(d, before);
  A.setTool('edit');
  select(d, o);
  A.toast('그림을 넣었습니다 — 끌어서 옮기고, 모서리로 크기 조절');
}

// ───────────────────────── 모양 바꾸기(리본) ─────────────────────────
let ctl = null;
export function styleGroup(h) {
  const color = (id, tip) => { const i = h('input', { type: 'color', id, title: tip }); return i; };
  const sel = (id, opts, tip) => { const s = h('select', { id, title: tip }); for (const [v, t] of opts) s.append(h('option', { value: v, text: t })); return s; };
  const sc = color('eSc', '선·글자 색'), fc = color('eFc', '채우기 색');
  const noFill = h('input', { type: 'checkbox', id: 'eNoFill' });
  const lw = sel('eLw', [[0.5, '0.5'], [1, '1'], [2, '2'], [3, '3'], [5, '5'], [8, '8']].map(([v, t]) => [v, t + ' pt']), '선 굵기');
  const op = sel('eOp', [[1, '100%'], [0.75, '75%'], [0.5, '50%'], [0.3, '30%']], '불투명도');
  const fs = sel('eFs', [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72].map((v) => [v, v + ' pt']), '글자 크기');
  const row = (label, ...els) => h('label', { class: 'erow' }, h('span', { text: label }), ...els);
  const box = h('div', { class: 'estyle' },
    h('div', { class: 'ecol' }, row('선 색', sc), row('채우기', fc, noFill, h('small', { text: '없음' }))),
    h('div', { class: 'ecol' }, row('굵기', lw), row('투명', op)),
    h('div', { class: 'ecol' }, row('글자', fs)));
  ctl = { sc, fc, noFill, lw, op, fs };
  const apply = (k, v) => {
    style[k] = v;
    const d = A.cur(), o = selected();
    if (!o) return;
    const before = snap(d);
    o[k] = v;
    if (o.t === 'text' && k === 'fs') layoutText(o);
    pushUndo(d, before); drawOverlay(d, o.p);
  };
  sc.oninput = () => apply('sc', sc.value);
  fc.oninput = () => { noFill.checked = false; apply('fc', fc.value); };
  noFill.onchange = () => apply('fc', noFill.checked ? '' : fc.value);
  lw.onchange = () => apply('lw', +lw.value);
  op.onchange = () => apply('op', +op.value);
  fs.onchange = () => apply('fs', +fs.value);
  syncControls();
  return box;
}
export function syncControls() {
  if (!ctl || !ctl.sc.isConnected) return;
  const o = selected() || style;
  ctl.sc.value = o.sc || style.sc || '#000000';
  ctl.noFill.checked = !o.fc;
  if (o.fc) ctl.fc.value = o.fc;
  ctl.lw.value = String(o.lw || style.lw);
  ctl.op.value = String(o.op || 1);
  ctl.fs.value = String(o.fs || style.fs);
  A.syncSymButton && A.syncSymButton();
}

// ───────────────────────── 인쇄: 캔버스에 그리기 ─────────────────────────
//  m: 화면 좌표(배율 1) → 캔버스 좌표 [a,b,c,d,e,f]
export function paintCanvas(ctx, d, i, m) {
  if (!d.ed) return;
  for (const o of d.ed.objs.filter((x) => x.p === i)) {
    ctx.save();
    ctx.setTransform(...m);
    ctx.globalAlpha = o.op < 1 ? o.op : 1;
    ctx.lineWidth = o.lw; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = o.sc || '#000'; ctx.fillStyle = o.fc || 'transparent';
    if (o.t === 'hilite') ctx.globalCompositeOperation = 'multiply';
    if (NEW_TYPES.has(o.t)) { primsCanvas(ctx, prims(o)); ctx.restore(); continue; }
    if (o.meas && o.t === 'line') { ctx.beginPath(); ctx.moveTo(o.x1, o.y1); ctx.lineTo(o.x2, o.y2); ctx.stroke(); primsCanvas(ctx, prims(o)); ctx.restore(); continue; }
    if (o.t === 'mark') {
      ctx.globalAlpha = o.kind === 'hl' ? (o.op < 1 ? o.op : 0.45) : (o.op || 1);
      if (o.kind === 'hl') ctx.globalCompositeOperation = 'multiply';
      for (const [x, y, w, h] of o.rects) {
        if (o.kind === 'hl') { ctx.fillStyle = o.sc; ctx.fillRect(x, y, w, h); }
        else { const yy = o.kind === 'ul' ? y + h * 0.93 : y + h * 0.55; ctx.lineWidth = Math.max(0.8, h * 0.07); ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke(); }
      }
    } else if (o.t === 'rect' || o.t === 'white' || o.t === 'hilite' || o.t === 'ellipse') {
      ctx.beginPath();
      if (o.t === 'ellipse') ctx.ellipse(o.x + o.w / 2, o.y + o.h / 2, o.w / 2, o.h / 2, 0, 0, Math.PI * 2); else ctx.rect(o.x, o.y, o.w, o.h);
      if (o.fc) ctx.fill();
      if (o.sc && o.lw > 0) ctx.stroke();
    } else if (o.t === 'line' || o.t === 'arrow') {
      ctx.beginPath(); ctx.moveTo(o.x1, o.y1); ctx.lineTo(o.x2, o.y2);
      if (o.t === 'arrow') { const [a, b, c] = arrowHead(o); ctx.moveTo(...a); ctx.lineTo(...b); ctx.lineTo(...c); }
      ctx.stroke();
    } else if (o.t === 'pen') {
      for (const s of o.pts) { ctx.beginPath(); s.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke(); }
    } else if (PIC.has(o.t)) {
      const [w0, h0] = dims0(o);
      ctx.translate(o.x + o.w / 2, o.y + o.h / 2);
      if (o.r) ctx.rotate(o.r * Math.PI / 180);
      const src = o.t === 'image' ? (d.ed.imgs.get(o.img) || {}).el : raster(o).canvas;
      if (src) ctx.drawImage(src, -w0 / 2, -h0 / 2, w0, h0);
    }
    ctx.restore();
  }
}

// ───────────────────────── 열기: 있던 주석 읽기 ─────────────────────────
export const refId = (r) => r.objectNumber + 'R' + (r.generationNumber ? r.generationNumber : '');
const look = (doc, v) => (v instanceof PDFRef ? doc.context.lookup(v) : v);
const nums = (doc, v) => { v = look(doc, v); return v instanceof PDFArray ? v.asArray().map((x) => { x = look(doc, x); return x instanceof PDFNumber ? x.asNumber() : NaN; }) : null; };
const hex = (r, g, b) => '#' + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, '0')).join('');
function colorOf(doc, v) {
  const c = nums(doc, v);
  if (!c || !c.length) return '';
  if (c.length === 1) return hex(c[0], c[0], c[0]);
  if (c.length === 3) return hex(...c);
  if (c.length === 4) { const [C, M, Y, Kk] = c; return hex((1 - C) * (1 - Kk), (1 - M) * (1 - Kk), (1 - Y) * (1 - Kk)); }
  return '';
}
const textOf = (doc, v) => { v = look(doc, v); return v instanceof PDFString || v instanceof PDFHexString ? v.decodeText() : ''; };
const numOf = (doc, v, def) => { v = look(doc, v); return v instanceof PDFNumber ? v.asNumber() : def; };
const nameOf = (v) => (v instanceof PDFName ? v.decodeText() : '');
function widthOf(doc, dict) {
  const bs = look(doc, dict.get(N('BS')));
  if (bs instanceof PDFDict) { const w = numOf(doc, bs.get(N('W')), null); if (w != null) return w; }
  const b = nums(doc, dict.get(N('Border')));
  return b && b.length >= 3 ? b[2] : 1;
}
function boxFromPdf(vp, [x1, y1, x2, y2]) {
  const pts = [[x1, y1], [x2, y1], [x1, y2], [x2, y2]].map(([x, y]) => vp.convertToViewportPoint(x, y));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}
async function decodeImage(doc, st) {
  if (!(st instanceof PDFRawStream)) return null;
  const dict = st.dict;
  const f = look(doc, dict.get(N('Filter')));
  const filters = f instanceof PDFName ? [nameOf(f)] : f instanceof PDFArray ? f.asArray().map((x) => nameOf(look(doc, x))) : [];
  const parms = look(doc, dict.get(N('DecodeParms')));
  if (parms instanceof PDFDict && numOf(doc, parms.get(N('Predictor')), 1) > 1) return null;
  const W = numOf(doc, dict.get(N('Width')), 0), H = numOf(doc, dict.get(N('Height')), 0);
  if (!W || !H || W * H > 40e6) return null;
  let cs = look(doc, dict.get(N('ColorSpace'))), comps = 0;
  if (cs instanceof PDFName) comps = { DeviceRGB: 3, DeviceGray: 1, DeviceCMYK: 4 }[nameOf(cs)] || 0;
  else if (cs instanceof PDFArray && nameOf(look(doc, cs.get(0))) === 'ICCBased') { const icc = look(doc, cs.get(1)); comps = icc && icc.dict ? numOf(doc, icc.dict.get(N('N')), 0) : 0; }
  const smaskSt = look(doc, dict.get(N('SMask')));
  let alpha = null;
  if (smaskSt instanceof PDFRawStream) {
    const a = await decodeImage(doc, smaskSt);
    if (!a || !a.gray) return null;
    alpha = a.gray;
  }
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d');
  if (filters.length === 1 && filters[0] === 'DCTDecode') {
    const bytes = st.getContents();
    const bmp = await createImageBitmap(new Blob([bytes], { type: 'image/jpeg' }));
    c.drawImage(bmp, 0, 0, W, H);
    if (!alpha) return { blob: new Blob([bytes], { type: 'image/jpeg' }) };
  } else if ((filters.length === 0 || (filters.length === 1 && filters[0] === 'FlateDecode')) && numOf(doc, dict.get(N('BitsPerComponent')), 8) === 8 && (comps === 1 || comps === 3)) {
    const px = filters.length ? decodePDFRawStream(st).decode() : st.getContents();
    if (px.length < W * H * comps) return null;
    if (comps === 1 && !alpha && !cs) return null;
    if (comps === 1 && dict.get(N('SMask')) == null && nameOf(cs) === 'DeviceGray') {
      //  SMask 로 쓰이는 회색 그림이면 그대로 돌려준다
      if (!alpha) { const id = c.createImageData(W, H); for (let i = 0; i < W * H; i++) { id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = px[i]; id.data[i * 4 + 3] = 255; } c.putImageData(id, 0, 0); return { gray: px.subarray(0, W * H), blob: await new Promise((r) => cv.toBlob(r, 'image/png')) }; }
    }
    const id = c.createImageData(W, H);
    for (let i = 0; i < W * H; i++) {
      if (comps === 3) { id.data[i * 4] = px[i * 3]; id.data[i * 4 + 1] = px[i * 3 + 1]; id.data[i * 4 + 2] = px[i * 3 + 2]; }
      else id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = px[i];
      id.data[i * 4 + 3] = 255;
    }
    c.putImageData(id, 0, 0);
  } else return null;
  if (alpha) {
    const id = c.getImageData(0, 0, W, H);
    for (let i = 0; i < W * H; i++) id.data[i * 4 + 3] = alpha[i];
    c.putImageData(id, 0, 0);
  }
  return { blob: await new Promise((r) => cv.toBlob(r, 'image/png')) };
}
//  모양(AP) 안에서 첫 그림을 찾는다 — 상용 프로그램의 스탬프는 폼 안에 폼이 들어 있기도 하다
async function findApImage(doc, form, depth = 0) {
  if (!(form instanceof PDFRawStream) || depth > 3) return null;
  const res = look(doc, form.dict.get(N('Resources')));
  const xo = res instanceof PDFDict ? look(doc, res.get(N('XObject'))) : null;
  if (!(xo instanceof PDFDict)) return null;
  for (const [, v] of xo.entries()) {
    const st = look(doc, v);
    if (!(st instanceof PDFRawStream)) continue;
    const sub = nameOf(look(doc, st.dict.get(N('Subtype'))));
    if (sub === 'Image') { const r = await decodeImage(doc, st); if (r) return r; }
    else if (sub === 'Form') { const r = await findApImage(doc, st, depth + 1); if (r) return r; }
  }
  return null;
}
async function readAnnot(doc, dict, vp, E) {
  const sub = nameOf(look(doc, dict.get(N('Subtype'))));
  const flags = numOf(doc, dict.get(N('F')), 0);
  if (flags & 2) return null;                       //  숨김
  let meta = {};
  const hj = textOf(doc, dict.get(N('HanilObj')));
  if (hj) { try { meta = JSON.parse(hj); } catch {} }
  const rect = nums(doc, dict.get(N('Rect')));
  if (!rect || rect.length !== 4 || rect.some(isNaN)) return null;
  const base = { sc: colorOf(doc, dict.get(N('C'))), fc: '', lw: widthOf(doc, dict), op: numOf(doc, dict.get(N('CA')), 1), fs: 14 };
  //  저장한 뒤 페이지가 돌았으면(구성 → 회전) 속 그림도 그만큼 돌아 보인다
  const r = meta.pr != null ? (((meta.r || 0) + vp.rotation - meta.pr) % 360 + 360) % 360 : 0;
  const it = nameOf(look(doc, dict.get(N('IT'))));
  const ratio = meta.ratio || 1;
  if (sub === 'Polygon' || sub === 'PolyLine') {
    const v = nums(doc, dict.get(N('Vertices')));
    if (!v || v.length < 4) return null;
    const vs = [];
    for (let k = 0; k + 1 < v.length; k += 2) vs.push(vp.convertToViewportPoint(v[k], v[k + 1]));
    const be = look(doc, dict.get(N('BE')));
    const cloud = be instanceof PDFDict && nameOf(look(doc, be.get(N('S')))) === 'C';
    const kind = meta.kind || (sub === 'PolyLine' ? 'polyline' : cloud ? 'cloud' : 'polygon');
    const meas = meta.meas || (it === 'PolygonDimension' ? 'area' : it === 'PolyLineDimension' ? 'perim' : undefined);
    return { ...base, t: 'poly', kind, vs, fc: colorOf(doc, dict.get(N('IC'))), sc: base.sc || '#e5262e', ...(meas ? { meas, ratio } : {}) };
  }
  if (sub === 'Link') {
    const a = look(doc, dict.get(N('A')));
    let url = null, page = null;
    if (a instanceof PDFDict) {
      const S = nameOf(look(doc, a.get(N('S'))));
      if (S === 'URI') url = textOf(doc, a.get(N('URI')));
      else if (S === 'GoTo') { const dd = look(doc, a.get(N('D'))); if (dd instanceof PDFArray && dd.get(0) instanceof PDFRef) page = E._pageIdx.get(refId(dd.get(0))); }
    }
    const dst = look(doc, dict.get(N('Dest')));
    if (dst instanceof PDFArray && dst.get(0) instanceof PDFRef) page = E._pageIdx.get(refId(dst.get(0)));
    if (url == null && page == null) return null;          //  이름 붙은 목적지 등은 그대로 둔다
    return { ...boxFromPdf(vp, rect), t: 'link', sc: '#1a73e8', fc: '', lw: 0, op: 1, fs: 14, ...(url != null ? { url } : { page }) };
  }
  if (sub === 'Redact') return { ...boxFromPdf(vp, rect), t: 'redact', sc: '#e5262e', fc: '', lw: 1.5, op: 1, fs: 14 };
  if (sub === 'FreeText' && (it === 'FreeTextCallout' || meta.t === 'callout')) {
    const cl = nums(doc, dict.get(N('CL')));
    const rd = nums(doc, dict.get(N('RD'))) || [0, 0, 0, 0];
    const r0 = [Math.min(rect[0], rect[2]), Math.min(rect[1], rect[3]), Math.max(rect[0], rect[2]), Math.max(rect[1], rect[3])];
    const b = boxFromPdf(vp, [r0[0] + rd[0], r0[1] + rd[3], r0[2] - rd[2], r0[3] - rd[1]]);
    const [ax, ay] = cl && cl.length >= 4 ? vp.convertToViewportPoint(cl[0], cl[1]) : [b.x - 30, b.y + b.h + 30];
    const da = textOf(doc, dict.get(N('DA')));
    const mf = /([\d.]+)\s+Tf/.exec(da);
    return { ...base, ...b, t: 'callout', ax, ay, text: textOf(doc, dict.get(N('Contents'))), fs: meta.fs || (mf ? +mf[1] : 12), sc: meta.sc || base.sc || '#000000', fc: meta.fc != null ? meta.fc : '#ffffff', tc: meta.tc || meta.sc || '#000000', lw: meta.lw || 1 };
  }
  if (sub === 'Highlight' || sub === 'Underline' || sub === 'StrikeOut') {
    const q = nums(doc, dict.get(N('QuadPoints')));
    if (!q || q.length < 8) return null;
    const rects = [];
    for (let k = 0; k + 7 < q.length; k += 8) {
      const pts = [0, 2, 4, 6].map((j) => vp.convertToViewportPoint(q[k + j], q[k + j + 1]));
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      rects.push([Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)]);
    }
    const kind = { Highlight: 'hl', Underline: 'ul', StrikeOut: 'so' }[sub];
    return { ...base, t: 'mark', kind, rects, sc: base.sc || MARK_TOOLS[{ hl: 'mhl', ul: 'mul', so: 'mso' }[kind]][1], op: kind === 'hl' ? Math.min(base.op, 0.45) : base.op };
  }
  if (sub === 'Text') {
    const b = boxFromPdf(vp, rect);
    return { ...base, x: b.x, y: b.y, w: Math.max(12, Math.min(b.w, 40)), h: Math.max(12, Math.min(b.h, 40)), t: 'note', text: textOf(doc, dict.get(N('Contents'))), fc: base.sc || '#ffd84d', sc: '', lw: 0 };
  }
  if (sub === 'Stamp' && meta.t === 'stamp') return { ...base, ...boxFromPdf(vp, rect), t: 'stamp', sym: meta.sym || textOf(doc, dict.get(N('Contents'))), sc: meta.sc || '#e5262e', fc: '', lw: 0, r };
  if (sub === 'Square' || sub === 'Circle') {
    const lw = base.lw, rd = nums(doc, dict.get(N('RD')));
    const r = [Math.min(rect[0], rect[2]), Math.min(rect[1], rect[3]), Math.max(rect[0], rect[2]), Math.max(rect[1], rect[3])];
    const ins = rd && rd.length === 4 ? rd : [lw / 2, lw / 2, lw / 2, lw / 2];
    const b = boxFromPdf(vp, [r[0] + ins[0], r[1] + ins[3], r[2] - ins[2], r[3] - ins[1]]);
    const t = sub === 'Circle' ? 'ellipse' : (meta.t === 'hilite' || meta.t === 'white' ? meta.t : 'rect');
    return { ...base, ...b, t, fc: colorOf(doc, dict.get(N('IC'))), sc: lw > 0 ? base.sc : '' };
  }
  if (sub === 'Line') {
    const l = nums(doc, dict.get(N('L')));
    if (!l || l.length !== 4) return null;
    let [x1, y1] = vp.convertToViewportPoint(l[0], l[1]), [x2, y2] = vp.convertToViewportPoint(l[2], l[3]);
    const le = look(doc, dict.get(N('LE')));
    const ends = le instanceof PDFArray ? le.asArray().map((x) => nameOf(look(doc, x))) : [];
    const head = (n) => n && n !== 'None';
    if (head(ends[0]) && !head(ends[1])) [x1, y1, x2, y2] = [x2, y2, x1, y1];
    const dist = meta.meas === 'dist' || it === 'LineDimension';
    return { ...base, t: head(ends[0]) || head(ends[1]) ? 'arrow' : 'line', x1, y1, x2, y2, ...(dist ? { meas: 'dist', ratio } : {}) };
  }
  if (sub === 'Ink') {
    const il = look(doc, dict.get(N('InkList')));
    if (!(il instanceof PDFArray)) return null;
    const pts = il.asArray().map((s) => { const a = nums(doc, s) || []; const out = []; for (let k = 0; k + 1 < a.length; k += 2) out.push(vp.convertToViewportPoint(a[k], a[k + 1])); return out; }).filter((s) => s.length);
    if (!pts.length) return null;
    return { ...base, t: 'pen', pts };
  }
  if (sub === 'FreeText') {
    const text = textOf(doc, dict.get(N('Contents')));
    const da = textOf(doc, dict.get(N('DA')));
    let fs = 12, sc = '#000000';
    const mf = /([\d.]+)\s+Tf/.exec(da); if (mf) fs = +mf[1] || 12;
    const mc = /([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg/.exec(da), mg = /([\d.]+)\s+g(\s|$)/.exec(da);
    if (mc) sc = hex(+mc[1], +mc[2], +mc[3]); else if (mg) sc = hex(+mg[1], +mg[1], +mg[1]);
    const b = boxFromPdf(vp, rect);
    if (meta.t === 'sym') return { ...base, ...b, t: 'sym', sym: text, sc: meta.sc || sc, fc: meta.fc || '', r };
    return { ...base, ...b, t: 'text', text, fs: meta.fs || fs, sc: meta.sc || sc, fc: meta.fc != null ? meta.fc : colorOf(doc, dict.get(N('C'))), auto: false, r };
  }
  if (sub === 'Stamp') {
    const ap = look(doc, dict.get(N('AP')));
    const nn = ap instanceof PDFDict ? look(doc, ap.get(N('N'))) : null;
    const im = await findApImage(doc, nn);
    if (!im) return null;
    const id = await registerImg(E, im.blob);
    return { ...base, ...boxFromPdf(vp, rect), t: 'image', img: id, sc: '', lw: 0, r };
  }
  return null;
}
export async function ensureLoaded(d) {
  const E = ed(d);
  if (E.loaded) return true;
  if (E.loading) return E.loading;
  E.loading = (async () => {
    let info = {};
    try { info = (await d.pdf.getMetadata()).info || {}; } catch {}
    if (info.EncryptFilterName || info.IsEncrypted) {
      A.ask('고칠 수 없음', '이 PDF 는 <b>암호(보안)</b>가 걸려 있어 고쳐 저장할 수 없습니다.<br>보기·찾기·인쇄는 됩니다.', { cancel: null });
      E.loading = null; return false;
    }
    let doc;
    try { doc = await PDFDocument.load(d.base.slice(0), { updateMetadata: false }); }
    catch (e) { A.ask('고칠 수 없음', '이 PDF 구조를 고칠 수 있게 읽지 못했습니다.<br><small>' + String(e.message || e).slice(0, 200) + '</small>', { cancel: null }); E.loading = null; return false; }
    const pages = doc.getPages();
    E._pageIdx = new Map(pages.map((p, k) => [refId(p.ref), k]));
    for (let i = 0; i < pages.length && i < d.n; i++) {
      const annots = pages[i].node.Annots();
      if (!annots) continue;
      const vp = await A.vp1(d, i);
      for (let k = 0; k < annots.size(); k++) {
        const ref = annots.get(k);
        if (!(ref instanceof PDFRef)) continue;
        const dict = doc.context.lookup(ref);
        if (!(dict instanceof PDFDict)) continue;
        let o = null;
        try { o = await readAnnot(doc, dict, vp, E); } catch (e) { console.warn('주석 읽기', e); }
        if (!o) continue;
        o.id = 'o' + (E.seq++); o.p = i; o.src = refId(ref);
        E.objs.push(o);
        E.managed.add(o.src);
        if (o.meas && o.ratio) E.ratio = o.ratio;
      }
    }
    E.loaded = true;
    if (E.managed.size) A.rerender(d);
    return true;
  })();
  return E.loading;
}

// ───────────────────────── 저장: 표준 주석으로 쓰기 ─────────────────────────
const f3 = (v) => (Math.round(v * 1000) / 1000).toString();
const rgb = (h) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16) / 255);
const pdfDate = (t = new Date()) => {
  const p = (n) => String(n).padStart(2, '0'), off = -t.getTimezoneOffset();
  return 'D:' + t.getFullYear() + p(t.getMonth() + 1) + p(t.getDate()) + p(t.getHours()) + p(t.getMinutes()) + p(t.getSeconds()) + (off >= 0 ? '+' : '-') + p(Math.floor(Math.abs(off) / 60)) + "'" + p(Math.abs(off) % 60) + "'";
};
function ellipseOps(x, y, w, h) {
  const k = 0.5523, cx = x + w / 2, cy = y + h / 2, rx = w / 2, ry = h / 2;
  return [cx + rx, cy, 'm', cx + rx, cy + ry * k, cx + rx * k, cy + ry, cx, cy + ry, 'c', cx - rx * k, cy + ry, cx - rx, cy + ry * k, cx - rx, cy, 'c',
    cx - rx, cy - ry * k, cx - rx * k, cy - ry, cx, cy - ry, 'c', cx + rx * k, cy - ry, cx + rx, cy - ry * k, cx + rx, cy, 'c'].map((v) => (typeof v === 'number' ? f3(v) : v)).join(' ') + '\n';
}
function rgbaXObject(ctx, data, w, h, refs) {
  const rgbB = new Uint8Array(w * h * 3), a = new Uint8Array(w * h);
  let hasA = false;
  for (let i = 0; i < w * h; i++) {
    rgbB[i * 3] = data[i * 4]; rgbB[i * 3 + 1] = data[i * 4 + 1]; rgbB[i * 3 + 2] = data[i * 4 + 2];
    a[i] = data[i * 4 + 3]; if (a[i] !== 255) hasA = true;
  }
  const d = { Type: 'XObject', Subtype: 'Image', Width: w, Height: h, ColorSpace: 'DeviceRGB', BitsPerComponent: 8 };
  if (hasA) { const sm = ctx.register(ctx.flateStream(a, { Type: 'XObject', Subtype: 'Image', Width: w, Height: h, ColorSpace: 'DeviceGray', BitsPerComponent: 8 })); refs.push(sm); d.SMask = sm; }
  const r = ctx.register(ctx.flateStream(rgbB, d));
  refs.push(r);
  return r;
}
function canvasPixels(src, w, h) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const c = cv.getContext('2d'); c.drawImage(src, 0, 0, w, h);
  return c.getImageData(0, 0, w, h).data;
}
//  새 도형 저장 — 그리기 조각(prims)으로 모양(AP)을 만들고 표준 주석 이름을 붙인다
function writePrimAnnot(doc, o, vp, pageRefs) {
  const ctx = doc.context, refs = [], res = {};
  const [a, b, c, dd] = vp.transform, det = a * dd - b * c;
  const Lm = [dd / det, -b / det, -c / det, a / det, 0, 0];
  const toPdf = (x, y) => vp.convertToPdfPoint(x, y);
  const meta = { t: o.t, kind: o.kind, meas: o.meas, ratio: o.ratio, sc: o.sc, fc: o.fc, tc: o.tc, lw: o.lw, op: o.op, fs: o.fs, pr: vp.rotation };
  const common = { Type: 'Annot', F: 4, NM: PDFString.of('hanil-' + o.id + '-' + Date.now().toString(36)), M: PDFString.of(pdfDate()), T: PDFHexString.fromText(style.author || AUTHOR), HanilObj: PDFHexString.fromText(JSON.stringify(meta)) };
  if (o.t === 'link') {
    const dict = { ...common, Subtype: 'Link', Rect: boxPdf(vp, o.x, o.y, o.x + o.w, o.y + o.h), Border: [0, 0, 0] };
    if (o.url) dict.A = { S: 'URI', URI: PDFString.of(o.url) };
    else if (o.page != null && pageRefs[o.page]) dict.Dest = [pageRefs[o.page], 'Fit'];
    else return null;
    delete dict.HanilObj; dict.HanilObj = PDFHexString.fromText(JSON.stringify(meta));
    return ctx.register(ctx.obj(dict));
  }
  let P = prims(o);
  if (o.t === 'line') P = [{ k: 'path', seg: [['M', o.x1, o.y1], ['L', o.x2, o.y2]], stroke: o.sc || '#000', lw: o.lw || 1, op: o.op }, ...P];
  let [x0, y0, x1, y1] = primsBox(P);
  const pad = (o.lw || 1) / 2 + 1;
  x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
  const ops = primsOps(ctx, P, res, refs);
  const ap = ctx.register(ctx.flateStream(ops, { Type: 'XObject', Subtype: 'Form', BBox: [x0, y0, x1, y1], Matrix: Lm, Resources: res }));
  refs.push(ap);
  const rect = boxPdf(vp, x0, y0, x1, y1);
  const dict = { ...common, Rect: rect, AP: { N: ap }, CA: o.op, BS: { W: o.lw || 1, S: 'S' } };
  if (o.sc) dict.C = rgb(o.sc);
  if (o.t === 'poly') {
    Object.assign(dict, { Subtype: o.kind === 'polyline' ? 'PolyLine' : 'Polygon', Vertices: o.vs.flatMap(([x, y]) => toPdf(x, y)) });
    if (o.fc && o.kind !== 'polyline') dict.IC = rgb(o.fc);
    if (o.kind === 'cloud') dict.BE = { S: 'C', I: 1 };
    if (o.meas) { dict.IT = o.meas === 'area' ? 'PolygonDimension' : 'PolyLineDimension'; dict.Contents = PDFHexString.fromText(measLabel(o)); }
  } else if (o.t === 'line') {
    Object.assign(dict, { Subtype: 'Line', L: [...toPdf(o.x1, o.y1), ...toPdf(o.x2, o.y2)], LE: ['None', 'None'], IT: 'LineDimension', Contents: PDFHexString.fromText(measLabel(o)) });
  } else if (o.t === 'callout') {
    const [ex, ey] = calloutAttach(o), inner = boxPdf(vp, o.x, o.y, o.x + o.w, o.y + o.h);
    Object.assign(dict, { Subtype: 'FreeText', IT: 'FreeTextCallout', CL: [...toPdf(o.ax, o.ay), ...toPdf(ex, ey)], LE: 'OpenArrow',
      Contents: PDFHexString.fromText(o.text || ''), DA: PDFString.of('/Helv ' + f3(o.fs || 12) + ' Tf ' + rgb(o.tc || o.sc || '#000000').map(f3).join(' ') + ' rg'),
      RD: [inner[0] - rect[0], rect[3] - inner[3], rect[2] - inner[2], inner[1] - rect[1]].map((v) => Math.max(0, v)) });
    if (o.fc) dict.C = rgb(o.fc);
  } else if (o.t === 'redact') {
    Object.assign(dict, { Subtype: 'Redact', QuadPoints: [...toPdf(o.x, o.y), ...toPdf(o.x + o.w, o.y), ...toPdf(o.x, o.y + o.h), ...toPdf(o.x + o.w, o.y + o.h)], IC: [0, 0, 0], OC: [1, 0, 0] });
  } else return null;
  dict.HanilRefs = refs;
  return ctx.register(ctx.obj(dict));
}
function writeAnnot(doc, pageRef, o, vp, E, pageRefs = []) {
  if (NEW_TYPES.has(o.t) || o.meas) return writePrimAnnot(doc, o, vp, pageRefs);
  const ctx = doc.context, refs = [], res = {};
  //  화면 좌표 → PDF 좌표(선형 부분) — 모양(AP)은 화면 좌표로 그리고 Matrix 로 돌린다(돌아간 페이지도 맞음)
  const [a, b, c, dd] = vp.transform, det = a * dd - b * c;
  const Lm = [dd / det, -b / det, -c / det, a / det, 0, 0];
  const pad = (o.t === 'arrow' ? Math.max(7, o.lw * 4) : 0) + (o.lw || 0) / 2 + 1;
  let [x0, y0, x1, y1] = bbox(o);
  x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
  let ops = '';
  if ((o.op < 1 || o.t === 'hilite') && o.t !== 'mark') {
    res.ExtGState = { G0: { Type: 'ExtGState', CA: o.op, ca: o.op, ...(o.t === 'hilite' ? { BM: 'Multiply' } : {}) } };
    ops += '/G0 gs\n';
  }
  if (o.t !== 'mark') {
    if (o.sc) ops += rgb(o.sc).map(f3).join(' ') + ' RG\n';
    if (o.fc) ops += rgb(o.fc).map(f3).join(' ') + ' rg\n';
    ops += f3(o.lw || 0) + ' w 1 J 1 j\n';
  }
  const paint = (o.fc ? (o.sc && o.lw > 0 ? 'B' : 'f') : (o.sc && o.lw > 0 ? 'S' : 'n')) + '\n';
  let sub, extra = {};
  const toPdf = (x, y) => vp.convertToPdfPoint(x, y);
  void toPdf;
  if (o.t === 'mark') {
    sub = { hl: 'Highlight', ul: 'Underline', so: 'StrikeOut' }[o.kind];
    if (o.kind === 'hl') { ops = '/G0 gs\n' + rgb(o.sc).map(f3).join(' ') + ' rg\n'; res.ExtGState = { G0: { Type: 'ExtGState', CA: 0.45, ca: 0.45, BM: 'Multiply' } }; for (const [x, y, w, h] of o.rects) ops += [x, y, w, h].map(f3).join(' ') + ' re f\n'; }
    else { ops = rgb(o.sc).map(f3).join(' ') + ' RG\n'; for (const [x, y, w, h] of o.rects) { const yy = o.kind === 'ul' ? y + h * 0.93 : y + h * 0.55; ops += f3(Math.max(0.8, h * 0.07)) + ' w ' + f3(x) + ' ' + f3(yy) + ' m ' + f3(x + w) + ' ' + f3(yy) + ' l S\n'; } }
    extra.QuadPoints = o.rects.flatMap(([x, y, w, h]) => [...toPdf(x, y), ...toPdf(x + w, y), ...toPdf(x, y + h), ...toPdf(x + w, y + h)]);
    extra.C = rgb(o.sc);
  } else if (o.t === 'rect' || o.t === 'hilite' || o.t === 'white' || o.t === 'ellipse') {
    sub = o.t === 'ellipse' ? 'Circle' : 'Square';
    ops += (o.t === 'ellipse' ? ellipseOps(o.x, o.y, o.w, o.h) : [o.x, o.y, o.w, o.h].map(f3).join(' ') + ' re\n') + paint;
    if (o.fc) extra.IC = rgb(o.fc);
    extra.BS = { W: o.sc ? o.lw : 0, S: 'S' };
    const inner = boxPdf(vp, o.x, o.y, o.x + o.w, o.y + o.h), outer = boxPdf(vp, x0, y0, x1, y1);
    extra.RD = [inner[0] - outer[0], outer[3] - inner[3], outer[2] - inner[2], inner[1] - outer[1]].map((v) => Math.max(0, v));
  } else if (o.t === 'line' || o.t === 'arrow') {
    sub = 'Line';
    ops += [o.x1, o.y1].map(f3).join(' ') + ' m ' + [o.x2, o.y2].map(f3).join(' ') + ' l S\n';
    if (o.t === 'arrow') { const [p, q, r] = arrowHead(o); ops += p.map(f3).join(' ') + ' m ' + q.map(f3).join(' ') + ' l ' + r.map(f3).join(' ') + ' l S\n'; }
    extra.L = [...toPdf(o.x1, o.y1), ...toPdf(o.x2, o.y2)];
    extra.LE = ['None', o.t === 'arrow' ? 'OpenArrow' : 'None'];
    extra.BS = { W: o.lw, S: 'S' };
  } else if (o.t === 'pen') {
    sub = 'Ink';
    for (const s of o.pts) ops += s.map(([x, y], k) => f3(x) + ' ' + f3(y) + (k ? ' l' : ' m')).join(' ') + ' S\n';
    extra.InkList = o.pts.map((s) => s.flatMap(([x, y]) => toPdf(x, y)));
    extra.BS = { W: o.lw, S: 'S' };
  } else {
    //  그림 붙이기: 글상자·기호·스탬프·메모는 미리 그린 그림, 이미지는 원본(JPEG 은 그대로 · 나머지는 RGB+투명)
    let im;
    if (o.t === 'stamp' || o.t === 'note') {
      const rr = raster(o);
      im = rgbaXObject(ctx, canvasPixels(rr.canvas, rr.canvas.width, rr.canvas.height), rr.canvas.width, rr.canvas.height, refs);
      if (o.t === 'stamp') { sub = 'Stamp'; extra.Name = 'Approved'; extra.Contents = PDFHexString.fromText(o.sym || ''); }
      else { sub = 'Text'; extra.Name = 'Comment'; extra.Open = false; extra.Contents = PDFHexString.fromText(o.text || ''); extra.C = rgb(o.fc || '#ffd84d'); }
    } else if (o.t === 'image') {
      const r = E.imgs.get(o.img);
      if (!r) return null;
      if (r.jpeg) { im = ctx.register(ctx.stream(r.jpeg, { Type: 'XObject', Subtype: 'Image', Width: r.nw, Height: r.nh, ColorSpace: 'DeviceRGB', BitsPerComponent: 8, Filter: 'DCTDecode' })); refs.push(im); }
      else im = rgbaXObject(ctx, canvasPixels(r.el, r.nw, r.nh), r.nw, r.nh, refs);
      sub = 'Stamp';
      extra.Name = 'Image';
    } else {
      const rr = raster(o);
      im = rgbaXObject(ctx, canvasPixels(rr.canvas, rr.canvas.width, rr.canvas.height), rr.canvas.width, rr.canvas.height, refs);
      sub = 'FreeText';
      const txt = o.t === 'sym' ? o.sym : o.text;
      extra.Contents = PDFHexString.fromText(txt || '');
      extra.DA = PDFString.of('/Helv ' + f3(o.fs || 12) + ' Tf ' + rgb(o.sc || '#000000').map(f3).join(' ') + ' rg');
      extra.BS = { W: 0 };
      if (o.fc) extra.C = rgb(o.fc);
    }
    res.XObject = { Im0: im };
    const [w0, h0] = dims0(o), rad = (o.r || 0) * Math.PI / 180, co = Math.round(Math.cos(rad)), si = Math.round(Math.sin(rad));
    ops += 'q ' + [co, si, -si, co, o.x + o.w / 2, o.y + o.h / 2].map(f3).join(' ') + ' cm ' + [w0, 0, 0, -h0, -w0 / 2, h0 / 2].map(f3).join(' ') + ' cm /Im0 Do Q\n';
    x0 = o.x; y0 = o.y; x1 = o.x + o.w; y1 = o.y + o.h;
  }
  const ap = ctx.register(ctx.flateStream(ops, { Type: 'XObject', Subtype: 'Form', BBox: [x0, y0, x1, y1], Matrix: Lm, Resources: res }));
  refs.push(ap);
  const meta = { t: o.t, sc: o.sc, fc: o.fc, lw: o.lw, op: o.op, fs: o.fs, r: o.r || 0, pr: vp.rotation, ...(o.t === 'stamp' ? { sym: o.sym } : {}) };
  const dict = {
    Type: 'Annot', Subtype: sub, Rect: boxPdf(vp, x0, y0, x1, y1), F: 4,
    NM: PDFString.of('hanil-' + o.id + '-' + Date.now().toString(36)), M: PDFString.of(pdfDate()),
    T: PDFHexString.fromText(style.author || AUTHOR), AP: { N: ap }, CA: o.op,
    ...(o.sc && sub !== 'FreeText' && sub !== 'Stamp' && sub !== 'Text' ? { C: rgb(o.sc) } : {}),
    ...extra,
    HanilObj: PDFHexString.fromText(JSON.stringify(meta)),
  };
  if (sub === 'FreeText' && !o.fc) dict.C = [];
  dict.HanilRefs = refs;
  return ctx.register(ctx.obj(dict));
}
function boxPdf(vp, x0, y0, x1, y1) {
  const pts = [[x0, y0], [x1, y0], [x0, y1], [x1, y1]].map(([x, y]) => vp.convertToPdfPoint(x, y));
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
//  고친 PDF 바이트 — 고친 것이 없으면 원본 그대로
export async function buildPdf(d) {
  const E = d.ed;
  //  고친 것이 없으면 원본 그대로 — 주석·책갈피·문서 속성 중 하나라도 고쳤으면 새로 만든다
  if (!(E && E.loaded) && !d.bmDirty && !d.metaEdit) return d.base;
  const doc = await PDFDocument.load(d.base.slice(0), { updateMetadata: false });
  if (!(E && E.loaded)) { doc.setProducer('한일 PDF 리더 · 한일특장(주)'); if (A.docHook) await A.docHook(doc, d); return await doc.save({ useObjectStreams: false }); }
  doc.setProducer('한일 PDF 리더 · 한일특장(주)');
  doc.setModificationDate(new Date());
  const ctx = doc.context, pages = doc.getPages();
  for (let i = 0; i < pages.length && i < d.n; i++) {
    const page = pages[i];
    let annots = page.node.Annots();
    if (annots) {
      //  가져와 고친 주석은 지우고(아래에서 새로 씀) · 그 주석에 딸린 쪽지(Popup)도 함께
      const gone = new Set();
      for (let k = annots.size() - 1; k >= 0; k--) {
        const r = annots.get(k);
        if (!(r instanceof PDFRef) || !E.managed.has(refId(r))) continue;
        const dict = ctx.lookup(r);
        if (dict instanceof PDFDict) {
          const own = look(doc, dict.get(N('HanilRefs')));
          if (own instanceof PDFArray) for (const x of own.asArray()) if (x instanceof PDFRef) ctx.delete(x);
          const pop = dict.get(N('Popup'));
          if (pop instanceof PDFRef) gone.add(refId(pop));
        }
        gone.add(refId(r));
        annots.remove(k);
        ctx.delete(r);
      }
      for (let k = annots.size() - 1; k >= 0; k--) {
        const r = annots.get(k);
        if (r instanceof PDFRef && gone.has(refId(r))) { annots.remove(k); ctx.delete(r); }
      }
    }
    const objs = E.objs.filter((o) => o.p === i);
    if (!objs.length) continue;
    if (!annots) { annots = ctx.obj([]); page.node.set(N('Annots'), annots); }
    const vp = await A.vp1(d, i);
    const pageRefs = pages.map((p) => p.ref);
    for (const o of objs) { const r = writeAnnot(doc, page.ref, o, vp, E, pageRefs); if (r) annots.push(r); }
  }
  if (A.docHook) await A.docHook(doc, d);
  return await doc.save({ useObjectStreams: false });
}
