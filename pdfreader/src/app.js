//  📕 한일 PDF 리더 — 화면
//   엔진: pdf.js(Mozilla, Apache-2.0). 파일은 이 PC 밖으로 나가지 않는다(서버 없음).
//   ⭐ 오른쪽 「검색」 칸: 열린 문서·폴더 통째·고른 파일들에서 글자(도면 번호 등)를 찾아 문서별로 늘어놓는다.
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf.mjs';
import { pageRaw, prepare, searchRaw, snippet } from './search.js';
import * as EDIT from './edit.js';
import { PDFDocument, degrees, StandardFonts, rgb as pdfRgb } from 'pdf-lib';

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
//  🏭 만든 곳 — 화면·정보 창·저장한 PDF 의 「PDF 변환기」에 들어간다
const MAKER = '한일특장(주)';
//  윈도우 프로그램(hanil-pdf.exe)·크롬 확장 안에서 돌면 그쪽이 넣어 주는 것(저장·열기)
const HOST = window.HANIL_HOST || null;

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
    //  크롬 확장·포털: 일꾼 파일이 따로 있다 · 단독 한 장: HTML 안에 글로 들어 있다
    const url = window.PDF_WORKER_URL || URL.createObjectURL(new Blob([$('#pdfworker').textContent], { type: 'text/javascript' }));
    //  ⭐ 일꾼 하나를 모든 문서가 함께 쓴다 — 문서를 닫아도 일꾼은 안 죽는다(getDocument 에 worker 를 직접 넘김)
    pdfWorker = new PDFWorker({ port: new Worker(url) });
  }
  return pdfWorker;
}
function loadPdf(bytes, name, { askPw = true } = {}) {
  const task = getDocument({
    data: bytes, worker: worker(), CMapReaderFactory: CMapFactory, StandardFontDataFactory: FontFactory,
    useWorkerFetch: false, enableXfa: false,
    isEvalSupported: !window.HANIL_EXT,            //  ⚠ 크롬 확장은 eval 을 막는다
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
function ask(title, html, { input = null, ok = '확인', cancel = '취소', value = '', extra = null } = {}) {
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
    if (extra) foot.append(h('button', { text: extra, onclick: () => done('extra') }));
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

async function openFile(file, { handle = null, path = null } = {}) {
  const key = path || fileKey(file);
  const have = docs.find((d) => d.key === key);
  if (have) { activate(have); return have; }
  const d = {
    id: nextId++, name: file.name, file, key, pdf: null, n: 0, pages: [], texts: [],
    zoom: 1, fit: 'width', rot: 0, cur: 1, sx: 0, sy: 0, hist: [], fwd: [], find: null, el: null, thumbs: null,
    handle, path, base: null, ed: null, mod: false,
  };
  let task;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    d.base = bytes.slice();                 //  ⚠ pdf.js 가 bytes 를 일꾼에게 넘겨 비운다 — 고쳐 저장할 원본은 따로
    task = loadPdf(bytes, file.name);
    d.pdf = await task.promise;
    EDIT.attachDoc(d);
  } catch (e) {
    if (!(task && task.__pw)) ask('열 수 없음', '<b>' + esc(file.name) + '</b><br>' + esc(why(e)), { cancel: null });
    return null;
  }
  d.n = d.pdf.numPages;
  d.el = h('div', { class: 'doc' + (twoPage ? ' two' : '') });
  d.el.style.display = 'none';
  viewer.append(d.el);
  if (SET.zoom === '1') { d.fit = null; d.zoom = 1; } else d.fit = SET.zoom;
  //  페이지 크기 — 첫 페이지 크기로 먼저 깔고, 나머지는 뒤에서 읽어 다르면 고친다(1000쪽 문서도 바로 뜨게)
  await buildPages(d);
  docs.push(d);
  renderTabs();
  addRecent(d);
  return d;
}
async function sizeRest(d) {
  const pdf = d.pdf;
  for (let i = 1; i < d.n; i++) {
    if (!docs.includes(d) || d.pdf !== pdf) return;      //  닫았거나 페이지를 바꿔 다시 열었으면 그만
    let pg;
    try { pg = await pdf.getPage(i + 1); } catch { return; }
    if (d.pdf !== pdf) return;
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

async function closeDoc(d, force = false) {
  if (!d) return;
  if (d.mod && !force) {
    if (cur !== d) activate(d);
    const r = await ask('닫기', '<b>' + esc(d.name) + '</b><br>고친 내용을 저장할까요?', { ok: '저장', extra: '저장 안 함', cancel: '취소' });
    if (r === null || r === '__closed') return;
    if (r === true && !(await saveDoc(false))) return;
  }
  const i = docs.indexOf(d);
  if (i < 0) return;
  docs.splice(i, 1);
  for (const p of d.pages) unrender(p);
  pumpGen++;
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
      h('span', { text: (d.mod ? '● ' : '') + d.name }), h('b', { text: '×', title: '닫기', onclick: (e) => { e.stopPropagation(); closeDoc(d); } }));
    t.addEventListener('mousedown', (e) => { if (e.button === 1) { e.preventDefault(); closeDoc(d); } });
    t.addEventListener('click', () => activate(d));
    bar.append(t);
  }
  whereText();
  const t = cur ? (cur.mod ? '● ' : '') + cur.name + ' — 한일 PDF 리더' : '한일 PDF 리더';
  $('#title').textContent = t;
  document.title = t;
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
let queue = [], pumping = -1, pumpGen = 0;     //  ⚠ 문서를 다시 열면 pumpGen 을 올려, 옛 문서에서 멈춘 그리기를 기다리지 않는다
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
  p.div.querySelectorAll('canvas,.textLayer,.hl,.lnk,.ov,.tedit').forEach((e) => e.remove());
  p.ov = null;
  p.canvas = null; p.tdivs = null; p.key = null; p.gen = (p.gen || 0) + 1;
  if (!p.div.querySelector('.ldg')) p.div.append(h('div', { class: 'ldg', text: (+p.div.dataset.i + 1) + '' }));
}
async function pump() {
  if (pumping === pumpGen) return;
  const g = pumping = pumpGen;
  try {
    while (queue.length && g === pumpGen) {
      const [d, i] = queue.shift();
      if (d !== cur) continue;
      try { await renderPage(d, i); } catch (e) { if (!/cancel|destroyed/i.test(e && e.name + e.message)) console.warn(e); }
    }
  } finally { if (pumping === g) pumping = -1; }
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
  EDIT.drawOverlay(d, i);
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
  EDIT.drawOverlay(d, i);
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
  if (!t) { getText(d, i).then(() => paintHits(d, i), () => {}); return; }
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
    t.onclick = (e) => thumbClick(d, i, e);
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
  $$('.th', box).forEach((e) => e.classList.toggle('ps', !!(d.psel && d.psel.has(+e.dataset.i))));
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
    //  ⚠ 'display' 로 — 고치려고 가져온 주석은 숨기고, 고친 모양은 아래에서 그린다
    await pg.render({ canvasContext: ctx, viewport: vp }).promise;
    const sc = 150 / 72, p = d.pages[i - 1], W = p.w, H = p.h;
    const r = { 0: [1, 0, 0, 1, 0, 0], 90: [0, 1, -1, 0, H, 0], 180: [-1, 0, 0, -1, W, H], 270: [0, -1, 1, 0, 0, W] }[d.rot];
    EDIT.paintCanvas(ctx, d, i - 1, r.map((v) => v * sc));
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
//  💾 저장 — 고친 것이 있으면 표준 주석을 넣은 PDF 를 새로 만든다
//   윈도우 프로그램: 그 파일에 바로 · 크롬(파일을 「열기」로 연 것): 그 파일에 바로 · 그 밖: 저장할 곳을 묻거나 내려받기
async function saveDoc(asNew = false) {
  const d = cur; if (!d) return false;
  let bytes;
  try { toast('저장 준비 중…', 60000); bytes = await EDIT.buildPdf(d); }
  catch (e) { console.error(e); ask('저장하지 못함', esc(String(e.message || e)), { cancel: null }); return false; }
  const blob = new Blob([bytes], { type: 'application/pdf' });
  let name = d.name;
  try {
    if (HOST && HOST.save) {
      const r = await HOST.save(d, bytes, asNew);
      if (!r) { toast('저장을 그만두었습니다'); return false; }
      if (r.name) name = r.name;
      if (r.path) d.path = r.path;
    } else if (!asNew && d.handle && d.handle.createWritable) {
      if (d.handle.requestPermission && (await d.handle.requestPermission({ mode: 'readwrite' })) !== 'granted') throw new Error('그 파일에 쓸 권한을 받지 못했습니다');
      const w = await d.handle.createWritable(); await w.write(blob); await w.close();
    } else if (window.showSaveFilePicker) {
      const hd = await window.showSaveFilePicker({ suggestedName: d.name, types: [{ description: 'PDF 문서', accept: { 'application/pdf': ['.pdf'] } }] });
      const w = await hd.createWritable(); await w.write(blob); await w.close();
      d.handle = hd; name = hd.name;
    } else download(blob, d.name);
  } catch (e) {
    if (e && e.name === 'AbortError') { toast('저장을 그만두었습니다'); return false; }
    console.error(e);
    ask('저장하지 못함', esc(String(e.message || e)) + '<br><br>대신 내려받기로 저장합니다.', { cancel: null }).then(() => download(blob, d.name));
    return false;
  }
  d.name = name; d.mod = false;
  renderTabs();
  toast('저장했습니다 — ' + name);
  return true;
}

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
 sel: '<path d="M5 3l13 8-6 1.5 3.5 7-2.5 1.2-3.4-7L5 18z" fill="#fff" stroke="#222" stroke-width="1.4" stroke-linejoin="round"/>',
  tRect: '<rect x="3" y="5" width="18" height="14" fill="none" stroke="#e5262e" stroke-width="2.2"/>',
  tEll: '<ellipse cx="12" cy="12" rx="9.5" ry="7.5" fill="none" stroke="#e5262e" stroke-width="2.2"/>',
  tLine: '<path d="M3 20L21 4" stroke="#e5262e" stroke-width="2.4"/>',
  tArrow: '<path d="M3 20L20 5M12 5h8v8" fill="none" stroke="#e5262e" stroke-width="2.4" stroke-linejoin="round"/>',
  tPen: '<path d="M3 21l1.5-5L16 4.5l3.5 3.5L8 19.5z" fill="#ffd27a" stroke="#555" stroke-width="1.3"/><path d="M14 6.5l3.5 3.5" stroke="#555"/>',
  tHi: '<rect x="2" y="13" width="20" height="7" fill="#ffeb3b"/><path d="M6 3l9 0-2 9H8z" fill="#f5c400" stroke="#8a6d00"/>',
  tText: '<rect x="2" y="3" width="20" height="18" fill="#fff" stroke="#555"/><text x="12" y="17" text-anchor="middle" font-size="13" font-weight="700" fill="#e5262e">T</text>',
  tWhite: '<rect x="3" y="4" width="18" height="16" fill="#fff" stroke="#888" stroke-dasharray="2 2"/><path d="M6 9h12M6 13h8" stroke="#ccc" stroke-width="2"/>',
  tImg: '<rect x="2" y="4" width="20" height="16" rx="1" fill="#eaf3ff" stroke="#2b6cb0"/><circle cx="8" cy="9" r="2" fill="#f6c444"/><path d="M3 19l6-6 4 4 3-3 5 5z" fill="#3b9a3b"/>',
  undo: '<path d="M9 5L4 10l5 5" fill="none" stroke="#2b6cb0" stroke-width="2.2"/><path d="M4 10h10a6 6 0 0 1 0 12h-3" fill="none" stroke="#2b6cb0" stroke-width="2.2"/>',
  redo: '<path d="M15 5l5 5-5 5" fill="none" stroke="#2b6cb0" stroke-width="2.2"/><path d="M20 10H10a6 6 0 0 0 0 12h3" fill="none" stroke="#2b6cb0" stroke-width="2.2"/>',
  del: '<path d="M5 7h14l-1.2 14H6.2z" fill="#f3d2d2" stroke="#b22"/><path d="M3 7h18M9 7V4h6v3" fill="none" stroke="#b22" stroke-width="1.6"/>',
  dup: '<rect x="3" y="3" width="13" height="13" fill="#fff" stroke="#555"/><rect x="8" y="8" width="13" height="13" fill="#eaf3ff" stroke="#2b6cb0"/>',
  saveAs: '<path d="M4 3h13l4 4v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" fill="#6d5fc7"/><rect x="6" y="13" width="12" height="8" fill="#fff"/><path d="M14 4l6 6" stroke="#f6c444" stroke-width="3"/>',
  keys: '<rect x="2" y="6" width="20" height="12" rx="2" fill="#fff" stroke="#555"/><path d="M5 9h2M9 9h2M13 9h2M17 9h2M5 12h2M9 12h2M13 12h2M17 12h2M7 15h10" stroke="#555" stroke-width="1.5"/>',
};
const svg = (n) => '<svg viewBox="0 0 24 24">' + I[n] + '</svg>';
Object.assign(I, {
  snap: '<rect x="2" y="6" width="20" height="14" rx="2" fill="#6b7d93"/><circle cx="12" cy="13" r="4.2" fill="#dfe8f3" stroke="#fff" stroke-width="1.4"/><rect x="8" y="3.5" width="8" height="3" fill="#6b7d93"/>',
  clip: '<rect x="4" y="4" width="16" height="18" rx="1.5" fill="#d9a35b" stroke="#8a5a1c"/><rect x="7" y="2" width="10" height="5" rx="1" fill="#eee" stroke="#777"/><rect x="7" y="9" width="10" height="10" fill="#fff"/>',
  cut: '<circle cx="7" cy="18" r="3" fill="none" stroke="#555" stroke-width="2"/><circle cx="17" cy="18" r="3" fill="none" stroke="#555" stroke-width="2"/><path d="M9 16L17 3M15 16L7 3" stroke="#555" stroke-width="2"/>',
  copy: '<rect x="3" y="3" width="12" height="14" fill="#fff" stroke="#555"/><rect x="9" y="7" width="12" height="14" fill="#eaf3ff" stroke="#2b6cb0"/>',
  paste: '<rect x="4" y="4" width="14" height="18" rx="1.5" fill="#d9a35b" stroke="#8a5a1c"/><rect x="7" y="2" width="8" height="4" fill="#eee" stroke="#777"/><rect x="10" y="10" width="11" height="12" fill="#fff" stroke="#2b6cb0"/>',
  stampI: '<path d="M9 3h6v6l3 4H6l3-4z" fill="#8b8b8b"/><rect x="3" y="13" width="18" height="4" fill="#6b6b6b"/><rect x="3" y="19" width="18" height="2" fill="#e5262e"/>',
  note: '<path d="M3 3h18v13l-5 5H3z" fill="#ffd84d" stroke="#8a6d00"/><path d="M16 21v-5h5" fill="#f0c020" stroke="#8a6d00"/><path d="M6 8h12M6 11h12M6 14h7" stroke="#8a6d00"/>',
  type: '<rect x="2" y="3" width="20" height="18" fill="#fff" stroke="#777"/><text x="5" y="16" font-size="11" font-weight="700" fill="#222">T</text><path d="M14 6v12" stroke="#222"/>',
  hlT: '<rect x="3" y="12" width="18" height="8" fill="#ffeb3b"/><text x="12" y="18" text-anchor="middle" font-size="13" font-weight="700" fill="#222">T</text>',
  ulT: '<text x="12" y="16" text-anchor="middle" font-size="14" font-weight="700" fill="#222">T</text><path d="M4 20h16" stroke="#1a73e8" stroke-width="2.4"/>',
  soT: '<text x="12" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#222">T</text><path d="M4 13h16" stroke="#e5262e" stroke-width="2.4"/>',
  eraser: '<path d="M3 16l9-9 7 7-6 6H7z" fill="#f4a3b4" stroke="#a33"/><path d="M12 7l7 7" stroke="#a33"/><path d="M7 20h14" stroke="#555"/>',
  ins: '<path d="M5 2h9l5 5v15H5z" fill="#fff" stroke="#555"/><circle cx="17" cy="17" r="5.5" fill="#3b9a3b"/><path d="M17 14v6M14 17h6" stroke="#fff" stroke-width="2"/>',
  pdel: '<path d="M5 2h9l5 5v15H5z" fill="#fff" stroke="#555"/><circle cx="17" cy="17" r="5.5" fill="#d33"/><path d="M15 15l4 4M19 15l-4 4" stroke="#fff" stroke-width="2"/>',
  ext: '<path d="M3 4h9l3 3v13H3z" fill="#fff" stroke="#555"/><path d="M9 2h9l3 3v13H9z" fill="#eaf3ff" stroke="#2b6cb0"/><path d="M13 13h8M18 10l3 3-3 3" stroke="#2b6cb0" stroke-width="1.8" fill="none"/>',
  crop: '<path d="M6 2v16h16M2 6h16v16" fill="none" stroke="#2b6cb0" stroke-width="2.4"/>',
  pnum: '<path d="M5 2h14v20H5z" fill="#fff" stroke="#555"/><text x="12" y="19" text-anchor="middle" font-size="8" font-weight="700" fill="#2b6cb0">1..N</text>',
  wm: '<path d="M5 2h14v20H5z" fill="#fff" stroke="#555"/><text x="12" y="15" text-anchor="middle" font-size="9" font-weight="700" fill="#e5262e" opacity=".55" transform="rotate(-35 12 12)">A</text>',
  up: '<path d="M12 4l7 8h-4v8H9v-8H5z" fill="#3b9a3b"/>',
  down: '<path d="M12 20l7-8h-4V4H9v8H5z" fill="#3b9a3b"/>',
  blank: '<path d="M5 2h10l4 4v16H5z" fill="#fff" stroke="#555"/><path d="M15 2v4h4" fill="none" stroke="#555"/>',
  img2pdf: '<rect x="2" y="3" width="12" height="10" fill="#eaf3ff" stroke="#2b6cb0"/><path d="M3 12l4-4 3 3 2-2 2 3" fill="#3b9a3b"/><path d="M11 10h9l2 2v10H11z" fill="#fff" stroke="#c8102e"/><text x="16.5" y="19" text-anchor="middle" font-size="5" font-weight="700" fill="#c8102e">PDF</text>',
  expImg: '<path d="M3 2h10l3 3v11H3z" fill="#fff" stroke="#c8102e"/><text x="9" y="11" text-anchor="middle" font-size="5" font-weight="700" fill="#c8102e">PDF</text><rect x="10" y="11" width="12" height="11" fill="#eaf3ff" stroke="#2b6cb0"/><path d="M11 21l4-4 3 3 2-2 2 3" fill="#3b9a3b"/>',
  gear: '<circle cx="12" cy="12" r="3.5" fill="none" stroke="#555" stroke-width="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" stroke="#555" stroke-width="2.2"/>',
  pundo: '<path d="M5 2h12v20H5z" fill="#fff" stroke="#555"/><path d="M10 9l-3 3 3 3" fill="none" stroke="#2b6cb0" stroke-width="2"/><path d="M7 12h7a3 3 0 0 1 0 6h-2" fill="none" stroke="#2b6cb0" stroke-width="2"/>',
  find2: '<circle cx="10" cy="10" r="6.5" fill="#fff6c8" stroke="#2b6cb0" stroke-width="2"/><path d="M15 15l6 6" stroke="#555" stroke-width="3"/>',
});
//  🎀 리본 — PDF-XChange 와 같은 탭·같은 무리(되는 것만)
//   [모양, 명령, 글, 그림, 도움말, (menu: [[글, 명령], …])]
//   big=큰 단추 · sm=작은 단추(세 개씩 쌓음) · ico=그림만(세 개씩) · menu=▾ 펼침 · 'style'·'zoom'·'nav' = 묶음 칸
const RIB = {
  home: [
    ['도구', [['big', 'hand', '손', 'hand', 'H'], ['big', 'select', '텍스트 선택', 'select', 'V'], ['big', 'tSel', '주석 선택', 'sel', '넣은 도형 고르기·옮기기'],
      ['sm', 'tSnap', '스냅샷', 'snap', '네모를 끌면 그 부분을 그림으로 복사'], ['menu', 'mClip', '클립보드', 'clip', '', [['잘라내기 (Ctrl+X)', 'oCut'], ['복사 (Ctrl+C)', 'oCopy'], ['붙여넣기 (Ctrl+V)', 'oPaste']]],
      ['menu', 'mFind', '찾기', 'find2', '', [['이 문서에서 찾기 (Ctrl+F)', 'find'], ['여러 문서·폴더 검색 (Ctrl+Shift+F)', 'searchPane']]]]],
    ['보기', 'zoom'],
    ['개체', [['big', 'tImg', '이미지', 'tImg', '파일에서 · Ctrl+V 붙여넣기'], ['big', 'tText', '글상자', 'tText', ''], ['big', 'tSel', '선택', 'sel', '']]],
    ['주석', [['sm', 'tType', '타자기', 'type', '테두리 없는 글'], ['sm', 'mhl', '강조 표시', 'hlT', '글자를 끌어 고르면 노란 칠'], ['sm', 'mul', '밑줄', 'ulT', '글자를 끌어 고르면 밑줄'],
      ['sm', 'tNote', '스티커 메모', 'note', ''], ['sm', 'tArrow', '화살표', 'tArrow', ''], ['sm', 'tRect', '사각형', 'tRect', '']]],
    ['', [['stamp']]],
    ['페이지', [['big', 'pRotR', '페이지 회전', 'rr', '고른 페이지를 오른쪽으로(저장됨)'], ['big', 'pDel', '페이지 삭제', 'pdel', '']]],
  ],
  view: [
    ['도구', [['sm', 'hand', '손', 'hand', ''], ['sm', 'select', '텍스트 선택', 'select', '']]],
    ['이동', 'nav'],
    ['확대/축소', [['big', 'actual', '실제 크기', 'actual', 'Ctrl+1'], ['sm', 'page', '페이지에 맞춤', 'page', 'Ctrl+0'], ['sm', 'width', '너비에 맞춤', 'width', 'Ctrl+2'], ['sm', 'zoomIn', '확대', 'zin', 'Ctrl++'], ['sm', 'zoomOut', '축소', 'zout', 'Ctrl+-']]],
    ['', [['menu', 'mVRot', '보기 회전', 'rr', '화면만 돌림(저장 안 됨)', [['오른쪽으로', 'rotR'], ['왼쪽으로', 'rotL']]]]],
    ['페이지 표시', [['big', 'one', '연속', 'one', ''], ['big', 'two', '두 페이지', 'two', '']]],
    ['창', [['sm', 'leftPane', '탐색 창', 'left', 'F4'], ['sm', 'searchPane', '검색 창', 'search', ''], ['sm', 'propsPane', '속성 창', 'props', ''], ['big', 'full', '전체 화면', 'full', 'F11']]],
  ],
  edit: [
    ['도구', [['sm', 'hand', '손', 'hand', ''], ['sm', 'select', '텍스트 선택', 'select', '']]],
    ['', [['big', 'tSel', '주석 선택', 'sel', '옮기기·크기·지우기']]],
    ['텍스트', [['sm', 'tType', '타자기', 'type', ''], ['sm', 'tText', '텍스트 상자', 'tText', '']]],
    ['참고', [['sm', 'tNote', '스티커 메모', 'note', '']]],
    ['텍스트 마크업', [['sm', 'mhl', '강조 표시', 'hlT', '글자를 끌어 고르기'], ['sm', 'mul', '밑줄', 'ulT', ''], ['sm', 'mso', '취소선', 'soT', '']]],
    ['그리기', [['sm', 'tLine', '선', 'tLine', 'Shift: 45°'], ['sm', 'tArrow', '화살표', 'tArrow', ''], ['sm', 'tRect', '사각형', 'tRect', 'Shift: 정사각형'], ['sm', 'tEll', '원', 'tEll', 'Shift: 정원'],
      ['sm', 'tPen', '연필', 'tPen', ''], ['sm', 'tHi', '형광펜', 'tHi', ''], ['sm', 'tWhite', '가리기', 'tWhite', '흰 상자로 덮기'], ['sm', 'tErase', '지우개', 'eraser', '누른 도형 지우기']]],
    ['', [['stamp'], ['symbol'], ['big', 'tImg', '이미지', 'tImg', '']]],
    ['모양', 'style'],
    ['고치기', [['sm', 'undo', '실행 취소', 'undo', 'Ctrl+Z'], ['sm', 'redo', '다시 실행', 'redo', 'Ctrl+Y'], ['sm', 'del', '삭제', 'del', 'Delete'],
      ['sm', 'oRot', '회전', 'rr', 'Ctrl+R (Shift: 왼쪽)'], ['sm', 'oCopy', '복사', 'copy', 'Ctrl+C'], ['sm', 'oCut', '잘라내기', 'cut', 'Ctrl+X'], ['sm', 'oPaste', '붙여넣기', 'paste', 'Ctrl+V'], ['sm', 'dup', '복제', 'dup', 'Ctrl+D']]],
    ['', [['big', 'save', '저장', 'save', 'Ctrl+S']]],
  ],
  org: [
    ['도구', [['sm', 'hand', '손', 'hand', ''], ['sm', 'select', '텍스트 선택', 'select', '']]],
    ['페이지', [['menu', 'mIns', '삽입', 'ins', '', [['파일에서 페이지…', 'pInsFile'], ['빈 페이지', 'pInsBlank'], ['이미지에서…', 'pInsImg']]], ['big', 'pDel', '삭제', 'pdel', 'Delete(페이지 칸에서)'], ['big', 'pExt', '페이지 추출', 'ext', '고른 페이지를 새 PDF 로'],
      ['sm', 'pDup', '페이지 복제', 'dup', ''], ['sm', 'pCopy', '복사', 'copy', '페이지 칸에서 Ctrl+C'], ['sm', 'pCut', '잘라내기', 'cut', '페이지 칸에서 Ctrl+X'], ['sm', 'pPaste', '붙여넣기', 'paste', '고른 페이지 뒤에 · 다른 문서에도'], ['sm', 'pUp', '앞으로', 'up', ''], ['sm', 'pDown', '뒤로', 'down', '']]],
    ['페이지 변환', [['menu', 'mPRot', '회전', 'rr', '', [['오른쪽 90°', 'pRotR'], ['왼쪽 90°', 'pRotL'], ['180°', 'pRot180']]], ['big', 'tCrop', '자르기', 'crop', '남길 부분을 네모로 끌기']]],
    ['페이지 표시', [['big', 'pWm', '워터마크', 'wm', ''], ['big', 'pNum', '페이지 번호', 'pnum', '']]],
    ['', [['big', 'pUndo', '되돌리기', 'pundo', '페이지 바꾼 것 되돌리기']]],
  ],
  conv: [
    ['도구', [['sm', 'hand', '손', 'hand', ''], ['sm', 'select', '텍스트 선택', 'select', '']]],
    ['만들기', [['big', 'newDoc', '공백', 'blank', '빈 A4 문서'], ['big', 'img2pdf', '이미지에서', 'img2pdf', '사진·그림 파일 → PDF']]],
    ['내보내기', [['big', 'expImg', '이미지로 내보내기', 'expImg', 'PNG·JPEG (여러 쪽은 ZIP)'], ['big', 'pExt', '페이지 추출', 'ext', '']]],
  ],
  help: [
    ['도움말', [['big', 'keys', '단축키', 'keys', ''], ['big', 'about', '정보', 'help', ''], ['big', 'settings', '환경 설정', 'gear', '']]],
  ],
  fmt: [
    ['모양', 'style'],
    ['개체', [['sm', 'oRot', '오른쪽 회전', 'rr', 'Ctrl+R'], ['sm', 'oRotL', '왼쪽 회전', 'rl', 'Ctrl+Shift+R'], ['sm', 'dup', '복제', 'dup', 'Ctrl+D'],
      ['sm', 'oCopy', '복사', 'copy', 'Ctrl+C'], ['sm', 'oCut', '잘라내기', 'cut', 'Ctrl+X'], ['sm', 'oPaste', '붙여넣기', 'paste', 'Ctrl+V'], ['sm', 'del', '삭제', 'del', 'Delete']]],
    ['', [['sm', 'undo', '실행 취소', 'undo', 'Ctrl+Z'], ['sm', 'redo', '다시 실행', 'redo', 'Ctrl+Y']]],
  ],
};
let ribTab = 'home';
function ribButton(kind, cmd, label, icon, tip, menu) {
  const b = h('button', { class: kind === 'menu' ? 'sm' : kind, 'data-cmd': menu ? null : cmd, title: label + (tip ? ' — ' + tip : '') });
  b.innerHTML = svg(icon) + (kind === 'ico' ? '' : '<span>' + esc(label) + (menu ? ' ▾' : '') + '</span>');
  if (!menu) return b;
  const pop = h('div', { class: 'rmenu' });
  for (const [t, c] of menu) pop.append(h('button', { text: t, 'data-cmd': c }));
  b.addEventListener('click', (e) => { e.stopPropagation(); const on = pop.classList.contains('on'); $$('.rmenu.on').forEach((p) => p.classList.remove('on')); if (!on) pop.classList.add('on'); });
  b.dataset.menu = cmd;
  return h('div', { class: 'mwrap' }, b, pop);
}
function zoomGroup() {
  const sel = h('select', { class: 'zsel', title: '배율' });
  for (const o of $('#zoomSel').options) sel.append(h('option', { value: o.value, text: o.textContent, ...(o.hidden ? { hidden: '' } : {}) }));
  sel.onchange = () => { const v = sel.value; if (v !== 'custom') setZoom(v === 'width' || v === 'page' ? v : +v); viewer.focus({ preventScroll: true }); };
  const row1 = h('div', { class: 'zrow' }, ribButton('ico', 'zoomOut', '축소', 'zout', 'Ctrl+-'), sel, ribButton('ico', 'zoomIn', '확대', 'zin', 'Ctrl++'));
  const row2 = h('div', { class: 'zrow' }, ...[['actual', '실제 크기', 'actual'], ['page', '페이지에 맞춤', 'page'], ['width', '너비에 맞춤', 'width'], ['rotL', '보기 왼쪽 회전', 'rl'], ['rotR', '보기 오른쪽 회전', 'rr']].map(([c, t, i]) => ribButton('ico', c, t, i, '')));
  const row3 = h('div', { class: 'zrow' }, ...[['leftPane', '탐색 창', 'left'], ['searchPane', '검색 창', 'search'], ['propsPane', '속성 창', 'props'], ['one', '연속', 'one'], ['two', '두 페이지', 'two']].map(([c, t, i]) => ribButton('ico', c, t, i, '')));
  return h('div', { class: 'zgrp' }, row1, row2, row3);
}
function navGroup() {
  const inp = h('input', { class: 'npg', type: 'text', title: '페이지 번호 — Enter' });
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); goPage(parseInt(inp.value, 10) || 1); viewer.focus({ preventScroll: true }); } });
  const row1 = h('div', { class: 'zrow' }, ribButton('ico', 'first', '첫 페이지', 'first', ''), ribButton('ico', 'prev', '이전 페이지', 'prev', ''), inp, ribButton('ico', 'next', '다음 페이지', 'next', ''), ribButton('ico', 'last', '마지막 페이지', 'last', ''));
  return h('div', { class: 'zgrp' }, row1, ribButton('sm', 'back', '이전 보기', 'prev', 'Alt+←'), ribButton('sm', 'fwd', '다음 보기', 'next', 'Alt+→'));
}
function stampButton() {
  const b = h('button', { class: 'big', 'data-cmd': 'tStamp', title: '스탬프 — 누른 자리에 찍기' });
  b.innerHTML = svg('stampI') + '<span>스탬프 ▾</span>';
  const pop = h('div', { class: 'rmenu stamps' });
  for (const s of EDIT.STAMPS) pop.append(h('button', { class: 'stp', text: s === '날짜' ? '날짜 (' + new Date().toLocaleDateString('ko-KR') + ')' : s, onclick: (e) => { e.stopPropagation(); EDIT.style.stamp = s; pop.classList.remove('on'); setTool('stamp'); } }));
  b.querySelector('span').addEventListener('click', (e) => { e.stopPropagation(); pop.classList.toggle('on'); });
  return h('div', { class: 'mwrap' }, b, pop);
}
function renderRibbon() {
  const r = $('#ribbon');
  r.innerHTML = '';
  for (const [cap, items] of RIB[ribTab]) {
    const row = h('div', { class: 'row' });
    const grp = h('div', { class: 'grp' }, row, h('div', { class: 'cap', text: cap }));
    r.append(grp);
    if (items === 'style') { row.append(EDIT.styleGroup(h)); continue; }
    if (items === 'zoom') { row.append(zoomGroup()); continue; }
    if (items === 'nav') { row.append(navGroup()); continue; }
    let stack = null;
    for (const it of items) {
      const [kind] = it;
      if (kind === 'symbol') { stack = null; row.append(symButton()); continue; }
      if (kind === 'stamp') { stack = null; row.append(stampButton()); continue; }
      const b = ribButton(...it);
      if (kind === 'sm' || kind === 'ico' || kind === 'menu') {
        if (!stack || stack.children.length >= 3) { stack = h('div', { class: 'stack' + (kind === 'ico' ? ' icos' : '') }); row.append(stack); }
        stack.append(b);
      } else { stack = null; row.append(b); }
    }
  }
  updateUi();
}
//  기호 단추 — 누르면 그 기호로 찍기, ▾ 로 고르기
function symButton() {
  const b = h('button', { class: 'big symb', 'data-cmd': 'tSym', title: '기호 — 누른 자리에 찍기(끌면 크기)' });
  b.innerHTML = '<b class="symg"></b><span>기호 ▾</span>';
  const pop = h('div', { class: 'sympop' });
  for (const s of EDIT.SYMBOLS) pop.append(h('button', { text: s, onclick: (e) => { e.stopPropagation(); EDIT.style.sym = s; pop.classList.remove('on'); syncSymButton(); setTool('sym'); } }));
  b.querySelector('span').addEventListener('click', (e) => { e.stopPropagation(); pop.classList.toggle('on'); });
  const wrap = h('div', { class: 'symwrap' }, b, pop);
  setTimeout(syncSymButton, 0);
  return wrap;
}
function syncSymButton() { const g = $('.symg'); if (g) g.textContent = EDIT.style.sym; }
document.addEventListener('click', (e) => {
  if (!e.target.closest('.symwrap')) $$('.sympop.on').forEach((p) => p.classList.remove('on'));
  if (!e.target.closest('.mwrap') || e.target.closest('.rmenu button')) $$('.rmenu.on').forEach((p) => p.classList.remove('on'));
});
function selectTab(name) {
  ribTab = name;
  $$('#tabs .rt').forEach((x) => x.classList.toggle('on', x.dataset.rt === name));
  $('#ribbon').classList.remove('mini');
  renderRibbon();
}
$$('#tabs .rt').forEach((b) => b.onclick = () => {
  if (b.dataset.rt === 'file') { openBackstage(); return; }
  selectTab(b.dataset.rt);
});
//  「형식」(노란 탭) — 주석 도구를 쓰는 동안만 보인다(PDF-XChange 의 그 탭)
function syncFmtTab() {
  const on = EDIT.EDIT_TOOLS.includes(tool) && !!cur;
  $('#fmtTab').style.display = on ? '' : 'none';
  $('#fmtTool').textContent = TOOL_NAMES[tool] || '도구';
  if (!on && ribTab === 'fmt') selectTab('edit');
}
const TOOL_NAMES = { edit: '주석 선택', rect: '사각형', ellipse: '원', line: '선', arrow: '화살표', pen: '연필', hilite: '형광펜', white: '가리기', text: '텍스트 상자', type: '타자기', under: '밑줄', sym: '기호', stamp: '스탬프', note: '스티커 메모', snap: '스냅샷', crop: '자르기', erase: '지우개', mhl: '강조 표시', mul: '밑줄', mso: '취소선' };


