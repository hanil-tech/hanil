//  📅 회사 일정 — 포털에 넣는 조각 (한일 바탕화면 달력이 읽고 쓴다)
//   넣는 법: 이 파일을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./calendar-route')(app);
//
//   API (모두 로그인 필요)
//     GET    /api/cal/events?from=2026-11-01&to=2026-12-06   그 사이에 걸친 일정
//     POST   /api/cal/events            { title, start, end?, time?, endTime?, place?, memo?, kind: 'company'|'private', color?, holiday? }
//     PUT    /api/cal/events/:id        (같은 꼴 — 보낸 칸만 바뀐다)
//     DELETE /api/cal/events/:id
//     GET    /api/cal/holidays?year=2026     그해 공휴일 { days: { '2026-01-01': '1월1일', … } } — 아래 「휴일 자동」
//
//   🔴 휴일 자동 — 공공데이터포털(data.go.kr)의 「한국천문연구원_특일 정보」에서 그해 공휴일을 받아 온다.
//      임시공휴일·선거일·대체공휴일이 새로 정해져도 포털이 알아서 받아 오므로 손댈 것이 없다.
//      ① data.go.kr 가입 → 「한국천문연구원_특일 정보」 활용 신청(무료·자동 승인) → 일반 인증키(Decoding) 복사
//      ② require('./calendar-route')(app, { holidayKey: '받은 인증키' });   (또는 환경 변수 HOLIDAY_KEY)
//      받아 온 것은 calendar-store/holidays-2026.json 에 두고 하루 한 번만 다시 묻는다(인터넷이 끊겨도 마지막 것을 쓴다).
//      인증키가 없으면 days 가 null — 달력 프로그램이 스스로 계산한 휴일(양력·설·추석·부처님오신날·대체공휴일)을 쓴다.
//
//   ⭐ 종류 두 가지
//      company(회사 일정) — 로그인한 직원 **모두에게** 보인다. 누가 올렸는지 이름이 붙는다.
//      private(내 일정)  — 올린 사람에게만 보인다.
//   ⭐ 고치기·지우기는 올린 사람과 관리자만.
//      회사 일정을 아무나 올리지 못하게 하려면:  require('./calendar-route')(app, { companyEdit: 'admin' });
//   ⚠ 저장: 포털 폴더 옆 calendar-store/events.json (바꿔치기로 써서 쓰다가 꺼져도 반쪽 파일이 남지 않는다)
//      다른 곳에 두려면: require('./calendar-route')(app, { dir: 'D:/portal-data/calendar' });
//   ⚠ 포털의 express.json() 이 있든 없든 돈다 — 없으면 몸통을 직접 읽는다.
'use strict';
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const DATE = /^\d{4}-\d{2}-\d{2}$/, TIME = /^([01]\d|2[0-3]):[0-5]\d$/, COLOR = /^#[0-9a-fA-F]{6}$/, ID = /^[0-9a-f]{16}$/;
const DAY = 86400000;

