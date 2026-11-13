//  📠 받은 팩스 — 포털에 넣는 조각 (CimFAX 팩스 서버 → 포털)
//
//   어떻게 붙나
//     CimFAX 클라이언트(FaxBox)에는 「자동 내보내기」 기능이 있다. 팩스를 다 받으면 지정한 폴더에 PDF(또는 TIF)로 저장한다.
//     (분석 근거: docs/CimFAX_포털연동_분석.md 5.1.1 — FaxBox.exe 5022E 디컴파일)
//     이 조각은 그 폴더를 15초마다 살펴서 새 팩스를 포털에 등록하고, /fax 화면에서 보고·처리하게 한다.
//
//   넣는 법: 이 파일과 fax-page.html 을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./fax-route')(app, { inbox: '\\\\FAXPC\\fax-export' });
//
//   설정 (모두 생략 가능 — inbox 만 꼭 필요)
//     inbox      팩스가 떨어지는 폴더. 여러 곳이면 배열. (또는 환경 변수 FAX_INBOX, 여러 곳은 ; 로 구분)
//     dir        포털이 팩스를 보관하는 곳 (기본: 포털 폴더 옆 fax-store)
//     pollSec    폴더를 살피는 간격 초 (기본 15)
//     sinceDays  처음 켤 때 이 날수보다 오래된 파일은 건너뜀 (기본 30, 0 이면 전부)
//     after      등록한 원본 파일을 'keep'(그대로, 기본) | 'move'(inbox\_포털등록 으로 옮김) | 'delete'
//     view       누가 보나: 'all'(로그인한 직원 모두, 기본) | 'admin' | (user, fax) => true/false
//     route      담당자 자동 지정: { to: { 'CimFAX계정': '포털아이디' }, from: { '보낸번호 또는 이름': '포털아이디' } }
//                또는 (fax) => '포털아이디'
//     notify     새 팩스가 들어오면 부르는 함수: async (fax, { url }) => { … }  — 포털 쪽지·NOPS 알림을 여기서 보낸다
//     user       포털 세션에서 사용자를 꺼내는 함수 (기본: req.session.user 의 흔한 칸 이름을 본다 — 달력·대용량 조각과 같은 잣대)
//
//   API (모두 로그인 필요)
//     GET    /api/fax?status=new|seen|done|all&q=검색어&limit=50&before=<id>   목록 + 상태별 수
//     GET    /api/fax/count                       { new: 안 본 팩스 수 } — 메뉴 빨간 숫자용
//     GET    /api/fax/:id                         한 건
//     GET    /api/fax/:id/file                    팩스 파일 (PDF 는 화면에 바로, TIF 는 내려받기). ?download=1 이면 언제나 내려받기
//     PUT    /api/fax/:id                         { status?: 'new'|'seen'|'done', assignee?, memo? }
//     DELETE /api/fax/:id                         목록에서 숨김 (관리자만, 파일은 남김)
//     GET    /api/fax/admin/status                폴더 상태·마지막 검사·오류 (관리자만)
//     GET    /fax                                 받은 팩스 화면
//
//   📤 보내기 — device 를 넣으면 켜진다 (장비와 직접 통신: cimfax-client.js · PDF→팩스 TIFF 는 Ghostscript)
//     device     { host: '192.168.0.50', user: 'CimFAX계정', password: '비밀번호',
//                  ghostscript?: 'C:/Program Files/gs/gs10.04.0/bin/gswin64c.exe', dryRun?: true(시험: 장비로 안 보냄),
//                  priority?: 2, quality?: 1, dialTotal?: 5, serverId?: '장비ID 확인', portBase?: 3001 }
//                (또는 환경 변수 FAX_DEVICE_HOST · FAX_DEVICE_USER · FAX_DEVICE_PASSWORD)
//     sendBy     누가 보내나: 'all'(기본) | 'admin' | (user) => true/false
//     sentView   보낸 목록: 자기 것만(기본) | 'all' — 관리자는 언제나 전부
//     maxSendMB  올리는 파일 크기 한도 (기본 20)
//     POST   /api/fax/send?to=번호[,번호…]&name=받는곳&memo=메모&file=파일이름   몸통 = PDF(또는 팩스 TIFF) 그대로
//     GET    /api/fax/send/config                 { enabled, canSend, maxMB, dryRun }
//     GET    /api/fax/sent                        보낸 팩스 목록 (상태: queued·converting·sending·accepted·failed)
//     GET    /api/fax/sent/:id/file               보낸 원본
//     POST   /api/fax/sent/:id/retry              실패한 것 다시 보내기
//     GET    /api/fax/device/check                장비 로그인 시험 (관리자만)
//
//   ⚠ 저장: fax-store/faxes.json (바꿔치기로 써서 쓰다가 꺼져도 반쪽 파일이 남지 않는다) + fax-store/files/<번호>.pdf
//   ⚠ 포털 서버가 inbox 폴더를 읽을 수 있어야 한다 (공유 폴더면 포털을 돌리는 Windows 계정에 읽기·쓰기 권한).
'use strict';
const path = require('path');
const fs = require('fs');
const fsp = fs.promises;
const crypto = require('crypto');

