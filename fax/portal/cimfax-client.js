//  📠 CimFAX 장비와 직접 이야기하는 조각 — 팩스 보내기 · 보낸 팩스 상태
//
//   근거: CimFAX 공식 앱 FaxGo(Android) 의 LoginSuperMethod · SendFaxNetwork · FaxQueueNetwork · ConvertUtil · MD5Code ·
//         CFaxItem 을 디컴파일해서 똑같이 옮겼다. (docs/CimFAX_포털연동_분석.md 10장)
//         TIFF 형식은 CimFAX 클라이언트가 만든 TransReport.tif 와 같게: 폭 1728, 204×196 dpi, CCITT G3 2D.
//
//   흐름 (보내기, 장비 TCP 3002)
//     장비 → <SERVER_ID>…<SERVER_NAME>…<VERIFY_STRING>…           (접속하자마자)
//     포털 → <ACTION>LOGIN</ACTION><USERNAME>계정</USERNAME><PASSWORD>md5(VERIFY_STRING + cal128MD5(비밀번호))</PASSWORD>
//     장비 → <LOGIN_STATE>OK</LOGIN_STATE><PERMISSION>…<EXT_NUM>…
//     포털 → <ACTION>SENDFAX</ACTION><FILELEN>머리+TIFF</FILELEN><HEADERSIZE>1088</HEADERSIZE><BUFSIZE>1200</BUFSIZE>
//     장비 → R   포털 → 1200 바이트   (머리 1088 바이트 다음 TIFF, 끝날 때까지 반복)
//     장비 → <FEEDBACK>RECV_OK</FEEDBACK><TASKID>작업번호</TASKID>
//   글자는 모두 UTF-16LE, 끝 표시 없음.
'use strict';
const net = require('net');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');

const PORT = { login: 3001, send: 3002, voice: 3003, recv: 3005, admin: 3006, cmd: 3007 };
const HEADER_SIZE = 1024;
const BUF_SIZE = 1200;
const VERSION = '2026-11-14';   //  점검 도구가 찍는 판 — 머리 1024(FaxBox SENDFAX 와 같음) → 거부되면 1088

//  ── MD5 (FaxGo MD5Code: 시작값을 seed 로 비튼 MD5) ──
const K = new Uint32Array(64).map((_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0);
const R = [7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
  4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21];
function md5Seeded(buf, seed) {
  const s = seed || 0;
  let a0 = (0x67452301 + 11 * s) >>> 0, b0 = (0xefcdab89 + 71 * s) >>> 0, c0 = (0x98badcfe + 37 * s) >>> 0, d0 = (0x10325476 + 97 * s) >>> 0;
  const len = buf.length, padLen = ((len + 8) >> 6) + 1 << 6;
  const m = Buffer.alloc(padLen);
  buf.copy(m);
  m[len] = 0x80;
  m.writeUInt32LE((len * 8) >>> 0, padLen - 8);
  m.writeUInt32LE(Math.floor(len / 0x20000000), padLen - 4);
  for (let o = 0; o < padLen; o += 64) {
    let A = a0, B = b0, C = c0, D = d0;
    for (let i = 0; i < 64; i++) {
      let F, g;
      if (i < 16) { F = (B & C) | (~B & D); g = i; } else if (i < 32) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16; } else if (i < 48) { F = B ^ C ^ D; g = (3 * i + 5) % 16; } else { F = C ^ (B | ~D); g = (7 * i) % 16; }
      F = (F + A + K[i] + m.readUInt32LE(o + g * 4)) >>> 0;
      A = D; D = C; C = B;
      B = (B + ((F << R[i]) | (F >>> (32 - R[i])))) >>> 0;
    }
    a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0; c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0;
  }
  const out = Buffer.alloc(16);
  out.writeUInt32LE(a0, 0); out.writeUInt32LE(b0, 4); out.writeUInt32LE(c0, 8); out.writeUInt32LE(d0, 12);
  return out.toString('hex');
}
//  FaxGo 는 바이트 수가 아니라 글자 수만큼 넣는다(md5Update(bytes, s.length())) — 영문·숫자 비밀번호면 같다
const cal128MD5 = (pw) => [0, 1, 2, 3].map((k) => md5Seeded(Buffer.from(pw, 'utf8').subarray(0, pw.length), k)).join('');
const md5hex = (s) => crypto.createHash('md5').update(Buffer.from(s, 'utf8')).digest('hex');
const loginHash = (verify, pw) => md5hex(verify + cal128MD5(pw));

