//  🧊 한일특장 3D 도면 보기 — STEP(.stp/.step) · IGES(.igs/.iges) · BREP
//   ⭐ 브라우저 안에서 다 한다: OpenCASCADE(occt-import-js, WASM)가 곡면을 삼각형으로 깎고 three.js 가 그린다.
//      서버에 아무것도 안 깔아도 되고, 파일이 이 기기 밖으로 나가지 않는다.
//   ⚠ CATIA 원본(.CATPart·.CATProduct)은 3D 로는 못 연다(다쏘 독점 형식) — 파일 안의 미리보기 그림을 보인다.
//   ⭐ 큰 파일(100MB 급): 포털에서는 **포털 변환기**(viewer3d-route.js)가 한 번 가볍게 바꿔 두고 그것을 받는다.
//      직접 읽을 때도 엔진은 **일꾼(Web Worker)** 에서 돌아 화면이 멈추지 않는다.
//   쓰는 곳 두 군데(같은 코드):
//     · 폰 앱 안 — 앱이 첨부(.stp)를 받아 ?src= 로 넘긴다
//     · PC 단독 HTML 한 장 — 끌어다 놓기·파일 고르기 (WASM 을 글자로 품고 있어 인터넷 없이도 열린다)
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { toCreasedNormals } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { SAMPLE_STEP } from './sample.js';
import { WORKER_BODY } from './occt-worker-body.mjs';

const $ = (id) => document.getElementById(id);
const view = $('view');

// ── 그리기 판 ───────────────────────────────────────────────
//   ⚠⚠ 그래픽 가속(WebGL)이 안 되는 PC 가 있다(원격 데스크톱·옛 그래픽 드라이버·막아 둔 브라우저).
//     그때 WebGL 을 만들다 터지면 **스크립트 전체가 멈춰** 3D 는 물론 DWG 까지 아무것도 안 떴다(포털 쪽 신고).
//   ⭐ 그래서 WebGL 은 되면 쓰고, 안 되면 **간이 미리보기**(2D 그림판에 직접 그림 — 돌려 보기는 됨)로 넘어간다.
let renderer = null, glOk = false, glWhy = '';
try {
  const t = document.createElement('canvas');
  if (!(t.getContext('webgl2') || t.getContext('webgl'))) throw new Error('WebGL 없음');
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0xeef1f6, 1);
  view.appendChild(renderer.domElement);
  glOk = true;
} catch (e) {
  glWhy = String(e && e.message || e);
  renderer = null;
}

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100000);
camera.up.set(0, 0, 1);                    //  CAD 는 대개 Z 가 위
scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa6b8, 2.2));
const head = new THREE.DirectionalLight(0xffffff, 2.2);   //  카메라에 붙은 불 — 어느 쪽에서 봐도 밝다
camera.add(head);
head.position.set(0.5, 1, 1);
scene.add(camera);

const controls = glOk ? new OrbitControls(camera, renderer.domElement) : null;
if (controls) {
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.screenSpacePanning = true;
}

let model = null;          //  지금 그린 것(THREE.Group)
let parts = [];            //  { name, mesh, edges, color }
let box = null;            //  크기 상자
let fileBytes = null, fileName = '';
let edgesOn = true, glass = false, measuring = false;

function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  if (glOk) renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
  if (!glOk) soft.draw();
}
window.addEventListener('resize', resize);
(function loop() {
  if (!glOk) return;
  requestAnimationFrame(loop);
  controls.update();
  renderer.render(scene, camera);
})();

// ── 간이 미리보기(WebGL 없을 때) ────────────────────────────
//   삼각형을 깊이 순으로 칠한다(먼 것부터). 끌면 돈다·바퀴로 확대. 크기·부품 수·그림 저장은 그대로.
const soft = {
  cv: null, tris: null, rot: { yaw: -0.8, pitch: 0.55 }, zoom: 1, c: null, r: 1,
  init() {
    if (this.cv) return;
    this.cv = document.createElement('canvas');
    this.cv.style.cssText = 'display:block;width:100%;height:100%;touch-action:none';
    view.appendChild(this.cv);
    let d = null;
    this.cv.addEventListener('pointerdown', (e) => { d = { x: e.clientX, y: e.clientY }; this.cv.setPointerCapture(e.pointerId); });
    this.cv.addEventListener('pointermove', (e) => {
      if (!d) return;
      this.rot.yaw += (e.clientX - d.x) * 0.01; this.rot.pitch = Math.max(-1.55, Math.min(1.55, this.rot.pitch + (e.clientY - d.y) * 0.01));
      d = { x: e.clientX, y: e.clientY }; this.draw();
    });
    this.cv.addEventListener('pointerup', () => { d = null; });
    this.cv.addEventListener('wheel', (e) => { e.preventDefault(); this.zoom *= e.deltaY > 0 ? 0.88 : 1.14; this.draw(); }, { passive: false });
  },
  load(res, colors) {
    this.init();
    const T = [];
    const b = new THREE.Box3();
    //  ⚠ 2D 그림판은 느리다 — 삼각형이 많으면 고르게 솎아 30만 개 안쪽만 그린다(미리보기니까)
    let all = 0;
    res.meshes.forEach((m) => { all += (m.index ? m.index.array.length : m.attributes.position.array.length / 3) / 3; });
    const step = Math.max(1, Math.ceil(all / 300000)) * 3;
    res.meshes.forEach((m, i) => {
      const P = m.attributes.position.array, I = m.index ? m.index.array : null;
      const n = I ? I.length : P.length / 3;
      const col = new THREE.Color(colors[i]);
      for (let k = 0; k < n; k += step) {
        const a = (I ? I[k] : k) * 3, bb = (I ? I[k + 1] : k + 1) * 3, cc = (I ? I[k + 2] : k + 2) * 3;
        T.push([P[a], P[a + 1], P[a + 2], P[bb], P[bb + 1], P[bb + 2], P[cc], P[cc + 1], P[cc + 2], col.r, col.g, col.b, i]);
      }
      for (let k = 0; k < P.length; k += 3 * Math.max(1, step / 3)) b.expandByPoint(new THREE.Vector3(P[k], P[k + 1], P[k + 2]));
    });
    this.tris = T;
    this.c = b.getCenter(new THREE.Vector3());
    this.r = Math.max(b.getSize(new THREE.Vector3()).length() / 2, 1e-6);
    this.zoom = 1;
    this.draw();
  },
  view(dir) {
    const V = { iso: [-0.8, 0.55], front: [0, 0], top: [0, 1.55], side: [-Math.PI / 2, 0] }[dir || 'iso'];
    this.rot.yaw = V[0]; this.rot.pitch = V[1]; this.zoom = 1; this.draw();
  },
  draw() {
    if (!this.cv || !this.tris) return;
    const k = Math.min(window.devicePixelRatio || 1, 2), W = view.clientWidth, H = view.clientHeight;
    this.cv.width = W * k; this.cv.height = H * k;
    const g = this.cv.getContext('2d');
    g.setTransform(k, 0, 0, k, 0, 0);
    g.fillStyle = '#eef1f6'; g.fillRect(0, 0, W, H);
    const cy = Math.cos(this.rot.yaw), sy = Math.sin(this.rot.yaw), cp = Math.cos(this.rot.pitch), sp = Math.sin(this.rot.pitch);
    const sc = Math.min(W, H) / 2 / this.r * 0.9 * this.zoom, ox = W / 2, oy = H / 2, C = this.c;
    //  Z 가 위: 먼저 Z 축으로 돌리고(yaw), 그다음 앞뒤로 숙인다(pitch). 화면 x=오른쪽, y=아래, 깊이=화면 안쪽
    const pr = (x, y, z) => {
      x -= C.x; y -= C.y; z -= C.z;
      const x1 = x * cy - y * sy, y1 = x * sy + y * cy;
      const zz = z * cp - y1 * sp, dd = y1 * cp + z * sp;
      return [ox + x1 * sc, oy - zz * sc, dd];
    };
    const vis = parts.length ? parts.map((p) => p.mesh.visible) : null;
    const L = [];
    for (const t of this.tris) {
      if (vis && vis[t[12]] === false) continue;
      const a = pr(t[0], t[1], t[2]), b = pr(t[3], t[4], t[5]), c = pr(t[6], t[7], t[8]);
      //  빛 — 화면 쪽을 향한 정도(면의 기울기)
      const ux = b[0] - a[0], uy = b[1] - a[1], vx = c[0] - a[0], vy = c[1] - a[1];
      const ar = ux * vy - uy * vx;
      const nx = (t[4] - t[1]) * (t[8] - t[2]) - (t[5] - t[2]) * (t[7] - t[1]);
      const ny = (t[5] - t[2]) * (t[6] - t[0]) - (t[3] - t[0]) * (t[8] - t[2]);
      const nz = (t[3] - t[0]) * (t[7] - t[1]) - (t[4] - t[1]) * (t[6] - t[0]);
      const nl = Math.hypot(nx, ny, nz) || 1;
      //  보는 방향(화면 안쪽) 벡터를 원래 좌표로
      const vxw = sy * cp, vyw = cy * cp * -1, vzw = sp;
      const lam = Math.abs((nx * -vxw + ny * -vyw + nz * vzw) / nl);
      L.push([(a[2] + b[2] + c[2]) / 3, a, b, c, t[9], t[10], t[11], 0.45 + 0.55 * lam, ar]);
    }
    L.sort((p, q) => q[0] - p[0]);
    for (const q of L) {
      const sh = q[7];
      const col = 'rgb(' + Math.round(q[4] * 255 * sh) + ',' + Math.round(q[5] * 255 * sh) + ',' + Math.round(q[6] * 255 * sh) + ')';
      g.fillStyle = col; g.strokeStyle = col; g.lineWidth = 0.6;
      g.beginPath(); g.moveTo(q[1][0], q[1][1]); g.lineTo(q[2][0], q[2][1]); g.lineTo(q[3][0], q[3][1]); g.closePath();
      g.fill(); g.stroke();
    }
  },
};
resize();

