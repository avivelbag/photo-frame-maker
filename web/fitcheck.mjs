import Module from 'manifold-3d';
import {createRequire} from 'module';
const FG = createRequire(import.meta.url)('./frame-geom.js');
const wasm = await Module(); wasm.setup();
for (const fit of [-0.2, 0, 0.2]) for (const sz of [[87,87],[54,86],[127,177.8]]) {
  const p = {mode:'photo', w:sz[0], h:sz[1], border:19, overlap:2.5, stack:2.2, keyhole:true, plate:true, stand:false, style:'classic', fit};
  const r = FG.build(wasm, p);
  const seated = r.parts.back_plate.translate([0,0,-2]).rotate([180,0,0]);   // undo print flip -> z 0..2
  const clash = r.parts.frame.intersect(seated).volume();
  const bb = seated.boundingBox();
  const wall = r.dims.rabW / 2;
  console.log(`fit ${fit>0?'+':''}${fit}  photo ${sz}  clash ${clash.toFixed(3)} mm3  catch reaches ${(bb.max[0]-wall).toFixed(2)} mm past wall  plate z ${bb.min[2].toFixed(2)}..${bb.max[2].toFixed(2)}`);
}
