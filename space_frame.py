"""Space-themed 120x120 mm photo frame for a Bambu P1S.

Generates:
  stl/frame.stl          frame body + relief as one mesh
  stl/frame_body.stl     frame body only     } load both at once in Bambu Studio
  stl/frame_relief.stl   raised artwork only } as one object -> two colours
  stl/back_plate.stl     snap-in back plate (print as oriented)
  stl/moon_stand.stl     lunar-surface desk stand

All dims in mm. Frame coords: back face on z=0, front face at z=BODY_T,
artwork rises above that. Print the frame back-down, no supports.
"""
import math
import os
import random

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
import manifold3d as mf
from manifold3d import CrossSection, FillRule, JoinType, Manifold

mf.set_circular_segments(64)

# ---------------------------------------------------------------- parameters
OUTER = 120.0          # outer size
OUTER_R = 6.0          # outer corner radius
BODY_T = 8.0           # frame body thickness
EDGE_CHAMFER = 1.0     # chamfer on the front outer edge
WINDOW = 82.0          # visible photo opening
WINDOW_CHAMFER = 2.0   # per side, on the front face
RABBET = 88.0          # pocket for photo + back plate
RABBET_D = 4.2         # straight pocket depth from back
LIP_TAPER = 1.0        # 45 deg underside taper on the lip (cuts overhang to 2 mm)
PLATE_T = 2.0          # back plate thickness
CLEAR = 0.2            # per-side fit clearance
RELIEF = 1.2           # base artwork height above front face
EPS = 0.01

Z0 = BODY_T            # artwork starts here

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


# ------------------------------------------------------------------- helpers
def rrect(w, h, r):
    return box(-w / 2 + r, -h / 2 + r, w / 2 - r, h / 2 - r).buffer(r, quad_segs=16)


def to_cs(geom):
    """shapely (Multi)Polygon -> CrossSection."""
    if geom.is_empty:
        return CrossSection()
    polys = getattr(geom, "geoms", [geom])
    rings = []
    for p in polys:
        if p.is_empty or p.area < 1e-6:
            continue
        rings.append(np.asarray(p.exterior.coords)[:-1])
        for hole in p.interiors:
            rings.append(np.asarray(hole.coords)[:-1])
    return CrossSection(rings, FillRule.EvenOdd)


def extrude(geom, h, z=0.0, scale_top=(1.0, 1.0)):
    return Manifold.extrude(to_cs(geom), h, scale_top=scale_top).translate((0, 0, z))


def pyramid_star(x, y, R, h, points=4, inner=0.3, rot=0.0):
    """Faceted sparkle star: star outline extruded to a point."""
    pts = []
    for i in range(points * 2):
        a = math.radians(rot) + math.pi * i / points
        rr = R if i % 2 == 0 else R * inner
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    m = Manifold.extrude(to_cs(Polygon(pts)), h, scale_top=(0.0, 0.0))
    return m.translate((x, y, Z0))


def dome(geom, cx, cy, radius, h):
    """Extrude geom and trim it with a spherical cap of base radius `radius`, height h."""
    R = (radius ** 2 + h ** 2) / (2 * h)
    sph = Manifold.sphere(R, max(24, min(96, int(R * 8)))).translate((cx, cy, Z0 + h - R))
    return extrude(geom, h + EPS, Z0) ^ sph


def dot(x, y, r, h):
    return dome(Point(x, y).buffer(r, quad_segs=12), x, y, r, h)


def text_geom(s, size, cx, cy, tracking=0.0, weight="bold", family="DejaVu Sans"):
    fp = FontProperties(family=family, weight=weight)
    glyphs, x = [], 0.0
    for ch in s:
        if ch == " ":
            x += size * 0.45 + tracking
            continue
        tp = TextPath((0, 0), ch, size=size, prop=fp)
        polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
        # even-odd compose glyph contours (handles holes in A, R ...)
        g = Polygon()
        for p in polys:
            g = g.symmetric_difference(p.buffer(0))
        bx = tp.get_extents()
        glyphs.append(affinity.translate(g, x - bx.x0, 0))
        x += bx.width + tracking
    g = unary_union(glyphs)
    minx, miny, maxx, maxy = g.bounds
    return affinity.translate(g, cx - (minx + maxx) / 2, cy - (miny + maxy) / 2)