// ── 알림 ────────────────────────────────────────────────────
let msgT = 0;
function toast(t, ms) {
  const m = $('msg');
  m.textContent = t;
  m.style.display = 'block';
  clearTimeout(msgT);
  msgT = setTimeout(() => { m.style.display = 'none'; }, ms || 2500);
}
function busy(on, t) {
  $('busy').classList.toggle('on', !!on);
  if (t) $('busyT').textContent = t;
}

// ── OpenCASCADE — 일꾼(Web Worker) 안에서 돈다 ─────────────────
//   ⚠ 큰 STEP 은 읽는 데 몇 분 걸린다 — 화면 쪽에서 돌리면 그동안 브라우저가 「응답 없음」이 된다.
//     일꾼에서 돌리면 화면은 살아 있고 「n초째」를 보여 줄 수 있다.
//   일꾼 만들기: 포털·앱은 occt-worker.js 파일, PC 단독판은 품고 있는 엔진 글(<script id="occtjs">)로.
//  일꾼 글은 occt-worker-body.mjs 에(build.mjs 가 occt-worker.js 파일로도 쓴다)
let wk = null, wkWait = null, wasmSent = false;
function worker() {
  if (wk) return wk;
  wasmSent = false;
  const src = document.getElementById('occtjs');
  if (src) {
    //  PC 단독판 — 엔진 글과 일꾼 글을 합쳐 일꾼을 만든다(file:// 은 따로 받아올 수 없다)
    wk = new Worker(URL.createObjectURL(new Blob([src.textContent + '\n' + WORKER_BODY], { type: 'text/javascript' })));
  } else {
    wk = new Worker('occt-worker.js?v=' + (document.querySelector('meta[name=hanil-viewer3d]') || {}).content);
  }
  wk.onmessage = (e) => { const w = wkWait; wkWait = null; if (w) (e.data.ok ? w.ok(e.data) : w.no(new Error(e.data.err))); };
  wk.onerror = (e) => {
    e.preventDefault && e.preventDefault();
    const w = wkWait; wkWait = null; wk.terminate(); wk = null;
    if (w) w.no(new Error(String(e.message || '3D 엔진이 멈췄습니다') + ' — 이 기기 메모리로는 벅찬 큰 파일일 수 있습니다'));
  };
  return wk;
}
let wasmB = null;
function engineMsg(msg) {
  const w = worker();
  if (window.OCCT_WASM_B64 && !wasmB) {
    const bin = atob(window.OCCT_WASM_B64);
    wasmB = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) wasmB[i] = bin.charCodeAt(i);
    window.OCCT_WASM_B64 = null;
  }
  msg.wasm = wasmSent ? null : wasmB;            //  엔진(7MB)은 일꾼에 한 번만 넘긴다
  wasmSent = true;
  msg.base = new URL('.', location.href).href;
  return new Promise((ok, no) => { wkWait = { ok, no }; w.postMessage(msg); });
}
let warmP = null;
function occtWarm() { return warmP || (warmP = engineMsg({ cmd: 'warm' }).catch((e) => { warmP = null; throw e; })); }
async function parse3d(kind, u8) {
  await occtWarm();
  const r = await engineMsg({ kind, u8, params: quality(u8.length) });
  return r.res;
}
//  큰 파일일수록 덜 곱게 깎는다(미리보기니까) — 포털 변환기(viewer3d-convert.js quality)와 같게
function quality(bytes) {
  const mb = bytes / 1048576;
  if (mb < 10) return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.001, angularDeflection: 0.5 };
  if (mb < 40) return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.002, angularDeflection: 0.8 };
  return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.004, angularDeflection: 1.2 };
}
//  「n초째」 시계 — 오래 걸리는 일 동안 멈춘 게 아님을 보인다
function ticker(label, est) {
  const t0 = Date.now();
  const f = () => {
    const sec = Math.round((Date.now() - t0) / 1000);
    busy(true, label + '\n' + clock(sec) + (est ? ' / 어림 ' + clock(est) : ''));
  };
  f();
  const id = setInterval(f, 1000);
  return () => clearInterval(id);
}
function clock(sec) { return sec >= 60 ? Math.floor(sec / 60) + '분 ' + (sec % 60) + '초' : sec + '초'; }
const MB = (n) => (n / 1048576 >= 10 ? Math.round(n / 1048576) : Math.round(n / 104857.6) / 10) + 'MB';

// ── .hm3 — 포털 변환기가 만든 가벼운 미리보기 묶음 읽기 ───────────────
//   'HM3' 1 | 머리글 길이 | 머리글 JSON | (부품마다) 꼭짓점 Uint16×3 · 삼각형 번호 Uint16/Uint32  (viewer3d-convert.js packHM3)
function loadHM3(ab) {
  const dv = new DataView(ab);
  if (dv.getUint8(0) !== 0x48 || dv.getUint8(1) !== 0x4D || dv.getUint8(2) !== 0x33) throw new Error('변환 결과가 깨졌습니다');
  const hl = dv.getUint32(4, true);
  const head = JSON.parse(new TextDecoder().decode(new Uint8Array(ab, 8, hl)));
  let p = 8 + hl;
  const meshes = head.meshes.map((m) => {
    const nq = m.n * 3 + ((m.n * 3) & 1);
    const q = new Uint16Array(ab, p, nq); p += nq * 2;
    const pos = new Float32Array(m.n * 3);
    const sc = [0, 1, 2].map((a) => (m.max[a] - m.min[a]) / 65535);
    for (let i = 0; i < m.n * 3; i += 3) {
      pos[i] = m.min[0] + q[i] * sc[0]; pos[i + 1] = m.min[1] + q[i + 1] * sc[1]; pos[i + 2] = m.min[2] + q[i + 2] * sc[2];
    }
    let idx = null;
    if (m.i) {
      if (m.i16) { const ni = m.i + (m.i & 1); idx = new Uint16Array(ab, p, m.i); p += ni * 2; } else { idx = new Uint32Array(ab, p, m.i); p += m.i * 4; }
    }
    return { name: m.name, color: m.color, attributes: { position: { array: pos } }, index: idx ? { array: idx } : null };
  });
  return { success: true, root: null, meshes, head };
}

