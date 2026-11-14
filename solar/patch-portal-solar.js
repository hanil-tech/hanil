//  ☀️ 포털 server.js 에 태양광 조각을 넣는 패치 — faxbox 를 붙이는 줄 바로 앞에 한 줄 넣는다
//   node patch-portal-solar.js /data/portal/server.js [--notify 포털아이디]   넣기 (백업: server.js.bak-solar-날짜)
//   node patch-portal-solar.js /data/portal/server.js --undo                  빼기
//   --notify 를 주면 발전소 이상·복귀 때 그 사람에게 nopsPush 알림 (포털에 nopsPush 가 있을 때만)
'use strict';
const fs = require('fs');
const file = process.argv[2];
const undo = process.argv.includes('--undo');
const ni = process.argv.indexOf('--notify');
const who = ni > 0 ? process.argv[ni + 1] : '';
if (!file || !fs.existsSync(file)) { console.log('쓰는 법: node patch-portal-solar.js /data/portal/server.js [--notify 포털아이디] [--undo]'); process.exit(1); }
const src = fs.readFileSync(file, 'utf8');
const MARK = '// ☀️ 태양광 (patch-portal-solar)';
const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');

if (undo) {
  const a = src.indexOf(MARK);
  if (a < 0) { console.log('들어 있지 않습니다 — 할 일 없음'); process.exit(0); }
  const ls = src.lastIndexOf('\n', a) + 1, le = src.indexOf('\n', a) + 1;
  fs.writeFileSync(file + '.bak-solar-undo-' + stamp, src);
  fs.writeFileSync(file, src.slice(0, ls) + src.slice(le));
  console.log('✅ 뺐습니다. 포털을 다시 켜면 적용됩니다.');
  process.exit(0);
}
if (src.includes(MARK)) { console.log('이미 들어 있습니다 — 할 일 없음 (바꾸려면 --undo 뒤 다시)'); process.exit(0); }
const m = /^[ \t]*[^\n]*require\(\s*['"]\.\/faxbox(?:\.js)?['"]\s*\)[^\n]*$/m.exec(src);
if (!m) { console.log("❌ server.js 에서 require('./faxbox') 줄을 못 찾았습니다 — 바꾸지 않았습니다"); process.exit(1); }
const indent = /^[ \t]*/.exec(m[0])[0];
if (who && !/^[\w.@-]+$/.test(who)) { console.log('❌ --notify 아이디에 쓸 수 없는 글자가 있습니다'); process.exit(1); }
const notify = who ? `, notify: (msg) => { try { if (typeof nopsPush === 'function') nopsPush(${JSON.stringify(who)}, msg); } catch (e) { /* 알림 실패는 넘어감 */ } }` : '';
const line = `${indent}try { require('./solar-route')(app, { passFile: ${JSON.stringify(require('os').homedir() + '/.vpp-pass')}${notify} }); } catch (e) { console.warn('[태양광] 못 붙임:', e.message); } ${MARK}\n`;
fs.writeFileSync(file + '.bak-solar-' + stamp, src);
fs.writeFileSync(file, src.slice(0, m.index) + line + src.slice(m.index));
const ln = src.slice(0, m.index).split('\n').length;
console.log('✅ ' + ln + '번째 줄(faxbox) 앞에 넣었습니다 (백업: ' + file + '.bak-solar-' + stamp + ')');
console.log('   다음: node --check ' + file + '  →  포털 다시 켜기');