//  ── 태그 읽기 (FaxGo ConvertUtil.getValue — 대소문자 무시) ──
function tag(text, name) {
  const lo = text.toLowerCase(), n = name.toLowerCase();
  const a = lo.indexOf('<' + n + '>'), b = lo.indexOf('</' + n + '>');
  return a >= 0 && b > a ? text.substring(a + n.length + 2, b) : '';
}

//  ── 접속 ──
class Conn {
  constructor(sock, timeoutMs) {
    this.sock = sock; this.buf = Buffer.alloc(0); this.waiters = []; this.closed = false; this.timeout = timeoutMs || 15000;
    sock.on('data', (d) => { this.buf = Buffer.concat([this.buf, d]); this._wake(); });
    sock.on('close', () => { this.closed = true; this._wake(); });
    sock.on('error', (e) => { this.err = e; this.closed = true; this._wake(); });
  }
  _wake() { const w = this.waiters; this.waiters = []; w.forEach((f) => f()); }
  //  글자 받기: 무엇이든 도착하면 조금 더 기다렸다가(이어 오는 조각) 돌려준다
  async text(settleMs) {
    const until = Date.now() + this.timeout;
    while (this.buf.length < 2) {
      if (this.closed) throw this.err || new Error('장비가 연결을 끊었습니다');
      const left = until - Date.now();
      if (left <= 0) throw new Error('장비가 답하지 않습니다 (' + this.timeout / 1000 + '초)');
      await new Promise((ok) => { const t = setTimeout(ok, left); this.waiters.push(() => { clearTimeout(t); ok(); }); });
    }
    await new Promise((ok) => setTimeout(ok, settleMs === undefined ? 30 : settleMs));
    const n = this.buf.length & ~1;
    const s = this.buf.subarray(0, n).toString('utf16le');
    this.buf = this.buf.subarray(n);
    return s.replace(/\0+/g, '');
  }
  //  끝 표시(정규식)가 보일 때까지 모아서 바로 돌려준다 — 넉넉히 기다리지 않아 빠르다. 못 보면 graceMs 뒤 있는 만큼
  async textUntil(re, graceMs) {
    const until = Date.now() + this.timeout;
    let acc = '';
    for (;;) {
      const n = this.buf.length & ~1;
      if (n) { acc += this.buf.subarray(0, n).toString('utf16le').replace(/\0+/g, ''); this.buf = this.buf.subarray(n); }
      if (re.test(acc)) return acc;
      if (this.closed) { if (acc) return acc; throw this.err || new Error('장비가 연결을 끊었습니다'); }
      const left = until - Date.now();
      if (left <= 0) { if (acc) return acc; throw new Error('장비가 답하지 않습니다 (' + this.timeout / 1000 + '초)'); }
      const wait = acc ? Math.min(left, graceMs || 300) : left;
      const before = this.buf.length;
      await new Promise((ok) => { const t = setTimeout(ok, wait); this.waiters.push(() => { clearTimeout(t); ok(); }); });
      if (acc && this.buf.length === before) return acc;   //  더 안 오면 있는 만큼
    }
  }
  async bytes(n) {
    const until = Date.now() + this.timeout;
    while (this.buf.length < n) {
      if (this.closed) throw this.err || new Error('장비가 연결을 끊었습니다');
      const left = until - Date.now();
      if (left <= 0) throw new Error('장비가 답하지 않습니다');
      await new Promise((ok) => { const t = setTimeout(ok, left); this.waiters.push(() => { clearTimeout(t); ok(); }); });
    }
    const b = this.buf.subarray(0, n); this.buf = this.buf.subarray(n); return b;
  }
  say(s) { return new Promise((ok, no) => this.sock.write(Buffer.from(s, 'utf16le'), (e) => (e ? no(e) : ok()))); }
  raw(b) { return new Promise((ok, no) => this.sock.write(b, (e) => (e ? no(e) : ok()))); }
  close() { try { this.sock.destroy(); } catch (e) { /* 이미 */ } }
}

