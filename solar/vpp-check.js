//  ☀️ 에너지어스 VPP 확인 도구 — 포털 서버에서 실행
//
//   1) 아이디·비밀번호 파일 만들기 (한 번)
//        read -rp "VPP 아이디(이메일): " I; read -rsp "VPP 비밀번호: " P; printf '%s\n%s\n' "$I" "$P" > ~/.vpp-pass; chmod 600 ~/.vpp-pass; unset I P; echo
//   2) 로그인 시험:          node vpp-check.js
//   3) 데이터 모양 보기:      node vpp-check.js --probe            (값은 앞부분만, 구조 위주)
//   4) 전부 파일로 저장:      node vpp-check.js --dump vpp-dump.json
//   (다른 파일이면 --pass-file 경로)
'use strict';
const fs = require('fs'), os = require('os'), path = require('path');
const { Vpp, readPassFile } = require('./vpp-client');

const a = {};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i];
  if (k.startsWith('--')) { const v = process.argv[i + 1]; if (!v || v.startsWith('--')) a[k.slice(2)] = true; else { a[k.slice(2)] = v; i++; } }
}

//  모양 요약: 키와 값의 종류, 배열은 길이 + 첫 항목
function shape(v, depth) {
  depth = depth || 0;
  if (Array.isArray(v)) return depth > 4 ? '[…]' : { '배열 길이': v.length, '첫 항목': v.length ? shape(v[0], depth + 1) : null };
  if (v && typeof v === 'object') {
    if (depth > 4) return '{…}';
    const o = {};
    Object.keys(v).slice(0, 60).forEach((k) => { o[k] = shape(v[k], depth + 1); });
    return o;
  }
  if (typeof v === 'string') return v.length > 40 ? v.slice(0, 40) + '…' : v;
  return v;
}

(async () => {
  const file = a['pass-file'] && a['pass-file'] !== true ? a['pass-file'] : path.join(os.homedir(), '.vpp-pass');
  const { id, pw } = readPassFile(file);
  const v = new Vpp();
  console.log('▶ 로그인 …  (' + id.replace(/^(.).*(@.*)$/, '$1***$2') + ')');
  await v.login(id, pw);
  const me = await v.currentUser().catch((e) => ({ error: e.message }));
  console.log('✅ 로그인 성공 — ' + (me && (me.name || me.uName || me.mail || (me.team && me.team.name)) || '사용자'));

  if (!a.probe && !a.dump) { await v.logout(); return; }
  const out = { currentUser: me };
  for (const [name, fn] of [['overview', () => v.overview()], ['plantsPower', () => v.plantsPower()], ['myPlants', () => v.myPlants(0, 100)]]) {
    try { out[name] = await fn(); console.log('✅ ' + name); } catch (e) { out[name] = { error: e.message }; console.log('❌ ' + name + ' — ' + e.message); }
  }
  //  첫 발전소의 장비(인버터 등)
  const list = (out.myPlants && (out.myPlants.items || out.myPlants.list)) || (Array.isArray(out.plantsPower) ? out.plantsPower : (out.plantsPower && out.plantsPower.items)) || [];
  const first = list[0];
  const pid = first && (first.tid || first.id || first.pid);
  if (pid) { try { out.firstPlantThings = await v.plantThings(pid); console.log('✅ 첫 발전소 장비 (' + pid + ')'); } catch (e) { out.firstPlantThings = { error: e.message }; } }
  await v.logout();

  if (a.dump) {
    const f = a.dump === true ? 'vpp-dump.json' : a.dump;
    fs.writeFileSync(f, JSON.stringify(out, null, 2), { mode: 0o600 });
    console.log('📁 ' + path.resolve(f) + ' 에 저장 (본인만 읽기)');
  }
  if (a.probe) console.log(JSON.stringify(shape(out), null, 2));
})().catch((e) => { console.error('❌ ' + e.message); process.exit(1); });
