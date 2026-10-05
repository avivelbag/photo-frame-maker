"""Classic moulded 120x120 mm photo frame for a Bambu P1S.

Generates:
  stl/frame.stl        the frame (print back face down)
  stl/back_plate.stl   snap-in back plate (print as oriented)
  stl/stand.stl        smooth desk stand

The frame is a moulding profile swept around the opening with mitred
corners, then the photo pocket, snap grooves and keyhole are cut from
the back. All dims in mm; back face on z=0.
"""
import math
import os

import numpy as np
from shapely.geometry import LineString, box
import manifold3d as mf
from manifold3d import CrossSection, FillRule, Manifold, Mesh

mf.set_circular_segments(64)

# ---------------------------------------------------------------- parameters
OUTER = 120.0          # outer size
WINDOW = 82.0          # visible photo opening
RABBET = 88.0          # pocket for photo + back plate
RABBET_D = 4.2         # straight pocket depth from back
LIP_TAPER = 1.0        # 45 deg underside taper on the lip
PLATE_T = 2.0          # back plate thickness
CLEAR = 0.2            # per-side fit clearance
CORNER_R = 0.8         # corner rounding along the mitre
# back-plate snap (frame coords). The groove is the original v1 groove, kept so new plates
# fit frames already printed. Catch: full-reach band SNAP_SHELF..SNAP_BAND, lead-in ramp above.
GROOVE_Z0, GROOVE_Z1, GROOVE_DEPTH = 0.9, 2.3, 0.9
SNAP_SHELF, SNAP_BAND = 0.95, 1.35
SNAP_REACH = 0.95      # past the plate edge = 0.75 mm past the pocket wall
EPS = 0.01

BORDER = (OUTER - WINDOW) / 2      # 19 mm of moulding

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


# ------------------------------------------------------------------- helpers
def rrect(w, h, r):
    return box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, quad_segs=16)


def to_cs(geom):
    polys = getattr(geom, "geoms", [geom])
    rings = []
    for p in polys:
        rings.append(np.asarray(p.exterior.coords)[:-1])
        rings += [np.asarray(h.coords)[:-1] for h in p.interiors]
    return CrossSection(rings, FillRule.EvenOdd)


def extrude(geom, h, z=0.0, scale_top=(1.0, 1.0)):
    return Manifold.extrude(to_cs(geom), h, scale_top=scale_top).translate((0, 0, z))


def arc(cx, cz, r, a0, a1, n=12):
    return [(cx + r * math.cos(math.radians(a)), cz + r * math.sin(math.radians(a)))
            for a in np.linspace(a0, a1, n)]


# -------------------------------------------------------------- the moulding
def profile():
    """Moulding cross-section as (d, z): d = distance in from the outer edge.
    Outer rounded bead -> sweeping cove -> fine inner bead -> bevelled sight edge."""
    p = [(0.0, 0.0), (0.0, 9.0)]
    p += arc(2.6, 9.0, 2.6, 180, 90, 14)[1:]                  # outer bead, up to z=11.6
    p += [(3.6, 11.6), (4.1, 11.0)]                           # flat + small step
    for t in np.linspace(0, 1, 18)[1:]:                       # cove, concave sweep down
        d = 4.1 + t * 7.0
        p.append((d, 8.8 + 2.2 * (1 - t) ** 2))
    p += [(12.0, 8.8)]
    p += arc(13.2, 8.8, 1.2, 180, 0, 14)[1:]                  # inner bead
    p += [(14.8, 8.1), (15.4, 8.1)]                           # step down to a fillet
    p += [(BORDER, 6.6), (BORDER, 0.0)]                       # bevelled sight edge, window wall
    return p


def ring(d, k=8):
    """Rounded-square contour inset d from the outer edge (same vertex count for any d)."""
    half = OUTER / 2 - d
    c = half - CORNER_R
    pts = []
    for (sx, sy), a0 in (((1, 1), 0), ((-1, 1), 90), ((-1, -1), 180), ((1, -1), 270)):
        for a in np.linspace(a0, a0 + 90, k):
            pts.append((sx * c + CORNER_R * math.cos(math.radians(a)),
                        sy * c + CORNER_R * math.sin(math.radians(a))))
    return np.array(pts)


def sweep(prof):
    rings = [np.column_stack([ring(d), np.full(32, z)]) for d, z in prof]
    N, M = len(rings[0]), len(rings)
    V = np.vstack(rings)
    F = []
    for i in range(M):
        i2 = (i + 1) % M
        for j in range(N):
            j2 = (j + 1) % N
            a, b, c, e = i * N + j, i * N + j2, i2 * N + j2, i2 * N + j
            F += [(a, b, c), (a, c, e)]
    F = np.array(F, dtype=np.uint32)
    t = V[F]
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6
    if vol < 0:
        F = F[:, ::-1].copy()
    return Manifold(Mesh(vert_properties=V.astype(np.float32), tri_verts=F))


