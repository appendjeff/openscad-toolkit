# /// script
# requires-python = ">=3.11"
# dependencies = ["manifold3d", "numpy", "trimesh", "matplotlib"]
# ///
"""Measure an STL so it can be re-modelled in OpenSCAD.

  uv run stl_probe.py part.stl                      # summary + flat levels (Z) + auto slices
  uv run stl_probe.py part.stl --axis y             # levels/slices across Y (side features: ports, slots)
  uv run stl_probe.py part.stl --at 1.5,13.2        # slice at given heights only
  uv run stl_probe.py part.stl --png slices.png     # also draw the slices (read the PNG to look at them)

Coordinates are reported in the STL's own frame. For --axis x the 2D slice
axes are (y, z); for --axis y they are (z, x); for --axis z they are (x, y).
"""
import argparse
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

AXES = {"x": 0, "y": 1, "z": 2}
UV = {"x": ("y", "z"), "y": ("z", "x"), "z": ("x", "y")}
# cyclic permutations (det +1), so the slice axis becomes Z
PERM = {"z": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
        "x": [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]],
        "y": [[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]]}


def load(path):
    tm = trimesh.load(path, force="mesh", process=True)
    m = mf.Manifold(mf.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                            tri_verts=np.asarray(tm.faces, np.uint32)))
    return tm, m


def f(x, n=2):
    return f"{x:.{n}f}".rstrip("0").rstrip(".") if abs(x) >= 10 ** -n else "0"


def vec(v, n=2):
    return "[" + ", ".join(f(x, n) for x in v) + "]"


def summary(path, tm, m):
    lo, hi = tm.bounds
    size = hi - lo
    print(f"# {path.name}")
    print(f"triangles {len(tm.faces)}   watertight {tm.is_watertight}   "
          f"manifold status {m.status().name}")
    bodies = m.decompose() if not m.is_empty() else [m]
    print(f"bodies {len(bodies)}" + ("   (several parts in one file: split them before modelling)"
                                     if len(bodies) > 1 else ""))
    print(f"bbox min {vec(lo)}  max {vec(hi)}")
    print(f"size {vec(size)}   centre {vec((lo + hi) / 2)}")
    vol = m.volume() if not m.is_empty() else abs(tm.volume)
    print(f"volume {f(vol, 1)} mm³   surface {f(tm.area, 1)} mm²")
    big = size.max()
    if big < 15:
        print("UNITS? largest size < 15: may be inches (×25.4) or cm (×10)")
    elif big > 2000:
        print("UNITS? largest size > 2 m: may be µm or a scaled export")
    if np.all(np.abs((lo + hi) / 2) < 0.5 * size) and abs(lo[2]) < 0.01:
        print("frame: centred on XY origin, sitting on Z=0")
    elif np.allclose(lo, 0, atol=0.01):
        print("frame: corner at origin")
    else:
        print("frame: offset from origin (likely exported in an assembly frame: keep it)")
    print()


def levels(tm, axis, min_area):
    """Flat faces perpendicular to the axis, grouped by position."""
    a = AXES[axis]
    n = tm.face_normals[:, a]
    flat = np.abs(n) > 0.999
    pos = tm.triangles_center[flat, a]
    area = tm.area_faces[flat]
    sign = np.sign(n[flat])
    out = {}
    for p, ar, s in zip(np.round(pos, 3), area, sign):
        k = (p, int(s))
        out[k] = out.get(k, 0) + ar
    rows = sorted((k[0], k[1], v) for k, v in out.items() if v >= min_area)
    print(f"## flat faces ⟂ {axis} (area ≥ {min_area} mm²): '+' faces look toward +{axis}, '-' toward -{axis}")
    for p, s, ar in rows:
        print(f"  {axis}={f(p, 3):>9}  {'+' if s > 0 else '-'}  {f(ar, 1):>9} mm²")
    print()
    return sorted({r[0] for r in rows})