// ── 파일 읽기 ───────────────────────────────────────────────
function kindOf(name, u8) {
  const ext = String(name || '').split('.').pop().toLowerCase();
  if (ext === 'stp' || ext === 'step') return 'step';
  if (ext === 'igs' || ext === 'iges') return 'iges';
  if (ext === 'brep' || ext === 'brp') return 'brep';
  if (ext === 'dwg') return 'dwg';
  if (/^(catpart|catproduct|catdrawing|catshape|catsystem|catmaterial|cgr|catanalysis|catprocess)$/.test(ext)) return 'catia';
  if (ext === 'dxf') return 'dxf';
  //  이름으로 모르면 앞머리를 본다
  const head = new TextDecoder('latin1').decode(u8.slice(0, 400));
  if (/ISO-10303-21/.test(head)) return 'step';
  if (/^.{72}S\s*1\s*$/m.test(head)) return 'iges';
  if (/^AC10\d\d/.test(head)) return 'dwg';
  if (/^V5_CFV2/.test(head)) return 'catia';
  if (/^\s*0\s*[\r\n]+\s*SECTION/.test(head)) return 'dxf';
  return '';
}

async function openBytes(name, u8) {
  const kind = kindOf(name, u8);
  if (!kind) {
    toast('STEP(.stp)·IGES(.igs)·DWG·DXF·CATIA 파일만 열 수 있습니다', 4000);
    return;
  }
  fileBytes = u8;
  fileName = name || ('model.' + kind);
  $('fname').textContent = fileName;
  document.title = fileName + ' — 도면 보기';
  if (kind === 'dwg' || kind === 'dxf') { await open2d(u8, kind); return; }
  if (kind === 'catia') { await openCatia(u8); return; }
  document.body.classList.remove('modeimg');
  if ($('vimg')) $('vimg').innerHTML = '';
  document.body.classList.remove('mode2d');
  busy(true, '3D 엔진을 준비하는 중…');
  let stop = null;
  try {
    await occtWarm();
    //  어림 — 이 엔진은 대략 1MB 에 2~3초(PC). 폰은 더 걸린다.
    const est = Math.round(2 + u8.length / 1048576 * (isSmall() ? 6 : 2.5));
    //  ⚠ 부품이 많으면 이 엔진은 부품 수의 제곱으로 느려진다 — 20MB 넘으면 어림을 안 보인다(틀리니까)
    const big = u8.length > 20 * 1048576;
    stop = ticker('모양을 읽는 중… (' + MB(u8.length) + ')' + (big ? '\n큰 파일이라 여기서는 수십 분 걸릴 수 있습니다\n포털의 도면 보기로 열면 서버가 1~2분에 바꿔 줍니다' : ''), !big && est > 8 ? est : 0);
    const t0 = performance.now();
    const res = await parse3d(kind, u8.slice());
    stop(); stop = null;
    if (!res || !res.success || !res.meshes || !res.meshes.length) throw new Error('모양을 찾지 못했습니다(파일이 깨졌거나 빈 파일)');
    busy(true, '그리는 중…');
    await new Promise((r) => setTimeout(r, 30));
    build(res);
    const ms = Math.round(performance.now() - t0);
    console.log('[3D] ' + fileName + ' ' + ms + 'ms');
  } catch (e) {
    if (stop) stop();
    fail('도면을 열지 못했습니다', (e && e.message || e) + (u8.length > 30 * 1048576 ? '\n큰 파일은 포털의 도면 보기로 여세요 — 포털 서버가 한 번 가볍게 바꿔 둡니다.' : ''));
  }
  busy(false);
}

