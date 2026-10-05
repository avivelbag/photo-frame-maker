// Parametric moulded photo frame. Port of frame.py; takes the manifold wasm module.
// All dimensions in mm. Frame back face on z=0.

const FrameGeom = (() => {
  const REF_BORDER = 19;     // profile was drawn for a 19 mm moulding
  const CORNER_R = 0.8;

  function deriveDims(p) {
    // p: {mode:'photo'|'outer', w, h, border, overlap, stack, clear}
    let sightW, sightH;
    if (p.mode === 'photo') {
      sightW = p.w - 2 * p.overlap;
      sightH = p.h - 2 * p.overlap;
    } else {
      sightW = p.w - 2 * p.border;
      sightH = p.h - 2 * p.border;
    }
    const outerW = sightW + 2 * p.border, outerH = sightH + 2 * p.border;
    const photoW = sightW + 2 * p.overlap, photoH = sightH + 2 * p.overlap;
    const rabW = photoW + 1.0, rabH = photoH + 1.0;     // 0.5 mm play around the photo
    const plateT = 2.0;
    const rabD = plateT + p.stack;                       // straight pocket depth
    return {sightW, sightH, outerW, outerH, photoW, photoH, rabW, rabH, rabD, plateT,
            rabInset: (outerW - rabW) / 2};
  }

  function validate(p, d, prof) {
    const errs = [];
    if (!errs.length && d.sightW >= 20 && p.border >= 12 && p.border <= 45) {
      const lip = minHeight(prof, d.rabInset, p.border) - (d.rabD + 1);
      if (lip < 1.2) errs.push(`This moulding is too shallow over the photo for a ${p.stack} mm pocket. Lower the pocket room to ${Math.max(0, p.stack - (1.2 - lip)).toFixed(1)} mm or less, or pick a deeper style.`);
    }
    if (!(d.sightW >= 20 && d.sightH >= 20)) errs.push('The photo window would be under 20 mm. Use a bigger size or a narrower moulding.');
    if (p.border < 12) errs.push('Moulding width must be at least 12 mm.');
    if (p.border > 45) errs.push('Moulding width can be at most 45 mm.');
    if (p.overlap < 1 || p.overlap >= p.border - 4) errs.push('Photo overlap must be between 1 mm and (moulding width − 4 mm).');
    if (p.stack < 0.5 || p.stack > 4) errs.push('Pocket depth must be between 0.5 and 4 mm.');
    return errs;
  }

  const arc = (cx, cz, r, a0, a1, n) => {
    const out = [];
    for (let i = 0; i < n; i++) {
      const a = (a0 + (a1 - a0) * i / (n - 1)) * Math.PI / 180;
      out.push([cx + r * Math.cos(a), cz + r * Math.sin(a)]);
    }
    return out;
  };

  // Each style returns the moulding cross-section as [d, z] points, d = distance in
  // from the outer edge (0..B), z = height. It starts at [0,0] and ends at [B,0].
  const STYLES = {
    classic: {
      name: 'Classic', blurb: 'Rounded outer bead, cove and a fine inner bead',
      fn(B) {
        const k = B / REF_BORDER;
        let p = [[0, 0], [0, 9.0]];
        p = p.concat(arc(2.6, 9.0, 2.6, 180, 90, 14).slice(1));
        p.push([3.6, 11.6], [4.1, 11.0]);
        for (let i = 1; i < 18; i++) { const t = i / 17; p.push([4.1 + t * 7.0, 8.8 + 2.2 * (1 - t) ** 2]); }
        p.push([12.0, 8.8]);
        p = p.concat(arc(13.2, 8.8, 1.2, 180, 0, 14).slice(1));
        p.push([14.8, 8.1], [15.4, 8.1], [REF_BORDER, 6.6], [REF_BORDER, 0]);
        return p.map(([d, z]) => [d * k, z]);
      },
    },
    gallery: {
      name: 'Gallery', blurb: 'Flat, deep face with crisp chamfers',
      fn: B => [[0, 0], [0, 9.4], [0.6, 10], [B - 0.6, 10], [B, 9.4], [B, 0]],
    },
    bevel: {
      name: 'Bevel', blurb: 'Slopes down toward the photo',
      fn: B => [[0, 0], [0, 11.0], [0.8, 11.8], [3.0, 11.8], [B - 1.4, 7.4], [B - 1.0, 7.0], [B, 7.0], [B, 0]],
    },
    reverse: {
      name: 'Reverse', blurb: 'Rises toward the photo, thin at the edge',
      fn: B => [[0, 0], [0, 5.6], [0.8, 6.4], [B - 3.2, 11.2], [B - 2.2, 11.8], [B - 0.8, 11.8], [B, 11.0], [B, 0]],
    },
    cushion: {
      name: 'Cushion', blurb: 'One soft, rounded dome across the width',
      fn(B) {
        const p = [[0, 0], [0, 7.0]];
        for (let i = 1; i <= 30; i++) {
          const t = i / 30;
          p.push([t * B, 7.0 - 0.4 * t + 4.2 * Math.sin(Math.PI * t) ** 0.7]);
        }
        p.push([B, 0]);
        return p;
      },
    },
    reeded: {
      name: 'Reeded', blurb: 'Flat face with parallel half-round reeds',
      fn(B) {
        const m = 1.2, base = 8.4, span = B - 2 * m;
        const n = Math.max(3, Math.round(span / 3.2)), r = span / (2 * n);
        let p = [[0, 0], [0, base - 0.4], [0.4, base], [m, base]];
        for (let i = 0; i < n; i++) p = p.concat(arc(m + r * (2 * i + 1), base, r, 180, 0, 10).slice(1));
        p.push([B - 0.4, base], [B, base - 0.4], [B, 0]);
        return p;
      },
    },
    stepped: {
      name: 'Stepped', blurb: 'Three terraces stepping down to the photo',
      fn(B) {
        const w1 = B * 0.3, w2 = B * 0.33;
        return [[0, 0], [0, 10.6], [0.8, 11.4], [w1 - 0.6, 11.4], [w1, 10.8], [w1, 9.6],
                [w1 + w2 - 0.6, 9.6], [w1 + w2, 9.0], [w1 + w2, 7.6], [B - 0.5, 7.6], [B, 7.1], [B, 0]];
      },
    },
  };

  function profile(border, style = 'classic') {
    return (STYLES[style] || STYLES.classic).fn(border);
  }

  // lowest point of the moulding's top surface between d0 and d1
  function minHeight(prof, d0, d1) {
    const top = prof.slice(1, -1);
    let lo = Infinity;
    const at = d => {
      let best = -Infinity;
      for (let i = 0; i < top.length - 1; i++) {
        const [a, za] = top[i], [b, zb] = top[i + 1];
        if (d < Math.min(a, b) || d > Math.max(a, b)) continue;
        best = Math.max(best, b === a ? Math.max(za, zb) : za + (zb - za) * (d - a) / (b - a));
      }
      return best;
    };
    for (let i = 0; i <= 40; i++) lo = Math.min(lo, at(d0 + (d1 - d0) * i / 40));
    for (const [d, z] of top) if (d >= d0 && d <= d1) lo = Math.min(lo, z);
    return lo;
  }

  function ring(d, W, H, k = 8) {
    const cx = W / 2 - d - CORNER_R, cy = H / 2 - d - CORNER_R;
    const pts = [];
    const corners = [[1, 1, 0], [-1, 1, 90], [-1, -1, 180], [1, -1, 270]];
    for (const [sx, sy, a0] of corners)
      for (let i = 0; i < k; i++) {
        const a = (a0 + 90 * i / (k - 1)) * Math.PI / 180;
        pts.push([sx * cx + CORNER_R * Math.cos(a), sy * cy + CORNER_R * Math.sin(a)]);
      }
    return pts;
  }

  function sweep(wasm, prof, W, H) {
    const rings = prof.map(([d, z]) => ring(d, W, H).map(([x, y]) => [x, y, z]));
    const N = rings[0].length, M = rings.length;
    const V = new Float32Array(N * M * 3);
    rings.flat().forEach((v, i) => V.set(v, i * 3));
    const F = [];
    for (let i = 0; i < M; i++) {
      const i2 = (i + 1) % M;
      for (let j = 0; j < N; j++) {
        const j2 = (j + 1) % N;
        const a = i * N + j, b = i * N + j2, c = i2 * N + j2, e = i2 * N + j;
        F.push(a, b, c, a, c, e);
      }
    }
    // orient outward
    let vol = 0;
    for (let t = 0; t < F.length; t += 3) {
      const [p, q, r] = [F[t], F[t + 1], F[t + 2]].map(i => V.subarray(i * 3, i * 3 + 3));
      vol += p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0]);
    }
    if (vol < 0) for (let t = 0; t < F.length; t += 3) { const s = F[t + 1]; F[t + 1] = F[t + 2]; F[t + 2] = s; }
    const mesh = new wasm.Mesh({numProp: 3, vertProperties: V, triVerts: new Uint32Array(F)});
    return new wasm.Manifold(mesh);
  }

  function rrect(wasm, w, h, r) {
    return wasm.CrossSection.square([w - 2 * r, h - 2 * r], true).offset(r, 'Round', 2, 64);
  }

  function stadium(wasm, x0, y0, x1, y1, r) {
    const {CrossSection} = wasm;
    return CrossSection.hull([CrossSection.circle(r, 48).translate([x0, y0]),
                              CrossSection.circle(r, 48).translate([x1, y1])]);
  }

  function frame(wasm, p, d) {
    const {Manifold} = wasm;
    let body = sweep(wasm, d.prof, d.outerW, d.outerH);

    // photo pocket from the back, 45 deg taper under the lip
    const rab = rrect(wasm, d.rabW, d.rabH, 1.5);
    body = body.subtract(rab.extrude(d.rabD + 1).translate([0, 0, -1]));
    body = body.subtract(rab.extrude(1.0, 0, 0, [(d.rabW - 2) / d.rabW, (d.rabH - 2) / d.rabH]).translate([0, 0, d.rabD]));

    // grooves for the back plate catches (left + right walls)
    const gl = Math.min(20, d.rabH * 0.25);
    const g = Manifold.cube([1.0, gl, 1.4]).translate([d.rabW / 2 - 0.1, -gl / 2, 0.9]);
    body = body.subtract(g).subtract(g.mirror([1, 0, 0]));

    // pry notch, bottom centre
    body = body.subtract(Manifold.cube([14, 1.7, 2.0]).translate([-7, -d.rabH / 2 - 1.6, -1]));

    // keyhole hanger in the top border
    let keyhole = false;
    if (p.keyhole) {
      const frameWallD = d.rabInset;                   // border depth on the back
      const travel = Math.max(0, Math.min(4.5, frameWallD - 3.5 - 1.5 - 3.5 - 2));
      const kd = frameWallD - 3.5 - 1.5;              // head centre, measured in from the top edge
      const deepEnough = minHeight(d.prof, Math.max(0.5, kd - travel - 3.5), kd + 3.5) >= 3.6 + 1.2;
      if (travel >= 2.5 && deepEnough) {
        const ky = d.outerH / 2 - (frameWallD - 3.5 - 1.5);   // head centre, 1.5 mm wall to the pocket
        const head = Manifold.cylinder(4.6, 3.5, 3.5, 48).translate([0, ky, -1]);
        const slot = stadium(wasm, 0, ky, 0, ky + travel, 1.8).extrude(2.6).translate([0, 0, -1]);
        const under = stadium(wasm, 0, ky, 0, ky + travel, 3.5).extrude(2.0).translate([0, 0, 1.6]);
        body = body.subtract(head.add(slot).add(under));
        keyhole = true;
      }
    }
    return {mesh: body, keyhole};
  }

  function backPlate(wasm, p, d) {
    const {Manifold, CrossSection} = wasm;
    const c = 0.2;
    const sw = d.rabW - 2 * c, sh = d.rabH - 2 * c, t = d.plateT;
    let plate = rrect(wasm, sw, sh, 1.3).extrude(t);
    const sl = Math.min(22, sh * 0.25);
    for (const s of [-1, 1]) {
      const slit = stadium(wasm, s * (sw / 2 - 2), -sl, s * (sw / 2 - 2), sl, 0.6);
      plate = plate.subtract(slit.extrude(t + 2).translate([0, 0, -1]));
    }
    const e = sw / 2, cl = Math.min(16, sh * 0.2);
    const prof = new CrossSection([[[e - 0.3, 0.9], [e + 0.6, 0.9], [e + 0.6, 1.2], [e, t], [e - 0.3, t]]]);
    const ctch = prof.extrude(cl).rotate([90, 0, 0]).translate([0, cl / 2, 0]);
    plate = plate.add(ctch).add(ctch.mirror([1, 0, 0]));
    return plate.rotate([180, 0, 0]).translate([0, 0, t]);   // print inner face down
  }

  function stand(wasm, p, d) {
    const {Manifold} = wasm;
    const L = Math.min(Math.max(d.outerW * 0.87, 60), 240), D = 46;
    const A = L * 0.635, B = 34, C = 15, lean = 12;
    const slotW = d.maxZ + 0.6;   // thickest part of the moulding + slack
    const slab = rrect(wasm, L, D, 14).extrude(C + 1);
    const hill = Manifold.sphere(1, 192).scale([A, B, C]).add(Manifold.cube([L, D, 2], true).translate([0, 0, 1]));
    let st = slab.intersect(hill);
    const slot = Manifold.cube([L + 10, slotW, 60]).translate([-(L + 10) / 2, -slotW / 2, 0]).rotate([-lean, 0, 0]);
    return st.subtract(slot.translate([0, 0, 4]));
  }

  function build(wasm, p) {
    const d = deriveDims(p);
    d.prof = profile(p.border, p.style);
    d.maxZ = Math.max(...d.prof.map(q => q[1]));
    const errors = validate(p, d, d.prof);
    if (errors.length) return {dims: d, errors};
    const out = {dims: d, errors: [], parts: {}};
    const f = frame(wasm, p, d);
    out.parts.frame = f.mesh;
    out.keyhole = f.keyhole;
    if (p.plate) out.parts.back_plate = backPlate(wasm, p, d);
    if (p.stand) out.parts.stand = stand(wasm, p, d);
    return out;
  }

  function toSTL(manifold, name) {
    const mesh = manifold.getMesh();
    const V = mesh.vertProperties, T = mesh.triVerts, np = mesh.numProp;
    const n = T.length / 3;
    const buf = new ArrayBuffer(84 + 50 * n);
    const dv = new DataView(buf);
    const hdr = ('frame-maker ' + name).slice(0, 80);
    for (let i = 0; i < hdr.length; i++) dv.setUint8(i, hdr.charCodeAt(i));
    dv.setUint32(80, n, true);
    let o = 84;
    for (let t = 0; t < n; t++) {
      const a = T[3 * t] * np, b = T[3 * t + 1] * np, c = T[3 * t + 2] * np;
      const ux = V[b] - V[a], uy = V[b + 1] - V[a + 1], uz = V[b + 2] - V[a + 2];
      const vx = V[c] - V[a], vy = V[c + 1] - V[a + 1], vz = V[c + 2] - V[a + 2];
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz) || 1;
      dv.setFloat32(o, nx / l, true); dv.setFloat32(o + 4, ny / l, true); dv.setFloat32(o + 8, nz / l, true);
      o += 12;
      for (const i of [a, b, c]) {
        dv.setFloat32(o, V[i], true); dv.setFloat32(o + 4, V[i + 1], true); dv.setFloat32(o + 8, V[i + 2], true);
        o += 12;
      }
      dv.setUint16(o, 0, true); o += 2;
    }
    return buf;
  }

  return {build, toSTL, deriveDims, profile, STYLES};
})();

if (typeof module !== 'undefined') module.exports = FrameGeom;
