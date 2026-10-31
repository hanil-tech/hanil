//  🔎 글자 찾기 — 화면 없이 도는 부분(node 로 시험한다)
//   한 페이지의 글은 pdf.js 의 글 조각(items)을 이어 붙인 것(raw)이다. 줄이 끝난 조각 뒤에는 '\n' 을 넣는다.
//   찾을 때는 raw 를 「맞춰 보기 좋은 모양」(norm)으로 바꾸고, norm 의 글자마다 raw 의 몇 번째 글자에서 왔는지 적어 둔다
//   → 찾은 자리를 raw 로 되돌려 미리보기 글과 화면의 노란 칠을 만든다.

const WS = /\s/;
const WORD = /[\p{L}\p{N}_]/u;

//  조각들 → raw 와, raw 글자마다 「몇 번째 조각의 몇 번째 글자」(줄바꿈은 조각 -1)
export function pageRaw(items, withMap = false) {
  let raw = '';
  const it = [], off = [];
  for (let i = 0; i < items.length; i++) {
    const s = items[i].str;
    if (s === undefined) continue;
    raw += s;
    if (withMap) for (let k = 0; k < s.length; k++) { it.push(i); off.push(k); }
    if (items[i].hasEOL) { raw += '\n'; if (withMap) { it.push(-1); off.push(0); } }
  }
  return withMap ? { raw, it, off } : { raw };
}

//  ⚠ NFKC: 전각 숫자·기호(４０３－５)와 ㈜ 같은 묶음 글자를 보통 글자로
export function normalize(raw, o) {
  let s = '';
  const map = [];
  let lastSpace = true;
  for (let i = 0; i < raw.length; i++) {
    let c = raw[i];
    //  짝 글자(이모지 등)는 둘을 함께
    const cp = raw.codePointAt(i);
    if (cp > 0xffff) { c = raw.slice(i, i + 2); }
    let n = c.normalize('NFKC');
    if (!o.caseSens) n = n.toLowerCase();
    for (const ch of n) {
      if (WS.test(ch)) {
        if (o.ignoreSpace || lastSpace) continue;
        s += ' '; map.push(i); lastSpace = true;
      } else {
        s += ch;
        for (let k = 0; k < ch.length; k++) map.push(i);
        lastSpace = false;
      }
    }
    if (cp > 0xffff) i++;
  }
  return { s, map };
}

export function prepare(q, o) {
  q = String(q || '').trim();
  const terms = o.any ? q.split(/\s+/) : [q];
  const out = [];
  for (const t of terms) {
    const n = normalize(t.normalize('NFC'), o).s.trim();
    if (n && !out.includes(n)) out.push(n);
  }
  return out;
}

//  raw 한 페이지에서 찾은 자리들 [{rs, re}] (raw 위치 · re 는 안 들어감) — 앞에서부터 차례로
export function searchRaw(raw, terms, o) {
  if (!terms.length || !raw) return [];
  const { s, map } = normalize(raw, o);
  const hits = [];
  for (const t of terms) {
    let from = 0;
    for (;;) {
      const p = s.indexOf(t, from);
      if (p < 0) break;
      const rs = map[p], re = map[p + t.length - 1] + 1;
      if (!o.word || (!WORD.test(raw[rs - 1] || ' ') && !WORD.test(raw[re] || ' ') )) hits.push({ rs, re });
      from = p + Math.max(1, t.length);
    }
  }
  hits.sort((a, b) => a.rs - b.rs || b.re - a.re);
  //  겹치는 것은 하나로(여러 낱말 찾기에서)
  const out = [];
  for (const h of hits) {
    const last = out[out.length - 1];
    if (last && h.rs < last.re) { if (h.re > last.re) last.re = h.re; continue; }
    out.push(h);
  }
  return out;
}

export function snippet(raw, rs, re, before = 14, after = 70) {   //  앞은 짧게 — 좁은 칸에서도 찾은 글자가 보이게
  const a = Math.max(0, rs - before), b = Math.min(raw.length, re + after);
  const clean = (x) => x.replace(/\s+/g, ' ');
  return {
    pre: (a > 0 ? '…' : '') + clean(raw.slice(a, rs)).trimStart(),
    hit: clean(raw.slice(rs, re)),
    post: clean(raw.slice(re, b)).trimEnd() + (b < raw.length ? '…' : ''),
  };
}
