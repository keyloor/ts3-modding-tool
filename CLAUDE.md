# Toy Story 3 Modding Tool — notes for developers and AI agents

A tool for modding Toy Story 3 Complete Edition (PC, Avalanche's Octane engine) without programming. Its first section
puts a user's humanoid model (rigged FBX, or OBJ) in place of a game character and builds texture replacement packs;
the explorer previews/exports sounds, while audio editing is planned. Author: keyloor (`kit/about.py`; the attribution must stay, see
`NOTICE.md`). `PLAN.md` (Spanish) has the phases and decisions; `CONTRIBUTING.md` the rules for contributions.

Users talk to the tool in Spanish or English; the maintainer works in Spanish.

## Layout

| Path | What |
|---|---|
| `kit/about.py` | Name, version, author, credit line |
| `kit/paths.py` | Finds `tools/` (here, or next to the .exe when frozen) and puts it on `sys.path`; `doc()` finds docs |
| `kit/automap.py` | FBX/OBJ skeleton → a converter map (bones) |
| `kit/autotex.py` | FBX/OBJ materials → `TEXTURES` / `MATERIALS` / `SKIP_MATERIALS` |
| `kit/objlib.py` | OBJ reader + automatic skeleton and weights; `open_scene()` stands in for `fbxlib.Scene` |
| `kit/kit.py` | The commands (`characters`, `make`, `install`, `restore`, `export`) and the functions the window calls |
| `kit/app.py` | The window (tkinter; texts in `TEXT`, `es` and `en`) |
| `kit/viewer.py` | Live 3D preview: reads a converted character, skins it on the CPU (poses, live adjustments), draws it with moderngl offscreen into a tkinter label |
| `kit/gltf.py` | Read-only GLB export: compact primitives, embedded diffuse maps, static/skinned separation and pivot-based rest skeleton |
| `kit/gltflib.py` | Bounded glTF 2.0 Scene adapter; local/base64 resources, transforms/skin and project-owned PNG extraction |
| `kit/explorer.py`, `kit/explorercli.py`, `kit/explorerui.py` | Read-only asset index, inspection, extraction and previews; CLI and bilingual screen |
| `kit/build_kit.py` | PyInstaller build: `release/<TOOL> v<VERSION>/` + zip, or `--local` (test copy in Start Menu/Programs + shortcut; `--desktop` is an alias) |
| `kit/loader.py`, `kit/loaderui.py`, `kit/loadercli.py` | Player application; no authoring imports. Uses the same modstore/modfile/modupdate as the Tool. |
| `kit/gamepaths.py`, `kit/loaderprefs.py` | Standard-library game discovery and merge-only game/language settings for the Loader |
| `kit/pack/` | Templates of the exported Nexus pack: `README_tool.txt` (installed with the tool), or with `--installer` `installer.ps1`, `action.bat`, `README.txt` |
| `tools/` | Game formats and the converter (below) |
| `docs/` | `GUIA_MANUAL.md` (manual workflow, Spanish), `AGENTS.md` (for users' AI agents), `ejemplos/`, `CREDITS.md` |
| `skill/ts3-modding-tool/` | Skill for users' AI agents; keep its commands in step with the real ones |

Run with Python 3.12 + numpy + Pillow, always `python -I` (each script puts its own folder on `sys.path`).

## Decisions

- The tool is a layer on top of `tools/`. A change in `tools/` must not change what it produces for maps that already
  work (other mods built on it depend on byte-identical output): new behaviour is an option whose default is the old.
- Two levels: the automatic map is a normal map `.py`, so advanced users edit it by hand with every converter option;
  the window has an "advanced mode" that converts with the map as it is.
- Write our own code. The Disney Infinity community repos (DisneyInfinityTools, DisneyInfinityCreator) were read as
  documentation only.
- GUI in tkinter (ships with Python), packaged with PyInstaller (onedir, windowed).
- Never ship game files or other people's models; packs carry only the mod's files per archive.

## Game formats (all little-endian)

- **Archives** (`.zip`): end record + central directory at the front, the files, directory + end record again at the
  back; every directory entry has an extra field `KF` (0x464B, 19 bytes) = `"MD5"` + MD5 of the unpacked file.
  `tools/install.py` writes them byte for byte like the game; the pack's PowerShell `Write-Zip` must stay
  byte-identical to it (the manifest's "MD5 after install" is computed with the Python writer).
- **`.oct`** (`tools/octlib.py`): 0x3C header (magic 0x45017629, f32 1.1, name-table size, data size, record count),
  NUL-separated names, records `u16 flag, u16 name` + payload; type `flag & 0x3FF`, level `flag >> 10`, pre-order
  tree. Pools: `TexturePool` (DDS, `DataCRC` = crc32), `MaterialPool`, vertex/index buffer and stream pools,
  `SceneComponentPool` (`SkinRemap`), `SceneTreeNodePool` (bones, geometry, `SubGeometryLit` pieces). The animation
  network (`SubNetworkPool`) is never touched.
- **Mesh** (`tools/ts3model.py`): stream 0 = pos f32x3, bone indices u8x4 (into the piece's remap), weights u8x4
  summing to 255, uv f16x2 (v from the top); stream 1 = tangent/normal/binormal f16x4. u16 indices. Bind pose: Y up,
  facing +Z, metres, the character's left at +x.

## The converter (`tools/convert.py`)

Driven by a map (tables: `TORSO`, `LANDMARKS`, `SCALE_JOINTS`, `FACE_ALIGN`, `DRIVE`, `WEIGHTS`, `TORSO_SCALE`, `GIRTH`,
`JOINT_POS`, `WEIGHT_SMOOTH`, `SCALE`, `EYES`/`EYE_MODE`,
`KEEP_PIECES`, `MATERIAL_EFFECT`, `TEXTURES`/`MATERIALS`, ...; `docs/GUIA_MANUAL.md` §4 explains each). It fits the
model onto the game's bind pose (overall scale, torso block, each `DRIVE` limb turned and stretched onto its game
pivot, other bones follow their driver), maps weights to game bones, splits pieces of ≤40 bones, and rewrites the
`.oct` pools (new pieces, one material cloned from `MATERIAL_EFFECT`, 3 textures per set). Game characters are T-posed
in the bind pose but animated with the arms down: shoulders can look right in previews and wrong in game.

## Automatic map (`kit/automap.py`)

Finds the body by shape, in the game frame, from skinned bind positions:
- feet = lowest bone per side; hands = from the most lateral bone up to the first bone with 3+ branches (or 2 within
  15% of the height); hips/chest = common ancestors of the feet/hands; neck/head = the biggest non-arm branch of the
  chest, followed down to a bone named "head" or with 3+ branches;
- legs: hip = first bone below the hips, knee = nearest half way to the foot, toe if it points forward; arms: a
  clavicle only if short next to the arm, elbow = nearest half way to the hand; fingers: thumb nearest the wrist, then
  by name or front to back; held props (`prop`, `weapon`, `staff`...) are never fingers;
- game bone names are resolved per character (`ClavicleLeft`/`SternumLeft`, `Index1Left`/`IndexLeft1`, case-blind);
  accessories (`Hat`, `Holster`, `Hair1`, `WingLeft1`) by name words + side; helper bones on a joint take its bone;
- face bones stay on `Head` (`FACE = False`); every skinned bone gets an explicit `WEIGHTS` entry;
- `MATERIAL_EFFECT` per character (`material_effect()`: Jessie lacks Woody/Buzz's skin shader);
- `overrides` {role: bone} (the window's bone table, `ROLES`) replace what is found, with ancestry checks;
- `adjust` {'torso': [x, y, z] %, 'head_pct', 'neck_pct', 'arms_pct', 'legs_pct'}: written as `TORSO_SCALE` and
  `GIRTH` (head = its size; arms = shoulder + elbow bones, legs = hip + knee); `measure_torso()` reports the block
  scale the converter fits on its own;
- `adjust` {'head_cm'}: the head's `DRIVE` `offset` and the neck's `tip_offset` (same y, metres). `measure_neck()`
  compares the model's neck at the converter's scale (least squares over `SCALE_JOINTS`, as `convert.fit`) with the
  game's and gives the stretch and the offset that keeps the model's own length (window: Adjustments tab).

- `adjust` also takes `props` {model bone: hand_left | hand_right | head | chest | hips | out} (`extra_bones()`
  lists the candidates: skinned bones that are no body joint, face or helper; `PROP_PLACES`), `garments` {material:
  percent} (→ `MATERIAL_SCALE` (k, 1, k)), `weights` {model bone: game bone | {game bone: share}}, `smooth` (→
  `WEIGHT_SMOOTH`), `eyes_open` {top, bottom} (→ `EYES` from `eye_bones()`, by name, `EYE_MODE` 'rotate'), `face`
  (→ `FACE`), `head_by_face` (→ `FACE_ALIGN` from the face bones + `face` / `aim_face`), `scale_pct` (→ `SCALE`),
  `stretch_limit` {neck | arms | legs | hands: L} (→ `max_stretch` / `min_stretch` on those `DRIVE` bones),
  `shoulders_cm` / `hips_cm` (→ `offset` + `tip_offset` in x on the arm / leg `DRIVE` bones); an FBX's moved joints
  (`objlib.JOINTS`, model bone names) replace `sk.pos` and are written as `JOINT_POS`. Absent keys write nothing
  new: the map stays byte-identical (checked on 7 rigs). `kit.ADJUST_KEYS` documents them; `kit.py adjust`
  edits them and `--info` reports the choices.

- A model it can't use raises `ModelError(problem, detail, **info)` (never a bare exception): `kit.model_error()`
  turns it into `KitError` code `invalid_model` with `kit.MODEL_HELP`'s English fix, and the window shows its own
  words (`TEXT[...]['model_errors']`, title "Invalid model"). A new failure in the body search gets a problem id
  and text in all three (`tests/test_model_errors.py` checks they match).

Regression check after changing it: generate maps for a few different rigs and diff the reports before/after.

## Textures (`kit/autotex.py`)

Material → the image the file links, else a diffuse image sharing a name word (with `SYNONYMS`), else the only image,
else the material's colour if not white/grey, else the biggest set marked `CHECK`. Normal/ORM/spec images pair by the
same name but the kind word; a spec image becomes `mask` + `mask_spec`. Repeated meshes (same points in any order) are
left out. `overrides` {material: image | [r, g, b] | 'skip'} come from the window.

## OBJ (`kit/objlib.py`)

No skeleton in the file: it is turned Y-up / facing +Z (thinnest axis, feet forward), put on the floor and centred;
`landmarks()` measures, with cuts through the mesh (edges crossing a plane, so long low-poly triangles count), the
crotch (lowest triangle crossing x = 0), each shoulder (`arm_landmarks`: vertical cuts from 70% of the fingertip's
reach inwards, tracking the arm's centre, until the cut spreads over 2.2 arm thicknesses; a drooping hand doesn't
tilt it) and the neck (narrowest horizontal cut above the shoulders); the neck and head joints take the game
character's own fractions of the shoulder-to-narrowest span (`narrowest()` on its mesh); `rig()` stretches the game
character's skeleton onto that (game proportions along each limb) and weights each vertex 1/d⁴ to the 3 nearest bone
segments of its side and region. `use_game(dir, base)` must be called before opening an OBJ (automap and kit.build do).
Checked against real rigs exported as OBJ: joints within 1–6% of the height.

## Commands and projects (`kit/kit.py`)

A project folder holds `kit_project.json` (character, model, textures, game, the window's choices), `game/<c>/` (the
character extracted from the game's original archive), `map.py`, `out/<c>/`, `previews/`, `report.txt`.
- The game is found through Steam (registry + `libraryfolders.vdf`).
- `find_original()`: `ORIGINAL` holds the MD5 of the shipped woody/buzzlightyear/jessie archives; the original is
  taken from the tool's backup (`<game>/TS3 Modding Tool backup/`), the live archive, or any other installer's
  `<game>/* backup/` folder. With none, `make` refuses unless `--force`. Extractions are tagged
  (`game/<c>/.ts3tool_source`) and redone when built on a modded archive and an original turns up.
- `build()`: map (kept as is unless remapping), convert (the previous `out/` moves to `out_prev/`), check the
  `.oct` reads back byte for byte, previews (+ `compare.png` when there is a previous conversion).
- `diagnose()` (command `diagnose`, the window's Diagnosis tab): findings {id, level, message, args, fixes: [{label,
  set}], see} from the measurements (neck, torso), `strain()` (parts at their stretch limit), the materials marked
  CHECK, the skeleton (backwards, eyes, face, held props); `merge_adjust()` applies a fix; `limit_step()` keeps
  suggested limits on the window's 0.05 steps. The window has its texts per id (`diag`, `diag_fix`).
- `adjust` (command): the Adjustments from the CLI (`ADJUST_KEYS`, `check_adjust`, versions in
  `adjust_versions`, `adjust_info` = what the window's tab shows, `strain()` = stretch per game bone).
- `export_pack()` builds the pack with `tools/build_release.py`: `patches/`, `mod.json`, `README_tool.txt` (no
  scripts: players install it with the manager, and Nexus doesn't quarantine it). `installer=True` (`--installer`)
  adds `kit/pack/`'s installer instead (UTF-8 BOM + CRLF for PowerShell 5.1; `@@WHAT@@` escaped for single quotes).
- The `.exe` takes the same commands (`app.main` forwards them; output in `report.txt` and `%TEMP%`).
- `main()`: every command returns its data; `--json` (stripped from argv wherever it is) prints one envelope
  like `modcli`'s (`command` = `kit.<cmd>`) with the command's stdout sent to stderr. `KitError.code` names the
  refusal (from `KitError.CODES` by message when not given); exit 0 / 2 / 3 / 5 / 130. A new command returns a
  dict and prints its text only when `not a.json`.

## 3D preview (`kit/viewer.py`)

`Character(dir, base)` reads every piece of a converted `.oct` with each vertex's game bones (remap BoneIDs →
bone index) and weights, the diffuse maps and the skeleton. `pose(turns, shapes)`: turns (axis/degrees, 3x3 about
the pivot, or 4x4) chain down the skeleton (pre-order), shapes (4x4) change only that bone's vertices; linear blend
skinning in numpy (~6 ms for 7k vertices). `live_adjust(ch, applied, now)` turns the Adjustments' values into
turns/shapes relative to the ones the model was converted with (head move/size, neck stretch, limb girth across
the bone's segment, torso block scale about the landmarks) — an approximation; converting gives the exact result.
`SourceModel` is an OBJ before converting (corners as vertices, its `.mtl` images) with its automatic skeleton; in
the window's joints mode `View.on_joints` is set: a left click within 14 px of a joint drags it across the screen at
its depth (mirrored to its Left/Right twin when `mirror`), and the release reports {bone: position}, saved as the
project's `joints` → `objlib.use_joints()` → `rig(joints=...)` replaces those joints before weighting.
`SourceFBX` does the same for an FBX: its merged meshes and the body joints (roles from the Bones tab), named
by role so mirroring works; `keys` maps roles back to model bones and `unit` scales files in cm to about 1.8 m
for the view (the app divides it out when saving). `Character.K` is one number per vertex the shader colours by
(`View.colour_mode` 1 = red over the texture, `strain()` from `kit.strain(work)`, the report's stretch lines;
2 = heat, `bone_weight()`).
`View(label)`: standalone moderngl context, framebuffer read back into the label (~12 ms a frame); mouse orbit/pan/
zoom; optional game original (grey) and skeleton lines. Without OpenGL 3.3 `available()` is False and the window
shows the still images. `kit.py doctor` reports it.

## The window (`kit/app.py`)

Start screen (game, workspace `<Documents>/Toy Story 3 Modding Tool/`, sections, recent projects, new project) and a
project screen in 4 steps (pinned Woody / Buzz Lightyear / Jessie, model, convert, install/export/restore), tabs Bones,
Materials, Adjustments (pages: head and proportions, accessories and clothes, eyes and face, weights; undo / redo
keeps snapshots of `adjust_now()`, versions), Preview (3D, images, weights, joints; stretch in red; beside it the
game's original or the previous conversion), Log. Work runs in a thread (stdout → Log tab); a spinner shows while busy. Settings in
`~/.ts3_modding_tool.json`; the env var `TS3TOOL_SETTINGS` points it elsewhere: use it in tests so a user's own
settings are never touched.

## Checks

No unit tests: `tools/rt.py` byte-exact, the previews (look at them), byte-identical output of `tools/` for existing
maps, and testing in the game. Never claim something works in game before someone has seen it there.

## Every feature from the CLI too

Anything new a user can do in the window must also be possible from the command line, without a window, so an AI
agent can do it: a `kit.py` command or option (the mod manager's: a `mods` subcommand in `kit/modcli.py`, with
the JSON contract of `docs/CLI.md`), or a documented key in `kit_project.json` that `make` reads. Document it in
`docs/CLI.md` or `docs/AGENTS.md` and in the skill, and test it in `tests/`. Only seeing things (the 3D view) is
exempt; give the agent images instead.

## Git

Commits carry no `Co-Authored-By` or other AI attribution line: the maintainer is the author.

## Next work

0.2 released on GitHub (03/11/2026). Conflicts are checked before merging a patch: a pack over another's OCT is
`file_conflict`, never `external_change`. Manager refusals reach the window through `App.mod_error_text`.

Priorities (03/11): `modlayers.py` implements optional `Store.preview/install(..., layer=True)` and
`preview_order/order(ids, expected=...)`; default CLI installs still refuse new shared targets without --layer.
Registry v1 stays readable/unmodified until a confirmed layered operation migrates it to v2. Each row retains
baseline before, composed after, kind(file/archive) and SHA-256 payload of its standalone output. The mods list
is lowest-to-highest order. `modpriorityui.py` shares reorder/review dialogs across Tool/Loader. GUI installation
reviews layers; new mods append, replacements retain position; removal replays remaining snapshots. Distinct ZIP
members compose, a matching member/OCT wins whole; per-texture OCT merging is the next D slice, then resolution.
All transitions use existing _commit/journal; tickets bind full old/new registry, payload hashes and current bytes.
Verification checks composed file and all participating payloads. Dependencies/declared conflicts/external guards
remain. Migration may need extra snapshots, capped at 2 GiB new data and rebuilt content per operation. Loader
ships these stdlib modules too, without authoring dependencies. Test test_layers.py [--loader|--exe CLI] and
test_loader.py cross-app priorities. Never edit/migrate the user's installed registry manually for testing.

Explorer audio: `kit/audiobank.py` bounds RIFF/FSB5 inspection, PCM16 decoding, isolated native decoding,
WAV export and explicit WinMM playback. `audio_worker.py` uses only the selected game's FMOD 2.03 DLL;
never redistribute it. Frozen workers enter through `TS3 Modding CLI.exe _audio-decode` (private protocol).
Public CLI: `explore audio PATH --track N --seconds N --out NEW_DIRECTORY [--play]`.
Tests: `tests/test_audio.py [--exe CLI]`; no game files/runtime/audio device needed by synthetic checks.

Local testing preference (02/11/2026): after a finished change, `python -I kit/build_kit.py --local` updates
`%APPDATA%/Microsoft/Windows/Start Menu/Programs/Toy Story 3 Modding Tool/` and its sibling shortcut.
The user moved the build there; do not recreate the Desktop copy. Run visual tests on the secondary monitor.

Since 02/11/2026, the same build also produces **Toy Story 3 Mod Loader** in its own sibling Programs folder
and shortcut. `build_kit.py` without flags produces two ZIPs for a requested release. The Loader has its own
`TS3 Mod Loader CLI.exe`, with the same mod CLI protocol. No NumPy/Pillow/ModernGL in its bundle. Keep the
registry path `<game>/TS3 Modding Tool/` unchanged: both products share it and its recovery journal/backups.
Game discovery is in `gamepaths`; kit.find_game wraps its failures as KitError for backward compatibility.
Loader settings use the existing TS3TOOL_SETTINGS/default file, merging only game/lang and preserving recents.
Tests: `test_cli.py --loader` (source), `test_cli.py --exe <Loader CLI>`, and `test_loader.py [--exe <Loader CLI>]`.
The last checks cross-app installation/removal and that authoring/image dependencies do not load.

Same-ID replacement: `Store.preview/install(..., replace=True)`; CLI `mods plan/install --replace`.
GUI review shows `replaces` metadata and `restores` retired paths. `_prepare` reads retained targets from
the original backup, keeps that baseline in the installed record, and separately tracks current bytes for
transaction expectations/tickets. Existing dependents must accept the new version. Never implement updates
as a separate remove/install pair. `tests/test_replacement.py` covers archives, restoration, rollback,
recovery, races, backup corruption and dependents. CLI and cross-app tests also cover replacement.
`TS3TOOL_GEOMETRY` overrides initial window geometry for isolated secondary-monitor UI tests in both apps.

Implemented first slice: `kit/modfile.py` (schema 1 + folder/ZIP packages), `kit/modstore.py`
(transactional install/remove, exclusive target ownership, recoverable journal), `kit.py mods`
commands, and `mod.json` in exports with a stable project ID. See `docs/MOD_FORMAT.md`.
Run `python -I tests/test_mods.py` and `python -I tests/test_adjust.py`: synthetic tests, no game files or user settings.
Backups in `<game>/TS3 Modding Tool/objects/` are SHA-256 addressed; never delete them manually.
Done since: the console CLI (`kit/cli.py`, `kit/modcli.py`, `TS3 Modding CLI.exe`), the "Installed mods"
screen with review and drag-and-drop (`kit/dropfiles.py`: `WM_DROPFILES` through a window subclass, no extra
dependency), and update checks (`kit/modupdate.py`: GitHub's latest release for `update.github`, once a day per
repository, cached in `<game>/TS3 Modding Tool/updates.json`; the window's list reads only the cache, its
button and `mods updates` ask GitHub; never downloads). A and B are done. C now has a working first version;
D has multi-archive workspaces and shared DDS edits; E exports GLB and reads GLB/glTF as normal character inputs.
Original-skeleton character reinsertion is explicit; bounded rigid same-topology workspaces are available.
Unrestricted static object/level reinsertion remains pending.

Texture workflow: `kit/texpack.py` dumps PNGs + `index.json` for up to 256 archives (or one selected OCT), then builds a
data-only patch pack from changed PNG hashes. `kit/ddsedit.py` keeps the source DDS header/dimensions/mip count
(DXT1/3/5 or byte-aligned 32-bit RGB(A)); it does not resize. Validate the source archive/OCT/texture hashes
before encoding. Exports/builds never install; use the existing manager. No shared-archive priorities yet.
The GUI workspace UUID gives repeated exports a stable mod ID; the CLI takes `--id` explicitly.
`textures dump A.zip B.zip --shared` groups only byte-identical DDS occurrences in selected archives;
one PNG in shared/ uses CRC32 plus full SHA-256. Separate edits are the default. Schema 2 records archives,
editing mode and per-row archive; schema 1 is normalized only in memory and remains readable. Never group by
CRC or texture name alone. All selected source hashes must match before building; only changed archives
enter the pack. Stage every archive before publishing output, and keep the one-mod-per-archive constraint.
The GUI offers Export multiple ZIPs and an unchecked-by-default shared editing option.
`kit/texturecli.py` uses the standard JSON envelope. Test with `python -I tests/test_textures.py`, also `--exe`.

GLB export: `Browser.export_glb` / `explore glb` creates model.glb, report.json and README in a new folder.
`GameModel.skin_mask` tracks actual skinned vertices so static pieces never acquire the first bone's weights.
`bone_ids` preserves OCT BoneID in glTF extras. Mesh skin nodes are scene roots. Joint nodes use local pivot
differences and column-major inverse translations (not original bone rotations/roll). Diffuse maps are decoded
at source resolution, one at a time, with `_texture(..., limit=None)`; preview downsizing is unchanged.
Original-skeleton reinsertion is optional (below); no animations or full game materials. Source signatures include loose buffers.
Tests: `test_gltf.py [--exe CLI] [--artifacts build/gltf-checks]` and `validate_gltf.cjs` (pinned dev-only
Khronos npm package; never bundled). Exported game assets stay outside git. Both apps still build locally.

GLTF input: objlib.open_scene routes .glb/.gltf to gltflib.Scene without global caching; .fbx/.obj retain their
existing routes. Meshes expose already-world/default-pose geometry with row-convention xf@xlink=identity.
Skin node transforms are ignored as glTF requires; joint globals and inverse bind matrices bake default pose.
UV V is flipped into the converter's bottom-left contract, then flipped back by build_vertices. Normal maps
and base-colour factors are read; PBR/animations are not carried over. Static/mixed character inputs fail early.
prepare validates generated PNGs under model-textures/<fingerprint> and refreshes automatic textures when
sources change; explicit user texture folders are preserved. `model-info FILE --json` has no game/file writes.
`--model` aliases --fbx; keep the project field named fbx for old project compatibility. SourceFBX preview uses
open_scene too. Tests: test_gltflib.py [--exe CLI], plus converter/OBJ/FBX regressions.
GLTF primitives may overlap intentionally: autotex skips its legacy duplicate-mesh heuristic only when the
scene declares deduplicate_meshes=False. Keep the FBX/OBJ default unchanged. Explicit --textures or GUI folder
selection clears the automatic-cache marker, including when the user selects an edited generated folder itself.

Original-skeleton mode (03/11/2026): `make --fit normal|identity`, persisted `fit_mode` (absent=normal).
`kit/identity.py` builds explicit IDENTITY maps and validates reused map modes without executing them;
`tools/identityfit.py` optionally verifies GLTF joint BoneIDs/exact names, unique mappings, pivots <=1e-5 m,
collapsed hierarchy and <=4 distinct influences. Unknown present IDs never fall back to names. Geometry,
winding and UVs stay at TS3 float32/float16 precision; rounded byte weights retain original 255-based weights.
The converter's normal path stays byte-identical; all new behavior is guarded by IDENTITY/identity=False.
Runtime checks loaded map mode too; identity preflight runs before rotating previous output. Original target
skeleton matrices/IDs/hierarchy and animation network stay. Counts/bounds, tangents, pieces and materials are
rebuilt; palette/explicit material edits can remap UVs. Do not claim a byte-identical archive/material roundtrip.
GUI step 3 selects mode, displays verified mappings and disables Adjustments/joint dragging/bone edits;
saved adjust/joints/bones are preserved but ignored. Live preview/diagnosis do not apply stale fitting strain.
Tests: test_identity.py [--exe CLI]. Woody's real geometry/UV/byte weights and original skeleton checked locally;
pack install/verify/remove restores an isolated game copy exactly. In-game and Blender visual checks pending.

Rigid editing (03/11/2026): `kit/meshpack.py`, `meshcli.py`, `meshes dump/build`, explorer buttons. One OCT
member inside a ZIP, <=250000 visible rigid vertices/512 MiB archive and buffers. `mesh.json` stores source
hashes/UUID; GLB `_TS3_VERTEX` float attributes map compact GameModel vertices back to original stream offsets.
`GameModel(...provenance=True)` records blocks/transforms/source vertices; default output is unchanged.
`gltf.encode(...vertex_ids=True)` is optional; gltflib exposes correspondence only when present. Ordinary
explore glb exports cannot reinsert rigid edits. Keep point attributes and triangles (Blender Mesh > Attributes).
Re-read live sources to derive offsets; never trust manifest offsets. Verify topology/multiplicity, split
vertex consistency and source hashes. Apply positions/normals/UVs in original local coordinates/storage formats,
rebuild tangent frames on incident faces, expand ancestor BoundingBox (never shrink); preserve other bytes.
Protect overlapping/hidden streams and conflicting shared-instance edits. Reject skins, position-only fallback,
unsupported bounding spheres/layouts and changed topology. GLB material edits are explicitly ignored;
materials/textures/indices/collisions stay. Collision shapes do not follow visual edits. Staged data-only
pack via existing texpack.patch_archive/manager ownership/backups. No direct game writes. Mesh pack ID from
workspace UUID in UI; explicit --id in CLI. Test `test_meshes.py [--exe CLI]`; actual small rigid Toy Box object
checked locally with exact fake-game restoration. New topology uses explicit replacement (below);
whole-level/collision editing remains pending.

Topology replacement (03/11/2026): optional `meshes build --topology replace`; default preserve remains.
GUI checkbox exists only for mesh-pack dialogs and defaults unchecked; texture-pack results remain three fields.
`kit/meshtopo.py` replaces one visible SubGeometryLit rigid piece, one input material; no scene-component refs,
unknown source attributes, variable padding/extra components or multi-UV layouts. Max 65535 vertices/1m faces
and original index width. Input GLTF Scene(correspondence=False) ignores obsolete/interpolated _TS3_VERTEX;
normal readers still validate it. New data appends aligned to existing buffers, cloned streams append to pools,
only the target's stream refs change. No node renumbering/deletion, no original buffer bytes removed/modified.
Materials/textures/collisions/hidden pieces stay. Bounds helper expands AABB, sphere radius and OBB extents,
retaining centers/axes and enclosing both orientation conventions; used by preserve mode too. Unknown combined
BoundingSphere records remain refused. Calculate replacement bounds after float32 position storage rounding.
Old preserve mode's attribute/tolerance rules stay. Tests: test_meshtopo.py [--exe CLI], test_meshes regression.
Actual Toy Box object subdivided with geometry growth, original buffer prefixes/materials/textures checked and
exact isolated-game restoration. In-game/Blender visuals, multi-piece/material/collision/level editing pending.

Compound selection: `GameModel(...provenance=True).source_pieces` maps OCT node IDs to compact triangles,
material and name. `meshes pieces WORKSPACE` or `meshes pieces ARCHIVE --member OCT` derives fresh visible
piece metadata and structural supported_layout/reason (padding/input checks still run at build).
`dump --piece NODE` writes a partial GLB/workspace with optional integer piece; it requires replace mode.
Whole-workspace preserve behavior stays. `build --topology replace --piece NODE` selects a visible node,
or uses the workspace default; auto requires one visible piece. New streams detach only that node even
when visible instances share a block. Runtime verifies target counts, whole-model triangle count, and
other visible pieces' positions/UV/materials. Reports distinguish per-piece and model counts. Query caches
OCT record/block lookups within a source snapshot, invalidated by record-count changes; no persisted offsets.
GUI performs fresh source reads in App.run, shows whole/partial export choices and a pack target combo;
partial workspaces preselect replace mode/node. Texture dialogs still return three fields. Mesh dialogs
return name/author/version/topology/piece. Old workspaces supported. Tests: test_meshselect.py [--exe CLI].
Real three-piece planter checked with exact isolated restoration and other two pieces unchanged.
PLAN's next phase: fix the sound decoder errors (40 of 71 real samples tried fail), then a more intuitive interface.
After it, D per-texture composition inside one OCT, then texture resolution; E remains partially complete.

Explorer: `Browser.index()` reads directories with `zipfile`, falling back to `FrontZip` for older TS3 archives
with a leading directory only. Cache in LocalAppData (beside `TS3TOOL_SETTINGS` when set), keyed by game and file
size/mtime/ctime. Never use cached offsets for reads. `export()` stages into a temporary sibling and publishes a
new destination folder outside the game; limits 512 MiB per asset, 2 GiB per archive. The window uses App.run;
OpenGL stays on the Tk thread. `viewer.GameModel(data, read)` reads any model of the game (it reads each stream's
`Elements`, places rigid pieces with their nodes' `LocalToParentMatrix`, row vectors; a skinned piece is in model
space); position-only and hidden pieces only show when a file has nothing else; `bounds()` frames the bulk of the
vertices when sky and clouds are far bigger (`full_bounds()` is everything). `snapshot()` draws PNGs with no GPU:
a lattice finer than a pixel per triangle, in numpy. `Character` stays for skinned characters and the project's
Preview. Textures are reduced when a model has many (256 px over 120 materials); alpha counts as a cut-out only
when many pixels are clear and many solid (others keep gloss in it). `View` redraws on `<Configure>` only when the
size really changed: showing the image fires it again, which otherwise draws for ever. `explore list` paginates; new commands use the standard JSON envelope. Test with
`python -I tests/test_explorer.py` (also accepts `--exe`). No game files in fixtures.

`PLAN.md` §10, "Cómo hacerlo": the plan (in order A–E) for a common mod format, drag-and-drop install and
removal, a game explorer, texture dumps / folder texture packs, and glTF export / re-import. Read it before starting.