//  ⚠ 못 열었으면 **까닭을 화면 가운데 남긴다**(잠깐 뜨고 사라지는 알림만으로는 무엇이 틀렸는지 모른다)
function fail(title, detail) {
  document.body.classList.remove('modeimg');
  busy(false);
  const d = $('drop');
  d.style.display = 'flex';
  d.querySelector('.card').innerHTML = '<b style="color:#b3261e">⚠ ' + esc0(title) + '</b>'
    + '<p style="text-align:left;word-break:break-all">' + esc0(detail) + '</p>'
    + '<p style="font-size:12.5px">이 PC: 그래픽 가속 ' + (glOk ? '켜짐' : '꺼짐(간이 미리보기)') + ' · WebAssembly ' + (typeof WebAssembly === 'object' ? '됨' : '<b>안 됨 — 브라우저가 너무 옛것</b>') + '</p>'
    + '<label>📂 다른 파일 고르기<input id="file3" type="file" accept=".stp,.step,.igs,.iges,.brep,.dwg,.dxf,.catpart,.catproduct,.catdrawing,.cgr"></label>';
  const f3 = $('file3');
  if (f3) f3.onchange = function () { fromInput(this); };
}
function esc0(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ── 장면 만들기 ─────────────────────────────────────────────
const PALETTE = [0x8fa3bf, 0xc7a46b, 0x7fb08a, 0xb98aa8, 0x6fa6c9, 0xc98a6f, 0x9a93c9, 0xa9b56f];
function build(res) {
  if (model) {
    scene.remove(model);
    model.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  }
  clearMeasure();
  model = new THREE.Group();
  parts = [];
  //  부품 이름 — 나무(root) 마디 이름을 그 마디의 모양에 붙인다
  const names = {};
  (function walk(n, path) {
    if (!n) return;
    const nm = (n.name || '').trim();
    (n.meshes || []).forEach((i) => { names[i] = nm || path; });
    (n.children || []).forEach((c) => walk(c, nm || path));
  })(res.root, '');
  let tris = 0;
  const many = res.meshes.length > 1;
  //  ⚠ 아주 큰 모델(삼각형 150만 개 넘음)은 모서리 선 계산이 오래 걸려 끈다 — 「선」 단추도 숨긴다
  let allTri = 0;
  res.meshes.forEach((m) => { allTri += (m.index ? m.index.array.length : m.attributes.position.array.length / 3) / 3; });
  const noEdge = allTri > 800000;
  res.meshes.forEach((m, i) => {
    let g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(m.attributes.position.array, 3));
    if (m.attributes.normal) g.setAttribute('normal', new THREE.Float32BufferAttribute(m.attributes.normal.array, 3));
    if (m.index) g.setIndex(new THREE.BufferAttribute(m.index.array instanceof Uint16Array || m.index.array instanceof Uint32Array ? m.index.array : Uint32Array.from(m.index.array), 1));
    //  서버 OpenCASCADE 로 바꾼 것(STL 꼴)은 면 경계를 모른다 — 30° 넘게 꺾인 곳은 날카롭게(상자 모서리가 뭉개지지 않게)
    if (res.head && res.head.crease) g = toCreasedNormals(g, Math.PI / 6);
    else if (!m.attributes.normal) g.computeVertexNormals();
    tris += (m.index ? m.index.array.length : m.attributes.position.array.length / 3) / 3;
    let color = many ? PALETTE[i % PALETTE.length] : 0xb4c3d8;
    if (m.color && m.color.length === 3) color = new THREE.Color(m.color[0], m.color[1], m.color[2]).getHex();
    const mat = new THREE.MeshStandardMaterial({ color, metalness: 0.1, roughness: 0.45, side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const mesh = new THREE.Mesh(g, mat);
    const edges = noEdge ? null : new THREE.LineSegments(new THREE.EdgesGeometry(g, 28), new THREE.LineBasicMaterial({ color: 0x1f2733, transparent: true, opacity: 0.7 }));
    if (edges) mesh.add(edges);
    model.add(mesh);
    //  ⚠ 이름 없이 내보낸 파일은 「Open CASCADE STEP translator 7.7 2.1」 같은 프로그램 이름이 붙는다 — 그때는 「부품 n」
    let nm = String(m.name || names[i] || '').trim();
    if (!nm || /translator|^(solid|shape|body|part)?\s*\d*$/i.test(nm)) nm = '부품 ' + (i + 1);
    parts.push({ name: nm, mesh, edges, color });
  });
  scene.add(model);
  box = new THREE.Box3().setFromObject(model);
  applyLook();
  if (!glOk) soft.load(res, parts.map((p) => p.color));
  fit('iso');
  drawParts();
  const s = box.getSize(new THREE.Vector3());
  const f = (v) => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString('ko-KR');
  $('info').innerHTML = '크기 <b>' + f(s.x) + ' × ' + f(s.y) + ' × ' + f(s.z) + '</b> mm'
    + '<br>부품 ' + parts.length + '개 · 삼각형 ' + Math.round(tris).toLocaleString('ko-KR') + '개'
    + (res.head ? '<br><span style="color:#6b7684">포털에서 가볍게 바꿔 둔 미리보기' + (res.head.bytes ? ' (원본 ' + MB(res.head.bytes) + ')' : '') + '</span>' : '')
    + (glOk ? '' : '<br><span style="color:#9a6700">간이 미리보기 — 이 PC 는 그래픽 가속(WebGL)이 꺼져 있습니다</span>');
  document.body.classList.toggle('nogl', !glOk);
  $('tEdge').style.display = noEdge ? 'none' : '';
  $('drop').style.display = 'none';
  $('tools').style.display = 'flex';
}

function applyLook() {
  parts.forEach((p) => {
    if (p.edges) p.edges.visible = edgesOn;
    p.mesh.material.transparent = glass;
    p.mesh.material.opacity = glass ? 0.35 : 1;
    p.mesh.material.depthWrite = !glass;
    p.mesh.material.needsUpdate = true;
  });
  $('tEdge').classList.toggle('on', edgesOn);
  $('tGlass').classList.toggle('on', glass);
}

// ── 보는 방향 ───────────────────────────────────────────────
function fit(dir) {
  if (!box) return;
  if (!glOk) { soft.view(dir); return; }
  const vis = new THREE.Box3();
  parts.forEach((p) => { if (p.mesh.visible) vis.expandByObject(p.mesh); });
  const b = vis.isEmpty() ? box : vis;
  const c = b.getCenter(new THREE.Vector3());
  const r = Math.max(b.getSize(new THREE.Vector3()).length() / 2, 1);
  //  ⚠ 세로로 긴 폰 화면은 **가로 시야가 더 좁다** — 좁은 쪽에 맞춰야 옆이 안 잘린다
  const vf = THREE.MathUtils.degToRad(camera.fov);
  const hf = 2 * Math.atan(Math.tan(vf / 2) * camera.aspect);
  const d = r / Math.sin(Math.min(vf, hf) / 2) * 1.08;
  const D = { iso: [1, -1, 0.8], front: [0, -1, 0], top: [0, 0, 1], side: [1, 0, 0] }[dir || 'iso'];
  const v = new THREE.Vector3(D[0], D[1], D[2]).normalize();
  camera.up.set(0, 0, 1);
  if (dir === 'top') camera.up.set(0, 1, 0);
  camera.position.copy(c).addScaledVector(v, d);
  camera.near = Math.max(d / 1000, 0.01);
  camera.far = d * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(c);
  controls.update();
}

// ── 부품 목록 ───────────────────────────────────────────────
function drawParts() {
  const L = $('plist');
  L.innerHTML = '';
  parts.forEach((p, i) => {
    const lb = document.createElement('label');
    lb.innerHTML = '<input type="checkbox" checked><i style="background:#' + new THREE.Color(p.color).getHexString() + '"></i><span></span>';
    lb.querySelector('span').textContent = p.name;
    lb.querySelector('input').onchange = (e) => { p.mesh.visible = e.target.checked; if (!glOk) soft.draw(); };
    L.appendChild(lb);
  });
  $('tParts').style.display = parts.length > 1 ? '' : 'none';
}

// ── 재기(두 점 사이 거리) ───────────────────────────────────
const marks = new THREE.Group();
scene.add(marks);
let pts = [];
function clearMeasure() {
  marks.children.slice().forEach((o) => { marks.remove(o); if (o.geometry) o.geometry.dispose(); });
  pts = [];
}
const ray = new THREE.Raycaster();
let downAt = null;
if (glOk) renderer.domElement.addEventListener('pointerdown', (e) => { downAt = { x: e.clientX, y: e.clientY }; });
if (glOk) renderer.domElement.addEventListener('pointerup', (e) => {
  if (!measuring || !downAt || !model) return;
  if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 6) return;     //  돌린 것이지 누른 것이 아니다
  const rc = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - rc.left) / rc.width) * 2 - 1, -((e.clientY - rc.top) / rc.height) * 2 + 1), camera);
  const hit = ray.intersectObjects(parts.filter((p) => p.mesh.visible).map((p) => p.mesh), false)[0];
  if (!hit) return;
  if (pts.length >= 2) clearMeasure();
  pts.push(hit.point.clone());
  const r = box.getSize(new THREE.Vector3()).length() / 200;
  const dot = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), new THREE.MeshBasicMaterial({ color: 0xe0484e, depthTest: false }));
  dot.position.copy(hit.point);
  dot.renderOrder = 10;
  marks.add(dot);
  if (pts.length === 2) {
    const ln = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0xe0484e, depthTest: false }));
    ln.renderOrder = 10;
    marks.add(ln);
    const d = pts[0].distanceTo(pts[1]);
    const dx = Math.abs(pts[1].x - pts[0].x), dy = Math.abs(pts[1].y - pts[0].y), dz = Math.abs(pts[1].z - pts[0].z);
    const f = (v) => (Math.round(v * 100) / 100).toLocaleString('ko-KR');
    toast('📏 ' + f(d) + ' mm   (X ' + f(dx) + ' · Y ' + f(dy) + ' · Z ' + f(dz) + ')', 8000);
  } else toast('두 번째 점을 누르세요', 2000);
});

