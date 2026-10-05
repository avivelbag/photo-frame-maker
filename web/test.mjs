import Module from 'manifold-3d';
import fs from 'fs';
import {createRequire} from 'module';
const require = createRequire(import.meta.url);
const FG = require('./frame-geom.js');
const wasm = await Module(); wasm.setup();
for (const p of [
  {mode:'outer', w:120, h:120, border:19, overlap:2.5, stack:2.2, keyhole:true, plate:true, stand:true},
  {mode:'photo', w:102, h:152, border:22, overlap:3, stack:2.2, keyhole:true, plate:true, stand:true},
  {mode:'photo', w:54, h:86, border:12, overlap:2, stack:1.5, keyhole:true, plate:true, stand:true},
]) {
  const t0 = performance.now();
  const r = FG.build(wasm, p);
  if (r.errors.length) { console.log('ERR', r.errors); continue; }
  const s = Object.entries(r.parts).map(([k,m]) => {
    const b = m.boundingBox();
    return `${k}: ${(b.max[0]-b.min[0]).toFixed(1)}x${(b.max[1]-b.min[1]).toFixed(1)}x${(b.max[2]-b.min[2]).toFixed(1)} vol ${(m.volume()/1000).toFixed(1)} parts ${m.decompose().length} status ${m.status()}`;
  });
  console.log(p.mode, p.w, p.h, 'keyhole', r.keyhole, (performance.now()-t0).toFixed(0)+'ms\n  '+s.join('\n  '));
  if (p.w===120) fs.writeFileSync('js_frame.stl', Buffer.from(FG.toSTL(r.parts.frame,'frame')));
}