async function setTool(t) {
  if (EDIT.EDIT_TOOLS.includes(t)) {
    if (!cur) { toast('먼저 PDF 를 여세요'); return; }
    if (!(await EDIT.ensureLoaded(cur))) t = 'hand';
  }
  tool = t;
  viewer.classList.toggle('hand', t === 'hand');
  const mark = !!EDIT.MARK_TOOLS[t];
  viewer.classList.toggle('editing', EDIT.EDIT_TOOLS.includes(t) && !mark);
  viewer.classList.toggle('creating', EDIT.EDIT_TOOLS.includes(t) && !mark && t !== 'edit' && t !== 'erase');
  viewer.classList.toggle('erasing', t === 'erase');
  viewer.classList.toggle('marking', mark);
  if (mark) toast('글자를 끌어 고르면 ' + TOOL_NAMES[t] + '이(가) 됩니다');
  if (t === 'snap') toast('그림으로 복사할 부분을 네모로 끄세요');
  if (t === 'crop') toast('남길 부분을 네모로 끄세요');
  if (t !== 'edit' && !EDIT.EDIT_TOOLS.includes(t)) EDIT.select(null);
  for (const d of docs) EDIT.redrawAll(d);
  syncFmtTab();
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
  open: openDialog,
  save: () => saveDoc(false), saveAs: () => saveDoc(true), print: printDoc,
  tSel: () => setTool('edit'), tRect: () => setTool('rect'), tEll: () => setTool('ellipse'), tLine: () => setTool('line'), tArrow: () => setTool('arrow'),
  tPen: () => setTool('pen'), tHi: () => setTool('hilite'), tText: () => setTool('text'), tSym: () => setTool('sym'), tWhite: () => setTool('white'),
  tImg: async () => { if (!cur) return toast('먼저 PDF 를 여세요'); if (await EDIT.ensureLoaded(cur)) $('#fImg').click(); },
  undo: () => EDIT.undo(false), redo: () => EDIT.undo(true), del: () => EDIT.delSel(), dup: () => EDIT.dupSel(),
  tType: () => setTool('type'), tNote: () => setTool('note'), tStamp: () => setTool('stamp'), tSnap: () => setTool('snap'), tCrop: () => setTool('crop'), tErase: () => setTool('erase'),
  mhl: () => setTool('mhl'), mul: () => setTool('mul'), mso: () => setTool('mso'),
  oRot: () => EDIT.rotateSel(1), oRotL: () => EDIT.rotateSel(-1),
  oCopy: () => { if (!EDIT.copySel(false)) { const t = String(getSelection() || ''); if (t) { navigator.clipboard && navigator.clipboard.writeText(t); toast('글자를 복사했습니다'); } else toast('복사할 도형(주석 선택)이나 글자를 먼저 고르세요'); } },
  oCut: () => { if (!EDIT.copySel(true)) toast('잘라낼 도형을 먼저 고르세요(주석 선택)'); },
  oPaste: async () => { if (!(await EDIT.pasteClip())) toast('붙여 넣을 도형이 없습니다 — 그림은 Ctrl+V'); },
  pRotR: () => rotPages(90), pRotL: () => rotPages(-90), pRot180: () => rotPages(180), pDel: delPages, pExt: extractPages, pDup: dupPages,
  pCopy: () => copyPages(false), pCut: () => copyPages(true), pPaste: pastePages, pUp: () => movePages(-1), pDown: () => movePages(1),
  pInsFile: insertFromFile, pInsBlank: insertBlank, pInsImg: insertImages, pNum: pageNumbers, pWm: watermark, pUndo: pageUndo,
  newDoc: newBlank, img2pdf, expImg: exportImages, settings: () => settings(),
  exportHtml: () => HOST && HOST.exportHtml && HOST.exportHtml(),
  exit: () => { if (HOST && HOST.exit) HOST.exit(); else window.close(); },
  closeAll: async () => { for (const d of [...docs]) await closeDoc(d); },
  close: () => closeDoc(cur),
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
    ['Ctrl+O', '열기'], ['Ctrl+S', '저장'], ['Ctrl+P', '인쇄'], ['Ctrl+W', '문서 닫기'], ['Ctrl+Tab', '다음 문서'],
    ['Ctrl+F', '이 문서에서 찾기 (Enter 다음 · Shift+Enter 이전)'], ['Ctrl+Shift+F', '여러 문서·폴더에서 검색'],
    ['Ctrl + 바퀴 · Ctrl++ / Ctrl+-', '확대 / 축소'], ['Ctrl+0 · 1 · 2', '페이지 맞춤 · 실제 크기 · 너비 맞춤'],
    ['← → · PageUp/Down · Home/End', '페이지 넘기기'], ['Alt+← / Alt+→', '이전 보기 / 다음 보기'],
    ['H · V', '손 도구 · 텍스트 선택'], ['F4', '탐색 창'], ['Ctrl+Shift++ / -', '오른쪽·왼쪽으로 돌리기'],
    ['Ctrl+Shift+S', '다른 이름으로 저장'], ['Ctrl+Z · Ctrl+Y', '고친 것 되돌리기 · 다시'], ['Delete · Ctrl+D', '고른 도형 지우기 · 복제'],
    ['Ctrl+C · Ctrl+V', '도형 복사·붙여 넣기 · 캡처한 그림 붙여 넣기'], ['← ↑ → ↓ (Shift)', '고른 도형 1pt(10pt)씩 옮기기'], ['Enter · 두 번 누르기', '글상자 글 고치기'],
  ].map(([k, v]) => '<tr><td style="padding:2px 12px 2px 0;white-space:nowrap"><kbd>' + k.split(' · ').join('</kbd> · <kbd>') + '</kbd></td><td>' + v + '</td></tr>').join('') + '</table>';
  const ver = (document.querySelector('meta[name=hanil-pdf]') || {}).content || '';
  const head = keysOnly ? '' : '<div style="display:flex;gap:12px;align-items:center"><div class="logo" style="width:42px;height:42px;font-size:14px;border-radius:6px">PDF</div><div><b style="font-size:16px">한일 PDF 리더</b> ' + esc(ver) + '<br>제작사: <b>' + MAKER + '</b></div></div>'
    + '<p style="margin:10px 0 4px">PDF 보기 · 여러 문서·폴더에서 찾기 · 도형·글·기호·이미지 넣어 고치기(표준 주석이라 Acrobat·PDF-XChange 에서도 보이고 고쳐짐).<br>파일은 이 PC 밖으로 나가지 않습니다.</p>'
    + '<small style="color:#888">© ' + MAKER + ' · 엔진: pdf.js (Mozilla, Apache-2.0) · pdf-lib (MIT)</small><hr style="border:0;border-top:1px solid #ddd">';
  ask(keysOnly ? '단축키' : '정보', head + keys, { cancel: null });
}

