//  🧊 도면 보기 — 포털 변환기 (viewer3d-route.js 가 따로 띄우는 일꾼)
//   ⭐ 큰 도면(100MB 급 STEP·IGES)은 폰·PC 브라우저가 직접 읽기에 너무 무겁다(몇 분 + 메모리 수 GB).
//     그래서 포털 서버가 **한 번만** 가벼운 미리보기(삼각형 묶음, .hm3)로 바꿔 두고, 다음부터는 그것만 내준다.
//   ⭐ CATIA 원본(.CATPart 등)은 파일 안의 미리보기 그림만 꺼낸다 — 100MB 를 폰으로 받을 필요가 없다.
//   ⭐⭐ 엔진 두 가지 — 있으면 빠른 것부터:
//     ① 서버의 OpenCASCADE(occt-draw, 우분투: sudo apt install -y occt-draw libocct-draw-dev) — **빠르다**.
//        조립품 나무(이름·색)를 안 읽고 모양만 읽어서다. 시험: 110MB STEP(부품 7,500개) 77초 · 12MB(1,600개) 9초.
//     ② 없으면 public/viewer3d/occt-import-js.js(.wasm) — 설치가 필요 없지만 **부품 수의 제곱으로 느려진다**
//        (조립품 나무를 읽는 OpenCASCADE XCAF 단계 탓 — 12MB(1,600개) 60초, 33MB 3분, 100MB 는 30분 넘음).
//     ⚠ 그래서 100MB 급은 ① 을 깔아야 제대로 된다. 깔렸는지는 /viewer3d/view?check=1 에 나온다.
//   ⚠ 따로 띄운 프로세스에서 돈다: 엔진이 메모리 부족 등으로 죽어도 포털은 멀쩡하다.
//   쓰는 법(직접 시험):  node viewer3d-convert.js <입력파일> <종류 step|iges|brep|catia> <출력 앞이름>
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

//  ── CATIA 미리보기 그림 찾기 ─────────────────────────────────
//   JPEG 를 표식(FF D8 … 조각 길이 … FF D9) 그대로 따라가 끝을 정확히 찾는다 — 압축 자료 속 우연한 FF D8 에 안 속는다.
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
    if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
      h = (u8[p + 5] << 8) | u8[p + 6];
      w = (u8[p + 7] << 8) | u8[p + 8];
    }
    p += 2 + len;
    if (m === 0xDA) {                        //  그림 자료 — 다음 표식(FF 00·FF Dn 은 자료 안의 것)까지 건너뛴다
      sos = true;
      while (p < n - 1) {
        if (u8[p] === 0xFF) { const x = u8[p + 1]; if (x !== 0 && !(x >= 0xD0 && x <= 0xD7) && x !== 0xFF) break; }
        p++;
      }
    }
  }
  return null;
}
function pngAt(u8, i) {
  const n = u8.length;
  const be = (p) => ((u8[p] << 24) | (u8[p + 1] << 16) | (u8[p + 2] << 8) | u8[p + 3]) >>> 0;
  if (be(i + 12) !== 0x49484452) return null;          //  IHDR
  const w = be(i + 16), h = be(i + 20);
  let p = i + 8;
  for (let k = 0; k < 100000 && p < n - 12; k++) {
    const len = be(p), type = be(p + 4);
    if (len > n) return null;
    p += 12 + len;
    if (type === 0x49454E44) return { start: i, end: p, w, h, mime: 'image/png' };   //  IEND
  }
  return null;
}
function findPreview(u8) {
  let best = null;
  const n = u8.length;
  for (let i = 0; i < n - 8; i++) {
    const b = u8[i];
    let r = null;
    if (b === 0xFF && u8[i + 1] === 0xD8 && u8[i + 2] === 0xFF) r = jpegAt(u8, i);
    else if (b === 0x89 && u8[i + 1] === 0x50 && u8[i + 2] === 0x4E && u8[i + 3] === 0x47) r = pngAt(u8, i);
    if (r && r.w >= 16 && r.h >= 16 && r.w <= 10000 && r.h <= 10000) {
      if (!best || r.w * r.h > best.w * best.h) best = r;
      i = r.end - 1;
    }
  }
  return best;
}

//  ── 큰 파일일수록 덜 곱게 깎는다(미리보기니까) ─────────────────
function quality(bytes) {
  const mb = bytes / 1048576;
  if (mb < 10) return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.001, angularDeflection: 0.5 };
  if (mb < 40) return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.002, angularDeflection: 0.8 };
  return { linearUnit: 'millimeter', linearDeflectionType: 'bounding_box_ratio', linearDeflection: 0.004, angularDeflection: 1.2 };
}

