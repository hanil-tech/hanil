//  📦 대용량 파일·폴더 올리기·받기 — 포털에 넣는 조각
//   넣는 법: 이 파일과 bigfile.html 을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./bigfile-route')(app);
//   여는 주소: /bigfile   (→ /bigfile/view — 포털 공통 조각이 안 끼는 주소)
//
//   ⭐ 올리기: 파일을 조각(기본 8MB)으로 잘라 3개씩 함께 보낸다. 조각마다 CRC32 를 맞춰 보고, 틀리면 그 조각만 다시.
//      끊겨도(망·창 닫음·새로고침) 같은 파일·폴더를 다시 고르면 **받은 조각 다음부터** 이어 올린다.
//   ⭐ 폴더: 먼저 「목록표」(모든 파일의 경로·크기·빈 폴더)를 받아 두고, 파일이 다 왔는지 목록표로 맞춰 본다(빠진 파일 0).
//      받을 때는 폴더째 ZIP 으로 묶어 흘려 보낸다 — 크기 제한 없음 · 묶음 모양이 늘 같아 Range(이어 받기)가 된다.
//   ⭐ 받기: Range 를 받는다 — 브라우저·폰 앱 내려받기가 끊겨도 이어 받는다. 메모리에 올리지 않고 흘려 보낸다.
//   ⭐ 공유: 사내 공개(로그인한 직원 누구나) · 바깥 사람용 링크(기한·횟수 제한, 로그인 없이).
//   ⚠ 디스크에는 파일 이름을 쓰지 않는다(<열쇠>.bin) — 이름·경로는 meta/·groups/ 의 JSON 에만. 이상한 이름으로 폴더를 벗어날 수 없다.
//   ⚠ 앞에 nginx 가 있으면 조각 크기보다 크게: client_max_body_size 16m;  (기본 1m 이면 413 으로 안 올라간다)
//   ⚠ 포털의 express.json() 이 있든 없든 돌게 — 값은 주소 꼬리(?a=)로, 폴더 목록표만 몸통(글자)으로 받아 직접 읽는다.
'use strict';
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { pipeline, Transform, Readable } = require('stream');

const MB = 1048576, GB = 1073741824, DAY = 86400000;

//  CRC32 — 브라우저(bigfile.html)와 같은 계산
const CRC_T = (() => { const t = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c; } return t; })();
function crc32js(buf, prev) { let c = ~(prev || 0); for (let i = 0; i < buf.length; i++) c = CRC_T[(c ^ buf[i]) & 0xff] ^ (c >>> 8); return ~c >>> 0; }
//  Node 20.15·22.2 부터는 zlib.crc32(빠름, 같은 값)가 있다 — 서버 검사가 디스크 속도로 돈다. 없으면 위의 것
const crc32 = typeof require('zlib').crc32 === 'function' ? (buf, prev) => require('zlib').crc32(buf, prev || 0) >>> 0 : crc32js;
//  조각 CRC 들을 이어 붙여 전체 CRC32 (zlib crc32_combine) — 파일을 다시 읽지 않고. ZIP 머리에 쓴다.
function gf2(mat, vec) { let s = 0, i = 0; vec >>>= 0; while (vec) { if (vec & 1) s ^= mat[i]; vec >>>= 1; i++; } return s >>> 0; }
function gf2sq(sq, mat) { for (let n = 0; n < 32; n++) sq[n] = gf2(mat, mat[n]); }
function crcShift(crc1, len) {
  const even = new Uint32Array(32), odd = new Uint32Array(32);
  odd[0] = 0xedb88320; let row = 1;
  for (let n = 1; n < 32; n++) { odd[n] = row; row <<= 1; }
  gf2sq(even, odd); gf2sq(odd, even);
  crc1 >>>= 0;
  while (len) {
    gf2sq(even, odd); if (len & 1) crc1 = gf2(even, crc1); len = Math.floor(len / 2); if (!len) break;
    gf2sq(odd, even); if (len & 1) crc1 = gf2(odd, crc1); len = Math.floor(len / 2);
  }
  return crc1;
}
function crcCombineAll(crcs, size, chunk) {          //  crcs: Buffer(4바이트씩)
  const n = crcs.length / 4;
  if (!size) return 0;
  const full = new Uint32Array(32);
  for (let k = 0; k < 32; k++) full[k] = crcShift(1 << k, chunk);
  let c = crcs.readUInt32LE(0);
  for (let i = 1; i < n; i++) {
    const len = Math.min(chunk, size - i * chunk);
    c = ((len === chunk ? gf2(full, c) : crcShift(c, len)) ^ crcs.readUInt32LE(i * 4)) >>> 0;
  }
  return c >>> 0;
}
const hex8 = (n) => (n >>> 0).toString(16).padStart(8, '0');