const TOOL_OF = { tSel: 'edit', tRect: 'rect', tEll: 'ellipse', tLine: 'line', tArrow: 'arrow', tPen: 'pen', tHi: 'hilite', tText: 'text', tSym: 'sym', tWhite: 'white',
  tType: 'type', tNote: 'note', tStamp: 'stamp', tSnap: 'snap', tCrop: 'crop', tErase: 'erase', mhl: 'mhl', mul: 'mul', mso: 'mso' };
const NEED_DOC = ['save', 'saveAs', 'print', 'close', 'closeAll', 'props', 'actual', 'width', 'page', 'zoomIn', 'zoomOut', 'first', 'prev', 'next', 'last', 'rotL', 'rotR',
  'undo', 'redo', 'del', 'dup', 'oRot', 'oRotL', 'oCopy', 'oCut', 'oPaste', 'tImg', 'pRotR', 'pRotL', 'pRot180', 'pDel', 'pExt', 'pDup', 'pCopy', 'pCut', 'pPaste', 'pUp', 'pDown',
  'pInsFile', 'pInsBlank', 'pInsImg', 'pNum', 'pWm', 'pUndo', 'expImg'];
function updateUi() {
  const has = !!cur;
  $$('[data-cmd]').forEach((b) => {
    const c = b.dataset.cmd;

    if (c === 'back') b.disabled = !has || !cur.hist.length;
    if (c === 'fwd') b.disabled = !has || !cur.fwd.length;
    if (c === 'hand' || c === 'select') b.classList.toggle('on', tool === c);
    if (TOOL_OF[c]) b.classList.toggle('on', tool === TOOL_OF[c]);
    if (NEED_DOC.includes(c) || TOOL_OF[c]) b.disabled = !has;
    if (c === 'one' || c === 'two') b.classList.toggle('on', twoPage === (c === 'two'));
    if (c === 'width' || c === 'page') b.classList.toggle('on', has && cur.fit === c);
    if (c === 'leftPane') b.classList.toggle('on', !$('#left').classList.contains('off'));
    if (c === 'searchPane') b.classList.toggle('on', !$('#right').classList.contains('off') && !$('#pSearch').classList.contains('off'));
    if (c === 'propsPane') b.classList.toggle('on', !$('#right').classList.contains('off') && !$('#pProps').classList.contains('off'));
  });
  $('#pgIn').disabled = !has;
  $$('.zsel').forEach((zs) => { zs.disabled = !has; if (has) { zs.value = $('#zoomSel').value; const c = zs.querySelector('[value=custom]'); if (c) c.textContent = Math.round(cur.zoom * 100) + '%'; } });
  $$('.mwrap > button').forEach((b) => { if (['mClip', 'mVRot', 'mIns', 'mPRot'].includes(b.dataset.menu)) b.disabled = !has; });
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
  $$('.npg').forEach((x) => { if (document.activeElement !== x) x.value = d ? d.cur + ' / ' + d.n : ''; x.disabled = !d; });
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
  if (!/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName) && EDIT.onKey(e)) return;
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 's' || e.key === 'S')) { e.preventDefault(); return CMD.saveAs(); }
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
  if (k === 'Escape' && EDIT.EDIT_TOOLS.includes(tool) && !inInput) { e.preventDefault(); return setTool(tool === 'edit' ? 'hand' : 'edit'); }
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
window.addEventListener('drop', async (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault(); dragDepth = 0;
  $('#emptyMsg').classList.remove('drag'); if (cur) $('#emptyMsg').style.display = 'none';
  const files = [...e.dataTransfer.files];
  //  크롬: 끌어다 놓은 파일도 「그 파일에 바로 저장」할 수 있게 손잡이(handle)를 받아 둔다
  const hs = [...e.dataTransfer.items].filter((it) => it.kind === 'file').map((it) => (it.getAsFileSystemHandle ? it.getAsFileSystemHandle().catch(() => null) : null));
  const handles = await Promise.all(hs);
  const imgs = files.filter((f) => f.type.startsWith('image/'));
  if (imgs.length && cur) {
    //  그림을 페이지 위에 놓으면 그 자리에 넣기
    const pg = e.target.closest && e.target.closest('.pg');
    let at = null;
    if (pg) { const i = +pg.dataset.i, p = cur.pages[i], r = pg.getBoundingClientRect(), s = scaleOf(cur); at = { i, x: (e.clientX - r.left) / s, y: (e.clientY - r.top) / s }; if (cur.rot) at = null; }
    for (const f of imgs) await EDIT.addImage(cur, f, at);
  }
  let last = null;
  for (let k = 0; k < files.length; k++) if (isPdf(files[k])) last = (await openFile(files[k], { handle: handles[k] && handles[k].kind === 'file' ? handles[k] : null })) || last;
  if (last) activate(last);
  else if (!imgs.length && files.length) toast('PDF 파일이 아닙니다');
});
$('#fOpen').addEventListener('change', (e) => { const f = [...e.target.files]; e.target.value = ''; openFiles(f); });
$('#fImg').addEventListener('change', async (e) => { const f = [...e.target.files]; e.target.value = ''; for (const x of f) if (cur) await EDIT.addImage(cur, x); });
document.addEventListener('paste', (e) => EDIT.onPaste(e));
//  ⚠ 고치고 저장 안 한 채 창을 닫으려 하면 묻는다
window.addEventListener('beforeunload', (e) => { if (docs.some((d) => d.mod)) { e.preventDefault(); e.returnValue = ''; } });