# ---------------------------------------------------------- 2D layout regions
outer_2d = rrect(OUTER, OUTER, OUTER_R)
win_top = WINDOW + 2 * WINDOW_CHAMFER
art_zone = rrect(OUTER - 2 * (EDGE_CHAMFER + 1.5), OUTER - 2 * (EDGE_CHAMFER + 1.5), OUTER_R - 2)
art_zone = art_zone.difference(rrect(win_top + 1.0, win_top + 1.0, 3.0))


# ------------------------------------------------------------------- frame
def frame_body():
    top_s = (OUTER - 2 * EDGE_CHAMFER) / OUTER
    body = extrude(outer_2d, BODY_T - EDGE_CHAMFER)
    body += extrude(outer_2d, EDGE_CHAMFER, BODY_T - EDGE_CHAMFER, (top_s, top_s))

    # photo window: straight bore + chamfer flaring out at the front
    win = rrect(WINDOW, WINDOW, 2.0)
    body -= extrude(win, BODY_T + 2, -1)
    s = win_top / WINDOW
    body -= extrude(win, WINDOW_CHAMFER + EPS, BODY_T - WINDOW_CHAMFER, (s, s))

    # rabbet from the back, with a 45 deg taper under the lip
    rab = rrect(RABBET, RABBET, 1.5)
    body -= extrude(rab, RABBET_D + 1, -1)
    s = (RABBET - 2 * LIP_TAPER) / RABBET
    body -= extrude(rab, LIP_TAPER, RABBET_D, (s, s))

    # snap grooves for the back-plate catches (left + right walls)
    for sx in (-1, 1):
        g = Manifold.cube((0.9 + 0.1, 20, 1.4)).translate((RABBET / 2 - 0.1, -10, 0.9))
        body -= g if sx > 0 else g.mirror((1, 0, 0))

    # pry notch, bottom centre, to pop the back plate out
    body -= Manifold.cube((14, 1.6 + 0.1, 1.0 + 1)).translate((-7, -RABBET / 2 - 1.6, -1))

    # keyhole hanger in the top border (screw head 7 mm, shank 3.6 mm)
    ky = 49.0
    head = Manifold.cylinder(3.6 + 1, 3.5, 3.5, 48).translate((0, ky, -1))
    slot = extrude(LineString([(0, ky), (0, ky + 4.5)]).buffer(1.8), 1.6 + 1, -1)
    under = extrude(LineString([(0, ky), (0, ky + 4.5)]).buffer(3.5), 2.0, 1.6)
    body -= head + slot + under
    return body


