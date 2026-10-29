//  📕 한일 PDF 리더 — 화면
//   엔진: pdf.js(Mozilla, Apache-2.0). 파일은 이 PC 밖으로 나가지 않는다(서버 없음).
//   ⭐ 오른쪽 「검색」 칸: 열린 문서·폴더 통째·고른 파일들에서 글자(도면 번호 등)를 찾아 문서별로 늘어놓는다.
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';
import { pageRaw, prepare, searchRaw, snippet } from './search.js';

const { getDocument, TextLayer, PDFWorker, PDFDateString } = pdfjsLib;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v != null) e.setAttribute(k, v);
  }
  for (const c of kids) if (c != null) e.append(c);
  return e;
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const CSS_PX = 96 / 72;
const viewer = $('#viewer');

// ───────────────────────── 엔진 준비 ─────────────────────────
//  ⚠ 단독 한 장(file://)에서도 돌게 일꾼(worker)·글꼴 표(CMap)·기본 글꼴을 모두 HTML 안에 품는다
const b64 = (s) => { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; };
class CMapFactory {
  async fetch({ name }) {
    const d = window.PDF_CMAPS && window.PDF_CMAPS[name];
    if (!d) throw new Error('글꼴 표(CMap) 없음: ' + name);
    return { cMapData: b64(d), isCompressed: true };
  }
}
class FontFactory {
  async fetch({ filename }) {
    const d = window.PDF_FONTS && window.PDF_FONTS[filename];
    if (!d) throw new Error('기본 글꼴 없음: ' + filename);
    return b64(d);
  }
}
let pdfWorker = null;
function worker() {
  if (!pdfWorker) {
    const src = $('#pdfworker').textContent;
    const url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
    //  ⭐ 일꾼 하나를 모든 문서가 함께 쓴다 — 문서를 닫아도 일꾼은 안 죽는다(getDocument 에 worker 를 직접 넘김)
    pdfWorker = new PDFWorker({ port: new Worker(url) });
  }
  return pdfWorker;
}
function loadPdf(bytes, name, { askPw = true } = {}) {
  const task = getDocument({
    data: bytes, worker: worker(), CMapReaderFactory: CMapFactory, StandardFontDataFactory: FontFactory,
    useWorkerFetch: false, enableXfa: false,
  });
  task.onPassword = (update, reason) => {
    if (!askPw) { task.__pw = true; task.destroy(); return; }
    ask('암호', '<b>' + esc(name) + '</b><br>' + (reason === 2 ? '<span style="color:#c00">암호가 틀렸습니다.</span> 다시 넣으세요.' : '이 문서는 암호가 걸려 있습니다.'), { input: 'password', ok: '열기' })
      .then((pw) => { if (pw == null) { task.__pw = true; task.destroy(); } else update(pw); });
  };
  return task;
}

// ───────────────────────── 작은 도구 ─────────────────────────
let toastT = 0;
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.style.display = 'block';
  clearTimeout(toastT); toastT = setTimeout(() => (t.style.display = 'none'), ms);
}
//  창 하나 — 단추를 누르면 그 값(입력칸이 있으면 입력한 글)으로 풀린다, 취소는 null
let modalDone = null;
const closeModal = () => modalDone && modalDone('__closed');
function ask(title, html, { input = null, ok = '확인', cancel = '취소', value = '' } = {}) {
  closeModal();
  return new Promise((res) => {
    const m = $('#modal');
    $('#mTitle').textContent = title;
    $('#mBody').innerHTML = html + (input ? '<input id="mIn" type="' + input + '">' : '');
    const foot = $('#mFoot'); foot.innerHTML = '';
    const done = (v) => { if (modalDone !== done) return; modalDone = null; m.classList.remove('on'); document.removeEventListener('keydown', key, true); res(v === '__closed' ? (input ? null : '__closed') : v); };
    modalDone = done;
    const okB = h('button', { text: ok, onclick: () => done(input ? $('#mIn').value : true) });
    foot.append(okB);
    if (cancel) foot.append(h('button', { text: cancel, onclick: () => done(null) }));
    const key = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(null); }
      if (e.key === 'Enter' && input) { e.preventDefault(); e.stopPropagation(); okB.click(); }
    };
    document.addEventListener('keydown', key, true);
    m.classList.add('on');
    if (input) { const i = $('#mIn'); i.value = value; setTimeout(() => i.focus(), 0); } else okB.focus();
  });
}
const fmtSize = (n) => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : n < 1073741824 ? (n / 1048576).toFixed(1) + ' MB' : (n / 1073741824).toFixed(2) + ' GB';
const fileKey = (f) => f.name + '|' + f.size + '|' + f.lastModified;
const isPdf = (f) => /\.pdf$/i.test(f.name) || f.type === 'application/pdf';
const collator = new Intl.Collator('ko', { numeric: true, sensitivity: 'base' });

// ───────────────────────── 문서 ─────────────────────────
const docs = [];
let cur = null;
let tool = 'hand';
let twoPage = false;
let nextId = 1;

async function openFiles(list) {
  const files = [...list].filter(isPdf);
  if (!files.length) { if (list.length) toast('PDF 파일이 아닙니다'); return; }
  let last = null;
  for (const f of files) last = (await openFile(f)) || last;
  if (last) activate(last);
}

async function openFile(file) {
  const key = fileKey(file);
  const have = docs.find((d) => d.key === key);
  if (have) { activate(have); return have; }
  const d = {
    id: nextId++, name: file.name, file, key, pdf: null, n: 0, pages: [], texts: [],
    zoom: 1, fit: 'width', rot: 0, cur: 1, sx: 0, sy: 0, hist: [], fwd: [], find: null, el: null, thumbs: null,
  };
  let task;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    task = loadPdf(bytes, file.name);
    d.pdf = await task.promise;
  } catch (e) {
    if (!(task && task.__pw)) ask('열 수 없음', '<b>' + esc(file.name) + '</b><br>' + esc(why(e)), { cancel: null });
    return null;
  }
  d.n = d.pdf.numPages;
  d.el = h('div', { class: 'doc' + (twoPage ? ' two' : '') });
  d.el.style.display = 'none';
  viewer.append(d.el);
  //  페이지 크기 — 첫 페이지 크기로 먼저 깔고, 나머지는 뒤에서 읽어 다르면 고친다(1000쪽 문서도 바로 뜨게)
  const p1 = await d.pdf.getPage(1);
  const v1 = p1.getViewport({ scale: 1 });
  for (let i = 0; i < d.n; i++) {
    const div = h('div', { class: 'pg', 'data-i': i });
    div.append(h('div', { class: 'ldg', text: (i + 1) + '' }));
    d.el.append(div);
    d.pages.push({ w: v1.width, h: v1.height, rot0: p1.rotate, div, key: null, busy: null });
  }
  docs.push(d);
  sizeRest(d);
  renderTabs();
  return d;
}
async function sizeRest(d) {
  for (let i = 1; i < d.n; i++) {
    if (!docs.includes(d)) return;
    const pg = await d.pdf.getPage(i + 1);
    const v = pg.getViewport({ scale: 1 });
    const p = d.pages[i];
    if (p.w !== v.width || p.h !== v.height || p.rot0 !== pg.rotate) {
      p.w = v.width; p.h = v.height; p.rot0 = pg.rotate;
      if (d === cur) keepAnchor(() => layoutPage(d, i)); else d.dirty = true;
    }
  }
}
function why(e) {
  const m = String((e && e.message) || e);
  if (/Invalid PDF|PDF header/i.test(m)) return 'PDF 파일이 아니거나 깨졌습니다.';
  if (/password/i.test(m)) return '암호가 필요합니다.';
  return m;
}

function closeDoc(d) {
  if (!d) return;
  const i = docs.indexOf(d);
  if (i < 0) return;
  docs.splice(i, 1);
  d.el.remove();
  d.pdf.destroy();
  if (cur === d) { cur = null; activate(docs[Math.min(i, docs.length - 1)] || null); }
  renderTabs();
}

function activate(d) {
  if (cur && cur !== d && cur.el) { cur.sx = viewer.scrollLeft; cur.sy = viewer.scrollTop; cur.el.style.display = 'none'; }
  cur = d;
  $('#emptyMsg').style.display = d ? 'none' : '';
  if (d) {
    d.el.style.display = '';
    d.el.classList.toggle('two', twoPage);
    if (d.dirty || !d.laid) { d.laid = true; d.dirty = false; applyZoom(d); }
    viewer.scrollLeft = d.sx; viewer.scrollTop = d.sy;
    viewer.focus({ preventScroll: true });
  }
  renderTabs(); buildThumbs(); buildOutline(); showProps(); updateUi(); schedule();
  if (findOpen()) refreshFindCount();
}

function renderTabs() {
  const bar = $('#doctabs'); bar.innerHTML = '';
  for (const d of docs) {
    const t = h('div', { class: 'dt' + (d === cur ? ' on' : ''), title: d.name },
      h('span', { text: d.name }), h('b', { text: '×', title: '닫기', onclick: (e) => { e.stopPropagation(); closeDoc(d); } }));
    t.addEventListener('mousedown', (e) => { if (e.button === 1) { e.preventDefault(); closeDoc(d); } });
    t.addEventListener('click', () => activate(d));
    bar.append(t);
  }
  whereText();
  $('#title').textContent = cur ? cur.name + ' — 한일 PDF 리더' : '한일 PDF 리더';
  document.title = cur ? cur.name + ' — 한일 PDF 리더' : '한일 PDF 리더';
}

