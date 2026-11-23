//  ✍ 전자 서명 — 인증서(.pfx·.p12)로 PDF 표준 서명(adbe.pkcs7.detached) · 서명 검사
//   1) 고친 것을 모두 넣은 PDF 를 만들고 서명 칸(위젯)과 서명 값(/Sig)을 넣는다 — Contents 는 0 으로 비워 두고
//   2) 파일에서 Contents 자리를 찾아 ByteRange(그 자리를 뺀 앞·뒤)를 채운 뒤
//   3) 그 앞·뒤 바이트의 SHA-256 으로 PKCS#7 서명을 만들어 Contents 자리에 넣는다(파일 길이는 그대로)
//   ⚠ 서명한 뒤 다시 고쳐 저장하면 서명이 깨진다(이 리더는 덧붙여 저장(증분)을 하지 않음)
import forge from 'node-forge';
import { PDFDocument, PDFName, PDFHexString, PDFString, PDFDict, PDFRef, PDFArray } from 'pdf-lib';

const N = (s) => PDFName.of(s);
const SIG_BYTES = 12000;                                    //  서명 자리(바이트) — 인증서 사슬이 길어도 넉넉히
const PH = 9999999999;                                      //  ByteRange 자리표

//  인증서 이름(UTF-8 로 들어 있음)을 글자로
const nameOf = (cert, which = 'subject') => { const f = cert[which].getField('CN') || cert[which].getField('O'); if (!f) return ''; try { return forge.util.decodeUtf8(f.value); } catch { return f.value; } };
const bin = (u8) => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return s; };
const pdfDate = (t = new Date()) => { const p = (n) => String(n).padStart(2, '0'); const off = -t.getTimezoneOffset(); return 'D:' + t.getFullYear() + p(t.getMonth() + 1) + p(t.getDate()) + p(t.getHours()) + p(t.getMinutes()) + p(t.getSeconds()) + (off >= 0 ? '+' : '-') + p(Math.floor(Math.abs(off) / 60)) + "'" + p(Math.abs(off) % 60) + "'"; };

//  .pfx → { key, cert, chain, cn }
export function readPfx(bytes, password) {
  const p12 = forge.pkcs12.pkcs12FromAsn1(forge.asn1.fromDer(bin(bytes)), password || '');
  const keyBags = [...(p12.getBags({ bagType: forge.pki.oids.pkcs8ShroudedKeyBag })[forge.pki.oids.pkcs8ShroudedKeyBag] || []), ...(p12.getBags({ bagType: forge.pki.oids.keyBag })[forge.pki.oids.keyBag] || [])];
  const certs = (p12.getBags({ bagType: forge.pki.oids.certBag })[forge.pki.oids.certBag] || []).map((b) => b.cert).filter(Boolean);
  if (!keyBags.length || !certs.length) throw new Error('인증서 파일에 개인 키나 인증서가 없습니다');
  const key = keyBags[0].key;
  //  개인 키와 짝인 인증서
  const cert = certs.find((c) => c.publicKey.n && key.n && c.publicKey.n.equals(key.n)) || certs[0];
  return { key, cert, chain: certs, cn: nameOf(cert) || '서명자' };
}