def frame_relief():
    parts = []
    keepout = []

    # window rim line
    rim = rrect(win_top + 3.4, win_top + 3.4, 4.2).difference(rrect(win_top + 2.0, win_top + 2.0, 3.5))
    parts.append(extrude(rim, 0.6, Z0))
    keepout.append(rim)

    # --- Saturn, top-right corner
    sx, sy, sr = 49.0, 49.0, 7.0
    tilt = -45   # ring runs corner-to-corner so it stays inside the border
    planet = Point(sx, sy).buffer(sr, quad_segs=32)
    sat = dome(planet, sx, sy, sr, 2.8)
    for off in (-2.0, 2.2):   # cloud bands, cut only into the upper dome
        band = affinity.rotate(box(sx - 12, sy + off - 0.3, sx + 12, sy + off + 0.3), tilt, (sx, sy))
        sat -= extrude(band, 3, Z0 + 1.1)
    ell = lambda a, b: affinity.rotate(
        affinity.scale(Point(sx, sy).buffer(1, quad_segs=48), a, b, origin=(sx, sy)), tilt, (sx, sy))
    ring = ell(11.6, 3.3).difference(ell(9.2, 2.2))
    front = affinity.rotate(box(sx - 30, sy - 30, sx + 30, sy), tilt, (sx, sy))
    ring_back = ring.difference(planet)
    ring_front = ring.intersection(front).intersection(planet)
    parts += [sat, extrude(ring_back, 1.3, Z0), extrude(ring_front, 3.3, Z0)]
    keepout.append(planet.union(ring))

    # --- little cratered world with an orbiting moon, top-left corner
    ex, ey, er = -50.0, 50.0, 5.0
    world_g = Point(ex, ey).buffer(er, quad_segs=32)
    world = dome(world_g, ex, ey, er, 2.2)
    for cx, cy, cr in ((-51.5, 51.2, 1.2), (-48.3, 48.4, 0.9), (-49.0, 52.6, 0.6)):
        world -= Manifold.sphere(cr, 24).translate((cx, cy, Z0 + 2.2 + cr * 0.35))
    orbit = affinity.rotate(
        affinity.scale(Point(ex, ey).buffer(1, quad_segs=48), 9.0, 4.2, origin=(ex, ey)), 20, (ex, ey))
    orbit_line = orbit.exterior.buffer(0.35).difference(world_g.buffer(0.6))
    mx, my = ex + 9.0 * math.cos(math.radians(200)), ey + 4.2 * math.sin(math.radians(200))
    mx, my = affinity.rotate(Point(mx, my), 20, (ex, ey)).coords[0]
    parts += [world, extrude(orbit_line.difference(Point(mx, my).buffer(1.9)), 0.5, Z0), dot(mx, my, 1.3, 1.2)]
    keepout.append(orbit.union(world_g))

    # --- crescent moon, bottom-left corner
    cx, cy, cr = -50.0, -50.0, 6.5
    cres = Point(cx, cy).buffer(cr, quad_segs=32).difference(Point(cx + 2.4, cy + 1.8).buffer(5.7, quad_segs=32))
    parts.append(dome(cres, cx, cy, cr, 2.2))
    keepout.append(Point(cx, cy).buffer(cr))

    # --- rocket + exhaust trail, bottom border
    rx, ry, rang = 30.0, -51.0, 8.0
    body_pts = [(-6.5, -2.4), (2.0, -2.4), (4.5, -1.9), (6.6, -1.0), (7.8, 0.0),
                (6.6, 1.0), (4.5, 1.9), (2.0, 2.4), (-6.5, 2.4)]
    fins = unary_union([
        Polygon([(-6.8, 2.0), (-2.5, 2.0), (-7.6, 5.4), (-8.6, 5.4)]),
        Polygon([(-6.8, -2.0), (-2.5, -2.0), (-7.6, -5.4), (-8.6, -5.4)]),
    ])
    nozzle = Polygon([(-6.4, -1.5), (-6.4, 1.5), (-8.3, 2.1), (-8.3, -2.1)])
    place = lambda g: affinity.translate(affinity.rotate(g, rang, (0, 0)), rx, ry)
    rbody, rfins, rnoz = place(Polygon(body_pts)), place(fins), place(nozzle)
    port = place(Point(1.2, 0).buffer(1.2, quad_segs=16))
    rocket = extrude(rbody, 1.6, Z0) + extrude(rfins, 1.0, Z0) + extrude(rnoz, 1.2, Z0)
    rocket -= extrude(port, 1.0, Z0 + 0.8)
    rocket -= extrude(place(box(-4.6, -2.6, -4.2, 2.6)), 1.0, Z0 + 1.2)  # body seam
    parts.append(rocket)
    keepout.append(unary_union([rbody, rfins, rnoz]))
    flame = place(Polygon([(-8.3, -1.7), (-11.0, -1.1), (-15.5, 0.0), (-11.0, 1.1), (-8.3, 1.7)]))
    parts.append(extrude(flame, 0.9, Z0))
    keepout.append(flame)
    trng = random.Random(11)
    x, trail = rx - 17.5, []
    for i in range(10):   # exhaust puffs thinning out behind the rocket
        r = 1.35 - i * 0.09
        y = ry - 2.3 + trng.uniform(-1.6, 1.6)
        trail.append((x, y, r))
        x -= 2.6 + i * 0.75 + trng.uniform(0, 1.0)
    for x, y, r in trail:
        parts.append(dot(x, y, r, 0.5 + r * 0.6))
    keepout.append(LineString([(rx - 9, ry)] + [(x, y) for x, y, _ in trail]).buffer(2.6))

    # --- comet streaking up the left border
    hx, hy = -50.5, 6.0
    ang = math.radians(97)
    ux, uy = math.cos(ang), math.sin(ang)
    px, py = -uy, ux
    tails = []
    for off, length, w in ((0.0, 27.0, 1.5), (1.9, 19.0, 0.9), (-1.9, 15.0, 0.8)):
        bx, by = hx + px * off * 0.4, hy + py * off * 0.4
        tails.append(Polygon([
            (bx + px * w, by + py * w),
            (bx + ux * length + px * off, by + uy * length + py * off),
            (bx - px * w, by - py * w)]))
    tail_g = unary_union(tails)
    parts.append(extrude(tail_g, 0.7, Z0))
    parts.append(pyramid_star(hx, hy, 3.6, 1.8, inner=0.32, rot=45))
    parts.append(dot(hx, hy, 1.9, 1.8))
    keepout.append(tail_g.union(Point(hx, hy).buffer(3.6)))

    # --- Orion, right border
    ox, oy, sc, scx = 51.0, -8.0, 2.15, 1.4
    stars = {
        "betelgeuse": (-3.0, 4.2, 1.15), "bellatrix": (2.6, 3.6, 0.85), "meissa": (0.0, 5.7, 0.6),
        "alnitak": (-0.9, -0.55, 0.75), "alnilam": (0.0, 0.0, 0.75), "mintaka": (0.9, 0.55, 0.7),
        "saiph": (-2.5, -4.6, 0.85), "rigel": (3.0, -4.0, 1.15)}
    P = {k: (ox + v[0] * scx, oy + v[1] * sc) for k, v in stars.items()}
    links = [("meissa", "betelgeuse"), ("meissa", "bellatrix"), ("betelgeuse", "alnitak"),
             ("bellatrix", "mintaka"), ("alnitak", "alnilam"), ("alnilam", "mintaka"),
             ("alnitak", "saiph"), ("mintaka", "rigel")]
    lines = unary_union([LineString([P[a], P[b]]).buffer(0.32) for a, b in links])
    parts.append(extrude(lines, 0.45, Z0))
    for k, (x, y) in P.items():
        r = stars[k][2]
        if r > 1.0:
            parts.append(pyramid_star(x, y, r * 1.9, 1.6, inner=0.3))
        parts.append(dot(x, y, r, 1.0 + r * 0.6))
    keepout.append(unary_union([lines] + [Point(p).buffer(2.8) for p in P.values()]))

    # --- AD ASTRA, top border
    txt = text_geom("AD ASTRA", 5.6, -8.0, 50.5, tracking=1.6)
    parts.append(extrude(txt, 1.0, Z0))
    keepout.append(txt.envelope)

    # --- scattered starfield (Poisson-disc in what's left of the border)
    free = art_zone.difference(unary_union(keepout).buffer(1.6))
    rng = random.Random(7)
    minx, miny, maxx, maxy = free.bounds
    placed = []
    for _ in range(6000):
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        big = rng.random() < 0.22
        r = rng.uniform(2.2, 3.2) if big else rng.uniform(0.55, 0.95)
        if not free.contains(Point(x, y).buffer(r * (0.7 if big else 1.0))):
            continue
        if any(math.hypot(x - a, y - b) < (r + c) * 1.25 + 1.8 for a, b, c in placed):
            continue
        placed.append((x, y, r))
        if big:
            parts.append(pyramid_star(x, y, r, 1.4, inner=0.28, rot=rng.choice((0, 45, 15))))
        else:
            parts.append(dot(x, y, r, 0.5 + r * 0.6))

    relief = Manifold.batch_boolean(parts, mf.OpType.Add)
    clip = extrude(art_zone.union(rim).union(rrect(OUTER - 2 * EDGE_CHAMFER - 1, OUTER - 2 * EDGE_CHAMFER - 1, OUTER_R - 1.5)
                                         .difference(rrect(win_top + 0.6, win_top + 0.6, 3.0))), 10, Z0)
    return relief ^ clip, len(placed)