// ───────────────────────── 배치 · 확대 ─────────────────────────
const scaleOf = (d) => d.zoom * CSS_PX;
function dims(d, p) {
  const r = (p.rot0 + d.rot) % 180 !== p.rot0 % 180;   //  돌린 만큼 가로세로가 바뀌나
  return r ? [p.h, p.w] : [p.w, p.h];
}
function layoutPage(d, i) {
  const p = d.pages[i];
  const [w, hh] = dims(d, p);
  const s = scaleOf(d);
  p.div.style.width = Math.floor(w * s) + 'px';
  p.div.style.height = Math.floor(hh * s) + 'px';
  p.div.style.setProperty('--scale-factor', s);
}
function fitZoom(d, mode) {
  const cw = viewer.clientWidth - 28, ch = viewer.clientHeight - 22;
  const p = d.pages[d.cur - 1] || d.pages[0];
  const [w, hh] = dims(d, p);
  let maxW = w;
  if (mode === 'width') for (const q of d.pages) maxW = Math.max(maxW, dims(d, q)[0]);
  const cols = twoPage ? 2 : 1;
  const zw = (cw - (cols - 1) * 10) / cols / (maxW * CSS_PX);
  if (mode === 'width') return zw;
  return Math.min(zw, ch / (hh * CSS_PX));
}
function applyZoom(d) {
  if (d.fit) d.zoom = Math.max(0.05, fitZoom(d, d.fit));
  d.zoom = Math.min(10, Math.max(0.05, d.zoom));
  for (let i = 0; i < d.n; i++) layoutPage(d, i);
  updateUi();
}
//  확대·회전 뒤에도 보고 있던 자리가 그대로 있게 — 기준점(화면 가운데 또는 마우스)이 있던 페이지의 같은 비율 자리로
function keepAnchor(fn, clientX = null, clientY = null) {
  const d = cur; if (!d) return fn();
  const vr = viewer.getBoundingClientRect();
  const ax = clientX == null ? vr.width / 2 : clientX - vr.left;
  const ay = clientY == null ? vr.height / 2 : clientY - vr.top;
  const i = pageAt(d, viewer.scrollTop + ay);
  const p = d.pages[i];
  const fy = (viewer.scrollTop + ay - p.div.offsetTop) / p.div.offsetHeight;
  const fx = (viewer.scrollLeft + ax - p.div.offsetLeft) / p.div.offsetWidth;
  fn();
  viewer.scrollTop = p.div.offsetTop + fy * p.div.offsetHeight - ay;
  viewer.scrollLeft = p.div.offsetLeft + fx * p.div.offsetWidth - ax;
  schedule();
}
function setZoom(z, cx, cy) {
  const d = cur; if (!d) return;
  keepAnchor(() => {
    if (z === 'width' || z === 'page') d.fit = z;
    else { d.fit = null; d.zoom = z; }
    applyZoom(d);
  }, cx, cy);
}
const STEPS = [0.1, 0.25, 0.33, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2, 3, 4, 6, 8];
function zoomStep(dir, cx, cy) {
  if (!cur) return;
  const z = cur.zoom;
  const n = dir > 0 ? STEPS.find((s) => s > z + 0.001) : [...STEPS].reverse().find((s) => s < z - 0.001);
  if (n) setZoom(n, cx, cy);
}
function rotate(by) {
  const d = cur; if (!d) return;
  const pg = d.cur;
  d.rot = (d.rot + by + 360) % 360;
  applyZoom(d);
  for (const p of d.pages) p.div.querySelectorAll('.hl,.lnk,.textLayer').forEach((e) => e.remove());
  buildThumbs();
  goPage(pg, { hist: false });
}

function pageAt(d, y) {
  //  y(스크롤 위치)에 걸친 페이지 — 반으로 갈라 찾는다
  let lo = 0, hi = d.n - 1;
  while (lo < hi) {
    const m = (lo + hi + 1) >> 1;
    if (d.pages[m].div.offsetTop <= y) lo = m; else hi = m - 1;
  }
  return lo;
}

// ───────────────────────── 그리기 ─────────────────────────
let schedT = 0;
function schedule() { if (!schedT) schedT = requestAnimationFrame(() => { schedT = 0; tick(); }); }
let queue = [], pumping = false;
function tick() {
  const d = cur; if (!d) return updateUi();
  const top = viewer.scrollTop, bot = top + viewer.clientHeight;
  let a = pageAt(d, top), b = pageAt(d, bot);
  if (twoPage) { a = Math.max(0, a - 1); b = Math.min(d.n - 1, b + 1); }
  //  지금 페이지 = 화면에 가장 많이 보이는 것
  let best = a, bestV = -1;
  for (let i = a; i <= b; i++) {
    const p = d.pages[i].div;
    const v = Math.min(bot, p.offsetTop + p.offsetHeight) - Math.max(top, p.offsetTop);
    if (v > bestV + 1) { bestV = v; best = i; }
  }
  if (d.cur !== best + 1) { d.cur = best + 1; markThumb(); }
  updatePageUi();
  const want = [];
  for (let i = a; i <= b; i++) want.push(i);
  if (b + 1 < d.n) want.push(b + 1);
  if (a - 1 >= 0) want.push(a - 1);
  queue = want.filter((i) => d.pages[i].key !== keyOf(d)).map((i) => [d, i]);
  //  멀리 간 페이지는 비운다(메모리)
  for (let i = 0; i < d.n; i++) {
    if (i < a - 6 || i > b + 6) unrender(d.pages[i]);
  }
  pump();
}
const keyOf = (d) => d.zoom.toFixed(4) + '|' + d.rot;
function unrender(p) {
  if (!p.key && !p.canvas) return;
  if (p.task) { try { p.task.cancel(); } catch {} p.task = null; }
  if (p.tl) { try { p.tl.cancel(); } catch {} p.tl = null; }
  p.div.querySelectorAll('canvas,.textLayer,.hl,.lnk').forEach((e) => e.remove());
  p.canvas = null; p.tdivs = null; p.key = null; p.gen = (p.gen || 0) + 1;
  if (!p.div.querySelector('.ldg')) p.div.append(h('div', { class: 'ldg', text: (+p.div.dataset.i + 1) + '' }));
}
async function pump() {
  if (pumping) return;
  pumping = true;
  try {
    while (queue.length) {
      const [d, i] = queue.shift();
      if (d !== cur) continue;
      try { await renderPage(d, i); } catch (e) { if (!/cancel/i.test(e && e.name + e.message)) console.warn(e); }
    }
  } finally { pumping = false; }
}
async function renderPage(d, i) {
  const p = d.pages[i];
  const key = keyOf(d);
  if (p.key === key) return;
  const gen = p.gen = (p.gen || 0) + 1;
  const stale = () => keyOf(d) !== key || p.gen !== gen || !docs.includes(d);
  const pg = await d.pdf.getPage(i + 1);
  const vp = pg.getViewport({ scale: scaleOf(d), rotation: (pg.rotate + d.rot) % 360 });
  //  ⚠ 캔버스가 너무 크면 브라우저가 못 그린다 — 1,600만 화소 안으로
  let ratio = window.devicePixelRatio || 1;
  const maxPx = 16e6;
  if (vp.width * vp.height * ratio * ratio > maxPx) ratio = Math.sqrt(maxPx / (vp.width * vp.height));
  const cv = document.createElement('canvas');
  cv.width = Math.floor(vp.width * ratio); cv.height = Math.floor(vp.height * ratio);
  const ctx = cv.getContext('2d', { alpha: false });
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  if (p.task) { try { p.task.cancel(); } catch {} }
  const task = pg.render({ canvasContext: ctx, viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null });
  p.task = task;
  await task.promise;
  p.task = null;
  if (stale()) return;
  //  새 그림이 다 그려진 뒤에 바꿔 끼운다(깜빡임 없이)
  p.div.querySelectorAll('canvas,.ldg').forEach((e) => e.remove());
  p.div.prepend(cv);
  p.canvas = cv;
  p.key = key;
  //  글자 층(고르기·찾은 자리 칠하기)
  const { tc } = await getText(d, i);
  if (stale()) return;
  p.div.querySelectorAll('.textLayer').forEach((e) => e.remove());
  if (p.tl) { try { p.tl.cancel(); } catch {} }
  const tdiv = h('div', { class: 'textLayer' });
  p.div.append(tdiv);
  const tl = new TextLayer({ textContentSource: tc, container: tdiv, viewport: vp });
  p.tl = tl;
  await tl.render();
  if (p.tl !== tl || stale()) return;
  p.tdivs = tl.textDivs;
  await drawLinks(d, i, pg, vp);
  paintHits(d, i);
}

