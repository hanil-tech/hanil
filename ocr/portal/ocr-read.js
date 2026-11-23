//  🔎 한일 포털 — 스캔 서식 OCR 읽개 (ocr-read.js)
//
//   손으로 쓴 생산일지·팩스 같은 스캔 서식을 Claude(비전)로 읽어 표로 돌려준다.
//   지금 포털 「AI 창구」가 인식률이 낮은 까닭과, 이 모듈이 고치는 점:
//     ① 쪽마다 방향이 다름(90° 돌아간 스캔) → 먼저 바로 세운다.
//     ② 10쪽을 한 번에·전처리 없이 보냄 → 쪽마다 따로, 고해상도·대비·기울기 보정 후 보낸다.
//     ③ 가장 작은 모델(Haiku) → 손글씨엔 더 강한 모델(기본 Opus 5.5, Sonnet 5.5 로 바꿀 수 있음).
//     ④ "그냥 읽어" → 서식의 칸 구조 + 아는 품번·공정 목록을 주어 **맞춰 읽게** 하고, 칸마다 확신도를 받는다(모르면 비움, 지어내지 않음).
//
//   넣는 법(포털):  npm i @anthropic-ai/sdk  후
//       const { extractProductionLog } = require('./ocr-read');
//       const out = await extractProductionLog({ pdf: '/경로/생산일지.pdf',
//         items: 아는품번목록, processes: ['사상','조립','포장','검사'], machines: ['M-1','라인1','UDI'] });
//   ⚠ 서버에 ANTHROPIC_API_KEY, 그리고 pdftoppm·ImageMagick(convert) 가 있어야 합니다(없으면 설치안내 참고).
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

let Anthropic;
try { Anthropic = require('@anthropic-ai/sdk'); } catch (e) { /* 설치 전이면 run 할 때 안내 */ }

const MODEL = process.env.OCR_MODEL || 'claude-opus-5-5';   // 손글씨엔 강한 모델. 비용을 줄이려면 'claude-sonnet-5-5'.
const ORIENT_MODEL = 'claude-haiku-5-5';                     // 방향만 보는 싼 모델

function tool(cmd) { try { return spawnSync(process.platform === 'win32' ? 'where' : 'which', [cmd]).status === 0; } catch (e) { return false; } }
const HAS_PDFTOPPM = tool('pdftoppm');
const MAGICK = tool('magick') ? 'magick' : (tool('convert') ? 'convert' : null);

// ── ① 쪽 그림 만들기(PDF → 쪽마다 PNG, 고해상도) ──────────────
function renderPages(pdfPath, workDir, dpi) {
  fs.mkdirSync(workDir, { recursive: true });
  if (HAS_PDFTOPPM) {
    const r = spawnSync('pdftoppm', ['-r', String(dpi || 220), '-png', pdfPath, path.join(workDir, 'p')], { encoding: 'utf8' });
    if (r.status !== 0) throw new Error('pdftoppm 실패: ' + (r.stderr || ''));
  } else if (MAGICK) {
    const r = spawnSync(MAGICK, ['-density', String(dpi || 220), pdfPath, path.join(workDir, 'p-%02d.png')]);
    if (r.status !== 0) throw new Error('ImageMagick PDF 변환 실패');
  } else {
    throw new Error('pdftoppm 또는 ImageMagick 가 필요합니다(설치안내).');
  }
  return fs.readdirSync(workDir).filter((f) => f.endsWith('.png')).sort().map((f) => path.join(workDir, f));
}

// ── ② 전처리(흐린 연필·잡음·기울기를 또렷하게) ───────────────
//    회색 → 기울기 보정 → 대비 평탄화 → 살짝 선명 → 너무 크면 줄임. 밝기 차가 큰 스캔에 효과가 큽니다.
function enhance(src) {
  if (!MAGICK) return src;
  const out = src.replace(/\.png$/, '.enh.png');
  const r = spawnSync(MAGICK, [src,
    '-colorspace', 'Gray',
    '-deskew', '40%',
    '-resize', '2200x2200>',            // 긴 변 2200px 로(이미 작으면 그대로)
    '-normalize', '-contrast-stretch', '1x1%',
    '-unsharp', '0x1',
    out]);
  return r.status === 0 && fs.existsSync(out) ? out : src;
}