const ID = /^[0-9a-f]{16}$/;
const EXT = /\.(pdf|tiff?)$/i;
const DAY = 86400000;
const STATUSES = ['new', 'seen', 'done'];
const DONE_DIR = '_포털등록';

//  FaxBox 내보내기 이름: 20261112093015_From_0212345678_To_hanil(.pdf|.tif), PDF 변환 실패본은 …_PdfErr.tif
const NAME = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})_From_(.*?)_To_(.*?)(?:_PdfErr)?$/i;

function parseName(rel, mtimeMs) {
  const base = path.basename(rel).replace(EXT, '');
  const parts = rel.split(/[\\/]/);
  const folder = parts.length > 1 ? parts[parts.length - 2] : '';
  const m = NAME.exec(base);
  let at = null, from = '', to = '';
  if (m) {
    const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    if (!isNaN(d)) at = d.getTime();
    from = m[7].trim();
    to = m[8].trim();
  }
  if (!at) at = mtimeMs;
  //  하위 폴더 이름 = 보낸 곳 (FaxBox 「보낸 곳별 폴더」 — 연락처 이름 또는 번호, 모르면 unknow)
  const fromName = folder && folder.toLowerCase() !== 'unknow' && folder !== from ? folder : '';
  if (!from && folder.toLowerCase() !== 'unknow') from = folder;
  return { received_at: at, from, from_name: fromName, to, original: base };
}

