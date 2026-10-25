//  📦 대용량 파일 올리기·받기 — 포털에 넣는 조각
//   넣는 법: 이 파일과 bigfile.html 을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./bigfile-route')(app);
//   여는 주소: /bigfile   (→ /bigfile/view — 포털 공통 조각이 안 끼는 주소)
//
//   ⭐ 올리기: 파일을 조각(기본 8MB)으로 잘라 3개씩 함께 보낸다. 조각마다 CRC32 를 맞춰 보고, 틀리면 그 조각만 다시.
//      끊겨도(망·창 닫음·새로고침) 같은 파일을 다시 고르면 **받은 조각 다음부터** 이어 올린다.
//   ⭐ 받기: Range(이어 받기)를 받는다 — 브라우저·폰 앱 내려받기가 끊겨도 이어 받는다. 메모리에 올리지 않고 흘려 보낸다.
//   ⭐ 공유: 사내 공개(로그인한 직원 누구나) · 바깥 사람용 링크(기한·횟수 제한, 로그인 없이).
//   ⚠ 디스크에는 파일 이름을 쓰지 않는다(<열쇠>.bin) — 이름은 meta/<열쇠>.json 에만. 이상한 이름으로 폴더를 벗어날 수 없다.
//   ⚠ 앞에 nginx 가 있으면 조각 크기보다 크게: client_max_body_size 16m;  (기본 1m 이면 413 으로 안 올라간다)
//   ⚠ 몸통(body)을 JSON 으로 받지 않는다 — 포털의 express.json() 이 있든 없든 돌게, 값은 모두 주소 꼬리(?a=)로 받는다.
'use strict';
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { pipeline, Transform } = require('stream');

const MB = 1048576, GB = 1073741824, DAY = 86400000;