//  ── .hm3 — 가벼운 미리보기 묶음 ────────────────────────────────
//   'HM3' 1 | 머리글 길이(u32) | 머리글 JSON | (부품마다) 꼭짓점 Uint16×3(부품 상자 안 65535 칸) · 삼각형 번호 Uint16/Uint32
//   통째로 gzip. 뷰어(main.js loadHM3)가 읽는다.
function packHM3(res, meta) {
  const names = {};
  (function walk(nd, p) {
    if (!nd) return;
    const nm = (nd.name || '').trim();
    (nd.meshes || []).forEach((i) => { names[i] = nm || p; });
    (nd.children || []).forEach((c) => walk(c, nm || p));
  })(res.root, '');
  const head = { ver: 1, meshes: [] };
  const bufs = [];
  let tri = 0;
  res.meshes.forEach((m, k) => {
    const pos = m.attributes.position.array;
    const nv = pos.length / 3;
    const idx = m.index ? m.index.array : null;
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < pos.length; i += 3) for (let a = 0; a < 3; a++) { const v = pos[i + a]; if (v < min[a]) min[a] = v; if (v > max[a]) max[a] = v; }
    const q = new Uint16Array(nv * 3 + ((nv * 3) & 1));        //  4바이트 줄 맞춤
    for (let i = 0; i < pos.length; i += 3) for (let a = 0; a < 3; a++) {
      const s = max[a] - min[a];
      q[i + a] = s > 0 ? Math.round((pos[i + a] - min[a]) / s * 65535) : 0;
    }
    const i16 = nv < 65536;
    let ib;
    if (idx) {
      ib = i16 ? new Uint16Array(idx.length + (idx.length & 1)) : new Uint32Array(idx.length);
      for (let i = 0; i < idx.length; i++) ib[i] = idx[i];
    } else ib = new Uint16Array(0);
    const ni = idx ? idx.length : 0;
    tri += (idx ? ni : nv) / 3;
    head.meshes.push({ name: String(m.name || names[k] || '').trim(), color: m.color || null, n: nv, i: ni, i16, min, max });
    bufs.push(Buffer.from(q.buffer, q.byteOffset, q.byteLength), Buffer.from(ib.buffer, ib.byteOffset, ib.byteLength));
  });
  Object.assign(head, meta, { tri: Math.round(tri) });
  let js = Buffer.from(JSON.stringify(head), 'utf8');
  const pad = (4 - ((8 + js.length) % 4)) % 4;
  js = Buffer.concat([js, Buffer.alloc(pad, 0x20)]);
  const hd = Buffer.alloc(8);
  hd.write('HM3', 0, 'latin1'); hd[3] = 1; hd.writeUInt32LE(js.length, 4);
  return { gz: zlib.gzipSync(Buffer.concat([hd, js, ...bufs]), { level: 6 }), head };
}