//  📎 문서 안 고리(목차 → 페이지, 웹 주소)
async function drawLinks(d, i, pg, vp) {
  const p = d.pages[i];
  p.div.querySelectorAll('.lnk').forEach((e) => e.remove());
  let anns;
  try { anns = await pg.getAnnotations({ intent: 'display' }); } catch { return; }
  for (const a of anns) {
    if (a.subtype !== 'Link' || !(a.url || a.unsafeUrl || a.dest)) continue;
    const [x1, y1, x2, y2] = vp.convertToViewportRectangle(a.rect);
    const l = Math.min(x1, x2), t = Math.min(y1, y2);
    const el = h('div', { class: 'lnk', title: a.url || a.unsafeUrl || '이 문서 안으로 이동' });
    Object.assign(el.style, { left: l / vp.width * 100 + '%', top: t / vp.height * 100 + '%', width: Math.abs(x2 - x1) / vp.width * 100 + '%', height: Math.abs(y2 - y1) / vp.height * 100 + '%' });
    el.addEventListener('click', (e) => {
      if (dragMoved) return;
      e.stopPropagation();
      if (a.dest) goDest(d, a.dest);
      else openUrl(a.url || a.unsafeUrl);
    });
    p.div.append(el);
  }
}
function openUrl(u) {
  if (!/^(https?:|mailto:)/i.test(u)) return toast('열지 않는 주소: ' + u);
  ask('바깥 주소 열기', '이 주소를 새 창으로 엽니다.<br><b style="word-break:break-all">' + esc(u) + '</b>', { ok: '열기' })
    .then((ok) => ok && window.open(u, '_blank', 'noopener'));
}
async function goDest(d, dest) {
  try {
    const arr = typeof dest === 'string' ? await d.pdf.getDestination(dest) : dest;
    if (!arr) return;
    const ref = arr[0];
    const idx = typeof ref === 'object' && ref ? await d.pdf.getPageIndex(ref) : (Number.isInteger(ref) ? ref : 0);
    let y = null;
    if (arr[1] && arr[1].name === 'XYZ' && arr[3] != null) {
      const pg = await d.pdf.getPage(idx + 1);
      const vp = pg.getViewport({ scale: scaleOf(d), rotation: (pg.rotate + d.rot) % 360 });
      y = vp.convertToViewportPoint(arr[2] || 0, arr[3])[1];
    }
    goPage(idx + 1, { y });
  } catch (e) { console.warn(e); }
}

// ───────────────────────── 이동 ─────────────────────────
function goPage(n, { hist = true, y = null } = {}) {
  const d = cur; if (!d) return;
  n = Math.max(1, Math.min(d.n, n | 0));
  if (hist) pushHist(d);
  const p = d.pages[n - 1].div;
  viewer.scrollTop = p.offsetTop - 8 + (y ? Math.max(0, y - 10) : 0);
  if (!twoPage) viewer.scrollLeft = Math.max(0, p.offsetLeft - (viewer.clientWidth - p.offsetWidth) / 2);
  d.cur = n;
  schedule();
}
function pushHist(d) {
  const s = { top: viewer.scrollTop, left: viewer.scrollLeft };
  const last = d.hist[d.hist.length - 1];
  if (!last || Math.abs(last.top - s.top) > 40) d.hist.push(s);
  if (d.hist.length > 100) d.hist.shift();
  d.fwd = [];
  updateUi();
}
function histMove(back) {
  const d = cur; if (!d) return;
  const from = back ? d.hist : d.fwd, to = back ? d.fwd : d.hist;
  const s = from.pop(); if (!s) return;
  to.push({ top: viewer.scrollTop, left: viewer.scrollLeft });
  viewer.scrollTop = s.top; viewer.scrollLeft = s.left;
  schedule(); updateUi();
}

// ───────────────────────── 글자(찾기의 바탕) ─────────────────────────
function getText(d, i) {
  return d.texts[i] || (d.texts[i] = d.pdf.getPage(i + 1).then((pg) => pg.getTextContent()).then((tc) => {
    const m = pageRaw(tc.items, true);
    const v = { tc, raw: m.raw, it: m.it, off: m.off };
    d.texts[i].__v = v;                 //  칠하기(paintHits)가 기다리지 않고 바로 쓰게
    return v;
  }));
}

//  찾은 자리 칠하기 — 글자 층의 글자 범위(Range)가 차지하는 네모를 페이지 비율(%)로 그린다(확대해도 맞는다)
function paintHits(d, i) {
  const p = d.pages[i];
  p.div.querySelectorAll('.hl').forEach((e) => e.remove());
  const f = d.find;
  if (!f || !f.pages[i] || !f.pages[i].length || !p.tdivs) return;
  const t = d.texts[i] && d.texts[i].__v;
  if (!t) { getText(d, i).then(() => paintHits(d, i)); return; }
  const pr = p.div.getBoundingClientRect();
  if (!pr.width) return;
  f.pages[i].forEach((hit, k) => {
    let a = hit.rs, b = hit.re - 1;
    while (a <= b && t.it[a] < 0) a++;
    while (b >= a && t.it[b] < 0) b--;
    if (a > b) return;
    const sa = p.tdivs[t.it[a]], sb = p.tdivs[t.it[b]];
    if (!sa || !sb || !sa.firstChild || !sb.firstChild) return;
    const r = document.createRange();
    try { r.setStart(sa.firstChild, t.off[a]); r.setEnd(sb.firstChild, t.off[b] + 1); } catch { return; }
    const seen = new Set();
    const isCur = f.cur && f.cur.p === i && f.cur.k === k;
    for (const rc of r.getClientRects()) {
      if (rc.width < 0.5 || rc.height < 0.5) continue;
      const id = Math.round(rc.left) + ',' + Math.round(rc.top) + ',' + Math.round(rc.width);
      if (seen.has(id)) continue;
      seen.add(id);
      const e = h('div', { class: 'hl' + (isCur ? ' cur' : ''), 'data-k': k });
      Object.assign(e.style, {
        left: (rc.left - pr.left) / pr.width * 100 + '%', top: (rc.top - pr.top) / pr.height * 100 + '%',
        width: rc.width / pr.width * 100 + '%', height: rc.height / pr.height * 100 + '%',
      });
      p.div.append(e);
    }
  });
  if (f.want && f.want.p === i) { const w = f.want; f.want = null; scrollToHit(d, w.p, w.k); }
}
function scrollToHit(d, i, k) {
  const p = d.pages[i];
  const e = p.div.querySelector('.hl[data-k="' + k + '"]');
  if (!e) return false;
  const vr = viewer.getBoundingClientRect(), er = e.getBoundingClientRect();
  if (er.top < vr.top + 30 || er.bottom > vr.bottom - 30) viewer.scrollTop += er.top - vr.top - vr.height / 3;
  if (er.left < vr.left + 10 || er.right > vr.right - 10) viewer.scrollLeft += er.left - vr.left - vr.width / 2;
  return true;
}

// ───────────────────────── 찾기(이 문서) ─────────────────────────
//  d.find = { terms, o, pages:[페이지마다 찾은 자리들 | 아직 undefined], cur:{p,k}, done, total }
function startFind(d, q, o) {
  const terms = prepare(q, o);
  const sig = JSON.stringify([terms, o]);
  if (d.find && d.find.sig === sig) return d.find;
  const old = d.find;
  d.find = { sig, q, terms, o, pages: new Array(d.n), cur: null, done: false, total: 0, run: Symbol() };
  if (old) for (let i = 0; i < d.n; i++) if (d.pages[i].div.querySelector('.hl')) paintHits(d, i);
  if (!terms.length) { d.find.done = true; return d.find; }
  fillFind(d, d.find);
  return d.find;
}
async function findPage(d, f, i) {
  if (f.pages[i]) return f.pages[i];
  const t = await getText(d, i);
  if (!f.pages[i]) {
    f.pages[i] = searchRaw(t.raw, f.terms, f.o);
    f.total += f.pages[i].length;
    if (f.pages[i].length && d.pages[i].tdivs) paintHits(d, i);
  }
  return f.pages[i];
}
async function fillFind(d, f) {
  //  지금 페이지부터 끝까지, 그다음 처음부터
  const start = d.cur - 1;
  for (let j = 0; j < d.n; j++) {
    if (d.find !== f || !docs.includes(d)) return;
    await findPage(d, f, (start + j) % d.n);
    if (j % 20 === 0) refreshFindCount();
  }
  f.done = true;
  refreshFindCount();
}
async function findMove(dir) {
  const d = cur; if (!d) return;
  const q = $('#findIn').value;
  const f = startFind(d, q, { caseSens: $('#findCase').checked, word: $('#findWord').checked, ignoreSpace: false });
  if (!f.terms.length) return refreshFindCount();
  let p, k;
  if (f.cur) { p = f.cur.p; k = f.cur.k + dir; } else { p = d.cur - 1; k = dir > 0 ? 0 : -1; }
  for (let step = 0; step <= d.n; step++) {
    const hits = await findPage(d, f, p);
    if (k < 0) k = hits.length - 1;
    if (k >= 0 && k < hits.length) { setFindCur(d, f, p, k); return; }
    p = (p + dir + d.n) % d.n;
    k = dir > 0 ? 0 : -1;
  }
  f.cur = null;
  refreshFindCount();
}
function setFindCur(d, f, p, k) {
  const old = f.cur;
  f.cur = { p, k };
  if (old && old.p !== p) paintHits(d, old.p);
  if (d !== cur) return;
  const pv = d.pages[p];
  if (pv.tdivs) { paintHits(d, p); if (!scrollToHit(d, p, k)) { f.want = { p, k }; goPage(p + 1, { hist: false }); } }
  else { f.want = { p, k }; goPage(p + 1, { hist: false }); }
  refreshFindCount();
}
function refreshFindCount() {
  const d = cur, c = $('#findCnt'), inp = $('#findIn');
  const f = d && d.find;
  if (!f || !f.terms.length || f.q !== inp.value) { c.textContent = ''; inp.classList.remove('bad'); return; }
  inp.classList.toggle('bad', f.done && f.total === 0);
  if (!f.cur) { c.textContent = f.done ? (f.total ? f.total + '개' : '없음') : '찾는 중…'; return; }
  if (!f.done) { c.textContent = f.total + '+ 찾는 중'; return; }
  let n = 0;
  for (let i = 0; i < f.cur.p; i++) n += (f.pages[i] || []).length;
  c.textContent = (n + f.cur.k + 1) + ' / ' + f.total;
}
const findOpen = () => $('#findbar').classList.contains('on');
function openFind(text) {
  $('#findbar').classList.add('on');
  const i = $('#findIn');
  if (text != null) i.value = text;
  else { const sel = String(getSelection() || '').trim(); if (sel && sel.length < 80) i.value = sel; }
  i.focus(); i.select();
  refreshFindCount();
}
function closeFind() {
  $('#findbar').classList.remove('on');
  for (const d of docs) if (d.find) { d.find = null; for (let i = 0; i < d.n; i++) d.pages[i].div.querySelectorAll('.hl').forEach((e) => e.remove()); }
  viewer.focus({ preventScroll: true });
}
let findT = 0;
$('#findIn').addEventListener('input', () => {
  clearTimeout(findT);
  findT = setTimeout(() => { if (cur) { cur.find = null; findMove(1); } }, 250);
});
$('#findIn').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); findMove(e.shiftKey ? -1 : 1); }
  if (e.key === 'Escape') { e.preventDefault(); closeFind(); }
});
$('#findPrev').onclick = () => findMove(-1);
$('#findNext').onclick = () => findMove(1);
$('#findClose').onclick = closeFind;
$('#findCase').onchange = $('#findWord').onchange = () => { if (cur) { cur.find = null; findMove(1); } };
$('#quick').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); if (!cur) return toast('먼저 문서를 여세요'); openFind($('#quick').value); if (cur) cur.find = null; findMove(1); }
});