# --------------------------------------------------------------- back plate
def back_plate():
    """Modelled in frame coords (outer face z=0, inner face z=PLATE_T).
    Flipped on export so it prints inner-face-down: the catch ramps then need no support."""
    side = RABBET - 2 * CLEAR
    plate = extrude(rrect(side, side, 1.3), PLATE_T)
    # slits make each edge a flexible beam (fixed both ends) carrying a catch
    for s in (-1, 1):
        slit = LineString([(s * (side / 2 - 2.0), -22), (s * (side / 2 - 2.0), 22)]).buffer(0.6)
        plate -= extrude(slit, PLATE_T + 2, -1)
    # catch profile in (x, z): ramp from 0 at z=PLATE_T up to 0.6 mm at z=1.2, flat to z=0.9
    e = side / 2
    prof = Polygon([(e - 0.3, 0.9), (e + 0.6, 0.9), (e + 0.6, 1.2), (e, PLATE_T), (e - 0.3, PLATE_T)])
    catch = Manifold.extrude(to_cs(prof), 16).rotate((90, 0, 0)).translate((0, 8, 0))
    plate += catch + catch.mirror((1, 0, 0))
    # engraving on the outside face
    plate -= extrude(text_geom("PER ASPERA", 6.0, 0, 6, tracking=1.2), 0.5, -EPS)
    plate -= extrude(text_geom("AD ASTRA", 4.0, 0, -4, tracking=1.0, weight="normal"), 0.5, -EPS)
    # orbit ring engraving around the text
    orb = affinity.scale(Point(0, 1).buffer(1, quad_segs=64), 34, 14)
    plate -= extrude(orb.exterior.buffer(0.4).difference(box(-30, -6.5, 30, 10)), 0.5, -EPS)
    plate -= extrude(Point(34 * math.cos(math.radians(-35)), 1 + 14 * math.sin(math.radians(-35))).buffer(1.4), 0.5, -EPS)
    return plate.rotate((180, 0, 0)).translate((0, 0, PLATE_T))


