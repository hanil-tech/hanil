//  📠 CimFAX 수신팩스 — 포털에 넣는 조각 (fax-route.js)
//
//   넣는 법: 이 파일을 포털 폴더(server.js 옆)에 두고, 세션(express-session)이 붙은 뒤 한 줄:
//       require('./fax-route')(app, {
//         db: async (sql, params) => (await pool.request()...).recordset,   // 포털 DB 실행기(아래 설명)
//         agentToken: process.env.FAX_AGENT_TOKEN,                          // 수집 에이전트용 토큰
//       });
//     (로그인 안 했으면 로그인 화면으로 — 팩스 파일도 로그인해야 받습니다)
//   그리고 fax-schema.sql 을 포털 DB 에 한 번 적용합니다. 자세한 건 설치안내.txt.
//
//   ctx(두 번째 인자) — 포털 구조에 맞춰 넘겨 줍니다. 모르는 건 기본값으로 돕니다:
//     db         (필수) async (sql, params[]) => rows.  sql 의 자리표시는 '?'(차례대로). ※ MSSQL 은 아래 어댑터로 ?→@p 로 바꿔 주세요(설치안내).
//     dialect    'mssql'(기본) | 'mysql'  — 페이지 자르는 문법만 다릅니다.
//     user(req)  로그인한 사람 → {id, name, admin}.  기본은 흔한 세션 모양을 봅니다.
//     agentToken 수집 에이전트 Bearer 토큰(업로드/보고 전용). 없으면 env FAX_AGENT_TOKEN.
//     lanOnly    기본 true — 에이전트는 사내망 IP 에서만.  (테스트할 때만 false)
//     dir        파일 저장 폴더(기본 이 파일 옆 fax-store/).
//     matchPartner(digits) → {partner_id, match_type, suggest?:[{id,name}]} 또는 null.  거래처 자동 매칭(아래 기본 설명).
//     assigneeOf(partner_id) → user_id   거래처 담당 영업사원(자동 배정). 없으면 배정 안 함.
//     notify(kind, info)   알림 보내기(new-fax / assign / agent-down / missing). 없으면 조용.
//   ⚠ 팩스에는 주민번호·계좌·계약서가 있을 수 있습니다 — 파일은 **로그인 다운로드로만** 내줍니다(공개 주소 없음). 열람·배정은 fax_event 에 남깁니다.
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