def frame():
    body = sweep(profile())
    assert body.status() == mf.Error.NoError, body.status()

    # rabbet from the back, with a 45 deg taper under the lip
    rab = rrect(RABBET, RABBET, 1.5)
    body -= extrude(rab, RABBET_D + 1, -1)
    s = (RABBET - 2 * LIP_TAPER) / RABBET
    body -= extrude(rab, LIP_TAPER, RABBET_D, (s, s))

    # snap grooves for the back-plate catches (left + right walls)
    g = Manifold.cube((GROOVE_DEPTH + 0.1, 20, GROOVE_Z1 - GROOVE_Z0)).translate((RABBET / 2 - 0.1, -10, GROOVE_Z0))
    body -= g + g.mirror((1, 0, 0))

    # pry notch, bottom centre, to pop the back plate out
    body -= Manifold.cube((14, 1.7, 2.0)).translate((-7, -RABBET / 2 - 1.6, -1))

    # keyhole hanger in the top border (screw head up to 7 mm, shank up to 3.6 mm)
    ky = 49.0
    head = Manifold.cylinder(4.6, 3.5, 3.5, 48).translate((0, ky, -1))
    slot = extrude(LineString([(0, ky), (0, ky + 4.5)]).buffer(1.8), 2.6, -1)
    under = extrude(LineString([(0, ky), (0, ky + 4.5)]).buffer(3.5), 2.0, 1.6)
    return body - (head + slot + under)


# --------------------------------------------------------------- back plate
def back_plate():
    """Modelled in frame coords (outer face z=0, inner face z=PLATE_T), then flipped
    so it prints inner-face-down and the catch ramps need no support."""
    side = RABBET - 2 * CLEAR
    plate = extrude(rrect(side, side, 1.3), PLATE_T)
    # slits turn each side edge into a 2 mm beam, fixed at both ends, that flexes inward
    for s in (-1, 1):
        x = s * (side / 2 - 2.0 - 0.7)
        plate -= extrude(LineString([(x, -22), (x, 22)]).buffer(0.7), PLATE_T + 2, -1)
    e = side / 2
    from shapely.geometry import Polygon
    prof = Polygon([(e - 0.3, SNAP_SHELF), (e + SNAP_REACH, SNAP_SHELF), (e + SNAP_REACH, SNAP_BAND),
                    (e, PLATE_T), (e - 0.3, PLATE_T)])
    catch = Manifold.extrude(to_cs(prof), 16).rotate((90, 0, 0)).translate((0, 8, 0))
    plate += catch + catch.mirror((1, 0, 0))
    return plate.rotate((180, 0, 0)).translate((0, 0, PLATE_T))


# ------------------------------------------------------------------- stand
def stand():
    """Smooth pebble-like base with a slot that leans the frame back 12 deg."""
    L, D = 104.0, 46.0
    A, B, C = 66.0, 34.0, 15.0
    lean = 12.0
    slot_w = 11.6 + 0.6                 # thickest part of the moulding + slack
    slab = extrude(rrect(L, D, 14), C + 1)
    hill = Manifold.sphere(1.0, 192).scale((A, B, C))
    st = slab ^ (hill + Manifold.cube((L, D, 2.0), center=True).translate((0, 0, 1.0)))
    slot = Manifold.cube((L + 10, slot_w, 60)).translate((-(L + 10) / 2, -slot_w / 2, 0)).rotate((-lean, 0, 0))
    return st - slot.translate((0, 0, 4.0))


# ------------------------------------------------------------------- export
def save(m, name):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    f = np.asarray(mesh.tri_verts)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec = np.zeros(len(f), dt)
    rec["n"], rec["v"] = n, tri
    with open(os.path.join(OUT_DIR, name), "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b" "))
        fh.write(np.uint32(len(f)).tobytes())
        fh.write(rec.tobytes())
    bb = m.bounding_box()
    print(f"{name:16s} {len(f):7d} tris  {bb[3]-bb[0]:6.1f} x {bb[4]-bb[1]:6.1f} x {bb[5]-bb[2]:5.1f} mm  "
          f"vol {m.volume()/1000:5.1f} cm3  parts {len(m.decompose())}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    save(frame(), "frame.stl")
    save(back_plate(), "back_plate.stl")
    save(stand(), "stand.stl")
