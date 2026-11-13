#!/usr/bin/env node
//  📠 한일 팩스 — CimFAX 장비와 직접 통신하는 독립 팩스 프로그램 (포털과 따로 돈다)
//
//   받기: 장비에서 새 팩스를 직접 가져와 PDF 로 보관 (FaxBox·공유 폴더 필요 없음)
//   보내기: PDF 를 올리면 팩스 그림(TIFF)으로 바꿔 장비로 보냄 (Ghostscript 필요)
//   화면: http://서버주소:3990  — 직원 계정으로 로그인
//
//   쓰는 법
//     node hanil-fax.js                         켜기 (설정: 같은 폴더의 hanil-fax.json)
//     node hanil-fax.js setup                   처음 설정 (장비 주소·계정·비밀번호 묻기)
//     node hanil-fax.js adduser 아이디 이름 [--admin]   직원 추가 (비밀번호를 묻는다)
//     node hanil-fax.js passwd 아이디           비밀번호 바꾸기
//     node hanil-fax.js deluser 아이디          직원 지우기
//     node hanil-fax.js users                   직원 목록
//     node hanil-fax.js check                   장비 로그인 시험
//
//   npm 으로 깔 것 없음 — Node.js 18 이상만 있으면 된다.
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');

const HERE = __dirname;
const CFG_FILE = process.env.HANIL_FAX_CONFIG || path.join(HERE, 'hanil-fax.json');
const VERSION = '1.0.0';
//  같은 폴더(배포 묶음) 또는 저장소의 ../portal 에서 모듈을 찾는다
const mod = (n) => { const a = path.join(HERE, n + '.js'); return fs.existsSync(a) ? a : path.join(HERE, '..', 'portal', n + '.js'); };

//  ── 설정 ──
function loadCfg() {
  let c = {};
  try { c = JSON.parse(fs.readFileSync(CFG_FILE, 'utf8')); } catch (e) {
    if (e.code !== 'ENOENT') { console.error('❌ 설정 파일을 읽지 못했습니다 (' + CFG_FILE + '): ' + e.message); process.exit(1); }
  }
  c.port = Number(c.port) || 3990;
  c.users = c.users || {};
  return c;
}
function saveCfg(c) {
  const tmp = CFG_FILE + '.new';
  fs.writeFileSync(tmp, JSON.stringify(c, null, 2), { mode: 0o600 });
  fs.renameSync(tmp, CFG_FILE);
  try { fs.chmodSync(CFG_FILE, 0o600); } catch (e) { /* 윈도 */ }
}
const hashPw = (pw, salt) => crypto.scryptSync(String(pw), salt, 32).toString('hex');
function checkPw(u, pw) {
  if (!u || !u.hash || !u.salt) return false;
  const a = Buffer.from(hashPw(pw, u.salt), 'hex'), b = Buffer.from(u.hash, 'hex');
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

//  ── 묻기 (비밀번호는 화면에 안 보이게) ──
function ask(q, hidden) {
  return new Promise((ok) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    if (hidden) {
      rl._writeToOutput = (s) => { if (s.includes(q)) rl.output.write(s); else rl.output.write(''); };
    }
    rl.question(q, (a) => { rl.close(); if (hidden) process.stdout.write('\n'); ok(a.trim()); });
  });
}
async function askNewPw() {
  for (;;) {
    const a = await ask('  비밀번호 (6자 이상): ', true);
    if (a.length < 6) { console.log('  6자 이상으로 넣어 주세요'); continue; }
    const b = await ask('  한 번 더: ', true);
    if (a !== b) { console.log('  두 번 넣은 것이 다릅니다'); continue; }
    return a;
  }
}

