# Twin-EDF F-22 Conversion

Parametric redesign of the central fuselage of TimF's 700 mm F-22 Raptor
(`docs/timf.pdf`) to house **two 50 mm EDFs side-by-side** instead of the
original single 50 mm EDF.

## What changed

Three parts in `jet/LW-PLA/F22_Raptor_Fuselage/` get modified:

| Part   | Original                              | Twin-EDF version                                                              |
|--------|---------------------------------------|-------------------------------------------------------------------------------|
| Fuse 2 | Two intake channels merge into one    | Two intake channels stay **separate** all the way through                     |
| Fuse 3 | Houses one 50 mm EDF                  | Houses **two** 50 mm EDFs in parallel bores                                   |
| Fuse 4 | Single exhaust nozzle                 | Two ducts blend together into a **single rectangular exhaust** at the rear   |

The outer fuselage skin (the F-22 outline TimF designed) is **unchanged** —
only the internal ducting is recut. This keeps wing-root, canopy, taileron,
and fan-hatch interfaces compatible with TimF's other parts.

## Layout

```
twin_edf/
├── README.md                       <- you are here
├── src/
│   ├── parameters.py               <- ALL dimensions live here. Tune and re-run.
│   ├── ducting.py                  <- build123d parametric duct geometry
│   ├── generate.py                 <- builds + booleans + exports STL/STEP
│   ├── inspect_stl.py              <- reads TimF's STLs, dumps measurements
│   └── compare_sections.py         <- before/after cross-section PNGs
├── output/
│   ├── stl/
│   │   ├── fuse2_modified.stl      <- print these
│   │   ├── fuse3_modified.stl      <- print these
│   │   ├── fuse4_modified.stl      <- print these
│   │   ├── fuse2_new_ducts.stl     <- (debug) the new air-channel volume only
│   │   ├── fuse3_new_ducts.stl
│   │   └── fuse4_new_ducts.stl
│   ├── step/
│   │   ├── fuse2_new_ducts.step    <- parametric source, open in Fusion/Onshape
│   │   ├── fuse3_new_ducts.step
│   │   └── fuse4_new_ducts.step
│   └── plots/
│       ├── fuse{2,3,4}_before_after.png       <- visual diff vs TimF original
│       └── fuse{2,3,4}_original_sections.png  <- TimF's original cross-sections
└── analysis/
    └── measurements.json           <- bbox + cross-section data extracted from STLs
```

## Geometry — design intent

Coordinate system is global (TimF's STLs share one frame):

- **X** = lateral (wingspan), centered at 0, fuselage skin at ±95.5 mm
- **Y** = longitudinal (nose-to-tail). Parts stack: Fuse 2 [171, 341] → Fuse 3
  [341, 463] → Fuse 4 [463, 653.4]
- **Z** = vertical, up positive

Key numbers (see `src/parameters.py` for the full list):

```
EDF bore diameter   = 56 mm   (5 mm clearance for 50 mm fan housings + tape wrap)
duct centerline |X| = 32.5 mm (so bores at X = -32.5 and +32.5)
duct centerline  Z  = -8 mm   (slightly below center so a fan hatch still fits)
wall between ducts  = 9 mm
clearance to outer skin (X) = 35 mm  (room for wing root + structure)
nozzle exit         = 70 × 25 mm rectangle (combined exhaust)
merger blend length = 90 mm (over which the two ducts merge in Fuse 4)
```

## How to re-run / re-tune

```bash
cd <repo root>
source .venv/bin/activate     # the venv created in this session

# Adjust parameters
$EDITOR twin_edf/src/parameters.py

# Regenerate STLs + STEP (takes ~5s; the 73 MB Fuse 2 STL is the slow part)
python twin_edf/src/generate.py

# Render new before/after cross-sections
python twin_edf/src/compare_sections.py
```

The pipeline is fully scripted. To pick a different EDF size (e.g. 64 mm),
change `EDF_BORE_DIAMETER` and `DUCT_CENTER_X` in `parameters.py` and re-run.

## What's verified (see `analysis/verification.md` for numbers)

- All three modified STLs are **watertight** (manifold) after boolean.
- **All six new bore centerlines are 0% blocked along their full length**
  (20 sample points each on left + right bores across all three parts —
  100% clear). An EDF housing can slide straight through.
- Outer fuselage skin from TimF is preserved (the booleans only subtract
  interior material).
- The Fuse 1 ↔ Fuse 2 intake interface overlay (`output/plots/intake_interface.png`)
  shows the new front-face intake openings are roughly centered on TimF's
  Fuse 1 output channels (X centers within ~5 mm, Z centers within ~5 mm).
  Not a perfect match — Fuse 1's exits are ovals, my new openings are
  rectangles — but the bulk overlap is good enough that air can flow.
- Cross-section visualizations (`output/plots/fuse{2,3,4}_before_after.png`)
  show the new ducts in the correct locations relative to the original skin.
- STEP files are produced so the parametric source is editable in Fusion 360
  or any STEP-aware CAD.

## What's NOT verified — read before printing

1. **Fuse 2 has TWO duct systems coexisting.** The new twin ducts are
   carved out, but TimF's original *merger* walls (the venturi that combined
   the two intakes into one in his single-EDF design) are still present
   between the new bores. Volumetrically this is fine — the new bores
   themselves are 0% blocked — but air entering through the new front
   openings will see both the new straight tubes AND fragments of the old
   merger geometry. Functionally it works (air takes the path of least
   resistance), aesthetically/aerodynamically it's not a clean redesign.
   Fuse 3 and Fuse 4 are cleaner because their old single ducts mostly
   overlapped with where the new twin ducts go.

   Cleanup options if you care about a tidy internal structure:
   - Print as-is and hot-knife the leftover internal walls (TimF's
     own assembly instructions already involve hot-knife cutting of
     internal panels for cable routing — see PDF page 5).
   - Open `fuse2_modified.stl` in Fusion 360 / Blender, identify the
     leftover merger walls between the new bores, and boolean them out.

