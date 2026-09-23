---
name: 3d-print-workflow
description: "End-to-end workflow for designing 3D-printable models and printing them on a Bambu Lab printer from Claude Code: turning a request (often a photo, sketch or rough description) into parametric CAD code (OpenSCAD / build123d / CadQuery), exporting STL/3MF, verifying printability and real-world proportions with rendered previews, slicing (Bambu Studio CLI or GUI), and sending the job to the printer through Bambu Studio with computer use. Load whenever the user asks to model, fix, scale, slice or print a part, mentions STL/3MF/G-code, Bambu Studio/Handy/MakerWorld, a printer (A1, A1 mini, P1S, P2S, X1C, H2D) or filament, or asks Claude to operate Bambu Studio on screen. Works together with opus-orchestration for routing."
---

# 3D print workflow (Bambu Lab + Claude Code)

The pipeline is **request → dimensions → CAD code → export → verify →
slice → user confirms → print → monitor**. Every step except slicing and
printing is plain files and shell commands. Screen control (computer use) is
only for the steps that have no CLI, so Claude can do everything up to the
Print button without touching the GUI.

Routing of each step across models is in `opus-orchestration`, section
"3D printing and computer use". This file covers what to do; that one covers
who does it.

## 1. Pin down the request before modelling

Most failed prints come from a wrong assumption, not bad code. Before writing
any geometry, get or state these explicitly (ask only for what can't be
inferred; state assumptions for the rest):

- **Real-world dimensions in mm.** If the part must fit something (a phone,
  a pipe, a screw, a shelf), get the measured size of that thing. Never guess
  a mating dimension. If the user gives a photo, ask for one reference
  measurement to scale from.
- **Purpose and load:** decorative, functional, snap-fit, outdoor, food
  contact, hot environment. This decides material and wall thickness.
- **Printer and filament:** model (A1 mini / A1 / P1S / P2S / X1C / H2D …),
  nozzle (default 0.4 mm), AMS or not, filament type and colours. Check the
  printer's build volume before designing: A1 mini is 180×180×180 mm, A1 and
  the P1/X1 series are 256×256×256 mm; look up newer models rather than
  assuming.
- **Multi-colour:** if wanted, each colour must be a separate body (exported
  as a multi-part 3MF), not a texture.

Ready-made models: for generic objects (a standard hook, a common enclosure,
a known phone stand), a quick look on MakerWorld or Printables can beat
designing from scratch. Mention it; let the user decide.

## 2. Model as code, parametric

Write CAD as code so dimensions stay editable and the model can be
regenerated after feedback.

- **OpenSCAD** — default. Models make far fewer code errors in it than in
  the Python kernels (GrandpaCAD 2026: about 0.4 errors per generation vs
  about 1.4–1.7 for build123d), because the language is small. Fast to
  write and render. CLI on macOS:
  `/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD` (or `openscad` via
  Homebrew: `brew install --cask openscad`).