//  CRC32 — 브라우저(bigfile.html)와 같은 계산
const CRC_T = (() => { const t = new Int32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c; } return t; })();
function crc32js(buf, prev) { let c = ~(prev || 0); for (let i = 0; i < buf.length; i++) c = CRC_T[(c ^ buf[i]) & 0xff] ^ (c >>> 8); return ~c >>> 0; }
//  Node 20.15·22.2 부터는 zlib.crc32(빠름, 같은 값)가 있다 — 서버 검사가 디스크 속도로 돈다. 없으면 위의 것
const crc32 = typeof require('zlib').crc32 === 'function' ? (buf, prev) => require('zlib').crc32(buf, prev || 0) >>> 0 : crc32js;

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
  const PAR = ctx.parallel || 3;                         //  한 파일을 몇 조각씩 함께 보내나
  const MAX = (ctx.maxGB || 50) * GB;                    //  파일 하나 최대
  const QUOTA = (ctx.quotaGB || 0) * GB;                 //  한 사람 합계(0 = 제한 없음)
  const KEEP_FREE = (ctx.keepFreeGB === undefined ? 5 : ctx.keepFreeGB) * GB;   //  디스크를 이만큼은 비워 둔다
  const PART_DAYS = ctx.partialDays || 7;                //  다 못 올린 것은 마지막 조각 뒤 n일에 지운다
  const KEEP_DAYS = ctx.keepDays || 0;                   //  다 올린 것을 n일 뒤 지운다(0 = 안 지움)
  const SHARE_DAYS_MAX = ctx.shareDaysMax || 30;
  const META = path.join(STORE, 'meta'), DATA = path.join(STORE, 'data');
  fs.mkdirSync(META, { recursive: true });
  fs.mkdirSync(DATA, { recursive: true });

  const ID = /^[0-9a-f]{32}$/, TOK = /^[0-9A-Za-z_-]{32}$/;
  const files = new Map();                               //  열쇠 → 정보(+ got: 받은 조각 Buffer 비트)
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
  //  조각마다 CRC32 를 적어 둔다(crcs: 4바이트씩, ck: 적어 둔 조각 비트) — 끝난 뒤 검사·받을 때 검사에 쓴다
  //  ⚠ 이 기능 전에 올린 파일은 crcs 가 없다 → 처음 검사할 때 디스크에서 읽어 채운다
  function fixCrc(m) {
    m.crcs = Buffer.from(typeof m.crcs === 'string' ? m.crcs : '', 'base64');
    m.ck = Buffer.from(typeof m.ck === 'string' ? m.ck : '', 'base64');
    if (m.crcs.length !== m.n * 4) m.crcs = Buffer.alloc(m.n * 4);
    if (m.ck.length !== Math.ceil(m.n / 8)) m.ck = Buffer.alloc(Math.ceil(m.n / 8));
  }
  const ckAll = (m) => { for (let i = 0; i < m.n; i++) if (!((m.ck[i >> 3] >> (i & 7)) & 1)) return false; return true; };
  const binOf = (id) => path.join(DATA, id + '.bin');
  const has = (m, i) => (m.got[i >> 3] >> (i & 7)) & 1;
  const gotCount = (m) => { let c = 0; for (let i = 0; i < m.n; i++) c += has(m, i); return c; };
  const chunkLen = (m, i) => Math.min(m.chunk, m.size - i * m.chunk);
  //  정보는 바뀔 때마다 파일에 — 같은 파일은 차례로(겹쳐 쓰면 깨진다), 임시 파일에 쓰고 이름 바꾸기
  const saving = new Map();
  function save(m) {
    const prev = saving.get(m.id) || Promise.resolve();
    const p = prev.then(() => new Promise((ok) => {
      if (!files.has(m.id)) return ok();
      const out = Object.assign({}, m, { got: m.got.toString('base64'), crcs: m.crcs.toString('base64'), ck: m.ck.toString('base64') });
      const f = path.join(META, m.id + '.json'), tmp = f + '.' + process.pid + '.tmp';
      fs.writeFile(tmp, JSON.stringify(out), (e) => { if (e) return ok(); fs.rename(tmp, f, () => ok()); });
    }));
    saving.set(m.id, p);
    p.then(() => { if (saving.get(m.id) === p) saving.delete(m.id); });
    return p;
  }
  function remove(m) {
    files.delete(m.id);
    fs.rm(binOf(m.id), { force: true }, () => {});
    fs.rm(path.join(META, m.id + '.json'), { force: true }, () => {});
  }
  const canSee = (u, m) => m.owner === u.id || u.admin || (m.pub && m.state === 'done');
  const canEdit = (u, m) => m.owner === u.id || u.admin;
  const view = (m, u) => ({
    id: m.id, name: m.name, size: m.size, type: m.type, state: m.state, owner: m.ownerName, mine: m.owner === u.id,
    t0: m.t0, t1: m.t1 || 0, pub: !!m.pub, dl: m.dl || 0, got: m.state === 'done' ? m.n : gotCount(m), n: m.n,
    v: m.verify ? { ok: m.verify.ok, at: m.verify.at } : null,
    shares: canEdit(u, m) ? (m.shares || []).map((s) => ({ tok: s.tok, exp: s.exp, max: s.max, used: s.used || 0 })) : [],
  });
  function diskFree() {
    try { const s = fs.statfsSync(STORE); return s.bavail * s.bsize; } catch (e) { return -1; }   //  Node 18.15 전에는 모름
  }
  const usedBy = (uid) => { let s = 0; for (const m of files.values()) if (m.owner === uid) s += m.size; return s; };
  //  아직 덜 온 바이트(다 올라오면 디스크를 더 쓸 몫)
  const pending = () => { let s = 0; for (const m of files.values()) if (m.state !== 'done') s += m.size - Math.min(m.size, gotCount(m) * m.chunk); return s; };

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

  //  ?all=1 — 관리자는 모든 사람 것
  app.get('/bigfile/api/list', apiAuth, (req, res) => {
    const u = req.bf, all = u.admin && req.query.all === '1';
    const out = [];
    for (const m of files.values()) if (all ? true : (m.owner === u.id || (m.pub && m.state === 'done'))) out.push(view(m, u));
    out.sort((a, b) => (b.t1 || b.t0) - (a.t1 || a.t0));
    res.json({ files: out });
  });

  //  올리기 시작 — 같은 사람이 같은 파일(이름·크기·수정 시각)을 올리다 말았으면 그것을 이어 간다
  app.post('/bigfile/api/init', apiAuth, (req, res) => {
    const u = req.bf;
    const name = String(req.query.name || '').replace(/[\u0000-\u001f\u007f]/g, '').replace(/[\\/]/g, '_').trim().slice(0, 255);
    const size = Number(req.query.size), lm = Number(req.query.lm) || 0;
    const type = String(req.query.type || '').slice(0, 100);
    if (!name) return res.status(400).json({ error: '파일 이름이 없습니다' });
    if (!Number.isSafeInteger(size) || size < 0) return res.status(400).json({ error: '파일 크기가 이상합니다' });
    if (size > MAX) return res.status(413).json({ error: '파일 하나는 ' + (MAX / GB) + 'GB 까지 올릴 수 있습니다' });
    for (const m of files.values()) {
      if (m.owner === u.id && m.state !== 'done' && m.name === name && m.size === size && m.lm === lm) {
        return res.json({ id: m.id, chunk: m.chunk, n: m.n, have: m.got.toString('base64'), resumed: true });
      }
    }
    if (QUOTA && usedBy(u.id) + size > QUOTA) return res.status(413).json({ error: '내 자리(' + (QUOTA / GB) + 'GB)가 모자랍니다 — 안 쓰는 파일을 지워 주세요' });
    const free = diskFree();
    if (free >= 0 && free - pending() - size < KEEP_FREE) return res.status(507).json({ error: '서버 디스크 자리가 모자랍니다(남은 ' + (free / GB).toFixed(1) + 'GB)' });
    const n = Math.max(1, Math.ceil(size / CHUNK));
    const m = { id: crypto.randomBytes(16).toString('hex'), name, size, type, lm, chunk: CHUNK, n, got: Buffer.alloc(Math.ceil(n / 8)),
      owner: u.id, ownerName: u.name, t0: Date.now(), tl: Date.now(), state: 'part', pub: false, shares: [], dl: 0 };
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
      save(m).then(() => { if (!res.headersSent) res.json({ ok: true }); });
    });
  });

  //  다 보냈다 — 빠진 조각이 없고 크기가 맞으면 끝
  app.post('/bigfile/api/done/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.owner !== req.bf.id) return res.status(404).json({ error: '올리던 파일이 없습니다' });
    if (m.state === 'done') return res.json({ file: view(m, req.bf) });
    const miss = [];
    for (let i = 0; i < m.n && miss.length < 50; i++) if (!has(m, i)) miss.push(i);
    if (miss.length) return res.status(409).json({ error: '빠진 조각이 있습니다', miss });
    fs.stat(binOf(m.id), (e, st) => {
      if (e || st.size !== m.size) return res.status(500).json({ error: '서버에 쌓인 크기가 맞지 않습니다' + (st ? '(' + st.size + '/' + m.size + ')' : '') });
      m.state = 'done'; m.t1 = Date.now();
      save(m).then(() => res.json({ file: view(m, req.bf) }));
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
    m.state = 'part'; m.tl = Date.now(); delete m.verify;
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
    remove(m);
    res.json({ ok: true });
  });

  //  사내 공개 켜기·끄기(?on=1)
  app.post('/bigfile/api/pub/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canEdit(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    m.pub = req.query.on === '1';
    save(m).then(() => res.json({ file: view(m, req.bf) }));
  });

  //  바깥 사람용 링크 — ?days=7&max=0(0 = 횟수 제한 없음)
  app.post('/bigfile/api/share/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canEdit(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    if (m.state !== 'done') return res.status(409).json({ error: '다 올린 다음에 링크를 만들 수 있습니다' });
    const days = Math.min(SHARE_DAYS_MAX, Math.max(1, Number(req.query.days) || 7));
    const max = Math.max(0, Math.min(1000, Number(req.query.max) || 0));
    const s = { tok: crypto.randomBytes(24).toString('base64url'), exp: Date.now() + days * DAY, max, used: 0, by: req.bf.name, t0: Date.now() };
    (m.shares = m.shares || []).push(s);
    save(m).then(() => res.json({ file: view(m, req.bf), tok: s.tok }));
  });
  app.delete('/bigfile/api/share/:id/:tok', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || !canEdit(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    m.shares = (m.shares || []).filter((s) => s.tok !== req.params.tok);
    save(m).then(() => res.json({ file: view(m, req.bf) }));
  });

  // ── 🔍 검사 — 서버가 디스크의 파일을 처음부터 끝까지 다시 읽는다 ──────────────
  //   POST /bigfile/api/verify/<열쇠>   검사 시작(?again=1 이면 지난 결과가 있어도 다시)
  //   GET  /bigfile/api/verify/<열쇠>   { state:'work', done, size, wait } | { state:'done', result } | { state:'fail', msg }
  //   GET  /bigfile/api/crcs/<열쇠>     조각별 CRC32(받는 쪽이 조각마다 맞춰 본다)
  //   결과: 크기(적어 둔 것 ↔ 디스크) · 조각별 CRC32(올릴 때 받은 값 ↔ 지금 디스크) · 전체 CRC32 · SHA-256
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
            crc: (whole >>> 0).toString(16).padStart(8, '0'), sha256: sha.digest('hex'),
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
  app.get('/bigfile/api/crcs/:id', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.state !== 'done' || !canSee(req.bf, m)) return res.status(404).json({ error: '없는 파일입니다' });
    if (!ckAll(m)) return res.json({ missing: true });
    res.json({ size: m.size, n: m.n, chunk: m.chunk, crcs: m.crcs.toString('base64'), crc: m.verify ? m.verify.crc : '', sha256: m.verify ? m.verify.sha256 : '' });
  });

  // ── 받기 ──────────────────────────────────────────────────────────
  app.get('/bigfile/api/file/:id/dl', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.state !== 'done' || !canSee(req.bf, m)) return res.status(404).send('없는 파일입니다.');
    send(req, res, m, null);
  });
  app.head('/bigfile/api/file/:id/dl', apiAuth, (req, res) => {
    const m = ID.test(req.params.id) && files.get(req.params.id);
    if (!m || m.state !== 'done' || !canSee(req.bf, m)) return res.status(404).end();
    send(req, res, m, null);
  });

  //  링크로 받기 — 로그인 없이
  function byToken(tok) {
    if (!TOK.test(tok)) return null;
    for (const m of files.values()) {
      if (m.state !== 'done') continue;
      const s = (m.shares || []).find((x) => x.tok === tok);
      if (s) return { m, s, ok: s.exp > Date.now() && (!s.max || (s.used || 0) < s.max) };
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
    send(req, res, r.m, r.s);
  };
  app.get('/bigfile/s/:tok/dl', dlByToken);
  app.head('/bigfile/s/:tok/dl', dlByToken);

  //  흘려 보내기 — Range 한 구간(이어 받기)을 받는다
  function send(req, res, m, share) {
    const file = binOf(m.id);
    fs.stat(file, (e, st) => {
      if (e) return res.status(404).send('파일이 서버에서 사라졌습니다.');
      const size = st.size, etag = '"' + m.id.slice(0, 16) + '-' + size.toString(36) + '"';
      let start = 0, end = size - 1, part = false;
      const rg = req.headers.range;
      const ifr = req.headers['if-range'];
      if (rg && (!ifr || ifr === etag) && size > 0) {
        const mm = /^bytes=(\d*)-(\d*)$/.exec(String(rg).trim());
        if (!mm || (mm[1] === '' && mm[2] === '')) { res.setHeader('Content-Range', 'bytes */' + size); return res.status(416).end(); }
        if (mm[1] === '') { start = Math.max(0, size - Number(mm[2])); } else { start = Number(mm[1]); if (mm[2] !== '') end = Math.min(end, Number(mm[2])); }
        if (start > end || start >= size) { res.setHeader('Content-Range', 'bytes */' + size); return res.status(416).end(); }
        part = true;
      }
      const ascii = m.name.replace(/[^\x20-\x7e]/g, '_').replace(/["\\]/g, '_');
      res.setHeader('Content-Type', 'application/octet-stream');        //  올린 HTML 이 포털 안에서 열리지 않게 — 늘 내려받기
      res.setHeader('Content-Disposition', 'attachment; filename="' + ascii + '"; filename*=UTF-8\'\'' + encodeURIComponent(m.name));
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.setHeader('Accept-Ranges', 'bytes');
      res.setHeader('ETag', etag);
      res.setHeader('Last-Modified', new Date(m.t1 || m.t0).toUTCString());
      res.setHeader('Cache-Control', 'private, no-transform');
      res.setHeader('Content-Length', String(size ? end - start + 1 : 0));
      if (part) res.setHeader('Content-Range', 'bytes ' + start + '-' + end + '/' + size);
      res.status(part ? 206 : 200);
      if (req.method === 'HEAD') return res.end();
      //  받은 횟수 — 처음부터 받을 때만 센다(이어 받기는 안 셈)
      if (start === 0) {
        m.dl = (m.dl || 0) + 1;
        if (share) share.used = (share.used || 0) + 1;
        save(m);
      }
      if (!size) return res.end();
      const rs = fs.createReadStream(file, { start, end, highWaterMark: MB });
      pipeline(rs, res, () => {});
    });
  }

  function sharePage(r, msg) {
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
    const body = r
      ? '<div class="nm">' + esc(r.m.name) + '</div><div class="sub">' + esc(human(r.m.size)) + ' · 올린 사람 ' + esc(r.m.ownerName) + '</div>' +
        '<a class="btn" href="/bigfile/s/' + esc(r.s.tok) + '/dl">⬇ 내려받기</a>' +
        '<div class="sub">' + esc(new Date(r.s.exp).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })) + ' 까지' +
        (r.s.max ? ' · ' + (r.s.max - (r.s.used || 0)) + '번 더 받을 수 있음' : '') + '</div>'
      : '<div class="nm">' + esc(msg) + '</div><div class="sub">보낸 분께 새 링크를 부탁하세요.</div>';
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<meta name="robots" content="noindex"><title>파일 받기 — 한일</title><style>' +
      'body{margin:0;font:15px/1.5 system-ui,"Malgun Gothic",sans-serif;background:#f3f5f9;color:#1d2433;display:flex;min-height:100vh;align-items:center;justify-content:center}' +
      '.c{background:#fff;border-radius:14px;box-shadow:0 4px 24px #0001;padding:28px 24px;max-width:440px;width:calc(100% - 32px);text-align:center}' +
      '.nm{font-weight:700;font-size:17px;word-break:break-all;margin:6px 0}.sub{color:#6a7385;font-size:13px;margin:8px 0}' +
      '.btn{display:inline-block;margin:14px 0 4px;padding:12px 28px;border-radius:10px;background:#1f5eff;color:#fff;text-decoration:none;font-weight:700}' +
      '@media (prefers-color-scheme:dark){body{background:#12151c;color:#e6e9f0}.c{background:#1b2030;box-shadow:none}.sub{color:#9aa3b5}}' +
      '</style></head><body><div class="c"><div style="font-size:34px">📦</div>' + body + '</div></body></html>';
  }

  // ── 치우기 — 한 시간마다 ─────────────────────────────────────────
  function sweep() {
    const now = Date.now();
    for (const m of [...files.values()]) {
      if (m.state !== 'done' && now - (m.tl || m.t0) > PART_DAYS * DAY) { remove(m); continue; }
      if (m.state === 'done' && KEEP_DAYS && now - (m.t1 || m.t0) > KEEP_DAYS * DAY) { remove(m); continue; }
      const before = (m.shares || []).length;
      m.shares = (m.shares || []).filter((s) => s.exp > now);
      if (m.shares.length !== before) save(m);
    }
    //  정보 없이 남은 .bin(정보를 지우다 꺼진 것)
    fs.readdir(DATA, (e, list) => {
      (list || []).forEach((f) => { const id = f.replace(/\.bin$/, ''); if (ID.test(id) && !files.has(id)) fs.rm(path.join(DATA, f), { force: true }, () => {}); });
    });
  }
  setTimeout(sweep, 10000).unref();
  setInterval(sweep, 3600000).unref();

  return { files, sweep, store: STORE };
};

function human(b) {
  if (b < 1024) return b + ' B';
  const u = ['KB', 'MB', 'GB', 'TB']; let i = -1;
  do { b /= 1024; i++; } while (b >= 1024 && i < u.length - 1);
  return b.toFixed(b < 10 ? 2 : b < 100 ? 1 : 0) + ' ' + u[i];
}
module.exports.crc32 = crc32;