module.exports = function mountCalendar(app, ctx) {
  ctx = ctx || {};
  //  로그인한 사람 — 포털 세션 모양을 몰라도 돌게 흔한 이름들을 본다(bigfile 과 같은 잣대). 다르면 ctx.user 로.
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
  const canCompany = (u) => (typeof ctx.companyEdit === 'function' ? !!ctx.companyEdit(u) : ctx.companyEdit === 'admin' ? u.admin : true);

  const DIR = ctx.dir || process.env.CALENDAR_DIR || path.join(__dirname, 'calendar-store');
  const FILE = path.join(DIR, 'events.json');
  fs.mkdirSync(DIR, { recursive: true });
  let events = [];
  try { events = JSON.parse(fs.readFileSync(FILE, 'utf8')).events || []; } catch (e) {
    try { events = JSON.parse(fs.readFileSync(FILE + '.bak', 'utf8')).events || []; } catch (e2) { events = []; }
  }
  function save() {
    const tmp = FILE + '.new';
    fs.writeFileSync(tmp, JSON.stringify({ v: 1, events }));
    try { fs.copyFileSync(FILE, FILE + '.bak'); } catch (e) { /* 처음 */ }
    fs.renameSync(tmp, FILE);
  }

  //  ── 휴일 자동(data.go.kr) ──
  const HKEY = ctx.holidayKey || process.env.HOLIDAY_KEY || '';
  const HURL = ctx.holidayURL || 'https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo';
  const hFile = (y) => path.join(DIR, 'holidays-' + y + '.json');
  const hMem = {}, hBusy = {};
  function getJSON(u) {
    if (typeof fetch === 'function') return fetch(u, { signal: AbortSignal.timeout ? AbortSignal.timeout(10000) : undefined }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
    return new Promise((ok, no) => {
      require(u.startsWith('https') ? 'https' : 'http').get(u, (r) => { let s = ''; r.setEncoding('utf8'); r.on('data', (c) => { s += c; }); r.on('end', () => { try { ok(JSON.parse(s)); } catch (e) { no(e); } }); }).on('error', no).setTimeout(10000, function () { this.destroy(new Error('timeout')); });
    });
  }
  async function fetchYear(y) {
    const u = HURL + '?serviceKey=' + encodeURIComponent(HKEY) + '&solYear=' + y + '&numOfRows=100&_type=json';
    const j = await getJSON(u);
    const body = j && j.response && j.response.body;
    if (!body) throw new Error((j && j.response && j.response.header && j.response.header.resultMsg) || '답 모양이 다릅니다');
    let items = body.items && body.items.item;
    if (!items) items = [];
    if (!Array.isArray(items)) items = [items];
    const days = {};
    items.forEach((x) => {
      if (String(x.isHoliday || 'Y') !== 'Y') return;
      const d = String(x.locdate || '');
      if (!/^\d{8}$/.test(d)) return;
      const k = d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8);
      const n = String(x.dateName || '공휴일').trim();
      days[k] = days[k] && days[k].indexOf(n) < 0 ? days[k] + '·' + n : (days[k] || n);
    });
    return days;
  }
  async function holidaysOf(y) {
    if (!HKEY) return null;
    let c = hMem[y];
    if (!c) { try { c = hMem[y] = JSON.parse(fs.readFileSync(hFile(y), 'utf8')); } catch (e) { c = null; } }
    const stale = !c || Date.now() - (c.at || 0) > DAY;
    if (stale && !hBusy[y]) {
      hBusy[y] = (async () => {
        try {
          const days = await fetchYear(y);
          if (Object.keys(days).length) {
            hMem[y] = { at: Date.now(), days };
            fs.writeFileSync(hFile(y), JSON.stringify(hMem[y]));
          } else if (c) c.at = Date.now();          //  아직 발표 전(먼 해) — 하루 뒤 다시
        } catch (e) {
          console.warn('[calendar] 휴일을 받아 오지 못함', y, e.message);
          if (c) c.at = Date.now() - DAY + 3600000;  //  한 시간 뒤 다시
        } finally { hBusy[y] = null; }
      })();
    }
    if (!c && hBusy[y]) await hBusy[y];
    c = hMem[y];
    return c && c.days && Object.keys(c.days).length ? c.days : null;
  }

  const auth = (req, res, next) => {
    const u = userOf(req);
    if (!u) return res.status(401).json({ ok: false, error: '로그인이 필요합니다' });
    req.calUser = u;
    next();
  };
  //  몸통 읽기 — express.json() 이 이미 읽었으면 그것을
  const body = (req, max) => new Promise((ok) => {
    if (req.body && typeof req.body === 'object' && Object.keys(req.body).length) return ok(req.body);
    let s = '';
    req.setEncoding('utf8');
    req.on('data', (c) => { s += c; if (s.length > (max || 64 * 1024)) req.destroy(); });
    req.on('end', () => { try { ok(JSON.parse(s || '{}')); } catch (e) { ok(null); } });
    req.on('error', () => ok(null));
  });
  const str = (v, max) => String(v === undefined || v === null ? '' : v).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').trim().slice(0, max);
  const days = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / DAY);
  const okDate = (s) => DATE.test(s) && !isNaN(Date.parse(s + 'T00:00:00Z')) && new Date(s + 'T00:00:00Z').toISOString().slice(0, 10) === s;

  //  들어온 값을 고르게 — 틀린 것은 까닭을 돌려준다
  function clean(src, old) {
    const e = Object.assign({}, old || {});
    const has = (k) => Object.prototype.hasOwnProperty.call(src, k);
    if (!old || has('title')) e.title = str(src.title, 200);
    if (!e.title) return '제목을 넣어 주세요';
    if (!old || has('start')) e.start = str(src.start, 10);
    if (!okDate(e.start)) return '시작 날짜가 올바르지 않습니다';
    if (!old || has('end')) e.end = str(src.end, 10) || e.start;
    if (!okDate(e.end)) return '끝 날짜가 올바르지 않습니다';
    if (e.end < e.start) return '끝 날짜가 시작보다 앞입니다';
    if (days(e.start, e.end) > 366) return '일정은 1년을 넘길 수 없습니다';
    for (const k of ['time', 'endTime']) {
      if (!old || has(k)) e[k] = str(src[k], 5);
      if (e[k] && !TIME.test(e[k])) return '시각은 09:30 처럼 넣어 주세요';
    }
    if (!old || has('place')) e.place = str(src.place, 200);
    if (!old || has('memo')) e.memo = str(src.memo, 2000);
    if (!old || has('kind')) e.kind = src.kind === 'private' ? 'private' : 'company';
    if (!old || has('color')) e.color = COLOR.test(String(src.color || '')) ? String(src.color) : '';
    //  🔁 반복 — 매주·매월·매년(끝나는 날 until 까지, 없으면 계속). 펼치는 것은 달력(화면)이 한다.
    if (!old || has('repeat')) e.repeat = ['weekly', 'monthly', 'yearly'].includes(src.repeat) ? src.repeat : '';
    if (!old || has('until')) e.until = okDate(str(src.until, 10)) ? str(src.until, 10) : '';
    //  ⏰ 미리 알림 — 몇 분 전(0 = 안 함). 시각이 있는 일정만.
    if (!old || has('remind')) { const m = parseInt(src.remind, 10); e.remind = [5, 10, 30, 60, 1440].includes(m) ? m : 0; }
    //  🔴 회사 휴무일(창립기념일·하계휴가 …) — 모든 직원 달력에 빨간 날로. 회사 일정일 때만.
    if (!old || has('holiday')) e.holiday = src.holiday === true || src.holiday === 1 || src.holiday === '1';
    if (e.kind !== 'company') e.holiday = false;
    return e;
  }
  const visible = (u, e) => e.kind === 'company' || e.owner === u.id;
  const canEdit = (u, e) => e.owner === u.id || u.admin;
  const view = (u, e) => Object.assign({}, e, { mine: e.owner === u.id, editable: canEdit(u, e) });

  app.get('/api/cal/events', auth, (req, res) => {
    const u = req.calUser;
    let from = String(req.query.from || ''), to = String(req.query.to || '');
    if (!okDate(from) || !okDate(to)) {
      const t = new Date(), ymd = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      from = ymd(new Date(t.getFullYear(), t.getMonth(), 1));
      to = ymd(new Date(t.getFullYear(), t.getMonth() + 2, 0));
    }
    const list = events.filter((e) => visible(u, e) && e.start <= to && (e.repeat ? (!e.until || e.until >= from) : e.end >= from))
      .sort((a, b) => (a.start + (a.time || '')).localeCompare(b.start + (b.time || '')))
      .map((e) => view(u, e));
    res.set('Cache-Control', 'no-store').json({ ok: true, me: { id: u.id, name: u.name, admin: u.admin, company: canCompany(u) }, events: list });
  });

  app.get('/api/cal/holidays', auth, async (req, res) => {
    const y = parseInt(req.query.year, 10);
    if (!(y >= 2000 && y <= 2100)) return res.status(400).json({ ok: false, error: '해를 넣어 주세요' });
    //  회사 휴무일(「휴일로 표시」한 회사 일정)도 함께 — 달력이 아닌 다른 화면에서도 쓸 수 있게
    const company = {};
    events.filter((e) => e.kind === 'company' && e.holiday && e.start.slice(0, 4) <= String(y) && e.end.slice(0, 4) >= String(y)).forEach((e) => {
      for (let d = e.start; d <= e.end; d = new Date(Date.parse(d + 'T00:00:00Z') + DAY).toISOString().slice(0, 10)) if (d.slice(0, 4) === String(y)) company[d] = company[d] ? company[d] + '·' + e.title : e.title;
    });
    const days = await holidaysOf(y);
    res.set('Cache-Control', 'no-store').json({ ok: true, year: y, source: days ? 'data.go.kr' : '', days, company });
  });

  app.post('/api/cal/events', auth, async (req, res) => {
    const u = req.calUser, src = await body(req);
    if (!src) return res.status(400).json({ ok: false, error: '보낸 값을 읽지 못했습니다' });
    const e = clean(src);
    if (typeof e === 'string') return res.status(400).json({ ok: false, error: e });
    if (e.kind === 'company' && !canCompany(u)) return res.status(403).json({ ok: false, error: '회사 일정은 관리자만 올릴 수 있습니다 — 「내 일정」으로 올려 주세요' });
    const now = new Date().toISOString();
    Object.assign(e, { id: crypto.randomBytes(8).toString('hex'), owner: u.id, ownerName: u.name, created: now, updated: now });
    events.push(e);
    save();
    res.json({ ok: true, event: view(u, e) });
  });

  app.put('/api/cal/events/:id', auth, async (req, res) => {
    const u = req.calUser, i = ID.test(req.params.id) ? events.findIndex((x) => x.id === req.params.id) : -1;
    if (i < 0 || !visible(u, events[i])) return res.status(404).json({ ok: false, error: '없는 일정입니다' });
    if (!canEdit(u, events[i])) return res.status(403).json({ ok: false, error: '올린 사람만 고칠 수 있습니다' });
    const src = await body(req);
    if (!src) return res.status(400).json({ ok: false, error: '보낸 값을 읽지 못했습니다' });
    const e = clean(src, events[i]);
    if (typeof e === 'string') return res.status(400).json({ ok: false, error: e });
    if (e.kind === 'company' && events[i].kind !== 'company' && !canCompany(u)) return res.status(403).json({ ok: false, error: '회사 일정은 관리자만 올릴 수 있습니다' });
    e.updated = new Date().toISOString();
    events[i] = e;
    save();
    res.json({ ok: true, event: view(u, e) });
  });

  app.delete('/api/cal/events/:id', auth, (req, res) => {
    const u = req.calUser, i = ID.test(req.params.id) ? events.findIndex((x) => x.id === req.params.id) : -1;
    if (i < 0 || !visible(u, events[i])) return res.status(404).json({ ok: false, error: '없는 일정입니다' });
    if (!canEdit(u, events[i])) return res.status(403).json({ ok: false, error: '올린 사람만 지울 수 있습니다' });
    events.splice(i, 1);
    save();
    res.json({ ok: true });
  });

  //  ════ ☁ 내 달력 자료 동기화(메모·할 일·기념일·설정) — 여러 PC·폰이 같은 것을 본다 ════
  //   GET  /api/cal/mydata                → { rev, at, data }
  //   PUT  /api/cal/mydata  { data }      → { rev }      (마지막에 쓴 것이 이긴다 — 대신 지난 판 30개를 남긴다)
  //   GET  /api/cal/mydata/history        → 지난 판 목록 { rev, at, notes, dev }
  //   POST /api/cal/mydata/rollback { rev } → 그 판으로 되돌린다(되돌린 것도 새 판으로 남는다)
  const UDIR = path.join(DIR, 'users');
  fs.mkdirSync(UDIR, { recursive: true });
  const uKey = (u) => crypto.createHash('sha1').update(String(u.id)).digest('hex');
  const uFile = (u) => path.join(UDIR, uKey(u) + '.json');
  const readU = (u) => { try { return JSON.parse(fs.readFileSync(uFile(u), 'utf8')); } catch (e) { return { rev: 0, at: 0, data: {}, hist: [] }; } };
  const writeU = (u, o) => { const f = uFile(u); fs.writeFileSync(f + '.new', JSON.stringify(o)); fs.renameSync(f + '.new', f); };
  const KEEP = ctx.keepVersions || 30;
  const count = (d) => (d && d.notes ? Object.keys(d.notes).length : 0);
  function pushVersion(u, data, dev) {
    const o = readU(u);
    if (o.rev) { o.hist = (o.hist || []).concat([{ rev: o.rev, at: o.at, dev: o.dev || '', data: o.data }]).slice(-KEEP); }
    o.rev = (o.rev || 0) + 1; o.at = Date.now(); o.dev = String(dev || '').slice(0, 40); o.data = data;
    writeU(u, o);
    return o;
  }
  app.get('/api/cal/mydata', auth, (req, res) => {
    const o = readU(req.calUser);
    res.set('Cache-Control', 'no-store').json({ ok: true, rev: o.rev || 0, at: o.at || 0, data: o.data || {} });
  });
  app.put('/api/cal/mydata', auth, async (req, res) => {
    const src = await body(req, 2 * 1024 * 1024);
    if (!src || typeof src.data !== 'object' || Array.isArray(src.data)) return res.status(400).json({ ok: false, error: '보낸 값을 읽지 못했습니다' });
    if (JSON.stringify(src.data).length > 2 * 1024 * 1024) return res.status(413).json({ ok: false, error: '너무 큽니다(2MB)' });
    const o = pushVersion(req.calUser, src.data, src.dev);
    res.json({ ok: true, rev: o.rev, at: o.at });
  });
  app.get('/api/cal/mydata/history', auth, (req, res) => {
    const o = readU(req.calUser);
    const list = (o.hist || []).map((h) => ({ rev: h.rev, at: h.at, dev: h.dev || '', notes: count(h.data) })).reverse();
    res.set('Cache-Control', 'no-store').json({ ok: true, rev: o.rev || 0, at: o.at || 0, notes: count(o.data), versions: list });
  });
  app.post('/api/cal/mydata/rollback', auth, async (req, res) => {
    const src = await body(req), u = req.calUser, o = readU(u);
    const h = (o.hist || []).find((x) => x.rev === Number(src && src.rev));
    if (!h) return res.status(404).json({ ok: false, error: '그 판이 없습니다' });
    const n = pushVersion(u, h.data, '되돌림 ← ' + h.rev);
    res.json({ ok: true, rev: n.rev, data: n.data });
  });

  //  ════ 🟦 구글 캘린더 ════
  //   ① 구글 → 달력: 구글 캘린더 설정의 「iCal 형식의 비공개 주소」를 한 번 넣어 두면 포털이 대신 받아 와(10분 보관) 달력에 보인다.
  //      PUT /api/cal/gcal { url }   ·   GET /api/cal/gcal?from=&to=  → { events }
  //   ② 달력 → 구글: 포털이 사람마다 «구독 주소(.ics)» 를 만들어 준다 → 구글 캘린더 「URL로 추가」에 넣으면
  //      회사 일정·내 일정·기념일이 구글 캘린더(폰 포함)에 나온다.  POST /api/cal/feed → { url }  (reset:true 면 새 주소)
  //      ⚠ 구글이 이 주소를 바깥에서 읽으므로 **바깥 주소**여야 한다: { publicURL: 'https://work.hanil-steel.com' }
  //   ⚠ 구글 OAuth(앱 등록) 없이 되는 길이다 — 대신 구글 쪽 반영은 구글이 몇 시간마다 다시 읽을 때 된다.
  const PUBLIC = (ctx.publicURL || process.env.CAL_PUBLIC_URL || 'https://work.hanil-steel.com').replace(/\/+$/, '');
  const gFile = (u) => path.join(UDIR, uKey(u) + '.google.json');
  const readG = (u) => { try { return JSON.parse(fs.readFileSync(gFile(u), 'utf8')); } catch (e) { return {}; } };
  const writeG = (u, o) => fs.writeFileSync(gFile(u), JSON.stringify(o));
  const FEEDS = path.join(DIR, 'feeds.json');
  let feeds = {};
  try { feeds = JSON.parse(fs.readFileSync(FEEDS, 'utf8')); } catch (e) { feeds = {}; }
  const gCache = {};
  const okICS = (u) => /^https:\/\/calendar\.google\.com\/calendar\/ical\/[^\s]+\.ics$/.test(u) || (ctx.icsAny && /^https?:\/\/\S+$/.test(u));
  function getText(u) {
    if (typeof fetch === 'function') return fetch(u).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); });
    return new Promise((ok, no) => {
      require(u.startsWith('https') ? 'https' : 'http').get(u, (r) => { if (r.statusCode >= 400) return no(new Error('HTTP ' + r.statusCode)); let s = ''; r.setEncoding('utf8'); r.on('data', (c) => { s += c; }); r.on('end', () => ok(s)); }).on('error', no);
    });
  }
  app.get('/api/cal/gcal', auth, async (req, res) => {
    const g = readG(req.calUser);
    if (!g.url) return res.json({ ok: true, linked: false, events: [] });
    const from = okDate(String(req.query.from || '')) ? String(req.query.from) : '2000-01-01';
    const to = okDate(String(req.query.to || '')) ? String(req.query.to) : '2100-01-01';
    try {
      let c = gCache[g.url];
      if (!c || Date.now() - c.at > 10 * 60000 || req.query.fresh) { c = gCache[g.url] = { at: Date.now(), ics: await getText(g.url) }; }
      res.set('Cache-Control', 'no-store').json({ ok: true, linked: true, at: c.at, events: icsEvents(c.ics, from, to) });
    } catch (e) {
      res.json({ ok: true, linked: true, error: '구글 캘린더를 읽지 못했습니다(' + e.message + ') — 주소를 다시 확인해 주세요', events: [] });
    }
  });
  app.put('/api/cal/gcal', auth, async (req, res) => {
    const src = await body(req), url = str(src && src.url, 600);
    if (url && !okICS(url)) return res.status(400).json({ ok: false, error: '구글 캘린더의 「iCal 형식의 비공개 주소」(https://calendar.google.com/calendar/ical/…/basic.ics)를 넣어 주세요' });
    const g = readG(req.calUser);
    g.url = url;
    writeG(req.calUser, g);
    res.json({ ok: true, linked: !!url });
  });
  app.post('/api/cal/feed', auth, async (req, res) => {
    const src = (await body(req)) || {}, u = req.calUser;
    let tok = Object.keys(feeds).find((k) => feeds[k].id === u.id);
    if (tok && src.reset) { delete feeds[tok]; tok = ''; }
    if (!tok) { tok = crypto.randomBytes(18).toString('base64url'); feeds[tok] = { id: u.id, name: u.name, at: Date.now() }; fs.writeFileSync(FEEDS, JSON.stringify(feeds)); }
    res.json({ ok: true, url: PUBLIC + '/api/cal/feed/' + tok + '.ics' });
  });
  //  ⚠ 로그인 없이(구글이 읽는다) — 주소 자체가 열쇠. 새 주소를 만들면 예전 주소는 바로 막힌다.
  app.get('/api/cal/feed/:tok.ics', (req, res) => {
    const f = feeds[req.params.tok];
    if (!f) return res.status(404).send('not found');
    const u = { id: f.id, name: f.name };
    const o = readU(u);
    res.set('Content-Type', 'text/calendar; charset=utf-8').set('Cache-Control', 'no-store').send(makeICS(u, events.filter((e) => visible(u, e)), (o.data && o.data.annivs) || []));
  });

  //  ════ 📱 폰·브라우저용 달력 화면 — 바탕화면 달력과 같은 화면(calendar-page.html)을 포털이 그대로 보여 준다 ════
  const PAGE = ctx.page || path.join(__dirname, 'calendar-page.html');
  app.get('/calendar', (req, res) => {
    if (!userOf(req)) return res.redirect('/?next=' + encodeURIComponent('/calendar'));
    let html;
    try { html = fs.readFileSync(PAGE, 'utf8'); } catch (e) { return res.status(404).send('calendar-page.html 이 포털 폴더에 없습니다'); }
    res.set('Cache-Control', 'no-store').type('html').send(html.replace(/\{\{VER\}\}/g, 'portal').replace('<head>', '<head><script>window.__CAL_PORTAL=1</script>'));
  });
};