//  bytes(고친 것이 다 들어간 PDF) → 서명한 PDF 바이트
export async function signPdf(bytes, id, { page = 0, rect = null, fieldName = null, reason = '', location = '', image = null, contact = '' } = {}) {
  const doc = await PDFDocument.load(bytes, { updateMetadata: false });
  const ctx = doc.context, pages = doc.getPages(), form = doc.getForm();
  //  서명 칸 — 이름으로 찾거나, 비어 있는 첫 서명 칸, 없으면 새로(보이지 않는 칸 또는 rect)
  let widget = null, field = null;
  for (const f of form.acroForm.getAllFields()) {
    const [fd, fref] = f;
    if (String(fd.get(N('FT'))) !== '/Sig') continue;
    if (fieldName ? fd.get(N('T')) && fd.get(N('T')).decodeText() === fieldName : !fd.get(N('V'))) { field = fd; widget = fref; break; }
  }
  if (!field) {
    const pg = pages[page] || pages[0];
    const r = rect || [0, 0, 0, 0];
    const names = new Set(form.getFields().map((f) => f.getName()));
    let nm = '서명', k = 2; while (names.has(nm)) nm = '서명' + k++;
    widget = ctx.register(ctx.obj({ Type: 'Annot', Subtype: 'Widget', FT: 'Sig', T: PDFHexString.fromText(nm), Rect: r, F: 132, P: pg.ref }));
    let annots = pg.node.Annots();
    if (!annots) { annots = ctx.obj([]); pg.node.set(N('Annots'), annots); }
    annots.push(widget);
    form.acroForm.addField(widget);
    field = ctx.lookup(widget);
  }
  form.acroForm.dict.set(N('SigFlags'), ctx.obj(3));
  //  보이는 서명 모양(이름·날짜 그림)
  if (image && field instanceof PDFDict) {
    const r = field.get(N('Rect')) instanceof PDFArray ? field.get(N('Rect')).asArray().map((x) => x.asNumber()) : null;
    if (r && r[2] - r[0] > 1) {
      const im = await doc.embedPng(image);
      const w = Math.abs(r[2] - r[0]), hgt = Math.abs(r[3] - r[1]);
      const ap = ctx.register(ctx.flateStream('q ' + w + ' 0 0 ' + hgt + ' 0 0 cm /Im0 Do Q', { Type: 'XObject', Subtype: 'Form', BBox: [0, 0, w, hgt], Resources: { XObject: { Im0: im.ref } } }));
      field.set(N('AP'), ctx.obj({ N: ap }));
    }
  }
  const sig = ctx.obj({
    Type: 'Sig', Filter: 'Adobe.PPKLite', SubFilter: 'adbe.pkcs7.detached',
    ByteRange: [0, PH, PH, PH], Contents: PDFHexString.of('0'.repeat(SIG_BYTES * 2)),
    M: PDFString.of(pdfDate()), Name: PDFHexString.fromText(id.cn),
    ...(reason ? { Reason: PDFHexString.fromText(reason) } : {}), ...(location ? { Location: PDFHexString.fromText(location) } : {}), ...(contact ? { ContactInfo: PDFHexString.fromText(contact) } : {}),
    Prop_Build: { App: { Name: 'Hanil.PDF' } },
  });
  field.set(N('V'), ctx.register(sig));
  doc.setProducer('한일 PDF 리더 · 한일특장(주)');
  const out = await doc.save({ useObjectStreams: false });
  //  자리 찾기
  const s = bin(out);
  const brTxt = '[ 0 ' + PH + ' ' + PH + ' ' + PH + ' ]';
  const brAt = s.lastIndexOf(brTxt);
  const cAt = s.lastIndexOf('<' + '0'.repeat(SIG_BYTES * 2) + '>');
  if (brAt < 0 || cAt < 0) throw new Error('서명 자리를 찾지 못했습니다');
  const a = cAt, b = cAt + SIG_BYTES * 2 + 2, L = out.length;
  const br = ('[ 0 ' + a + ' ' + b + ' ' + (L - b) + ' ]');
  const brPad = br.slice(0, -1) + ' '.repeat(brTxt.length - br.length) + ']';
  for (let k = 0; k < brPad.length; k++) out[brAt + k] = brPad.charCodeAt(k);
  //  서명
  const data = bin(out.subarray(0, a)) + bin(out.subarray(b));
  const p7 = forge.pkcs7.createSignedData();
  p7.content = forge.util.createBuffer(data);
  for (const c of id.chain) p7.addCertificate(c);
  p7.addSigner({
    key: id.key, certificate: id.cert, digestAlgorithm: forge.pki.oids.sha256,
    authenticatedAttributes: [{ type: forge.pki.oids.contentType, value: forge.pki.oids.data }, { type: forge.pki.oids.messageDigest }, { type: forge.pki.oids.signingTime, value: new Date() }],
  });
  p7.sign({ detached: true });
  //  ⚠ node-forge 는 서명자 칸의 발급자 이름(한글 등 UTF-8)을 두 번 인코딩한다 → 인증서 원본의 발급자 이름으로 바꿔 끼운다
  const asn = p7.toAsn1();
  try {
    const tbs = forge.pki.certificateToAsn1(id.cert).value[0];
    const issuer = tbs.value[tbs.value[0].tagClass === forge.asn1.Class.CONTEXT_SPECIFIC ? 3 : 2];
    const sd = asn.value[1].value[0], infos = sd.value[sd.value.length - 1];
    for (const si of infos.value) si.value[1].value[0] = issuer;
  } catch (e) { console.warn('서명자 이름 바꾸기', e); }
  const der = forge.asn1.toDer(asn).getBytes();
  if (der.length > SIG_BYTES) throw new Error('서명이 너무 깁니다(' + der.length + ' 바이트)');
  const hex = forge.util.bytesToHex(der).toUpperCase().padEnd(SIG_BYTES * 2, '0');
  for (let k = 0; k < hex.length; k++) out[a + 1 + k] = hex.charCodeAt(k);
  return out;
}