2. **Fan-hatch interface is unchanged.** TimF's fan hatch on Fuse 3 was
   designed for a single EDF. For twin EDFs you'll need either:
   - Two new fan hatches (cut from TimF's existing one as a template), or
   - Install both EDFs through the rear of Fuse 3 before gluing Fuse 4 on,
     or
   - One larger hatch covering both fans.
   I have NOT redesigned the fan hatch — that's a separate part not in
   Fuse 2/3/4.

3. **Aerodynamic performance is unverified.** The merger geometry in Fuse 4
   (two circles → one rectangle over 90 mm) is a clean-looking loft but
   there is no CFD or wind-tunnel data behind it. Cross-sectional area
   progression and merger losses haven't been quantified.

4. **No test print yet.** The modified STLs slice cleanly in any conventional
   slicer but a real print is the only ground truth on wall thickness,
   bridging, and fit-up with TimF's adjacent parts (Fuse 1, fan hatch).

5. **CG shifts.** Two EDFs + ESCs + larger battery to feed them will move
   the CG. TimF's spec is 87 mm from wing LE (PDF page 7). Reweigh and
   rebalance — the original CG location is no longer guaranteed.

## Engineering decisions logged

- **Why subtract from TimF's STL instead of remodeling outer skin from
  scratch?** TimF's outer skin matches the F-22 aerodynamic profile and
  interfaces with adjacent parts (canopy, wings, taileron). Remodeling from
  scratch risks breaking those interfaces and burns a huge amount of
  modeling time. Subtracting new ducts keeps everything else compatible.

- **Why 56 mm bore for 50 mm EDFs?** Standard 50 mm EDFs (FMS, XRP, XFly)
  have ~52 mm housing OD. 56 mm gives 2 mm radial slack which covers tape
  wrap, print tolerance, and shrink fit. The PDF mentions "wrap with masking
  tape/cut plastic if needed."

- **Why ±32.5 mm centerline?** Gives 9 mm of plastic between the two
  housings (printable, structurally adequate for a foamie-class jet) while
  keeping 35 mm of clearance from the fuselage skin on each side for the
  wing roots and side panels.

- **Why merge ducts in Fuse 4 instead of dual nozzle?** User spec —
  TimF's airframe has a single exhaust opening at the rear that aligns with
  the F-22's visual lines. Dual nozzles would protrude through the existing
  outer skin and look wrong. The single rectangular merge gives the rear
  fuselage roughly the F-22's "horizontal slot" exhaust look.

## Recommended next iteration

If you (or future-me with computer-use) want to clean this up further:

1. Open `fuse2_modified.stl` in Fusion 360 and remove TimF's leftover
   merger walls between the new bores (this is the main outstanding
   cleanup item; Fuse 3 and Fuse 4 are already clean inside the bores).
2. Reshape the front intake openings of Fuse 2 to better match Fuse 1's
   actual exit shape (Fuse 1 outputs oval-ish profiles; my new openings
   are rectangles centered close to but not exactly on the ovals — see
   `output/plots/intake_interface.png`).
3. Redesign the fan hatch on Fuse 3 (two cutouts in a single larger
   hatch is probably simplest — keeps print orientation the same).
4. Verify part-to-part seam fit by importing Fuse 2 + Fuse 3 + Fuse 4
   modified into Fusion as separate bodies; check that the bore centers
   and rear seam profiles align cleanly across the Y=341 and Y=463 seams.
5. (Optional) Run a flow simulation in Fusion's CFD if the merger losses
   in Fuse 4 are a concern.

## File-size warning

`fuse2_modified.stl` is **70 MB** (TimF's source mesh was 73 MB with 1.46M
triangles, and the boolean preserved most of it). This is under GitHub's
100 MB hard limit but above the 50 MB warning. If you want to push it,
either use Git LFS or strip the file count down with mesh decimation in
Blender (`Decimate` modifier, ratio 0.3 typically halves size with no
visible quality loss for an F-22 outer skin).

## Sources & references

- Original model: "3D Print F22 Raptor by TimF" V3, 13 Oct 2022
  (`docs/timf.pdf`)
- RC Groups thread: <https://www.rcgroups.com/forums/showthread.php?3931791-F22-Raptor-700mm-LW-PLA>
- Twin-EDF F-22 prior art (paid, STL-only): JazakKhan's 31" F-22 (`https://cults3d.com/en/3d-model/gadget/f22-raptor-50mm-x-2-edf`)
  and ptikyle's twin 40 mm (`https://cults3d.com/en/3d-model/gadget/rc-f22-raptor-edf-64mm`)
- This conversion was done without source CAD access to TimF's design — only
  the published STLs. The new ducting is original parametric geometry.