function connect(host, port, timeoutMs) {
  return new Promise((ok, no) => {
    const s = net.connect({ host, port });
    const t = setTimeout(() => { s.destroy(); no(new Error(host + ':' + port + ' 에 접속하지 못했습니다 (3초)')); }, 3000);
    s.once('connect', () => { clearTimeout(t); s.setNoDelay(true); ok(new Conn(s, timeoutMs)); });
    s.once('error', (e) => { clearTimeout(t); no(new Error(host + ':' + port + ' 접속 실패: ' + e.code)); });
  });
}

//  장비에 로그인 (FaxGo LoginSuperMethod.login) — 접속한 연결을 돌려준다
async function login(dev, port) {
  const c = await connect(dev.host, (dev.portBase ? dev.portBase - PORT.login : 0) + port, dev.timeoutMs);
  try {
    let hello = await c.text(200);
    if (!/VERIFY_STRING/i.test(hello)) hello += await c.text(200);
    const verify = tag(hello, 'VERIFY_STRING'), serverId = tag(hello, 'SERVER_ID');
    if (!verify) throw new Error('장비 인사말이 예상과 다릅니다: ' + hello.slice(0, 120));
    if (dev.serverId && serverId && String(dev.serverId).toLowerCase() !== serverId.toLowerCase()) throw new Error('장비 ID 가 다릅니다 (' + serverId + ')');
    await c.say('<ACTION>LOGIN</ACTION><USERNAME>' + dev.user + '</USERNAME><PASSWORD>' + loginHash(verify, dev.password || '') + '</PASSWORD>');
    const r = await c.text(100);
    const st = tag(r, 'LOGIN_STATE');
    if (st !== 'OK') throw new Error(st === 'DENY' ? 'CimFAX 계정 또는 비밀번호가 틀립니다' : '로그인 실패: ' + (st || r.slice(0, 120)));
    c.info = { serverId, serverName: tag(hello, 'SERVER_NAME'), permission: tag(r, 'PERMISSION'), ext: tag(r, 'EXT_NUM') };
    return c;
  } catch (e) { c.close(); throw e; }
}

//  ── 팩스 한 건의 머리 1088 바이트 (FaxGo CFaxItem → mergeArrays 순서 그대로) ──
function systemTime(d) {
  const b = Buffer.alloc(16);
  if (!d) return b;
  [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDay() + 1, d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds(), d.getUTCMilliseconds()]
    .forEach((v, i) => b.writeUInt16LE(v, i * 2));
  return b;
}
function shorts(str, n) {          //  FaxGo: UTF-8 바이트 하나를 short 하나에
  const b = Buffer.alloc(n * 2), src = Buffer.from(str || '', 'utf8');
  for (let i = 0; i < n && i < src.length; i++) b.writeUInt16LE(src[i], i * 2);
  return b;
}
//   1024: 장비·FaxBox 의 C 구조체 그대로 (FaxBox 는 0x400 바이트 머리를 보낸다 — Ghidra FUN_0044c6a0, 받은 팩스 머리 +0x194 수신자 · +0x1d4 발신자)
//   1088: FaxGo 앱 배치 (receiver 를 int[32] 로 보냄). 현장 장비(5060 계열)는 1088 을 「Header size is invalidate」 로 거부했다.
function buildHeader(o, size) {
  size = size || HEADER_SIZE;
  const h = Buffer.alloc(size);
  const i32 = (off, v) => h.writeInt32LE(v | 0, off);
  i32(24, 5);                                      //  status — FaxGo 가 새 작업에 넣는 값
  i32(28, o.priority === undefined ? 2 : o.priority);
  shorts(String(o.phone).replace(/--/g, ',,,,,,,,'), 32).copy(h, 96);
  i32(160, o.pages);
  i32(168, o.dialTotal === undefined ? 5 : o.dialTotal);
  systemTime(new Date()).copy(h, 176);
  if (o.planAt) systemTime(new Date(o.planAt)).copy(h, 192);
  //  ↓ 여기부터 배치가 갈린다: 장비(C 구조체)는 receiver 가 WCHAR[32]=64 바이트, FaxGo 는 int[32]=128 바이트
  const d = size === 1088 ? 0 : -64;
  i32(976 + d, o.retryMinutes || 0);
  i32(980 + d, o.quality === undefined ? 1 : o.quality);
  h[988 + d] = o.disableSvrHeader ? 1 : 0;
  h[996 + d] = o.disableDialPrefix ? 1 : 0;
  return h;
}