// ───────────────────────── 검색(여러 문서·폴더) ─────────────────────────
const S = { running: false, stop: false, groups: [], folder: [], folderName: '', files: [], terms: [], o: null, q: '', sel: null };
const textCache = new Map();          //  파일 → 페이지마다의 글(다시 찾을 때 빠르게)
let cacheChars = 0;
const CACHE_MAX = 120e6;

function sOpts() {
  const adv = $('#smAdv').checked || $('#opts').classList.contains('on');
  return {
    caseSens: adv && $('#oCase').checked, word: adv && $('#oWord').checked,
    ignoreSpace: adv ? $('#oSpace').checked : true, any: adv && $('#oAny').checked,
    sub: adv ? $('#oSub').checked : true, first: adv && $('#oFirst').checked,
  };
}
function whereText() {
  const w = $('#where').value, el = $('#where2');
  if (w === 'folder') el.textContent = S.folder.length || S.folderName ? '📁 ' + S.folderName + ' — PDF ' + S.folder.length + '개' : '';
  else if (w === 'files') el.textContent = S.files.length ? '📄 고른 파일 ' + S.files.length + '개' : '';
  else if (w === 'open') el.textContent = '열린 문서 ' + docs.length + '개';
  else if (w === 'cur') el.textContent = cur ? cur.name : '(열린 문서 없음)';
  else el.textContent = '';
}
$('#where').addEventListener('change', () => {
  const w = $('#where').value;
  if (w === 'folder') $('#fFolder').click();
  if (w === 'files') $('#fFiles').click();
  whereText();
});
$('#where2').addEventListener('click', () => {      //  같은 칸을 다시 고르면 change 가 안 온다 → 글을 눌러 다시 고르기
  const w = $('#where').value;
  if (w === 'folder') $('#fFolder').click();
  if (w === 'files') $('#fFiles').click();
});
$('#fFolder').addEventListener('change', (e) => {
  const all = [...e.target.files];
  e.target.value = '';
  const pdfs = all.filter(isPdf);
  if (!all.length) return;
  S.folderName = (all[0].webkitRelativePath || all[0].name).split('/')[0];
  S.folder = pdfs.sort((a, b) => collator.compare(a.webkitRelativePath || a.name, b.webkitRelativePath || b.name));
  whereText();
  if (!pdfs.length) toast('그 폴더에는 PDF 가 없습니다');
});
$('#fFiles').addEventListener('change', (e) => {
  S.files = [...e.target.files].filter(isPdf); e.target.value = ''; whereText();
});
$('#advLink').onclick = () => { $('#smAdv').checked = true; $('#opts').classList.add('on'); };
$('#smAdv').onchange = () => $('#opts').classList.add('on');
$('#smSimple').onchange = () => $('#opts').classList.remove('on');
$('#sOpt').onclick = () => { const on = $('#opts').classList.toggle('on'); $('#smAdv').checked = on; $('#smSimple').checked = !on; };
$('#sq').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); if (!S.running) runSearch(); } });
$('#sGo').onclick = () => (S.running ? (S.stop = true) : runSearch());
$('#sClear').onclick = () => { S.groups = []; $('#results').innerHTML = ''; setStat(0, '유휴'); $('#prog i').style.width = '0'; $('#sCsv').disabled = $('#sClear').disabled = true; };
$('#sCsv').onclick = saveCsv;

function setStat(files, state) {
  const items = S.groups.reduce((a, g) => a + g.hits.length, 0);
  $('#sstat').textContent = '발견: ' + S.groups.length + ' 문서, ' + items + ' 항목' + (files ? ' (살펴본 문서 ' + files + '개)' : '') + '\n상태: ' + state;
}

async function runSearch() {
  const q = $('#sq').value.trim();
  if (!q) { $('#sq').focus(); return toast('찾을 글자를 넣으세요'); }
  let w = $('#where').value;
  if (!w) { w = cur ? (docs.length > 1 ? 'open' : 'cur') : ''; if (w) $('#where').value = w; whereText(); }
  if (!w) return toast('어디에서 찾을지 고르세요(폴더 선택…)');
  const o = sOpts();
  const terms = prepare(q, o);
  let targets = [];
  if (w === 'cur') { if (cur) targets = [{ doc: cur, name: cur.name, path: cur.name }]; }
  else if (w === 'open') targets = docs.map((d) => ({ doc: d, name: d.name, path: d.name }));
  else {
    let list = w === 'folder' ? S.folder : S.files;
    if (w === 'folder' && !o.sub) list = list.filter((f) => (f.webkitRelativePath || '').split('/').length <= 2);
    targets = list.map((f) => ({ file: f, name: f.name, path: f.webkitRelativePath || f.name }));
  }
  if (!targets.length) return toast(w === 'folder' ? '폴더를 고르세요' : w === 'files' ? '파일을 고르세요' : '열린 문서가 없습니다');

  Object.assign(S, { running: true, stop: false, groups: [], terms, o, q, sel: null });
  $('#results').innerHTML = '';
  $('#sGo').textContent = '중지';
  $('#sCsv').disabled = $('#sClear').disabled = true;
  const bad = [], noText = [];
  const t0 = performance.now();
  let done = 0, lastUi = 0;
  for (const t of targets) {
    if (S.stop) break;
    const now = performance.now();
    if (now - lastUi > 120) { lastUi = now; setStat(done, '검색 중 (' + (done + 1) + '/' + targets.length + ') ' + t.path); $('#prog i').style.width = (done / targets.length * 100) + '%'; }
    try {
      const pages = await pagesOf(t);
      if (pages === null) { bad.push([t, '암호가 걸려 있음']); }
      else {
        if (!pages.some((r) => r.replace(/\s/g, '').length > 0)) noText.push(t);
        const g = { ...t, hits: [] };
        for (let i = 0; i < pages.length; i++) {
          const hs = searchRaw(pages[i], terms, o);
          hs.forEach((x, k) => g.hits.push({ p: i, k, ...snippet(pages[i], x.rs, x.re) }));
          if (o.first && g.hits.length) { g.hits.length = 1; break; }
        }
        if (g.hits.length) { S.groups.push(g); addGroup(g); }
      }
    } catch (e) { bad.push([t, why(e)]); }
    done++;
  }
  const sec = ((performance.now() - t0) / 1000).toFixed(1);
  $('#prog i').style.width = '100%';
  let state = (S.stop ? '중지됨' : '완료') + ' · ' + sec + '초';
  if (noText.length) state += '\n⚠ 글자가 없는(스캔한 그림) PDF ' + noText.length + '개는 찾을 수 없습니다';
  if (bad.length) state += '\n⚠ 열지 못한 PDF ' + bad.length + '개';
  setStat(done, state);
  if (bad.length || noText.length) addProblems(bad, noText);
  if (!S.groups.length) $('#results').prepend(h('div', { class: 'empty', text: '「' + q + '」을(를) 찾지 못했습니다' }));
  S.running = false;
  $('#sGo').textContent = '검색…';
  $('#sCsv').disabled = !S.groups.length;
  $('#sClear').disabled = false;
}

