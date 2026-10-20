# /// script
# requires-python = ">=3.11"
# dependencies = ["manifold3d", "numpy", "trimesh", "matplotlib"]
# ///
"""Compare a rebuilt part against the original STL: volume, IoU and where they differ.

  uv run compare_stl.py original.stl rebuilt.scad              # renders the SCAD first
  uv run compare_stl.py original.stl rebuilt.scad -D side='"right"'
  uv run compare_stl.py left.stl right.stl --mirror x   # is B a mirror of A?
  uv run compare_stl.py original.stl rebuilt.stl --overlay z=13.5 --png overlay.png
  uv run compare_stl.py original.stl rebuilt.stl --xor-out diff.stl  # view the difference

Both parts must be in the same frame. Exit code 1 if IoU < --min-iou.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import manifold3d as mf
import numpy as np
import trimesh

PERM = {"z": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
        "x": [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]],
        "y": [[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]]}
UV = {"x": ("y", "z"), "y": ("z", "x"), "z": ("x", "y")}


def render(scad: Path, defines: list[str]) -> Path:
    out = Path(tempfile.mkdtemp()) / (scad.stem + ".stl")
    cmd = ["openscad", "--backend", "Manifold", "-o", str(out)]
    for d in defines:
        cmd += ["-D", d]
    p = subprocess.run(cmd + [str(scad)], capture_output=True, text=True)
    if p.returncode != 0 or not out.exists():
        sys.exit(f"openscad failed on {scad}:\n{p.stderr}")
    warn = [l for l in p.stderr.splitlines() if "WARNING" in l]
    for l in warn:
        print(l)
    return out


def load(path: Path) -> mf.Manifold:
    tm = trimesh.load(path, force="mesh", process=True)
    m = mf.Manifold(mf.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                            tri_verts=np.asarray(tm.faces, np.uint32)))
    if m.status() != mf.Error.NoError or m.is_empty():
        sys.exit(f"{path.name}: not a closed manifold mesh ({m.status().name})")
    return m


def vol(m):
    return 0.0 if m.is_empty() else m.volume()


def bb(m):
    b = m.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def v3(v):
    return "[" + ", ".join(f"{x:.2f}" for x in v) + "]"


def save(m: mf.Manifold, path: Path):
    mesh = m.to_mesh()
    trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts).export(path)
    print(f"wrote {path}")


def overlay(a, b, spec, png, names):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    axis, at = spec.split("=")
    at = float(at)
    fig, ax = plt.subplots(figsize=(10, 7))
    for m, color, name in ((a, "tab:blue", names[0]), (b, "tab:red", names[1])):
        for i, r in enumerate(m.transform(PERM[axis]).slice(at).to_polygons()):
            r = np.vstack([r, r[:1]])
            ax.plot(r[:, 0], r[:, 1], color=color, lw=0.8, label=name if i == 0 else None)
    u, v = UV[axis]
    ax.set_title(f"{axis} = {at}   blue: {names[0]}   red: {names[1]}")
    ax.set_xlabel(u)
    ax.set_ylabel(v)
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    print(f"wrote {png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original", type=Path)
    ap.add_argument("rebuilt", type=Path, help=".stl, or .scad to render with OpenSCAD")
    ap.add_argument("-D", action="append", default=[], help="OpenSCAD define for a .scad input")
    ap.add_argument("--mirror", choices="xyz", help="mirror the ORIGINAL across this axis' plane through 0")
    ap.add_argument("--min-iou", type=float, default=0.99)
    ap.add_argument("--min-region", type=float, default=0.5, help="ignore diff regions below this (mm³)")
    ap.add_argument("--top", type=int, default=12, help="list this many diff regions")
    ap.add_argument("--xor-out", type=Path, help="write the symmetric difference as an STL")
    ap.add_argument("--overlay", help="slice both at e.g. z=13.5 and draw outlines (needs --png)")
    ap.add_argument("--png", type=Path)
    a = ap.parse_args()

    rb = render(a.rebuilt, a.D) if a.rebuilt.suffix.lower() == ".scad" else a.rebuilt
    A, B = load(a.original), load(rb)
    if a.mirror:
        A = A.mirror([1 if a.mirror == ax else 0 for ax in "xyz"])

    va, vb = vol(A), vol(B)
    only_a, only_b = A - B, B - A
    inter = vol(A ^ B)
    union = va + vb - inter
    iou = inter / union if union else 0.0
    (alo, ahi), (blo, bhi) = bb(A), bb(B)

    print(f"original  {a.original.name}{' (mirrored ' + a.mirror + ')' if a.mirror else ''}")
    print(f"rebuilt   {a.rebuilt.name}")
    print(f"volume    original {va:.1f}   rebuilt {vb:.1f}   diff {vb - va:+.1f} mm³ ({(vb - va) / va * 100:+.3f} %)")
    print(f"missing   {vol(only_a):.1f} mm³ in original but not rebuilt")
    print(f"extra     {vol(only_b):.1f} mm³ in rebuilt but not original")
    print(f"IoU       {iou:.5f}   (threshold {a.min_iou})")
    print(f"bbox min  Δ {v3(blo - alo)}")
    print(f"bbox max  Δ {v3(bhi - ahi)}")
    if np.max(np.abs(np.r_[blo - alo, bhi - ahi])) > 1 and iou < 0.5:
        print("NOTE: the parts barely overlap. Different frames? Model in the original's frame "
              "(or try --mirror for a left/right pair).")

    regions = []
    for kind, m in (("missing", only_a), ("extra", only_b)):
        if not m.is_empty():
            for part in m.decompose():
                v = vol(part)
                if v >= a.min_region:
                    lo, hi = bb(part)
                    regions.append((v, kind, lo, hi))
    regions.sort(key=lambda r: -r[0])
    print(f"\ndiff regions ≥ {a.min_region} mm³: {len(regions)}")
    for v, kind, lo, hi in regions[:a.top]:
        print(f"  {kind:7} {v:9.2f} mm³   from {v3(lo)} to {v3(hi)}   size {v3(hi - lo)}")
    if len(regions) > a.top:
        print(f"  … {len(regions) - a.top} more (--top)")

    if a.xor_out:
        save(only_a + only_b, a.xor_out)
    if a.overlay:
        if not a.png:
            sys.exit("--overlay needs --png")
        overlay(A, B, a.overlay, a.png, (a.original.name, a.rebuilt.name))

    ok = iou >= a.min_iou
    print(f"\n{'PASS' if ok else 'FAIL'}: IoU {iou:.5f} {'≥' if ok else '<'} {a.min_iou}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
