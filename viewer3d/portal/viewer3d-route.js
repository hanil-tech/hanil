//  🧊 도면 보기(3D STEP·IGES · 2D DWG·DXF) 길 — 포털에 넣는 조각
//   넣는 법: 이 파일을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./viewer3d-route')(app);
//     (로그인 안 했으면 로그인 화면으로 갔다가 돌아온다 — 도면 파일도 로그인해야 받으므로)
//   그리고 hanil-viewer3d-portal.zip 을 public/ 에 풀어 public/viewer3d/ 가 생기게 한다.
//   ⭐ v1.3.0: 큰 도면 변환기 — viewer3d-convert.js 를 이 파일 옆에 함께 둔다.
//      빠르게 하려면(권장, 우분투) sudo apt install -y occt-draw libocct-draw-dev  (없어도 돈다 — 느릴 뿐)
//   여는 법:  /viewer3d/view?src=<파일 주소>&name=<파일 이름>      (그냥 /viewer3d 는 파일 고르기 화면)
//       예) 메신저 첨부   /viewer3d/view?src=%2Fapi%2Fchat%2Ffile%2F123&name=bracket.stp
//           결재 첨부     /viewer3d/view?src=%2Fapi%2Fappr%2Ffile%2Fabc.dwg&name=도면.dwg
//   ⚠ 이 포털은 express.static 이 없다 — 그래서 이 길이 파일을 하나하나 내준다(정해 둔 이름만 — 다른 파일은 안 내준다).
//   ⚠ sendFile 로 내준다 — HTML 에 끼우는 포털 조각(쪽지함·단추 등)이 뷰어 화면 위에 올라오지 않게.
//   ⚠ 엔진(wasm)은 크니(3D 7MB · 2D 9MB) 브라우저가 한동안 받아 두게 한다. 판이 바뀌면 index.html 이 ?v= 로 새로 받는다.
'use strict';
const path = require('path');
const fs = require('fs');
const http = require('http');
const https = require('https');
const crypto = require('crypto');
const { fork } = require('child_process');

module.exports = function mountViewer3d(app, ctx) {
  const auth = (ctx && ctx.auth) || ((q, r, n) => ((q.session && q.session.user) ? n()
    : r.redirect('/?next=' + encodeURIComponent(q.originalUrl || '/viewer3d/'))));
  const DIR = path.join(__dirname, 'public', 'viewer3d');
  const FILES = {
    'index.html': 'text/html; charset=utf-8',
    'viewer.js': 'text/javascript; charset=utf-8',
    'dwg.js': 'text/javascript; charset=utf-8',
    'occt-import-js.js': 'text/javascript; charset=utf-8',
    'occt-import-js.wasm': 'application/wasm',
    'libredwg-web.wasm': 'application/wasm',
    'license.occt.txt': 'text/plain; charset=utf-8',
    'license.occt-import-js.txt': 'text/plain; charset=utf-8',
    'license.libredwg.txt': 'text/plain; charset=utf-8',
    'occt-worker.js': 'text/javascript; charset=utf-8',
  };
  mountConvert(app, auth, DIR, ctx || {});
  //  ⭐ 화면 주소는 /viewer3d/view — 포털은 주소가 /view 로 끝나는 화면(미리보기)에는 공통 조각(쪽지함·단추·화면 줄이기 등)을
  //     끼우지 않는다. 다른 주소로 내주면 그 조각들이 도면 위에 올라와 돌리기·재기를 가린다(시험에서 확인).
  //  ⚠ express 는 /viewer3d 와 /viewer3d/ 를 같은 길로 본다 — 둘 다 /viewer3d/view 로 보낸다(주소 꼬리 ?src= 는 그대로)
  app.get('/viewer3d', auth, (req, res) => {
    const u = req.originalUrl || '';
    res.redirect('/viewer3d/view' + (u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : ''));
  });
  app.get('/viewer3d/:f', auth, (req, res) => {
    if (req.params.f === 'index.html') return res.redirect('/viewer3d/view');   //  공통 조각이 안 끼는 주소로만
    const f = req.params.f === 'view' ? 'index.html' : req.params.f;
    if (!FILES[f]) return res.status(404).send('없는 파일입니다.');
    const fp = path.join(DIR, f);
    if (!fs.existsSync(fp)) return res.status(404).send('도면 보기가 아직 설치되지 않았습니다(public/viewer3d).');
    res.setHeader('Content-Type', FILES[f]);
    //  화면(index.html)은 늘 새로, 엔진·코드는 7일 받아 둔다(index.html 이 ?v=판 으로 부른다)
    res.setHeader('Cache-Control', f === 'index.html' ? 'no-cache' : 'private, max-age=604800');
    res.sendFile(fp);
  });
};