//  열기 — 크롬(https·file·확장)은 파일 손잡이를 받아 「저장」이 그 파일에 바로 쓴다
async function openDialog() {
  if (HOST && HOST.open) return HOST.open();
  if (window.showOpenFilePicker) {
    let hs;
    try { hs = await window.showOpenFilePicker({ multiple: true, types: [{ description: 'PDF 문서', accept: { 'application/pdf': ['.pdf'] } }] }); }
    catch (e) { if (e && e.name === 'AbortError') return; $('#fOpen').click(); return; }
    let last = null;
    for (const hd of hs) last = (await openFile(await hd.getFile(), { handle: hd })) || last;
    if (last) activate(last);
    return;
  }
  $('#fOpen').click();
}
//  주소로 열기 — ?src=<주소>&name=<이름> (크롬 확장이 PDF 주소를 넘김 · 윈도우 프로그램이 파일을 넘김)
async function openUrl0(src, name, path = null) {
  try {
    const r = await fetch(src, { credentials: 'include' });
    if (!r.ok) throw new Error('받지 못함 (' + r.status + ')');
    const b = await r.blob();
    name = name || decodeURIComponent((new URL(src, location.href).pathname.split('/').pop() || 'document.pdf'));
    if (!/\.pdf$/i.test(name)) name += '.pdf';
    const d = await openFile(new File([b], name, { type: 'application/pdf' }), { path: path || src });
    if (d) activate(d);
    return d;
  } catch (e) { ask('열 수 없음', esc(src) + '<br>' + esc(e.message || e), { cancel: null }); }
}
function visibleCenter(d, i) {
  const p = d.pages[i], vr = viewer.getBoundingClientRect(), r = p.div.getBoundingClientRect(), s = scaleOf(d);
  const cx = (Math.max(r.left, vr.left) + Math.min(r.right, vr.right)) / 2 - r.left;
  const cy = (Math.max(r.top, vr.top) + Math.min(r.bottom, vr.bottom)) / 2 - r.top;
  if (d.rot) return [p.w / 2, p.h / 2];
  return [Math.max(0, Math.min(p.w, cx / s)), Math.max(0, Math.min(p.h, cy / s))];
}

