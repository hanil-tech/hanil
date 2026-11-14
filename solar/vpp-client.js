//  ☀️ 에너지어스 VPP(www.energyus-vppc.com) 태양광 발전량 — 로그인해서 데이터 가져오기
//
//   근거: 사이트 화면 코드(/js/main.*.js)를 분석 (2026-11-14). 화면이 쓰는 것과 같은 주소를 같은 방식으로 부른다.
//     baseURL /tws · 세션 쿠키(withCredentials) · GET 에는 ?_=난수
//     POST /any/login {identity: 이메일, password}  → { ok: true, … }   (ok:false 면 result 에 이유)
//     GET  /any/session/alive · POST /ctx/session/renew · POST /ctx/logout
//     GET  /master/currentUser · /stats/overview · /stats/power/plants?status= · /master/me/plants?ps=&pp=
//     GET  /master/plants/{id}/things
//     POST /stats/plant/power/download · /stats/inverter/{hour,day,month}/download · /stats/plant/string/download (엑셀)
'use strict';

const BASE = 'https://www.energyus-vppc.com/tws';

class Vpp {
  constructor(opt) {
    this.base = (opt && opt.base) || BASE;
    this.cookies = new Map();
    this.timeoutMs = (opt && opt.timeoutMs) || 30000;
  }
  _cookieHeader() { return [...this.cookies].map(([k, v]) => k + '=' + v).join('; '); }
  _keep(res) {
    const list = typeof res.headers.getSetCookie === 'function' ? res.headers.getSetCookie() : [res.headers.get('set-cookie')].filter(Boolean);
    for (const c of list) {
      const [kv] = c.split(';');
      const i = kv.indexOf('=');
      if (i > 0) this.cookies.set(kv.slice(0, i).trim(), kv.slice(i + 1).trim());
    }
  }
  async _req(method, path, { params, body, raw } = {}) {
    const u = new URL(this.base + path);
    if (params) Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null) u.searchParams.set(k, typeof v === 'object' ? JSON.stringify(v) : String(v)); });
    if (method === 'GET') u.searchParams.set('_', String(Math.random()));
    const res = await fetch(u, {
      method,
      headers: Object.assign({ 'Accept': 'application/json, text/plain, */*', 'User-Agent': 'hanil-portal-solar/1.0' },
        body !== undefined ? { 'Content-Type': 'application/json' } : {},
        this.cookies.size ? { Cookie: this._cookieHeader() } : {}),
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    this._keep(res);
    if (raw) {
      if (!res.ok) throw new Error(path + ' → HTTP ' + res.status);
      return { buf: Buffer.from(await res.arrayBuffer()), type: res.headers.get('content-type'), name: res.headers.get('content-disposition') };
    }
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (e) { data = text; }
    if (res.status === 401) throw Object.assign(new Error('로그인이 필요합니다 (401)'), { status: 401 });
    if (!res.ok) throw Object.assign(new Error(path + ' → HTTP ' + res.status + ' ' + String(text).slice(0, 120)), { status: res.status });
    //  화면 코드와 같은 판단: ok 가 false 면 실패, result 에 이유(코드 또는 JSON)
    if (data && typeof data === 'object' && data.ok === false) throw Object.assign(new Error('사이트가 거절: ' + (data.result || data.code || JSON.stringify(data).slice(0, 120))), { status: 200, data });
    return data;
  }
  get(path, params) { return this._req('GET', path, { params }); }
  post(path, body) { return this._req('POST', path, { body: body === undefined ? {} : body }); }

  async login(identity, password) {
    const r = await this._req('POST', '/any/login', { body: { identity, password } });
    if (!r || r.ok === false) throw new Error('로그인 실패');
    return r;
  }
  alive() { return this.get('/any/session/alive'); }
  renew() { return this._req('POST', '/ctx/session/renew', {}); }
  logout() { return this.post('/ctx/logout').catch(() => null); }
  currentUser() { return this.get('/master/currentUser'); }
  overview() { return this.get('/stats/overview'); }
  plantsPower(status) { return this.get('/stats/power/plants', status ? { status } : undefined); }
  myPlants(page, size) { return this.get('/master/me/plants', { ps: size || 100, pp: page || 0 }); }
  plantThings(id) { return this.get('/master/plants/' + encodeURIComponent(id) + '/things'); }
  download(kind, body) {
    const p = { plant: '/stats/plant/power/download', string: '/stats/plant/string/download', hour: '/stats/inverter/hour/download', day: '/stats/inverter/day/download', month: '/stats/inverter/month/download' }[kind];
    if (!p) throw new Error('모르는 종류: ' + kind);
    return this._req('POST', p, { body: body || {}, raw: true });
  }
}

//  아이디·비밀번호 파일: 첫 줄 아이디(이메일), 둘째 줄 비밀번호 — chmod 600
function readPassFile(file) {
  const fs = require('fs');
  const [id, pw] = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  if (!id || !pw) throw new Error('비밀번호 파일 형식: 첫 줄 아이디, 둘째 줄 비밀번호 (' + file + ')');
  return { id: id.trim(), pw };
}

module.exports = { Vpp, readPassFile, BASE };