//  ── 보내기 (FaxGo SendFaxNetwork.uploadFax) ──
async function sendFax(dev, o) {
  const tiff = Buffer.isBuffer(o.tiff) ? o.tiff : await fsp.readFile(o.tiff);
  const sizes = dev.headerSize ? [dev.headerSize] : [1024, 1088];
  for (let i = 0; ; i++) {
    try {
      if (o.onAttempt) o.onAttempt(sizes[i]);
      return await sendOnce(dev, o, tiff, sizes[i]);
    } catch (e) {
      //  머리 크기를 거부하면(전화를 걸기 전) 다른 배치로 한 번 더
      if (i + 1 < sizes.length && /header\s*size/i.test(e.message)) continue;
      throw e;
    }
  }
}
async function sendOnce(dev, o, tiff, size) {
  const head = buildHeader(o, size);
  const all = Buffer.concat([head, tiff]);
  const c = await login(dev, PORT.send);
  try {
    await c.say('<ACTION>SENDFAX</ACTION><FILELEN>' + all.length + '</FILELEN><HEADERSIZE>' + head.length + '</HEADERSIZE><BUFSIZE>' + BUF_SIZE + '</BUFSIZE>');
    let sent = 0;
    for (;;) {
      const r = (await c.text(10)).trim();
      if (!r) continue;
      if (/^R+$/.test(r)) {
        for (let k = 0; k < r.length && sent < all.length; k++) {
          const piece = all.subarray(sent, sent + BUF_SIZE);
          await c.raw(piece);
          sent += piece.length;
          if (o.onProgress) o.onProgress(Math.round((100 * sent) / all.length));
        }
        continue;
      }
      const fb = tag(r, 'FEEDBACK');
      if (fb === 'RECV_OK') return { taskId: Number(tag(r, 'TASKID')) || tag(r, 'TASKID'), bytes: all.length, headerSize: size };
      throw new Error('장비가 받지 않았습니다: ' + (fb || tag(r, 'ERROR') || r.slice(0, 120)));
    }
  } finally { c.close(); }
}

//  ── 보낸 팩스 상태 (FaxGo FaxQueueNetwork — 장비 TCP 3007) ──
//   목록: 'all in queue'(대기 중 전부) 또는 작업번호들 '12,13'. 한 건마다 R 을 보내고 1024 바이트 기록을 받는다.
async function sendStatus(dev, list) {
  const c = await login(dev, PORT.cmd);
  try {
    await c.say('<ACTION>GET_SEND_FAX_STATUS</ACTION><TASK_ID_LIST>' + list + '</TASK_ID_LIST>');
    const r = await c.text(100);
    if (tag(r, 'FEEDBACK') !== 'OK') return { ok: false, raw: r.slice(0, 200), items: [] };
    const n = Number(tag(r, 'AMOUNT')) || 0, items = [];
    for (let i = 0; i < n; i++) {
      await c.say('R');
      const b = await c.bytes(1024);
      const s16 = (off, len) => b.subarray(off, off + len * 2).toString('utf16le').replace(/\0[\s\S]*$/, '');
      items.push({
        taskId: b.readInt32LE(4), status: b.readInt32LE(24), priority: b.readInt32LE(28),
        phone: s16(96, 32), pageTotal: b.readInt32LE(160), pageSent: b.readInt32LE(164),
        dialTotal: b.readInt32LE(168), dialDone: b.readInt32LE(172),
      });
    }
    return { ok: true, items };
  } finally { c.close(); }
}

