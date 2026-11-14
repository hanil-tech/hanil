//  ☀️ 태양광 발전 — 포털에 넣는 조각 (에너지어스 VPP → 포털 /solar)
//
//   하는 일
//     · 포털이 켜져 있는 동안 N분마다(기본 10분) VPP 사이트에 로그인해 발전량을 가져와 저장한다 (cron 따로 필요 없음 — 포털이 재부팅 후 다시 켜지면 같이 켜짐)
//     · /solar 화면: 지금 발전(kW) · 오늘/어제/이번 달/누적 발전량(kWh) · 발전시간 · 오늘 시간대별 그래프 · 최근 30일 막대
//     · 발전소 상태가 정상에서 벗어나면(고장·통신 끊김·정지) notify 로 알림 — 되돌아오면 「정상 복귀」 도 알림
//
//   넣는 법 (server.js, 세션이 붙은 뒤 — faxbox 줄 옆):
//       require('./solar-route')(app, { passFile: '/home/gaos/.vpp-pass', notify: (msg, url) => nopsPush('관리자아이디', msg) });
//
//   설정 (모두 생략 가능)
//     passFile  아이디(첫 줄)·비밀번호(둘째 줄) 파일 (기본 ~/.vpp-pass, chmod 600)
//     dir       저장 폴더 (기본 ~/solar/data)
//     everyMin  가져오는 간격 분 (기본 10, 최소 5)
//     view      누가 보나: 'all'(로그인한 직원 모두, 기본) | 'admin' | (user) => true/false
//     notify    async (메시지, url) => { … } — 이상·복귀·로그인 실패 알림
//     base      시험용: 사이트 주소 바꾸기 (기본 https://www.energyus-vppc.com/tws)
//
//   API (로그인 필요)
//     GET /solar                        화면
//     GET /api/solar/latest             마지막으로 가져온 값 { at, overview, plants[], alerts[], error? }
//     GET /api/solar/today?date=YYYY-MM-DD   그날 10분 간격 기록 [{t, kw, kwh}]
//     GET /api/solar/daily?days=30      날짜별 발전량 [{date, kwh, peakKw, hours}]
//     POST /api/solar/refresh           지금 바로 가져오기 (관리자만)
'use strict';
const fs = require('fs'), path = require('path'), os = require('os');
const { Vpp, readPassFile } = require('./vpp-client');

