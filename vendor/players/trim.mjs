import { NodeIO } from '@gltf-transform/core';
import { resample, prune, dedup } from '@gltf-transform/functions';
const [inp, out] = process.argv.slice(2);
const keep = new Set(['Idle_Loop','Walk_Loop','Jog_Fwd_Loop','Sprint_Loop','Crouch_Idle_Loop','Crouch_Fwd_Loop','Jump_Start','Jump_Loop','Jump_Land','Push_Loop']);
const io = new NodeIO();
const doc = await io.read(inp);
for (const a of doc.getRoot().listAnimations()) {
  if (!keep.has(a.getName())) { a.listChannels().forEach(c => c.dispose()); a.listSamplers().forEach(s => s.dispose()); a.dispose(); continue; }
  for (const ch of a.listChannels()) {
    const n = ch.getTargetNode()?.getName() ?? '';
    const path = ch.getTargetPath();
    // drop finger rotation tracks (hand stays rigid) and all translation/scale tracks except root and pelvis translation
    const finger = /^(index|middle|ring|pinky|thumb)_/.test(n);
    const keepTr = path === 'translation' && (n === 'root' || n === 'pelvis');
    if (finger || (path !== 'rotation' && !keepTr)) { ch.dispose(); }
  }
}
for (const a of doc.getRoot().listAnimations()) { const used = new Set(a.listChannels().map(c => c.getSampler())); for (const s of a.listSamplers()) if (!used.has(s)) s.dispose(); }
await doc.transform(resample({ tolerance: 2e-3 }), dedup(), prune());
console.log('accessors before', doc.getRoot().listAccessors().length);
for (const ac of doc.getRoot().listAccessors()) if (ac.listParents().every(p => p.propertyType === 'Root')) ac.dispose();
console.log('after', doc.getRoot().listAccessors().length);
await io.write(out, doc);
console.log('written', out);
