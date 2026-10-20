//  3D 엔진 일꾼(Web Worker) 글 — main.js 가 쓰고, build.mjs 가 occt-worker.js 로도 만든다
//   받는 것: { cmd:'warm' } 또는 { kind, u8, params } (+ wasm 또는 base)  → { ok, res } / { ok:0, err }
export const WORKER_BODY = `
let P = null;
self.onmessage = async (e) => {
  const d = e.data;
  try {
    if (!P) {
      const opt = {};
      if (d.wasm) opt.wasmBinary = d.wasm; else opt.locateFile = (f) => d.base + f;
      P = occtimportjs(opt);
    }
    const oc = await P;
    if (d.cmd === 'warm') { postMessage({ ok: 1 }); return; }
    const r = d.kind === 'step' ? oc.ReadStepFile(d.u8, d.params) : d.kind === 'iges' ? oc.ReadIgesFile(d.u8, d.params) : oc.ReadBrepFile(d.u8, d.params);
    if (!r || !r.success) { postMessage({ ok: 1, res: { success: false, meshes: [] } }); return; }
    const tr = [];
    const meshes = r.meshes.map((m) => {
      const pos = Float32Array.from(m.attributes.position.array); tr.push(pos.buffer);
      const o = { name: m.name, color: m.color, attributes: { position: { array: pos } } };
      if (m.attributes.normal) { const nn = Float32Array.from(m.attributes.normal.array); tr.push(nn.buffer); o.attributes.normal = { array: nn }; }
      if (m.index) { const ix = Uint32Array.from(m.index.array); tr.push(ix.buffer); o.index = { array: ix }; }
      return o;
    });
    postMessage({ ok: 1, res: { success: true, root: r.root, meshes } }, tr);
  } catch (x) { postMessage({ ok: 0, err: String((x && x.message) || x) }); }
};`;