// ── CATIA 원본(.CATPart 등) — 들어 있는 미리보기 그림 ─────────
//   ⚠ CATIA 원본은 다쏘 전용 형식이라 3D 모양을 읽는 공개 엔진이 없다.
//   ⭐ 대신 CATIA 가 저장할 때 파일 안에 넣어 두는 **미리보기 그림**(CATIA 「열기」 창에 보이는 그것)을 꺼내 보인다.
//     JPEG(FF D8 FF … FF D9)·PNG·BMP 를 훑어, **실제로 그림으로 열리는 것 중 가장 큰 것**을 고른다
//     (그냥 FF D8~FF D9 를 자르면 압축 자료 속 우연한 표식에 속는다 — 열어 보고 확인한다).
async function decodeImg(bytes, mime) {
  const blob = new Blob([bytes], { type: mime });
  if (window.createImageBitmap) {
    const bm = await createImageBitmap(blob);
    const r = { w: bm.width, h: bm.height, blob };
    if (bm.close) bm.close();
    return r;
  }
  return await new Promise((ok, no) => {
    const im = new Image(); const u = URL.createObjectURL(blob);
    im.onload = () => { ok({ w: im.naturalWidth, h: im.naturalHeight, blob }); URL.revokeObjectURL(u); };
    im.onerror = () => { no(new Error('bad')); URL.revokeObjectURL(u); };
    im.src = u;
  });
}
//  JPEG 를 표식(FF D8 … 조각 길이 … FF D9) 그대로 따라가 끝을 정확히 찾는다 — 100MB 도 몇 초면 훑는다
//   (viewer3d-convert.js 의 jpegAt·pngAt 와 같은 방법)
function jpegAt(u8, i) {
  const n = u8.length;
  let p = i + 2, w = 0, h = 0, sos = false, segs = 0;
  while (p < n - 3 && segs++ < 400) {
    if (u8[p] !== 0xFF) return null;
    while (u8[p + 1] === 0xFF && p < n - 2) p++;
    const m = u8[p + 1];
    if (m === 0xD9) return (w && h && sos) ? { start: i, end: p + 2, w, h, mime: 'image/jpeg' } : null;
    if ((m >= 0xD0 && m <= 0xD7) || m === 0x01) { p += 2; continue; }
    const len = (u8[p + 2] << 8) | u8[p + 3];
    if (len < 2) return null;
    if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) { h = (u8[p + 5] << 8) | u8[p + 6]; w = (u8[p + 7] << 8) | u8[p + 8]; }
    p += 2 + len;
    if (m === 0xDA) {
      sos = true;
      while (p < n - 1) { if (u8[p] === 0xFF) { const x = u8[p + 1]; if (x !== 0 && !(x >= 0xD0 && x <= 0xD7) && x !== 0xFF) break; } p++; }
    }
  }
  return null;
}
function pngAt(u8, i) {
  const n = u8.length;
  const be = (p) => ((u8[p] << 24) | (u8[p + 1] << 16) | (u8[p + 2] << 8) | u8[p + 3]) >>> 0;
  if (be(i + 12) !== 0x49484452) return null;
  const w = be(i + 16), h = be(i + 20);
  let p = i + 8;
  for (let k = 0; k < 100000 && p < n - 12; k++) {
    const len = be(p), type = be(p + 4);
    if (len > n) return null;
    p += 12 + len;
    if (type === 0x49454E44) return { start: i, end: p, w, h, mime: 'image/png' };
  }
  return null;
}
async function findPreviews(u8) {
  const cand = [];
  const n = u8.length;
  for (let i = 0; i < n - 8; i++) {
    const b = u8[i];
    let r = null;
    if (b === 0xFF && u8[i + 1] === 0xD8 && u8[i + 2] === 0xFF) r = jpegAt(u8, i);
    else if (b === 0x89 && u8[i + 1] === 0x50 && u8[i + 2] === 0x4E && u8[i + 3] === 0x47) r = pngAt(u8, i);
    else if (b === 0x42 && u8[i + 1] === 0x4D && (u8[i + 14] | (u8[i + 15] << 8)) === 40) {          //  BMP
      const size = (u8[i + 2] | (u8[i + 3] << 8) | (u8[i + 4] << 16) | (u8[i + 5] << 24)) >>> 0;
      if (size > 200 && i + size <= n) r = { start: i, end: i + size, w: (u8[i + 18] | (u8[i + 19] << 8)), h: Math.abs((u8[i + 22] | (u8[i + 23] << 8) | (u8[i + 24] << 16) | (u8[i + 25] << 24))), mime: 'image/bmp' };
    }
    if (r && r.w >= 16 && r.h >= 16 && r.w <= 10000 && r.h <= 10000) { cand.push(r); i = r.end - 1; }
  }
  cand.sort((a, b) => b.w * b.h - a.w * a.h);
  //  정말 그림으로 열리는지 확인(큰 것부터)
  for (const r of cand.slice(0, 8)) {
    try { const d = await decodeImg(u8.subarray(r.start, r.end), r.mime); if (d.w > 8 && d.h > 8) return [d]; } catch (x) { /* 다음 */ }
  }
  return [];
}
async function openCatia(u8) {
  busy(true, 'CATIA 파일에서 미리보기 그림을 찾는 중… (' + MB(u8.length) + ')');
  await new Promise((r) => setTimeout(r, 30));
  let list = [];
  try { list = await findPreviews(u8); } catch (e) { list = []; }
  busy(false);
  if (!list.length) {
    fail('이 CATIA 파일에는 미리보기 그림이 없습니다',
      'CATIA 원본은 다쏘 전용 형식이라 3D 모양은 직접 읽을 수 없고, 파일 안의 미리보기 그림만 보여 드립니다. '
      + '이 파일은 미리보기 없이 저장되었습니다. 3D 로 보려면 CATIA 에서 「다른 이름으로 저장 → STEP(.stp)」으로 내보내 열어 주세요.');
    return;
  }
  showImage(list[0].blob, list[0].w, list[0].h);
}
function showImage(blob, w, h) {
  const best = { blob, w, h };
  if (model) { scene.remove(model); model = null; }
  parts = []; box = null; clearMeasure();
  document.body.classList.remove('mode2d');
  document.body.classList.add('modeimg');
  let host = $('vimg');
  if (!host) {
    host = document.createElement('div');
    host.id = 'vimg';
    view.appendChild(host);
  }
  const url = URL.createObjectURL(best.blob);
  host.innerHTML = '<img alt="CATIA 미리보기" src="' + url + '">';
  host.dataset.url = url;
  $('info').innerHTML = '<b>CATIA 원본</b> — 저장할 때 들어간 <b>미리보기 그림</b>입니다 (' + best.w + '×' + best.h + 'px)'
    + '<br><span style="color:#6b7684">3D 로 돌려 보려면 CATIA 에서 STEP(.stp)으로 내보내 주세요</span>';
  $('drop').style.display = 'none';
  $('tools').style.display = 'flex';
}

