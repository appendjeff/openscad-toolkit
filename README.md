# openscad-toolkit

OpenSCAD skills for Claude.

Four [Claude Code](https://claude.com/claude-code) skills for designing 3D-printable parts in OpenSCAD, and for turning existing STL files into OpenSCAD you can edit.

| Skill | What it does | Use it when |
|---|---|---|
| [`openscad`](openscad/SKILL.md) | Writes versioned `.scad` files (`part_001`, `part_002`, …), renders each one and compares it with the previous version | Designing a new part or iterating on one |
| [`preview-scad`](preview-scad/SKILL.md) | Renders a `.scad` file to PNG, so Claude can look at what it built and fix it | After every change |
| [`export-stl`](export-stl/SKILL.md) | Exports to STL and checks the mesh is printable (watertight, no self-intersections) | When the design is ready to slice |
| [`stl-to-openscad`](stl-to-openscad/README.md) | Rebuilds an existing STL as parametric OpenSCAD, proves the rebuild matches the original, then customizes it | Remixing a part from a project that only ships STLs (see its own [README](stl-to-openscad/README.md)) |

They work as a pipeline. You don't have to name them: Claude picks the right one from what you ask.

```
                     stl-to-openscad ─┐   (start from someone's STL)
                                      ▼
  (start from scratch)  openscad ──► preview-scad ──► export-stl ──► slicer
                           ▲              │
                           └── iterate ◄──┘
```

## Who this is for

Makers who 3D print and want Claude to do the CAD: you describe the part, or point at a project's STLs, and Claude writes the OpenSCAD, renders it, checks it, and exports it. You should be comfortable running a few terminal commands. You don't need to know OpenSCAD or Python.

If you already write OpenSCAD, the scripts in each skill's `scripts/` folder also work on their own.

## What you need

| | Needed by | Version |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | all | current (terminal, desktop app or IDE extension) |
| [OpenSCAD](https://openscad.org/downloads.html) | all | a version with the **Manifold** backend: `openscad --help` lists `--backend`. The 2021.01 release is too old |
| bash | `openscad`, `preview-scad`, `export-stl` | built into macOS and Linux. On Windows, use WSL or Git Bash |
| [uv](https://docs.astral.sh/uv/) | `stl-to-openscad` | 0.4 or later. It downloads Python and the libraries the scripts need by itself: you don't install Python or any packages |
| git | `stl-to-openscad` | any, for cloning the projects you remix |

## Installing

### 1. OpenSCAD

- **macOS:** `brew install --cask openscad`. If you installed the app by dragging it to Applications instead, the scripts still find it there. To also use `openscad` in your own terminal, run once:
  ```
  sudo ln -s /Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD /usr/local/bin/openscad
  ```
- **Windows / Linux:** download from [openscad.org/downloads](https://openscad.org/downloads.html). On Windows, add the install folder (usually `C:\Program Files\OpenSCAD`) to your `PATH`. On a Linux machine with no display, PNG previews need a virtual display: install `xvfb` and run Claude Code under `xvfb-run`.

Check it:
```
openscad --version
openscad --help | grep backend      # must print a line; if not, install a newer OpenSCAD
```

### 2. uv (for stl-to-openscad)

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`)
- **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Check it with `uv --version`. Open a new terminal if the command isn't found.

### 3. The skills

Clone this repo, then copy the four folders into a skills folder. Copy whole folders, not just the `SKILL.md` files: the scripts are needed too.

```
git clone https://github.com/appendjeff/openscad-toolkit.git
cd openscad-toolkit

# for every project on your machine
cp -r openscad preview-scad export-stl stl-to-openscad ~/.claude/skills/

# or for one project only (and everyone who clones that project)
mkdir -p /path/to/project/.claude/skills
cp -r openscad preview-scad export-stl stl-to-openscad /path/to/project/.claude/skills/
```

Keep them **in the same skills folder**: `openscad` calls `preview-scad`'s render script as a sibling folder. Claude Code picks the skills up the next time it starts. Type `/` in Claude Code to see them listed.

If you only want to remix STLs, `stl-to-openscad` works on its own. The other three make it faster (PNG previews, validated exports).

**On claude.ai:** you can upload a skill (a zip of its folder) in claude.ai's Skills settings. claude.ai runs the scripts in its own sandbox, so it can't use the OpenSCAD on your computer, and the preview and export steps work much better in Claude Code.

### 4. Check it works

In an empty folder:

```
echo 'difference() { cube([40, 30, 10]); translate([20, 15, -1]) cylinder(d = 5, h = 12, $fn = 48); }' > test_part.scad

# preview-scad and export-stl
~/.claude/skills/preview-scad/scripts/render-scad.sh test_part.scad
~/.claude/skills/export-stl/scripts/export-stl.sh test_part.scad

# stl-to-openscad (uv downloads the Python libraries on the first run, about 100 MB)
uv run ~/.claude/skills/stl-to-openscad/scripts/stl_probe.py test_part.stl
uv run ~/.claude/skills/stl-to-openscad/scripts/compare_stl.py test_part.stl test_part.scad
```

Change `~/.claude/skills` to wherever you installed them. You should get:
- `test_part_preview.png`: a block with a hole through it,
- `test_part.stl`, with `STATUS: PASSED` from the validation,
- from the probe, `size [40, 30, 10]` and `circle  d=5 at [20, 15]  (48 segments → $fn≈48)`,
- from the compare, `PASS: IoU 1.00000`.

Then try them through Claude:
- *"Design a wall-mount bracket for a 60 × 40 mm PCB with M3 holes 52 mm apart"* (`openscad` → `preview-scad` → `export-stl`)
- *"Rebuild test_part.stl as parametric OpenSCAD"* (`stl-to-openscad`)

## Troubleshooting

- **`OpenSCAD not found`** / **`openscad: command not found`:** OpenSCAD isn't installed, or isn't on your `PATH`. See step 1.
- **`unrecognised option '--backend'`**, or an error about Manifold: your OpenSCAD is too old. Install a newer one.
- **The preview PNG is blank or the render fails on a server:** no display. Use `xvfb-run` (step 1).
- **Claude doesn't use a skill:** check it's listed when you type `/`, and that the folder has its `SKILL.md` at the top level (`~/.claude/skills/openscad/SKILL.md`, not `~/.claude/skills/openscad/openscad/SKILL.md`). You can also ask for it by name: *"use the stl-to-openscad skill"*.

For problems specific to STL rebuilding, see the [stl-to-openscad README](stl-to-openscad/README.md#troubleshooting).

## Credits and license

MIT, see [LICENSE](LICENSE).

The `openscad`, `preview-scad` and `export-stl` skills are adapted from [iancanderson/openscad-agent](https://github.com/iancanderson/openscad-agent) by Ian C. Anderson (MIT). The changes here: paths that work wherever the skills are installed, corrected `--camera` docs, and notes on OpenSCAD preview pitfalls. `stl-to-openscad` is new.