// ───────────────────────── 구성: 페이지 바꾸기(저장됨) ─────────────────────────
//  고친 도형까지 넣은 PDF 를 만들어 → pdf-lib 로 페이지를 바꾸고 → 그것을 새 원본으로 다시 연다.
//  되돌리기는 바꾸기 전 바이트를 10번까지 기억한다.
let pageClip = null;                  //  { bytes, idx:[…], name }
const targets = (d) => (d.psel && d.psel.size ? [...d.psel].sort((a, b) => a - b) : [d.cur - 1]);
async function pageOp(d, label, fn) {
  if (!d) return toast('먼저 PDF 를 여세요');
  const info = await d.pdf.getMetadata().then((m) => m.info || {}, () => ({}));
  if (info.EncryptFilterName) return ask('바꿀 수 없음', '암호(보안)가 걸린 PDF 는 페이지를 바꿀 수 없습니다.', { cancel: null });
  toast(label + ' 중…', 60000);
  let before, doc, r;
  try {
    before = await EDIT.buildPdf(d);
    doc = await PDFDocument.load(before.slice(0), { updateMetadata: false });
    r = await fn(doc);
    if (r === false) { toast('그만두었습니다'); return; }
    doc.setProducer('한일 PDF 리더 · ' + MAKER);
    const out = await doc.save({ useObjectStreams: false });
    (d.pundo || (d.pundo = [])).push(before);
    if (d.pundo.length > 10) d.pundo.shift();
    await reloadDoc(d, out, r && r.page);
    toast(label + ' — 끝 (저장해야 파일에 남습니다)');
  } catch (e) { console.error(e); ask(label, '하지 못했습니다.<br><small>' + esc(String(e.message || e)) + '</small>', { cancel: null }); }
}
async function buildPages(d) {
  const p1 = await d.pdf.getPage(1);
  const v1 = p1.getViewport({ scale: 1 });
  d.pages = [];
  d.el.textContent = '';
  for (let i = 0; i < d.n; i++) {
    const div = h('div', { class: 'pg', 'data-i': i });
    div.append(h('div', { class: 'ldg', text: (i + 1) + '' }));
    d.el.append(div);
    d.pages.push({ w: v1.width, h: v1.height, rot0: p1.rotate, div, key: null });
  }
  sizeRest(d);
}
async function reloadDoc(d, bytes, page = null) {
  const wasEd = d.ed && d.ed.loaded;
  const keep = page || d.cur;
  for (const p of d.pages) unrender(p);
  pumpGen++; queue = [];
  try { d.pdf.destroy(); } catch {}
  d.base = bytes.slice();
  d.ed = null; d.texts = []; d.find = null; d.psel = new Set();
  const task = loadPdf(bytes, d.name);
  d.pdf = await task.promise;
  EDIT.attachDoc(d);
  d.n = d.pdf.numPages;
  await buildPages(d);
  d.laid = false; d.mod = true;
  if (wasEd) await EDIT.ensureLoaded(d);
  if (cur === d) { cur = null; activate(d); } else renderTabs();
  goPage(Math.min(d.n, keep), { hist: false });
}
const pdfPage = (doc, i) => doc.getPage(i);
const rotPages = (by) => pageOp(cur, '페이지 회전', (doc) => { for (const i of targets(cur)) { const p = pdfPage(doc, i); p.setRotation(degrees(((p.getRotation().angle + by) % 360 + 360) % 360)); } });
async function delPages() {
  const d = cur; if (!d) return;
  const idx = targets(d);
  if (idx.length >= d.n) return ask('페이지 삭제', '모든 페이지를 지울 수는 없습니다.', { cancel: null });
  if (!(await ask('페이지 삭제', idx.length + '쪽(' + idx.map((i) => i + 1).join(', ') + ')을 지울까요?', { ok: '삭제' }))) return;
  return pageOp(d, '페이지 삭제', (doc) => { for (const i of [...idx].reverse()) doc.removePage(i); return { page: idx[0] + 1 }; });
}
async function copyPages(cut) {
  const d = cur; if (!d) return;
  const idx = targets(d);
  pageClip = { bytes: await EDIT.buildPdf(d), idx, name: d.name };
  if (cut) {
    if (idx.length >= d.n) return toast('모든 페이지를 잘라낼 수는 없습니다 — 복사했습니다');
    await pageOp(d, '페이지 잘라내기', (doc) => { for (const i of [...idx].reverse()) doc.removePage(i); return { page: idx[0] + 1 }; });
  } else toast(idx.length + '쪽 복사 — 붙여 넣을 페이지를 고르고 Ctrl+V (다른 문서에도 됨)');
}
function pastePages() {
  const d = cur; if (!d) return;
  if (!pageClip) return toast('복사한 페이지가 없습니다');
  const at = targets(d).slice(-1)[0] + 1;
  return pageOp(d, '페이지 붙여넣기', async (doc) => {
    const src = await PDFDocument.load(pageClip.bytes.slice(0), { updateMetadata: false });
    const cp = await doc.copyPages(src, pageClip.idx);
    cp.forEach((p, k) => doc.insertPage(at + k, p));
    return { page: at + 1 };
  });
}
function dupPages() {
  const d = cur; if (!d) return;
  const idx = targets(d), at = idx[idx.length - 1] + 1;
  return pageOp(d, '페이지 복제', async (doc) => { const cp = await doc.copyPages(doc, idx); cp.forEach((p, k) => doc.insertPage(at + k, p)); return { page: at + 1 }; });
}
function movePages(dir) {
  const d = cur; if (!d) return;
  const idx = targets(d);
  if ((dir < 0 && idx[0] === 0) || (dir > 0 && idx[idx.length - 1] === d.n - 1)) return toast('더 옮길 수 없습니다');
  return pageOp(d, '페이지 옮기기', (doc) => {
    const pages = idx.map((i) => doc.getPage(i));
    for (const i of [...idx].reverse()) doc.removePage(i);
    const at = idx[0] + dir;
    pages.forEach((p, k) => doc.insertPage(at + k, p));
    d.psel = new Set(idx.map((i) => i + dir));
    return { page: at + 1 };
  }).then(() => { d.psel = new Set(idx.map((i) => i + dir)); markThumb(); });
}
function insertBlank() {
  const d = cur; if (!d) return;
  const at = targets(d).slice(-1)[0] + 1, p = d.pages[at - 1];
  return pageOp(d, '빈 페이지 넣기', (doc) => { doc.insertPage(at, [p.rot0 % 180 ? p.h : p.w, p.rot0 % 180 ? p.w : p.h]); return { page: at + 1 }; });
}
async function pickFiles(accept, multiple = true) {
  return new Promise((res) => {
    const i = h('input', { type: 'file', accept, ...(multiple ? { multiple: '' } : {}) });
    i.style.display = 'none';
    i.onchange = () => { res([...i.files]); i.remove(); };
    document.body.append(i);
    i.click();
  });
}
async function insertFromFile() {
  const d = cur; if (!d) return;
  const fs = (await pickFiles('.pdf,application/pdf')).filter(isPdf);
  if (!fs.length) return;
  const at = targets(d).slice(-1)[0] + 1;
  return pageOp(d, '파일에서 페이지 넣기', async (doc) => {
    let k = 0;
    for (const f of fs) {
      const src = await PDFDocument.load(new Uint8Array(await f.arrayBuffer()), { updateMetadata: false });
      const cp = await doc.copyPages(src, src.getPageIndices());
      for (const p of cp) doc.insertPage(at + k++, p);
    }
    return { page: at + 1 };
  });
}
//  그림 파일 → PDF 페이지(그림 크기대로, 96dpi) — JPEG·PNG 는 그대로, 나머지는 PNG 로
async function embedImageFile(doc, f) {
  let bytes = new Uint8Array(await f.arrayBuffer()), type = f.type;
  if (type !== 'image/jpeg' && type !== 'image/png') {
    const bmp = await createImageBitmap(f);
    const cv = h('canvas', { width: bmp.width, height: bmp.height }); cv.getContext('2d').drawImage(bmp, 0, 0);
    bytes = new Uint8Array(await (await new Promise((r) => cv.toBlob(r, 'image/png'))).arrayBuffer()); type = 'image/png';
  }
  return type === 'image/jpeg' ? doc.embedJpg(bytes) : doc.embedPng(bytes);
}
async function imagesToPages(doc, files, at) {
  let k = 0;
  for (const f of files) {
    const im = await embedImageFile(doc, f);
    let w = im.width * 0.75, hh = im.height * 0.75;
    const sc = Math.min(1, 1190 / Math.max(w, hh));
    w *= sc; hh *= sc;
    const p = at == null ? doc.addPage([w, hh]) : doc.insertPage(at + k++, [w, hh]);
    p.drawImage(im, { x: 0, y: 0, width: w, height: hh });
  }
}
async function insertImages() {
  const d = cur; if (!d) return;
  const fs = (await pickFiles('image/*')).filter((f) => f.type.startsWith('image/'));
  if (!fs.length) return;
  const at = targets(d).slice(-1)[0] + 1;
  return pageOp(d, '이미지 페이지 넣기', async (doc) => { await imagesToPages(doc, fs, at); return { page: at + 1 }; });
}
async function extractPages() {
  const d = cur; if (!d) return;
  const idx = targets(d);
  const src = await PDFDocument.load((await EDIT.buildPdf(d)).slice(0), { updateMetadata: false });
  const out = await PDFDocument.create();
  for (const p of await out.copyPages(src, idx)) out.addPage(p);
  out.setProducer('한일 PDF 리더 · ' + MAKER);
  const name = d.name.replace(/\.pdf$/i, '') + ' (' + (idx.length === 1 ? idx[0] + 1 + '쪽' : idx[0] + 1 + '-' + (idx[idx.length - 1] + 1) + '쪽') + ').pdf';
  await openNew(await out.save(), name);
}
async function openNew(bytes, name) {
  const f = new File([bytes], name, { type: 'application/pdf' });
  const d = await openFile(f, { path: 'new:' + Date.now() + ':' + name });
  if (d) { d.mod = true; d.isNew = true; activate(d); }
  return d;
}
async function newBlank() {
  const doc = await PDFDocument.create();
  doc.addPage([595.28, 841.89]);
  doc.setProducer('한일 PDF 리더 · ' + MAKER);
  await openNew(await doc.save(), '새 문서.pdf');
}
async function img2pdf() {
  const fs = (await pickFiles('image/*')).filter((f) => f.type.startsWith('image/'));
  if (!fs.length) return;
  toast('PDF 만드는 중…', 60000);
  const doc = await PDFDocument.create();
  doc.setProducer('한일 PDF 리더 · ' + MAKER);
  await imagesToPages(doc, fs.sort((a, b) => collator.compare(a.name, b.name)), null);
  await openNew(await doc.save(), (fs.length === 1 ? fs[0].name.replace(/\.[^.]+$/, '') : '이미지 ' + fs.length + '장') + '.pdf');
}
//  자르기(크롭) — 끈 네모만 남긴다(CropBox). 다른 프로그램에서도 잘린 대로 보인다.
async function cropBox(d, i, [x, y, w, hh]) {
  const r = await ask('자르기', '고른 네모만 남기고 바깥을 잘라냅니다.', { ok: '이 페이지만', extra: '모든 페이지', cancel: '취소' });
  if (r === null || r === '__closed') return;
  const vp = (await d.pdf.getPage(i + 1)).getViewport({ scale: 1 });
  const a = vp.convertToPdfPoint(x, y), b = vp.convertToPdfPoint(x + w, y + hh);
  const box = [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])];
  setTool('hand');
  await pageOp(d, '자르기', (doc) => { for (const k of r === 'extra' ? doc.getPageIndices() : [i]) doc.getPage(k).setCropBox(...box); return { page: i + 1 }; });
}
//  페이지 번호 「n / N」 — 보이는 아래 가운데(돌아간 페이지도 바로 서게)
async function pageNumbers() {
  const d = cur; if (!d) return;
  const fmt = await ask('페이지 번호', '형식을 고르세요. <b>{n}</b> = 쪽, <b>{N}</b> = 모든 쪽', { input: 'text', value: '{n} / {N}', ok: '넣기' });
  if (!fmt) return;
  return pageOp(d, '페이지 번호', async (doc) => {
    const font = await doc.embedFont(StandardFonts.Helvetica);
    const n = doc.getPageCount();
    for (let i = 0; i < n; i++) {
      const p = doc.getPage(i), vp = (await d.pdf.getPage(i + 1)).getViewport({ scale: 1 });
      const t = fmt.replace(/\{n\}/g, i + 1).replace(/\{N\}/g, n).replace(/[^\x20-\x7e]/g, '');
      const size = 10, tw = font.widthOfTextAtSize(t, size);
      const [cx, cy] = vp.convertToPdfPoint(vp.width / 2, vp.height - 22);
      const rot = p.getRotation().angle * Math.PI / 180;
      p.drawText(t, { x: cx - Math.cos(rot) * tw / 2, y: cy - Math.sin(rot) * tw / 2, size, font, color: pdfRgb(0.2, 0.2, 0.2), rotate: degrees(p.getRotation().angle) });
    }
  });
}
//  워터마크 — 글(한글 됨)을 그림으로 만들어 페이지 가운데에 비스듬히, 옅게
async function watermark() {
  const d = cur; if (!d) return;
  const txt = await ask('워터마크', '넣을 글(예: 대외비, 한일특장(주))', { input: 'text', value: '대외비', ok: '넣기' });
  if (!txt) return;
  const cv = h('canvas'); const c = cv.getContext('2d');
  c.font = '700 120px "Malgun Gothic","맑은 고딕",sans-serif';
  const tw = Math.ceil(c.measureText(txt).width) + 20;
  cv.width = tw; cv.height = 160;
  c.font = '700 120px "Malgun Gothic","맑은 고딕",sans-serif'; c.fillStyle = '#c8102e'; c.textBaseline = 'middle';
  c.fillText(txt, 10, 82);
  const png = new Uint8Array(await (await new Promise((r) => cv.toBlob(r, 'image/png'))).arrayBuffer());
  return pageOp(d, '워터마크', async (doc) => {
    const im = await doc.embedPng(png);
    for (let i = 0; i < doc.getPageCount(); i++) {
      const p = doc.getPage(i), vp = (await d.pdf.getPage(i + 1)).getViewport({ scale: 1 });
      const W = Math.min(vp.width, vp.height) * 0.8, H = W * im.height / im.width;
      const [cx, cy] = vp.convertToPdfPoint(vp.width / 2, vp.height / 2);
      const a = (p.getRotation().angle + 35) * Math.PI / 180;
      p.drawImage(im, { x: cx - (Math.cos(a) * W - Math.sin(a) * H) / 2, y: cy - (Math.sin(a) * W + Math.cos(a) * H) / 2, width: W, height: H, rotate: degrees(p.getRotation().angle + 35), opacity: 0.16 });
    }
  });
}
async function pageUndo() {
  const d = cur; if (!d || !d.pundo || !d.pundo.length) return toast('되돌릴 페이지 작업이 없습니다');
  await reloadDoc(d, d.pundo.pop());
  toast('되돌렸습니다');
}