// ── 2D 도면(DWG·DXF) ────────────────────────────────────────
//   ⭐ LibreDWG 가 도면을 SVG 로 바꾸고, 여기서 맞춤·확대·끌기·재기를 한다.
//   ⚠ 바꾼 SVG 를 그대로 쓰면 안 된다: ① 멀리 떨어진 선 하나(보조선 등)가 범위를 수백만으로 늘려 도면이 점이 되고
//     ② 선 굵기를 그 범위의 %로 정해 선이 화면을 덮는다 → 굵기는 화면 1px 로 고정, 범위는 동떨어진 것을 빼고 잡는다.
const v2d = $('v2d');
let svg2 = null, vb = null, ext2 = null, white = false;
function loadDwgEngine() {
  if (window.HanilDwg) return Promise.resolve();
  return new Promise((ok, no) => {
    const sc = document.createElement('script');
    sc.src = (window.HANIL_DWG_BASE || '') + 'dwg.js';
    sc.onload = ok;
    sc.onerror = () => no(new Error('도면 엔진(dwg.js)을 불러오지 못했습니다'));
    document.head.appendChild(sc);
  });
}
async function open2d(u8, kind) {
  document.body.classList.remove('modeimg');
  busy(true, '도면 엔진을 준비하는 중…');
  await new Promise((r) => setTimeout(r, 30));
  try {
    await loadDwgEngine();
    busy(true, '도면을 읽는 중…');
    await new Promise((r) => setTimeout(r, 30));
    window.__dwgSkip = 0; globalThis.__dwgSkip = 0;
    const t0 = performance.now();
    const r = await window.HanilDwg.toSvg(u8, kind);
    console.log('[2D] ' + fileName + ' ' + Math.round(performance.now() - t0) + 'ms');
    render2d(r);
  } catch (e) {
    fail('도면(DWG·DXF)을 열지 못했습니다', (e && e.message || e));
  }
  busy(false);
}
function render2d(r) {
  if (model) { scene.remove(model); model = null; }
  parts = []; box = null; clearMeasure();
  document.body.classList.add('mode2d');
  v2d.innerHTML = String(r.svg).replace(/^<\?xml[^>]*>/, '');
  svg2 = v2d.querySelector('svg');
  svg2.removeAttribute('width'); svg2.removeAttribute('height');
  svg2.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  const root = svg2.querySelector(':scope > g');
  if (root) root.setAttribute('stroke-width', '1');
  //  범위 — 요소마다 상자를 재고, 한가운데 무리에서 동떨어진 것(보조선·먼 점)은 뺀다
  const ms = root && root.querySelector(':scope > g');
  const items = ms ? [].slice.call(ms.children) : [];
  const boxes = [];
  items.forEach((e) => {
    try {
      const b = e.getBBox();
      if (!isFinite(b.x) || !isFinite(b.width) || (b.width === 0 && b.height === 0)) return;
      boxes.push({ x: b.x, y: -(b.y + b.height), w: b.width, h: b.height });   //  위아래 뒤집힘(matrix 1,0,0,-1)
    } catch (x) { /* */ }
  });
  ext2 = robustExtent(boxes) || { x: 0, y: 0, w: 100, h: 100 };
  white = false; v2d.classList.remove('white');
  fit2d();
  const f = (v) => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString('ko-KR');
  const skip = window.__dwgSkip || globalThis.__dwgSkip || 0;
  $('info').innerHTML = '범위 <b>' + f(ext2.w) + ' × ' + f(ext2.h) + '</b> (도면 단위)'
    + '<br>요소 ' + items.length.toLocaleString('ko-KR') + '개'
    + (skip ? ' · <span style="color:#b3261e">그리지 못한 것 ' + skip + '개</span>' : '');
  $('drop').style.display = 'none';
  $('tools').style.display = 'flex';
}
function robustExtent(bs) {
  if (!bs.length) return null;
  const q = (arr, p) => arr[Math.min(arr.length - 1, Math.max(0, Math.floor(p * (arr.length - 1))))];
  const cx = bs.map((b) => b.x + b.w / 2).sort((a, b) => a - b);
  const cy = bs.map((b) => b.y + b.h / 2).sort((a, b) => a - b);
  const x1 = q(cx, 0.05), x2 = q(cx, 0.95), y1 = q(cy, 0.05), y2 = q(cy, 0.95);
  const rx = Math.max(x2 - x1, 1), ry = Math.max(y2 - y1, 1), R = Math.max(rx, ry);
  let X1 = Infinity, Y1 = Infinity, X2 = -Infinity, Y2 = -Infinity;
  bs.forEach((b) => {
    const c1 = b.x + b.w / 2, c2 = b.y + b.h / 2;
    if (c1 < x1 - R || c1 > x2 + R || c2 < y1 - R || c2 > y2 + R) return;     //  무리에서 동떨어진 것
    if (b.w > R * 6 || b.h > R * 6) return;                                     //  끝없이 긴 보조선
    X1 = Math.min(X1, b.x); Y1 = Math.min(Y1, b.y); X2 = Math.max(X2, b.x + b.w); Y2 = Math.max(Y2, b.y + b.h);
  });
  if (!isFinite(X1)) return null;
  return { x: X1, y: Y1, w: Math.max(X2 - X1, 1e-6), h: Math.max(Y2 - Y1, 1e-6) };
}
//  화면 비율에 맞춘 보기 상자(SVG 좌표 — y 는 아래로)
function setVB(n) {
  const cw = v2d.clientWidth || 1, ch = v2d.clientHeight || 1, a = cw / ch;
  if (n.w / n.h > a) { const h = n.w / a; n.y -= (h - n.h) / 2; n.h = h; } else { const w = n.h * a; n.x -= (w - n.w) / 2; n.w = w; }
  vb = n;
  svg2.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.w + ' ' + vb.h);
  redrawMarks2d();
}
function fit2d() {
  if (!svg2 || !ext2) return;
  const m = Math.max(ext2.w, ext2.h) * 0.04;
  //  도면 좌표(y 위로) → SVG 좌표(y 아래로)
  setVB({ x: ext2.x - m, y: -(ext2.y + ext2.h) - m, w: ext2.w + 2 * m, h: ext2.h + 2 * m });
}
function zoom2d(k, sx, sy) {
  if (!vb) return;
  const cw = v2d.clientWidth, ch = v2d.clientHeight;
  if (sx == null) { sx = cw / 2; sy = ch / 2; }
  const ux = vb.x + sx / cw * vb.w, uy = vb.y + sy / ch * vb.h;
  setVB({ x: ux - (ux - vb.x) * k, y: uy - (uy - vb.y) * k, w: vb.w * k, h: vb.h * k });
}
const ptrs = new Map();
let pinch = null, moved2 = false;
v2d.addEventListener('pointerdown', (e) => {
  v2d.setPointerCapture(e.pointerId);
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
  moved2 = false;
  if (ptrs.size === 2) {
    const [a, b] = [...ptrs.values()];
    pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) };
  }
});
v2d.addEventListener('pointermove', (e) => {
  const p = ptrs.get(e.pointerId);
  if (!p || !vb) return;
  const rc = v2d.getBoundingClientRect();
  if (ptrs.size === 1) {
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    if (Math.hypot(e.clientX - p.x0, e.clientY - p.y0) > 5) moved2 = true;
    setVB({ x: vb.x - dx / rc.width * vb.w, y: vb.y - dy / rc.height * vb.h, w: vb.w, h: vb.h });
  }
  p.x = e.clientX; p.y = e.clientY;
  if (ptrs.size === 2 && pinch) {
    moved2 = true;
    const [a, b] = [...ptrs.values()];
    const d = Math.hypot(a.x - b.x, a.y - b.y);
    if (d > 0 && pinch.d > 0) zoom2d(pinch.d / d, (a.x + b.x) / 2 - rc.left, (a.y + b.y) / 2 - rc.top);
    pinch.d = d;
  }
});
function ptrEnd(e) {
  const p = ptrs.get(e.pointerId);
  ptrs.delete(e.pointerId);
  if (ptrs.size < 2) pinch = null;
  if (p && measuring && !moved2 && vb && ptrs.size === 0) {
    const rc = v2d.getBoundingClientRect();
    const ux = vb.x + (e.clientX - rc.left) / rc.width * vb.w, uy = vb.y + (e.clientY - rc.top) / rc.height * vb.h;
    if (pts2.length >= 2) pts2 = [];
    pts2.push({ x: ux, y: uy });
    redrawMarks2d();
    if (pts2.length === 2) {
      const dx = Math.abs(pts2[1].x - pts2[0].x), dy = Math.abs(pts2[1].y - pts2[0].y);
      const f = (v) => (Math.round(v * 100) / 100).toLocaleString('ko-KR');
      toast('📏 ' + f(Math.hypot(dx, dy)) + '   (가로 ' + f(dx) + ' · 세로 ' + f(dy) + ')  — 도면 단위', 8000);
    } else toast('두 번째 점을 누르세요', 2000);
  }
}
v2d.addEventListener('pointerup', ptrEnd);
v2d.addEventListener('pointercancel', ptrEnd);
v2d.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rc = v2d.getBoundingClientRect();
  zoom2d(e.deltaY > 0 ? 1.18 : 1 / 1.18, e.clientX - rc.left, e.clientY - rc.top);
}, { passive: false });
let pts2 = [];
function redrawMarks2d() {
  if (!svg2) return;
  let g = svg2.querySelector('#__hm2');
  if (!g) { g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.id = '__hm2'; svg2.appendChild(g); }
  const r = vb ? vb.w / 160 : 1;
  g.innerHTML = pts2.map((p) => '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + r + '" fill="#e0484e" stroke="none"/>').join('')
    + (pts2.length === 2 ? '<line x1="' + pts2[0].x + '" y1="' + pts2[0].y + '" x2="' + pts2[1].x + '" y2="' + pts2[1].y + '" stroke="#e0484e" stroke-width="2"/>' : '');
}
window.addEventListener('resize', () => { if (vb && document.body.classList.contains('mode2d')) setVB({ ...vb }); });
function shot2d() {
  if (!svg2) return;
  const cw = v2d.clientWidth, ch = v2d.clientHeight, k = 2;
  const clone = svg2.cloneNode(true);
  clone.setAttribute('width', cw * k); clone.setAttribute('height', ch * k);
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('x', vb.x); bg.setAttribute('y', vb.y); bg.setAttribute('width', vb.w); bg.setAttribute('height', vb.h);
  bg.setAttribute('fill', white ? '#ffffff' : '#1e232b');
  clone.insertBefore(bg, clone.firstChild);
  const st = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  st.textContent = '*{vector-effect:non-scaling-stroke}' + (white ? WHITE_CSS : '');
  clone.insertBefore(st, clone.firstChild);
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(clone));
  const img = new Image();
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = cw * k; c.height = ch * k;
    c.getContext('2d').drawImage(img, 0, 0);
    saveFile(fileName.replace(/\.[^.]+$/, '') + '_도면.png', 'image/png', c.toDataURL('image/png'));
  };
  img.src = url;
}
//  흰 바탕 — 검은 바탕용 색(흰·노랑·하늘)을 흰 바탕에서도 보이게
const WHITE_CSS = '[stroke="rgb(255,255,255)"]{stroke:#111}[fill="rgb(255,255,255)"]{fill:#111}'
  + '[stroke="rgb(255,255,0)"]{stroke:#9a7d00}[fill="rgb(255,255,0)"]{fill:#9a7d00}'
  + '[stroke="rgb(0,255,255)"]{stroke:#007f8c}[fill="rgb(0,255,255)"]{fill:#007f8c}';