const STS = { normal: '정상', fault: '고장', check: '점검', offline: '통신 끊김', stop: '정지', on: '연결', off: '끊김' };
const ymd = (d) => { const x = new Date(d); return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0'); };
const num = (v) => (v === null || v === undefined || v === '' || isNaN(Number(v)) ? null : Math.round(Number(v) * 1000) / 1000);

//  사이트 값 → 포털에서 쓰는 이름 (2026-11-14 실제 응답으로 확인한 칸)
function plantOf(p) {
  const problems = [];
  if (p.plantSts && p.plantSts !== 'normal') problems.push('발전소 ' + (STS[p.plantSts] || p.plantSts));
  if (p.iotSts && p.iotSts !== 'on') problems.push('IoT 통신 ' + (STS[p.iotSts] || p.iotSts));
  if (p.derRtuSts && p.derRtuSts !== 'on') problems.push('RTU 통신 ' + (STS[p.derRtuSts] || p.derRtuSts));
  if (p.blocked) problems.push('차단됨');
  return {
    id: String(p.tid), name: p.name || '', addr: p.addr || '',
    capacityKw: num(p.capacity),        // 설비 용량 kW
    nowKw: num(p.nomActPower),          // 지금 발전 kW
    todayKwh: num(p.daiPowYields),      // 오늘 kWh
    totalKwh: num(p.totPowYields),      // 누적 kWh
    todayHours: num(p.daiDevTime),      // 오늘 발전시간 (kWh ÷ 용량)
    yesterdayKwh: num(p.previousPower), // 어제 kWh
    yesterdayHours: num(p.previousDevTime),
    powerFactor: num(p.powerFactor),
    plantSts: p.plantSts || '', iotSts: p.iotSts || '', rtuSts: p.derRtuSts || '',
    stsText: STS[p.plantSts] || p.plantSts || '',
    problems,
  };
}
function overviewOf(o) {
  o = o || {};
  return {
    plants: num(o.qty), normal: num(o.normalQty), fault: num(o.faultQty), check: num(o.checkQty), offline: num(o.offlineQty),
    nowKw: num(o.nomActPower), todayKwh: num(o.daiPowYields), monthKwh: num(o.monthPowYields), totalKwh: num(o.totPowYields),
    capacityKw: num(o.totalCapacity), monthAvgHours: num(o.monthAvgDevTime),
  };
}

module.exports = function mountSolar(app, ctx) {
  ctx = ctx || {};
  const DIR = ctx.dir || process.env.SOLAR_DIR || path.join(os.homedir(), 'solar', 'data');
  const PASS = ctx.passFile || process.env.VPP_PASS_FILE || path.join(os.homedir(), '.vpp-pass');
  const EVERY = Math.max(0.05, Number(ctx.everyMin) || 10) * 60000;
  fs.mkdirSync(path.join(DIR, 'days'), { recursive: true });
  const userOf = ctx.user || ((req) => {
    const u = req.session && req.session.user;
    if (!u) return null;
    const id = [u.username, u.id, u.user_id, u.uid, u.login, u.name].find((v) => v !== undefined && v !== null && v !== '');
    if (id === undefined) return null;
    return { id: String(id), admin: !!(u.is_admin || u.isAdmin || u.admin || u.role === 'admin' || u.level === 'admin' || u.grade === 'admin') };
  });
  const canView = (u) => (typeof ctx.view === 'function' ? !!ctx.view(u) : ctx.view === 'admin' ? u.admin : true);
  const notify = async (msg) => {
    console.log('[태양광] ' + msg);
    if (typeof ctx.notify === 'function') { try { await ctx.notify(msg, '/solar'); } catch (e) { console.warn('[태양광] 알림 실패', e.message); } }
  };

  const writeJson = (f, v) => { const t = f + '.tmp'; fs.writeFileSync(t, JSON.stringify(v)); fs.renameSync(t, f); };
  const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { return d; } };
  const F_LATEST = path.join(DIR, 'latest.json'), F_DAILY = path.join(DIR, 'daily.json');
  let latest = readJson(F_LATEST, null);
  const daily = readJson(F_DAILY, {});
  let busy = false, failCount = 0;
  const lastProblems = {};
  if (latest && latest.plants) latest.plants.forEach((p) => { lastProblems[p.id] = (p.problems || []).join(', '); });

  async function collect() {
    if (busy) return latest;
    busy = true;
    const v = ctx.vpp || new Vpp({ base: ctx.base || process.env.VPP_BASE });
    try {
      const { id, pw } = readPassFile(PASS);
      await v.login(id, pw);
      const [ov, pp] = await Promise.all([v.overview(), v.plantsPower()]);
      v.logout();
      const at = Date.now();
      const list = Array.isArray(pp) ? pp : ((pp && (pp.items || pp.list)) || []);
      const plants = list.map(plantOf);
      const overview = overviewOf(ov);
      const alerts = plants.filter((p) => p.problems.length).map((p) => p.name + ': ' + p.problems.join(', '));
      latest = { at, overview, plants, alerts };
      writeJson(F_LATEST, latest);
      //  그날 기록 (그래프용) — 한 줄에 하나
      fs.appendFileSync(path.join(DIR, 'days', ymd(at) + '.jsonl'), JSON.stringify({ t: at, kw: overview.nowKw, kwh: overview.todayKwh, p: plants.map((p) => [p.id, p.nowKw, p.todayKwh]) }) + '\n');
      //  날짜별 합계 — 오늘 값은 계속 덮어쓰고, 어제 값은 사이트의 「어제」 로 바로잡는다
      const d = ymd(at), y = ymd(at - 86400000);
      const t = daily[d] || {};
      daily[d] = { kwh: overview.todayKwh, peakKw: Math.max(t.peakKw || 0, overview.nowKw || 0), hours: plants.length === 1 ? plants[0].todayHours : t.hours || null };
      const yk = plants.reduce((s, p) => s + (p.yesterdayKwh || 0), 0);
      if (plants.length && plants.every((p) => p.yesterdayKwh !== null)) {
        daily[y] = Object.assign({}, daily[y] || {}, { kwh: Math.round(yk * 10) / 10 }, plants.length === 1 && plants[0].yesterdayHours !== null ? { hours: plants[0].yesterdayHours } : {});
      }
      writeJson(F_DAILY, daily);
      //  상태 바뀜 알림
      for (const p of plants) {
        const now = p.problems.join(', '), was = lastProblems[p.id] || '';
        if (now && now !== was) await notify('⚠️ 태양광 ' + p.name + ' — ' + now);
        else if (!now && was) await notify('✅ 태양광 ' + p.name + ' 정상으로 돌아옴');
        lastProblems[p.id] = now;
      }
      if (failCount >= 3) await notify('✅ 태양광 사이트 다시 연결됨');
      failCount = 0;
      return latest;
    } catch (e) {
      failCount++;
      console.warn('[태양광] 가져오기 실패 (' + failCount + '번째): ' + e.message);
      if (latest) { latest.error = e.message; latest.errorAt = Date.now(); }
      else latest = { at: null, overview: null, plants: [], alerts: [], error: e.message, errorAt: Date.now() };
      if (failCount === 3) await notify('❌ 태양광 사이트에서 3번 연속 못 가져왔습니다: ' + e.message);
      return latest;
    } finally { busy = false; }
  }

  const first = setTimeout(collect, ctx.firstDelayMs === undefined ? 20000 : ctx.firstDelayMs);
  const timer = setInterval(collect, EVERY);
  if (first.unref) first.unref();
  if (timer.unref) timer.unref();

  //  ── API ──
  const guard = (req, res) => {
    const u = userOf(req);
    if (!u) { res.status(401).json({ error: '로그인이 필요합니다' }); return null; }
    if (!canView(u)) { res.status(403).json({ error: '볼 권한이 없습니다' }); return null; }
    return u;
  };
  app.get('/api/solar/latest', (req, res) => { const u = guard(req, res); if (!u) return; res.json(Object.assign({ everyMin: EVERY / 60000, admin: u.admin }, latest || { at: null, plants: [], alerts: [] })); });
  app.get('/api/solar/today', (req, res) => {
    if (!guard(req, res)) return;
    const d = /^\d{4}-\d{2}-\d{2}$/.test(req.query.date || '') ? req.query.date : ymd(Date.now());
    let rows = [];
    try { rows = fs.readFileSync(path.join(DIR, 'days', d + '.jsonl'), 'utf8').split('\n').filter(Boolean).map((l) => { try { const r = JSON.parse(l); return { t: r.t, kw: r.kw, kwh: r.kwh }; } catch (e) { return null; } }).filter(Boolean); } catch (e) { /* 그날 기록 없음 */ }
    res.json({ date: d, rows });
  });
  app.get('/api/solar/daily', (req, res) => {
    if (!guard(req, res)) return;
    const n = Math.min(400, Math.max(1, Number(req.query.days) || 30));
    const out = [];
    for (let i = n - 1; i >= 0; i--) { const d = ymd(Date.now() - i * 86400000); out.push(Object.assign({ date: d }, daily[d] || { kwh: null })); }
    res.json({ days: out });
  });
  app.post('/api/solar/refresh', async (req, res) => {
    const u = guard(req, res); if (!u) return;
    if (!u.admin) return res.status(403).json({ error: '관리자만' });
    res.json(await collect());
  });
  const PAGE = path.join(__dirname, 'solar-page.html');
  app.get('/solar', (req, res) => {
    if (!userOf(req)) return res.redirect('/?next=' + encodeURIComponent('/solar'));
    res.setHeader('Cache-Control', 'no-cache');
    res.sendFile(PAGE);
  });

  return { collect, latest: () => latest, stop: () => { clearTimeout(first); clearInterval(timer); } };
};
module.exports.plantOf = plantOf;
module.exports.overviewOf = overviewOf;
