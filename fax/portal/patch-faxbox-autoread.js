//  🤖 포털 faxbox.js 에 「새 팩스 자동 AI 판독」 을 넣는 패치
//   node patch-faxbox-autoread.js /data/portal/faxbox.js          넣기 (백업: faxbox.js.bak-autoread-날짜)
//   node patch-faxbox-autoread.js /data/portal/faxbox.js --undo   빼기
//
//   하는 일: 1분마다 「패치를 넣은 뒤 등록됐고 아직 판독 안 한」 받은 팩스를 한 장씩
//            「읽기」 단추와 똑같이 readFax(f, {}) → saveText(f, r) 로 판독한다.
//   · 한 팩스는 한 번만 시도 (실패해도 다시 안 함 — 비용이 되풀이되지 않게. 다시 하려면 「읽기」 단추)
//   · 패치를 넣기 전에 등록된 팩스(기존 2,235건)는 건드리지 않는다
//   · 이미 들어 있으면 다시 넣지 않는다
'use strict';
const fs = require('fs');

const file = process.argv[2];
const undo = process.argv.includes('--undo');
if (!file || !fs.existsSync(file)) { console.log('쓰는 법: node patch-faxbox-autoread.js /data/portal/faxbox.js [--undo]'); process.exit(1); }
let src = fs.readFileSync(file, 'utf8');
const BEGIN = '//  >>> 자동 AI 판독 (patch-faxbox-autoread)';
const END = '//  <<< 자동 AI 판독';

if (undo) {
  const a = src.indexOf(BEGIN), b = src.indexOf(END);
  if (a < 0 || b < 0) { console.log('들어 있지 않습니다 — 할 일 없음'); process.exit(0); }
  const lineStart = src.lastIndexOf('\n', a) + 1, lineEnd = src.indexOf('\n', b) + 1;
  fs.writeFileSync(file + '.bak-autoread-undo-' + Date.now(), src);
  fs.writeFileSync(file, src.slice(0, lineStart) + src.slice(lineEnd));
  console.log('✅ 뺐습니다. 포털을 다시 켜면 적용됩니다.');
  process.exit(0);
}

if (src.includes(BEGIN)) { console.log('이미 들어 있습니다 — 할 일 없음'); process.exit(0); }
for (const need of ['async function readFax(', 'function saveText(', "app.post('/api/fax/read/:id'"]) {
  if (!src.includes(need)) { console.log('❌ faxbox.js 모양이 예상과 다릅니다 (못 찾음: ' + need + ') — 바꾸지 않았습니다'); process.exit(1); }
}

//  ⚠ 넣는 「지금」 이후 등록된 팩스부터 — 오늘 아침 한꺼번에 들여온 지난 팩스(235건)까지 판독해 돈이 들지 않게
const since = new Date();
const snippet = `  ${BEGIN} — ${new Date().toISOString().slice(0, 10)}
  //   1분마다, ${since.toLocaleString('ko-KR')} 이후 포털에 등록됐고 아직 글자가 없는 받은 팩스를 한 장씩 「읽기」 와 똑같이 판독한다.
  //   한 팩스는 한 번만 시도(auto_read_at) — 실패해도 되풀이하지 않는다. 다시 하려면 화면의 「읽기」 단추.
  const AUTO_READ_SINCE = ${since.getTime()};
  let autoReadBusy = false;
  const autoReadTimer = setInterval(async () => {
    if (autoReadBusy) return;
    const d = (api && api.db) ? api.db() : null;
    if (!d) return;
    const f = (d.faxes || []).find((x) => !x.hidden && !x.text && !x.auto_read_at && (x.created_at || 0) >= AUTO_READ_SINCE);
    if (!f) return;
    autoReadBusy = true;
    f.auto_read_at = Date.now();
    try {
      const r = await readFax(f, {});
      if (r && r.ok) { saveText(f, r); console.log('[팩스] 자동 판독 ' + f.id + ' · ' + (r.how || '') + ' · ' + String(r.text || '').length + '자'); }
      else { f.auto_read_err = String((r && r.error) || '실패').slice(0, 200); try { if (api && api.save) api.save(); } catch (e) { /* */ } console.warn('[팩스] 자동 판독 실패 ' + f.id + ': ' + f.auto_read_err); }
    } catch (e) {
      f.auto_read_err = String(e.message).slice(0, 200);
      console.warn('[팩스] 자동 판독 오류 ' + f.id + ': ' + e.message);
    } finally { autoReadBusy = false; }
  }, 60000);
  if (autoReadTimer.unref) autoReadTimer.unref();
  ${END}
`;
const at = src.indexOf("app.post('/api/fax/read/:id'");
const lineStart = src.lastIndexOf('\n', at) + 1;
const backup = file + '.bak-autoread-' + new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
fs.writeFileSync(backup, src);
fs.writeFileSync(file, src.slice(0, lineStart) + snippet + src.slice(lineStart));
console.log('✅ 넣었습니다 (백업: ' + backup + ')');
console.log('   다음: node --check ' + file + '  →  포털 다시 켜기');