(function () { const st = document.createElement('style'); st.textContent = WHITE_CSS.replace(/\[/g, '#v2d.white [').replace(/\}#v2d/g, '}#v2d'); document.head.appendChild(st); })();

// ── 단추 ────────────────────────────────────────────────────
$('tFit').onclick = () => (document.body.classList.contains('mode2d') ? fit2d() : fit('iso'));
$('tIn').onclick = () => zoom2d(1 / 1.4);
$('tOut').onclick = () => zoom2d(1.4);
$('tBg').onclick = () => { white = !white; v2d.classList.toggle('white', white); $('tBg').classList.toggle('on', white); };
$('tIso').onclick = () => fit('iso');
$('tFront').onclick = () => fit('front');
$('tTop').onclick = () => fit('top');
$('tSide').onclick = () => fit('side');
$('tEdge').onclick = () => { edgesOn = !edgesOn; applyLook(); };
$('tGlass').onclick = () => { glass = !glass; applyLook(); };
$('tMeasure').onclick = () => {
  measuring = !measuring;
  $('tMeasure').classList.toggle('on', measuring);
  if (measuring) toast('잴 곳 두 점을 차례로 누르세요', 3000); else { clearMeasure(); pts2 = []; redrawMarks2d(); }
};
$('tParts').onclick = () => $('parts').classList.toggle('on');
$('pX').onclick = () => $('parts').classList.remove('on');
$('pAll').onclick = () => { parts.forEach((p) => { p.mesh.visible = true; }); [].forEach.call($('plist').querySelectorAll('input'), (c) => { c.checked = true; }); if (!glOk) soft.draw(); };

function saveFile(name, mime, dataUrlOrBytes) {
  //  앱 안이면 앱이 다운로드 폴더에 저장한다(HanilApp.saveBase64)
  const b64 = typeof dataUrlOrBytes === 'string' ? dataUrlOrBytes.split(',')[1] : bytesToB64(dataUrlOrBytes);
  if (window.HanilApp && window.HanilApp.saveBase64) { window.HanilApp.saveBase64(name, mime, b64); return; }
  const a = document.createElement('a');
  a.href = typeof dataUrlOrBytes === 'string' ? dataUrlOrBytes : URL.createObjectURL(new Blob([dataUrlOrBytes], { type: mime }));
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
function bytesToB64(u8) {
  let s = '';
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
}
$('tShot').onclick = () => {
  if (document.body.classList.contains('mode2d')) { shot2d(); return; }
  if (document.body.classList.contains('modeimg')) {
    const im = document.querySelector('#vimg img');
    if (im) { const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight; c.getContext('2d').drawImage(im, 0, 0);
      saveFile(fileName.replace(/\.[^.]+$/, '') + '_미리보기.png', 'image/png', c.toDataURL('image/png')); }
    return;
  }
  if (!glOk) { saveFile(fileName.replace(/\.[^.]+$/, '') + '_3D.png', 'image/png', soft.cv.toDataURL('image/png')); return; }
  renderer.render(scene, camera);
  saveFile(fileName.replace(/\.[^.]+$/, '') + '_3D.png', 'image/png', renderer.domElement.toDataURL('image/png'));
};
$('bSave').onclick = () => { if (fileBytes) saveFile(fileName, 'application/octet-stream', fileBytes); };
if (window.HanilApp && window.HanilApp.saveBase64) $('bSave').style.display = '';

// ── 파일 받기: 고르기 · 끌어다 놓기 · 주소(?src=) ─────────────
function fromInput(inp) {
  const f = inp.files && inp.files[0];
  if (!f) return;
  f.arrayBuffer().then((b) => openBytes(f.name, new Uint8Array(b)));
  inp.value = '';
}
$('file').onchange = function () { fromInput(this); };
$('file2').onchange = function () { fromInput(this); };
['dragenter', 'dragover'].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); document.body.classList.add('drag'); }));
['dragleave', 'drop'].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); document.body.classList.remove('drag'); }));
document.addEventListener('drop', (e) => {
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (f) f.arrayBuffer().then((b) => openBytes(f.name, new Uint8Array(b)));
});

//  폰·약한 기기 — 직접 읽을 크기를 작게 잡는다
function isSmall() { return /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent) || (navigator.deviceMemory && navigator.deviceMemory <= 4); }

//  받으면서 「n MB / 전체」를 보인다
async function download(url, label) {
  const r = await fetch(url, { credentials: 'same-origin' });
  const ct = r.headers.get('content-type') || '';
  if (!r.ok) throw new Error('서버가 ' + r.status + ' 로 답했습니다' + (r.status === 401 || r.status === 403 ? ' — 로그인·권한을 확인하세요' : r.status === 404 ? ' — 파일 주소가 틀렸거나 지워진 파일' : '') + '\n주소: ' + url);
  const total = +(r.headers.get('content-length') || 0);
  let b;
  if (r.body && r.body.getReader) {
    const rd = r.body.getReader(), chunks = [];
    let got = 0, last = 0;
    for (;;) {
      const { done, value } = await rd.read();
      if (done) break;
      chunks.push(value); got += value.length;
      if (Date.now() - last > 250) { last = Date.now(); busy(true, label + '\n' + MB(got) + (total && !r.headers.get('content-encoding') ? ' / ' + MB(total) : '')); }
    }
    b = new Uint8Array(got);
    let o = 0;
    for (const c of chunks) { b.set(c, o); o += c.length; }
  } else b = new Uint8Array(await r.arrayBuffer());
  return { b, ct };
}

