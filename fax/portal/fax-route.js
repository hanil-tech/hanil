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

  //  ── 화면 ──
  const PAGE = path.join(__dirname, 'fax-page.html');
  app.get('/fax', (req, res) => {
    if (!userOf(req)) return res.redirect('/?next=' + encodeURIComponent('/fax'));
    res.setHeader('Cache-Control', 'no-cache');
    res.sendFile(PAGE);
  });

  //  시험·관리용
  return { scan, state, db: () => db, stop: () => clearInterval(timer) };
};

module.exports.parseName = parseName;