//  ── 받은 팩스 (FaxGo ReceiveFaxNetwork — 장비 TCP 3007) ──
//   <ACTION>GET_NEW_FAX</ACTION><DATETIME>2001-01-01 00:00:00</DATETIME><TASK>마지막 작업번호</TASK><USER>계정</USER>
//   → <COUNT>남은 수</COUNT><TASK>…<TIME>UTC</TIME><CID>보낸번호</CID><FILE>8자리</FILE><SENDER>…<RECEIVER>…<SVRID>…<REMARK>…<STATUS_ID>…
//   한 번에 한 건. 받은 TASK 를 다음 요청에 넣어 이어 간다. COUNT 가 0 이면 끝.
async function listNewFaxes(dev, lastTask, max, onItem) {
  const c = await login(dev, PORT.cmd);
  const out = [];
  try {
    let task = Number(lastTask) || 0;
    for (let i = 0; i < (max || 200); i++) {
      await c.say('<ACTION>GET_NEW_FAX</ACTION><DATETIME>2001-01-01 00:00:00</DATETIME><TASK>' + task + '</TASK><USER>' + dev.user + '</USER>');
      const r = await c.textUntil(/<\/STATUS_ID>|<COUNT>\s*0\s*<\/COUNT>/i, 300);
      const count = Number(tag(r, 'COUNT')) || 0;
      if (count <= 0) break;
      const t = Number(tag(r, 'TASK'));
      if (!t || t <= task) break;                     //  같은 자리를 맴돌지 않게
      task = t;
      const time = tag(r, 'TIME');
      const at = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}/.test(time) ? Date.parse(time.replace(' ', 'T') + 'Z') : NaN;
      out.push({
        taskId: t, receivedAt: isNaN(at) ? Date.now() : at, timeRaw: time, cid: tag(r, 'CID'), file: tag(r, 'FILE'),
        sender: tag(r, 'SENDER'), receiver: tag(r, 'RECEIVER'), serverId: tag(r, 'SVRID'), remark: tag(r, 'REMARK'),
        status: tag(r, 'STATUS_ID'), left: count,
      });
      if (onItem) onItem(out[out.length - 1]);
    }
    return out;
  } finally { c.close(); }
}
//  파일 받기: $STG_DIR$FaxFiles/AB/CD/EF/GH.tif — FILE_LEN 을 받고, R 을 보낼 때마다 최대 1200 바이트
async function downloadFax(dev, file) {
  if (!/^[0-9A-Za-z]{8}$/.test(file)) throw new Error('팩스 파일 이름이 이상합니다: ' + file);
  const sep = dev.pathSep || '/';
  const p = '$STG_DIR$FaxFiles' + sep + [file.slice(0, 2), file.slice(2, 4), file.slice(4, 6), file.slice(6, 8)].join(sep) + '.tif';
  const c = await login(dev, PORT.cmd);
  try {
    await c.say('<ACTION>DOWN_FILE</ACTION><FILE>' + p + '</FILE><BUFSIZE>' + BUF_SIZE + '</BUFSIZE>');
    const r = await c.text(100);
    const len = Number(tag(r, 'FILE_LEN'));
    if (!(len > 0)) throw new Error('장비가 파일을 주지 않았습니다: ' + r.slice(0, 120));
    const parts = [];
    let got = 0;
    while (got < len) {
      const want = Math.min(BUF_SIZE, len - got);
      await c.say('R');
      const b = await c.bytes(want);
      parts.push(b); got += b.length;
    }
    return Buffer.concat(parts);
  } finally { c.close(); }
}