module.exports = function mountFax(app, ctx) {
  ctx = ctx || {};
  const userOf = ctx.user || ((req) => {
    const u = req.session && req.session.user;
    if (!u) return null;
    const id = [u.username, u.id, u.user_id, u.uid, u.login, u.name].find((v) => v !== undefined && v !== null && v !== '');
    if (id === undefined) return null;
    return {
      id: String(id),
      name: String(u.name || u.username || id),
      admin: !!(u.is_admin || u.isAdmin || u.admin || u.role === 'admin' || u.level === 'admin' || u.grade === 'admin'),
    };
  });
  const canView = (u, f) => (typeof ctx.view === 'function' ? !!ctx.view(u, f) : ctx.view === 'admin' ? u.admin : true);

  let inboxes = ctx.inbox || process.env.FAX_INBOX || [];
  if (typeof inboxes === 'string') inboxes = inboxes.split(';');
  inboxes = inboxes.map((s) => String(s).trim()).filter(Boolean);
  if (!inboxes.length) console.warn('[fax] inbox 폴더가 없습니다 — require(\'./fax-route\')(app, { inbox: \'…\' })');

  const DIR = ctx.dir || process.env.FAX_DIR || path.join(__dirname, 'fax-store');
  const FILES = path.join(DIR, 'files');
  const FILE = path.join(DIR, 'faxes.json');
  const POLL = Math.max(3, Number(ctx.pollSec) || 15) * 1000;
  const SINCE = ctx.sinceDays === 0 ? 0 : (Number(ctx.sinceDays) || 30) * DAY;
  const AFTER = ['keep', 'move', 'delete'].includes(ctx.after) ? ctx.after : 'keep';
  fs.mkdirSync(FILES, { recursive: true });

  //  ── 저장 ──
  let db = { v: 1, startedAt: Date.now(), faxes: [], seen: {} };
  try { db = JSON.parse(fs.readFileSync(FILE, 'utf8')); } catch (e) {
    try { db = JSON.parse(fs.readFileSync(FILE + '.bak', 'utf8')); } catch (e2) { /* 처음 */ }
  }
  db.faxes = db.faxes || [];
  db.seen = db.seen || {};             //  이미 본 원본: 열쇠(경로|크기|시각) → 팩스 번호 (건너뛴 것은 '-')
  db.startedAt = db.startedAt || Date.now();
  function save() {
    const tmp = FILE + '.new';
    fs.writeFileSync(tmp, JSON.stringify(db));
    try { fs.copyFileSync(FILE, FILE + '.bak'); } catch (e) { /* 처음 */ }
    fs.renameSync(tmp, FILE);
  }
  if (!fs.existsSync(FILE)) save();
  const byId = (id) => db.faxes.find((f) => f.id === id && !f.hidden);

  //  ── 담당자 자동 지정 ──
  function routeOf(f) {
    const r = ctx.route;
    if (!r) return '';
    if (typeof r === 'function') { try { return String(r(f) || ''); } catch (e) { return ''; } }
    return String((r.to && f.to && r.to[f.to]) || (r.from && ((f.from_name && r.from[f.from_name]) || (f.from && r.from[f.from]))) || '');
  }

  //  ── 폴더 살피기 ──
  const state = { lastScan: 0, lastError: '', scanning: false, pending: {}, inboxes: {} };

  async function listFiles(root) {
    const out = [];
    async function walk(dir, rel, depth) {
      let ents;
      try { ents = await fsp.readdir(dir, { withFileTypes: true }); } catch (e) {
        if (depth === 0) throw e;
        return;
      }
      for (const e of ents) {
        if (e.name.startsWith('_') || e.name.startsWith('.')) continue;     //  _포털등록 같은 곳은 건너뜀
        const r = rel ? rel + '/' + e.name : e.name;
        if (e.isDirectory()) { if (depth < 2) await walk(path.join(dir, e.name), r, depth + 1); continue; }
        if (!e.isFile() || !EXT.test(e.name) || /_CvrtTemp/i.test(e.name)) continue;
        out.push(r);
      }
    }
    await walk(root, '', 0);
    return out;
  }

  async function hashFile(p) {
    return new Promise((ok, no) => {
      const h = crypto.createHash('sha256');
      fs.createReadStream(p).on('data', (c) => h.update(c)).on('error', no).on('end', () => ok(h.digest('hex')));
    });
  }

  async function ingest(root, rel, st) {
    const src = path.join(root, rel);
    const sha = await hashFile(src);
    const twin = db.faxes.find((f) => f.sha256 === sha);
    if (twin) return { id: twin.id, dup: true };               //  같은 팩스가 두 곳에 내보내진 경우
    const id = crypto.randomBytes(8).toString('hex');
    const ext = path.extname(rel).toLowerCase() === '.pdf' ? 'pdf' : 'tif';
    const tmp = path.join(FILES, id + '.' + ext + '.new');
    await fsp.copyFile(src, tmp);
    await fsp.rename(tmp, path.join(FILES, id + '.' + ext));
    const meta = parseName(rel, st.mtimeMs);
    const f = {
      id, sha256: sha, ext, size: st.size,
      received_at: meta.received_at, from: meta.from, from_name: meta.from_name, to: meta.to,
      original: meta.original, source: rel,
      status: 'new', assignee: '', memo: '',
      created_at: Date.now(), history: [{ at: Date.now(), by: '', action: '등록' }],
    };
    f.assignee = routeOf(f);
    if (f.assignee) f.history.push({ at: Date.now(), by: '', action: '담당 ' + f.assignee + ' (자동)' });
    db.faxes.push(f);
    return { id, fax: f };
  }

  async function afterIngest(root, rel) {
    if (AFTER === 'keep') return;
    const src = path.join(root, rel);
    try {
      if (AFTER === 'delete') await fsp.unlink(src);
      else {
        const dst = path.join(root, DONE_DIR, rel);
        await fsp.mkdir(path.dirname(dst), { recursive: true });
        await fsp.rename(src, dst);
      }
    } catch (e) { console.warn('[fax] 원본 정리 실패', rel, e.message); }
  }

  async function scan() {
    if (state.scanning) return;
    state.scanning = true;
    const fresh = [];
    try {
      for (const root of inboxes) {
        const info = state.inboxes[root] = state.inboxes[root] || { ok: false, files: 0, error: '' };
        let list;
        try { list = await listFiles(root); info.ok = true; info.error = ''; } catch (e) {
          info.ok = false; info.error = e.code === 'ENOENT' ? '폴더가 없습니다' : e.code === 'EACCES' || e.code === 'EPERM' ? '읽을 권한이 없습니다' : e.message;
          continue;
        }
        info.files = list.length;
        for (const rel of list) {
          let st;
          try { st = await fsp.stat(path.join(root, rel)); } catch (e) { continue; }
          const key = root + '|' + rel + '|' + st.size + '|' + Math.round(st.mtimeMs);
          if (db.seen[key]) continue;
          //  다 써진 파일만 — 두 번 연속 크기·시각이 같고, 5초 넘게 안 바뀐 것
          const pk = root + '|' + rel;
          const prev = state.pending[pk];
          state.pending[pk] = key;
          if (prev !== key || Date.now() - st.mtimeMs < 5000 || st.size === 0) continue;
          delete state.pending[pk];
          if (SINCE && st.mtimeMs < db.startedAt - SINCE) { db.seen[key] = '-'; continue; }
          try {
            const r = await ingest(root, rel, st);
            db.seen[key] = r.id;
            if (r.fax) fresh.push(r.fax);
            save();
            await afterIngest(root, rel);
          } catch (e) {
            console.warn('[fax] 등록 실패', rel, e.message);
            state.lastError = rel + ': ' + e.message;
          }
        }
      }
      state.lastScan = Date.now();
    } catch (e) {
      state.lastError = e.message;
    } finally {
      state.scanning = false;
    }
    if (typeof ctx.notify === 'function') {
      for (const f of fresh) {
        try { await ctx.notify(view(f), { url: '/fax#' + f.id }); } catch (e) { console.warn('[fax] 알림 실패', e.message); }
      }
    }
  }
  const timer = setInterval(scan, POLL);
  if (timer.unref) timer.unref();
  setTimeout(scan, 500);

  //  ── 공통 ──
  function view(f) {
    const { sha256, hidden, ...rest } = f;
    return rest;
  }
  const auth = (req, res, next) => {
    const u = userOf(req);
    if (!u) return res.status(401).json({ ok: false, error: '로그인이 필요합니다' });
    req.faxUser = u;
    next();
  };
  const admin = (req, res, next) => (req.faxUser.admin ? next() : res.status(403).json({ ok: false, error: '관리자만 할 수 있습니다' }));
  function body(req) {
    if (req.body && typeof req.body === 'object' && Object.keys(req.body).length) return Promise.resolve(req.body);
    return new Promise((ok) => {
      let s = '';
      req.setEncoding('utf8');
      req.on('data', (c) => { s += c; if (s.length > 1e5) req.destroy(); });
      req.on('end', () => { try { ok(JSON.parse(s || '{}')); } catch (e) { ok(null); } });
      req.on('error', () => ok(null));
    });
  }
  const visible = (u) => db.faxes.filter((f) => !f.hidden && canView(u, f));

  //  ── API ──
  app.get('/api/fax', auth, (req, res) => {
    const u = req.faxUser;
    const all = visible(u);
    const counts = { new: 0, seen: 0, done: 0, all: all.length };
    all.forEach((f) => { counts[f.status] = (counts[f.status] || 0) + 1; });
    const st = String(req.query.status || 'all');
    const q = String(req.query.q || '').trim().toLowerCase();
    const limit = Math.min(200, Math.max(1, Number(req.query.limit) || 50));
    let list = all.filter((f) => (st === 'all' || f.status === st));
    if (q) list = list.filter((f) => [f.from, f.from_name, f.to, f.memo, f.assignee, f.original].some((v) => String(v || '').toLowerCase().includes(q)));
    list.sort((a, b) => b.received_at - a.received_at || b.created_at - a.created_at);
    if (req.query.before && ID.test(req.query.before)) {
      const i = list.findIndex((f) => f.id === req.query.before);
      if (i >= 0) list = list.slice(i + 1);
    }
    res.json({ ok: true, counts, items: list.slice(0, limit).map(view), more: list.length > limit });
  });

  app.get('/api/fax/count', auth, (req, res) => {
    res.json({ ok: true, new: visible(req.faxUser).filter((f) => f.status === 'new').length });
  });

  app.get('/api/fax/admin/status', auth, admin, (req, res) => {
    res.json({
      ok: true, inboxes: inboxes.map((p) => Object.assign({ path: p }, state.inboxes[p] || { ok: null })),
      lastScan: state.lastScan, lastError: state.lastError, total: db.faxes.length, pollSec: POLL / 1000, after: AFTER,
    });
  });

  const sendApi = {};
  mountSend();

  app.get('/api/fax/:id', auth, (req, res) => {
    const f = ID.test(req.params.id) && byId(req.params.id);
    if (!f || !canView(req.faxUser, f)) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
    res.json({ ok: true, fax: view(f) });
  });

  app.get('/api/fax/:id/file', auth, (req, res) => {
    const f = ID.test(req.params.id) && byId(req.params.id);
    if (!f || !canView(req.faxUser, f)) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
    const p = path.join(FILES, f.id + '.' + f.ext);
    if (!fs.existsSync(p)) return res.status(410).json({ ok: false, error: '파일이 지워졌습니다' });
    if (f.status === 'new') {
      f.status = 'seen';
      f.history.push({ at: Date.now(), by: req.faxUser.name, action: '열어 봄' });
      save();
    }
    const d = new Date(f.received_at);
    const pad = (n) => String(n).padStart(2, '0');
    const name = `팩스_${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}_${(f.from_name || f.from || '발신미상').replace(/[\\/:*?"<>|]/g, '_')}.${f.ext}`;
    const inline = f.ext === 'pdf' && !req.query.download;
    res.setHeader('Content-Type', f.ext === 'pdf' ? 'application/pdf' : 'image/tiff');
    res.setHeader('Content-Disposition', (inline ? 'inline' : 'attachment') + "; filename*=UTF-8''" + encodeURIComponent(name));
    res.setHeader('Cache-Control', 'private, max-age=300');
    fs.createReadStream(p).pipe(res);
  });

  app.put('/api/fax/:id', auth, async (req, res) => {
    const f = ID.test(req.params.id) && byId(req.params.id);
    if (!f || !canView(req.faxUser, f)) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
    const b = await body(req);
    if (!b) return res.status(400).json({ ok: false, error: '보낸 값을 읽지 못했습니다' });
    const by = req.faxUser.name, now = Date.now();
    if (b.status !== undefined) {
      if (!STATUSES.includes(b.status)) return res.status(400).json({ ok: false, error: '상태는 new / seen / done 중 하나입니다' });
      if (b.status !== f.status) {
        f.status = b.status;
        f.history.push({ at: now, by, action: { new: '안 봄으로', seen: '확인', done: '처리 완료' }[b.status] });
      }
    }
    if (b.assignee !== undefined) {
      const a = String(b.assignee || '').trim().slice(0, 60);
      if (a !== f.assignee) { f.assignee = a; f.history.push({ at: now, by, action: a ? '담당 ' + a : '담당 지움' }); }
    }
    if (b.memo !== undefined) {
      const m = String(b.memo || '').slice(0, 2000);
      if (m !== f.memo) { f.memo = m; f.history.push({ at: now, by, action: '메모' }); }
    }
    if (f.history.length > 100) f.history = f.history.slice(-100);
    save();
    res.json({ ok: true, fax: view(f) });
  });

  app.delete('/api/fax/:id', auth, admin, (req, res) => {
    const f = ID.test(req.params.id) && byId(req.params.id);
    if (!f) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
    f.hidden = true;
    f.history.push({ at: Date.now(), by: req.faxUser.name, action: '숨김' });
    save();
    res.json({ ok: true });
  });

  //  ── 보내기 (ctx.device 가 있을 때만) ──
  function mountSend() {
    const dev = ctx.device || (process.env.FAX_DEVICE_HOST ? {
      host: process.env.FAX_DEVICE_HOST, user: process.env.FAX_DEVICE_USER, password: process.env.FAX_DEVICE_PASSWORD,
    } : null);
    const cim = ctx.cimfax || require('./cimfax-client');
    const SENT = path.join(DIR, 'sent');
    fs.mkdirSync(SENT, { recursive: true });
    db.sent = db.sent || [];
    const canSend = (u) => (typeof ctx.sendBy === 'function' ? !!ctx.sendBy(u) : ctx.sendBy === 'admin' ? u.admin : true);
    const MAX = (Number(ctx.maxSendMB) || 20) * 1048576;
    const sview = (s) => { const { tif, src, ...rest } = s; return rest; };
    const mine = (u) => db.sent.filter((s) => !s.hidden && (u.admin || ctx.sentView === 'all' || s.by_id === u.id));

    app.get('/api/fax/send/config', auth, (req, res) => {
      res.json({ ok: true, enabled: !!dev, canSend: !!dev && canSend(req.faxUser), maxMB: MAX / 1048576, dryRun: !!(dev && dev.dryRun) });
    });

    //  POST /api/fax/send?to=0212345678,0311112222&name=대한상사&memo=견적서   몸통 = PDF 또는 팩스 TIFF 파일 그대로
    app.post('/api/fax/send', auth, (req, res) => {
      const u = req.faxUser;
      if (!dev) return res.status(503).json({ ok: false, error: '팩스 장비가 설정되지 않았습니다 (관리자에게 문의)' });
      if (!canSend(u)) return res.status(403).json({ ok: false, error: '팩스를 보낼 권한이 없습니다' });
      const nums = String(req.query.to || '').split(/[,\s;]+/).map((s) => s.replace(/[^0-9,*#-]/g, '')).filter((s) => /\d{3,}/.test(s));
      if (!nums.length) return res.status(400).json({ ok: false, error: '받는 팩스 번호를 넣어 주세요' });
      if (nums.length > 20) return res.status(400).json({ ok: false, error: '한 번에 20곳까지 보낼 수 있습니다' });
      const chunks = [];
      let size = 0, over = false;
      req.on('data', (c) => { size += c.length; if (size > MAX) { over = true; req.destroy(); } else chunks.push(c); });
      req.on('error', () => {});
      req.on('end', async () => {
        if (over) return;
        const buf = Buffer.concat(chunks);
        const sig = buf.toString('latin1', 0, 4);
        if (sig !== '%PDF' && sig !== 'II*\0' && sig !== 'MM\0*') return res.status(400).json({ ok: false, error: 'PDF 파일(또는 팩스 TIFF)만 보낼 수 있습니다' });
        const job = crypto.randomBytes(8).toString('hex');
        const ext = sig === '%PDF' ? 'pdf' : 'tif';
        const src = path.join(SENT, job + '.src.' + ext);
        try { await fsp.writeFile(src, buf); } catch (e) { return res.status(500).json({ ok: false, error: '파일을 저장하지 못했습니다' }); }
        const now = Date.now();
        const name = String(req.query.name || '').trim().slice(0, 60), memo = String(req.query.memo || '').trim().slice(0, 500);
        const fileName = String(req.query.file || '').trim().slice(0, 120);
        const items = nums.map((to) => ({
          id: crypto.randomBytes(8).toString('hex'), job, to, name, memo, file_name: fileName, ext, size: buf.length,
          src, tif: path.join(SENT, job + '.tif'), pages: 0, state: 'queued', task_id: null, device: null, error: '', tries: 0,
          by: u.name, by_id: u.id, created_at: now, history: [{ at: now, by: u.name, action: '보내기 요청' }],
        }));
        db.sent.push(...items);
        save();
        res.json({ ok: true, items: items.map(sview) });
        kick();
      });
    });

    app.get('/api/fax/sent', auth, (req, res) => {
      const list = mine(req.faxUser).slice().sort((a, b) => b.created_at - a.created_at);
      const limit = Math.min(200, Math.max(1, Number(req.query.limit) || 50));
      const busy = list.filter((s) => ['queued', 'converting', 'sending'].includes(s.state)).length;
      res.json({ ok: true, busy, items: list.slice(0, limit).map(sview), more: list.length > limit });
    });

    app.get('/api/fax/sent/:id/file', auth, (req, res) => {
      const s = ID.test(req.params.id) && mine(req.faxUser).find((x) => x.id === req.params.id);
      if (!s || !fs.existsSync(s.src)) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
      res.setHeader('Content-Type', s.ext === 'pdf' ? 'application/pdf' : 'image/tiff');
      res.setHeader('Content-Disposition', (s.ext === 'pdf' && !req.query.download ? 'inline' : 'attachment') + "; filename*=UTF-8''" + encodeURIComponent((s.file_name || '보낸팩스_' + s.to) .replace(/\.(pdf|tiff?)$/i, '') + '.' + s.ext));
      fs.createReadStream(s.src).pipe(res);
    });

    app.post('/api/fax/sent/:id/retry', auth, (req, res) => {
      const s = ID.test(req.params.id) && mine(req.faxUser).find((x) => x.id === req.params.id);
      if (!s) return res.status(404).json({ ok: false, error: '없는 팩스입니다' });
      if (s.state !== 'failed') return res.status(409).json({ ok: false, error: '실패한 팩스만 다시 보낼 수 있습니다' });
      s.state = 'queued'; s.error = ''; s.tries = 0;
      s.history.push({ at: Date.now(), by: req.faxUser.name, action: '다시 보내기' });
      save();
      res.json({ ok: true, item: sview(s) });
      kick();
    });

    app.get('/api/fax/device/check', auth, admin, async (req, res) => {
      if (!dev) return res.json({ ok: false, error: '장비 설정 없음' });
      if (dev.dryRun) return res.json({ ok: true, dryRun: true });
      try {
        const c = await cim.login(dev, cim.PORT.cmd);
        c.close();
        res.json({ ok: true, device: c.info });
      } catch (e) { res.json({ ok: false, error: e.message }); }
    });

    //  ── 보내는 일꾼: 한 번에 한 건씩 ──
    let working = false;
    async function kick() {
      if (working || !dev) return;
      working = true;
      try {
        for (;;) {
          const s = db.sent.find((x) => x.state === 'queued' && !x.hidden);
          if (!s) break;
          await sendOne(s);
        }
      } finally { working = false; }
    }
    async function sendOne(s) {
      const step = (state, action) => { s.state = state; if (action) s.history.push({ at: Date.now(), by: '', action }); save(); };
      try {
        if (!fs.existsSync(s.tif)) {
          step('converting');
          const r = await cim.toFaxTiff(s.src, s.tif + '.new', { ghostscript: dev.ghostscript });
          await fsp.rename(s.tif + '.new', s.tif);
          db.sent.filter((x) => x.job === s.job).forEach((x) => { x.pages = r.pages; });
        } else if (!s.pages) {
          s.pages = cim.tiffPages(await fsp.readFile(s.tif)).pages;
        }
        step('sending');
        s.tries++;
        if (dev.dryRun) {
          s.task_id = 0;
          step('accepted', '시험 모드 — 장비로 보내지 않음 (' + s.pages + '쪽)');
        } else {
          const r = await cim.sendFax(dev, { phone: s.to, pages: s.pages, tiff: s.tif, priority: dev.priority, quality: dev.quality, dialTotal: dev.dialTotal });
          s.task_id = r.taskId;
          s.accepted_at = Date.now();
          step('accepted', '장비 접수 · 작업번호 ' + r.taskId);
        }
      } catch (e) {
        s.error = e.message;
        const network = /접속|연결|답하지/.test(e.message);
        if (network && s.tries < 3) {
          step('queued', '다시 시도 예정: ' + e.message);
          await new Promise((ok) => setTimeout(ok, 20000));
        } else {
          step('failed', '실패: ' + e.message);
          if (typeof ctx.notify === 'function') {
            try { await ctx.notify(Object.assign({ kind: 'send_failed' }, sview(s)), { url: '/fax#sent' }); } catch (e2) { /* 알림 실패는 넘어감 */ }
          }
        }
      }
    }

    //  ── 접수된 팩스 상태 묻기 (1분마다, 하루 동안) ──
    async function poll() {
      if (!dev || dev.dryRun) return;
      const live = db.sent.filter((s) => s.state === 'accepted' && s.task_id && Date.now() - (s.accepted_at || 0) < DAY);
      if (!live.length) return;
      try {
        const r = await cim.sendStatus(dev, live.map((s) => s.task_id).join(','));
        if (!r.ok) return;
        let changed = false;
        r.items.forEach((it) => {
          const s = live.find((x) => x.task_id === it.taskId);
          if (!s) return;
          const d = { status: it.status, pageSent: it.pageSent, pageTotal: it.pageTotal, dialDone: it.dialDone, dialTotal: it.dialTotal, at: Date.now() };
          if (!s.device || s.device.status !== d.status || s.device.pageSent !== d.pageSent || s.device.dialDone !== d.dialDone) {
            s.device = d; changed = true;
          }
        });
        if (changed) save();
      } catch (e) { state.lastSendError = e.message; }
    }
    const pt = setInterval(poll, (Number(ctx.statusSec) || 60) * 1000);
    if (pt.unref) pt.unref();
    //  켜질 때 보내던 중이던 것은 다시 줄 세운다
    db.sent.forEach((s) => { if (s.state === 'converting' || s.state === 'sending') s.state = 'queued'; });
    const kt = setTimeout(kick, 1000);
    if (kt.unref) kt.unref();
    sendApi.kick = kick; sendApi.poll = poll; sendApi.timer = pt;
  }

  //  ── 화면 ──
  const PAGE = path.join(__dirname, 'fax-page.html');
  app.get('/fax', (req, res) => {
    if (!userOf(req)) return res.redirect('/?next=' + encodeURIComponent('/fax'));
    res.setHeader('Cache-Control', 'no-cache');
    res.sendFile(PAGE);
  });

  //  시험·관리용
  return { scan, state, db: () => db, send: sendApi, stop: () => { clearInterval(timer); if (sendApi.timer) clearInterval(sendApi.timer); } };
};

module.exports.parseName = parseName;
