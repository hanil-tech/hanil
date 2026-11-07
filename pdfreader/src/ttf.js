//  🔤 글꼴 다듬기 — 쓰는 글자의 모양(glyf)만 남기고 나머지는 비운 TTF
//   ⚠ pdf-lib 의 글자 고르기(subset)는 이 한글 글꼴에서 모양이 빠진다 → 글자 번호(gid)는 그대로 두고
//     안 쓰는 모양만 0 바이트로 만든 글꼴을 「통째로」 넣는다(번호가 같아 어긋날 일이 없다).
//   남기는 표: cmap·head·hhea·hmtx·maxp·name·OS/2·post·glyf·loca (나머지 — 힌팅·GSUB·GPOS·TSI… — 는 뺌)
const KEEP = new Set(['cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2', 'post', 'glyf', 'loca']);

export function slimTTF(bytes, gids) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const n = dv.getUint16(4), T = {};
  for (let k = 0; k < n; k++) {
    const o = 12 + k * 16;
    const tag = String.fromCharCode(bytes[o], bytes[o + 1], bytes[o + 2], bytes[o + 3]);
    T[tag] = { off: dv.getUint32(o + 8), len: dv.getUint32(o + 12) };
  }
  const longLoca = dv.getInt16(T.head.off + 50) === 1;
  const numGlyphs = dv.getUint16(T.maxp.off + 4);
  const loca = (g) => (longLoca ? dv.getUint32(T.loca.off + g * 4) : dv.getUint16(T.loca.off + g * 2) * 2);
  //  복합 글자(다른 모양을 가져다 쓰는 것)는 그 조각까지
  const need = new Set([0, ...gids]);
  const stack = [...need];
  while (stack.length) {
    const g = stack.pop();
    if (g >= numGlyphs) continue;
    const a = loca(g), b = loca(g + 1);
    if (b - a < 10) continue;
    const go = T.glyf.off + a;
    if (dv.getInt16(go) >= 0) continue;                    //  단순 글자
    let p = go + 10, more = true;
    while (more) {
      const flags = dv.getUint16(p), comp = dv.getUint16(p + 2);
      if (!need.has(comp)) { need.add(comp); stack.push(comp); }
      p += 4 + (flags & 1 ? 4 : 2);
      if (flags & 8) p += 2; else if (flags & 0x40) p += 4; else if (flags & 0x80) p += 8;
      more = !!(flags & 0x20);
    }
  }
  //  새 glyf·loca(긴 형식)
  const parts = [];
  const newLoca = new Uint8Array((numGlyphs + 1) * 4), ldv = new DataView(newLoca.buffer);
  let pos = 0;
  for (let g = 0; g < numGlyphs; g++) {
    ldv.setUint32(g * 4, pos);
    if (need.has(g)) {
      const a = loca(g), b = loca(g + 1);
      if (b > a) { const len = b - a, pad = (4 - (len % 4)) % 4; parts.push(bytes.subarray(T.glyf.off + a, T.glyf.off + b)); if (pad) parts.push(new Uint8Array(pad)); pos += len + pad; }
    }
  }
  ldv.setUint32(numGlyphs * 4, pos);
  const glyf = new Uint8Array(pos);
  let w = 0;
  for (const p of parts) { glyf.set(p, w); w += p.length; }
  const head = bytes.slice(T.head.off, T.head.off + T.head.len);
  new DataView(head.buffer).setInt16(50, 1);               //  indexToLocFormat = 긴 형식
  new DataView(head.buffer).setUint32(8, 0);               //  checkSumAdjustment(다시 안 셈 — 읽는 쪽이 보지 않음)
  const tables = [];
  for (const tag of Object.keys(T).sort()) {
    if (!KEEP.has(tag)) continue;
    let data = tag === 'glyf' ? glyf : tag === 'loca' ? newLoca : tag === 'head' ? head : bytes.subarray(T[tag].off, T[tag].off + T[tag].len);
    if (tag === 'post') { data = bytes.slice(T.post.off, T.post.off + 32); new DataView(data.buffer).setUint32(0, 0x00030000); }   //  글자 이름 표(크다)는 뺀다
    tables.push({ tag, data });
  }
  const nt = tables.length;
  let es = 0; while ((1 << (es + 1)) <= nt) es++;
  const hdrLen = 12 + nt * 16;
  let total = hdrLen;
  for (const t of tables) total += t.data.length + ((4 - (t.data.length % 4)) % 4);
  const out = new Uint8Array(total), odv = new DataView(out.buffer);
  odv.setUint32(0, 0x00010000); odv.setUint16(4, nt); odv.setUint16(6, (1 << es) * 16); odv.setUint16(8, es); odv.setUint16(10, nt * 16 - (1 << es) * 16);
  let off = hdrLen;
  tables.forEach((t, k) => {
    const o = 12 + k * 16;
    for (let j = 0; j < 4; j++) out[o + j] = t.tag.charCodeAt(j);
    let sum = 0;
    for (let j = 0; j < t.data.length; j += 4) sum = (sum + (((t.data[j] << 24) | ((t.data[j + 1] || 0) << 16) | ((t.data[j + 2] || 0) << 8) | (t.data[j + 3] || 0)) >>> 0)) >>> 0;
    odv.setUint32(o + 4, sum); odv.setUint32(o + 8, off); odv.setUint32(o + 12, t.data.length);
    out.set(t.data, off);
    off += t.data.length + ((4 - (t.data.length % 4)) % 4);
  });
  return out;
}

//  자주 쓰는 한글 2,350자(KS X 1001) — 양식 칸에 나중에 쓸 글자
let ksCache = null;
export function commonHangul() {
  if (ksCache) return ksCache;
  const dec = new TextDecoder('euc-kr');
  let s = '';
  for (let hi = 0xb0; hi <= 0xc8; hi++) for (let lo = 0xa1; lo <= 0xfe; lo++) s += dec.decode(new Uint8Array([hi, lo]));
  ksCache = s.replace(/�/g, '');
  return ksCache;
}