//  한 문서의 페이지마다 글 — 열린 문서는 그 문서에서, 아니면 파일을 잠깐 열어 읽고 닫는다
async function pagesOf(t) {
  if (t.doc && docs.includes(t.doc)) {
    const d = t.doc, out = [];
    for (let i = 0; i < d.n; i++) { if (S.stop) break; out.push((await getText(d, i)).raw); }
    return out;
  }
  const f = t.file, key = fileKey(f);
  const open = docs.find((d) => d.key === key);
  if (open) return pagesOf({ doc: open });
  if (textCache.has(key)) return textCache.get(key);
  const bytes = new Uint8Array(await f.arrayBuffer());
  const task = loadPdf(bytes, f.name, { askPw: false });
  let pdf;
  try { pdf = await task.promise; } catch (e) { if (task.__pw) return null; throw e; }
  const out = [];
  try {
    for (let i = 1; i <= pdf.numPages; i++) {
      if (S.stop) return out;
      const pg = await pdf.getPage(i);
      const tc = await pg.getTextContent();
      out.push(pageRaw(tc.items).raw);
      pg.cleanup();
    }
  } finally { pdf.destroy(); }
  const n = out.reduce((a, s) => a + s.length, 0);
  if (cacheChars + n < CACHE_MAX) { textCache.set(key, out); cacheChars += n; }
  return out;
}

function addGroup(g) {
  const head = h('div', { class: 'rh', title: g.path },
    h('i', { text: '▾' }), h('span', { text: '📄 ' + g.path }), h('em', { text: '(' + g.hits.length + ')' }));
  const box = h('div', { class: 'rd' }, head);
  head.onclick = () => { box.classList.toggle('shut'); head.firstChild.textContent = box.classList.contains('shut') ? '▸' : '▾'; };
  head.ondblclick = () => openHit(g, g.hits[0]);
  for (const x of g.hits) {
    const it = h('div', { class: 'ri', title: (x.pre + x.hit + x.post) });
    it.innerHTML = '<u>' + (x.p + 1) + '쪽</u>' + esc(x.pre) + '<b>' + esc(x.hit) + '</b>' + esc(x.post);
    it.onclick = () => { $$('.ri.on').forEach((e) => e.classList.remove('on')); it.classList.add('on'); openHit(g, x); };
    box.append(it);
  }
  $('#results').append(box);
}
function addProblems(bad, noText) {
  const box = h('div', { class: 'rd shut' });
  const head = h('div', { class: 'rh', style: 'color:#a15c00' }, h('i', { text: '▸' }), h('span', { text: '⚠ 찾지 못하는 문서 (' + (bad.length + noText.length) + ')' }));
  head.onclick = () => { box.classList.toggle('shut'); head.firstChild.textContent = box.classList.contains('shut') ? '▸' : '▾'; };
  box.append(head);
  for (const [t, r] of bad) box.append(h('div', { class: 'ri', text: t.path + ' — ' + r }));
  for (const t of noText) box.append(h('div', { class: 'ri', text: t.path + ' — 글자 없음(스캔 그림)', onclick: () => openTarget(t) }));
  $('#results').append(box);
}
async function openTarget(t) {
  if (t.doc && docs.includes(t.doc)) { activate(t.doc); return t.doc; }
  const f = t.file || (t.doc && t.doc.file);
  if (!f) return null;
  const d = await openFile(f);
  if (d) activate(d);
  return d;
}
//  결과 하나를 누르면: 그 문서를 열고, 같은 조건으로 그 문서 전체를 칠한 뒤, 그 자리(k번째)로 간다
async function openHit(g, x) {
  const d = await openTarget(g);
  if (!d) return;
  d.find = null;
  const f = startFind(d, S.q, { caseSens: S.o.caseSens, word: S.o.word, ignoreSpace: S.o.ignoreSpace, any: S.o.any });
  const hits = await findPage(d, f, x.p);
  if (x.k < hits.length) setFindCur(d, f, x.p, x.k); else goPage(x.p + 1);
}