// ── 🏭 포털 변환기 — 큰 도면을 서버에서 한 번만 가볍게 바꿔 둔다 ─────────────
//   GET /viewer3d/api/ping                     → { ok, convert:true } (뷰어가 변환기가 있는지 본다)
//   GET /viewer3d/api/prep?src=&name=&small=   → 바로 받아 열지(raw) / 변환해 둔 것(done) / 변환 중(work) / 실패(fail)
//   GET /viewer3d/api/job/<열쇠>               → 변환 중이면 몇 초째인지, 끝났으면 done
//   GET /viewer3d/api/out/<열쇠>               → 변환 결과(.hm3 묶음 또는 CATIA 미리보기 그림)
//   ⭐ 첨부 파일은 **그 사람의 로그인(쿠키)을 그대로 붙여** 포털 자신에게 받아 온다 → 권한 없는 파일은 변환도 안 된다.
//      어떤 첨부 길(메신저·결재·게시판…)이든 따로 손댈 것이 없다.
//   ⭐ 결과는 viewer3d-cache/ 에 둔다(파일 내용이 같으면 다시 안 바꾼다). 오래된 것부터 지워 5GB·60일을 넘지 않게.
//   ⚠ 한 번에 하나만 바꾼다(엔진이 CPU 하나·메모리 수 GB 를 쓴다). 나머지는 줄을 선다.
function mountConvert(app, auth, DIR, ctx) {
  const CACHE = ctx.cacheDir || process.env.VIEWER3D_CACHE || path.join(__dirname, 'viewer3d-cache');
  //  서버 OpenCASCADE(occt-draw)가 있으면 서버가 훨씬 빠르다 → 2MB 넘는 3D 는 서버가. 없으면 15MB(폰 4MB)부터.
  //  ⚠ 깔렸는지 보는 데 1초쯤 걸린다 — 포털이 뜬 뒤 한 번만(뜨는 것을 늦추지 않게)
  let native = false;
  setTimeout(() => { try { native = !!require('./viewer3d-convert').drawBin(); } catch (e) { native = false; } }, 3000);
  const rawMax = (small) => (native ? (small ? 1 : 2) : (small ? (ctx.rawMaxSmallMB || 4) : (ctx.rawMaxMB || 15))) * 1048576;
  const SRC_MAX = (ctx.srcMaxMB || 600) * 1048576;
  const TIME_MAX = (ctx.timeMaxMin || 30) * 60000;
  const CACHE_MAX = (ctx.cacheMaxGB || 5) * 1073741824;
  fs.mkdirSync(CACHE, { recursive: true });
  const saltF = path.join(CACHE, '.salt');
  if (!fs.existsSync(saltF)) fs.writeFileSync(saltF, crypto.randomBytes(24).toString('hex'));
  const SALT = fs.readFileSync(saltF, 'utf8');
  const jobs = new Map();          //  열쇠 → { state, t0, phase, msg, name, file, kind }
  const queue = [];
  let running = null;
  const KEY = /^[0-9a-f]{40}$/;
  const kindOf = (name) => {
    const e = String(name || '').split('?')[0].split('.').pop().toLowerCase();
    if (e === 'stp' || e === 'step') return 'step';
    if (e === 'igs' || e === 'iges') return 'iges';
    if (e === 'brep' || e === 'brp') return 'brep';
    if (/^(catpart|catproduct|catdrawing|catshape|catsystem|cgr)$/.test(e)) return 'catia';
    return '';
  };
  const metaOf = (k) => { try { return JSON.parse(fs.readFileSync(path.join(CACHE, k + '.json'), 'utf8')); } catch (e) { return null; } };
  const status = (k) => {
    const m = metaOf(k);
    if (m && fs.existsSync(path.join(CACHE, k + '.out'))) return Object.assign({ state: 'done', key: k, out: '/viewer3d/api/out/' + k }, m);
    const j = jobs.get(k);
    if (!j) return { state: 'gone', key: k };
    if (j.state === 'fail') return { state: 'fail', key: k, msg: j.msg };
    return { state: 'work', key: k, phase: j.phase || 'wait', sec: Math.round((Date.now() - j.t0) / 1000),
      wait: j.phase ? 0 : queue.indexOf(k) + 1, mb: Math.round(j.bytes / 1048576), est: estimate(j) };
  };
  //  어림 시간(초) — 이 서버에서 지난번에 걸린 속도(MB 당 초)로
  let secPerMB = 0;
  function estimate(j) { return j.kind === 'catia' ? 2 : Math.round(5 + (secPerMB || (native ? 0.8 : 2.5)) * j.bytes / 1048576); }

  function next() {
    if (running || !queue.length) return;
    const k = queue.shift();
    const j = jobs.get(k);
    if (!j) return next();
    running = k;
    j.phase = 'start';
    j.t1 = Date.now();
    const outBase = path.join(CACHE, k);
    const child = fork(path.join(__dirname, 'viewer3d-convert.js'), [j.file, j.kind, outBase, DIR],
      { execArgv: ['--max-old-space-size=6144'], stdio: ['ignore', 'ignore', 'pipe', 'ipc'] });
    let err = '';
    child.stderr.on('data', (d) => { err = (err + d).slice(-2000); });
    const timer = setTimeout(() => { j.msg = '변환이 ' + Math.round(TIME_MAX / 60000) + '분을 넘어 멈췄습니다 — 파일이 너무 큽니다'; child.kill('SIGKILL'); }, TIME_MAX);
    child.on('message', (m) => {
      if (m.phase) j.phase = m.phase;
      if (m.error) j.msg = m.error;
    });
    child.on('exit', (code, sig) => {
      clearTimeout(timer);
      fs.unlink(j.file, () => {});
      if (code === 0 && metaOf(k)) {
        if (j.kind !== 'catia' && j.bytes > 5 * 1048576) secPerMB = Math.max(0.3, (Date.now() - j.t1) / 1000 / (j.bytes / 1048576));
        jobs.delete(k);
        trim();
      } else {
        j.state = 'fail';
        j.msg = j.msg || (/memory|Aborted|OOM|Cannot enlarge/i.test(err) || sig ? '서버 메모리가 모자라 변환하지 못했습니다(파일이 너무 큼)' : '변환하지 못했습니다') + (err ? ' — ' + err.split('\n').filter(Boolean).pop().slice(0, 200) : '');
        setTimeout(() => { if (jobs.get(k) === j) jobs.delete(k); }, 10 * 60000);    //  실패는 10분 기억(같은 것을 또 돌리지 않게)
      }
      running = null;
      next();
    });
  }
  function trim() {
    try {
      const fl = fs.readdirSync(CACHE).filter((f) => /\.out$/.test(f)).map((f) => { const st = fs.statSync(path.join(CACHE, f)); return { f, t: st.atimeMs > st.mtimeMs ? st.atimeMs : st.mtimeMs, s: st.size }; })
        .sort((a, b) => b.t - a.t);
      let tot = 0;
      fl.forEach((x) => {
        tot += x.s;
        if (tot > CACHE_MAX || Date.now() - x.t > 60 * 86400000) {
          const k = x.f.slice(0, -4);
          ['.out', '.json'].forEach((e) => fs.unlink(path.join(CACHE, k + e), () => {}));
        }
      });
    } catch (e) { /* 지우기는 다음에 */ }
  }

  //  포털 자신에게서 첨부를 받는다(그 사람 쿠키를 붙여)
  function pull(req, src) {
    return new Promise((ok, no) => {
      const tls = !!(req.socket && req.socket.encrypted);
      const lib = tls ? https : http;
      const port = (req.socket && req.socket.localPort) || (ctx.port || 80);
      const r = lib.request({ host: '127.0.0.1', port, path: src, method: 'GET', rejectUnauthorized: false,
        headers: { cookie: req.headers.cookie || '', 'user-agent': 'hanil-viewer3d-convert', host: req.headers.host || ('127.0.0.1:' + port),
          'x-forwarded-for': req.ip || '', 'x-forwarded-proto': req.protocol || 'http' } }, (rs) => ok(rs));
      r.on('error', no);
      r.setTimeout(120000, () => r.destroy(new Error('첨부를 받는 데 너무 오래 걸립니다')));
      r.end();
    });
  }

  app.get('/viewer3d/api/ping', auth, (req, res) => res.json({ ok: true, convert: true, native }));

  app.get('/viewer3d/api/prep', auth, async (req, res) => {
    const src = String(req.query.src || '');
    const name = String(req.query.name || src.split('?')[0].split('/').pop() || '');
    //  ⚠ 포털 안의 주소만(다른 서버로 심부름 보내기 막기)
    if (!/^\/(?!\/)/.test(src) || /^\/viewer3d/i.test(src) || /[\r\n]/.test(src)) return res.status(400).json({ state: 'fail', msg: '포털 안의 첨부 주소(/로 시작)만 됩니다' });
    let kind = kindOf(name) || kindOf(src);
    if (!kind) return res.json({ state: 'raw' });            //  DWG·DXF 등은 브라우저가 직접
    let rs;
    try { rs = await pull(req, src); } catch (e) { return res.json({ state: 'fail', msg: '첨부를 받지 못했습니다: ' + e.message }); }
    if (rs.statusCode !== 200) { rs.resume(); return res.json({ state: 'fail', msg: '서버가 ' + rs.statusCode + ' 로 답했습니다' + (rs.statusCode === 401 || rs.statusCode === 403 ? ' — 로그인·권한을 확인하세요' : rs.statusCode === 404 ? ' — 파일 주소가 틀렸거나 지워진 파일' : '') }); }
    if (/text\/html/i.test(rs.headers['content-type'] || '')) { rs.resume(); return res.json({ state: 'fail', msg: '파일 대신 화면(HTML)이 왔습니다 — 로그인 화면이거나 내려받기 주소가 아닙니다' }); }
    const len = +rs.headers['content-length'] || 0;
    if (len > SRC_MAX) { rs.destroy(); return res.json({ state: 'fail', msg: '파일이 너무 큽니다(' + Math.round(len / 1048576) + 'MB)' }); }
    //  작은 3D 는 브라우저가 직접(서버 일 줄이기). CATIA 는 늘 서버(그림만 보내면 되니).
    if (kind !== 'catia' && len && len < rawMax(req.query.small)) { rs.destroy(); return res.json({ state: 'raw' }); }
    //  열쇠 — 주소+크기+바뀐 때(ETag·Last-Modified)를 알면 받기 전에 정한다(이미 바꿔 둔 것이면 바로 끝)
    const tag = rs.headers.etag || rs.headers['last-modified'] || '';
    let key = (len && tag) ? crypto.createHash('sha1').update(SALT + '|' + kind + '|' + src + '|' + len + '|' + tag).digest('hex') : '';
    if (key && (status(key).state === 'done' || jobs.has(key))) { rs.destroy(); return res.json(status(key)); }
    //  받아 둔다(내용 지문도 함께 — 열쇠를 미리 못 정했으면 이것으로)
    const tmp = path.join(CACHE, 'in-' + crypto.randomBytes(8).toString('hex') + '.' + kind);
    const h = crypto.createHash('sha1');
    let got = 0;
    try {
      await new Promise((ok, no) => {
        const w = fs.createWriteStream(tmp);
        rs.on('data', (d) => { got += d.length; h.update(d); if (got > SRC_MAX) rs.destroy(new Error('파일이 너무 큽니다')); });
        rs.on('error', no); w.on('error', no); w.on('finish', ok);
        rs.pipe(w);
      });
    } catch (e) { fs.unlink(tmp, () => {}); return res.json({ state: 'fail', msg: '첨부를 받지 못했습니다: ' + e.message }); }
    if (!got) { fs.unlink(tmp, () => {}); return res.json({ state: 'fail', msg: '빈 파일이 왔습니다' }); }
    if (!len && kind !== 'catia' && got < rawMax(req.query.small)) { fs.unlink(tmp, () => {}); return res.json({ state: 'raw' }); }
    if (!key) key = crypto.createHash('sha1').update(SALT + '|' + kind + '|' + h.digest('hex')).digest('hex');
    const st = status(key);
    if (st.state === 'done' || jobs.has(key)) { fs.unlink(tmp, () => {}); return res.json(st); }
    jobs.set(key, { state: 'work', t0: Date.now(), phase: '', name, file: tmp, kind, bytes: got });
    queue.push(key);
    next();
    res.json(status(key));
  });

  app.get('/viewer3d/api/job/:k', auth, (req, res) => {
    if (!KEY.test(req.params.k)) return res.status(400).json({ state: 'fail' });
    res.setHeader('Cache-Control', 'no-store');
    res.json(status(req.params.k));
  });

  app.get('/viewer3d/api/out/:k', auth, (req, res) => {
    const k = req.params.k;
    const m = KEY.test(k) && metaOf(k);
    const fp = path.join(CACHE, k + '.out');
    if (!m || !fs.existsSync(fp)) return res.status(404).send('없습니다');
    res.setHeader('Cache-Control', 'private, max-age=604800');
    fs.utimes(fp, new Date(), fs.statSync(fp).mtime, () => {});      //  쓴 때 — 오래 안 쓴 것부터 지운다
    if (m.type === 'mesh') {
      //  .hm3 는 gzip 으로 담아 두었다 — 브라우저가 알아서 푼다
      res.setHeader('Content-Type', 'application/octet-stream');
      res.setHeader('Content-Encoding', 'gzip');
      res.setHeader('Content-Length', fs.statSync(fp).size);
      fs.createReadStream(fp).pipe(res);
    } else {
      res.setHeader('Content-Type', m.mime || 'image/jpeg');
      fs.createReadStream(fp).pipe(res);
    }
  });
}