def ring_area(r):
    x, y = r[:, 0], r[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def inside(r, p):
    x, y = r[:, 0], r[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    c = ((y > p[1]) != (y2 > p[1])) & (p[0] < (x2 - x) * (p[1] - y) / (y2 - y + 1e-300) + x)
    return np.count_nonzero(c) % 2 == 1


def corners(r, tol=1e-4):
    """Drop collinear points (a slice crosses each facet's diagonal too)."""
    prev, nxt = np.roll(r, 1, axis=0), np.roll(r, -1, axis=0)
    e1, e2 = r - prev, nxt - r
    cross = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    scale = np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1) + 1e-12
    return r[cross / scale > tol]


def classify(r):
    """Best-guess primitive for a closed ring."""
    r = corners(r)
    lo, hi = r.min(0), r.max(0)
    w, h = hi - lo
    A = abs(ring_area(r))
    c = (lo + hi) / 2
    # circle: Kasa fit
    x, y = r[:, 0], r[:, 1]
    M = np.c_[2 * x, 2 * y, np.ones(len(x))]
    cx, cy, k = np.linalg.lstsq(M, x * x + y * y, rcond=None)[0]
    rad = np.sqrt(max(k + cx * cx + cy * cy, 0))
    err = np.max(np.abs(np.hypot(x - cx, y - cy) - rad)) if rad else 1e9
    if len(r) >= 8 and err < 0.02 + 0.01 * rad and abs(w - h) < 0.05 * max(w, h):
        return f"circle  d={f(2 * rad, 3)} at {vec([cx, cy], 3)}  ({len(r)} segments → $fn≈{len(r)})"
    fill = A / (w * h) if w * h else 0
    if fill > 0.995:
        return f"rect    {f(w, 3)} × {f(h, 3)} centred {vec(c, 3)}"
    if fill > 0.9:
        # rounded rect: missing corner area = (4 - π) r²
        rr = np.sqrt(max(w * h - A, 0) / (4 - np.pi))
        if rr < min(w, h) / 4:
            return f"rrect   {f(w, 3)} × {f(h, 3)} r≈{f(rr, 2)} centred {vec(c, 3)}"
    if abs(w - h) < 0.05 * max(w, h) and abs(A - np.pi * w * h / 4) < 0.03 * A:
        return f"circle? d≈{f(w, 3)} at {vec(c, 3)} (coarse, {len(r)} segments)"
    return f"poly    {len(r)} pts, bbox {f(w, 2)} × {f(h, 2)} from {vec(lo, 2)} to {vec(hi, 2)}, fill {f(fill, 2)}"


def do_slice(m, axis, at):
    mm = m.transform(PERM[axis])
    rings = [np.asarray(r, float) for r in mm.slice(at).to_polygons()]
    rows = []
    for i, r in enumerate(rings):
        depth = sum(inside(o, r[0]) for j, o in enumerate(rings) if j != i)
        rows.append((depth, r))
    rows.sort(key=lambda t: (t[0], -abs(ring_area(t[1]))))
    return rows


def shape_key(depth, r):
    lo, hi = r.min(0), r.max(0)
    return (depth % 2, len(corners(r)), *np.round(hi - lo, 2), round(abs(ring_area(r)), 1))


def pitch(vals):
    v = np.unique(np.round(vals, 3))
    if len(v) < 2:
        return f"{f(v[0], 3)}"
    d = np.diff(v)
    if np.allclose(d, d[0], atol=0.02):
        return f"{len(v)} × pitch {f(d[0], 3)} from {f(v[0], 3)} to {f(v[-1], 3)}"
    return "[" + ", ".join(f(x, 3) for x in v) + "]"


def print_slice(rows, axis, at, group_min=3):
    u, v = UV[axis]
    print(f"## slice {axis}={f(at, 3)}   2D axes ({u}, {v})   {len(rows)} rings")
    if not rows:
        print("  (empty)")
    groups = {}
    for depth, r in rows:
        groups.setdefault(shape_key(depth, r), []).append((depth, r))
    shown = set()
    for depth, r in rows:
        k = shape_key(depth, r)
        g = groups[k]
        kind = "solid" if depth % 2 == 0 else "hole "
        if len(g) >= group_min:
            if k in shown:
                continue
            shown.add(k)
            cs = np.array([(x.min(0) + x.max(0)) / 2 for _, x in g])
            print(f"  {'  ' * depth}{len(g)} × {kind} area {f(abs(ring_area(r)), 2):>9}  "
                  f"{classify(r).split(' centred')[0].split(' at ')[0]}")
            print(f"  {'  ' * depth}     {u}: {pitch(cs[:, 0])}")
            print(f"  {'  ' * depth}     {v}: {pitch(cs[:, 1])}")
        else:
            print(f"  {'  ' * depth}{kind} area {f(abs(ring_area(r)), 2):>9}  {classify(r)}")
    print()


def draw(slices, axis, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(slices)
    cols = min(n, 3)
    rws = (n + cols - 1) // cols
    ext = np.ptp(np.vstack([r for _, rows in slices for _, r in rows] or [np.zeros((2, 2))]), axis=0)
    aspect = np.clip(ext[1] / ext[0], 0.15, 3) if ext[0] else 1
    fig, axs = plt.subplots(rws, cols, figsize=(6 * cols, (6 * aspect + 1) * rws), squeeze=False)
    u, v = UV[axis]
    for ax, (at, rows) in zip(axs.flat, slices):
        for depth, r in rows:
            rr = np.vstack([r, r[:1]])
            ax.fill(rr[:, 0], rr[:, 1], color="white" if depth % 2 else "#9ab", zorder=depth)
            ax.plot(rr[:, 0], rr[:, 1], "k-", lw=0.6, zorder=depth)
        ax.set_title(f"{axis} = {f(at, 3)}")
        ax.set_xlabel(u)
        ax.set_ylabel(v)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.3)
    for ax in list(axs.flat)[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl", type=Path)
    ap.add_argument("--axis", choices="xyz", default="z")
    ap.add_argument("--at", help="comma-separated slice positions (default: midway between flat levels)")
    ap.add_argument("--min-area", type=float, default=1.0, help="ignore flat levels smaller than this (mm²)")
    ap.add_argument("--max-slices", type=int, default=12)
    ap.add_argument("--png", type=Path, help="draw the slices to this PNG")
    a = ap.parse_args()

    tm, m = load(a.stl)
    summary(a.stl, tm, m)
    if m.is_empty() or m.status() != mf.Error.NoError:
        sys.exit("mesh is not a closed manifold: repair it first (e.g. trimesh fill_holes, "
                 "or import() it in OpenSCAD and export), then probe again")
    lv = levels(tm, a.axis, a.min_area)
    lo, hi = tm.bounds[:, AXES[a.axis]]
    if a.at:
        ats = [float(s) for s in a.at.split(",")]
    else:
        edges = sorted({round(lo, 3), *lv, round(hi, 3)})
        ats = [(p + q) / 2 for p, q in zip(edges, edges[1:]) if q - p > 0.05]
        if len(ats) > a.max_slices:
            print(f"({len(ats)} bands; showing {a.max_slices} evenly spread. Use --at for the rest)\n")
            ats = [ats[i] for i in np.linspace(0, len(ats) - 1, a.max_slices).round().astype(int)]
    slices = []
    for at in ats:
        rows = do_slice(m, a.axis, at)
        print_slice(rows, a.axis, at)
        slices.append((at, rows))
    if a.png:
        draw(slices, a.axis, a.png)


if __name__ == "__main__":
    main()