//  ?src= 로 열기 — 포털이면 먼저 **포털 변환기**에 묻는다(큰 3D·CATIA 는 서버가 가볍게 바꿔 둔다)
async function fromSrc(src, name) {
  try {
    if (/^https?:$/.test(location.protocol) && /^\/viewer3d\//.test(location.pathname) && /^\/(?!\/)/.test(src)) {
      const done = await viaConverter(src, name);
      if (done) return;
    }
    busy(true, '파일을 받는 중…');
    const { b, ct } = await download(src, '파일을 받는 중…');
    //  ⚠ 도면 대신 화면(HTML)이 오면 — 로그인 화면·오류 화면·다른 미리보기 화면의 주소를 준 것
    const head = new TextDecoder('latin1').decode(b.slice(0, 200)).trim().toLowerCase();
    if (/text\/html/.test(ct) && (head.startsWith('<!doctype') || head.startsWith('<html') || head.indexOf('<head') >= 0)) {
      throw new Error('파일 대신 화면(HTML)이 왔습니다 — 로그인 화면이거나, 내려받기 주소가 아니라 다른 화면 주소입니다.\n주소: ' + src + '\n(첨부를 「내려받는」 주소를 src 에 주세요)');
    }
    if (!b.length) throw new Error('빈 파일이 왔습니다\n주소: ' + src);
    await openBytes(name, b);
  } catch (e) { fail('파일을 받지 못했습니다', e.message); }
}
const PHASE = { wait: '차례를 기다리는 중', start: '변환을 시작하는 중', engine: '3D 엔진을 준비하는 중', read: '모양을 읽고 깎는 중', pack: '가볍게 묶는 중', scan: '미리보기 그림을 찾는 중',
  nread: '모양을 읽는 중', nmesh: '삼각형으로 깎는 중', nwrite: '부품별로 나누는 중' };
//  true: 다 했음 · false: 변환기 없음/작은 파일 → 직접 받아 연다
async function viaConverter(src, name) {
  busy(true, '포털에 묻는 중…');
  let st;
  try {
    const r = await fetch('/viewer3d/api/prep?src=' + encodeURIComponent(src) + '&name=' + encodeURIComponent(name) + (isSmall() ? '&small=1' : ''), { credentials: 'same-origin' });
    if (r.status === 404 || !/json/.test(r.headers.get('content-type') || '')) return false;      //  변환기 없는 포털(옛 판)
    st = await r.json();
  } catch (e) { return false; }
  if (st.state === 'raw') return false;
  fileName = name;
  $('fname').textContent = name;
  document.title = name + ' — 도면 보기';
  while (st.state === 'work') {
    const ph = PHASE[st.phase] || '변환하는 중';
    busy(true, '포털 서버가 가볍게 바꾸는 중 — 처음 한 번만 걸립니다\n' + ph + (st.wait > 1 ? ' (앞에 ' + (st.wait - 1) + '개)' : '')
      + '\n' + clock(st.sec || 0) + (st.est ? ' / 어림 ' + clock(st.est) : '') + (st.mb ? ' · 원본 ' + st.mb + 'MB' : '')
      + '\n(창을 닫아도 서버는 계속 바꿉니다 — 나중에 다시 열면 바로 보입니다)');
    await new Promise((ok) => setTimeout(ok, 2000));
    try { st = await (await fetch('/viewer3d/api/job/' + st.key, { credentials: 'same-origin', cache: 'no-store' })).json(); } catch (e) { /* 다시 */ }
  }
  if (st.state === 'gone') { const again = await viaConverter(src, name); return again; }
  if (st.state === 'fail') {
    if (/CATIA|미리보기 그림/.test(st.msg || '')) { fail('이 CATIA 파일에는 미리보기 그림이 없습니다', st.msg); return true; }
    fail('포털에서 변환하지 못했습니다', st.msg || '');
    return true;
  }
  //  done
  const { b } = await download(st.out, st.type === 'image' ? '미리보기 그림을 받는 중…' : '가볍게 바꾼 미리보기를 받는 중…');
  fileBytes = null;
  $('bSave').style.display = 'none';
  if (st.type === 'image') {
    showImage(new Blob([b], { type: st.mime || 'image/jpeg' }), st.w, st.h);
    busy(false);
    return true;
  }
  busy(true, '그리는 중…');
  await new Promise((r) => setTimeout(r, 30));
  document.body.classList.remove('modeimg', 'mode2d');
  build(loadHM3(b.buffer));
  busy(false);
  return true;
}

const q = new URLSearchParams(location.search);
if (q.get('src')) {
  const name = q.get('name') || decodeURIComponent(q.get('src').split('/').pop().split('?')[0]);
  fromSrc(q.get('src'), name);
} else if (q.get('check')) {
  selfCheck();
} else {
  occtWarm().catch(() => {});            //  고르는 동안 엔진을 미리 데워 둔다
}

//  🩺 점검 — /viewer3d/view?check=1 : 이 PC·브라우저에서 무엇이 되고 안 되는지 한 화면에
async function selfCheck() {
  const rows = [];
  const show = () => {
    const d = $('drop');
    d.style.display = 'flex';
    d.querySelector('.card').innerHTML = '<b>🩺 도면 보기 점검</b><div style="text-align:left;font-size:14px;line-height:1.9;margin-top:10px">'
      + rows.map((r) => (r[1] === true ? '✅ ' : r[1] === false ? '❌ ' : r[1] === 'warn' ? '⚠️ ' : r[1] === 'info' ? 'ℹ️ ' : '⏳ ') + esc0(r[0]) + (r[2] ? ' <span style="color:#6b7684">— ' + esc0(r[2]) + '</span>' : '')).join('<br>') + '</div>';
  };
  rows.push(['그래픽 가속(WebGL)', glOk ? true : 'warn', glOk ? '3D 를 부드럽게 돌립니다' : '꺼짐 → 간이 미리보기로 보입니다 (' + glWhy + ')']);
  rows.push(['WebAssembly', typeof WebAssembly === 'object', typeof WebAssembly === 'object' ? '' : '브라우저를 새것(크롬·엣지)으로']);
  show();
  let t0 = performance.now();
  try { await occtWarm(); rows.push(['3D 엔진(occt-import-js.wasm)', true, Math.round(performance.now() - t0) + 'ms']); } catch (e) { rows.push(['3D 엔진(occt-import-js.wasm)', false, e.message]); }
  show();
  t0 = performance.now();
  try { await loadDwgEngine(); rows.push(['2D 엔진(dwg.js)', true, Math.round(performance.now() - t0) + 'ms']); } catch (e) { rows.push(['2D 엔진(dwg.js)', false, e.message]); }
  show();
  try {
    const r = await parse3d('step', new TextEncoder().encode(SAMPLE_STEP));
    rows.push(['예시 STEP 읽기', !!(r && r.success && r.meshes.length), r && r.meshes ? ('삼각형 ' + r.meshes.reduce((n, m) => n + m.index.array.length / 3, 0) + '개') : '']);
  } catch (e) { rows.push(['예시 STEP 읽기', false, e.message]); }
  show();
  if (/^\/viewer3d\//.test(location.pathname)) {
    try {
      const r = await fetch('/viewer3d/api/ping', { credentials: 'same-origin' });
      const j = r.ok ? await r.json() : null;
      rows.push(['포털 변환기(큰 도면)', j ? (j.native ? true : 'warn') : 'warn',
        !j ? 'viewer3d-route.js 가 옛 판 — 큰 파일은 브라우저가 직접 읽습니다'
          : j.native ? '서버 OpenCASCADE 로 빠르게 바꿉니다(100MB 급 1~2분)'
            : '서버에 OpenCASCADE 가 없어 느린 엔진으로 바꿉니다 — sudo apt install -y occt-draw libocct-draw-dev']);
    } catch (e) { rows.push(['포털 변환기(큰 도면)', 'warn', e.message]); }
    show();
  }
  rows.push(['', 'info', '❌ 가 없으면 이 PC 에서 도면 보기가 됩니다(⚠️ 는 간이 미리보기로 대신). ❌ 가 있으면 이 화면을 찍어 보내 주세요.']);
  show();
}
window.__hanil3d = { openBytes };