function saveCsv() {
  const q = (s) => '"' + String(s).replace(/"/g, '""') + '"';
  const rows = [['문서', '경로', '쪽', '앞 글', '찾은 글자', '뒤 글'].map(q).join(',')];
  for (const g of S.groups) for (const x of g.hits) rows.push([g.name, g.path, x.p + 1, x.pre, x.hit, x.post].map(q).join(','));
  download(new Blob(['﻿' + rows.join('\r\n')], { type: 'text/csv' }), '검색결과_' + S.q.replace(/[\\/:*?"<>|]/g, '_').slice(0, 40) + '.csv');
}
function download(blob, name) {
  const a = h('a', { href: URL.createObjectURL(blob), download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 30000);
}

// ───────────────────────── 왼쪽: 페이지 그림 · 책갈피 ─────────────────────────
let thumbIO = null;
function buildThumbs() {
  const box = $('#thumbs');
  box.innerHTML = '';
  if (thumbIO) thumbIO.disconnect();
  const d = cur;
  if (!d) { box.append(h('div', { class: 'empty', text: '문서가 없습니다' })); return; }
  thumbIO = new IntersectionObserver((ents) => {
    for (const en of ents) if (en.isIntersecting) { thumbIO.unobserve(en.target); drawThumb(d, +en.target.dataset.i, en.target); }
  }, { root: box, rootMargin: '300px' });
  for (let i = 0; i < d.n; i++) {
    const [w, hh] = dims(d, d.pages[i]);
    const bw = 118, bh = Math.round(bw * hh / w);
    const t = h('div', { class: 'th' + (i + 1 === d.cur ? ' on' : ''), 'data-i': i },
      h('div', { class: 'box', style: 'width:' + bw + 'px;height:' + Math.min(bh, 200) + 'px' }), h('div', { text: String(i + 1) }));
    t.onclick = () => goPage(i + 1);
    box.append(t);
    thumbIO.observe(t);
  }
  d.thumbRot = d.rot;
}
async function drawThumb(d, i, t) {
  try {
    const pg = await d.pdf.getPage(i + 1);
    const v1 = pg.getViewport({ scale: 1, rotation: (pg.rotate + d.rot) % 360 });
    const s = Math.min(118 / v1.width, 200 / v1.height) * Math.min(2, window.devicePixelRatio || 1);
    const vp = pg.getViewport({ scale: s, rotation: (pg.rotate + d.rot) % 360 });
    const cv = h('canvas', { width: Math.floor(vp.width), height: Math.floor(vp.height) });
    await pg.render({ canvasContext: cv.getContext('2d'), viewport: vp }).promise;
    const box = t.querySelector('.box');
    box.innerHTML = '';
    box.append(cv);
  } catch {}
}
function markThumb() {
  const d = cur; if (!d) return;
  const box = $('#thumbs');
  $$('.th.on', box).forEach((e) => e.classList.remove('on'));
  const t = box.children[d.cur - 1];
  if (t && t.classList) {
    t.classList.add('on');
    if (!$('#left').classList.contains('off') && $('#thumbs').style.display !== 'none') {
      const br = box.getBoundingClientRect(), tr = t.getBoundingClientRect();
      if (tr.top < br.top || tr.bottom > br.bottom) box.scrollTop += tr.top - br.top - br.height / 2 + tr.height / 2;
    }
  }
}
async function buildOutline() {
  const box = $('#outline');
  box.innerHTML = '';
  const d = cur;
  if (!d) { box.append(h('div', { class: 'empty', text: '문서가 없습니다' })); return; }
  let ol = null;
  try { ol = await d.pdf.getOutline(); } catch {}
  if (cur !== d) return;
  if (!ol || !ol.length) { box.append(h('div', { class: 'empty', text: '책갈피가 없습니다' })); return; }
  const add = (items, parent, depth) => {
    for (const it of items) {
      const kids = it.items && it.items.length ? h('div', { class: 'olk' + (depth === 0 && items.length < 12 ? ' open' : '') }) : null;
      const tw = h('i', { text: kids ? (kids.classList.contains('open') ? '▾' : '▸') : '' });
      const row = h('div', { class: 'ol', style: 'padding-left:' + (4 + depth * 14) + 'px;' + (it.bold ? 'font-weight:700;' : '') + (it.italic ? 'font-style:italic' : ''), title: it.title }, tw, document.createTextNode(it.title));
      tw.onclick = (e) => { if (!kids) return; e.stopPropagation(); kids.classList.toggle('open'); tw.textContent = kids.classList.contains('open') ? '▾' : '▸'; };
      row.onclick = () => { if (it.dest) goDest(d, it.dest); else if (it.url) openUrl(it.url); };
      parent.append(row);
      if (kids) { parent.append(kids); add(it.items, kids, depth + 1); }
    }
  };
  add(ol, box, 0);
}
$$('.ltabs button').forEach((b) => b.onclick = () => {
  $$('.ltabs button').forEach((x) => x.classList.toggle('on', x === b));
  $('#thumbs').style.display = b.dataset.lt === 'thumbs' ? '' : 'none';
  $('#outline').style.display = b.dataset.lt === 'outline' ? '' : 'none';
  if (b.dataset.lt === 'thumbs') markThumb();
});

// ───────────────────────── 속성 ─────────────────────────
async function showProps() {
  const box = $('#pProps .pbody');
  const d = cur;
  if (!d) { box.innerHTML = '<div class="empty" style="padding-top:60px">속성 없음</div>'; return; }
  let meta = {};
  try { meta = await d.pdf.getMetadata(); } catch {}
  if (cur !== d) return;
  const info = meta.info || {};
  const date = (s) => { try { const x = PDFDateString.toDateObject(s); return x ? x.toLocaleString('ko-KR') : s || ''; } catch { return s || ''; } };
  const p = d.pages[d.cur - 1];
  const [w, hh] = dims(d, p);
  const mm = (pt) => (pt / 72 * 25.4).toFixed(1);
  const rows = [
    ['#', '파일'], ['이름', d.name], ['크기', fmtSize(d.file.size) + ' (' + d.file.size.toLocaleString() + ' 바이트)'],
    ['쪽 수', d.n + '쪽'], ['이 쪽 크기', mm(w) + ' × ' + mm(hh) + ' mm' + paperName(w, hh)],
    ['#', '문서 정보'], ['제목', info.Title], ['작성자', info.Author], ['주제', info.Subject], ['키워드', info.Keywords],
    ['만든 프로그램', info.Creator], ['PDF 변환기', info.Producer], ['만든 날', date(info.CreationDate)], ['고친 날', date(info.ModDate)],
    ['#', '고급'], ['PDF 판', info.PDFFormatVersion], ['빠른 웹 보기', info.IsLinearized ? '예' : '아니요'],
    ['양식(폼)', info.IsAcroFormPresent ? '있음' : '없음'], ['암호화', info.EncryptFilterName || (info.IsEncrypted ? '예' : '없음')],
  ];
  box.innerHTML = '<table>' + rows.map(([k, v]) => k === '#' ? '<tr class="sec"><td colspan="2">' + esc(v) + '</td></tr>' : '<tr><td>' + esc(k) + '</td><td>' + esc(v == null || v === '' ? '—' : v) + '</td></tr>').join('') + '</table>';
}
function paperName(w, hh) {
  const a = Math.min(w, hh) / 72 * 25.4, b = Math.max(w, hh) / 72 * 25.4;
  const P = [['A0', 841, 1189], ['A1', 594, 841], ['A2', 420, 594], ['A3', 297, 420], ['A4', 210, 297], ['A5', 148, 210], ['B4', 257, 364], ['B5', 182, 257], ['Letter', 215.9, 279.4], ['Legal', 215.9, 355.6]];
  for (const [n, x, y] of P) if (Math.abs(a - x) < 3 && Math.abs(b - y) < 3) return ' (' + n + (w > hh ? ' 가로' : '') + ')';
  return '';
}

// ───────────────────────── 인쇄 · 저장 ─────────────────────────
async function printDoc() {
  const d = cur; if (!d) return;
  if (d.n > 300 && !(await ask('인쇄', d.n + '쪽입니다. 모두 준비하는 데 시간이 걸립니다. 계속할까요?', { ok: '계속' }))) return;
  const area = $('#printArea');
  area.innerHTML = '';
  let stop = false;
  ask('인쇄 준비', '<span id="prMsg">페이지 그리는 중…</span>', { ok: '그만', cancel: null }).then((v) => { if (v !== '__closed') stop = true; });
  const urls = [];
  for (let i = 1; i <= d.n && !stop; i++) {
    $('#prMsg') && ($('#prMsg').textContent = '페이지 그리는 중… ' + i + ' / ' + d.n);
    const pg = await d.pdf.getPage(i);
    const vp = pg.getViewport({ scale: 150 / 72, rotation: (pg.rotate + d.rot) % 360 });
    const cv = h('canvas', { width: Math.floor(vp.width), height: Math.floor(vp.height) });
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
    await pg.render({ canvasContext: ctx, viewport: vp, intent: 'print' }).promise;
    const blob = await new Promise((r) => cv.toBlob(r, 'image/jpeg', 0.92));
    const u = URL.createObjectURL(blob);
    urls.push(u);
    area.append(h('img', { src: u }));
  }
  if (stop) { area.innerHTML = ''; urls.forEach(URL.revokeObjectURL); return; }
  closeModal();
  await Promise.all($$('img', area).map((im) => im.decode().catch(() => {})));
  window.print();
  setTimeout(() => { area.innerHTML = ''; urls.forEach(URL.revokeObjectURL); }, 1000);
}
function saveDoc() { if (cur) download(cur.file, cur.name); }

// ───────────────────────── 리본 ─────────────────────────
const I = {
  open: '<path d="M2 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v1H7.5a2 2 0 0 0-1.9 1.4L3 18V6z" fill="#e8a21a"/><path d="M5.6 10.4A2 2 0 0 1 7.5 9H22l-3.2 9.4a2 2 0 0 1-1.9 1.6H3z" fill="#f6c444"/>',
  print: '<rect x="6" y="2" width="12" height="7" fill="#fff" stroke="#777"/><rect x="2" y="8" width="20" height="9" rx="2" fill="#7d7d7d"/><rect x="6" y="14" width="12" height="8" fill="#fff" stroke="#777"/>',
  save: '<path d="M4 3h13l4 4v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" fill="#6d5fc7"/><rect x="7" y="3" width="9" height="6" fill="#e7e3fb"/><rect x="6" y="13" width="12" height="8" fill="#fff"/>',
  hand: '<path d="M7 11V5.5a1.5 1.5 0 0 1 3 0V10V4a1.5 1.5 0 0 1 3 0v6V5a1.5 1.5 0 0 1 3 0v6-3a1.5 1.5 0 0 1 3 0v6c0 4.5-3 8-7.5 8-3 0-4.6-1.4-6.3-4L3.4 14a1.5 1.5 0 0 1 2.5-1.6L7 14z" fill="#fde7c4" stroke="#8a5a1c" stroke-width="1.2" stroke-linejoin="round"/>',
  select: '<path d="M8 4h3M9.5 4v16M8 20h3" stroke="#222" stroke-width="1.8" fill="none"/><rect x="12" y="8" width="9" height="8" fill="#9cc3f0"/><path d="M13 11h6M13 13.5h4" stroke="#1b4f8a" stroke-width="1.3"/>',
  actual: '<rect x="4" y="2" width="16" height="20" fill="#fff" stroke="#555"/><text x="12" y="16" font-size="8" text-anchor="middle" font-weight="700" fill="#2b6cb0">1:1</text>',
  width: '<rect x="4" y="2" width="16" height="20" fill="#fff" stroke="#555"/><path d="M2 12h20M5 9l-3 3 3 3M19 9l3 3-3 3" stroke="#2b6cb0" stroke-width="1.8" fill="none"/>',
  page: '<rect x="4" y="2" width="16" height="20" fill="#fff" stroke="#555"/><path d="M7 6h10v12H7z" stroke="#2b6cb0" stroke-width="1.8" fill="none"/>',
  zin: '<circle cx="10" cy="10" r="7" fill="#eaf3ff" stroke="#2b6cb0" stroke-width="2"/><path d="M15 15l6 6" stroke="#555" stroke-width="3"/><path d="M6.5 10h7M10 6.5v7" stroke="#2b6cb0" stroke-width="2"/>',
  zout: '<circle cx="10" cy="10" r="7" fill="#eaf3ff" stroke="#2b6cb0" stroke-width="2"/><path d="M15 15l6 6" stroke="#555" stroke-width="3"/><path d="M6.5 10h7" stroke="#2b6cb0" stroke-width="2"/>',
  rl: '<path d="M8 4a9 9 0 1 1-3 11" fill="none" stroke="#2b6cb0" stroke-width="2.2"/><path d="M3 3v6h6z" fill="#2b6cb0"/>',
  rr: '<path d="M16 4a9 9 0 1 0 3 11" fill="none" stroke="#2b6cb0" stroke-width="2.2"/><path d="M21 3v6h-6z" fill="#2b6cb0"/>',
  first: '<path d="M6 5v14M18 5l-9 7 9 7z" fill="#3b9a3b" stroke="#3b9a3b" stroke-width="2"/>',
  prev: '<path d="M16 5l-9 7 9 7z" fill="#3b9a3b"/>',
  next: '<path d="M8 5l9 7-9 7z" fill="#3b9a3b"/>',
  last: '<path d="M18 5v14M6 5l9 7-9 7z" fill="#3b9a3b" stroke="#3b9a3b" stroke-width="2"/>',
  find: '<rect x="3" y="2" width="14" height="18" fill="#fff" stroke="#666"/><path d="M6 7h8M6 10h8M6 13h5" stroke="#999"/><circle cx="15" cy="15" r="4.5" fill="#fff6c8" stroke="#2b6cb0" stroke-width="2"/><path d="M18 18l4 4" stroke="#555" stroke-width="2.6"/>',
  search: '<path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" fill="#f6c444"/><circle cx="13" cy="13" r="4.5" fill="#fff" stroke="#2b6cb0" stroke-width="2"/><path d="M16 16l5 5" stroke="#555" stroke-width="2.6"/>',
  left: '<rect x="2" y="3" width="20" height="18" fill="#fff" stroke="#555"/><rect x="2" y="3" width="7" height="18" fill="#9cc3f0" stroke="#555"/>',
  right: '<rect x="2" y="3" width="20" height="18" fill="#fff" stroke="#555"/><rect x="15" y="3" width="7" height="18" fill="#9cc3f0" stroke="#555"/>',
  props: '<rect x="3" y="3" width="18" height="18" fill="#fff" stroke="#555"/><path d="M6 8h4M6 12h4M6 16h4" stroke="#888" stroke-width="1.6"/><path d="M12 8h6M12 12h6M12 16h6" stroke="#2b6cb0" stroke-width="1.6"/>',
  one: '<rect x="7" y="2" width="10" height="9" fill="#fff" stroke="#555"/><rect x="7" y="13" width="10" height="9" fill="#fff" stroke="#555"/>',
  two: '<rect x="2" y="2" width="9" height="9" fill="#fff" stroke="#555"/><rect x="13" y="2" width="9" height="9" fill="#fff" stroke="#555"/><rect x="2" y="13" width="9" height="9" fill="#fff" stroke="#555"/><rect x="13" y="13" width="9" height="9" fill="#fff" stroke="#555"/>',
  full: '<path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6" fill="none" stroke="#2b6cb0" stroke-width="2.2"/>',
  help: '<circle cx="12" cy="12" r="10" fill="#2b6cb0"/><text x="12" y="17" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">?</text>',
  keys: '<rect x="2" y="6" width="20" height="12" rx="2" fill="#fff" stroke="#555"/><path d="M5 9h2M9 9h2M13 9h2M17 9h2M5 12h2M9 12h2M13 12h2M17 12h2M7 15h10" stroke="#555" stroke-width="1.5"/>',
};
const svg = (n) => '<svg viewBox="0 0 24 24">' + I[n] + '</svg>';
//  [모양, 명령, 글, 그림, 도움말]  big=큰 단추, sm=작은 단추(세 개씩 쌓음)
const RIB = {
  home: [
    ['파일', [['big', 'open', '열기', 'open', 'Ctrl+O'], ['big', 'print', '인쇄', 'print', 'Ctrl+P'], ['big', 'save', '저장', 'save', '다른 이름으로 저장 (Ctrl+S)']]],
    ['도구', [['big', 'hand', '손 도구', 'hand', '끌어서 움직이기 (H)'], ['big', 'select', '텍스트 선택', 'select', '글자를 골라 복사 (V)']]],
    ['보기', [['sm', 'actual', '실제 크기', 'actual', 'Ctrl+1'], ['sm', 'width', '너비 맞춤', 'width', 'Ctrl+2'], ['sm', 'page', '페이지 맞춤', 'page', 'Ctrl+0'], ['big', 'zoomIn', '확대', 'zin', 'Ctrl++'], ['big', 'zoomOut', '축소', 'zout', 'Ctrl+-']]],
    ['페이지', [['sm', 'first', '첫 페이지', 'first', 'Home'], ['sm', 'prev', '이전 페이지', 'prev', '←'], ['sm', 'next', '다음 페이지', 'next', '→'], ['sm', 'last', '마지막 페이지', 'last', 'End'], ['sm', 'rotL', '왼쪽으로 돌리기', 'rl', 'Ctrl+Shift+-'], ['sm', 'rotR', '오른쪽으로 돌리기', 'rr', 'Ctrl+Shift++']]],
    ['찾기', [['big', 'find', '찾기', 'find', '이 문서에서 (Ctrl+F)'], ['big', 'searchPane', '검색', 'search', '여러 문서·폴더에서 (Ctrl+Shift+F)']]],
  ],
  view: [
    ['창', [['big', 'leftPane', '탐색 창', 'left', '페이지 그림·책갈피 (F4)'], ['big', 'searchPane', '검색 창', 'search', 'Ctrl+Shift+F'], ['big', 'propsPane', '속성 창', 'props', '문서 정보']]],
    ['페이지 보기', [['big', 'one', '한 페이지 연속', 'one', ''], ['big', 'two', '두 페이지', 'two', '두 쪽씩 나란히']]],
    ['확대/축소', [['sm', 'actual', '실제 크기', 'actual', 'Ctrl+1'], ['sm', 'width', '너비 맞춤', 'width', 'Ctrl+2'], ['sm', 'page', '페이지 맞춤', 'page', 'Ctrl+0']]],
    ['회전', [['big', 'rotL', '왼쪽', 'rl', ''], ['big', 'rotR', '오른쪽', 'rr', '']]],
    ['화면', [['big', 'full', '전체 화면', 'full', 'F11']]],
  ],
  help: [
    ['도움말', [['big', 'keys', '단축키', 'keys', ''], ['big', 'about', '정보', 'help', '']]],
  ],
};
let ribTab = 'home';
function renderRibbon() {
  const r = $('#ribbon');
  r.innerHTML = '';
  for (const [cap, items] of RIB[ribTab]) {
    const row = h('div', { class: 'row' });
    let stack = null;
    for (const [kind, cmd, label, icon, tip] of items) {
      const b = h('button', { class: kind, 'data-cmd': cmd, title: label + (tip ? ' — ' + tip : '') });
      b.innerHTML = svg(icon) + '<span>' + esc(label) + '</span>';
      if (kind === 'sm') {
        if (!stack || stack.children.length >= 3) { stack = h('div', { class: 'stack' }); row.append(stack); }
        stack.append(b);
      } else { stack = null; row.append(b); }
    }
    r.append(h('div', { class: 'grp' }, row, h('div', { class: 'cap', text: cap })));
  }
  updateUi();
}
$$('#tabs .rt').forEach((b) => b.onclick = () => {
  if (b.dataset.rt === 'file') { $('#backstage').classList.toggle('on'); updateUi(); return; }
  ribTab = b.dataset.rt;
  $$('#tabs .rt').forEach((x) => x.classList.toggle('on', x === b));
  $('#ribbon').classList.remove('mini');
  renderRibbon();
});
$('#backstage').addEventListener('click', (e) => { if (e.target.id === 'backstage') $('#backstage').classList.remove('on'); });

function setTool(t) {
  tool = t;
  viewer.classList.toggle('hand', t === 'hand');
  updateUi();
}
function setTwo(on) {
  twoPage = on;
  for (const d of docs) { d.el.classList.toggle('two', on); if (d !== cur) d.dirty = true; }
  if (cur) { const pg = cur.cur; applyZoom(cur); goPage(pg, { hist: false }); }
  updateUi();
}
function togglePane(which) {
  if (which === 'left') { $('#left').classList.toggle('off'); }
  else {
    const p = which === 'search' ? $('#pSearch') : $('#pProps');
    const right = $('#right');
    const showing = !right.classList.contains('off') && !p.classList.contains('off');
    if (showing) p.classList.add('off'); else { p.classList.remove('off'); right.classList.remove('off'); }
    if ($('#pSearch').classList.contains('off') && $('#pProps').classList.contains('off')) right.classList.add('off');
    if (which === 'search' && !p.classList.contains('off')) { const q = $('#sq'); const sel = String(getSelection() || '').trim(); if (sel && sel.length < 80) q.value = sel; setTimeout(() => { q.focus(); q.select(); }, 0); }
  }
  if (cur && cur.fit) setZoom(cur.fit); else schedule();
  updateUi();
}

const CMD = {
  open: () => $('#fOpen').click(),
  save: saveDoc, print: printDoc,
  close: () => closeDoc(cur), closeAll: () => [...docs].forEach(closeDoc),
  props: () => { $('#pProps').classList.add('off'); togglePane('props'); },
  back: () => histMove(true), fwd: () => histMove(false),
  hand: () => setTool('hand'), select: () => setTool('select'),
  actual: () => setZoom(1), width: () => setZoom('width'), page: () => setZoom('page'),
  zoomIn: () => zoomStep(1), zoomOut: () => zoomStep(-1),
  first: () => goPage(1), prev: () => cur && goPage(cur.cur - (twoPage ? 2 : 1), { hist: false }),
  next: () => cur && goPage(cur.cur + (twoPage ? 2 : 1), { hist: false }), last: () => cur && goPage(cur.n),
  rotL: () => rotate(-90), rotR: () => rotate(90),
  find: () => (findOpen() ? closeFind() : openFind()),
  searchPane: () => togglePane('search'), propsPane: () => togglePane('props'), leftPane: () => togglePane('left'),
  closeSearch: () => togglePane('search'), closeProps: () => togglePane('props'),
  one: () => setTwo(false), two: () => setTwo(true),
  full: () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(() => {})),
  ribbonMini: () => $('#ribbon').classList.toggle('mini'),
  keys: () => about(true), about: () => about(false),
};
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-cmd]');
  if (!b || b.disabled) return;
  if (b.closest('#backstage')) $('#backstage').classList.remove('on');
  const f = CMD[b.dataset.cmd];
  if (f) f();
});

function about(keysOnly) {
  const keys = '<table style="border-collapse:collapse;font-size:12px">' + [
    ['Ctrl+O', '열기'], ['Ctrl+S', '다른 이름으로 저장'], ['Ctrl+P', '인쇄'], ['Ctrl+W', '문서 닫기'], ['Ctrl+Tab', '다음 문서'],
    ['Ctrl+F', '이 문서에서 찾기 (Enter 다음 · Shift+Enter 이전)'], ['Ctrl+Shift+F', '여러 문서·폴더에서 검색'],
    ['Ctrl + 바퀴 · Ctrl++ / Ctrl+-', '확대 / 축소'], ['Ctrl+0 · 1 · 2', '페이지 맞춤 · 실제 크기 · 너비 맞춤'],
    ['← → · PageUp/Down · Home/End', '페이지 넘기기'], ['Alt+← / Alt+→', '이전 보기 / 다음 보기'],
    ['H · V', '손 도구 · 텍스트 선택'], ['F4', '탐색 창'], ['Ctrl+Shift++ / -', '오른쪽·왼쪽으로 돌리기'],
  ].map(([k, v]) => '<tr><td style="padding:2px 12px 2px 0;white-space:nowrap"><kbd>' + k.split(' · ').join('</kbd> · <kbd>') + '</kbd></td><td>' + v + '</td></tr>').join('') + '</table>';
  const ver = (document.querySelector('meta[name=hanil-pdf]') || {}).content || '';
  const head = keysOnly ? '' : '<b>한일 PDF 리더</b> ' + esc(ver) + '<br>설치 없이 브라우저에서 PDF 를 보고, 여러 문서·폴더에서 글자를 찾습니다.<br>파일은 이 PC 밖으로 나가지 않습니다.<br><small style="color:#888">엔진: pdf.js (Mozilla, Apache-2.0)</small><hr style="border:0;border-top:1px solid #ddd">';
  ask(keysOnly ? '단축키' : '정보', head + keys, { cancel: null });
}

function updateUi() {
  const has = !!cur;
  $$('[data-cmd]').forEach((b) => {
    const c = b.dataset.cmd;
    if (['save', 'print', 'close', 'closeAll', 'props', 'actual', 'width', 'page', 'zoomIn', 'zoomOut', 'first', 'prev', 'next', 'last', 'rotL', 'rotR'].includes(c)) b.disabled = !has;
    if (c === 'back') b.disabled = !has || !cur.hist.length;
    if (c === 'fwd') b.disabled = !has || !cur.fwd.length;
    if (c === 'hand' || c === 'select') b.classList.toggle('on', tool === c);
    if (c === 'one' || c === 'two') b.classList.toggle('on', twoPage === (c === 'two'));
    if (c === 'width' || c === 'page') b.classList.toggle('on', has && cur.fit === c);
    if (c === 'leftPane') b.classList.toggle('on', !$('#left').classList.contains('off'));
    if (c === 'searchPane') b.classList.toggle('on', !$('#right').classList.contains('off') && !$('#pSearch').classList.contains('off'));
    if (c === 'propsPane') b.classList.toggle('on', !$('#right').classList.contains('off') && !$('#pProps').classList.contains('off'));
  });
  $('#pgIn').disabled = !has;
  const zs = $('#zoomSel');
  zs.disabled = !has;
  if (has) {
    const z = cur.fit || String(+cur.zoom.toFixed(2));
    const opt = [...zs.options].find((o) => o.value === z);
    if (opt) zs.value = z;
    else { const c = zs.querySelector('[value=custom]'); c.textContent = Math.round(cur.zoom * 100) + '%'; zs.value = 'custom'; }
  }
  updatePageUi();
}
function updatePageUi() {
  const d = cur;
  if (document.activeElement !== $('#pgIn')) $('#pgIn').value = d ? d.cur : '';
  $('#pgCnt').textContent = '/ ' + (d ? d.n : 0);
  if (d) {
    const [w, hh] = dims(d, d.pages[d.cur - 1]);
    $('#dims').textContent = (w / 72 * 25.4).toFixed(0) + ' × ' + (hh / 72 * 25.4).toFixed(0) + ' mm · ' + Math.round(d.zoom * 100) + '%';
  } else $('#dims').textContent = '';
}
$('#pgIn').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); goPage(parseInt($('#pgIn').value, 10) || 1); viewer.focus({ preventScroll: true }); }
  if (e.key === 'Escape') { $('#pgIn').blur(); updatePageUi(); }
});
$('#pgIn').addEventListener('blur', updatePageUi);
$('#zoomSel').addEventListener('change', () => {
  const v = $('#zoomSel').value;
  if (v !== 'custom') setZoom(v === 'width' || v === 'page' ? v : +v);
  viewer.focus({ preventScroll: true });
});

