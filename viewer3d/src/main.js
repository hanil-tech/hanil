//  🧊 한일특장 3D 도면 보기 — STEP(.stp/.step) · IGES(.igs/.iges) · BREP
//   ⭐ 브라우저 안에서 다 한다: OpenCASCADE(occt-import-js, WASM)가 곡면을 삼각형으로 깎고 three.js 가 그린다.
//      서버에 아무것도 안 깔아도 되고, 파일이 이 기기 밖으로 나가지 않는다.
//   ⚠ CATIA 원본(.CATPart·.CATProduct)은 열 수 없다(다쏘 독점 형식) — CATIA 에서 STEP 으로 내보내 연다.
//   쓰는 곳 두 군데(같은 코드):
//     · 폰 앱 안 — 앱이 첨부(.stp)를 받아 ?src= 로 넘긴다
//     · PC 단독 HTML 한 장 — 끌어다 놓기·파일 고르기 (WASM 을 글자로 품고 있어 인터넷 없이도 열린다)
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { SAMPLE_STEP } from './sample.js';

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
    res.meshes.forEach((m, i) => {
      const P = m.attributes.position.array, I = m.index ? m.index.array : null;
      const n = I ? I.length : P.length / 3;
      const col = new THREE.Color(colors[i]);
      for (let k = 0; k < n; k += 3) {
        const a = (I ? I[k] : k) * 3, bb = (I ? I[k + 1] : k + 1) * 3, cc = (I ? I[k + 2] : k + 2) * 3;
        T.push([P[a], P[a + 1], P[a + 2], P[bb], P[bb + 1], P[bb + 2], P[cc], P[cc + 1], P[cc + 2], col.r, col.g, col.b, i]);
      }
      for (let k = 0; k < P.length; k += 3) b.expandByPoint(new THREE.Vector3(P[k], P[k + 1], P[k + 2]));
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

// ── OpenCASCADE 불러오기(한 번만) ───────────────────────────
let occtP = null;
function occt() {
  if (occtP) return occtP;
  if (typeof window.occtimportjs !== 'function') return Promise.reject(new Error('3D 엔진(occt-import-js)이 없습니다'));
  const opt = {};
  if (window.OCCT_WASM_B64) {
    //  PC 단독판 — 엔진을 글자(base64)로 품고 있다(file:// 에서는 따로 받아올 수 없다)
    const bin = atob(window.OCCT_WASM_B64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    opt.wasmBinary = u8;
    window.OCCT_WASM_B64 = null;
  } else {
    opt.locateFile = (f) => f;            //  앱 — 같은 자리의 occt-import-js.wasm
  }
  occtP = window.occtimportjs(opt);
  return occtP;
}

// ── 파일 읽기 ───────────────────────────────────────────────
function kindOf(name, u8) {
  const ext = String(name || '').split('.').pop().toLowerCase();
  if (ext === 'stp' || ext === 'step') return 'step';
  if (ext === 'igs' || ext === 'iges') return 'iges';
  if (ext === 'brep' || ext === 'brp') return 'brep';
  if (ext === 'dwg') return 'dwg';
  if (ext === 'dxf') return 'dxf';
  //  이름으로 모르면 앞머리를 본다
  const head = new TextDecoder('latin1').decode(u8.slice(0, 400));
  if (/ISO-10303-21/.test(head)) return 'step';
  if (/^.{72}S\s*1\s*$/m.test(head)) return 'iges';
  if (/^AC10\d\d/.test(head)) return 'dwg';
  if (/^\s*0\s*[\r\n]+\s*SECTION/.test(head)) return 'dxf';
  return '';
}

async function openBytes(name, u8) {
  const kind = kindOf(name, u8);
  if (!kind) {
    if (/\.catpart$|\.catproduct$/i.test(name)) toast('CATIA 원본 파일은 열 수 없습니다 — CATIA 에서 STEP(.stp)으로 내보내 주세요', 6000);
    else toast('STEP(.stp)·IGES(.igs)·DWG·DXF 파일만 열 수 있습니다', 4000);
    return;
  }
  fileBytes = u8;
  fileName = name || ('model.' + kind);
  $('fname').textContent = fileName;
  document.title = fileName + ' — 도면 보기';
  if (kind === 'dwg' || kind === 'dxf') { await open2d(u8, kind); return; }
  document.body.classList.remove('mode2d');
  busy(true, '3D 엔진을 준비하는 중…');
  await new Promise((r) => setTimeout(r, 30));            //  글자가 먼저 보이게
  try {
    const oc = await occt();
    busy(true, '모양을 읽는 중… (큰 파일은 시간이 걸립니다)');
    await new Promise((r) => setTimeout(r, 30));
    const t0 = performance.now();
    const params = { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.001, angularDeflection: 0.5 };
    const res = kind === 'step' ? oc.ReadStepFile(u8, params)
      : kind === 'iges' ? oc.ReadIgesFile(u8, params) : oc.ReadBrepFile(u8, params);
    if (!res || !res.success || !res.meshes || !res.meshes.length) throw new Error('모양을 찾지 못했습니다(파일이 깨졌거나 빈 파일)');
    build(res);
    const ms = Math.round(performance.now() - t0);
    console.log('[3D] ' + fileName + ' ' + ms + 'ms');
  } catch (e) {
    fail('도면을 열지 못했습니다', (e && e.message || e));
  }
  busy(false);
}

//  ⚠ 못 열었으면 **까닭을 화면 가운데 남긴다**(잠깐 뜨고 사라지는 알림만으로는 무엇이 틀렸는지 모른다)
function fail(title, detail) {
  busy(false);
  const d = $('drop');
  d.style.display = 'flex';
  d.querySelector('.card').innerHTML = '<b style="color:#b3261e">⚠ ' + esc0(title) + '</b>'
    + '<p style="text-align:left;word-break:break-all">' + esc0(detail) + '</p>'
    + '<p style="font-size:12.5px">이 PC: 그래픽 가속 ' + (glOk ? '켜짐' : '꺼짐(간이 미리보기)') + ' · WebAssembly ' + (typeof WebAssembly === 'object' ? '됨' : '<b>안 됨 — 브라우저가 너무 옛것</b>') + '</p>'
    + '<label>📂 다른 파일 고르기<input id="file3" type="file" accept=".stp,.step,.igs,.iges,.brep,.dwg,.dxf"></label>';
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
  res.meshes.forEach((m, i) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(m.attributes.position.array, 3));
    if (m.attributes.normal) g.setAttribute('normal', new THREE.Float32BufferAttribute(m.attributes.normal.array, 3));
    if (m.index) g.setIndex(new THREE.Uint32BufferAttribute(Uint32Array.from(m.index.array), 1));
    if (!m.attributes.normal) g.computeVertexNormals();
    tris += (m.index ? m.index.array.length : m.attributes.position.array.length / 3) / 3;
    let color = many ? PALETTE[i % PALETTE.length] : 0xb4c3d8;
    if (m.color && m.color.length === 3) color = new THREE.Color(m.color[0], m.color[1], m.color[2]).getHex();
    const mat = new THREE.MeshStandardMaterial({ color, metalness: 0.1, roughness: 0.45, side: THREE.DoubleSide,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const mesh = new THREE.Mesh(g, mat);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 28), new THREE.LineBasicMaterial({ color: 0x1f2733, transparent: true, opacity: 0.7 }));
    mesh.add(edges);
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
    + (glOk ? '' : '<br><span style="color:#9a6700">간이 미리보기 — 이 PC 는 그래픽 가속(WebGL)이 꺼져 있습니다</span>');
  document.body.classList.toggle('nogl', !glOk);
  $('drop').style.display = 'none';
  $('tools').style.display = 'flex';
}

function applyLook() {
  parts.forEach((p) => {
    p.edges.visible = edgesOn;
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

const q = new URLSearchParams(location.search);
if (q.get('src')) {
  const name = q.get('name') || decodeURIComponent(q.get('src').split('/').pop().split('?')[0]);
  busy(true, '파일을 받는 중…');
  const src = q.get('src');
  fetch(src, { credentials: 'same-origin' }).then(async (r) => {
    const ct = r.headers.get('content-type') || '';
    if (!r.ok) throw new Error('서버가 ' + r.status + ' 로 답했습니다' + (r.status === 401 || r.status === 403 ? ' — 로그인·권한을 확인하세요' : r.status === 404 ? ' — 파일 주소가 틀렸거나 지워진 파일' : '') + '\n주소: ' + src);
    const b = new Uint8Array(await r.arrayBuffer());
    //  ⚠ 도면 대신 화면(HTML)이 오면 — 로그인 화면·오류 화면·다른 미리보기 화면의 주소를 준 것
    const head = new TextDecoder('latin1').decode(b.slice(0, 200)).trim().toLowerCase();
    if (/text\/html/.test(ct) && (head.startsWith('<!doctype') || head.startsWith('<html') || head.indexOf('<head') >= 0)) {
      throw new Error('파일 대신 화면(HTML)이 왔습니다 — 로그인 화면이거나, 내려받기 주소가 아니라 다른 화면 주소입니다.\n주소: ' + src + '\n(첨부를 「내려받는」 주소를 src 에 주세요)');
    }
    if (!b.length) throw new Error('빈 파일이 왔습니다\n주소: ' + src);
    return b;
  }).then((b) => openBytes(name, b))
    .catch((e) => fail('파일을 받지 못했습니다', e.message));
} else if (q.get('check')) {
  selfCheck();
} else {
  occt().catch(() => {});            //  고르는 동안 엔진을 미리 데워 둔다
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
  try { await occt(); rows.push(['3D 엔진(occt-import-js.wasm)', true, Math.round(performance.now() - t0) + 'ms']); } catch (e) { rows.push(['3D 엔진(occt-import-js.wasm)', false, e.message]); }
  show();
  t0 = performance.now();
  try { await loadDwgEngine(); rows.push(['2D 엔진(dwg.js)', true, Math.round(performance.now() - t0) + 'ms']); } catch (e) { rows.push(['2D 엔진(dwg.js)', false, e.message]); }
  show();
  try {
    const oc = await occt();
    const r = oc.ReadStepFile(new TextEncoder().encode(SAMPLE_STEP), null);
    rows.push(['예시 STEP 읽기', !!(r && r.success && r.meshes.length), r && r.meshes ? ('삼각형 ' + r.meshes.reduce((n, m) => n + m.index.array.length / 3, 0) + '개') : '']);
  } catch (e) { rows.push(['예시 STEP 읽기', false, e.message]); }
  show();
  rows.push(['', 'info', '❌ 가 없으면 이 PC 에서 도면 보기가 됩니다(⚠️ 는 간이 미리보기로 대신). ❌ 가 있으면 이 화면을 찍어 보내 주세요.']);
  show();
}
window.__hanil3d = { openBytes };
