# Customizing electronics enclosures

Read this before changing a rebuilt enclosure (step 6 of SKILL.md) and when checking fit (step 7).

Contents:
1. Reference component models
2. Fasteners: clearance holes, counterbores, heat-set inserts
3. FDM tolerances
4. Component swaps
5. Fit checks
6. Test coupons
7. Splitting a part that's bigger than the bed

## 1. Reference component models

Put a simple model of each electronic part in `assembly_*.scad`: a `cube()` for a board, plus cubes for whatever sticks out of it (USB connector, headers, a display's FPC tail, the tallest components on the back). They're not printed. They're there so the fit check can find a board that hits a boss or a connector that misses its opening.

- Take dimensions from the vendor's product page or datasheet (Adafruit and Waveshare publish mechanical drawings, and Adafruit often has a STEP or Fusion model on GitHub at `adafruit/Adafruit_CAD_Parts`). Note the source in a comment.
- Give each reference a parameter block and a comment saying how sure the size is: `// datasheet`, `// measured with calipers`, `// typical, MEASURE`. Fit-check problems that involve a guessed size are warnings to measure, not design failures.
- Model the *envelope*: the board outline plus the highest component and the space a cable plug needs. A USB-C plug overmold is much bigger than the receptacle.
- Ask the user to measure the parts they actually have (with calipers) before the final print, especially cheap modules from marketplaces, which vary between batches.

## 2. Fasteners

Keep all hardware in one block in `common_*.scad` and derive every hole from it.

| | M2 | M2.5 | M3 |
|---|---|---|---|
| Clearance hole (ISO 273 medium) | 2.4 | 2.9 | 3.4 |
| Socket cap head Ø × h (ISO 4762, max) | 3.8 × 2.0 | 4.5 × 2.5 | 5.5 × 3.0 |
| Pan head Ø × h (ISO 7045, max) | 4.0 × 1.6 | 5.0 × 1.75 | 5.6 × 2.1 |

- **Counterbores:** head Ø + 0.4–0.6 mm, depth = head height + a little if the head must sit flush or below (for example under keycaps).
- **Heat-set inserts:** the hole size depends on the insert brand and length, so use the vendor's recommended hole if it's published. Otherwise start from the insert's outer knurl diameter minus ~0.1–0.2 mm and test with a coupon (section 6). Make the hole at least 1 mm deeper than the insert, and the boss wall at least ~1.5 mm around the hole.
- **Screw length:** check the stack: head seat → clearance through the first part → thread engagement in the insert → room for the tip below. If the user has an assortment, list which lengths work instead of naming just one.
- **Self-tapping into plastic:** a pilot hole of about 0.8 × the nominal diameter is a starting point. Inserts are better for anything opened more than a few times.

## 3. FDM tolerances

- Holes print **undersize** (often 0.1–0.3 mm on small holes) and pegs print oversize. Never assume the nominal size fits. Expose the size as a parameter and test it.
- Sliding or removable fits between printed parts: 0.2–0.4 mm gap per side. Press fits: 0–0.1 mm, and test.
- Thin walls: at least 2 × the nozzle width (0.8 mm for a 0.4 mm nozzle), preferably 1.2 mm or more for anything that takes a load.
- Long bridges and overhangs: note the print orientation in the README, and add chamfers (45°) in place of horizontal overhangs where that doesn't change the fit.

## 4. Component swaps

Make the component a choice parameter and derive every dependent dimension from a lookup on it, so a single value switches the whole design:

```openscad
switch_type = "choc";   // "choc" | "mx"
function sw(t) = t == "mx"
    ? [["cut", 14.0], ["pitch", [19.05, 19.05]]]
    : [["cut", 13.8], ["pitch", [18, 17]]];
function swp(key) = sw(switch_type)[search([key], sw(switch_type))[0]][1];
key_pitch = swp("pitch");
```

(Or use plain ternaries per parameter if there are only a few.)

- Keep the original's option in the list. Setting it should reproduce the original, so `compare_stl.py` can still prove the baseline after you've refactored.
- Find every place the old part was implied: plate cutouts, pitch, plate and tray length, the openings in the walls, standoff positions, the clearance above and below the part. The step 2 survey of the interfaces is your checklist.
- Common examples: MX ↔ Choc V1 switches (MX cutout 14.0 mm on 19.05 pitch; Choc V1 13.8 mm on 18 × 17 pitch); display size or panel (window, glass pocket, FPC slot, mounting holes); MCU board (USB opening position, standoffs, antenna keep-out: don't put screws or metal under an ESP32 module's antenna); charger and battery (micro-USB → USB-C, 18650 → LiPo pouch).

## 5. Fit checks

Run `scripts/check_assembly.py` on the exported parts and the reference components, all in the assembly frame:

```
uv run <skill-dir>/scripts/check_assembly.py out/*.stl ref/*.stl --bed 256x256x256 --print out/tray.stl …
```

It reports every overlapping pair with the volume and location of each overlap, and for parts close to each other, how far one can slide toward the other in each direction. "Touching" in one direction is normal for a part resting on another (plate on a ledge).

What it doesn't check, and you should when the project has screws:

- **Hole alignment across parts.** Find the holes in each exported mesh by slicing it (`stl_probe.py --at <z>` lists circles and their centres), and compare the centres of matching holes in mating parts. They should be within ~0.1 mm. Measure the meshes. Don't read the positions from `common_*.scad`: a check that reads the same numbers as the model can't catch a part that ignores them.
- **Screw stack:** the head fits its counterbore, the shank clears the first part, the thread engages the insert for most of its length, and the tip doesn't bottom out.
- **Seating:** a part that should rest on another touches it (a gap of 0 in −z) and doesn't float.

For a bigger project, put these in a project script (`fit_check.py` next to the SCAD files) that exports every part, runs all the checks (interference, mesh-measured hole alignment, screw stack, seating, clearances, bed fit) and writes a report file. Start from `check_assembly.py` and add the project's holes and screws. Test the checker itself by deliberately breaking the design (move one part's holes 0.5 mm with `-D`) and making sure the check fails.

## 6. Test coupons

For press fits, inserts and snap-in parts, a 20-minute coupon saves a failed multi-hour print.

- Cut the coupon **from the real part** so it has the real geometry. In OpenSCAD, prefer `difference()` with the complement of the region you keep, wrapped in `render()`: `intersection()` with a hollow part draws wrong in preview.
- Add a **sweep strip**: the same feature at several sizes (switch cutouts 13.7/13.8/13.9/14.0, insert holes 2.9–3.3 in 0.1 steps), labelled with embossed text or a notch count. The user picks the size that fits and sets the parameter to it.
- Print the coupon on the same printer, in the same material and the same orientation as the real part.

## 7. Splitting a part that's bigger than the bed

- Split at a place with little stress and no fit surface, away from screw bosses.
- Join with a lap or tongue-and-groove (0.2 mm clearance) plus screws, or with alignment pins and glue.
- Put each half in its own export, and keep the unsplit part in the assembly so the fit checks still see the whole part.