//  ── iCalendar(.ics) 읽기·쓰기 ─────────────────────────────
//   읽기: VEVENT 의 SUMMARY·DTSTART·DTEND·LOCATION·DESCRIPTION·RRULE(DAILY/WEEKLY/MONTHLY/YEARLY · INTERVAL · COUNT · UNTIL · BYDAY)·EXDATE
//   시각은 한국 시간으로(…Z 는 +9시간, TZID 가 있으면 그 시각 그대로).
function icsLines(t) { return String(t).replace(/\r\n[ \t]/g, '').replace(/\n[ \t]/g, '').split(/\r?\n/); }
function icsUnesc(s) { return String(s || '').replace(/\\n/gi, '\n').replace(/\\([,;\\])/g, '$1'); }
function icsDate(v, params) {
  const m = /^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})?(Z)?)?$/.exec(String(v || '').trim());
  if (!m) return null;
  if (!m[4]) return { d: m[1] + '-' + m[2] + '-' + m[3], t: '' };
  let dt = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
  if (m[7]) dt = new Date(dt.getTime() + 9 * 3600000);                   //  UTC → 한국
  else if (params && /TZID=/i.test(params) && !/Seoul|Asia\/Seoul/i.test(params)) { /* 다른 시간대 — 그 시각 그대로 둔다 */ }
  const iso = dt.toISOString();
  return { d: iso.slice(0, 10), t: iso.slice(11, 16) };
}
const DAYMS = 86400000;
const addD = (d, n) => new Date(Date.parse(d + 'T00:00:00Z') + n * DAYMS).toISOString().slice(0, 10);
function icsEvents(text, from, to) {
  const out = [];
  let cur = null;
  for (const ln of icsLines(text)) {
    if (ln === 'BEGIN:VEVENT') { cur = { ex: {} }; continue; }
    if (ln === 'END:VEVENT') { if (cur && cur.s) expand(cur); cur = null; continue; }
    if (!cur) continue;
    const i = ln.indexOf(':');
    if (i < 0) continue;
    const head = ln.slice(0, i), val = ln.slice(i + 1), name = head.split(';')[0].toUpperCase(), params = head.slice(name.length);
    if (name === 'SUMMARY') cur.title = icsUnesc(val);
    else if (name === 'LOCATION') cur.place = icsUnesc(val);
    else if (name === 'DESCRIPTION') cur.memo = icsUnesc(val).slice(0, 500);
    else if (name === 'UID') cur.uid = val;
    else if (name === 'DTSTART') cur.s = icsDate(val, params);
    else if (name === 'DTEND') cur.e = icsDate(val, params);
    else if (name === 'RRULE') cur.rr = val;
    else if (name === 'STATUS' && /CANCELLED/i.test(val)) cur.cancel = true;
    else if (name === 'EXDATE') val.split(',').forEach((v) => { const x = icsDate(v, params); if (x) cur.ex[x.d] = 1; });
  }
  function push(ev, s, len) {
    if (ev.ex[s]) return;
    const e = len > 0 ? addD(s, len) : s;
    if (s <= to && e >= from) out.push({ id: 'g-' + (ev.uid || '').slice(0, 40) + '-' + s, title: ev.title || '(제목 없음)', start: s, end: e, time: ev.s.t, endTime: ev.e ? ev.e.t : '', place: ev.place || '', memo: ev.memo || '', kind: 'google' });
  }
  function expand(ev) {
    if (ev.cancel || out.length > 3000) return;
    let len = 0;
    if (ev.e) { len = Math.round((Date.parse(ev.e.d) - Date.parse(ev.s.d)) / DAYMS); if (!ev.s.t && len > 0) len -= 1; if (len < 0) len = 0; }
    if (!ev.rr) return push(ev, ev.s.d, len);
    const r = {};
    ev.rr.split(';').forEach((kv) => { const [k, v] = kv.split('='); r[k.toUpperCase()] = v; });
    const iv = Math.max(1, parseInt(r.INTERVAL, 10) || 1), cnt = parseInt(r.COUNT, 10) || 0;
    const until = r.UNTIL ? (icsDate(r.UNTIL) || {}).d : '';
    const W = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA'];
    const byday = r.BYDAY && r.FREQ === 'WEEKLY' ? r.BYDAY.split(',').map((x) => W.indexOf(x.replace(/^[-+\d]+/, ''))).filter((x) => x >= 0) : null;
    let n = 0, d = ev.s.d, guard = 0;
    const s0 = new Date(ev.s.d + 'T00:00:00Z');
    while (guard++ < 5000) {
      if ((until && d > until) || d > to || (cnt && n >= cnt)) break;
      if (byday) {
        //  그 주의 고른 요일들
        const wk = new Date(d + 'T00:00:00Z'), base = addD(d, -wk.getUTCDay());
        for (const wd of byday.sort()) { const x = addD(base, wd); if (x >= ev.s.d && (!until || x <= until) && x <= to && !(cnt && n >= cnt)) { n++; push(ev, x, len); } }
        d = addD(base, 7 * iv);
        continue;
      }
      n++; push(ev, d, len);
      if (r.FREQ === 'DAILY') d = addD(d, iv);
      else if (r.FREQ === 'WEEKLY') d = addD(d, 7 * iv);
      else if (r.FREQ === 'MONTHLY' || r.FREQ === 'YEARLY') {
        const k = r.FREQ === 'MONTHLY' ? n * iv : n * iv * 12, y = s0.getUTCFullYear(), m = s0.getUTCMonth() + k;
        const nd = new Date(Date.UTC(y, m, s0.getUTCDate()));
        if (nd.getUTCDate() !== s0.getUTCDate()) { n++; continue; }      //  31일이 없는 달은 건너뛴다
        d = nd.toISOString().slice(0, 10);
      } else break;
    }
  }
  return out;
}
function icsEsc(s) { return String(s || '').replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/([,;])/g, '\\$1'); }
function icsFold(l) { const out = []; let s = l; while (Buffer.byteLength(s) > 74) { let i = 70; while (Buffer.byteLength(s.slice(0, i)) > 74) i--; out.push(s.slice(0, i)); s = ' ' + s.slice(i); } out.push(s); return out.join('\r\n'); }
function makeICS(u, list, annivs) {
  const L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Hanil//DeskCal//KO', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:한일 포털 일정 (' + icsEsc(u.name) + ')', 'X-WR-TIMEZONE:Asia/Seoul'];
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
  const ymd = (d) => d.replace(/-/g, '');
  //  ⚠ 줄 접기(75바이트)는 맨 끝에서 한 번만 한다
  const RR = { weekly: 'WEEKLY', monthly: 'MONTHLY', yearly: 'YEARLY' };
  for (const e of list) {
    L.push('BEGIN:VEVENT', 'UID:' + e.id + '@hanil-cal', 'DTSTAMP:' + stamp);
    if (e.time) {
      L.push('DTSTART;TZID=Asia/Seoul:' + ymd(e.start) + 'T' + e.time.replace(':', '') + '00');
      L.push('DTEND;TZID=Asia/Seoul:' + ymd(e.end) + 'T' + (e.endTime || e.time).replace(':', '') + '00');
    } else {
      L.push('DTSTART;VALUE=DATE:' + ymd(e.start), 'DTEND;VALUE=DATE:' + ymd(addD(e.end, 1)));
    }
    if (e.repeat && RR[e.repeat]) L.push('RRULE:FREQ=' + RR[e.repeat] + (e.until ? ';UNTIL=' + ymd(e.until) : ''));
    L.push(('SUMMARY:' + (e.kind === 'company' ? '[회사] ' : '') + icsEsc(e.title)));
    if (e.place) L.push(('LOCATION:' + icsEsc(e.place)));
    if (e.memo || e.ownerName) L.push(('DESCRIPTION:' + icsEsc((e.memo ? e.memo + '\n' : '') + '올린 사람: ' + (e.ownerName || ''))));
    L.push('END:VEVENT');
  }
  //  기념일(양력만 — 음력 기념일은 해마다 날짜가 달라 구글 반복으로 못 나타낸다 → 올해·내년 두 번 넣는다)
  for (const a of annivs || []) {
    if (!a || !a.title || !/^\d{2}-\d{2}$/.test(a.md || '')) continue;
    if (a.lunar && Array.isArray(a.solar)) {
      a.solar.forEach((d, i) => { if (/^\d{4}-\d{2}-\d{2}$/.test(d)) L.push('BEGIN:VEVENT', 'UID:anv-' + i + '-' + icsEsc(a.id || a.title) + '@hanil-cal', 'DTSTAMP:' + stamp, 'DTSTART;VALUE=DATE:' + ymd(d), 'DTEND;VALUE=DATE:' + ymd(addD(d, 1)), ('SUMMARY:🎂 ' + icsEsc(a.title) + ' (음력)'), 'END:VEVENT'); });
      continue;
    }
    const y = String(a.year || new Date().getFullYear());
    L.push('BEGIN:VEVENT', 'UID:anv-' + icsEsc(a.id || a.title) + '@hanil-cal', 'DTSTAMP:' + stamp, 'DTSTART;VALUE=DATE:' + y + a.md.replace('-', ''), 'DTEND;VALUE=DATE:' + ymd(addD(y + '-' + a.md, 1)), 'RRULE:FREQ=YEARLY', ('SUMMARY:🎂 ' + icsEsc(a.title)), 'END:VEVENT');
  }
  L.push('END:VCALENDAR');
  return L.map(icsFold).join('\r\n') + '\r\n';
}
module.exports.icsEvents = icsEvents;
module.exports.makeICS = makeICS;