module.exports = function mountFax(app, ctx) {
  ctx = ctx || {};

  // ── 로그인한 사람 (bigfile·calendar 와 같은 잣대) ──────────────
  const userOf = ctx.user || ((req) => {
    const u = (req.session && (req.session.user || req.session.member)) || null;
    if (!u) return null;
    return {
      id: u.id != null ? u.id : (u.uid != null ? u.uid : u.userId),
      name: u.name || u.nick || u.username || '',
      admin: !!(u.admin || u.is_admin || u.isAdmin || u.role === 'admin'),
    };
  });
  const isAdmin = ctx.isAdmin || ((u) => !!(u && u.admin));

  // ── DB (포털이 넘겨 준 실행기) ────────────────────────────────
  const rawDb = ctx.db;
  if (typeof rawDb !== 'function') {
    console.warn('[fax] ⚠ ctx.db 가 없습니다 — 포털 DB 실행기(async (sql,params)=>rows)를 넘겨 주세요. 라우트는 뜨지만 저장·조회가 안 됩니다.');
  }
  const DIALECT = ctx.dialect || 'mssql';
  const all = async (sql, params) => (typeof rawDb === 'function' ? (await rawDb(sql, params || [])) || [] : []);
  const one = async (sql, params) => (await all(sql, params))[0] || null;
  const run = async (sql, params) => { await all(sql, params); };
  //  페이지 자르기(목록) — 방언마다 다른 유일한 곳
  const pageClause = (limit, offset) => DIALECT === 'mysql'
    ? ` LIMIT ${(offset | 0)}, ${(limit | 0)}`
    : ` OFFSET ${(offset | 0)} ROWS FETCH NEXT ${(limit | 0)} ROWS ONLY`;

  // ── 파일 저장소 ───────────────────────────────────────────────
  const STORE = ctx.dir || process.env.FAX_DIR || path.join(__dirname, 'fax-store');
  fs.mkdirSync(STORE, { recursive: true });
  const ymd = (d) => { const z = (n) => String(n).padStart(2, '0'); return d.getFullYear() + '/' + z(d.getMonth() + 1); };

  // ── 수집 에이전트 토큰 + 사내망만 ─────────────────────────────
  const TOKEN = ctx.agentToken || process.env.FAX_AGENT_TOKEN || '';
  const lanOnly = ctx.lanOnly !== false;
  function clientIp(req) {
    let ip = (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket.remoteAddress || '';
    if (ip.startsWith('::ffff:')) ip = ip.slice(7);
    return ip;
  }
  function isLan(ip) {
    if (!ip) return false;
    if (ip === '127.0.0.1' || ip === '::1' || ip.toLowerCase() === 'localhost') return true;
    if (/^10\./.test(ip) || /^192\.168\./.test(ip)) return true;
    const m = /^172\.(\d+)\./.exec(ip); if (m && +m[1] >= 16 && +m[1] <= 31) return true;
    return false;
  }
  function needAgent(req, res, next) {
    const tok = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
    if (!TOKEN) return res.status(503).json({ error: '에이전트 토큰이 포털에 설정되지 않았습니다(FAX_AGENT_TOKEN).' });
    if (!tok || tok !== TOKEN) return res.status(401).json({ error: '토큰이 올바르지 않습니다.' });
    if (lanOnly && !isLan(clientIp(req))) return res.status(403).json({ error: '사내망에서만 허용됩니다.' });
    next();
  }
  function needLogin(req, res, next) {
    if (userOf(req)) return next();
    if ((req.headers.accept || '').indexOf('application/json') >= 0 || req.path.startsWith('/api/'))
      return res.status(401).json({ error: '로그인이 필요합니다.' });
    res.redirect('/?next=' + encodeURIComponent(req.originalUrl || '/fax'));
  }
  function needAdmin(req, res, next) { const u = userOf(req); if (u && isAdmin(u)) return next(); res.status(403).json({ error: '관리자만' }); }

  // ── 번호 다루기 ───────────────────────────────────────────────
  const digitsOnly = (s) => String(s || '').replace(/\D+/g, '');
  const INTERNET_FAX = (ctx.internetFaxNames || ['SmartWorks', 'ACEFAX', 'KODIT EFAX', 'SENDLABS FAX1', 'SENDLABS FAX2'])
    .map((s) => s.toLowerCase());
  function isInternetFax(raw) {
    const s = String(raw || '').toLowerCase();
    return INTERNET_FAX.some((n) => s.indexOf(n) >= 0);
  }
  function meaningless(d) {
    if (!d) return true;
    if (/^0+$/.test(d)) return true;      // 0000000000
    if (d.length < 4) return true;        // 1, 123
    return false;
  }

  // ── 거래처 자동 매칭 (설계서 5.2) ─────────────────────────────
  //   ① 숫자만 → ② 학습표(fax_sender_map) → ③ 거래처 팩스/전화 완전일치 → ④ 뒤 8자리 후보(제안만)
  //   인터넷팩스 이름·의미없는 번호는 미매칭. ③④ 는 거래처표를 알아야 하므로 ctx.matchPartner 로 넘겨 주세요(없으면 ①②만).
  async function matchPartner(rawSender) {
    const digits = digitsOnly(rawSender);
    if (isInternetFax(rawSender) || meaningless(digits)) return { digits, partner_id: null, match_type: null, suggest: [] };
    //  ② 학습표
    const learned = await one('SELECT partner_id FROM fax_sender_map WHERE sender_digits = ?', [digits]);
    if (learned && learned.partner_id != null) return { digits, partner_id: learned.partner_id, match_type: 'learned', suggest: [] };
    //  ③④ 거래처표 — 포털이 ctx.matchPartner 로 알려 주면 그걸 쓴다
    if (typeof ctx.matchPartner === 'function') {
      try {
        const r = await ctx.matchPartner(digits);
        if (r && r.partner_id != null) return { digits, partner_id: r.partner_id, match_type: r.match_type || 'exact', suggest: r.suggest || [] };
        if (r && r.suggest && r.suggest.length) return { digits, partner_id: null, match_type: 'suggest', suggest: r.suggest };
      } catch (e) { console.warn('[fax] matchPartner 오류:', e.message); }
    }
    return { digits, partner_id: null, match_type: null, suggest: [] };
  }

  // ── TIF→PDF · 쪽수 · 썸네일 (있는 도구로, 없으면 원본만) ───────
  const has = (cmd) => { try { return spawnSync(process.platform === 'win32' ? 'where' : 'which', [cmd]).status === 0; } catch (e) { return false; } };
  const HAS = { magick: has('magick') || has('convert'), gs: has('gs'), pdfinfo: has('pdfinfo'), pdftoppm: has('pdftoppm') };
  const magick = has('magick') ? 'magick' : 'convert';
  function pdfPages(pdf) {
    try {
      if (HAS.pdfinfo) {
        const o = spawnSync('pdfinfo', [pdf], { encoding: 'utf8' });
        const m = /Pages:\s+(\d+)/.exec(o.stdout || ''); if (m) return +m[1];
      }
      if (HAS.magick) {
        const o = spawnSync(magick, ['identify', '-format', '%n ', pdf], { encoding: 'utf8' });
        const n = (o.stdout || '').trim().split(/\s+/).filter(Boolean).length; if (n) return n;
      }
    } catch (e) {}
    return null;
  }
  //  원본(TIF/PDF) → { pdf, pages, thumb }.  thumb·pages 는 못 만들면 null.
  function makePdfAndThumb(origPath, isTif, baseNoExt) {
    let pdf = origPath, pages = null, thumb = null;
    try {
      if (isTif) {
        const out = baseNoExt + '.pdf';
        if (HAS.magick && spawnSync(magick, [origPath, out]).status === 0) pdf = out;
        else if (has('tiff2pdf') && spawnSync('tiff2pdf', ['-o', out, origPath]).status === 0) pdf = out;
      }
      pages = pdfPages(pdf);
      const tb = baseNoExt + '.thumb.png';
      if (HAS.pdftoppm && spawnSync('pdftoppm', ['-png', '-f', '1', '-l', '1', '-scale-to', '480', pdf, baseNoExt + '.thumb']).status === 0) {
        //  pdftoppm 은 .thumb-1.png 처럼 만든다 → 맞춰 찾는다
        const cand = [tb, baseNoExt + '.thumb-1.png', baseNoExt + '.thumb-01.png'];
        thumb = cand.find((p) => fs.existsSync(p)) || null;
      } else if (HAS.magick && spawnSync(magick, ['-density', '120', pdf + '[0]', '-resize', '480x', tb]).status === 0 && fs.existsSync(tb)) {
        thumb = tb;
      }
    } catch (e) { console.warn('[fax] 변환 오류:', e.message); }
    return { pdf, pages, thumb };
  }

  // ── 아주 작은 multipart 읽개(파일 하나 + 글자칸들) ────────────
  //   수집 에이전트가 curl -F 로 보내는 standard multipart/form-data 를 읽는다(팩스는 작아 통째로 받는다).
  const MAX_BODY = (ctx.maxMB || 60) * 1024 * 1024;
  function readMultipart(req, cb) {
    const ct = req.headers['content-type'] || '';
    const mb = /boundary=(?:"([^"]+)"|([^;]+))/i.exec(ct);
    if (!mb) return cb(new Error('multipart 가 아닙니다'));
    const boundary = Buffer.from('--' + (mb[1] || mb[2]).trim());
    const chunks = []; let size = 0, over = false;
    req.on('data', (c) => { size += c.length; if (size > MAX_BODY) { over = true; req.destroy(); return; } chunks.push(c); });
    req.on('error', (e) => cb(e));
    req.on('end', () => {
      if (over) return cb(new Error('파일이 너무 큽니다'));
      try {
        const body = Buffer.concat(chunks);
        const fields = {}; let file = null;
        let i = body.indexOf(boundary);
        while (i >= 0) {
          let start = i + boundary.length;
          if (body[start] === 0x2d && body[start + 1] === 0x2d) break;       // 끝 경계 --boundary--
          if (body[start] === 0x0d) start += 2;                              // CRLF
          const next = body.indexOf(boundary, start);
          if (next < 0) break;
          let part = body.slice(start, next - 2);                            // 뒤 CRLF 제거
          const he = part.indexOf('\r\n\r\n');
          const head = part.slice(0, he).toString('utf8');
          const data = part.slice(he + 4);
          const nameM = /name="([^"]*)"/i.exec(head);
          const fileM = /filename="([^"]*)"/i.exec(head);
          const name = nameM ? nameM[1] : '';
          if (fileM) file = { field: name, filename: fileM[1], data };
          else fields[name] = data.toString('utf8');
          i = next;
        }
        cb(null, { fields, file });
      } catch (e) { cb(e); }
    });
  }

  const safeExt = (name, fallback) => { const e = (path.extname(name || '') || fallback).toLowerCase().replace(/[^.a-z0-9]/g, ''); return e || fallback; };
  const nowIso = () => new Date().toISOString();

  // ════════════════════════════════════════════════════════════
  //  ① POST /api/fax/inbound  — 수집 에이전트가 받은 팩스를 올린다
  // ════════════════════════════════════════════════════════════
  app.post('/api/fax/inbound', needAgent, (req, res) => {
    readMultipart(req, async (err, parsed) => {
      if (err) return res.status(400).json({ error: err.message });
      const f = parsed.file, F = parsed.fields || {};
      if (!f || !f.data || !f.data.length) return res.status(400).json({ error: 'file 이 없습니다.' });
      const sha = (F.sha256 || crypto.createHash('sha256').update(f.data).digest('hex')).toLowerCase();
      try {
        //  이미 있으면 409 (sha256 UNIQUE)
        const dup = await one('SELECT id, partner_id, pages FROM fax_inbox WHERE sha256 = ?', [sha]);
        if (dup) return res.status(409).json({ id: dup.id, partner_id: dup.partner_id, pages: dup.pages, duplicate: true });

        const received = F.received_at && !isNaN(Date.parse(F.received_at)) ? new Date(F.received_at) : new Date();
        const dir = path.join(STORE, ymd(received)); fs.mkdirSync(dir, { recursive: true });
        const ext = safeExt(f.filename, '.pdf');
        const base = path.join(dir, sha.slice(0, 16) + '_' + Date.now());
        const origPath = base + ext;
        fs.writeFileSync(origPath, f.data);
        const isTif = /\.tif{1,2}$/i.test(ext) || (f.data.length > 3 && (f.data[0] === 0x49 || f.data[0] === 0x4d) && !/%PDF/.test(f.data.slice(0, 5).toString('latin1')));
        const { pdf, pages, thumb } = makePdfAndThumb(origPath, isTif, base);

        const m = await matchPartner(F.sender);
        const assignee = (m.partner_id != null && typeof ctx.assigneeOf === 'function') ? await safe(() => ctx.assigneeOf(m.partner_id)) : null;
        const rel = (p) => (p ? path.relative(STORE, p) : null);

        await run(
          'INSERT INTO fax_inbox (received_at, sender_raw, sender_digits, mailbox, pages, file_pdf, file_orig, thumb, sha256, source, original_name, partner_id, match_type, assignee_id, status) ' +
          'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
          [received, (F.sender || '').slice(0, 64), m.digits || null, (F.mailbox || '').slice(0, 32) || null, pages,
           rel(pdf), isTif ? rel(origPath) : null, rel(thumb), sha, (F.source || 'cimfax-export').slice(0, 20),
           (F.original_name || f.filename || '').slice(0, 200), m.partner_id, m.match_type, assignee != null ? assignee : null, 'new']);
        const row = await one('SELECT id, partner_id, pages FROM fax_inbox WHERE sha256 = ?', [sha]);
        const id = row ? row.id : null;
        if (id != null) {
          await event(id, assignee != null ? assignee : null, 'ingest', (F.source || 'cimfax-export'));
          notify('new-fax', { id, partner_id: m.partner_id, sender: F.sender, pages, assignee_id: assignee });
          if (assignee != null) notify('assign', { id, assignee_id: assignee, partner_id: m.partner_id });
        }
        res.status(201).json({ id, partner_id: m.partner_id, pages });
      } catch (e) {
        console.error('[fax] inbound 오류:', e);
        res.status(500).json({ error: '서버 오류: ' + e.message });
      }
    });
  });

  // ════════════════════════════════════════════════════════════
  //  ② POST /api/fax/agent-report  — 5분마다 점검 보고(하트비트 + 누락)
  // ════════════════════════════════════════════════════════════
  app.post('/api/fax/agent-report', needAgent, express_json(), async (req, res) => {
    try {
      const b = req.body || {};
      const agent = (b.agent || 'default').toString().slice(0, 40);
      const missing = Array.isArray(b.missing) ? b.missing : [];
      await upsertAgent(agent, {
        last_report_at: new Date(),
        faxbox_running: b.faxbox_running ? 1 : 0,
        total_in_db: num(b.total_in_db), exported: num(b.exported),
        missing_count: missing.length, missing_json: JSON.stringify(missing).slice(0, 1000000),
      });
      //  누락이 1시간 넘게 남아 있으면(가장 오래된 누락 기준) 관리자 알림
      const oldest = missing.map((x) => Date.parse(x.received_at)).filter((n) => !isNaN(n)).sort()[0];
      if (missing.length && oldest && Date.now() - oldest > 60 * 60 * 1000) notify('missing', { agent, count: missing.length, oldest: new Date(oldest).toISOString() });
      res.json({ ok: true, missing: missing.length });
    } catch (e) { console.error('[fax] agent-report 오류:', e); res.status(500).json({ error: e.message }); }
  });

  // ════════════════════════════════════════════════════════════
  //  ③ 팩스함 — 목록·검색
  // ════════════════════════════════════════════════════════════
  app.get('/api/fax', needLogin, async (req, res) => {
    try {
      const u = userOf(req);
      const w = [], p = [];
      const Q = req.query;
      if (Q.from && !isNaN(Date.parse(Q.from))) { w.push('received_at >= ?'); p.push(new Date(Q.from)); }
      if (Q.to && !isNaN(Date.parse(Q.to))) { w.push('received_at <= ?'); p.push(new Date(Q.to)); }
      if (Q.status) { w.push('status = ?'); p.push(String(Q.status).slice(0, 12)); }
      if (Q.partner_id) { w.push('partner_id = ?'); p.push(+Q.partner_id); }
      if (Q.assignee) { w.push('assignee_id = ?'); p.push(+Q.assignee); }
      if (Q.unmatched === '1' || Q.unmatched === 'true') w.push('partner_id IS NULL');
      if (Q.sender) { w.push('sender_digits LIKE ?'); p.push('%' + digitsOnly(Q.sender) + '%'); }
      if (Q.q) { w.push('(memo LIKE ? OR ocr_text LIKE ? OR original_name LIKE ?)'); const s = '%' + String(Q.q).slice(0, 60) + '%'; p.push(s, s, s); }
      //  권한: 전체 / 내 담당만
      if (ctx.readScope === 'assigned' && !isAdmin(u)) { w.push('assignee_id = ?'); p.push(u.id); }
      const where = w.length ? ' WHERE ' + w.join(' AND ') : '';
      const page = Math.max(1, +Q.page || 1), size = Math.min(100, +Q.size || 30);
      const rows = await all(
        'SELECT id, received_at, sender_raw, sender_digits, mailbox, pages, status, partner_id, match_type, category, assignee_id, thumb, original_name ' +
        'FROM fax_inbox' + where + ' ORDER BY received_at DESC' + pageClause(size, (page - 1) * size), p);
      const cnt = await one('SELECT COUNT(*) AS n FROM fax_inbox' + where, p);
      res.json({ items: rows.map(pub), total: cnt ? cnt.n : rows.length, page, size, warn: await warnBlock() });
    } catch (e) { console.error('[fax] 목록 오류:', e); res.status(500).json({ error: e.message }); }
  });

  //  상세  (:id 가 숫자가 아니면 stats·agent-status 같은 뒤 길로 넘긴다 — Express 4·5 모두 안전)
  app.get('/api/fax/:id', needLogin, async (req, res, next) => {
    if (!/^\d+$/.test(req.params.id)) return next();
    try {
      const row = await one('SELECT * FROM fax_inbox WHERE id = ?', [+req.params.id]);
      if (!row) return res.status(404).json({ error: '없는 팩스입니다.' });
      const links = await all('SELECT voucher_id FROM fax_link WHERE fax_id = ?', [row.id]);
      res.json({ item: pub(row, true), links: links.map((x) => x.voucher_id) });
    } catch (e) { res.status(500).json({ error: e.message }); }
  });

  //  PDF — 로그인 사용자만, 링크 공유 금지(열람은 기록)
  app.get('/api/fax/:id/file', needLogin, async (req, res) => {
    try {
      const u = userOf(req);
      const row = await one('SELECT id, file_pdf, original_name FROM fax_inbox WHERE id = ?', [+req.params.id]);
      if (!row || !row.file_pdf) return res.status(404).send('없는 팩스입니다.');
      const fp = path.join(STORE, row.file_pdf);
      if (!fp.startsWith(STORE) || !fs.existsSync(fp)) return res.status(404).send('파일이 없습니다.');
      await event(row.id, u.id, 'view', null);
      res.setHeader('Content-Type', 'application/pdf');
      res.setHeader('Cache-Control', 'private, no-store');
      res.setHeader('Content-Disposition', 'inline; filename="fax-' + row.id + '.pdf"');
      fs.createReadStream(fp).pipe(res);
    } catch (e) { res.status(500).send(e.message); }
  });

  //  썸네일(작은 그림)
  app.get('/api/fax/:id/thumb', needLogin, async (req, res) => {
    try {
      const row = await one('SELECT thumb FROM fax_inbox WHERE id = ?', [+req.params.id]);
      if (!row || !row.thumb) return res.status(404).end();
      const fp = path.join(STORE, row.thumb);
      if (!fp.startsWith(STORE) || !fs.existsSync(fp)) return res.status(404).end();
      res.setHeader('Content-Type', 'image/png');
      res.setHeader('Cache-Control', 'private, max-age=86400');
      fs.createReadStream(fp).pipe(res);
    } catch (e) { res.status(500).end(); }
  });

  //  변경 — 거래처·분류·담당자·상태·메모 (거래처 바꾸면 학습표 갱신)
  app.patch('/api/fax/:id', needLogin, express_json(), async (req, res) => {
    try {
      const u = userOf(req);
      const row = await one('SELECT * FROM fax_inbox WHERE id = ?', [+req.params.id]);
      if (!row) return res.status(404).json({ error: '없는 팩스입니다.' });
      const b = req.body || {};
      const set = [], p = [];
      if ('partner_id' in b) { set.push('partner_id = ?', 'match_type = ?'); p.push(b.partner_id == null ? null : +b.partner_id, b.partner_id == null ? null : 'manual'); }
      if ('category' in b) { set.push('category = ?'); p.push(b.category ? String(b.category).slice(0, 20) : null); }
      if ('assignee_id' in b) { set.push('assignee_id = ?'); p.push(b.assignee_id == null ? null : +b.assignee_id); }
      if ('status' in b) { set.push('status = ?'); p.push(String(b.status).slice(0, 12)); }
      if ('memo' in b) { set.push('memo = ?'); p.push(b.memo == null ? null : String(b.memo).slice(0, 1000)); }
      if (!set.length) return res.json({ ok: true });
      set.push('updated_at = ' + nowFn());
      await run('UPDATE fax_inbox SET ' + set.join(', ') + ' WHERE id = ?', [...p, row.id]);
      //  거래처를 손으로 바꾸면 '번호→거래처' 학습표에 저장(다음부터 자동)
      if ('partner_id' in b && b.partner_id != null && row.sender_digits && !meaningless(row.sender_digits)) {
        await upsertSenderMap(row.sender_digits, +b.partner_id, u.id);
      }
      if ('assignee_id' in b && b.assignee_id != null) notify('assign', { id: row.id, assignee_id: +b.assignee_id });
      await event(row.id, u.id, 'edit', Object.keys(b).join(','));
      res.json({ ok: true });
    } catch (e) { console.error('[fax] patch 오류:', e); res.status(500).json({ error: e.message }); }
  });

  //  전표 연결(수주·매입)
  app.post('/api/fax/:id/links', needLogin, express_json(), async (req, res) => {
    try {
      const u = userOf(req);
      const id = +req.params.id;
      const vid = req.body && req.body.voucher_id;
      if (vid == null) return res.status(400).json({ error: 'voucher_id 가 필요합니다.' });
      await run('INSERT INTO fax_link (fax_id, voucher_id) VALUES (?, ?)', [id, +vid]).catch(() => {});
      await event(id, u.id, 'link', String(vid));
      res.json({ ok: true });
    } catch (e) { res.status(500).json({ error: e.message }); }
  });

  //  통계
  app.get('/api/fax/stats', needLogin, async (req, res) => {
    try {
      const byStatus = await all('SELECT status, COUNT(*) AS n FROM fax_inbox GROUP BY status', []);
      const unmatched = await one('SELECT COUNT(*) AS n FROM fax_inbox WHERE partner_id IS NULL', []);
      res.json({ byStatus, unmatched: unmatched ? unmatched.n : 0, warn: await warnBlock() });
    } catch (e) { res.status(500).json({ error: e.message }); }
  });

  //  에이전트 상태(관리자)
  app.get('/api/fax/agent-status', needLogin, needAdmin, async (req, res) => {
    try { res.json({ agents: await all('SELECT * FROM fax_agent_status ORDER BY agent', []), warn: await warnBlock() }); }
    catch (e) { res.status(500).json({ error: e.message }); }
  });

  //  팩스함 화면
  const PAGE = ctx.page || path.join(__dirname, 'fax-page.html');
  app.get('/fax', needLogin, (req, res) => { if (fs.existsSync(PAGE)) res.sendFile(PAGE); else res.status(404).send('팩스함 화면(fax-page.html)이 없습니다.'); });

  // ── 공통 도우미 ───────────────────────────────────────────────
  function pub(row, full) {
    const o = {
      id: row.id, received_at: row.received_at, sender_raw: row.sender_raw, sender_digits: row.sender_digits,
      mailbox: row.mailbox, pages: row.pages, status: row.status, partner_id: row.partner_id,
      match_type: row.match_type, category: row.category, assignee_id: row.assignee_id,
      original_name: row.original_name, has_thumb: !!row.thumb,
    };
    if (full) { o.memo = row.memo; o.source = row.source; o.created_at = row.created_at; o.updated_at = row.updated_at; o.file = true; }
    return o;
  }
  async function event(fax_id, user_id, action, detail) {
    try { await run('INSERT INTO fax_event (fax_id, user_id, action, detail) VALUES (?,?,?,?)', [fax_id, user_id != null ? user_id : null, action, detail ? String(detail).slice(0, 400) : null]); }
    catch (e) {}
  }
  async function upsertSenderMap(digits, partner_id, by) {
    const ex = await one('SELECT sender_digits FROM fax_sender_map WHERE sender_digits = ?', [digits]);
    if (ex) await run('UPDATE fax_sender_map SET partner_id = ?, updated_by = ?, updated_at = ' + nowFn() + ' WHERE sender_digits = ?', [partner_id, by != null ? by : null, digits]);
    else await run('INSERT INTO fax_sender_map (sender_digits, partner_id, updated_by) VALUES (?,?,?)', [digits, partner_id, by != null ? by : null]);
  }
  async function upsertAgent(agent, v) {
    const ex = await one('SELECT agent FROM fax_agent_status WHERE agent = ?', [agent]);
    const cols = ['last_report_at', 'faxbox_running', 'total_in_db', 'exported', 'missing_count', 'missing_json'];
    if (ex) await run('UPDATE fax_agent_status SET ' + cols.map((c) => c + ' = ?').join(', ') + ', updated_at = ' + nowFn() + ' WHERE agent = ?', [...cols.map((c) => v[c]), agent]);
    else await run('INSERT INTO fax_agent_status (agent, ' + cols.join(', ') + ') VALUES (?,' + cols.map(() => '?').join(',') + ')', [agent, ...cols.map((c) => v[c])]);
  }
  //  팩스함 상단 '미저장 N건' 경고 + 에이전트 끊김(15분) 경고
  async function warnBlock() {
    try {
      const ags = await all('SELECT * FROM fax_agent_status', []);
      let missing = [], down = [];
      const now = Date.now();
      for (const a of ags) {
        const last = a.last_report_at ? Date.parse(a.last_report_at) : 0;
        if (!last || now - last > 15 * 60 * 1000) down.push({ agent: a.agent, last_report_at: a.last_report_at });
        if (a.missing_json) { try { missing = missing.concat(JSON.parse(a.missing_json)); } catch (e) {} }
      }
      return { missing, missing_count: missing.length, agents_down: down };
    } catch (e) { return { missing: [], missing_count: 0, agents_down: [] }; }
  }
  function notify(kind, info) { if (typeof ctx.notify === 'function') { try { ctx.notify(kind, info); } catch (e) {} } }
  function nowFn() { return DIALECT === 'mysql' ? 'CURRENT_TIMESTAMP' : 'SYSDATETIME()'; }
  function num(v) { const n = +v; return isNaN(n) ? null : n; }
  async function safe(fn) { try { return await fn(); } catch (e) { return null; } }
  //  express.json() 이 이미 전역에 걸려 있으면 그걸, 아니면 우리 것(이 라우트에서만)
  function express_json() {
    return (req, res, next) => {
      if (req.body && typeof req.body === 'object') return next();
      let s = ''; let over = false;
      req.on('data', (c) => { s += c; if (s.length > MAX_BODY) { over = true; req.destroy(); } });
      req.on('end', () => { if (over) return res.status(413).json({ error: '너무 큽니다' }); try { req.body = s ? JSON.parse(s) : {}; } catch (e) { req.body = {}; } next(); });
      req.on('error', () => next());
    };
  }

  console.log('[fax] 📠 수신팩스 라우트 올림 · 저장소=' + STORE + ' · 도구(변환/썸네일)=' + JSON.stringify(HAS) + (TOKEN ? '' : ' · ⚠ 에이전트 토큰 없음'));
};