// ───────────────────────── 스냅샷 · 이미지로 내보내기 ─────────────────────────
async function renderWithEdits(d, i, k) {
  const pg = await d.pdf.getPage(i + 1);
  const vp = pg.getViewport({ scale: k });
  const cv = h('canvas', { width: Math.floor(vp.width), height: Math.floor(vp.height) });
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await pg.render({ canvasContext: ctx, viewport: vp }).promise;
  EDIT.paintCanvas(ctx, d, i, [k, 0, 0, k, 0, 0]);
  return cv;
}
async function snapshot(d, i, [x, y, w, hh]) {
  const k = (SET.snapDpi || 200) / 72;
  const full = await renderWithEdits(d, i, k);
  const cv = h('canvas', { width: Math.round(w * k), height: Math.round(hh * k) });
  cv.getContext('2d').drawImage(full, -x * k, -y * k);
  const blob = await new Promise((r) => cv.toBlob(r, 'image/png'));
  EDIT.setClipImage(blob);
  try {
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
    toast('📷 클립보드에 복사했습니다 — 한글·엑셀·메신저에 Ctrl+V');
  } catch {
    toast('📷 이 창 안에서는 Ctrl+V 로 붙여 넣을 수 있습니다(클립보드 허용이 안 돼 파일로도 받습니다)');
    download(blob, d.name.replace(/\.pdf$/i, '') + ' 스냅샷.png');
  }
}
//  ZIP(압축 없이 묶기) — 이미지 여러 장을 한 번에 받게
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = (u) => { let c = 0xffffffff; for (let i = 0; i < u.length; i++) c = CRC[(c ^ u[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function zip(files) {
  const enc = new TextEncoder(), parts = [], cen = [];
  let off = 0;
  for (const { name, data } of files) {
    const nb = enc.encode(name), crc = crc32(data);
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint32(14, crc, true);
    lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, nb.length, true);
    parts.push(new Uint8Array(lh.buffer), nb, data);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint32(16, crc, true);
    ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, nb.length, true); ch.setUint32(42, off, true);
    cen.push(new Uint8Array(ch.buffer), nb);
    off += 30 + nb.length + data.length;
  }
  const cl = cen.reduce((a, b) => a + b.length, 0);
  const e = new DataView(new ArrayBuffer(22));
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, cl, true); e.setUint32(16, off, true);
  return new Blob([...parts, ...cen, new Uint8Array(e.buffer)], { type: 'application/zip' });
}
async function exportImages() {
  const d = cur; if (!d) return toast('먼저 PDF 를 여세요');
  const sel = d.psel && d.psel.size ? targets(d) : null;
  const html = '<label style="display:block;margin:4px 0"><input type="radio" name="xr" value="cur" checked> 지금 페이지 (' + d.cur + '쪽)</label>'
    + (sel ? '<label style="display:block;margin:4px 0"><input type="radio" name="xr" value="sel"> 고른 페이지 ' + sel.length + '쪽</label>' : '')
    + '<label style="display:block;margin:4px 0"><input type="radio" name="xr" value="all"> 모든 페이지 (' + d.n + '쪽 · ZIP)</label>'
    + '<div style="margin-top:8px">형식 <select id="xf"><option value="png">PNG</option><option value="jpeg">JPEG</option></select> &nbsp; 해상도 <select id="xd"><option>96</option><option selected>150</option><option>200</option><option>300</option></select> dpi</div>';
  const pend = ask('이미지로 내보내기', html, { ok: '내보내기' });
  let opt = null;
  const grab = () => { const r = $('input[name=xr]:checked'); opt = { range: r && r.value, fmt: $('#xf').value, dpi: +$('#xd').value }; };
  $('#mFoot button').addEventListener('click', grab, { capture: true });
  if (!(await pend) || !opt) return;
  const idx = opt.range === 'all' ? [...Array(d.n).keys()] : opt.range === 'sel' ? sel : [d.cur - 1];
  const base = d.name.replace(/\.pdf$/i, ''), ext = opt.fmt === 'png' ? 'png' : 'jpg', out = [];
  for (const i of idx) {
    toast('그리는 중… ' + (out.length + 1) + ' / ' + idx.length, 60000);
    const cv = await renderWithEdits(d, i, opt.dpi / 72);
    const b = await new Promise((r) => cv.toBlob(r, 'image/' + opt.fmt, 0.92));
    out.push({ name: base + '-' + String(i + 1).padStart(String(d.n).length, '0') + '.' + ext, data: new Uint8Array(await b.arrayBuffer()), blob: b });
  }
  if (out.length === 1) download(out[0].blob, out[0].name); else download(zip(out), base + ' 이미지.zip');
  toast('내보냈습니다 — ' + out.length + '장');
}

// ───────────────────────── 페이지 그림 칸: 여러 장 고르기 ─────────────────────────
function thumbClick(d, i, e) {
  d.psel = d.psel || new Set();
  if (e.shiftKey && d.panchor != null) { d.psel = new Set(); const [a, b] = [Math.min(d.panchor, i), Math.max(d.panchor, i)]; for (let k = a; k <= b; k++) d.psel.add(k); }
  else if (e.ctrlKey || e.metaKey) { d.psel.has(i) ? d.psel.delete(i) : d.psel.add(i); d.panchor = i; }
  else { d.psel = new Set([i]); d.panchor = i; goPage(i + 1); }
  $('#thumbs').focus({ preventScroll: true });
  markThumb();
}
//  페이지 칸에 초점이 있으면 Ctrl+C·X·V·Delete 는 페이지에
$('#thumbs').tabIndex = 0;
$('#thumbs').addEventListener('keydown', (e) => {
  const c = e.ctrlKey || e.metaKey;
  if (!cur) return;
  if (c && (e.key === 'c' || e.key === 'C')) { e.preventDefault(); e.stopPropagation(); copyPages(false); }
  else if (c && (e.key === 'x' || e.key === 'X')) { e.preventDefault(); e.stopPropagation(); copyPages(true); }
  else if (c && (e.key === 'a' || e.key === 'A')) { e.preventDefault(); e.stopPropagation(); cur.psel = new Set([...Array(cur.n).keys()]); markThumb(); }
  else if (e.key === 'Delete') { e.preventDefault(); e.stopPropagation(); delPages(); }
});
const pagePaste = (e) => { if (document.activeElement === $('#thumbs') && pageClip) { e.preventDefault(); pastePages(); return true; } return false; };
//  오른쪽 단추 메뉴(페이지 칸)
$('#thumbs').addEventListener('contextmenu', (e) => {
  const t = e.target.closest('.th'); if (!t || !cur) return;
  e.preventDefault();
  const i = +t.dataset.i;
  if (!cur.psel || !cur.psel.has(i)) { cur.psel = new Set([i]); cur.panchor = i; markThumb(); }
  ctxMenu(e.clientX, e.clientY, [['오른쪽으로 회전', 'pRotR'], ['왼쪽으로 회전', 'pRotL'], null, ['복사', 'pCopy'], ['잘라내기', 'pCut'], ['붙여넣기(뒤에)', 'pPaste'], ['복제', 'pDup'], null,
    ['앞으로', 'pUp'], ['뒤로', 'pDown'], ['빈 페이지 넣기', 'pInsBlank'], ['파일에서 넣기…', 'pInsFile'], null, ['페이지 추출', 'pExt'], ['이미지로 내보내기…', 'expImg'], ['삭제', 'pDel']]);
});
function ctxMenu(x, y, items) {
  $$('.ctxm').forEach((m) => m.remove());
  const m = h('div', { class: 'ctxm' });
  for (const it of items) m.append(it ? h('button', { text: it[0], 'data-cmd': it[1] }) : h('hr'));
  document.body.append(m);
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 4) + 'px';
  m.style.top = Math.min(y, innerHeight - r.height - 4) + 'px';
  setTimeout(() => document.addEventListener('click', () => m.remove(), { once: true }), 0);
}
//  도형 위 오른쪽 단추
viewer.addEventListener('contextmenu', (e) => {
  if (!cur || !EDIT.EDIT_TOOLS.includes(tool)) return;
  const g = e.target.closest && e.target.closest('[data-id]');
  if (!g) return;
  e.preventDefault();
  const o = cur.ed.objs.find((x) => x.id === g.dataset.id);
  if (o) EDIT.select(cur, o);
  ctxMenu(e.clientX, e.clientY, [['오른쪽으로 회전', 'oRot'], ['왼쪽으로 회전', 'oRotL'], null, ['복사', 'oCopy'], ['잘라내기', 'oCut'], ['붙여넣기', 'oPaste'], ['복제', 'dup'], null, ['삭제', 'del']]);
});
//  글자 표시 도구: 글자를 끌어 고르고 손을 떼면 그 줄에 칠한다
viewer.addEventListener('mouseup', () => {
  if (cur && EDIT.MARK_TOOLS[tool]) setTimeout(() => EDIT.markFromSelection(cur, tool), 0);
});

