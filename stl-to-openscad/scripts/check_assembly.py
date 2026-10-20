# /// script
# requires-python = ">=3.11"
# dependencies = ["manifold3d", "numpy", "trimesh"]
# ///
"""Check that exported parts (all in one assembly frame) fit together and fit the printer.

  uv run check_assembly.py out/tray.stl out/lid.stl ref/pcb.stl ref/battery.stl
  uv run check_assembly.py out/*.stl --bed 256x256x256 --bed 340x320x340
  uv run check_assembly.py out/*.stl --print out/tray.stl --print out/lid.stl  # bed-check only these

For every pair: overlap volume and where it is (FAIL), else the gap you could
move one part toward the other in ±x/±y/±z before they touch (up to --max-gap).
Parts in contact (gap 0, no overlap) are reported as touching, which is expected
for a lid on a rim or a board on a standoff. Exit code 1 on any overlap.
"""
import argparse
import itertools
import sys
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh


def load(path):
    tm = trimesh.load(path, force="mesh", process=True)
    m = mf.Manifold(mf.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                            tri_verts=np.asarray(tm.faces, np.uint32)))
    if m.status() != mf.Error.NoError or m.is_empty():
        sys.exit(f"{path}: not a closed manifold mesh ({m.status().name})")
    return m


def vol(m):
    return 0.0 if m.is_empty() else m.volume()


def bb(m):
    b = m.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def v3(v):
    return "[" + ", ".join(f"{x:.2f}" for x in v) + "]"


def boxes_near(a, b, margin):
    (alo, ahi), (blo, bhi) = bb(a), bb(b)
    return np.all(alo - margin <= bhi) and np.all(blo - margin <= ahi)


def gap(a, b, d, cmax, tol=0.01, eps=1e-3):
    """How far a can move along unit vector d before it overlaps b (cmax if never)."""
    d = np.asarray(d, float)
    if vol(a.translate(list(d * cmax)) ^ b) <= eps:
        return cmax  # may still collide further away; we only care about the near field
    lo, hi = 0.0, cmax
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if vol(a.translate(list(d * mid)) ^ b) > eps:
            hi = mid
        else:
            lo = mid
    return lo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl", type=Path, nargs="+")
    ap.add_argument("--max-gap", type=float, default=3.0, help="search clearances up to this (mm)")
    ap.add_argument("--min-gap", type=float, default=0.2,
                    help="warn when a sliding gap is above 0 but below this (mm)")
    ap.add_argument("--bed", action="append", default=[], help="build volume WxDxH, repeatable")
    ap.add_argument("--print", action="append", type=Path, default=[],
                    help="only these files are printed parts for the bed check (default: all)")
    a = ap.parse_args()

    parts = {p.stem: load(p) for p in a.stl}
    fails = warns = 0
    dirs = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0),
            "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}

    print("## pairs")
    for (na, A), (nb, B) in itertools.combinations(parts.items(), 2):
        if not boxes_near(A, B, a.max_gap):
            continue
        ov = A ^ B
        v = vol(ov)
        if v > 1e-3:
            fails += 1
            print(f"FAIL  {na} ∩ {nb}: {v:.2f} mm³ overlap")
            pieces = [m for m in ov.decompose() if vol(m) > 1e-3]
            for piece in sorted(pieces, key=lambda m: -vol(m))[:5]:
                lo, hi = bb(piece)
                print(f"        {vol(piece):8.2f} mm³ from {v3(lo)} to {v3(hi)}")
            continue
        gaps = {k: gap(A, B, d, a.max_gap) for k, d in dirs.items()}
        near = {k: g for k, g in gaps.items() if g < a.max_gap}
        if not near:
            continue
        touching = [k for k, g in near.items() if g < 0.01]
        tight = {k: g for k, g in near.items() if 0.01 <= g < a.min_gap}
        desc = "  ".join(f"{k} {g:.2f}" for k, g in sorted(near.items(), key=lambda t: t[1]))
        status = "WARN" if tight else "ok  "
        warns += bool(tight)
        note = f"  (touching {','.join(touching)})" if touching else ""
        print(f"{status}  {na} → {nb}: can move {desc} mm before contact{note}")

    beds = [tuple(float(x) for x in b.lower().split("x")) for b in a.bed]
    if beds:
        print("\n## bed fit (axis-aligned, either way round on the bed)")
        targets = a.print or a.stl
        for p in targets:
            lo, hi = bb(parts[p.stem])
            s = hi - lo
            fits = []
            for bw, bd, bh in beds:
                ok = s[2] <= bh and ((s[0] <= bw and s[1] <= bd) or (s[1] <= bw and s[0] <= bd))
                fits.append(f"{bw:g}×{bd:g}×{bh:g} {'✓' if ok else '✗'}")
            print(f"  {p.stem:30} {s[0]:.1f} × {s[1]:.1f} × {s[2]:.1f}   " + "   ".join(fits))

    print(f"\n{fails} FAIL, {warns} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