function b64(p) { return fs.readFileSync(p).toString('base64'); }
function imgBlock(p) { return { type: 'image', source: { type: 'base64', media_type: 'image/png', data: b64(p) } }; }

// ── 방향 바로 세우기(90° 돌아간 스캔 때문에 인식률이 폭락) ──────
async function uprightIfNeeded(client, src) {
  if (!MAGICK) return src;
  try {
    const r = await client.messages.create({
      model: ORIENT_MODEL, max_tokens: 16,
      system: 'You see one scanned Korean production-log form. Reply with ONLY the clockwise degrees (0, 90, 180, or 270) needed to make the printed title and table upright. Reply with just the number.',
      messages: [{ role: 'user', content: [imgBlock(src), { type: 'text', text: '회전 각도?' }] }],
    });
    const t = (r.content.find((b) => b.type === 'text') || {}).text || '0';
    const deg = (t.match(/\d{1,3}/) || ['0'])[0];
    if (deg === '90' || deg === '180' || deg === '270') {
      const out = src.replace(/\.png$/, '.rot.png');
      if (spawnSync(MAGICK, [src, '-rotate', deg, out]).status === 0 && fs.existsSync(out)) return out;
    }
  } catch (e) { /* 방향 확인 실패하면 원본으로 간다 */ }
  return src;
}

// ── 한 쪽 읽기(양식 맞춤 + 칸별 확신도 + 아는 목록에 맞춤) ──────
function schemaFor(columns) {
  return {
    type: 'object', additionalProperties: false,
    required: ['date', 'worker_name', 'rows'],
    properties: {
      date: { type: ['string', 'null'], description: '일자 YYYY-MM-DD, 못 읽으면 null' },
      worker_name: { type: ['string', 'null'], description: '이름(직원). 한국·태국·베트남어일 수 있음' },
      rows: {
        type: 'array',
        items: {
          type: 'object', additionalProperties: false,
          required: columns.map((c) => c.key).concat(['confidence']),
          properties: Object.assign(
            {},
            ...columns.map((c) => ({ [c.key]: { type: ['string', 'null'], description: c.desc } })),
            { confidence: { type: 'object', additionalProperties: { type: 'number' }, description: '칸마다 0~100 확신도' } }),
        },
      },
    },
  };
}

const PRODLOG_COLUMNS = [
  { key: 'part_no', desc: '품번/품명 (예: 405950524-WD, 714.9-1-M). 아는 품번 목록에 가까우면 그 품번으로 고친다.' },
  { key: 'process', desc: '공정 (예: 사상, 조립, 포장, 검사). 아는 공정 목록에 맞춘다.' },
  { key: 'machine', desc: '설비 (예: M-1, 라인1, UDI).' },
  { key: 'start', desc: '시작 시각 (예: 08:00). 오전/오후 고려해 24시간으로.' },
  { key: 'end', desc: '종료 시각.' },
  { key: 'qty_good', desc: '생산 수량(숫자).' },
  { key: 'qty_bad', desc: '불량 수량(숫자). 보통 0.' },
  { key: 'bad_reason', desc: '불량 사유/비고.' },
];

function sysPrompt(columns, vocab) {
  const cols = columns.map((c) => '- ' + c.key + ': ' + c.desc).join('\n');
  const v = [];
  if (vocab.items && vocab.items.length) v.push('아는 품번 목록(이 중 하나에 가까우면 그 품번으로 고쳐 적어라): ' + vocab.items.slice(0, 400).join(', '));
  if (vocab.processes && vocab.processes.length) v.push('아는 공정: ' + vocab.processes.join(', '));
  if (vocab.machines && vocab.machines.length) v.push('아는 설비: ' + vocab.machines.join(', '));
  return [
    'You read ONE scanned, handwritten Korean "생산일지"(production log) form and return its table as structured data.',
    'The form has a header (일자 date, 이름 worker name) and a table where each ROW is one production record with these columns:',
    cols,
    '',
    'Rules:',
    '- Read the handwriting carefully. Numbers and part codes matter most.',
    '- For each cell give a confidence 0~100 in the "confidence" object (key = column name).',
    '- If a cell is empty or illegible, use null and confidence 0 — NEVER guess a value.',
    '- Worker names may be Korean, Thai (e.g. WANDEE NAKHARIN) or Vietnamese (e.g. DUONG NGOC DUY). Transcribe as printed/written.',
    '- Only return rows that actually have handwriting; ignore blank table lines.',
    v.length ? '\nKnown lists to match handwriting against:\n' + v.join('\n') : '',
  ].join('\n');
}