// ───────────────────────── 마우스 · 키보드 ─────────────────────────
viewer.addEventListener('scroll', schedule, { passive: true });
viewer.addEventListener('wheel', (e) => {
  if (!e.ctrlKey || !cur) return;
  e.preventDefault();
  const z = cur.zoom * Math.pow(1.0018, -e.deltaY);
  setZoom(Math.min(10, Math.max(0.05, z)), e.clientX, e.clientY);
}, { passive: false });
$('#emptyMsg').addEventListener('dblclick', () => { if (!cur) $('#fOpen').click(); });
let drag = null, dragMoved = false;
viewer.addEventListener('mousedown', (e) => {
  if (tool !== 'hand' || e.button !== 0 || !cur) return;
  const r = viewer.getBoundingClientRect();
  if (e.clientX - r.left >= viewer.clientWidth || e.clientY - r.top >= viewer.clientHeight) return;   //  스크롤 막대는 그대로
  drag = { x: e.clientX, y: e.clientY, l: viewer.scrollLeft, t: viewer.scrollTop };
  dragMoved = false;
  viewer.classList.add('grabbing');
  e.preventDefault();
  viewer.focus({ preventScroll: true });
});
window.addEventListener('mousemove', (e) => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 4) dragMoved = true;
  viewer.scrollLeft = drag.l - dx; viewer.scrollTop = drag.t - dy;
});
window.addEventListener('mouseup', () => { if (drag) { drag = null; viewer.classList.remove('grabbing'); setTimeout(() => (dragMoved = false), 0); } });