// ── ① 서버 OpenCASCADE(occt-draw) ─────────────────────────────
const { spawn, spawnSync } = require('child_process');
const os = require('os');
let _draw;
function drawBin() {
  if (_draw !== undefined) return _draw;
  _draw = '';
  if (process.env.V3_NO_NATIVE) return _draw;            //  서버 엔진을 일부러 안 쓸 때(시험·문제 생겼을 때)
  const cands = [process.env.OCCT_BIN, '/usr/bin/occt-draw', '/usr/bin/occt-draw-7.6', '/usr/bin/occt-draw-7.7', '/usr/bin/occt-draw-7.8',
    '/usr/bin/DRAWEXE', '/usr/local/bin/DRAWEXE'].filter(Boolean);
  for (const b of cands) {
    if (!fs.existsSync(b)) continue;
    //  ⚠ 파일만 있다고 도는 게 아니다 — 우분투는 libTK*.so 링크가 빠져 「libTKTopTest.so 를 못 찾는다」로 죽는다
    //    (libocct-draw-dev 를 같이 깔면 된다). 한 번 돌려 보고 판정한다.
    try {
      const tcl = path.join(os.tmpdir(), 'v3chk_' + process.pid + '.tcl');
      fs.writeFileSync(tcl, 'pload MODELING DATAEXCHANGE\nputs V3-OK\nexit\n');
      const r = spawnSync(b, ['-b', '-f', tcl], { encoding: 'utf8', timeout: 30000 });
      fs.unlink(tcl, () => {});
      const out = String(r.stdout || '') + String(r.stderr || '');
      if (/V3-OK/.test(out) && !/cannot open shared object|Draw_Failure/.test(out)) { _draw = b; break; }
    } catch (e) { /* 다음 */ }
  }
  return _draw;
}
//  크기에 따라 곱기(상대 처짐·각도) — 미리보기라 큰 것은 성기게(삼각형 수를 브라우저가 감당할 만큼)
function drawQuality(bytes) {
  const mb = bytes / 1048576;
  if (mb < 20) return { defl: 0.02, ang: 30 };
  if (mb < 60) return { defl: 0.05, ang: 40 };
  return { defl: 0.1, ang: 60 };
}
//  STL(이진·글자) → 꼭짓점 합친 삼각형 묶음
function readStl(buf) {
  const n = buf.length >= 84 ? buf.readUInt32LE(80) : 0;
  let tri;
  if (buf.length === 84 + n * 50 && n > 0) {
    tri = new Float32Array(n * 9);
    for (let i = 0; i < n; i++) { const o = 84 + i * 50 + 12; for (let k = 0; k < 9; k++) tri[i * 9 + k] = buf.readFloatLE(o + k * 4); }
  } else {
    const v = [];
    const re = /vertex\s+(\S+)\s+(\S+)\s+(\S+)/g;
    const t = buf.toString('latin1');
    let m;
    while ((m = re.exec(t))) v.push(+m[1], +m[2], +m[3]);
    tri = Float32Array.from(v.slice(0, v.length - (v.length % 9)));
  }
  return dedupe(tri);
}
function dedupe(tri) {
  const nt = tri.length / 3;                         //  꼭짓점 수(삼각형×3)
  let cap = 16; while (cap < nt * 2) cap <<= 1;
  const table = new Int32Array(cap).fill(-1);
  const u = new Uint32Array(tri.buffer, tri.byteOffset, tri.length);
  const pos = new Float32Array(tri.length), pu = new Uint32Array(pos.buffer);
  const idx = new Uint32Array(nt);
  let nv = 0;
  for (let i = 0; i < nt; i++) {
    const a = u[i * 3], b = u[i * 3 + 1], c = u[i * 3 + 2];
    let h = (Math.imul(a, 73856093) ^ Math.imul(b, 19349663) ^ Math.imul(c, 83492791)) & (cap - 1);
    for (;;) {
      const v = table[h];
      if (v < 0) { table[h] = nv; pu[nv * 3] = a; pu[nv * 3 + 1] = b; pu[nv * 3 + 2] = c; idx[i] = nv++; break; }
      if (pu[v * 3] === a && pu[v * 3 + 1] === b && pu[v * 3 + 2] === c) { idx[i] = v; break; }
      h = (h + 1) & (cap - 1);
    }
  }
  return { pos: pos.subarray(0, nv * 3), idx };
}
async function runDraw(bin, inFile, kind, bytes, say) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'v3d-'));
  try {
    //  ⚠ Tcl 은 한글 경로를 못 연다 — 영문 임시 폴더로 옮겨 읽는다
    const inp = path.join(work, 'in.' + (kind === 'iges' ? 'igs' : kind === 'brep' ? 'brep' : 'stp'));
    try { fs.linkSync(inFile, inp); } catch (e) { fs.copyFileSync(inFile, inp); }
    const out = path.join(work, 'stl');
    const q = drawQuality(bytes);
    const T = (p) => '{' + p.replace(/\\/g, '/') + '}';
    const read = kind === 'iges' ? 'igesread ' + T(inp) + ' a *' : kind === 'brep' ? 'restore ' + T(inp) + ' a_1' : 'stepread ' + T(inp) + ' a *';
    fs.writeFileSync(path.join(work, 'c.tcl'), [
      'pload MODELING DATAEXCHANGE',
      'puts "V3 read"', read,
      'set names {}',
      'for {set i 1} {[isdraw a_$i]} {incr i} { lappend names a_$i }',
      'if {[llength $names] == 0} { puts "V3 empty"; exit }',
      'eval compound $names all',
      'puts "V3 mesh"',
      'incmesh all ' + q.defl + ' -a ' + q.ang + ' -relative -parallel',
      'puts "V3 write"',
      'set od ' + T(out),
      'file mkdir $od',
      'set parts [explode all so]',
      'if {[llength $parts] == 0} { set parts [explode all sh] }',
      'if {[llength $parts] == 0} { set parts {all} }',
      'set k 0',
      'foreach s $parts { incr k; writestl $s "$od/p$k.stl" }',
      'puts "V3 done $k"',
      'exit', ''].join('\n'));
    const log = await new Promise((ok, no) => {
      const ch = spawn(bin, ['-b', '-f', path.join(work, 'c.tcl')], { cwd: work, stdio: ['ignore', 'pipe', 'pipe'] });
      let all = '';
      const on = (d) => {
        all = (all + d).slice(-20000);
        const m = String(d).match(/V3 (read|mesh|write)/g);
        if (m) say({ phase: 'n' + m[m.length - 1].slice(3) });
      };
      ch.stdout.on('data', on); ch.stderr.on('data', on);
      ch.on('error', no);
      ch.on('exit', () => ok(all));
    });
    if (/V3 empty/.test(log)) throw new Error('모양을 찾지 못했습니다(파일이 깨졌거나 빈 파일)');
    const m = log.match(/V3 done (\d+)/);
    if (!m || !+m[1]) throw new Error('서버 OpenCASCADE 가 변환하지 못했습니다' + (/xception|rror/.test(log) ? ' — ' + log.split('\n').filter((l) => /xception|rror/.test(l)).pop().slice(0, 200) : ''));
    say({ phase: 'pack' });
    const meshes = [];
    for (let k = 1; k <= +m[1]; k++) {
      const f = path.join(out, 'p' + k + '.stl');
      if (!fs.existsSync(f)) continue;
      const { pos, idx } = readStl(fs.readFileSync(f));
      if (!idx.length) continue;
      meshes.push({ name: '', attributes: { position: { array: pos } }, index: { array: idx } });
    }
    if (!meshes.length) throw new Error('모양을 찾지 못했습니다(삼각형이 없음)');
    return { success: true, meshes, root: null, q };
  } finally {
    if (!process.env.V3_KEEP) fs.rm(work, { recursive: true, force: true }, () => {});
  }
}

