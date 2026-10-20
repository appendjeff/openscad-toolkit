# stl-to-openscad: a Claude skill

Turns STL files into **parametric OpenSCAD** that you can edit. It's written mainly for open-source electronics projects (keyboards, handheld gadgets, ESP32/Arduino/Raspberry Pi builds) that publish only STLs for their cases, but it works on any STL.

With the skill installed, ask Claude something like:

> Clone https://github.com/someone/cool-gadget and turn the case STLs into OpenSCAD. I want to fit a 3.5" display instead of the 2.8" one.

Claude then works through the same steps every time:
1. checks the project's license and looks for original CAD files,
2. measures each STL with cross-sections,
3. rebuilds each part in OpenSCAD with named parameters,
4. **proves** the rebuild matches the original, with a boolean diff (volume difference and IoU),
5. only then makes your changes, and checks that the parts still fit together and fit the printer.

The full method is in [`SKILL.md`](SKILL.md).

## Who this is for

- **Makers** who want to change a printed part from someone else's project: swap a component, use the screws they have, or fit it to their printer. You should be comfortable 3D printing and willing to run a few terminal commands. You don't need to know OpenSCAD or Python: Claude writes and runs both, and explains what it finds.
- **People who already write OpenSCAD** and want a repeatable, verified way to get from a mesh to clean source. The scripts in `scripts/` are useful on their own, without Claude (see [Using the scripts by hand](#using-the-scripts-by-hand)).

It's **not** for organic or sculpted models (figurines, scanned objects). Those can't be rebuilt from simple shapes in a useful way. It works best on boxy, mechanical parts: enclosures, plates, trays, brackets, mounts.

## Setup

This skill is one of a set of four OpenSCAD skills. Installing, dependencies and a quick check for all of them are in the [skills README](../README.md).

Specific to this skill:
- It needs **[uv](https://docs.astral.sh/uv/)** and **git** as well as OpenSCAD.
- It works on its own, but goes faster with the companion `openscad`, `preview-scad` and `export-stl` skills installed in the same skills folder.
- The scripts declare their Python dependencies at the top (a `# /// script` block). uv installs them into a cached, private environment on the first run (about 100 MB), so you never install Python packages yourself:

| Python package | Used for |
|---|---|
| `manifold3d` | Boolean operations, volumes and cross-sections of meshes |
| `trimesh` | Loading STL files, finding flat faces |
| `numpy` | Geometry maths |
| `matplotlib` | Drawing cross-sections and overlays to PNG |

## Using the scripts by hand

The scripts work without Claude. Run them from anywhere; `SKILL` below is the path to this folder.

```
SKILL=~/.claude/skills/stl-to-openscad     # or wherever you installed it

# What is this STL? Size, units, frame, flat heights, cross-sections (+ a picture)
uv run $SKILL/scripts/stl_probe.py part.stl --png part_sections.png
uv run $SKILL/scripts/stl_probe.py part.stl --axis y --at 33   # slice across a wall to find ports

# Does my rebuild match the original? (renders the .scad for you)
uv run $SKILL/scripts/compare_stl.py original.stl part_001.scad
uv run $SKILL/scripts/compare_stl.py original.stl part_001.scad --overlay z=13.5 --png overlay.png
uv run $SKILL/scripts/compare_stl.py left.stl right.stl --mirror x     # are these a mirror pair?

# Do the parts fit together, and on which printers?
uv run $SKILL/scripts/check_assembly.py out/*.stl --bed 256x256x256 --bed 350x350x350   # your printers' build volumes
```

Add `--help` to any of them for every option. `compare_stl.py` and `check_assembly.py` exit with code 1 on a failure, so they can be used in scripts.

## Files

```
stl-to-openscad/
  README.md                          this file (for people)
  SKILL.md                           the workflow (for Claude)
  references/electronics-enclosures.md
                                     component models, screws and inserts, FDM tolerances,
                                     component swaps, fit checks, test coupons
  scripts/stl_probe.py               measure an STL
  scripts/compare_stl.py             original vs rebuild: volume, IoU, where they differ
  scripts/check_assembly.py          overlaps, clearances, bed fit
```

## Troubleshooting

For install problems (OpenSCAD not found or too old), see the [skills README](../README.md#troubleshooting).

- **`not a closed manifold mesh`:** the original STL has holes or broken triangles. Ask Claude to repair it first, or open it in OpenSCAD (`import("part.stl");`), render (F6) and export it again.
- **The first `uv run` is slow or fails offline:** uv needs the internet once to download the Python packages. After that it works offline.
- **The parts "barely overlap" in `compare_stl.py`:** the original and the rebuild aren't in the same coordinate frame. Model the rebuild in the original STL's frame, or check whether the part is the mirror of the one you compared it to.

## Credit and licenses

Projects you remix keep their own licenses. Many open hardware projects are CC BY-NC-SA, which means you must credit the author, share your remix under the same license and not sell it. The skill asks Claude to check this and put the attribution at the top of every file it creates.