//  ── 팩스 TIFF → PDF (CCITT 압축 그대로 싣기 — 다시 그리지 않아 빠르고 화질 그대로) ──
function tiffToPdf(buf) {
  const le = buf.toString('latin1', 0, 2) === 'II';
  if (!le && buf.toString('latin1', 0, 2) !== 'MM') throw new Error('TIFF 가 아닙니다');
  const u16 = (o) => (le ? buf.readUInt16LE(o) : buf.readUInt16BE(o)), u32 = (o) => (le ? buf.readUInt32LE(o) : buf.readUInt32BE(o));
  const SZ = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8 };
  const pages = [];
  let off = u32(4);
  while (off && off < buf.length && pages.length < 500) {
    const n = u16(off), tags = {};
    for (let i = 0; i < n; i++) {
      const e = off + 2 + i * 12, id = u16(e), type = u16(e + 2), cnt = u32(e + 4);
      const size = (SZ[type] || 1) * cnt, vo = size > 4 ? u32(e + 8) : e + 8;
      const vals = [];
      for (let k = 0; k < cnt && k < 4096; k++) {
        if (type === 3) vals.push(u16(vo + k * 2));
        else if (type === 4) vals.push(u32(vo + k * 4));
        else if (type === 5) vals.push(u32(vo + k * 8) / (u32(vo + k * 8 + 4) || 1));
        else vals.push(buf[vo + k]);
      }
      tags[id] = vals;
    }
    pages.push(tags);
    off = u32(off + 2 + n * 12);
  }
  if (!pages.length) throw new Error('쪽이 없습니다');
  const objs = [];
  const add = (s) => { objs.push(s); return objs.length; };
  const pageIds = [];
  const catalog = add(null), pagesId = add(null);
  for (const t of pages) {
    const w = t[256][0], h = t[257][0], comp = (t[259] || [1])[0], photo = (t[262] || [0])[0];
    if (comp !== 3 && comp !== 4) throw new Error('CCITT 팩스 TIFF 가 아닙니다 (압축 ' + comp + ')');
    const offs = t[273], cnts = t[279];
    if (!offs || !cnts || offs.length !== 1) throw new Error('여러 조각으로 나뉜 TIFF 는 아직 못 바꿉니다');
    const data = buf.subarray(offs[0], offs[0] + cnts[0]);
    const t4 = (t[292] || [0])[0];
    const K = comp === 4 ? -1 : (t4 & 1 ? 1 : 0);
    const xr = (t[282] || [204])[0] || 204, yr = (t[283] || [196])[0] || 196;
    const pw = (w * 72) / xr, ph = (h * 72) / yr;
    //  Ghostscript 로 그려 보며 맞춤: G3 는 EndOfLine true, WhiteIsZero(0) 는 그대로, BlackIsZero(1) 만 뒤집는다
    const parms = `/K ${K} /Columns ${w} /Rows ${h}${comp === 3 ? ' /EndOfLine true' : ''}${t4 & 4 ? ' /EncodedByteAlign true' : ''}`;
    const img = add({ head: `<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} /ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /CCITTFaxDecode /DecodeParms << ${parms} >>${photo === 1 ? ' /Decode [1 0]' : ''} /Length ${data.length} >>`, data });
    const content = `q ${pw.toFixed(2)} 0 0 ${ph.toFixed(2)} 0 0 cm /Im0 Do Q`;
    const cs = add({ head: `<< /Length ${content.length} >>`, data: Buffer.from(content) });
    pageIds.push(add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 ${pw.toFixed(2)} ${ph.toFixed(2)}] /Resources << /XObject << /Im0 ${img} 0 R >> >> /Contents ${cs} 0 R >>`));
  }
  objs[catalog - 1] = `<< /Type /Catalog /Pages ${pagesId} 0 R >>`;
  objs[pagesId - 1] = `<< /Type /Pages /Kids [${pageIds.map((i) => i + ' 0 R').join(' ')}] /Count ${pageIds.length} >>`;
  const chunks = [Buffer.from('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n', 'latin1')];
  let pos = chunks[0].length;
  const xref = [];
  objs.forEach((o, i) => {
    xref.push(pos);
    const parts = typeof o === 'string' ? [Buffer.from(`${i + 1} 0 obj\n${o}\nendobj\n`, 'latin1')]
      : [Buffer.from(`${i + 1} 0 obj\n${o.head}\nstream\n`, 'latin1'), o.data, Buffer.from('\nendstream\nendobj\n', 'latin1')];
    parts.forEach((p) => { chunks.push(p); pos += p.length; });
  });
  const xs = `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + xref.map((x) => String(x).padStart(10, '0') + ' 00000 n \n').join('') +
    `trailer\n<< /Size ${objs.length + 1} /Root ${catalog} 0 R >>\nstartxref\n${pos}\n%%EOF\n`;
  chunks.push(Buffer.from(xs, 'latin1'));
  return { pdf: Buffer.concat(chunks), pages: pages.length };
}

