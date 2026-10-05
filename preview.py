"""Render shaded top-down previews of the STLs (z-buffer heightmap + hillshade)."""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))


def load_stl(path):
    with open(path, "rb") as fh:
        fh.seek(80)
        n = np.frombuffer(fh.read(4), "<u4")[0]
        dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        return np.frombuffer(fh.read(), dt, count=n)["v"].astype(np.float64)


def heightmap(tris, res=0.1, pad=2.0):
    lo = tris.reshape(-1, 3).min(0) - pad
    hi = tris.reshape(-1, 3).max(0) + pad
    W, H = int((hi[0] - lo[0]) / res), int((hi[1] - lo[1]) / res)
    Z = np.full((H, W), np.nan)
    p = (tris[:, :, :2] - lo[:2]) / res
    for t, z in zip(p, tris[:, :, 2]):
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = t
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not m.any():
            continue
        zz = l1 * z[0] + l2 * z[1] + l3 * z[2]
        sub = Z[y0:y1, x0:x1]
        cur = np.where(np.isnan(sub), -np.inf, sub)
        Z[y0:y1, x0:x1] = np.where(m & (zz > cur), zz, sub)
    return Z, lo, hi


def shade(Z, res, base_rgb, hi_rgb, split):
    z = np.nan_to_num(Z, nan=np.nanmin(Z))
    gy, gx = np.gradient(z, res)
    n = np.dstack([-gx, -gy, np.ones_like(z)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    light = np.array([-0.5, 0.6, 0.8]); light /= np.linalg.norm(light)
    lam = np.clip((n * light).sum(2), 0, 1)
    col = np.where((z > split)[..., None], hi_rgb, base_rgb)
    img = col * (0.25 + 0.75 * lam[..., None])
    img[np.isnan(Z)] = (0.96, 0.96, 0.97)
    return np.clip(img, 0, 1)


def render(name, out, split, res=0.1, flip=False):
    tris = load_stl(os.path.join(HERE, "stl", name))
    if flip:  # look at the underside
        tris = tris * np.array([1, 1, -1])
    Z, lo, hi = heightmap(tris, res)
    img = shade(Z, res, np.array([0.13, 0.16, 0.30]), np.array([0.95, 0.78, 0.35]), split)
    plt.imsave(out, img[::-1])
    print("wrote", out)


if __name__ == "__main__":
    pv = os.path.join(HERE, "preview")
    os.makedirs(pv, exist_ok=True)
    render("frame.stl", os.path.join(pv, "frame_front.png"), split=8.05)
    render("frame.stl", os.path.join(pv, "frame_back.png"), split=1e9, flip=True)
    render("back_plate.stl", os.path.join(pv, "back_plate.png"), split=1e9, flip=True)
    render("moon_stand.stl", os.path.join(pv, "moon_stand_top.png"), split=17.5)