module.exports = function mountBigfile(app, ctx) {
  ctx = ctx || {};
  //  로그인한 사람 — 포털 세션 모양을 몰라도 돌게 흔한 이름들을 본다. 다르면 ctx.user 로 넘겨 준다.
  const userOf = ctx.user || ((req) => {
    const u = req.session && req.session.user;
    if (!u) return null;
    const id = [u.id, u.user_id, u.uid, u.username, u.login, u.name].find((v) => v !== undefined && v !== null && v !== '');
    if (id === undefined) return null;
    return {
      id: String(id),
      name: String(u.name || u.username || id),
      admin: !!(u.is_admin || u.isAdmin || u.admin || u.role === 'admin' || u.level === 'admin' || u.grade === 'admin'),
    };
  });
  const pageAuth = (req, res, next) => (userOf(req) ? next() : res.redirect('/?next=' + encodeURIComponent(req.originalUrl || '/bigfile')));
  const apiAuth = (req, res, next) => { const u = userOf(req); if (!u) return res.status(401).json({ error: '로그인이 필요합니다' }); req.bf = u; next(); };

  const STORE = ctx.dir || process.env.BIGFILE_DIR || path.join(__dirname, 'bigfile-store');
  const CHUNK = Math.round((ctx.chunkMB || 8) * MB);
  const PAR = ctx.parallel || 3;                         //  한꺼번에 몇 조각씩 보내나
  const MAX = (ctx.maxGB || 50) * GB;                    //  파일 하나 최대
  const QUOTA = (ctx.quotaGB || 0) * GB;                 //  한 사람 합계(0 = 제한 없음)
  const KEEP_FREE = (ctx.keepFreeGB === undefined ? 5 : ctx.keepFreeGB) * GB;   //  디스크를 이만큼은 비워 둔다
  const PART_DAYS = ctx.partialDays || 7;                //  다 못 올린 것은 마지막 조각 뒤 n일에 지운다
  const KEEP_DAYS = ctx.keepDays || 0;                   //  다 올린 것을 n일 뒤 지운다(0 = 안 지움)
  const SHARE_DAYS_MAX = ctx.shareDaysMax || 30;
  const MAX_ENTRIES = ctx.maxEntries || 200000;          //  폴더 하나에 파일·폴더 수
  const META = path.join(STORE, 'meta'), DATA = path.join(STORE, 'data'), GDIR = path.join(STORE, 'groups');
  fs.mkdirSync(META, { recursive: true });
  fs.mkdirSync(DATA, { recursive: true });
  fs.mkdirSync(GDIR, { recursive: true });

  const ID = /^[0-9a-f]{32}$/, TOK = /^[0-9A-Za-z_-]{32}$/;
  const files = new Map();                               //  열쇠 → 파일 정보(+ got: 받은 조각 비트)
  const groups = new Map();                              //  열쇠 → 폴더 정보(목록표)
  for (const f of fs.readdirSync(META)) {
    if (!/^[0-9a-f]{32}\.json$/.test(f)) continue;
    try {
      const m = JSON.parse(fs.readFileSync(path.join(META, f), 'utf8'));
      m.got = Buffer.from(m.got || '', 'base64');
      if (m.got.length < Math.ceil(m.n / 8)) m.got = Buffer.concat([m.got, Buffer.alloc(Math.ceil(m.n / 8) - m.got.length)]);
      fixCrc(m);
      files.set(m.id, m);
    } catch (e) { /* 깨진 정보 — 건너뜀 */ }
  }
  for (const f of fs.readdirSync(GDIR)) {
    if (!/^[0-9a-f]{32}\.json$/.test(f)) continue;
    try { const g = JSON.parse(fs.readFileSync(path.join(GDIR, f), 'utf8')); groups.set(g.gid, g); } catch (e) { /* 건너뜀 */ }
  }
  //  조각마다 CRC32 를 적어 둔다(crcs: 4바이트씩, ck: 적어 둔 조각 비트) — 끝난 뒤 검사·받을 때 검사에 쓴다
  //  ⚠ 이 기능 전에 올린 파일은 crcs 가 없다 → 처음 검사할 때 디스크에서 읽어 채운다
  function fixCrc(m) {
    m.crcs = Buffer.from(typeof m.crcs === 'string' ? m.crcs : '', 'base64');
    m.ck = Buffer.from(typeof m.ck === 'string' ? m.ck : '', 'base64');
    if (m.crcs.length !== m.n * 4) m.crcs = Buffer.alloc(m.n * 4);
    if (m.ck.length !== Math.ceil(m.n / 8)) m.ck = Buffer.alloc(Math.ceil(m.n / 8));
  }
  const ckAll = (m) => { for (let i = 0; i < m.n; i++) if (!((m.ck[i >> 3] >> (i & 7)) & 1)) return false; return true; };
  //  파일 전체 CRC32 — 조각 CRC 를 이어 붙여서(다 알 때만)
  const wholeCrc = (m) => { if (!m.crc && m.state === 'done' && ckAll(m)) m.crc = hex8(crcCombineAll(m.crcs, m.size, m.chunk)); return m.crc || ''; };
  const binOf = (id) => path.join(DATA, id + '.bin');
  const has = (m, i) => (m.got[i >> 3] >> (i & 7)) & 1;
  const gotCount = (m) => { let c = 0; for (let i = 0; i < m.n; i++) c += has(m, i); return c; };
  const gotBytes = (m) => (m.state === 'done' ? m.size : Math.min(m.size, gotCount(m) * m.chunk));
  const chunkLen = (m, i) => Math.min(m.chunk, m.size - i * m.chunk);
  //  정보는 바뀔 때마다 파일에 — 같은 것은 차례로(겹쳐 쓰면 깨진다), 임시 파일에 쓰고 이름 바꾸기
  const saving = new Map();
  function writeJson(key, f, alive, data) {
    const prev = saving.get(key) || Promise.resolve();
    const p = prev.then(() => new Promise((ok) => {
      if (!alive()) return ok();
      const tmp = f + '.' + process.pid + '.tmp';
      fs.writeFile(tmp, JSON.stringify(data()), (e) => { if (e) return ok(); fs.rename(tmp, f, () => ok()); });
    }));
    saving.set(key, p);
    p.then(() => { if (saving.get(key) === p) saving.delete(key); });
    return p;
  }
  const save = (m) => writeJson(m.id, path.join(META, m.id + '.json'), () => files.has(m.id),
    () => Object.assign({}, m, { got: m.got.toString('base64'), crcs: m.crcs.toString('base64'), ck: m.ck.toString('base64') }));
  const saveG = (g) => writeJson('g' + g.gid, path.join(GDIR, g.gid + '.json'), () => groups.has(g.gid), () => g);
  function remove(m) {
    files.delete(m.id);
    fs.rm(binOf(m.id), { force: true }, () => {});
    fs.rm(path.join(META, m.id + '.json'), { force: true }, () => {});
  }
  function removeG(g) {
    for (const m of [...files.values()]) if (m.group === g.gid) remove(m);
    groups.delete(g.gid);
    fs.rm(path.join(GDIR, g.gid + '.json'), { force: true }, () => {});
  }
  const groupOf = (m) => (m.group ? groups.get(m.group) : null);
  const gPub = (g) => !!(g && g.pub && g.state === 'done');
  const canSee = (u, m) => m.owner === u.id || u.admin || (m.state === 'done' && (m.pub || gPub(groupOf(m))));
  const canEdit = (u, m) => m.owner === u.id || u.admin;
  const canSeeG = (u, g) => g.owner === u.id || u.admin || gPub(g);
  const shareView = (o) => (o.shares || []).map((s) => ({ tok: s.tok, exp: s.exp, max: s.max, used: s.used || 0 }));
  const view = (m, u) => ({
    kind: 'file', id: m.id, name: m.name, size: m.size, type: m.type, state: m.state, owner: m.ownerName, mine: m.owner === u.id,
    t0: m.t0, t1: m.t1 || 0, pub: !!m.pub, dl: m.dl || 0, got: m.state === 'done' ? m.n : gotCount(m), n: m.n,
    v: m.verify ? { ok: m.verify.ok, at: m.verify.at } : null,
    shares: canEdit(u, m) ? shareView(m) : [],
  });
  const fileEntries = (g) => g.entries.filter((e) => !e.d);
  function gview(g, u) {
    let got = 0;
    for (const e of fileEntries(g)) { const m = e.id && files.get(e.id); if (m) got += gotBytes(m); }
    return {
      kind: 'group', id: g.gid, name: g.name, size: g.total, nfiles: g.nfiles, ndirs: g.ndirs, nfolders: g.nfolders !== undefined ? g.nfolders : allDirs(g.entries).length,
      state: g.state, owner: g.ownerName,
      mine: g.owner === u.id, t0: g.t0, t1: g.t1 || 0, pub: !!g.pub, dl: g.dl || 0, gotBytes: got,
      v: g.v || null, shares: g.owner === u.id || u.admin ? shareView(g) : [],
    };
  }
  function diskFree() {
    try { const s = fs.statfsSync(STORE); return s.bavail * s.bsize; } catch (e) { return -1; }   //  Node 18.15 전에는 모름
  }
  const usedBy = (uid) => { let s = 0; for (const m of files.values()) if (m.owner === uid) s += m.size; return s; };
  //  아직 덜 온 바이트(다 올라오면 디스크를 더 쓸 몫)
  const pending = () => { let s = 0; for (const m of files.values()) if (m.state !== 'done') s += m.size - gotBytes(m); return s; };
  function roomFor(u, size) {
    if (QUOTA && usedBy(u.id) + size > QUOTA) return '내 자리(' + (QUOTA / GB) + 'GB)가 모자랍니다 — 안 쓰는 파일을 지워 주세요';
    const free = diskFree();
    if (free >= 0 && free - pending() - size < KEEP_FREE) return '서버 디스크 자리가 모자랍니다(남은 ' + (free / GB).toFixed(1) + 'GB)';
    return '';
  }
  //  경로 손질 — 이름은 **올린 그대로** 둔다(원본과 달라지지 않게). 막는 것은 「..」·「.」·제어 글자뿐.
  //   ⭐ 한글은 NFC 로 맞춘다 — 맥은 「한」을 ㅎ+ㅏ+ㄴ(NFD)로 넘겨 윈도에서 「ㅎㅏㄴ」으로 깨지고 같은 이름끼리도 다른 것으로 친다.
  //   (윈도에 못 쓰는 : * ? 따위는 받는 쪽 화면이 그 PC 에서만 바꿔 쓰고 검사표에 적는다)
  const cleanSeg = (s) => String(s).normalize('NFC').replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 255);
  function cleanPath(p) {
    const segs = String(p || '').replace(/\\/g, '/').split('/').map(cleanSeg).filter((s) => s !== '');
    if (!segs.length || segs.some((s) => s === '.' || s === '..')) return '';
    const out = segs.join('/');
    return out.length > 1024 ? '' : out;
  }
  //  몸통 읽기 — 포털이 이미 읽어 두었으면(express.json·text) 그것을, 아니면 직접
  function readBody(req, limit) {
    return new Promise((ok, no) => {
      if (req.body && typeof req.body === 'object' && !Buffer.isBuffer(req.body) && Object.keys(req.body).length) return ok(req.body);
      if (typeof req.body === 'string' && req.body) { try { return ok(JSON.parse(req.body)); } catch (e) { return no(e); } }
      if (Buffer.isBuffer(req.body) && req.body.length) { try { return ok(JSON.parse(req.body.toString('utf8'))); } catch (e) { return no(e); } }
      const bufs = []; let n = 0;
      req.on('data', (b) => { n += b.length; if (n > limit) { no(new Error('너무 큽니다')); req.destroy(); } else bufs.push(b); });
      req.on('end', () => { try { ok(JSON.parse(Buffer.concat(bufs).toString('utf8'))); } catch (e) { no(e); } });
      req.on('error', no);
    });
  }

  // ── 화면 ──────────────────────────────────────────────────────────
  //  ⭐ 주소가 /view 로 끝나야 포털이 공통 조각(쪽지함·단추 등)을 끼우지 않는다(viewer3d 와 같음). sendFile 로 내준다.
  app.get('/bigfile', pageAuth, (req, res) => res.redirect('/bigfile/view'));
  app.get('/bigfile/view', pageAuth, (req, res) => {
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.sendFile(path.join(__dirname, 'bigfile.html'));
  });

  // ── API ──────────────────────────────────────────────────────────
  app.get('/bigfile/api/info', apiAuth, (req, res) => {
    res.json({ user: req.bf.name, admin: req.bf.admin, chunk: CHUNK, parallel: PAR, max: MAX, quota: QUOTA,
      used: usedBy(req.bf.id), free: diskFree(), keepFree: KEEP_FREE, partDays: PART_DAYS, keepDays: KEEP_DAYS, shareDaysMax: SHARE_DAYS_MAX });
  });

  //  목록 — 낱개 파일과 폴더(폴더 안 파일은 폴더 한 줄로). ?all=1 — 관리자는 모든 사람 것
  app.get('/bigfile/api/list', apiAuth, (req, res) => {
    const u = req.bf, all = u.admin && req.query.all === '1';
    const out = [];
    for (const m of files.values()) {
      if (m.group && groups.has(m.group)) continue;
      if (all ? true : (m.owner === u.id || (m.pub && m.state === 'done'))) out.push(view(m, u));
    }
    for (const g of groups.values()) if (all ? true : (g.owner === u.id || gPub(g))) out.push(gview(g, u));
    out.sort((a, b) => (b.t1 || b.t0) - (a.t1 || a.t0));
    res.json({ files: out });
  });

  // ── 📁 폴더 — 목록표 먼저 ─────────────────────────────────────────
  //   PUT /bigfile/api/group   몸통 { name, entries:[{ p:'하위/파일.txt', s:크기, lm:수정시각 } | { p:'빈폴더', d:1 }] }
  //   같은 사람이 같은 이름의 폴더를 올리다 말았으면 그것을 이어 간다 — 목록표를 새것으로 바꾸고,
  //   경로·크기·수정 시각이 같은 파일은 받아 둔 것을 그대로 쓴다(바뀐·빠진 파일은 지운다).
  //   답: { gid, resumed, entries:[{ p, d, s, id, state }] }  — state 'done' 인 파일은 다시 안 보내도 된다
  app.put('/bigfile/api/group', apiAuth, (req, res) => {
    const u = req.bf;
    readBody(req, 64 * MB).then((b) => {
      const name = cleanSeg(b && b.name);
      if (!name || name === '.' || name === '..') return res.status(400).json({ error: '폴더 이름이 없습니다' });
      const list = Array.isArray(b.entries) ? b.entries : [];
      if (!list.length) return res.status(400).json({ error: '빈 폴더입니다' });
      if (list.length > MAX_ENTRIES) return res.status(413).json({ error: '폴더 하나에 ' + MAX_ENTRIES + '개까지 올릴 수 있습니다 — 나눠 올려 주세요' });
      const seen = new Map();
      for (const x of list) {
        const p = cleanPath(x && x.p);
        if (!p) return res.status(400).json({ error: '이상한 경로가 있습니다: ' + String(x && x.p).slice(0, 100) });
        if (x.d) { if (!seen.has(p)) seen.set(p, { p, d: 1 }); continue; }
        const s = Number(x.s);
        if (!Number.isSafeInteger(s) || s < 0) return res.status(400).json({ error: '크기가 이상한 파일: ' + p });
        if (s > MAX) return res.status(413).json({ error: '파일 하나는 ' + (MAX / GB) + 'GB 까지입니다: ' + p });
        if (seen.has(p) && !seen.get(p).d) return res.status(400).json({ error: '같은 경로가 두 번 있습니다: ' + p });
        seen.set(p, { p, s, lm: Number(x.lm) || 0 });
      }
      const entries = [...seen.values()].sort((a, c) => (a.p < c.p ? -1 : a.p > c.p ? 1 : 0));
      let g = null;
      //  ?gid — 다 올린 폴더를 고치거나(검사 불합격) 이어 올릴 때 그 폴더를 바로 가리킨다(올린 사람만)
      if (b.gid) {
        g = ID.test(String(b.gid)) && groups.get(String(b.gid));
        if (!g || g.owner !== u.id) return res.status(404).json({ error: '고칠 폴더가 없습니다(올린 사람만)' });
        g.state = 'part';
      } else for (const x of groups.values()) if (x.owner === u.id && x.state !== 'done' && x.name === name && (!g || x.tl > g.tl)) g = x;
      const resumed = !!g;
      const old = new Map();
      if (g) for (const e of g.entries) if (!e.d && e.id) old.set(e.p, e);
      let need = 0;
      for (const e of entries) {
        if (e.d) continue;
        const o = old.get(e.p), m = o && files.get(o.id);
        if (m && m.size === e.s && o.lm === e.lm && m.group === (g && g.gid)) { e.id = m.id; old.delete(e.p); } else need += e.s;
      }
      //  고치기(gid)일 때는 새 목록표에 없는 파일도 지우지 않고 그대로 둔다 — 다른 폴더를 잘못 골라도 서버 파일을 잃지 않게
      if (b.gid) {
        for (const o of old.values()) { entries.push(o); }
        for (const e of g.entries) if (e.d && !seen.has(e.p)) entries.push(e);
        old.clear();
        entries.sort((a, c) => (a.p < c.p ? -1 : a.p > c.p ? 1 : 0));
      }
      const why = roomFor(u, need);
      if (why) return res.status(why.indexOf('디스크') >= 0 ? 507 : 413).json({ error: why });
      for (const o of old.values()) { const m = files.get(o.id); if (m && g && m.group === g.gid) remove(m); }
      if (!g) {
        g = { gid: crypto.randomBytes(16).toString('hex'), name, owner: u.id, ownerName: u.name, t0: Date.now(), state: 'part', pub: false, shares: [], dl: 0 };
        groups.set(g.gid, g);
      }
      g.entries = entries; g.tl = Date.now(); delete g.v;
      g.name = b.gid ? g.name : name;
      g.nfiles = entries.filter((e) => !e.d).length; g.ndirs = entries.length - g.nfiles;
      g.nfolders = allDirs(entries).length;
      g.total = entries.reduce((a, e) => a + (e.s || 0), 0);
      saveG(g).then(() => res.json({ gid: g.gid, resumed, entries: entries.map((e) => entryView(e, false)) }));
    }).catch(() => res.status(400).json({ error: '목록표를 읽지 못했습니다' }));
  });
  //  폴더 수 — 빈 폴더만이 아니라 파일이 든 하위 폴더까지 모두(탐색기 「폴더 n개」와 같은 수)
  function allDirs(entries) {
    const set = new Set();
    for (const e of entries) {
      const segs = e.p.split('/'), upto = e.d ? segs.length : segs.length - 1;
      for (let i = 1; i <= upto; i++) set.add(segs.slice(0, i).join('/'));
    }
    return [...set].sort();
  }
  function entryView(e, withCrcs) {
    if (e.d) return { p: e.p, d: 1 };
    const m = e.id && files.get(e.id);
    const o = { p: e.p, s: e.s, lm: e.lm, id: m ? m.id : null, state: m ? m.state : null };
    if (m && m.state === 'done') {
      o.crc = wholeCrc(m); o.n = m.n; o.chunk = m.chunk;
      if (m.verify) o.v = { ok: m.verify.ok && (!o.crc || m.verify.crc === o.crc), badCount: m.verify.badCount, bad: m.verify.bad, disk: m.verify.disk, crc: m.verify.crc };
      if (withCrcs && ckAll(m)) o.crcs = m.crcs.toString('base64');
    }
    return o;
  }
  //  폴더 하나 — 목록표 + 파일마다 상태·CRC (?crcs=1 이면 조각 CRC 까지, ?dl=1 이면 받은 횟수 +1)
  app.get('/bigfile/api/group/:gid', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !canSeeG(req.bf, g)) return res.status(404).json({ error: '없는 폴더입니다' });
    if (req.query.dl === '1') { g.dl = (g.dl || 0) + 1; saveG(g); }
    res.json(Object.assign(gview(g, req.bf), { entries: g.entries.map((e) => entryView(e, req.query.crcs === '1')) }));
  });
  //  목록 받기(CSV, 엑셀에서 열림) — 원본 폴더와 하나하나 대어 볼 수 있게: 종류·경로·크기·수정한 날짜·CRC32
  app.get('/bigfile/api/group/:gid/list.csv', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !canSeeG(req.bf, g)) return res.status(404).send('없는 폴더입니다.');
    const q = (v) => '"' + String(v).replace(/"/g, '""') + '"';
    const two = (n) => String(n).padStart(2, '0');
    const when = (ms) => { if (!ms) return ''; const d = new Date(ms); return d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate()) + ' ' + two(d.getHours()) + ':' + two(d.getMinutes()) + ':' + two(d.getSeconds()); };
    const empty = new Set(g.entries.filter((e) => e.d).map((e) => e.p));
    const rows = [['종류', '경로', '크기(바이트)', '수정한 날짜', 'CRC32', '상태'].map(q).join(',')];
    const items = allDirs(g.entries).map((p) => ({ p, d: 1 })).concat(fileEntries(g)).sort((a, b) => (a.p < b.p ? -1 : a.p > b.p ? 1 : 0));
    for (const e of items) {
      if (e.d) { rows.push([q(empty.has(e.p) ? '빈 폴더' : '폴더'), q(g.name + '/' + e.p + '/'), '', '', '', ''].join(',')); continue; }
      const m = e.id && files.get(e.id);
      rows.push([q('파일'), q(g.name + '/' + e.p), e.s, q(when(e.lm)), q(m && m.state === 'done' ? wholeCrc(m) : ''), q(m ? (m.state === 'done' ? '다 올림' : '올리는 중') : '아직')].join(','));
    }
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', "attachment; filename=\"list.csv\"; filename*=UTF-8''" + encodeURIComponent(g.name + ' 목록.csv'));
    res.send('\ufeff' + rows.join('\r\n') + '\r\n');          //  BOM — 엑셀이 한글을 안 깨게
  });
  //  폴더 다 올림 — 목록표의 모든 파일이 다 왔는지 본다(빠진 파일이 있으면 409 + 그 경로들)
  app.post('/bigfile/api/gdone/:gid', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || g.owner !== req.bf.id) return res.status(404).json({ error: '올리던 폴더가 없습니다' });
    const miss = [];
    for (const e of fileEntries(g)) { const m = e.id && files.get(e.id); if (!m || m.state !== 'done' || m.size !== e.s) miss.push(e.p); }
    if (miss.length) return res.status(409).json({ error: '아직 안 온 파일이 ' + miss.length + '개 있습니다', missing: miss.slice(0, 200), count: miss.length });
    if (g.state !== 'done') { g.state = 'done'; g.t1 = Date.now(); }
    saveG(g).then(() => res.json({ group: gview(g, req.bf) }));
  });
  app.delete('/bigfile/api/group/:gid', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !(g.owner === req.bf.id || req.bf.admin)) return res.status(404).json({ error: '없는 폴더입니다' });
    removeG(g);
    res.json({ ok: true });
  });

  //  올리기 시작 — 같은 사람이 같은 파일(이름·크기·수정 시각)을 올리다 말았으면 그것을 이어 간다
  //   폴더 안 파일은 ?g=<폴더>&p=<경로> — 목록표에 있는 파일이어야 한다
  app.post('/bigfile/api/init', apiAuth, (req, res) => {
    const u = req.bf;
    let g = null, p = '';
    if (req.query.g) {
      g = ID.test(String(req.query.g)) && groups.get(String(req.query.g));
      if (!g || g.owner !== u.id) return res.status(404).json({ error: '올리던 폴더가 없습니다' });
      p = cleanPath(req.query.p);
    }
    const name = g ? p.split('/').pop() : cleanSeg(String(req.query.name || '').replace(/[\\/]/g, '_'));
    const size = Number(req.query.size), lm = Number(req.query.lm) || 0;
    const type = String(req.query.type || '').slice(0, 100);
    if (!name) return res.status(400).json({ error: '파일 이름이 없습니다' });
    if (!Number.isSafeInteger(size) || size < 0) return res.status(400).json({ error: '파일 크기가 이상합니다' });
    if (size > MAX) return res.status(413).json({ error: '파일 하나는 ' + (MAX / GB) + 'GB 까지 올릴 수 있습니다' });
    let ent = null;
    if (g) {
      ent = g.entries.find((e) => !e.d && e.p === p);
      if (!ent || ent.s !== size) return res.status(409).json({ error: '목록표에 없는 파일입니다(폴더를 다시 골라 주세요): ' + p });
      const m0 = ent.id && files.get(ent.id);
      if (m0 && m0.size === size) {
        if (m0.state === 'done') return res.json({ id: m0.id, chunk: m0.chunk, n: m0.n, have: m0.got.toString('base64'), resumed: true, done: true });
        return res.json({ id: m0.id, chunk: m0.chunk, n: m0.n, have: m0.got.toString('base64'), resumed: true });
      }
    } else {
      for (const m of files.values()) {
        if (m.owner === u.id && !m.group && m.state !== 'done' && m.name === name && m.size === size && m.lm === lm) {
          return res.json({ id: m.id, chunk: m.chunk, n: m.n, have: m.got.toString('base64'), resumed: true });
        }
      }
      const why = roomFor(u, size);
      if (why) return res.status(why.indexOf('디스크') >= 0 ? 507 : 413).json({ error: why });
    }
    const n = Math.max(1, Math.ceil(size / CHUNK));
    const m = { id: crypto.randomBytes(16).toString('hex'), name, size, type, lm, chunk: CHUNK, n, got: Buffer.alloc(Math.ceil(n / 8)),
      owner: u.id, ownerName: u.name, t0: Date.now(), tl: Date.now(), state: 'part', pub: false, shares: [], dl: 0 };
    if (g) { m.group = g.gid; m.path = p; ent.id = m.id; g.tl = Date.now(); saveG(g); }
    fixCrc(m);
    fs.writeFileSync(binOf(m.id), '');
    files.set(m.id, m);
    if (size === 0) { m.got[0] = 1; m.ck[0] = 1; }       //  빈 파일 — 보낼 조각이 없다(CRC32 는 0)
    save(m).then(() => res.json({ id: m.id, chunk: m.chunk, n: m.n, have: m.got.toString('base64'), resumed: false }));
  });

  //  조각 하나 — 몸통이 그대로 파일 자리(i × 조각 크기)에 들어간다. 머리 x-crc32 와 맞아야 받은 것으로 친다.
  const busy = new Set();
  app.put('/bigfile/api/chunk/:id/:i', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.owner !== req.bf.id) return res.status(404).json({ error: '올리던 파일이 없습니다(지워졌거나 기한이 지남)' });
    if (m.state === 'done') return res.status(409).json({ error: '이미 다 올린 파일입니다' });
    const i = Number(req.params.i);
    if (!Number.isInteger(i) || i < 0 || i >= m.n) return res.status(400).json({ error: '조각 번호가 이상합니다' });
    if (has(m, i)) { req.resume(); return res.json({ ok: true, dup: true }); }
    const want = chunkLen(m, i), wantCrc = Number.parseInt(String(req.headers['x-crc32'] || ''), 16);
    const k = m.id + ':' + i;
    if (busy.has(k)) { req.resume(); return res.status(409).json({ error: '같은 조각을 받는 중입니다' }); }
    busy.add(k);
    let got = 0, c = 0, over = false;
    const count = new Transform({
      transform(b, e, cb) {
        got += b.length;
        if (got > want) { over = true; return cb(new Error('too big')); }
        c = crc32(b, c); cb(null, b);
      },
    });
    const ws = fs.createWriteStream(binOf(m.id), { flags: 'r+', start: i * m.chunk });
    pipeline(req, count, ws, (err) => {
      busy.delete(k);
      if (res.headersSent) return;
      if (over) { res.setHeader('Connection', 'close'); return res.status(413).json({ error: '조각이 너무 큽니다' }); }
      if (err) return res.status(400).json({ error: '조각을 받다가 끊겼습니다' });
      if (got !== want) return res.status(400).json({ error: '조각 크기가 맞지 않습니다(' + got + '/' + want + ')' });
      if (!Number.isNaN(wantCrc) && wantCrc !== c) return res.status(422).json({ error: '조각이 깨져서 왔습니다(CRC)' });
      if (!files.has(m.id)) return res.status(404).json({ error: '올리던 파일이 지워졌습니다' });
      m.got[i >> 3] |= 1 << (i & 7);
      m.crcs.writeUInt32LE(c >>> 0, i * 4);
      m.ck[i >> 3] |= 1 << (i & 7);
      m.tl = Date.now();
      const g = groupOf(m); if (g) g.tl = m.tl;
      save(m).then(() => { if (!res.headersSent) res.json({ ok: true }); });
    });
  });

  //  다 보냈다 — 빠진 조각이 없고 크기가 맞으면 끝(전체 CRC32 를 조각 CRC 로 적어 둔다)
  app.post('/bigfile/api/done/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.owner !== req.bf.id) return res.status(404).json({ error: '올리던 파일이 없습니다' });
    if (m.state === 'done') return res.json({ file: view(m, req.bf) });
    const miss = [];
    for (let i = 0; i < m.n && miss.length < 50; i++) if (!has(m, i)) miss.push(i);
    if (miss.length) return res.status(409).json({ error: '빠진 조각이 있습니다', miss });
    fs.stat(binOf(m.id), (e, st) => {
      if (e || st.size !== m.size) return res.status(500).json({ error: '서버에 쌓인 크기가 맞지 않습니다' + (st ? '(' + st.size + '/' + m.size + ')' : '') });
      m.state = 'done'; m.t1 = Date.now(); delete m.crc; wholeCrc(m);
      save(m).then(() => res.json({ file: view(m, req.bf), crc: m.crc }));
    });
  });

  //  🔧 검사에서 틀린 조각을 다시 받게 연다 — ?chunks=3,17,20 또는 all
  //   그 조각들만 「안 받음」으로 돌리고 올리기 중(part)으로 되돌린다 → 올린 사람이 그 조각만 다시 보낸 뒤 done·검사
  //   디스크 파일이 적어 둔 크기보다 길면 잘라 낸다. 답은 init 과 같은 모양(have)이라 화면이 그대로 이어 올린다.
  app.post('/bigfile/api/reopen/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.owner !== req.bf.id) return res.status(404).json({ error: '다시 보낼 수 있는 파일이 아닙니다(올린 사람만)' });
    const vj = vjobs.get(m.id);
    if (vj && vj.state === 'work') return res.status(409).json({ error: '검사하는 중입니다 — 끝난 뒤 다시' });
    const q = String(req.query.chunks || '');
    const list = q === 'all' ? Array.from({ length: m.n }, (x, i) => i) : q.split(',').filter(Boolean).map(Number);
    if (!list.length || list.some((i) => !Number.isInteger(i) || i < 0 || i >= m.n)) return res.status(400).json({ error: '조각 번호가 이상합니다' });
    for (const i of list) { m.got[i >> 3] &= ~(1 << (i & 7)); m.ck[i >> 3] &= ~(1 << (i & 7)); }
    if (m.size === 0) { m.got[0] = 1; m.ck[0] = 1; }
    m.state = 'part'; m.tl = Date.now(); delete m.verify; delete m.crc;
    const g = groupOf(m);
    if (g) { g.state = 'part'; g.tl = Date.now(); delete g.v; saveG(g); }
    fs.stat(binOf(m.id), (e, st) => {
      const go = () => save(m).then(() => res.json({ id: m.id, chunk: m.chunk, n: m.n, have: m.got.toString('base64'), resumed: true, reopened: list.length }));
      if (!e && st.size > m.size) return fs.truncate(binOf(m.id), m.size, go);
      if (e) fs.writeFileSync(binOf(m.id), '');
      go();
    });
  });

  app.delete('/bigfile/api/file/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canEdit(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    if (groupOf(m)) return res.status(409).json({ error: '폴더 안의 파일은 폴더째 지웁니다' });
    remove(m);
    res.json({ ok: true });
  });

  //  사내 공개 켜기·끄기(?on=1) · 바깥 사람용 링크(?days=7&max=0) — 파일(/pub/<열쇠>)·폴더(/pub/g/<열쇠>) 같은 길
  function target(req) {
    if (req.params.kind === 'g') { const g = ID.test(req.params.id) && groups.get(req.params.id); return g && (g.owner === req.bf.id || req.bf.admin) ? { o: g, g: true } : null; }
    const m = ID.test(req.params.id) && files.get(req.params.id);
    return m && canEdit(req.bf, m) && !groupOf(m) ? { o: m, g: false } : null;
  }
  const saveT = (t) => (t.g ? saveG(t.o) : save(t.o));
  const viewT = (t, u) => (t.g ? gview(t.o, u) : view(t.o, u));
  const onPub = (req, res) => {
    const t = target(req);
    if (!t) return res.status(404).json({ error: '없는 파일입니다' });
    t.o.pub = req.query.on === '1';
    saveT(t).then(() => res.json({ file: viewT(t, req.bf) }));
  };
  const onShare = (req, res) => {
    const t = target(req);
    if (!t) return res.status(404).json({ error: '없는 파일입니다' });
    if (t.o.state !== 'done') return res.status(409).json({ error: '다 올린 다음에 링크를 만들 수 있습니다' });
    const days = Math.min(SHARE_DAYS_MAX, Math.max(1, Number(req.query.days) || 7));
    const max = Math.max(0, Math.min(1000, Number(req.query.max) || 0));
    const s = { tok: crypto.randomBytes(24).toString('base64url'), exp: Date.now() + days * DAY, max, used: 0, by: req.bf.name, t0: Date.now() };
    (t.o.shares = t.o.shares || []).push(s);
    saveT(t).then(() => res.json({ file: viewT(t, req.bf), tok: s.tok }));
  };
  const offShare = (req, res) => {
    const t = target(req);
    if (!t) return res.status(404).json({ error: '없는 파일입니다' });
    t.o.shares = (t.o.shares || []).filter((s) => s.tok !== req.params.tok);
    saveT(t).then(() => res.json({ file: viewT(t, req.bf) }));
  };
  app.post('/bigfile/api/pub/:id', apiAuth, onPub);
  app.post('/bigfile/api/pub/:kind/:id', apiAuth, onPub);
  app.post('/bigfile/api/share/:id', apiAuth, onShare);
  app.post('/bigfile/api/share/:kind/:id', apiAuth, (req, res, next) => (req.params.kind === 'g' ? onShare(req, res) : next()));
  app.delete('/bigfile/api/share/g/:id/:tok', apiAuth, (req, res) => { req.params.kind = 'g'; offShare(req, res); });
  app.delete('/bigfile/api/share/:id/:tok', apiAuth, offShare);

  // ── 🔍 검사 — 서버가 디스크의 파일을 처음부터 끝까지 다시 읽는다 ──────────────
  //   POST /bigfile/api/verify/<열쇠>   검사 시작(?again=1 이면 지난 결과가 있어도 다시)
  //   GET  /bigfile/api/verify/<열쇠>   { state:'work', done, size, wait } | { state:'done', result } | { state:'fail', msg }
  //   POST·GET /bigfile/api/gverify/<폴더>   폴더 안 파일을 모두(한 번에 하나씩 줄 서서) — 빠진 파일·틀린 파일을 모아 알려 준다
  //   GET  /bigfile/api/crcs/<열쇠>     조각별 CRC32(받는 쪽이 조각마다 맞춰 본다)
  //   ⚠ 디스크를 통째로 읽으니(50GB 면 몇 분) 한 번에 하나씩, 나머지는 줄을 선다. 결과는 정보에 남겨 다시 읽지 않는다.
  const vjobs = new Map(), vq = [];
  let vrun = 0;
  function startVerify(m) {
    const j0 = vjobs.get(m.id);
    if (j0 && j0.state === 'work') return j0;
    const j = { state: 'work', done: 0, size: m.size, wait: true, t0: Date.now() };
    vjobs.set(m.id, j); vq.push(m.id); pump();
    return j;
  }
  function pump() {
    while (vrun < 1 && vq.length) {
      const id = vq.shift(), m = files.get(id), j = vjobs.get(id);
      if (!m || !j) { vjobs.delete(id); continue; }
      vrun++; j.wait = false; j.t0 = Date.now();
      verifyFile(m, j).then((r) => { j.state = 'done'; j.result = r; m.verify = r; return save(m); },
        (e) => { j.state = 'fail'; j.msg = String((e && e.message) || e); })
        .then(() => { vrun--; pump(); setTimeout(() => { if (vjobs.get(id) === j) vjobs.delete(id); }, 600000).unref(); });
    }
  }
  function verifyFile(m, j) {
    return new Promise((ok, no) => {
      fs.stat(binOf(m.id), (e, st) => {
        if (e) return no(new Error('서버 디스크에서 파일을 찾지 못했습니다'));
        const sha = crypto.createHash('sha256'), disk = Buffer.alloc(m.n * 4);
        let pos = 0, whole = 0, cc = 0, ci = 0;
        const rs = fs.createReadStream(binOf(m.id), { highWaterMark: MB });
        rs.on('data', (b) => {
          sha.update(b); whole = crc32(b, whole);
          let o = 0;
          while (o < b.length && ci < m.n) {
            const end = Math.min(b.length, o + ((ci + 1) * m.chunk - pos));
            const part = b.subarray(o, end);
            cc = crc32(part, cc); pos += part.length; o = end;
            if (pos === (ci + 1) * m.chunk || pos === m.size) { disk.writeUInt32LE(cc >>> 0, ci * 4); cc = 0; ci++; }
          }
          j.done = Math.min(pos, m.size);
        });
        rs.on('error', no);
        rs.on('end', () => {
          const bad = [];
          let compared = 0, filled = 0;
          for (let i = 0; i < m.n; i++) {
            const known = (m.ck[i >> 3] >> (i & 7)) & 1;
            if (!known) { m.crcs.writeUInt32LE(disk.readUInt32LE(i * 4), i * 4); m.ck[i >> 3] |= 1 << (i & 7); filled++; continue; }
            compared++;
            if (m.crcs.readUInt32LE(i * 4) !== disk.readUInt32LE(i * 4)) bad.push(i);
          }
          const ms = Date.now() - j.t0;
          ok({
            ok: !bad.length && st.size === m.size, at: Date.now(), ms,
            name: m.name, size: m.size, disk: st.size, n: m.n, chunk: m.chunk,
            compared, filled, badCount: bad.length, bad: bad.slice(0, 50),
            crc: hex8(whole), sha256: sha.digest('hex'),
          });
        });
      });
    });
  }
  app.post('/bigfile/api/verify/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canSee(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    if (m.state !== 'done') return res.status(409).json({ error: '다 올린 다음에 검사할 수 있습니다' });
    if (m.verify && req.query.again !== '1') return res.json({ state: 'done', result: m.verify });
    const j = startVerify(m);
    res.json({ state: 'work', done: j.done, size: m.size, wait: j.wait ? vq.indexOf(m.id) + 1 : 0 });
  });
  app.get('/bigfile/api/verify/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canSee(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    const j = vjobs.get(m.id);
    if (j && j.state === 'work') return res.json({ state: 'work', done: j.done, size: m.size, wait: j.wait ? vq.indexOf(m.id) + 1 : 0 });
    if (j && j.state === 'fail') return res.json({ state: 'fail', msg: j.msg });
    if (m.verify) return res.json({ state: 'done', result: m.verify });
    res.json({ state: 'none' });
  });
  //  폴더 검사 — 목록표의 파일마다: 서버에 있나 · 크기 · 디스크 다시 읽은 조각 CRC · 전체 CRC
  function gstatus(g, kick) {
    let total = 0, done = 0, work = false, okc = 0, wait = 0;
    const bad = [], missing = [];
    for (const e of fileEntries(g)) {
      total += e.s;
      const m = e.id && files.get(e.id);
      if (!m || m.state !== 'done' || m.size !== e.s) { missing.push(e.p); continue; }
      const j = vjobs.get(m.id);
      if (j && j.state === 'work') { work = true; done += j.done || 0; if (j.wait) wait++; continue; }
      if (j && j.state === 'fail') { bad.push({ p: e.p, msg: j.msg }); done += e.s; continue; }
      if (!m.verify) { if (kick) startVerify(m); work = true; continue; }
      done += e.s;
      const c = wholeCrc(m);
      if (m.verify.ok && (!c || m.verify.crc === c)) okc++;
      else bad.push({ p: e.p, id: m.id, badCount: m.verify.badCount, bad: m.verify.bad, disk: m.verify.disk, size: m.size, crc: m.verify.crc, want: c });
    }
    const r = { state: work ? 'work' : 'done', done, total, files: g.nfiles, dirs: g.ndirs, ok: okc, wait,
      badCount: bad.length, bad: bad.slice(0, 200), missingCount: missing.length, missing: missing.slice(0, 200) };
    if (!work) {
      const v = { ok: !bad.length && !missing.length, at: Date.now() };
      if (!g.v || g.v.ok !== v.ok) { g.v = v; saveG(g); }
    }
    return r;
  }
  app.post('/bigfile/api/gverify/:gid', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !canSeeG(req.bf, g)) return res.status(404).json({ error: '없는 폴더입니다' });
    if (req.query.again === '1') for (const e of fileEntries(g)) { const m = e.id && files.get(e.id); if (m && m.state === 'done') startVerify(m); }
    res.json(gstatus(g, true));
  });
  app.get('/bigfile/api/gverify/:gid', apiAuth, (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !canSeeG(req.bf, g)) return res.status(404).json({ error: '없는 폴더입니다' });
    res.json(gstatus(g, true));
  });
  app.get('/bigfile/api/crcs/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.state !== 'done' || !canSee(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    if (!ckAll(m)) return res.json({ missing: true });
    res.json({ size: m.size, n: m.n, chunk: m.chunk, crcs: m.crcs.toString('base64'), crc: wholeCrc(m), sha256: m.verify ? m.verify.sha256 : '' });
  });

  // ── 받기 ──────────────────────────────────────────────────────────
  const dlFile = (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.state !== 'done' || !canSee(req.bf, m)) return res.status(404).send('없는 파일입니다.');
    send(req, res, m, null);
  };
  app.get('/bigfile/api/file/:id/dl', apiAuth, dlFile);
  app.head('/bigfile/api/file/:id/dl', apiAuth, dlFile);
  //  폴더째 ZIP — 크기 제한 없음, 이어 받기 됨
  const dlZip = (req, res) => {
    const g = ID.test(req.params.gid) && groups.get(req.params.gid);
    if (!g || !canSeeG(req.bf, g)) return res.status(404).send('없는 폴더입니다.');
    sendZip(req, res, g, null);
  };
  app.get('/bigfile/api/group/:gid/zip', apiAuth, dlZip);
  app.head('/bigfile/api/group/:gid/zip', apiAuth, dlZip);

  //  링크로 받기 — 로그인 없이
  function byToken(tok) {
    if (!TOK.test(tok)) return null;
    const live = (s) => s.exp > Date.now() && (!s.max || (s.used || 0) < s.max);
    for (const m of files.values()) {
      if (m.state !== 'done') continue;
      const s = (m.shares || []).find((x) => x.tok === tok);
      if (s) return { m, s, ok: live(s) };
    }
    for (const g of groups.values()) {
      if (g.state !== 'done') continue;
      const s = (g.shares || []).find((x) => x.tok === tok);
      if (s) return { g, s, ok: live(s) };
    }
    return null;
  }
  app.get('/bigfile/s/:tok', (req, res) => {
    const r = byToken(req.params.tok);
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Robots-Tag', 'noindex');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    if (!r || !r.ok) return res.status(r ? 410 : 404).send(sharePage(null, r ? '링크 기한이 지났거나 받을 수 있는 횟수를 다 썼습니다.' : '없는 링크입니다.'));
    res.send(sharePage(r));
  });
  const dlByToken = (req, res) => {
    const r = byToken(req.params.tok);
    if (!r || !r.ok) return res.status(r ? 410 : 404).send('링크 기한이 지났거나 없는 링크입니다.');
    if (r.g) return sendZip(req, res, r.g, r.s);
    send(req, res, r.m, r.s);
  };
  app.get('/bigfile/s/:tok/dl', dlByToken);
  app.head('/bigfile/s/:tok/dl', dlByToken);

  //  Range 한 구간 — 맞지 않으면 416 을 보내고 null
  function rangeOf(req, res, size, etag) {
    let start = 0, end = size - 1, part = false;
    const rg = req.headers.range, ifr = req.headers['if-range'];
    if (rg && (!ifr || ifr === etag) && size > 0) {
      const mm = /^bytes=(\d*)-(\d*)$/.exec(String(rg).trim());
      if (!mm || (mm[1] === '' && mm[2] === '')) { res.setHeader('Content-Range', 'bytes */' + size); res.status(416).end(); return null; }
      if (mm[1] === '') { start = Math.max(0, size - Number(mm[2])); } else { start = Number(mm[1]); if (mm[2] !== '') end = Math.min(end, Number(mm[2])); }
      if (start > end || start >= size) { res.setHeader('Content-Range', 'bytes */' + size); res.status(416).end(); return null; }
      part = true;
    }
    return { start, end, part };
  }
  function headers(res, name, size, etag, when, r) {
    const ascii = name.replace(/[^\x20-\x7e]/g, '_').replace(/["\\]/g, '_');
    res.setHeader('Content-Type', 'application/octet-stream');        //  올린 HTML 이 포털 안에서 열리지 않게 — 늘 내려받기
    res.setHeader('Content-Disposition', 'attachment; filename="' + ascii + '"; filename*=UTF-8\'\'' + encodeURIComponent(name));
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Accept-Ranges', 'bytes');
    res.setHeader('ETag', etag);
    res.setHeader('Last-Modified', new Date(when).toUTCString());
    res.setHeader('Cache-Control', 'private, no-transform');
    res.setHeader('Content-Length', String(size ? r.end - r.start + 1 : 0));
    if (r.part) res.setHeader('Content-Range', 'bytes ' + r.start + '-' + r.end + '/' + size);
    res.status(r.part ? 206 : 200);
  }
  //  흘려 보내기 — 파일 하나
  function send(req, res, m, share) {
    const file = binOf(m.id);
    fs.stat(file, (e, st) => {
      if (e) return res.status(404).send('파일이 서버에서 사라졌습니다.');
      const size = st.size, etag = '"' + m.id.slice(0, 16) + '-' + size.toString(36) + '"';
      const r = rangeOf(req, res, size, etag);
      if (!r) return;
      headers(res, m.name, size, etag, m.t1 || m.t0, r);
      if (req.method === 'HEAD') return res.end();
      //  받은 횟수 — 처음부터 받을 때만 센다(이어 받기는 안 셈)
      if (r.start === 0) {
        m.dl = (m.dl || 0) + 1;
        if (share) share.used = (share.used || 0) + 1;
        save(m);
      }
      if (!size) return res.end();
      pipeline(fs.createReadStream(file, { start: r.start, end: r.end, highWaterMark: MB }), res, () => {});
    });
  }

  // ── ZIP — 압축 없이(store) 묶기. CRC·크기를 다 알고 있어 묶음 모양이 늘 같다 → 길이를 미리 알고 Range 가 된다 ──
  //   4GB 넘는 파일·묶음은 ZIP64. 이름은 UTF-8 표시(윈도 탐색기에서 한글이 안 깨짐). 빈 폴더도 넣는다.
  function dosTime(ms) {
    const d = new Date(ms || Date.now());
    const y = Math.max(1980, d.getFullYear());
    return { time: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1), date: ((y - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate() };
  }
  function zipLayout(g) {
    const segs = [], cen = [];
    let off = 0, z64 = false;
    const top = g.name;
    for (const e of g.entries) {
      const m = e.d ? null : files.get(e.id);
      if (!e.d && (!m || m.state !== 'done')) throw new Error('아직 다 올라오지 않은 파일이 있습니다: ' + e.p);
      const size = m ? m.size : 0, crc = m ? parseInt(wholeCrc(m) || '0', 16) >>> 0 : 0;
      if (m && !wholeCrc(m)) throw new Error('CRC 를 모르는 파일이 있습니다(검사를 먼저): ' + e.p);
      const name = Buffer.from(top + '/' + e.p + (e.d ? '/' : ''), 'utf8');
      const big = size >= 0xFFFFFFFF, farOff = off >= 0xFFFFFFFF;
      const t = dosTime(e.lm || g.t0);
      //  지역 머리
      const lx = big ? Buffer.alloc(20) : Buffer.alloc(0);
      if (big) { lx.writeUInt16LE(1, 0); lx.writeUInt16LE(16, 2); lx.writeBigUInt64LE(BigInt(size), 4); lx.writeBigUInt64LE(BigInt(size), 12); }
      const lh = Buffer.alloc(30);
      lh.writeUInt32LE(0x04034b50, 0); lh.writeUInt16LE(big ? 45 : 20, 4); lh.writeUInt16LE(0x0800, 6); lh.writeUInt16LE(0, 8);
      lh.writeUInt16LE(t.time, 10); lh.writeUInt16LE(t.date, 12); lh.writeUInt32LE(crc, 14);
      lh.writeUInt32LE(big ? 0xFFFFFFFF : size, 18); lh.writeUInt32LE(big ? 0xFFFFFFFF : size, 22);
      lh.writeUInt16LE(name.length, 26); lh.writeUInt16LE(lx.length, 28);
      const head = Buffer.concat([lh, name, lx]);
      segs.push({ len: head.length, buf: head });
      if (size) segs.push({ len: size, id: m.id });
      //  가운데 목록 머리
      const cx = [];
      if (big) { const b = Buffer.alloc(16); b.writeBigUInt64LE(BigInt(size), 0); b.writeBigUInt64LE(BigInt(size), 8); cx.push(b); }
      if (farOff) { const b = Buffer.alloc(8); b.writeBigUInt64LE(BigInt(off), 0); cx.push(b); }
      let cxb = Buffer.concat(cx);
      if (cxb.length) { const h = Buffer.alloc(4); h.writeUInt16LE(1, 0); h.writeUInt16LE(cxb.length, 2); cxb = Buffer.concat([h, cxb]); z64 = true; }
      const ch = Buffer.alloc(46);
      //  만든 곳 = 유닉스(3) — 윈도·맥·unzip 모두 UTF-8 이름을 그대로 읽는다(MS-DOS(0)로 두면 ZIP64 항목 이름을 옛 글자로 바꾸는 풀개가 있다)
      ch.writeUInt32LE(0x02014b50, 0); ch.writeUInt16LE((3 << 8) | 45, 4); ch.writeUInt16LE(cxb.length ? 45 : 20, 6);
      ch.writeUInt16LE(0x0800, 8); ch.writeUInt16LE(0, 10); ch.writeUInt16LE(t.time, 12); ch.writeUInt16LE(t.date, 14);
      ch.writeUInt32LE(crc, 16); ch.writeUInt32LE(big ? 0xFFFFFFFF : size, 20); ch.writeUInt32LE(big ? 0xFFFFFFFF : size, 24);
      ch.writeUInt16LE(name.length, 28); ch.writeUInt16LE(cxb.length, 30); ch.writeUInt16LE(0, 32); ch.writeUInt16LE(0, 34); ch.writeUInt16LE(0, 36);
      ch.writeUInt32LE(e.d ? ((0o40755 << 16) | 0x10) >>> 0 : (0o100644 << 16) >>> 0, 38); ch.writeUInt32LE(farOff ? 0xFFFFFFFF : off, 42);
      cen.push(Buffer.concat([ch, name, cxb]));
      off += head.length + size;
    }
    const cd = Buffer.concat(cen), cdOff = off, count = cen.length;
    if (count >= 0xFFFF || cdOff >= 0xFFFFFFFF || cd.length >= 0xFFFFFFFF) z64 = true;
    const tail = [];
    if (z64) {
      const r = Buffer.alloc(56);
      r.writeUInt32LE(0x06064b50, 0); r.writeBigUInt64LE(44n, 4); r.writeUInt16LE(45, 12); r.writeUInt16LE(45, 14);
      r.writeUInt32LE(0, 16); r.writeUInt32LE(0, 20); r.writeBigUInt64LE(BigInt(count), 24); r.writeBigUInt64LE(BigInt(count), 32);
      r.writeBigUInt64LE(BigInt(cd.length), 40); r.writeBigUInt64LE(BigInt(cdOff), 48);
      const l = Buffer.alloc(20);
      l.writeUInt32LE(0x07064b50, 0); l.writeUInt32LE(0, 4); l.writeBigUInt64LE(BigInt(cdOff + cd.length), 8); l.writeUInt32LE(1, 16);
      tail.push(r, l);
    }
    const eo = Buffer.alloc(22);
    eo.writeUInt32LE(0x06054b50, 0); eo.writeUInt16LE(0, 4); eo.writeUInt16LE(0, 6);
    eo.writeUInt16LE(Math.min(count, 0xFFFF), 8); eo.writeUInt16LE(Math.min(count, 0xFFFF), 10);
    eo.writeUInt32LE(Math.min(cd.length, 0xFFFFFFFF), 12); eo.writeUInt32LE(z64 ? 0xFFFFFFFF : cdOff, 16); eo.writeUInt16LE(0, 20);
    tail.push(eo);
    const end = Buffer.concat([cd, ...tail]);
    segs.push({ len: end.length, buf: end });
    return { segs, total: off + end.length };
  }
  async function* zipBytes(L, start, end) {
    let pos = 0;
    for (const s of L.segs) {
      const a = pos, b = pos + s.len; pos = b;
      if (b <= start) continue;
      if (a > end) break;
      const from = Math.max(start, a) - a, to = Math.min(end + 1, b) - a;
      if (s.buf) yield s.buf.subarray(from, to);
      else for await (const c of fs.createReadStream(binOf(s.id), { start: from, end: to - 1, highWaterMark: MB })) yield c;
    }
  }
  function sendZip(req, res, g, share) {
    if (g.state !== 'done') return res.status(409).send('폴더를 아직 다 올리지 않았습니다.');
    let L;
    try { L = zipLayout(g); } catch (e) { return res.status(409).send(String(e.message || e)); }
    const etag = '"z' + g.gid.slice(0, 15) + '-' + L.total.toString(36) + '-' + (g.t1 || 0).toString(36) + '"';
    const r = rangeOf(req, res, L.total, etag);
    if (!r) return;
    headers(res, g.name + '.zip', L.total, etag, g.t1 || g.t0, r);
    if (req.method === 'HEAD') return res.end();
    if (r.start === 0) { g.dl = (g.dl || 0) + 1; if (share) share.used = (share.used || 0) + 1; saveG(g); }
    pipeline(Readable.from(zipBytes(L, r.start, r.end)), res, () => {});
  }

  function sharePage(r, msg) {
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    let body;
    if (!r) body = '<div class="nm">' + esc(msg) + '</div><div class="sub">보낸 분께 새 링크를 부탁하세요.</div>';
    else {
      const o = r.g || r.m;
      const until = '<div class="sub">' + esc(new Date(r.s.exp).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })) + ' 까지' +
        (r.s.max ? ' · ' + (r.s.max - (r.s.used || 0)) + '번 더 받을 수 있음' : '') + '</div>';
      body = '<div class="nm">' + esc(o.name) + (r.g ? ' (폴더)' : '') + '</div><div class="sub">' +
        esc(human(r.g ? r.g.total : r.m.size)) + (r.g ? ' · 파일 ' + r.g.nfiles + '개' : '') + ' · 올린 사람 ' + esc(o.ownerName) + '</div>' +
        '<a class="btn" href="/bigfile/s/' + esc(r.s.tok) + '/dl">' + (r.g ? 'ZIP 으로 내려받기' : '내려받기') + '</a>' + until;
      if (r.g) {
        const fl = fileEntries(r.g);
        body += '<table>' + fl.slice(0, 500).map((e) => '<tr><td>' + esc(e.p) + '</td><td class="r">' + esc(human(e.s)) + '</td></tr>').join('') + '</table>' +
          (fl.length > 500 ? '<div class="sub">… 그 밖에 ' + (fl.length - 500) + '개</div>' : '');
      }
    }
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<meta name="robots" content="noindex"><title>파일 받기 — 한일</title><style>' +
      'body{margin:0;font:13px/1.5 "Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif;background:#fff;color:#222}' +
      '.c{max-width:560px;margin:40px auto;padding:0 16px}.c h1{font-size:15px;border-bottom:2px solid #222;padding-bottom:6px;margin:0 0 14px}' +
      '.nm{font-weight:bold;word-break:break-all}.sub{color:#777;font-size:12px;margin:6px 0}' +
      '.btn{display:inline-block;margin:12px 0 6px;padding:6px 18px;background:#2f5bd3;color:#fff;text-decoration:none;border-radius:2px}' +
      'table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}td{border-top:1px solid #ddd;padding:3px 4px;word-break:break-all}td.r{text-align:right;white-space:nowrap;color:#777}' +
      '</style></head><body><div class="c"><h1>파일 받기</h1>' + body + '</div></body></html>';
  }

  // ── 치우기 — 한 시간마다 ─────────────────────────────────────────
  function sweep() {
    const now = Date.now();
    const trimShares = (o, sv) => { const b = (o.shares || []).length; o.shares = (o.shares || []).filter((s) => s.exp > now); if (o.shares.length !== b) sv(o); };
    for (const g of [...groups.values()]) {
      if (g.state !== 'done' && now - (g.tl || g.t0) > PART_DAYS * DAY) { removeG(g); continue; }
      if (g.state === 'done' && KEEP_DAYS && now - (g.t1 || g.t0) > KEEP_DAYS * DAY) { removeG(g); continue; }
      trimShares(g, saveG);
    }
    for (const m of [...files.values()]) {
      if (m.group && !groups.has(m.group)) { if (m.state !== 'done') { remove(m); continue; } delete m.group; save(m); }   //  폴더 정보가 사라진 파일
      if (m.group) continue;                              //  폴더 안 파일은 폴더가 정한다
      if (m.state !== 'done' && now - (m.tl || m.t0) > PART_DAYS * DAY) { remove(m); continue; }
      if (m.state === 'done' && KEEP_DAYS && now - (m.t1 || m.t0) > KEEP_DAYS * DAY) { remove(m); continue; }
      trimShares(m, save);
    }
    //  정보 없이 남은 .bin(정보를 지우다 꺼진 것)
    fs.readdir(DATA, (e, list) => {
      (list || []).forEach((f) => { const id = f.replace(/\.bin$/, ''); if (ID.test(id) && !files.has(id)) fs.rm(path.join(DATA, f), { force: true }, () => {}); });
    });
  }
  setTimeout(sweep, 10000).unref();
  setInterval(sweep, 3600000).unref();

  return { files, groups, sweep, store: STORE };
};

function human(b) {
  if (b < 1024) return b + ' B';
  const u = ['KB', 'MB', 'GB', 'TB']; let i = -1;
  do { b /= 1024; i++; } while (b >= 1024 && i < u.length - 1);
  return b.toFixed(b < 10 ? 2 : b < 100 ? 1 : 0) + ' ' + u[i];
}
module.exports.crc32 = crc32;
module.exports.crcCombineAll = crcCombineAll;