async function readPage(client, imgPath, columns, vocab, model) {
  const res = await client.messages.create({
    model: model || MODEL,
    max_tokens: 8000,
    thinking: { type: 'adaptive' },
    output_config: { effort: 'high', format: { type: 'json_schema', name: 'production_log_page', schema: schemaFor(columns) } },
    system: sysPrompt(columns, vocab),
    messages: [{ role: 'user', content: [imgBlock(imgPath), { type: 'text', text: '이 생산일지 한 쪽을 표로 읽어 주세요.' }] }],
  });
  const text = (res.content.find((b) => b.type === 'text') || {}).text || '{}';
  let data; try { data = JSON.parse(text); } catch (e) { data = { date: null, worker_name: null, rows: [] }; }
  // 쪽 전체 확신도 = 모든 칸 확신도의 평균
  let sum = 0, n = 0;
  (data.rows || []).forEach((r) => { Object.values(r.confidence || {}).forEach((c) => { sum += (+c || 0); n++; }); });
  data._pageConfidence = n ? Math.round(sum / n) : 0;
  return data;
}

// ── 바깥에서 부르는 함수 ──────────────────────────────────────
async function extractForm(opts) {
  opts = opts || {};
  if (!Anthropic) throw new Error('@anthropic-ai/sdk 가 설치돼 있지 않습니다. 포털 폴더에서  npm i @anthropic-ai/sdk');
  const client = new Anthropic({ apiKey: opts.apiKey || process.env.ANTHROPIC_API_KEY });
  const columns = opts.columns || PRODLOG_COLUMNS;
  const vocab = { items: opts.items, processes: opts.processes, machines: opts.machines };
  const model = opts.model || MODEL;

  const workDir = path.join(os.tmpdir(), 'hanil-ocr-' + crypto.randomBytes(6).toString('hex'));
  let pages = [];
  try {
    if (opts.pdf) pages = renderPages(opts.pdf, workDir, opts.dpi);
    else if (opts.images) pages = opts.images.slice();
    else throw new Error('pdf 또는 images 를 넘겨 주세요.');

    const out = { pages: [], rows: [] };
    for (let i = 0; i < pages.length; i++) {
      let img = enhance(pages[i]);
      img = await uprightIfNeeded(client, img);
      const page = await readPage(client, img, columns, vocab, model);
      page.page = i + 1;
      out.pages.push({ page: i + 1, date: page.date, worker_name: page.worker_name, confidence: page._pageConfidence, rowCount: (page.rows || []).length });
      (page.rows || []).forEach((r) => out.rows.push(Object.assign({ page: i + 1, worker_name: page.worker_name, date: page.date }, r)));
    }
    out.model = model;
    out.pageCount = pages.length;
    return out;
  } finally {
    try { fs.rmSync(workDir, { recursive: true, force: true }); } catch (e) {}
  }
}

const extractProductionLog = (opts) => extractForm(Object.assign({ columns: PRODLOG_COLUMNS }, opts));

module.exports = { extractForm, extractProductionLog, PRODLOG_COLUMNS };

// ── CLI:  node ocr-read.js 생산일지.pdf  ─────────────────────
if (require.main === module) {
  const pdf = process.argv[2];
  if (!pdf) { console.error('사용법: node ocr-read.js <생산일지.pdf>'); process.exit(1); }
  extractProductionLog({ pdf }).then((o) => console.log(JSON.stringify(o, null, 2)))
    .catch((e) => { console.error('오류:', e.message); process.exit(1); });
}
