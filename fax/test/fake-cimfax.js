//  시험용 가짜 CimFAX 장비 — FaxGo 가 기대하는 대로 답한다
//   인사(VERIFY_STRING) → LOGIN 확인(md5(VERIFY + cal128MD5(비밀번호))) → SENDFAX: R 주고 조각 받기 → RECV_OK + TASKID
//   GET_SEND_FAX_STATUS: OK + AMOUNT, R 마다 1024 바이트 기록
'use strict';
const net = require('net'), crypto = require('crypto');
const { cal128MD5 } = require('../portal/cimfax-client');

function start(opt) {
  opt = opt || {};
  const base = opt.portBase || 33001;
  const users = opt.users || { hanil: 'pw1234' };
  const got = { faxes: [], logins: [], bad: 0 };
  let nextTask = 101;
  const servers = [];
  const md5 = (s) => crypto.createHash('md5').update(s, 'utf8').digest('hex');
  const tag = (t, n) => { const m = new RegExp('<' + n + '>([\\s\\S]*?)</' + n + '>', 'i').exec(t); return m ? m[1] : ''; };

  function serve(port, onLogged) {
    const srv = net.createServer((sock) => {
      let buf = Buffer.alloc(0), stage = 'login', verify = crypto.randomBytes(6).toString('hex'), user = '';
      const say = (s) => sock.write(Buffer.from(s, 'utf16le'));
      say(`<SERVICE_NAME>CIMFAX_LOGIN</SERVICE_NAME><SWVER>5060</SWVER><SERVER_ID>${opt.serverId || '00ABCDEF'}</SERVER_ID><SERVER_NAME>HANIL-FAX</SERVER_NAME><VERIFY_STRING>${verify}</VERIFY_STRING>`);
      const ctx = { say, sock, setStage: (s) => { stage = s; }, user: () => user };
      sock.on('data', (d) => {
        buf = Buffer.concat([buf, d]);
        for (;;) {
          if (!buf.length) return;
          if (stage === 'login') {
            const t = buf.toString('utf16le');
            if (!/<\/PASSWORD>/.test(t)) return;
            buf = Buffer.alloc(0);
            user = tag(t, 'USERNAME');
            const ok = users[user] !== undefined && tag(t, 'PASSWORD') === md5(verify + cal128MD5(users[user]));
            got.logins.push({ port, user, ok });
            if (!ok) { got.bad++; say('<LOGIN_STATE>DENY</LOGIN_STATE>'); sock.end(); return; }
            say('<LOGIN_STATE>OK</LOGIN_STATE><PERMISSION>3</PERMISSION><EXT_NUM>801</EXT_NUM><BIND></BIND>');
            stage = 'ready';
            continue;
          }
          const r = onLogged(ctx, buf);
          if (!r) return;
          buf = r.rest;
        }
      });
      sock.on('error', () => {});
    });
    srv.listen(port, '127.0.0.1');
    servers.push(srv);
  }

  //  보내기 (3002)
  serve(base + 1, (c, buf) => {
    if (!c.job) {
      const t = buf.toString('utf16le');
      if (!/<\/BUFSIZE>/.test(t)) return null;
      c.job = { len: +tag(t, 'FILELEN'), head: +tag(t, 'HEADERSIZE'), bs: +tag(t, 'BUFSIZE'), data: [], n: 0 };
      if (opt.refuse) { c.say('<FEEDBACK>FAILED</FEEDBACK>'); return { rest: Buffer.alloc(0) }; }
      //  진짜 장비(현장 5060 계열)처럼: 머리 크기가 다르면 거부
      if (!(opt.headerSizes || [1024]).includes(c.job.head)) { got.rejected = (got.rejected || 0) + 1; c.say('<ERROR>Header size is invalidate!</ERROR>'); c.job = null; return { rest: Buffer.alloc(0) }; }
      c.say('R');
      return { rest: Buffer.alloc(0) };
    }
    const j = c.job;
    j.data.push(buf); j.n += buf.length;
    const want = Math.min(j.len, Math.ceil(j.n / j.bs) * j.bs);
    if (j.n < j.len && j.n % j.bs === 0) c.say('R');
    else if (j.n >= j.len) {
      const all = Buffer.concat(j.data);
      const taskId = nextTask++;
      got.faxes.push({ user: c.user(), taskId, header: all.subarray(0, j.head), tiff: all.subarray(j.head), headSize: j.head, bufSize: j.bs, fileLen: j.len });
      setTimeout(() => c.say(`<FEEDBACK>RECV_OK</FEEDBACK><TASKID>${taskId}</TASKID><INTER_FORWARD>0</INTER_FORWARD>`), 5);
    }
    void want;
    return { rest: Buffer.alloc(0) };
  });

  //  명령 (3007) — 보낸 팩스 상태
  serve(base + 6, (c, buf) => {
    const t = buf.toString('utf16le');
    if (c.queue) {
      if (t.trim() !== 'R') return { rest: Buffer.alloc(0) };
      const f = c.queue.shift();
      const b = Buffer.alloc(1024);
      b.writeInt32LE(f.taskId, 4);
      b.writeInt32LE(opt.status === undefined ? 0 : opt.status, 24);
      b.write('0212345678', 96, 'utf16le');
      b.writeInt32LE(f.header.readInt32LE(160), 160);
      b.writeInt32LE(f.header.readInt32LE(160), 164);
      b.writeInt32LE(5, 168);
      b.writeInt32LE(1, 172);
      c.sock.write(b);
      return { rest: Buffer.alloc(0) };
    }
    if (!/<\/TASK_ID_LIST>/.test(t)) return null;
    const ids = tag(t, 'TASK_ID_LIST').split(',').map(Number);
    c.queue = got.faxes.filter((f) => ids.includes(f.taskId));
    c.say(`<FEEDBACK>OK</FEEDBACK><AMOUNT>${c.queue.length}</AMOUNT>`);
    return { rest: Buffer.alloc(0) };
  });

  return { got, close: () => servers.forEach((s) => s.close()), portBase: base };
}
module.exports = start;