//  ── 명령 ──
async function cli(cmd, args) {
  const c = loadCfg();
  const flag = (f) => args.includes(f);
  const pos = args.filter((a) => !a.startsWith('--'));
  if (cmd === 'setup') {
    console.log('📠 한일 팩스 — 처음 설정 (' + CFG_FILE + ')');
    const d = c.device || {};
    d.host = (await ask('  CimFAX 장비 주소 [' + (d.host || '192.168.1.156') + ']: ')) || d.host || '192.168.1.156';
    d.user = (await ask('  CimFAX 계정 [' + (d.user || 'admin') + ']: ')) || d.user || 'admin';
    const pw = await ask('  CimFAX 비밀번호' + (d.password ? ' [그대로 두려면 Enter]' : '') + ': ', true);
    if (pw) d.password = pw;
    c.device = d;
    c.receive = 'device';
    const port = await ask('  화면 포트 [' + c.port + ']: ');
    if (port) c.port = Number(port) || c.port;
    saveCfg(c);
    console.log('✅ 저장했습니다. 장비 로그인 시험:  node hanil-fax.js check');
    if (!Object.keys(c.users).length) console.log('   직원 추가:  node hanil-fax.js adduser 아이디 이름 --admin');
    return;
  }
  if (cmd === 'adduser') {
    const [id, ...nameParts] = pos;
    if (!id || !/^[A-Za-z0-9._-]{2,30}$/.test(id)) { console.log('쓰는 법: node hanil-fax.js adduser 아이디(영문·숫자) 이름 [--admin]'); process.exit(1); }
    if (c.users[id]) { console.log('이미 있는 아이디입니다 — 비밀번호를 바꾸려면: node hanil-fax.js passwd ' + id); process.exit(1); }
    const name = nameParts.join(' ') || id;
    console.log('👤 ' + name + ' (' + id + ')' + (flag('--admin') ? ' — 관리자' : ''));
    const pw = await askNewPw();
    const salt = crypto.randomBytes(16).toString('hex');
    c.users[id] = { name, admin: flag('--admin'), salt, hash: hashPw(pw, salt), created: new Date().toISOString() };
    saveCfg(c);
    console.log('✅ 추가했습니다. 켜져 있는 프로그램에도 바로 적용됩니다.');
    return;
  }
  if (cmd === 'passwd') {
    const id = pos[0];
    if (!c.users[id]) { console.log('없는 아이디입니다: ' + id); process.exit(1); }
    const pw = await askNewPw();
    c.users[id].salt = crypto.randomBytes(16).toString('hex');
    c.users[id].hash = hashPw(pw, c.users[id].salt);
    saveCfg(c);
    console.log('✅ 바꿨습니다.');
    return;
  }
  if (cmd === 'deluser') {
    const id = pos[0];
    if (!c.users[id]) { console.log('없는 아이디입니다: ' + id); process.exit(1); }
    delete c.users[id];
    saveCfg(c);
    console.log('✅ 지웠습니다.');
    return;
  }
  if (cmd === 'users') {
    const ids = Object.keys(c.users);
    if (!ids.length) console.log('직원이 없습니다 — node hanil-fax.js adduser 아이디 이름 --admin');
    ids.forEach((id) => console.log((c.users[id].admin ? '★ ' : '  ') + id + '  ' + c.users[id].name));
    return;
  }
  if (cmd === 'check') {
    if (!c.device || !c.device.host) { console.log('장비 설정이 없습니다 — node hanil-fax.js setup'); process.exit(1); }
    const cim = require(mod('cimfax-client'));
    try {
      const k = await cim.login(c.device, cim.PORT.cmd);
      k.close();
      console.log('✅ 장비 로그인 성공 — ' + k.info.serverName + ' · 장비 ID ' + k.info.serverId);
      const list = await cim.listNewFaxes(c.device, 0, 1);
      console.log(list.length ? '✅ 받은 팩스 목록 읽기 성공 (가장 오래된 것: 작업 ' + list[0].taskId + ', ' + list[0].timeRaw + ', 남은 ' + list[0].left + '건)' : '받은 팩스 목록이 비어 있습니다');
    } catch (e) { console.log('❌ ' + e.message); process.exit(1); }
    return;
  }
  console.log('모르는 명령입니다: ' + cmd + '   (setup · adduser · passwd · deluser · users · check)');
  process.exit(1);
}