//  🔍 서명 검사 — 서명 뒤에 문서가 바뀌었나(해시) · 서명이 그 인증서의 것인가(RSA)
//   ⚠ 인증서를 믿을 수 있는지(발급 기관·폐지)는 보지 않는다 — Acrobat 등에서
export async function verifyPdf(bytes) {
  const out = [];
  const s = bin(bytes);
  const re = /\/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]/g;
  let m;
  while ((m = re.exec(s))) {
    const [o1, l1, o2, l2] = m.slice(1).map(Number);
    const r = { ok: false, cn: '', time: null, covers: o2 + l2 === bytes.length, why: '' };
    try {
      //  ⚠ 뒤의 0 을 지우면 서명 끝의 진짜 00 바이트도 지워진다 → 그대로 읽고 뒤 남는 0 은 무시
      const hex = s.slice(o1 + l1 + 1, o2 - 1).replace(/[^0-9a-fA-F]/g, '');
      const der = forge.util.hexToBytes(hex.length % 2 ? hex + '0' : hex);
      const msg = forge.pkcs7.messageFromAsn1(forge.asn1.fromDer(der, { strict: false, parseAllBytes: false }));
      const cert = msg.certificates[0];
      r.cn = cert ? nameOf(cert) : '';
      const si = msg.rawCapture;
      const data = s.slice(o1, o1 + l1) + s.slice(o2, o2 + l2);
      //  해시 방식 — 다른 프로그램은 SHA-1·384·512 로도 서명한다
      let alg = 'sha256';
      try { alg = { [forge.pki.oids.sha1]: 'sha1', [forge.pki.oids.sha256]: 'sha256', [forge.pki.oids.sha384]: 'sha384', [forge.pki.oids.sha512]: 'sha512' }[forge.asn1.derToOid(si.digestAlgorithm)] || 'sha256'; } catch {}
      const mk = () => forge.md[alg].create();
      const md = mk(); md.update(data);
      //  서명된 속성(messageDigest)과 문서 해시 맞춰 보기
      const attrs = si.authenticatedAttributes || [];
      let digestOk = false;
      for (const at of attrs) {
        const oid = forge.asn1.derToOid(at.value[0].value);
        if (oid === forge.pki.oids.messageDigest) digestOk = at.value[1].value[0].value === md.digest().getBytes();
        if (oid === forge.pki.oids.signingTime) { try { r.time = forge.asn1.utcTimeToDate(at.value[1].value[0].value); } catch {} }
      }
      //  서명 값 검사 — 속성 묶음(SET)의 해시를 인증서 공개키로
      const set = forge.asn1.create(forge.asn1.Class.UNIVERSAL, forge.asn1.Type.SET, true, attrs);
      const amd = mk(); amd.update(forge.asn1.toDer(set).getBytes());
      let sigOk = false;
      try { sigOk = cert.publicKey.verify(amd.digest().getBytes(), si.signature); } catch {}
      r.ok = digestOk && sigOk;
      r.why = !digestOk ? '서명한 뒤 문서가 바뀌었습니다' : !sigOk ? '서명 값이 인증서와 맞지 않습니다' : (r.covers ? '' : '서명 뒤에 내용이 덧붙었습니다');
    } catch (e) { r.why = '서명을 읽지 못했습니다: ' + (e.message || e); }
    out.push(r);
  }
  return out;
}
