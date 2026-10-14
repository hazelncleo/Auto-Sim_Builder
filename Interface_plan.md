# Interface Plan

A keyboard-driven [Textual](https://textual.textualize.io/) app for managing a project's objects, models and software, plus a few helper commands. Running simulations is out of scope. The database layout is in `Database_plan.md`.

Linux only for now; Windows support comes next.

---

## Project folder

Running `autosim` in a folder (or `autosim -f <dir>`) makes it a project:

```
~/Documents/simulations/project/
├── autosim.db            ← created on first run
├── autosim.toml          ← optional, overrides the global config
├── objects/
│   └── <object name>/    ← one folder per object, holding its copied files
├── models/
│   └── <model name>/     ← one folder per model
│       └── logs/
│           └── build-YYYYMMDD-HHMMSS.log
└── .trash/
    ├── objects/<name>-YYYYMMDD-HHMMSS/
    └── models/<name>-YYYYMMDD-HHMMSS/
```

- `objects/` and `models/` always match the database. Deleted folders go to `.trash/`, never stay behind.
- Object and model names double as folder names: letters, digits, `_`, `.`, `-` only, and they must start with a letter or digit (so no hidden `.name` folders or `-name` shell-option lookalikes).

## Startup

1. Find `autosim.db` in the folder.
2. **If there isn't one:** ask before creating anything, so running `autosim` in the wrong folder (e.g. home) doesn't scatter files.
   ```
   ┌ New autosim project ───────────────────────────────────┐
   │ No project found in ~/Documents/simulations/project.   │
   │                                                        │
   │ This will create:                                      │
   │   autosim.db   objects/   models/   .trash/            │
   │                                                        │
   │ Software used in this project:                         │
   │   [x] abaqus      [ ] fluent      [ ] mpcci            │
   │                                                        │
   │          [ Cancel ]          [ Create project ]        │
   └────────────────────────────────────────────────────────┘
   ```
3. **Consistency check:** compare `objects/` and `models/` with the database. Flag folders with no database entry, and entries with no folder, so the user can deal with them.
4. Open the main screen.

## Config

Read in order, later wins: built-in defaults → global `~/.config/auto-sim-builder/config.toml` → project `autosim.toml`. Read with the built-in `tomllib`; for now the config is edited by hand.

```toml
[storage]
trash_dir = ".trash"

[import]
max_file_size_mb   = 100      # hard limit: bigger files can't be imported
max_object_size_mb = 1000     # hard limit on an object's total; 0 = no limit
ignore = [
    "__pycache__/", "*.pyc",
    "*.rpy", "*.rpy.*", "*.log", "*.lck", "*.odb",   # Abaqus run leftovers
    "*.trn", "*.out",                                # Fluent run leftovers
]

[software.abaqus]
command = "abq2024"           # project database override wins over this
```

The limits are conservative on purpose. The interface tells the user which setting to raise when a file is refused.

---

## Main screen

Three tabs. Each has a list on the left and details on the right.

```
┌ autosim · ~/Documents/simulations/project ───────────────────────────┐
│ [1 Objects]   2 Models    3 Software                                 │
├─────────────────────────┬────────────────────────────────────────────┤
│ / filter                │ plate_with_hole                 geometry   │
│                         │ Parametric plate with a central hole       │
│ ANALYSES                │ Software  abaqus                           │
│   static_load        ●  │                                            │
│   fsi_coupled           │ ┌ Files ──────────────────── 3 · 41 MB ──┐ │
│ GEOMETRIES              │ │ ★ build_plate.py   abaqus         4 KB │ │
│ > plate_with_hole       │ │   mesh.msh                       41 MB │ │
│   bracket               │ │   materials.inp                   2 KB │ │
│                         │ └────────────────────────────────────────┘ │
│                         │ ┌ Parameters ─────────────── 3 ─── z ⤢ ──┐ │
│                         │ │ width      float   1 – 100      25.0   │ │
│                         │ │ hole_r     float   0.1 – 10     2.5    │ │
│                         │ │ elem_type  choice  C3D8 | C3D10 C3D8   │ │
│                         │ └────────────────────────────────────────┘ │
├─────────────────────────┴────────────────────────────────────────────┤
│ a add  e edit  c clone  d delete  r rescan  z zoom  f find  q quit   │
└──────────────────────────────────────────────────────────────────────┘
```

**Markers**
| marker | meaning |
|---|---|
| ● | object files changed on disk since import (or last Verify OK) |
| ✎ / ✗ | file modified / file missing |
| ★ | build file (with its software) |
| ✓ / ✗ | model built successfully / build failed |
| ⋯ | model building |
| • | model value differs from the default |

- The footer changes with the focused panel, showing only the keys that apply there.
- Parameter tables show a few rows and expand to full screen with `z`.

## Keys

Arrow keys move; action letters sit near WASD so the left hand covers them. **WASD does not move the cursor.** Keys are mnemonic, and a letter means the same thing wherever focus is.

**Global**
| key | action |
|---|---|
| ↑ ↓ ← → | move |
| Enter / Esc | open / go back |
| 1 2 3 | Objects / Models / Software tab |
| Tab / Shift+Tab | next / previous panel |
| f | find (filter the list) |
| q | quit |
| h | help |

**Lists and panels**
| key | action | where |
|---|---|---|
| a | add | everywhere |
| e | edit (full screen) | everywhere |
| c | clone into a new object / model | Objects, Models |
| d | delete (with confirmation) | everywhere |
| z | zoom panel to full screen | tables |
| r | rescan files / rebuild model | Objects / Models |
| v | view latest build log | Models |
| b | assign build file | object wizard, Files step |
| s | *reserved for parameter sweeps* | Models |

**Full-screen editors and wizards**
| key | action |
|---|---|
| Ctrl+S | save / create |
| Esc | cancel (asks first if there are unsaved changes) |
| Tab / Shift+Tab | next / previous field |
| Space | tick / untick (checklists) |

Single letters don't fire while a text field has focus; they're typed into it instead. That's why saving uses Ctrl+S.

---

## Objects tab

The list is grouped into **analyses** and **geometries**. The detail pane shows the description, software, files (with build file assignments) and parameters.

### Create (`a`): 4-step wizard

Everything structural is chosen here and locked once the object is saved.

| step | content |
|---|---|
| 1 Details | name, kind (analysis / geometry), description, software (tick one or more of the project's software) |
| 2 Folder | directory browser to choose the source folder |
| 3 Files | import checklist, then assign build files: one slot per chosen software, optional per software; at least one overall |
| 4 Parameters | add parameters; Ctrl+S creates the object and copies its files in |

**Step 2: directory browser** (Textual `DirectoryTree`). It starts in the project's parent folder and remembers the last folder chosen.
```
┌ Choose source folder ────────────────────────────────┐
│ ~/sims                                               │
│ ▾ plate_src/                                         │
│   ▸ submodels/                                       │
│ ▸ bracket_src/                                       │
├──────────────────────────────────────────────────────┤
│ ↑↓ move  → expand  ← collapse  Enter choose  Esc     │
└──────────────────────────────────────────────────────┘
```

**Step 3: import checklist**
```
┌ Add files · plate_with_hole ── from ~/sims/plate_src ────────────────┐
│ [x] build_plate.py                     4 KB   ★ abaqus (python)      │
│ [x] materials.inp                      2 KB                          │
│ [x] mesh.msh                          41 MB                          │
│ [ ] abaqus.rpy                         1 KB   ignored (*.rpy)        │
│ [ ] old_run.odb                      1.2 GB   ⚠ over 100 MB limit    │
│ ▸ [~] submodels/  (2 of 3)                                           │
├──────────────────────────────────────────────────────────────────────┤
│ 3 selected · 41 MB of 1000 MB object limit                           │
│ space toggle  → expand  b build file  Ctrl+S next  Esc cancel        │
└──────────────────────────────────────────────────────────────────────┘
```
- Files matching ignore patterns start unticked but can be ticked.
- Files over the per-file limit can't be ticked. The message names the setting to raise.
- The running total counts against the per-object limit. Going over it blocks the step.
- `b` on a ticked file assigns it as the build file for one of the object's software. The file type must be one that software accepts. Abaqus takes `.py` (built with Python) or `.inp` (a `*PARAMETER` block is added), and the marker shows which, e.g. `★ abaqus (python)` / `★ abaqus (input)`.
- Files are imported only once, so there are no name clashes.

**Step 4: parameter dialog** (opened with `a` / `e` on a parameter row)
- Fields: name, type, default (required), description.
- The range fields change with the type:
  - `int` / `float`: min / max (inclusive, blank = open);
  - `str`: min / max length;
  - `choice`: a choice-list editor;
  - `bool`: nothing.
- The default is checked against the range or choices before saving.

### Edit (`e`)
Full-screen editor:
- **Name and description:** always editable. Renaming moves `objects/<name>/`.
- **Parameters:** editable **until a model uses the object**. In the Parameters table, `a` adds, `e` edits, `c` clones (copies a parameter under a new name) and `d` deletes, using the same parameter dialog as the wizard. Once the object is used, the table becomes read-only and its header shows `🔒 used by N models`. It unlocks again if those models are deleted.
- **Files, software and build files:** always read-only.

### Clone (`c`)
Opens the creation wizard pre-filled from the selected object (details, software, source folder, parameters). This is how an object that's already used by a model is changed, or how its files or software are changed: by making a new one, e.g. `plate_with_hole_v2`.

### Rescan (`r`)
Runs the file check on the selected object, comparing size and modification time and only re-hashing when those differ. Results show in the Files panel (✎ modified, ✗ missing). Unlisted files in the object folder are ignored.

### Delete (`d`)
Blocked while any model uses the object; the dialog lists those models. Otherwise the user chooses **Move to trash** (default) or **Delete permanently**.

---

## Models tab

```
┌ autosim · ~/Documents/simulations/project ───────────────────────────┐
│  1 Objects   [2 Models]   3 Software                                 │
├─────────────────────────┬────────────────────────────────────────────┤
│ / filter                │ plate_static_v2                     ✓      │
│                         │ Coarser hole, same load case               │
│   plate_static_v1    ✓  │                                            │
│ > plate_static_v2    ✓  │ Analysis    static_load                    │
│   plate_static_v3    ⋯  │ Geometries  plate_with_hole                │
│   bracket_fsi        ✗  │ Last build  2026-10-13 16:10  success      │
│                         │                                            │
│                         │ ┌ Values ──────────────── 2 changed ─ z ⤢ ┐ │
│                         │ │ object            param      value      │ │
│                         │ │ plate_with_hole   width      25.0       │ │
│                         │ │ plate_with_hole   hole_r   • 3.0        │ │
│                         │ │ static_load       load_N   • 5000       │ │
│                         │ └─────────────────────────────────────────┘ │
├─────────────────────────┴────────────────────────────────────────────┤
│ a add  e edit  c clone  r rebuild  v log  d delete  z zoom  q quit   │
└──────────────────────────────────────────────────────────────────────┘
```

### Create (`a`): 3-step wizard

| step | content |
|---|---|
| 1 Analysis | pick exactly one analysis |
| 2 Geometries | tick any number of geometries (zero or more) |
| 3 Name + values | name, description, values table pre-filled with defaults; Ctrl+S creates and builds |

- **Parameter name clashes:** if the chosen objects share a parameter name, step 2 shows the clash and won't continue.
- **Editing values:** Enter on a row opens a small input showing the valid range or choices, e.g. `hole_r · float · 0.1 – 10`. Invalid values are refused with the reason.

### Clone (`c`)
Opens the wizard at step 3 with the same analysis and geometries, and the selected model's values filled in. The new model is built from the objects, not copied from the old model's folder.

### Build flow (create, clone, rebuild)
1. **File check** on each of the model's objects:
   - **Modified** files → dialog listing them with **[ Cancel ] [ Verify OK ]**. Verify OK overwrites the stored snapshot.
   - **Missing** files → the build is blocked.
2. **Create only:** insert the model, its geometries and values in one transaction.
3. **Create the model folder:** copy the **listed** files of each object into `models/<name>/`.
4. **Run the build:** for each object, run each software's build file with **all** of the model's parameter values. Order doesn't matter. Output goes to `logs/build-YYYYMMDD-HHMMSS.log`.
5. **Record the result:** set `build_status` (`success` / `failed`) and `built_at`.

**Rules while building**
- **Only one build at a time.** It runs in the background, so the interface stays usable, and the model shows ⋯ in the list. Starting a second build is refused with "another build is running". A queue may come later.
- **Quitting during a build** asks for confirmation first.
- **A failed model is kept** with ✗, for the user to debug from its folder and log.

### Rebuild (`r`)
```
┌ Rebuild plate_static_v2? ──────────────────────────┐
│ All files in models/plate_static_v2/ will be       │
│ deleted and re-copied from its objects.            │
│                                                    │
│        [ Cancel ]        [ Wipe and rebuild ]      │
└────────────────────────────────────────────────────┘
```
Cancel is the default. The wipe keeps `logs/`, then the build flow runs from step 1 (skipping step 2).

### View log (`v`)
Shows the newest `logs/build-*.log` in a scrollable full-screen viewer.

### Edit (`e`)
Full screen: **name**, **description** and **parameter values**. The analysis and geometries are read-only. Renaming moves `models/<name>/`.

### Delete (`d`)
Removes the model from the database. The folder goes to **trash** (default) or is **deleted permanently**.

### Sweeps (later)
`s` is reserved. Sweep-generated models would be grouped under a collapsible heading in the list.

---

## Software tab

```
┌ autosim · ~/Documents/simulations/project ───────────────────────────┐
│  1 Objects    2 Models   [3 Software]                                │
├─────────────────────────┬────────────────────────────────────────────┤
│ / filter                │ abaqus                                     │
│                         │ Build: .py → build(params) via scripting   │
│ > abaqus                │        .inp → *PARAMETER block added       │
│   fluent                │ Command   abq2024           ✓ found        │
│   mpcci                 │           (project override)               │
│                         │                                            │
│                         │ Used by   plate_with_hole, fsi_coupled     │
├─────────────────────────┴────────────────────────────────────────────┤
│ a add  e edit command  d delete  f find  q quit                      │
└──────────────────────────────────────────────────────────────────────┘
```

- **The catalogue** is defined in code: one entry per program (`abaqus`, `fluent`, `mpcci`). Names can't be edited. Each software's build setup is written separately in code, including which build file types it accepts and how each type is built.
- `a` adds an entry from the catalogue that the project isn't using yet.
- `e` edits the project's command override; leave it blank to fall back.
- `d` deletes; blocked while any object uses it.
- **Command lookup:** project override → config → catalogue default. The pane shows which one is in use and whether it's found on PATH.

---

## Helper commands

```
autosim [-f DIR]                  open the interface (the default)
autosim [-f DIR] init             create a project without opening the interface
autosim [-f DIR] list objects     print objects (or models) as a table
autosim [-f DIR] check            consistency + file check, prints problems
autosim [-f DIR] trash empty      permanently delete .trash/
autosim [-f DIR] rebuild <model>  rebuild from the shell
```

---

## Open questions

- **Builds (pending Abaqus testing):**
  - how Python (`.py`) builds are launched (e.g. `abaqus cae noGUI=...` with a wrapper that calls `build(params)`);
  - how parameters are passed in;
  - the same for Fluent and MPCCI.
- **File clashes in model folders:** two objects in one model with a file of the same name (e.g. both have `build.py`). Detect it at model creation, or use per-object subfolders if the software allows it.
- **Editing the config from the interface:** hand-edited for now. A settings screen would need `tomlkit` to keep comments when saving.
- **Windows support:** config location and paths.
- **Parameter sweeps:** later.