- **build123d / CadQuery** (Python, OpenCASCADE) — only when OpenSCAD is
  genuinely limiting: true fillets on complex edges, STEP export for other
  CAD tools, or standard-part geometry. Expect more repair loops (models
  call methods that don't exist), so run it and fix it until it executes.
  Install with `pip install build123d` in a venv.
- **Blender (bpy)** — only for organic/sculpted shapes. It is mesh-based, so
  check the result for manifold errors.

Code conventions:

- All key dimensions as named parameters at the top of the file, in mm.
- Keep the model on the XY plane with a flat face down (Z=0), centred.
- Put comments on the parameters that the user is likely to tweak.
- One file per part; an assembly file only if the parts must be checked
  together.

## 3. Design for FDM printing

Defaults for a 0.4 mm nozzle; tighten or relax by material and purpose.

| Rule | Default |
|---|---|
| Minimum wall | 1.2 mm (3 perimeters); 0.8 mm only for non-structural |
| Overhangs | ≤ 45° without supports; add chamfers instead of flat undersides |
| Bridges | ≤ ~10 mm without support |
| Hole clearance | model holes +0.2 mm (fit), +0.3–0.4 mm (sliding / loose) |
| Mating parts / press-fit | 0.1–0.2 mm; print a small test piece first for critical fits |
| Snap-fit / living hinge | PETG or PLA+, not plain PLA; keep strain low |
| Text / embossing | ≥ 0.6 mm stroke, ≥ 0.4 mm height/depth |
| First layer | large flat contact face; avoid sharp contact edges, add a small chamfer (0.4–0.6 mm) against elephant foot |
| Strength | layers are the weak direction; orient so loads run along the layers |
| Threads | model M6+ directly; below that, use heat-set inserts or self-tapping screw holes |

Materials in short: **PLA** default indoor; **PETG** tougher, some heat and
water; **ASA/ABS** outdoor / heat (enclosed printer); **TPU** flexible (often
not via AMS). Don't claim a print is food-safe.

## 4. Export and verify — never skip

Export: STL for single-material parts, **3MF** for multi-part/multi-colour or
when keeping units and plate layout matters (Bambu Studio prefers 3MF).

Before calling a model done:

1. **Mesh check** (watertight, size, volume), e.g.:
   ```bash
   python3 -c "import trimesh,sys; m=trimesh.load(sys.argv[1]); print('watertight',m.is_watertight,'extents_mm',m.extents.round(2),'volume_cm3',round(m.volume/1000,1))" part.stl
   ```
   Extents must match the intended size and fit the build volume. Also
   check for disconnected pieces: `len(m.split(only_watertight=False))`
   must equal the number of bodies you meant to make. A "floating" rib or
   boss that doesn't touch the main body is a common AI modelling error and
   it passes a render check easily.
2. **Render previews from several angles** (front, side, top, isometric,
   and underneath for the bed face), then look at them:
   ```bash
   openscad -o iso.png --render --imgsize=900,700 --viewall --autocenter \
     --camera=0,0,0,55,0,25,0 part.scad
   ```
   (For Python CAD, export STL and render with trimesh/pyrender or Blender.)
3. **Compare against reality.** Check the proportions against the real
   object or reference photo, not only against the code. A model can be
   dimensionally "correct" and still look wrong or not fit. Checking one
   angle is not enough. Check specifically: is the part upright in the
   intended orientation, do features sit on the correct face/plane, and
   would the mating object actually sit in it without falling out or
   intersecting it. (If useful, model the mating object as a ghost body in
   the preview only, e.g. OpenSCAD's `%` modifier.)
4. Report to the user: size, estimated volume, chosen orientation, anything
   assumed, and the preview images.

## 5. Slice

Prefer the **Bambu Studio CLI** (no screen control needed):

```bash
BS=$(ls /Applications/BambuStudio.app/Contents/MacOS/* | head -1)  # binary name varies by version
"$BS" --orient 1 --arrange 1 --slice 0 \
  --load-settings "machine.json;process.json" --load-filaments "filament.json" \
  --export-3mf out.gcode.3mf part.stl
```

- Output is a `.gcode.3mf` (a zip with G-code, thumbnail and AMS mapping),
  not a raw `.gcode`.
- The preset JSONs are exported from the user's own Bambu Studio (their
  printer / process / filament), so ask the user once to export them, or
  locate their user presets under
  `~/Library/Application Support/BambuStudio/user/`.
- The CLI **cannot send to the printer.** It only produces the file.
- If the CLI is awkward, open the model in the GUI and slice there:
  `open -a "Bambu Studio" part.3mf`. That opens the file without screen
  control; computer use is only needed to click through from there.

Report print time and filament use from the slice before printing.

## 6. Print through Bambu Studio (computer use)

Sending a job needs the Bambu Studio GUI (or Bambu Handy on the phone).
Since Bambu's 2025 Authorization Control firmware, third-party tools can't
start prints on a cloud-connected printer. Only LAN-only mode + Developer
Mode allows direct control. **Never change printer network or security
settings on your own**; recommend the GUI route.

Computer use in Claude Code (macOS, Pro/Max, interactive session only, not
`claude -p`): enable once with `/mcp` → `computer-use` → Enable, grant
Accessibility + Screen Recording, approve "Bambu Studio" when prompted.

Flow:

1. `open -a "Bambu Studio" <file>` from the shell (cheaper than clicking
   through Finder).
2. With computer use: check the printer, plate type, filament/AMS slot
   mapping and supports in the Prepare tab, then Slice plate.
3. **Stop and confirm with the user before pressing Print / Send.** A print
   is a physical action that uses material and time. Summarise: printer,
   plate, filament + slot, time, grams, supports, bed levelling/timelapse.
   Wait for an explicit yes. Approval covers that one job only.
4. In the send dialog, set the options the user confirmed, then Send.
5. Confirm the job started on the Device tab. If asked to monitor, check at
   long intervals (the first layer matters most), and report problems
   rather than trying to fix things on the printer by yourself.

Screen-control hygiene: make text in Bambu Studio large enough to read after
screenshot downscaling; fewer, deliberate screenshots; never type
credentials or access codes for the user; stop and ask on any login, payment,
firmware update or unexpected dialog.

## 7. Iterate

After a test print, the user will report things like "too tight", "broke at
X" or "warped". Adjust the named parameters, re-verify (step 4) and re-slice.
Keep a short changelog comment at the top of the model file (what changed
and why), so the next iteration starts from known facts.
