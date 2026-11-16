//  🧹 쓰지 않는 객체 치우기 — 문서 뿌리(Root·Info)에서 닿지 않는 객체는 저장하지 않는다
//   ⚠ pdf-lib 은 들고 있는 객체를 모두 쓴다: 지운 페이지·교정(검게 가림)한 옛 내용·지운 글자의 옛 내용이
//     파일 안에 그대로 남아, 메모장 같은 것으로 열면 보인다 → 저장 직전에 닿지 않는 것을 지운다.
import { PDFRef, PDFDict, PDFArray, PDFStream } from 'pdf-lib';

export function collectGarbage(doc) {
  const ctx = doc.context, seen = new Set(), stack = [];
  const visit = (o) => {
    if (!o) return;
    if (o instanceof PDFRef) { const k = o.tag; if (seen.has(k)) return; seen.add(k); stack.push(ctx.lookup(o)); return; }
    stack.push(o);
  };
  const t = ctx.trailerInfo;
  for (const r of [t.Root, t.Info, t.Encrypt, t.ID]) visit(r);
  while (stack.length) {
    const o = stack.pop();
    if (!o) continue;
    if (o instanceof PDFStream) visit(o.dict);
    else if (o instanceof PDFDict) for (const [, v] of o.entries()) visit(v);
    else if (o instanceof PDFArray) for (const v of o.asArray()) visit(v);
    else if (o instanceof PDFRef) visit(o);
  }
  let n = 0;
  for (const [ref] of ctx.enumerateIndirectObjects()) if (!seen.has(ref.tag)) { ctx.delete(ref); n++; }
  return n;
}