//  ── PDF → 팩스 TIFF (Ghostscript) ──
function tiffPages(buf) {
  const le = buf.toString('latin1', 0, 2) === 'II';
  if (!le && buf.toString('latin1', 0, 2) !== 'MM') throw new Error('TIFF 파일이 아닙니다');
  const u16 = (o) => (le ? buf.readUInt16LE(o) : buf.readUInt16BE(o)), u32 = (o) => (le ? buf.readUInt32LE(o) : buf.readUInt32BE(o));
  let off = u32(4), pages = 0, width = 0;
  while (off && off < buf.length && pages < 1000) {
    const n = u16(off);
    for (let i = 0; i < n && pages === 0; i++) {
      const e = off + 2 + i * 12;
      if (u16(e) === 256) width = u16(e + 2) === 3 ? u16(e + 8) : u32(e + 8);
    }
    pages++;
    off = u32(off + 2 + n * 12);
  }
  return { pages, width };
}
function findGhostscript(given) {
  if (given) return given;
  if (process.env.GHOSTSCRIPT) return process.env.GHOSTSCRIPT;
  if (process.platform !== 'win32') return 'gs';
  for (const root of [process.env.ProgramFiles, process.env['ProgramFiles(x86)']].filter(Boolean)) {
    try {
      const gsDir = path.join(root, 'gs');
      const vers = fs.readdirSync(gsDir).sort().reverse();
      for (const v of vers) {
        for (const exe of ['gswin64c.exe', 'gswin32c.exe']) {
          const p = path.join(gsDir, v, 'bin', exe);
          if (fs.existsSync(p)) return p;
        }
      }
    } catch (e) { /* 없음 */ }
  }
  return 'gswin64c';
}
//  PDF 를 받아 팩스 TIFF 로. 이미 TIFF 면 폭(1728)만 확인하고 그대로.
async function toFaxTiff(input, outFile, opt) {
  opt = opt || {};
  const head = Buffer.alloc(8);
  const fd = await fsp.open(input, 'r');
  try { await fd.read(head, 0, 8, 0); } finally { await fd.close(); }
  const sig = head.toString('latin1', 0, 4);
  if (sig === 'II*\0' || sig === 'MM\0*') {
    const b = await fsp.readFile(input);
    const t = tiffPages(b);
    if (t.width !== 1728) throw new Error('팩스용 TIFF 가 아닙니다 (폭 ' + t.width + ', 1728 이어야 함) — PDF 로 올려 주세요');
    await fsp.copyFile(input, outFile);
    return { pages: t.pages, bytes: b.length };
  }
  if (sig !== '%PDF') throw new Error('PDF 또는 팩스 TIFF 만 보낼 수 있습니다');
  const gs = findGhostscript(opt.ghostscript);
  const args = ['-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=tiffg32d', '-r204x196', '-dAdjustWidth=1',
    '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', '-sOutputFile=' + outFile, input];
  await new Promise((ok, no) => execFile(gs, args, { timeout: opt.timeoutMs || 120000, windowsHide: true }, (e, so, se) => {
    if (e) no(new Error(e.code === 'ENOENT' ? 'Ghostscript 가 없습니다 — 포털 서버에 설치해 주세요 (설치안내 참고)' : 'PDF 변환 실패: ' + String(se || e.message).slice(0, 200)));
    else ok();
  }));
  const b = await fsp.readFile(outFile);
  const t = tiffPages(b);
  if (!t.pages) throw new Error('변환된 쪽이 없습니다');
  return { pages: t.pages, bytes: b.length };
}

module.exports = { VERSION, PORT, HEADER_SIZE, BUF_SIZE, md5Seeded, cal128MD5, loginHash, tag, connect, login, buildHeader, sendFax, sendStatus, listNewFaxes, downloadFax, tiffToPdf, toFaxTiff, tiffPages, findGhostscript };