# ---------------------------------------------------------------- moon stand
def moon_stand():
    """A slice of lunar hill: domed, cratered slab with a tilted slot for the frame."""
    L, D = 104.0, 48.0
    A, B, C = 66.0, 36.0, 15.0          # ellipsoid semi-axes for the dome
    lean = 12.0                         # frame leans back by this much
    slot_w = BODY_T + 2.2 + 0.8         # body + tallest bottom-border artwork (moon) + slack
    slot_floor = 4.0
    rng = random.Random(5)

    surf = lambda x, y: C * math.sqrt(max(0.0, 1 - (x / A) ** 2 - (y / B) ** 2))
    slab = extrude(rrect(L, D, 14), C + 1)
    hill = Manifold.sphere(1.0, 192).scale((A, B, C))
    stand = slab ^ (hill + Manifold.cube((L, D, 2.0), center=True).translate((0, 0, 1.0)))

    # craters: bowl + raised rim, kept clear of the slot and the edges
    craters = []
    for _ in range(3000):
        x, y = rng.uniform(-L / 2 + 6, L / 2 - 6), rng.uniform(-D / 2 + 5, D / 2 - 5)
        r = rng.uniform(1.6, 4.6) if rng.random() < 0.5 else rng.uniform(0.9, 1.6)
        if abs(y) < slot_w / 2 + 3.5 + r or abs(x) > L / 2 - 7 - r or abs(y) > D / 2 - 4.5 - r:
            continue
        if surf(x, y) < 6:
            continue
        if any(math.hypot(x - a, y - b) < r + c + 1.0 for a, b, c in craters):
            continue
        craters.append((x, y, r))
        if len(craters) >= 26:
            break
    for x, y, r in craters:
        z = surf(x, y)
        stand += Manifold.cylinder(1.0 + 0.15 * r, r + 0.4 + 0.15 * r, r - 0.1, 48).translate((x, y, z - 0.6))
        stand -= Manifold.sphere(1.0, 48).scale((r * 1.05, r * 1.05, r * 0.45)).translate((x, y, z + 0.3 + 0.1 * r))

    # tilted slot (open at both ends) for the frame's bottom edge
    slot = Manifold.cube((L + 10, slot_w, 60)).translate((-(L + 10) / 2, -slot_w / 2, 0)).rotate((-lean, 0, 0))
    stand -= slot.translate((0, 0, slot_floor))

    # a tiny flag planted on the hill
    fx, fy = L / 2 - 16, -13.0     # front side, so it peeks out beside the frame
    fz = surf(fx, fy) - 1.0
    stand += Manifold.cylinder(15, 0.8, 0.8, 24).translate((fx, fy, fz))
    # pennant with a 45 deg underside so it prints without support
    pennant = Polygon([(0, 7.0), (7.5, 14.5), (0, 14.5)])
    stand += Manifold.extrude(to_cs(pennant), 1.2).rotate((90, 0, 0)).translate((fx + 0.4, fy + 0.6, fz))
    return stand


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
    path = os.path.join(OUT_DIR, name)
    with open(path, "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b" "))
        fh.write(np.uint32(len(f)).tobytes())
        fh.write(rec.tobytes())
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    print(f"{name:20s} {len(f):7d} tris  {hi[0]-lo[0]:6.1f} x {hi[1]-lo[1]:6.1f} x {hi[2]-lo[2]:5.1f} mm  "
          f"vol {m.volume()/1000:6.1f} cm3  genus {m.genus()}")
    return m


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    body = frame_body()
    relief, n_stars = frame_relief()
    relief -= body.trim_by_plane((0, 0, -1), -Z0)   # no overlap, parts just touch at z=Z0
    save(body, "frame_body.stl")
    save(relief, "frame_relief.stl")
    save(body + relief, "frame.stl")
    save(back_plate(), "back_plate.stl")
    save(moon_stand(), "moon_stand.stl")
    print(f"starfield: {n_stars} stars")