// ───────────────────────── 파일 메뉴(뒤 화면) · 최근 파일 · 위치 ─────────────────────────
//  최근 파일·위치는 이 PC 의 이 브라우저(또는 윈도우 프로그램)에만 남는다.
const idb = (() => {
  let dbp = null;
  const open = () => dbp || (dbp = new Promise((res, rej) => { const r = indexedDB.open('hanil-pdf', 1); r.onupgradeneeded = () => { r.result.createObjectStore('kv'); }; r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }));
  const tx = async (mode, fn) => { const db = await open(); return new Promise((res, rej) => { const t = db.transaction('kv', mode); const st = t.objectStore('kv'); const r = fn(st); t.oncomplete = () => res(r && r.result); t.onerror = () => rej(t.error); }); };
  return { get: (k) => tx('readonly', (s) => s.get(k)).catch(() => null), set: (k, v) => tx('readwrite', (s) => s.put(v, k)).catch(() => null) };
})();
async function addRecent(d) {
  if (!d || d.isNew) return;
  const list = (await idb.get('recent')) || [];
  const key = d.path && !String(d.path).startsWith('new:') ? d.path : d.name;
  const rest = list.filter((r) => r.key !== key);
  rest.unshift({ key, name: d.name, path: HOST ? d.path : null, handle: d.handle || null, t: Date.now() });
  await idb.set('recent', rest.slice(0, 20));
}
async function openRecent(r) {
  try {
    if (HOST && r.path && HOST.openPath) return HOST.openPath(r.path);
    if (r.handle) {
      if (r.handle.requestPermission && (await r.handle.requestPermission({ mode: 'read' })) !== 'granted') return;
      const d = await openFile(await r.handle.getFile(), { handle: r.handle });
      if (d) activate(d);
      return;
    }
    toast('이 파일은 다시 골라야 합니다(브라우저가 자리를 기억하지 못함)');
    openDialog();
  } catch (e) { ask('열 수 없음', esc(r.name) + '<br>' + esc(e.message || e) + '<br>파일이 옮겨졌거나 지워졌을 수 있습니다.', { cancel: null }); }
}
async function openBackstage(panel = 'open') {
  $('#backstage').classList.add('on');
  $$('#backstage .menu [data-bs]').forEach((b) => b.classList.toggle('on', b.dataset.bs === panel));
  const P = $('#bsPanel');
  P.innerHTML = '';
  if (panel === 'open') {
    P.append(h('h1', { text: '열기' }));
    const col = h('div', { class: 'bscol' }), list = h('div', { class: 'bslist' });
    const item = (icon, title, sub, onclick, extra) => {
      const b = h('div', { class: 'bsitem', title: sub || title }, h('span', { class: 'bsi', text: icon }), h('div', {}, h('b', { text: title }), sub ? h('small', { text: sub }) : null));
      b.onclick = onclick;
      if (extra) b.append(extra);
      return b;
    };
    const recent = (await idb.get('recent')) || [];
    const places = (await idb.get('places')) || [];
    const sec = (t) => h('div', { class: 'bssec', text: t });
    col.append(sec('최근 파일'));
    if (!recent.length) col.append(h('div', { class: 'bsnone', text: '아직 연 파일이 없습니다' }));
    for (const r of recent.slice(0, 12)) col.append(item('📄', r.name, (r.path || '') + ' · ' + new Date(r.t).toLocaleString('ko-KR'), () => { closeBackstage(); openRecent(r); }));
    col.append(sec('URL 에서 열기'));
    const u = h('input', { type: 'url', placeholder: 'https://… .pdf', class: 'bsurl' });
    const go = () => { if (u.value) { closeBackstage(); openUrl0(u.value.trim(), null); } };
    u.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
    col.append(h('div', { class: 'bsrow' }, u, h('button', { text: '열기', onclick: go })));
    col.append(sec('위치'));
    for (const pl of places) {
      const x = h('button', { class: 'bsx', text: '✕', title: '목록에서 빼기', onclick: async (e) => { e.stopPropagation(); await idb.set('places', places.filter((q) => q !== pl)); openBackstage('open'); } });
      col.append(item('📁', pl.name, pl.path || '', () => showPlace(pl, list), x));
    }
    col.append(item('➕', '위치 추가', '자주 여는 폴더를 고릅니다', addPlace));
    col.append(item('📂', '찾아보기', 'Ctrl+O', () => { closeBackstage(); openDialog(); }));
    P.append(h('div', { class: 'bsgrid' }, col, list));
  } else if (panel === 'export') {
    P.append(h('h1', { text: '내보내기' }));
    const col = h('div', { class: 'bscol' });
    const items = [['🖼', '이미지로 내보내기', 'PNG·JPEG · 여러 쪽은 ZIP', 'expImg'], ['📑', '페이지 추출', '고른 페이지를 새 PDF 로', 'pExt'], ['🗂', '검색 결과 목록', '검색 창의 [목록 저장(엑셀)]', 'searchPane']];
    if (HOST && HOST.exportHtml) items.push(['🌐', '브라우저용 파일', '설치가 안 되는 PC 에서 쓸 한 장(html)', 'exportHtml']);
    for (const [i, t, s, c] of items) {
      const b = h('div', { class: 'bsitem' }, h('span', { class: 'bsi', text: i }), h('div', {}, h('b', { text: t }), h('small', { text: s })));
      b.onclick = () => { closeBackstage(); CMD[c](); };
      col.append(b);
    }
    P.append(col);
  }
}
function closeBackstage() { $('#backstage').classList.remove('on'); }
async function addPlace() {
  try {
    let pl;
    if (HOST && HOST.pickFolder) { const p = await HOST.pickFolder(); if (!p) return; pl = { name: p.split(/[\\/]/).filter(Boolean).pop(), path: p }; }
    else if (window.showDirectoryPicker) { const dh = await window.showDirectoryPicker(); pl = { name: dh.name, handle: dh }; }
    else return ask('위치 추가', '이 브라우저는 폴더를 기억할 수 없습니다(크롬·엣지에서 됩니다).', { cancel: null });
    const places = (await idb.get('places')) || [];
    places.push(pl);
    await idb.set('places', places);
    openBackstage('open');
  } catch (e) { if (e && e.name !== 'AbortError') toast(String(e.message || e)); }
}
async function showPlace(pl, box) {
  box.innerHTML = '';
  box.append(h('div', { class: 'bssec', text: '📁 ' + pl.name }));
  try {
    let files = [];
    if (pl.path && HOST && HOST.listDir) files = (await HOST.listDir(pl.path)).map((f) => ({ name: f.name, open: () => HOST.openPath(f.path), dir: f.dir, path: f.path }));
    else if (pl.handle) {
      if ((await pl.handle.requestPermission({ mode: 'read' })) !== 'granted') return;
      for await (const [name, hd] of pl.handle.entries()) {
        if (hd.kind === 'directory') files.push({ name, dir: true, handle: hd });
        else if (/\.pdf$/i.test(name)) files.push({ name, open: async () => { const d = await openFile(await hd.getFile(), { handle: hd }); if (d) activate(d); } });
      }
    }
    files.sort((a, b) => (b.dir ? 1 : 0) - (a.dir ? 1 : 0) || collator.compare(a.name, b.name));
    if (!files.length) box.append(h('div', { class: 'bsnone', text: 'PDF 가 없습니다' }));
    for (const f of files) {
      const b = h('div', { class: 'bsitem small' }, h('span', { class: 'bsi', text: f.dir ? '📁' : '📄' }), h('div', {}, h('b', { text: f.name })));
      b.onclick = () => (f.dir ? showPlace({ name: pl.name + ' › ' + f.name, handle: f.handle, path: f.path }, box) : (closeBackstage(), f.open()));
      box.append(b);
    }
  } catch (e) { box.append(h('div', { class: 'bsnone', text: '열 수 없습니다: ' + (e.message || e) })); }
}
$('#backstage').addEventListener('click', (e) => {
  if (e.target.id === 'backstage') return closeBackstage();
  const b = e.target.closest('[data-bs]');
  if (b) openBackstage(b.dataset.bs);
});