//  ── 작은 웹 틀 (Express 와 같은 모양: app.get/post/put/delete, req.params/query/session, res.json/status/redirect/sendFile) ──
function makeApp() {
  const routes = [];
  const add = (method) => (p, ...h) => {
    const keys = [];
    const re = new RegExp('^' + p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\:([A-Za-z_]+)/g, (m, k) => { keys.push(k); return '([^/]+)'; }).replace(/:([A-Za-z_]+)/g, (m, k) => { keys.push(k); return '([^/]+)'; }) + '/?$');
    routes.push({ method, re, keys, h });
  };
  const app = { get: add('GET'), post: add('POST'), put: add('PUT'), delete: add('DELETE'), routes };
  app.handle = (req, res) => {
    for (const r of routes) {
      if (r.method !== req.method && !(r.method === 'GET' && req.method === 'HEAD')) continue;
      const m = r.re.exec(req.path);
      if (!m) continue;
      req.params = {};
      r.keys.forEach((k, i) => { req.params[k] = decodeURIComponent(m[i + 1]); });
      let i = 0;
      const next = () => { const f = r.h[i++]; if (f) Promise.resolve(f(req, res, next)).catch((e) => { console.error(e); if (!res.headersSent) res.status(500).json({ ok: false, error: '서버 오류' }); }); };
      next();
      return true;
    }
    return false;
  };
  return app;
}
function decorate(res) {
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (o) => { if (!res.getHeader('Content-Type')) res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.end(JSON.stringify(o)); return res; };
  res.send = (s) => { if (!res.getHeader('Content-Type')) res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(s); return res; };
  res.redirect = (u) => { res.statusCode = 302; res.setHeader('Location', u); res.end(); return res; };
  res.sendFile = (p) => {
    fs.readFile(p, (e, b) => {
      if (e) { res.statusCode = 404; return res.end('없음'); }
      if (!res.getHeader('Content-Type')) res.setHeader('Content-Type', p.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream');
      res.end(b);
    });
  };
  return res;
}

//  ── 세션 ──
const SESS_FILE = () => path.join(DATA_DIR(), 'sessions.json');
let DATA_DIR = () => path.join(HERE, 'fax-store');
const sessions = new Map();
const SESSION_MS = 12 * 3600 * 1000;
function loadSessions() {
  try {
    const o = JSON.parse(fs.readFileSync(SESS_FILE(), 'utf8'));
    Object.entries(o).forEach(([k, v]) => { if (v.exp > Date.now()) sessions.set(k, v); });
  } catch (e) { /* 처음 */ }
}
let sessSaveT = null;
function saveSessions() {
  clearTimeout(sessSaveT);
  sessSaveT = setTimeout(() => {
    try { fs.writeFileSync(SESS_FILE(), JSON.stringify(Object.fromEntries(sessions)), { mode: 0o600 }); } catch (e) { /* 넘어감 */ }
  }, 500);
}
function cookieOf(req, name) {
  const m = new RegExp('(?:^|;\\s*)' + name + '=([^;]+)').exec(req.headers.cookie || '');
  return m ? m[1] : '';
}

//  ── 로그인 화면 ──
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
function loginPage(err, next) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>한일 팩스 — 로그인</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--line:#e3e6ea;--text:#1d2329;--sub:#66707a;--accent:#1f6feb;--bad:#d1242f}
@media (prefers-color-scheme:dark){:root{--bg:#15181c;--card:#1d2126;--line:#30363d;--text:#e6e8eb;--sub:#9aa4ae}}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,"Malgun Gothic","맑은 고딕",sans-serif;padding:16px}
form{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px;width:min(360px,100%);display:flex;flex-direction:column;gap:12px}
h1{margin:0 0 4px;font-size:20px}p{margin:0;color:var(--sub);font-size:14px}
input{padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font:inherit}
button{padding:10px;border:0;border-radius:8px;background:var(--accent);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.err{color:var(--bad)}
</style></head><body>
<form method="post" action="/login">
  <h1>📠 한일 팩스</h1><p>직원 계정으로 로그인하세요.</p>
  ${err ? '<p class="err" id="err">' + esc(err) + '</p>' : ''}
  <input type="hidden" name="next" value="${esc(next || '/fax')}">
  <input name="username" id="u" placeholder="아이디" autocomplete="username" required autofocus>
  <input name="password" id="p" type="password" placeholder="비밀번호" autocomplete="current-password" required>
  <button id="go">로그인</button>
</form></body></html>`;
}

//  ── 켜기 ──
function start(opts) {
  opts = opts || {};
  let cfg = loadCfg();
  if (opts.cfg) cfg = Object.assign(cfg, opts.cfg);
  if (cfg.dir) DATA_DIR = () => cfg.dir;
  fs.mkdirSync(DATA_DIR(), { recursive: true });
  loadSessions();
  //  설정 파일이 바뀌면 (직원 추가 등) 다시 읽는다
  let users = cfg.users;
  if (!opts.cfg) fs.watchFile(CFG_FILE, { interval: 2000 }, () => { try { users = loadCfg().users; } catch (e) { /* 그대로 */ } });

  const app = makeApp();
  const fails = new Map();   //  IP → [시각…]  (10분에 5번 틀리면 잠깐 막음)

  app.get('/', (req, res) => {
    if (req.session.user) return res.redirect('/fax');
    res.send(loginPage(req.query.err, req.query.next));
  });
  app.post('/login', (req, res) => {
    let s = '';
    req.setEncoding('utf8');
    req.on('data', (c) => { s += c; if (s.length > 4096) req.destroy(); });
    req.on('end', () => {
      const f = new URLSearchParams(s);
      const ip = req.socket.remoteAddress || '';
      const now = Date.now(), list = (fails.get(ip) || []).filter((t) => now - t < 600000);
      const nextUrl = /^\/[A-Za-z0-9/_#?=&.-]*$/.test(f.get('next') || '') ? f.get('next') : '/fax';
      if (list.length >= 5) return res.send(loginPage('잠시 뒤 다시 해 주세요 (10분에 5번 틀림)', nextUrl));
      const id = String(f.get('username') || '').trim(), u = users[id];
      if (!checkPw(u, f.get('password') || '')) {
        list.push(now); fails.set(ip, list);
        return res.send(loginPage('아이디 또는 비밀번호가 틀립니다', nextUrl));
      }
      fails.delete(ip);
      const sid = crypto.randomBytes(24).toString('hex');
      sessions.set(sid, { user: { username: id, name: u.name, admin: !!u.admin }, exp: now + SESSION_MS });
      saveSessions();
      res.setHeader('Set-Cookie', 'hfsid=' + sid + '; HttpOnly; SameSite=Lax; Path=/; Max-Age=' + SESSION_MS / 1000);
      res.redirect(nextUrl);
    });
  });
  app.get('/logout', (req, res) => {
    const sid = cookieOf(req, 'hfsid');
    if (sid) { sessions.delete(sid); saveSessions(); }
    res.setHeader('Set-Cookie', 'hfsid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0');
    res.redirect('/');
  });
  app.get('/api/fax/me', (req, res) => {
    const u = req.session.user;
    if (!u) return res.status(401).json({ ok: false, error: '로그인이 필요합니다' });
    res.json({ ok: true, id: u.username, name: u.name, admin: !!u.admin, standalone: true, version: VERSION });
  });

  const fax = require(mod('fax-route'))(app, Object.assign({
    dir: DATA_DIR(),
    inbox: cfg.inbox || [],
    receive: cfg.receive || (cfg.device ? 'device' : undefined),
    device: cfg.device,
    sendBy: cfg.sendBy,
    sentView: cfg.sentView || 'all',
    view: cfg.view,
    route: cfg.route,
    sinceDays: cfg.sinceDays,
    receiveSec: cfg.receiveSec,
    user: (req) => {
      const u = req.session && req.session.user;
      if (!u) return null;
      //  지워진 직원은 바로 막는다
      const live = users[u.username];
      if (!live) return null;
      return { id: u.username, name: live.name, admin: !!live.admin };
    },
  }, opts.ctx || {}));

  const srv = http.createServer((req, res) => {
    decorate(res);
    const u = new URL(req.url, 'http://x');
    req.path = u.pathname;
    req.query = Object.fromEntries(u.searchParams);
    const sid = cookieOf(req, 'hfsid');
    const s = sid && sessions.get(sid);
    if (s && s.exp > Date.now()) {
      if (s.exp - Date.now() < SESSION_MS - 600000) { s.exp = Date.now() + SESSION_MS; saveSessions(); }   //  쓰는 동안 연장
      req.session = s;
    } else {
      if (s) { sessions.delete(sid); saveSessions(); }
      req.session = {};
    }
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'same-origin');
    if (!app.handle(req, res)) res.status(404).json({ ok: false, error: '없는 주소입니다' });
  });
  return new Promise((ok) => srv.listen(opts.port !== undefined ? opts.port : cfg.port, opts.host || cfg.host || '0.0.0.0', () => {
    if (!opts.quiet) {
      console.log('📠 한일 팩스 ' + VERSION + ' — http://' + (cfg.host || '0.0.0.0') + ':' + srv.address().port + '/fax');
      console.log('   장비: ' + (cfg.device ? cfg.device.host + ' (' + cfg.device.user + ')' + (cfg.device.dryRun ? ' · 시험 모드' : '') : '설정 없음 — node hanil-fax.js setup'));
      console.log('   직원: ' + Object.keys(users).length + '명' + (Object.keys(users).length ? '' : ' — node hanil-fax.js adduser 아이디 이름 --admin'));
    }
    ok({ srv, fax, port: srv.address().port });
  }));
}

module.exports = { start, makeApp, hashPw, checkPw };

if (require.main === module) {
  const [cmd, ...args] = process.argv.slice(2);
  if (cmd && cmd !== 'run') cli(cmd, args).catch((e) => { console.error('❌ ' + e.message); process.exit(1); });
  else start().catch((e) => { console.error('❌ ' + e.message); process.exit(1); });
}
