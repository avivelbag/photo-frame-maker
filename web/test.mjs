import Module from 'manifold-3d';
import {createRequire} from 'module';
const FG = createRequire(import.meta.url)('./frame-geom.js');
const wasm = await Module(); wasm.setup();
let bad = 0;
for (const style of Object.keys(FG.STYLES)) for (const border of [12, 19, 30, 40]) {
  const p = {mode:'photo', w:101.6, h:152.4, border, overlap:2.5, stack:2.2, keyhole:true, plate:true, stand:true, style, fit: border === 40 ? 0.15 : border === 12 ? -0.2 : 0};
  const r = FG.build(wasm, p);
  if (r.errors.length) { console.log(style, border, 'ERR', r.errors.join(' ')); continue; }
  const st = Object.entries(r.parts).map(([k, m]) => {
    const ok = m.status() === 'NoError' && m.decompose().length === 1 && m.volume() > 0;
    if (!ok) bad++;
    return `${k}:${ok ? 'ok' : 'BAD ' + m.status() + ' parts=' + m.decompose().length}`;
  });
  console.log(style.padEnd(8), String(border).padStart(2), 'depth', r.dims.maxZ.toFixed(1), 'keyhole', r.keyhole, 'frameVol', (r.parts.frame.volume()/1000).toFixed(1), st.join(' '));
}
// deep pocket should be refused for shallow-lipped styles
for (const style of ['classic', 'gallery']) console.log(style, 'stack 4:', FG.build(wasm, {mode:'outer', w:120, h:120, border:19, overlap:2.5, stack:4, keyhole:true, plate:false, stand:false, style}).errors);
console.log('bad parts:', bad);