// ───────────────────────── 환경 설정 ─────────────────────────
const SET = Object.assign({ zoom: 'width', layout: 'one', bg: 'gray', author: MAKER, sc: '#e5262e', lw: 2, fs: 14, ignoreSpace: true, snapDpi: 200, askClose: true }, (() => { try { return JSON.parse(localStorage.getItem('hanil-pdf-set') || '{}'); } catch { return {}; } })());
function applySettings() {
  EDIT.style.sc = SET.sc; EDIT.style.lw = +SET.lw; EDIT.style.fs = +SET.fs; EDIT.style.author = SET.author || MAKER;
  $('#oSpace').checked = !!SET.ignoreSpace;
  document.body.classList.toggle('darkbg', SET.bg === 'dark');
  EDIT.syncControls();
}
function settings() {
  const cats = [
    ['일반', '⚙', () => [row('닫을 때 저장 확인', chk('askClose')), note('탭으로 여러 문서를 엽니다. 창을 닫을 때 저장 안 한 문서가 있으면 묻습니다.')]],
    ['페이지 표시', '📄', () => [row('처음 확대', sel('zoom', [['width', '너비에 맞춤'], ['page', '페이지에 맞춤'], ['1', '실제 크기(100%)']])), row('페이지 보기', sel('layout', [['one', '연속'], ['two', '두 페이지']])), row('바탕', sel('bg', [['gray', '회색'], ['dark', '어두운 색']]))]],
    ['주석 달기', '📝', () => [row('작성자 이름', txt('author')), row('기본 선 색', col('sc')), row('기본 굵기', sel('lw', [[1, '1 pt'], [2, '2 pt'], [3, '3 pt'], [5, '5 pt']])), row('기본 글자 크기', sel('fs', [[10, '10'], [12, '12'], [14, '14'], [18, '18'], [24, '24']])), note('작성자 이름은 저장한 주석에 들어가 Acrobat·PDF-XChange 의 주석 목록에 보입니다.')]],
    ['검색', '🔎', () => [row('띄어쓰기·줄바꿈 무시(기본)', chk('ignoreSpace')), note('표 안에서 번호가 끊겨 있어도 찾습니다.')]],
    ['스냅샷 도구', '📷', () => [row('해상도', sel('snapDpi', [[96, '96 dpi'], [150, '150 dpi'], [200, '200 dpi'], [300, '300 dpi']]))]],
    ['파일 연결', '🔗', () => (HOST && HOST.associate
      ? [note('<b>① 탐색기에서 PDF 를 두 번 누르면</b> 이 프로그램으로 — 윈도우 설정이 열리면 .pdf 의 앱을 「한일 PDF 리더」로 고르세요.'), h('button', { class: 'setbtn', text: '기본 PDF 프로그램으로', onclick: () => HOST.associate() }),
        note('<b>② 크롬·엣지에서 연 PDF</b>(포털 첨부 등)도 이 프로그램으로 — 브라우저 안 뷰어 대신 내려받아 이 프로그램으로 엽니다. 바꾼 뒤 브라우저를 다시 켜세요.'), browserRow(),
        note('<b>③ 탐색기 미리 보기</b>(미리 보기 창 Alt+P · 큰 아이콘) — 설치할 때 함께 켜집니다.'), h('button', { class: 'setbtn', text: '탐색기 미리 보기 다시 켜기', onclick: () => HOST.preview && HOST.preview() }),
        note('설치가 안 되는 PC 에서 쓰려면 브라우저용 파일 한 장을 만들어 가져가세요.'), h('button', { class: 'setbtn', text: '브라우저용 파일 만들기…', onclick: () => HOST.exportHtml() })]
      : [note('지금은 브라우저에서 열려 있습니다. PDF 를 두 번 눌러 열기 · 크롬·엣지의 PDF 를 이 리더로 · 탐색기 미리 보기는 <b>윈도우 프로그램 hanil-pdf.exe</b> 하나를 설치하면 모두 됩니다.')])],
    ['정보', 'ℹ', () => [note('<b>한일 PDF 리더</b> ' + esc((document.querySelector('meta[name=hanil-pdf]') || {}).content || '') + '<br>제작사: <b>' + MAKER + '</b><br>엔진: pdf.js (Apache-2.0) · pdf-lib (MIT)')]],
  ];
  const draft = { ...SET };
  function browserRow() {
    const i = h('input', { type: 'checkbox' });
    const row = h('label', { class: 'setrow' }, h('span', { text: '크롬·엣지 PDF → 이 프로그램' }), i);
    HOST.browserPdfState().then((on) => (i.checked = !!on));
    i.onchange = () => HOST.browserPdf(i.checked);
    return row;
  }
  function row(label, el) { return h('label', { class: 'setrow' }, h('span', { text: label }), el); }
  function note(t) { const n = h('div', { class: 'setnote' }); n.innerHTML = t; return n; }
  function chk(k) { const i = h('input', { type: 'checkbox' }); i.checked = !!draft[k]; i.onchange = () => (draft[k] = i.checked); return i; }
  function txt(k) { const i = h('input', { type: 'text', value: draft[k] || '' }); i.oninput = () => (draft[k] = i.value); return i; }
  function col(k) { const i = h('input', { type: 'color', value: draft[k] }); i.oninput = () => (draft[k] = i.value); return i; }
  function sel(k, opts) { const s = h('select'); for (const [v, t] of opts) s.append(h('option', { value: v, text: t })); s.value = String(draft[k]); s.onchange = () => (draft[k] = s.value); return s; }
  const left = h('div', { class: 'setcats' }), right = h('div', { class: 'setbody' });
  const show = (k) => { $$('.setcats button', left).forEach((b, j) => b.classList.toggle('on', j === k)); right.innerHTML = ''; right.append(h('div', { class: 'sethd', text: cats[k][1] + ' ' + cats[k][0] + ' 설정' }), ...cats[k][2]()); };
  cats.forEach(([n, i], k) => left.append(h('button', { text: i + '  ' + n, onclick: () => show(k) })));
  const m = h('div', { class: 'setwin' }, h('div', { class: 'setttl' }, h('span', { text: '환경 설정' }), h('button', { text: '×', onclick: () => m.parentNode.remove() })),
    h('div', { class: 'setmain' }, h('div', { class: 'setleft' }, h('div', { class: 'setcap', text: '범주' }), left), right),
    h('div', { class: 'setfoot' },
      h('button', { text: '확인(O)', onclick: () => { save(); m.parentNode.remove(); } }),
      h('button', { text: '적용(P)', onclick: save }),
      h('button', { text: '취소(C)', onclick: () => m.parentNode.remove() })));
  function save() {
    Object.assign(SET, draft);
    try { localStorage.setItem('hanil-pdf-set', JSON.stringify(SET)); } catch {}
    applySettings();
    toast('설정을 저장했습니다');
  }
  document.body.append(h('div', { class: 'setback' }, m));
  show(0);
}

EDIT.initEdit({
  cur: () => cur, tool: () => tool, setTool, scaleOf, toast, ask, focus: () => viewer.focus({ preventScroll: true }),
  vp1: async (d, i) => (await d.pdf.getPage(i + 1)).getViewport({ scale: 1 }),
  rerender: (d) => { for (const p of d.pages) p.key = null; schedule(); },
  onModified: () => renderTabs(), visibleCenter, syncSymButton, snapshot, cropBox, pagePaste,
  docOf: (o) => (cur && cur.ed && cur.ed.objs.includes(o) ? cur : docs.find((d) => d.ed && d.ed.objs.includes(o))),
});

let resizeT = 0;
window.addEventListener('resize', () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => { if (cur && cur.fit) setZoom(cur.fit); else schedule(); for (const d of docs) if (d !== cur && d.fit) d.dirty = true; }, 120);
});
applySettings();
if (SET.layout === 'two') twoPage = true;
renderRibbon();
updateUi();
{
  //  ?src=<주소> — 크롬 확장의 규칙은 주소를 인코딩하지 않고 그대로 붙인다(그 주소 안의 & 까지) → ?src= 뒤를 통째로
  const m = /[?&]src=(.*)$/.exec(location.search);
  if (m) {
    let src = m[1], name = null;
    const nm = /&name=([^&]*)$/.exec(src);
    if (nm && /^https?%3A|^file%3A|^%2F/i.test(src)) { name = decodeURIComponent(nm[1]); src = src.slice(0, nm.index); }
    if (/^(https?|file)%3A|^%2F/i.test(src)) src = decodeURIComponent(src);
    openUrl0(src, name);
  }
  if (HOST && HOST.ready) HOST.ready({ openUrl: openUrl0, openFiles, docs, ask, welcome });
}
//  처음 설치한 뒤 한 번 — 기본 PDF 프로그램으로 지정할지
function welcome() {
  ask('한일 PDF 리더를 설치했습니다', '이 프로그램 하나가 세 가지를 합니다:<br>① PDF 보기·찾기·고치기 창 (바탕 화면·시작 메뉴 아이콘)<br>② 크롬·엣지에서 연 PDF 도 이 프로그램으로 (브라우저를 다시 켜면)<br>③ 탐색기 미리 보기 (미리 보기 창 Alt+P · 큰 아이콘)<br><br>'
    + 'PDF 를 <b>두 번 누르면 이 프로그램으로</b> 열리게 할까요?<br><small style="color:#777">윈도우 설정 화면이 열리면 .pdf 의 앱을 「한일 PDF 리더」로 고르세요.</small><br><br><small>제작: ' + MAKER + '</small>',
    { ok: '기본 프로그램으로', cancel: '나중에' }).then((r) => { if (r === true && HOST.associate) HOST.associate(); });
}
//  윈도우 프로그램이 창을 닫기 전에 묻는다 — 저장 안 한 문서가 있으면
window.__hanilCanClose = async () => {
  const m = docs.filter((d) => d.mod);
  if (!m.length) return true;
  const r = await ask('끝내기', '저장하지 않은 문서가 있습니다:<br><b>' + m.map((d) => esc(d.name)).join('<br>') + '</b><br><br>저장하지 않고 끝낼까요?', { ok: '저장 안 하고 끝내기', cancel: '취소' });
  return r === true;
};
{
}
window.__pdfReader = { docs, openFiles, openUrl: openUrl0, get cur() { return cur; }, get tool() { return tool; }, runSearch, S, EDIT, saveDoc, buildPdf: (d) => EDIT.buildPdf(d) };