async function run(inFile, kind, outBase, engineDir) {
  const say = (m) => { if (process.send) process.send(m); else console.log(JSON.stringify(m)); };
  const t0 = Date.now();
  const u8 = fs.readFileSync(inFile);
  if (kind !== 'catia' && drawBin()) {
    say({ phase: 'engine', native: true });
    const res = await runDraw(drawBin(), inFile, kind, u8.length, say);
    const { gz, head } = packHM3(res, { ms: Date.now() - t0, bytes: u8.length, crease: true, engine: 'occt-draw' });
    fs.writeFileSync(outBase + '.out', gz);
    return { type: 'mesh', mime: 'application/octet-stream', tri: head.tri, parts: head.meshes.length, ms: Date.now() - t0, gz: gz.length, engine: 'occt-draw' };
  }
  if (kind === 'catia') {
    say({ phase: 'scan' });
    const r = findPreview(u8);
    if (!r) throw new Error('이 CATIA 파일에는 미리보기 그림이 없습니다(미리보기 없이 저장됨) — 3D 로 보려면 CATIA 에서 STEP 으로 내보내 주세요');
    fs.writeFileSync(outBase + '.out', u8.subarray(r.start, r.end));
    return { type: 'image', mime: r.mime, w: r.w, h: r.h, ms: Date.now() - t0 };
  }
  say({ phase: 'engine' });
  const occtimportjs = require(path.join(engineDir, 'occt-import-js.js'));
  const oc = await occtimportjs({ locateFile: (f) => path.join(engineDir, f) });
  say({ phase: 'read' });
  const params = quality(u8.length);
  const res = kind === 'step' ? oc.ReadStepFile(u8, params) : kind === 'iges' ? oc.ReadIgesFile(u8, params) : oc.ReadBrepFile(u8, params);
  if (!res || !res.success || !res.meshes || !res.meshes.length) throw new Error('모양을 찾지 못했습니다(파일이 깨졌거나 빈 파일)');
  say({ phase: 'pack' });
  const { gz, head } = packHM3(res, { ms: Date.now() - t0, bytes: u8.length, q: params.angularDeflection, engine: 'wasm' });
  fs.writeFileSync(outBase + '.out', gz);
  return { type: 'mesh', mime: 'application/octet-stream', tri: head.tri, parts: head.meshes.length, ms: Date.now() - t0, gz: gz.length, engine: 'wasm' };
}

module.exports = { findPreview, quality, packHM3, run, drawBin };

if (require.main === module) {
  const [inFile, kind, outBase, engineDir] = process.argv.slice(2);
  run(inFile, kind, outBase, engineDir || path.join(__dirname, 'public', 'viewer3d'))
    .then((meta) => {
      fs.writeFileSync(outBase + '.json', JSON.stringify(meta));
      if (process.send) process.send({ done: meta }); else console.log(JSON.stringify(meta));
      process.exit(0);
    })
    .catch((e) => {
      const msg = String((e && e.message) || e);
      if (process.send) process.send({ error: msg }); else console.error(msg);
      process.exit(1);
    });
}