document.addEventListener('keydown', (e) => {
  if ($('#modal').classList.contains('on')) return;
  const k = e.key, c = e.ctrlKey || e.metaKey;
  const inInput = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  const run = (f) => { e.preventDefault(); CMD[f](); };
  if (c && !e.shiftKey && (k === 'o' || k === 'O')) return run('open');
  if (c && (k === 's' || k === 'S')) return run('save');
  if (c && (k === 'p' || k === 'P')) return run('print');
  if (c && (k === 'w' || k === 'W')) return run('close');
  if (c && e.shiftKey && (k === 'f' || k === 'F')) { e.preventDefault(); if ($('#right').classList.contains('off') || $('#pSearch').classList.contains('off')) togglePane('search'); else $('#sq').focus(); return; }
  if (c && (k === 'f' || k === 'F')) { e.preventDefault(); return openFind(); }
  if (c && k === 'Tab' && docs.length > 1) { e.preventDefault(); const i = docs.indexOf(cur); activate(docs[(i + (e.shiftKey ? -1 : 1) + docs.length) % docs.length]); return; }
  if (c && e.shiftKey && (k === '+' || k === '=')) return run('rotR');
  if (c && e.shiftKey && (k === '-' || k === '_')) return run('rotL');
  if (c && (k === '+' || k === '=')) return run('zoomIn');
  if (c && k === '-') return run('zoomOut');
  if (c && k === '0') return run('page');
  if (c && k === '1') return run('actual');
  if (c && k === '2') return run('width');
  if (k === 'F4') return run('leftPane');
  if (k === 'F1' && c) return run('ribbonMini');
  if (e.altKey && k === 'ArrowLeft') return run('back');
  if (e.altKey && k === 'ArrowRight') return run('fwd');
  if (k === 'Escape') { if ($('#backstage').classList.contains('on')) $('#backstage').classList.remove('on'); else if (findOpen() || docs.some((d) => d.find)) closeFind(); return; }
  if (k === 'F3') { e.preventDefault(); if (!findOpen()) openFind(); else findMove(e.shiftKey ? -1 : 1); return; }
  if (inInput || c || e.altKey || !cur) return;
  if (k === 'ArrowRight') return run('next');
  if (k === 'ArrowLeft') return run('prev');
  if (k === 'Home') return run('first');
  if (k === 'End') return run('last');
  if (k === 'h' || k === 'H') return run('hand');
  if (k === 'v' || k === 'V') return run('select');
});

//  끌어다 놓기
let dragDepth = 0;
const isFileDrag = (e) => [...(e.dataTransfer && e.dataTransfer.types || [])].includes('Files');
window.addEventListener('dragenter', (e) => { if (!isFileDrag(e)) return; e.preventDefault(); dragDepth++; $('#emptyMsg').classList.add('drag'); $('#emptyMsg').style.display = ''; });
window.addEventListener('dragover', (e) => { if (isFileDrag(e)) e.preventDefault(); });
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('#emptyMsg').classList.remove('drag'); if (cur) $('#emptyMsg').style.display = 'none'; } });
window.addEventListener('drop', (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault(); dragDepth = 0;
  $('#emptyMsg').classList.remove('drag'); if (cur) $('#emptyMsg').style.display = 'none';
  openFiles(e.dataTransfer.files);
});
$('#fOpen').addEventListener('change', (e) => { const f = [...e.target.files]; e.target.value = ''; openFiles(f); });

let resizeT = 0;
window.addEventListener('resize', () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => { if (cur && cur.fit) setZoom(cur.fit); else schedule(); for (const d of docs) if (d !== cur && d.fit) d.dirty = true; }, 120);
});
renderRibbon();
updateUi();
window.__pdfReader = { docs, openFiles, get cur() { return cur; }, runSearch, S };
