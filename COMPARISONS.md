# How stl-to-openscad compares to other STL → OpenSCAD / CAD tools

Survey as of 2026-10-20. The raviriley converter was checked by reading its source (`js/main.js`). Everything else here comes from each project's README or blog post. None of those tools has been run or tested here, so their accuracy figures are the authors' own claims.

## Summary

The tools fall into three groups:

1. **Mesh dumpers** copy the STL's triangles into one `polyhedron()` call. The result matches exactly but can't be edited.
2. **LLM reconstruction skills** have an agent measure the mesh and write parametric OpenSCAD. This skill belongs to this group.
3. **Conventional CAD mesh-to-solid tools** produce an editable B-rep solid in Fusion 360, FreeCAD or Geomagic. You rebuild the design intent yourself.

| Tool | Group | Output | Editable? | Checks the result | Several parts | Organic shapes |
|---|---|---|---|---|---|---|
| **stl-to-openscad (this skill)** | LLM skill | Parametric `.scad` built from primitives and extrusions | Yes, named parameters | Boolean diff: volume, IoU, list of differing regions | Yes: `common.scad`, mirror pairs, assembly, fit and bed checks | No |
| [raviriley/STL-to-OpenSCAD-Converter](https://github.com/raviriley/STL-to-OpenSCAD-Converter) | Dumper | `module objectN() { polyhedron(...) }` + bbox functions | No | Not needed (exact copy) | Separate unlinked modules | Yes (as a mesh) |
| [joshuaflanagan/stl2scad](https://github.com/joshuaflanagan/stl2scad) | Dumper | `polyhedron()` | No | Not needed | No | Yes (as a mesh) |
| [oculus42/openscad-poly-tools](https://npmjs.com/package/openscad-poly-tools) | Dumper | `polyhedron()` with duplicate vertices merged, optionally simplified | No | No | No | Yes (as a mesh) |
| [openscad-step-reader](https://github.com/agordon/openscad-step-reader) `--stl-scad` | Dumper | `polyhedron()` | No | Not needed | No | Yes (as a mesh) |
| [andreahaku/openscad_claude_skill](https://github.com/andreahaku/openscad_claude_skill) | LLM skill | Parametric `.scad` (a solid block with material removed) | Yes | Boolean diffs for missing and extra material, overlay image, IoU | Not covered | No |
| [Tao of Mac experiment](https://taoofmac.com/space/til/2026/02/16/1334) | LLM, one-off | Parametric `.scad` | Yes | Two-way Hausdorff distance, volume, bbox, Euler number | Not covered | No |
| [ModelRift/openscad-skill](https://github.com/ModelRift/openscad-skill) | LLM skill (for designing new parts) | New `.scad`, STL, 3MF | Yes | Colour diff between two versions | n/a | n/a |
| Fusion 360 mesh → solid | CAD | B-rep (facet by facet, or prismatic fit) | You rebuild the feature tree by hand | Deviation analysis | Manual | Better |
| FreeCAD shape from mesh | CAD | Faceted B-rep | Barely | Manual | Manual | Faceted |
| Geomagic Design X | CAD (commercial) | Fitted B-rep and feature tree | Yes, after manual work | Colour deviation map | Manual | Yes |

## 1. Mesh dumpers

### raviriley/STL-to-OpenSCAD-Converter

- A browser app (jQuery and a binary STL reader) that reads an ASCII or binary STL and downloads a `.scad` file containing:
  ```scad
  module object1(scale) { polyhedron(points=[...], faces=[...]); }
  function object1Min() = [...];
  function object1Max() = [...];
  object1(1);
  ```
- It exists because Thingiverse Customizer can't `import()` STLs, so the mesh has to live inside a single `.scad` file.
- The `scale` argument is never used. The repo has no LICENSE file. It has about 248 stars, and the last commit was July 2025.

### joshuaflanagan/stl2scad

A Python 3 command-line script that turns `model.stl` into `model.scad` (a polyhedron). License: CC BY-SA 3.0.

### oculus42/openscad-poly-tools (osPoly)

A Node.js library that imports an STL, merges duplicate vertices, can simplify the mesh, and exports OpenSCAD. It was written to fix the duplicated points in the earlier converters' output. Still before version 1.0.

### openscad-step-reader

Mainly reads STEP files. Its `--stl-scad` option writes triangles out as a single polyhedron.

### Compared with this skill

These tools don't compete with it. They give an exact copy you can't edit, which is the same thing `import("part.stl")` gives you in stock OpenSCAD. This skill already uses that for its `show_original` ghost. A dumper is only useful when one self-contained `.scad` file is required, or for parts too organic to rebuild (see the hybrid idea below).

## 2. LLM reconstruction

### andreahaku/openscad_claude_skill

The closest competitor: an MIT-licensed Claude skill (about 24 stars) with an STL reconstruction mode.

| | andreahaku | stl-to-openscad |
|---|---|---|
| Mesh triage | trimesh: volume, watertightness, normals, bounding cylinder | `stl_probe.py`: size, units and frame, watertightness, bodies |
| Measuring | `projection(cut=true)` SVG slices at **5 fixed Z levels** | Slices at **every flat level found**, midway between levels, plus `--axis x/y` sections and `--png` images |
| Recognising features | RANSAC axis estimation, guessing CSG operations from normals | Classifies rings as `rect` / `rrect` (with radius) / `circle` (with `$fn`) / `poly`, and groups repeated holes with their pitch |
| Fitting parameters | **SDF optimisation**: `scipy.optimize.minimize` raises IoU | **Rounds to design intent**: whole mm, inches, standard part sizes, derived values written as formulas |
| Modelling style | A solid block with material removed (holes cut last) | A stack of extrusions between flat levels |
| Checking | Boolean diffs for missing and extra material, overlay image | Volume difference, IoU, a list of differing regions with size and location, `--overlay`, `--xor-out` |
| Reported accuracy | 96.3% and 95.6% on two example parts | Targets IoU ≥ 0.999 for prismatic parts, about 0.99 with fillets |
| Several parts | Not covered | Shared `common.scad`, mirror pairs with a `side` parameter, assembly, `check_assembly.py` overlap and bed checks |
| Other features | Image-to-CAD, printability analysis, printer calibration, eval framework (4 scenarios, 20 assertions) | License and attribution step, versioned `_001` baseline, electronics-enclosure reference (inserts, tolerances, test coupons) |

### Tao of Mac: "Claude Opus 4.6 Can Reverse Engineer STL Files" (Feb 2026)

A one-off experiment. An agent with a `SPEC.md` (0.1 mm target, customiser constants) rebuilt a screen bracket and wrote its own tools along the way.

- **Method:** mesh triage, then the axis with the fewest unique Z levels, then `trimesh.section()` and Shapely, then classifying primitives, then cross-checking against raw vertices, then OpenSCAD with named constants. This is essentially the same method as this skill's.
- **Checking (the useful difference):** two-way **Hausdorff distance** from about 50k surface samples, plus volume, bbox, **Euler number** for the hole count, and up/down face-area sums as a quick checksum.
- **Result:** 0.004 mm of error on one prismatic part, with the leftover error coming from `$fn=64` circles.
- No reusable tool was published, and it covers only one part.

### ModelRift/openscad-skill

Not a reverse-engineering tool. It's comparable to this repo's `openscad`, `preview-scad` and `export-stl` skills: a render, inspect and revise loop, versioned file names, Customizer conventions, multi-object 3MF export with lazy union, and reference parts that have been checked for collisions. Its `stl_diff.py` renders the difference between two versions in colour (red for added, blue for removed, grey for unchanged). It needs an OpenSCAD 2026.x snapshot. It's made by a vendor that sells the ModelRift editor.

## 3. Conventional CAD mesh-to-solid

- **Fusion 360:** converts a mesh to a solid, either facet by facet or with a prismatic fit (planes and cylinders), then you model on top of it by hand. A good fit for the shop's Fusion → VCarve workflow when the part is going to the CNC router.
- **FreeCAD:** makes a faceted solid from a mesh. Useful for booleans, not for changing parameters.
- **Geomagic Design X:** the professional scan-to-CAD standard and the tool freelancers name most often. It fits surfaces and rebuilds a feature tree, and checks with a colour deviation map. It's the only option here that handles organic or scanned parts well, and it's expensive.

Compared with this skill, these handle curved surfaces far better. But all the work of naming parameters, sharing interfaces between parts, and checking assemblies is done by hand, and the output isn't text you can diff in git.

## What only this skill does

- **Rounds measurements to the designer's intent** instead of optimising them, so the parameters come out as `19.05` (MX key pitch), not `19.0487`.
- **Says where a rebuild is wrong,** with each differing region's location and size, not just one score.
- **Handles whole projects:** shared interfaces in `common.scad`, mirror pairs, assembly overlap and slide checks, and bed fit.
- **Checks the license and looks for existing CAD first,** and adds attribution to every file.
- **Keeps a versioned baseline:** `_001` stays faithful to the original, and each customisation goes into a later version that can be diffed against it.
- **Electronics-enclosure guidance:** reference component models, insert and fastener stacks, FDM tolerances, test coupons.

## Ideas to borrow

1. **Hausdorff distance in `compare_stl.py`** (from Tao of Mac). IoU is weighted by volume, so a small hole 0.3 mm off centre barely moves it. A largest-surface-gap number in mm catches that, and it's in the unit that matters for fit.
2. **Euler number or genus in `stl_probe.py`** (from Tao of Mac). A quick hole and handle count to compare between the original and the rebuild.
3. **Optimiser fallback** (from andreahaku). For dimensions that can't be read from slices (fillet radii, draft angles), run a short `scipy` fit that maximises IoU, only after rounding, so design-intent values still win.
4. **Eval set** (from andreahaku). A few known STLs, each with a target IoU and Hausdorff distance, to catch regressions when the skill or scripts change.
5. **Colour diff renders** (from ModelRift). Red and blue images of `--xor-out` regions for the README verification table.
6. **Hybrid mode** (from the dumpers). When part of a model can't be rebuilt, keep that part as `import()` or a polyhedron and model the parametric features around it, for example a sculpted shell with parametric port cutouts.

## Sources

- https://github.com/raviriley/STL-to-OpenSCAD-Converter
- https://github.com/joshuaflanagan/stl2scad
- https://npmjs.com/package/openscad-poly-tools
- https://github.com/agordon/openscad-step-reader
- https://github.com/andreahaku/openscad_claude_skill
- https://github.com/ModelRift/openscad-skill
- https://taoofmac.com/space/til/2026/02/16/1334
- https://www.cadcrowd.com/service/2349-reverse-engineering-stl-cad-models
