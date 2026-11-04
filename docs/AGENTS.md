# TS3 Modding Tool: instructions for AI agents

*TS3 Modding Tool by keyloor.* In a release this file sits at the kit's root; `<KIT>` is that folder (it holds
`kit/`, `tools/`, `docs/`). Read it fully before helping a user put a model into Toy Story 3. The user-facing guides
are `docs/GUIA_MANUAL.md` (manual, every map table explained) and the skill in `skill/ts3-modding-tool/`.

## What you are doing

The Tool home has six equal task cards. Character projects moved to Open characters, with new/open actions
and a read-only recent-project list. Textures, Models and objects, and Music and sounds open the existing
Explorer with a task title and initial filter; language changes retain that context. These are navigation
changes only: use the existing make/explore/textures/meshes/mods CLI commands and project format.

Audio inspection: `explore inspect PATH --game GAME --json` lists `sounds[].index` from `.assets.bank` or dialogue `.fsb`.
`explore audio PATH [--member NAME] --track INDEX --seconds 30 --out NEW_DIRECTORY --game GAME --json`
exports `sample.wav` (PCM16 mono/stereo) plus `audio.json` without changing the game. Maximum 120 seconds;
read `truncated` and `decoded_seconds`. Add `--play` only when listening is wanted; Ctrl+C stops playback.
Compressed samples require the selected game's existing Windows FMOD 2.03 DLL and matching architecture;
it is not redistributed. Event-only banks return no samples: use their `.assets.bank` companion.
These are sample excerpts, not simulated events/spatial mixing or audio replacement packs.
The offline decoder fixes v0.2's streaming-mode failures. Native diagnostics are in optional `error.details`;
GUI failures are localized. For full real-game validation, run the opt-in `tests/check_game_audio.py --game GAME
--out NEW_REPORT_DIRECTORY`; it decodes all loose banks/samples up to 120 seconds and checks source SHA-256.

For players, prefer the separate Toy Story 3 Mod Loader. Its `TS3 Mod Loader CLI.exe mods ...` and
`kit/loadercli.py mods ...` use the same protocol, registry and backups as this Tool. Never migrate or clear
the registry when switching apps. The Loader has no character/texture/explorer commands; use the Tool for those.

Texture editing: `kit/cli.py textures dump ARCHIVE [--member OCT] --out NEW_WORKSPACE --game GAME --json`
exports individual PNGs and `index.json`. Edit only the requested PNGs at their original size, then
`textures build WORKSPACE --out NEW_PACK --id ID --name NAME --author AUTHOR --game GAME --json`.
Use the user's mod name/credit and keep the ID for later versions. Building does not install; use the existing
manager's plan/install workflow within the user's authorized scope. Read `data.errors` and the workspace's
`editable` flags. A changed source requires a fresh export. Keep exported game images local; share only the
resulting mod pack when the user has authorized publication and has rights to any included modded source.

For repeated textures, `textures dump ARCHIVE [ARCHIVE ...] --shared --out NEW_WORKSPACE` exports one PNG
for each byte-identical DDS across the selected archives. Editing that PNG updates all matching occurrences
listed in index.json; this scope is explicit and does not search unselected archives. Without `--shared`,
each occurrence remains independent. `--member` requires a single archive. Both schema-1 and schema-2
workspaces build with the same command; reports distinguish PNG images, texture occurrences and archives.
See `docs/CLI.md` for formats, limits and shared-archive priority behavior.

Shared targets: review/install with `mods plan/install PACKAGE --layer` (combine with `--replace` for a
same-ID update). `mods order` reads the installed order; `mods order ID... --dry-run` reviews all IDs once,
lowest to highest priority, and `mods order ID... --expect TICKET` applies it. Last wins on matching ZIP
members or whole files. Distinct patched members combine; a matching OCT is replaced whole, without
per-texture merging. New mods go last; replacements keep position; removal rebuilds remaining layers.
Packages/JSON protocol stay schema 1. Installed registries migrate to schema 2 on confirmed layered changes,
keeping originals and layer payload snapshots; use current Tool/Loader versions. Never reset/migrate manually.
Inspect `shared`, `order`, and `files` before applying. External edits, dependencies, declared conflicts,
backup validation and recovery remain enforced. Keep plans bound to tickets; hidden-layer changes invalidate them.

For read-only game exploration, use `kit/cli.py explore list --game GAME --query TEXT --kind oct --json`.
`explore list --playable [--kind sound]` filters to loose banks with sample headers; plain list retains events
and unverified files. `audio_samples` is an index hint, not playback validation. Indexing reads only bounded
headers and seeks over audio payloads. GUI Sounds uses the filter; View restores technical files. The GUI now
groups readable names but keeps original paths, Edit/More contextual actions and Create mod for workspaces.
Use More → Technical details for raw metadata/errors. CLI paths and the existing query contract are unchanged.
File extensions always remain visible in names and the Format column. The GUI Preview column distinguishes format hints from unchecked OCT/ZIP
content and records the actual result after opening; refresh resets observations. Do not promise model geometry
solely because a file ends in `.oct`. CLI inspect/preview/audio still perform their own validation.
Completed GUI exports/builds show Open folder for `output`; new selections/previews and failures clear the action.
This does not install a pack or execute its contents. CLI output paths and validation remain unchanged.
For an export to Blender, use `explore glb PATH [--member OCT] --out NEW_DIRECTORY --game GAME --json`.
Read `report.json`/`data.warnings`: the GLB exports supported geometry, UVs, diffuse maps, pivot-based rest
skeleton and skin weights, while keeping rigid pieces outside the skin. Original bone rotations/roll,
game shaders and animations are not reconstructed. Rigged character GLB/glTF files can use normal fitting
or explicit original-skeleton reinsertion (`--fit identity`). Bounded rigid object editing uses a separate workspace below.
Keep game exports local; do not publish them or treat export/validator success as in-game verification.

GLB/glTF input: `model-info FILE --json` validates/inspects the selected scene without a game or extraction.
Use `make PROJECT --model FILE --character CHARACTER --game GAME --json` to convert a rigged humanoid with
every mesh skinned. Normal fitting is applied; do not describe it as an identity roundtrip. Static/mixed
meshes are refused before conversion. Textures are prepared under project/model-textures/<content-hash>;
source changes refresh generated textures, and edited generated files are preserved/refused until their
folder is explicitly selected with --textures. Read warnings/diagnosis. Only local resources inside the
model directory or base64 are supported; see docs/CLI.md for extension, skin, image and accessor limits.

For an edited export of the same TS3 character, use `make PROJECT --model FILE --character CHARACTER
--fit identity --game GAME --json` (window: Preserve original skeleton). It verifies unique BoneIDs or exact
names, rest pivots within 0.00001 m, hierarchy and at most four distinct skin influences per vertex.
Keep the rest pose/armature; new or moved bones are refused. It preserves edited geometry at the game's
float32/float16/byte-weight precision while retaining the original target skeleton/animation network.
Saved proportion/joint/bone adjustments are inactive; materials/textures are still rebuilt. Do not call
this a byte-identical archive or full material roundtrip. `fit_mode` persists; default/`--fit normal` uses
the existing humanoid fitting. Switching mode with an existing map requires `--remap`; preserve hand edits
first. Read `make.data.fit_mode`, previews and `adjust --info`'s verification report. See docs/CLI.md.

Rigid objects: `meshes dump ARCHIVE --member OCT --out NEW_WORKSPACE --game GAME --json` creates an editable
GLB plus mesh.json. `explore glb` exports do not contain its correspondence. Edit positions/normals/first UVs
without changing triangles or dropping `_TS3_VERTEX` (Blender export: Mesh > Attributes). Build with
`meshes build WORKSPACE [--model EDITED_GLB] --out NEW_PACK --id ID --name NAME --author AUTHOR --game GAME
--json`. The default model is workspace/model.glb. Keep ID stable; install via the existing manager when
authorized. Retains materials/textures, indices, unknown data and collisions; **collisions do not follow
shape edits**. Bounds expand; shared/hidden buffer conflicts, changed topology and missing IDs are refused.
Only rigid visible geometry, one OCT/ZIP, <=250000 vertices; no arbitrary new objects/levels or collision
editing. Read report.json/README and docs/CLI.md. Treat editor and in-game checks as still separate.

To add/remove rigid geometry explicitly, use `meshes build WORKSPACE --model FILE --topology replace`
with the usual output/ID/name/author/game arguments. Select one visible lit rigid piece; compound sources
require an explicit node. Replacement must be unskinned and use one material. No `_TS3_VERTEX` is needed. This appends separate
buffers/streams and switches only that piece's references, preserving original data, hidden aliases,
material/texture pools and collisions. Source attributes must be supported (no unknown per-vertex values
or variable padding). Limits 65535 vertices/1000000 triangles and original index width. Bounding AABB,
sphere and OBB extents expand conservatively. CLI/GUI default remains preserve. Read before/after counts
and use the normal manager review. This does not add source pieces/materials or update collisions/levels.

Compound rigid sources now support explicit selection: `meshes pieces ARCHIVE --member OCT --game GAME
--json` (or `meshes pieces WORKSPACE`). Select its `node`, not the displayed row number/name. Use
`meshes dump ARCHIVE --member OCT --piece NODE --out NEW_WORKSPACE` for a piece-only GLB, then build with
`--topology replace`; the workspace stores the target. Or pass `--piece NODE` on a whole-workspace build.
The replacement file must hold only the selected piece. Other visible/hidden/shared pieces, original
materials and collisions stay. Builds verify unselected visible geometry/UV/materials. `supported_layout`
is preliminary; padding/input checks still run. No selection on a compound source is `ambiguous_target`.
One selected piece per build, with original source-wide limits. See docs/CLI.md for JSON counts and UI flow.

Follow `data.next_offset` for more results. `explore inspect PATH --member NAME` describes an asset;
`explore preview PATH --member NAME --out NEW_DIRECTORY` writes PNG previews;
`explore extract PATH [--member NAME] --out NEW_DIRECTORY` extracts one asset or a whole ZIP.
Use a new output folder outside the game. Read `data.errors` from index/list for skipped files.
`inspect` gives a model's numbers (`data.model`: vertices, triangles, pieces, size); `preview` draws it as
`model.png` (levels also `model-top.png`), so look at those. See `docs/CLI.md` for limits. These commands read the currently installed
content, including mods; do not assume extracted files are the shipped originals. Never redistribute them.

For installing, inspecting, verifying or removing an existing mod package, prefer the
non-interactive CLI over driving the window. Read `docs/CLI.md` for the protocol and
`docs/MOD_FORMAT.md` for package constraints. Start with:

```text
python -I <KIT>/kit/cli.py mods capabilities --json
```

Without Python, use `<KIT>/TS3 Modding CLI.exe` with the same arguments after `cli.py`.
It returns UTF-8 JSON on stdout and meaningful exit codes. Use an explicit `--game` path,
inspect the package, prepare `mods plan`, and apply it with `mods install --expect TICKET`
within the user's authorized scope. `mods verify ID` checks installed files and backups;
`mods remove ID --dry-run` prepares removal. Tickets are bound to the operation and game
folder. A failed verification returns exit code 4 and includes its report in `data`.

The GUIs expose verification in both products with a shared readable report, including stored layer snapshots.
Session results can be reopened; refresh clears them. Raw diagnostics stay in Technical details. A health
warning must not be hidden by an update notice. Verification never repairs files or proves in-game behavior.
Loader details have Description/Files tabs; More holds View result and an available update page.
`mods updates` says which installed mods have a newer GitHub release (`url` = its page); it never downloads.
For a newer or rebuilt package with the same ID, use `mods plan PACKAGE --replace` and
`mods install PACKAGE --replace --expect TICKET` with the same explicit `--game` and `--json`.
Review `replaces`, `restores` and all `files`. This preserves the first installation's backups, restores
retired targets and checks dependent versions. A failed replacement recovers the previously installed mod.
Do not uninstall first to bypass external-change, damaged-backup or dependency failures.
Do not treat successful checks as proof of appearance or behavior in the game. The
character-conversion workflow below applies when creating or fixing a model, not merely
installing a package.

Replacing a Toy Story 3 Complete Edition (PC) character's mesh with the user's rigged FBX. The game keeps its own
skeleton, animations and animation network; the FBX mesh is fitted onto the game's bind pose, weighted to the game's
bones, split into pieces of at most 40 bones, and written into `<base>.oct` + `<base>_0.vbuf` + `<base>_0.ibuf`, which
go back into the game's `.zip`. Everything is driven by a **map**: a Python file of tables (see `GUIA_MANUAL.md` §4).

## The loop

Python 3.12 with `numpy` and `Pillow` (`pip install numpy pillow`); always `python -I`. One project folder per model +
character (e.g. `work/cj`); `kit.py` keeps its settings in `<project>/kit_project.json`.

0. If anything behaves oddly, `python -I <KIT>/kit/kit.py doctor` prints the versions, the game, which original
   archives it finds and whether the 3D preview works.
1. **Gather**: the FBX, its textures folder, which character. `python -I <KIT>/kit/kit.py characters` finds the game
   (Steam's folders; else ask the user and pass `--game`) and lists the characters, marking those another mod or the
   kit has changed.
2. **Inspect** the FBX: `tools/fbxinfo.py <fbx>` (meshes, materials) and `tools/bones5.py <fbx>` (bones in the game
   frame: Y up, facing +Z, character's left at +x). Stop and tell the user if there is no skinned mesh, if the left hand
   is at -x or the toes point to -z (it faces backwards: re-export), or if it is not a humanoid in a T/A pose.
3. **Make**: `python -I <KIT>/kit/kit.py make work/<name> --character woody --fbx <fbx> --textures <dir>`.
   It extracts the character, writes `map.py` (bones + textures), converts into `out/<character>/`, checks that the
   `.oct` reads back byte for byte, draws `previews/body.png` and `previews/face.png`, and writes everything it printed
   to `report.txt`. Read the whole report:
   - each side's leg (`hip > knee > foot > toe`), arm (`clavicle > shoulder > elbow > hand`) and fingers must name
     plausible bones; the head must be the skull bone, not the neck or a hat;
   - `CHECK in map.py`: materials no image matched by name, put on the biggest texture set. Open `map.py`'s
     `MATERIALS`, look at the images (you can view them) and the names, fix each one, or ask the user;
   - the converter's lines (meaning: `GUIA_MANUAL.md` §5). Red flags: landmark error > 0.05, a limb turned > 40° or
     stretched to 0.80/1.25, `the game has no bone`, many vertices without full weights.
   If it refuses because the archive "is not the game's original", another mod is installed on that character: the
   user must uninstall it with that mod's own uninstaller. `--force` builds on the modded files; avoid it.
4. **Look**: open both PNGs yourself before going on. In `body.png` the left half is the game's character, the right
   half the user's model: same height and stance, red joint dots inside the right limbs, textures on the right parts.
   `face.png`: the head from three sides; eyes open, mouth closed, nothing poking through. Show the user the images.
5. **Fix and repeat**: edit `work/<name>/map.py` (`GUIA_MANUAL.md` §4 tables, §7 common fixes, §8 closed eyes) and
   run `kit.py make work/<name>` again: an existing `map.py` is kept as it is. `--remap` writes a fresh one (and loses
   the edits). Keep each change small, re-run, look again; say what you changed and why. When you change a bone,
   `DRIVE`, `WEIGHTS`, `LANDMARKS` and `SCALE_JOINTS` name the same bones: change them together.
6. **Install** only when the user agrees and the game is closed: `kit.py install work/<name>`. The first install keeps
   the game's archive in `<game>/TS3 Modding Tool backup/`. Undo: `kit.py restore work/<name>`.
7. **Ask the user to play and send screenshots.** Never say it works in game before they confirm. The previews show
   the bind pose (arms out); the game animates with the arms down, so shoulders, armpits and loose clothes can only be
   judged in game. A wrong normal map also shows only in game (odd lighting): remove `n` from that texture set.

The user may also use the window (`kit/app.py`); it works on the same project folders. Its bone and material
choices are stored in `kit_project.json` (`bones`: {role: model bone, '' = none}, roles as in `automap.ROLES`;
`materials`: {FBX material: image file | [r, g, b] | 'skip'}) and apply whenever the map is written again
(`make --remap`). To change a body part's bone you can set them there instead of editing `map.py`.
`joints`: for an OBJ, {bone of the automatic skeleton, e.g. 'ForearmLeft': [x, y, z]} replaces that estimated joint
(coordinates in the OBJ scene's frame: Y up, facing +Z, on the floor, centred, the model's own units); for an FBX,
{model bone: [x, y, z]} moves that bone's joint for the fit (the file's units, Y up, facing +Z; `JOINT_POS` in the
map), the mesh and its weights stay. The window writes it from the Preview tab's "Your model's skeleton" mode.

Every `kit.py` command takes `--json` (anywhere on the line): one JSON object on stdout, `{schema_version, ok,
command: 'kit.<command>', data, error: {code, message}}`, the same shape as the `mods` commands; progress goes to
stderr; exit 0 ok, 2 bad arguments, 3 refused (codes in `docs/CLI.md`), 5 internal error. `make --json` returns the
previews' paths, the materials to check and the diagnosis, so read those instead of parsing `report.txt`.
`error.code` `invalid_model` means the model itself can't be used (`error.problem`: a skeleton in pieces, no skin,
not in a T/A pose, a missing joint, an unreadable file...); its message says how to fix the model. Tell the user
that in plain words; only a wrong Bones-tab choice (`bad_choice`) is fixed in the project.

**`kit.py adjust work/<name>`** reads and changes all of this without editing JSON by hand, then
`kit.py make work/<name> --remap` converts with it:
`--info --json` adds what the tool measured (neck, torso, how far each part was stretched in the last conversion:
`stretch` {game bone: factor}, 0.8 and 1.25 are the converter's limits) and what can be named (loose bones for
`props`, materials for `garments`, eyes and lids, face bones, every model and game bone, the body joints);
`--set KEY=JSON`, `--put KEY NAME=JSON` (one entry of `props` / `garments` / `weights`), `--unset KEY`,
`--drop KEY NAME`, `--joint BONE=X,Y,Z`, `--reset-joints`, `--save-version` / `--load-version` / `--delete-version`
NAME. Unknown keys and places are refused. The `adjust` keys (also in `kit.ADJUST_KEYS` and the JSON's `keys`):
`props` {model bone: hand_left | hand_right | head | chest | hips | out} (a loose object and what hangs below it
moves with that part, or is left out), `garments` {material: percent} (narrower / wider across, about the hips),
`weights` {model bone: game bone | {game bone: share}}, `smooth` (passes), `eyes_open` {top, bottom} degrees
(opens shut lids; needs eye and lid bones found by name), `face` true (jaw, lips and brows move with the game's),
`head_by_face` true (the head placed by the face bones), `scale_pct` (the whole model bigger / smaller; the joints
stay on the game's, so mostly the thickness changes), `shoulders_cm` / `hips_cm` (each arm / leg further out, cm),
`stretch_limit` {neck | arms | legs | hands: L} (that part may stretch to L and squeeze to 1/L; 1.25 is the default).

**`kit.py diagnose work/<name> [--json]`** says in plain words what looks wrong or could be better (a neck stretched
past the limit, a torso made much wider, parts at the stretch limit in the last report, materials with no image,
a model facing backwards, lid or face bones that could be used, a held object that doesn't follow the hand), each
with its fixes as `adjust` changes; `--fix ID [--option N]` applies one, then `make --remap`. Run it after every
conversion and tell the user what it found before changing anything they didn't ask for. Each conversion keeps the one before in `out_prev/` and
draws `previews/compare.png` (before, after).
`adjust` also takes proportions, in percent: `torso` [x, y, z] (written as `TORSO_SCALE`), `head_pct` (head size),
`neck_pct`, `arms_pct`, `legs_pct` (thickness; written as `GIRTH`). Lengths can't change: joints stay on the game's.
The report's `torso fit: W% wide, H% tall` says how much the tool already reshapes the torso.
`adjust`: {'head_cm': up (+) / down (-)} moves the head and the end of the neck from the game's head joint (the
window's Adjustments tab). The report's line `neck length: model X cm, game Y cm: stretched xZ ...; head N cm keeps
its own length` says when to use it: a stretch beyond 1.25 means a long, distorted neck; set `head_cm` to N.

To publish: `kit.py export work/<name> --name "<Mod name>" --version 1.0 --author "<user>" --what "<one line>"
--model-credits "<model author>"` writes `work/<name>/pack/<Mod name> for TS3/` and its zip: only the mod's changes to
the game archive (`patches/`), `mod.json` and a README with the credits. Players install it with the tool (drop it
on the window, or `mods install`); it holds no scripts, so Nexus doesn't quarantine it. `--installer` adds its
own installer (.bat + .ps1) for players without the tool; Nexus then reviews each upload by hand. Ask the user for
every field; never invent the model's author or permission.

Without Python, `Toy Story 3 Modding Tool.exe` takes the same commands (`"Toy Story 3 Modding Tool.exe" make work/<name>`); it has
no console, so read `<project>/report.txt` (and `%TEMP%\Toy Story 3 Modding Tool.log`).

`kit.py` only chains the single tools; for anything it does not cover, run them by hand (`GUIA_MANUAL.md`): `tools/zx.py`
(extract), `kit/automap.py` and `kit/autotex.py` (map), `tools/convert.py`, `tools/rt.py`, `tools/render.py`,
`tools/angles.py`, `tools/install.py`. Don't mix the two ways of installing: `tools/install.py` keeps its backup in
`<KIT>/game/backup/`, `kit.py` next to the game; restore with the same one you installed with.

## Facts you will need

- Game bone names differ per character: Woody/Jessie `ClavicleLeft`, `Index1Left`; Buzz `SternumLeft`, `IndexLeft1`
  (only the first finger joint), `MidddleBrow`; Jessie `eyeLeft`, `jaw` (lower case). Read the real names with
  `tools/ts3model.py work/<name>/game/<c> <c>`.
- Woody has no eye bones: its eyes must stay on `Head`. Buzz has `EyeLeft`, `EyeLidTopLeft`, `EyeLidBtmLeft`.
- Buzz's jetpack flames are a game piece: keep them with `KEEP_PIECES = ['JetPack_Flame']` (the automatic map does).
- OBJ models work too (`kit/objlib.py`): with no skeleton in the file, the tool estimates one from the mesh
  (crotch, neck, shoulders, fingertips) and the game character's proportions, and weights by distance. The report's
  bones are then the tool's own (`ThighLeft`, `BicepLeft`...). Check knees, elbows and shoulders in the previews; if
  they bend in the wrong place, the best fix is a real rig: Mixamo's free auto-rigger or Blender's automatic weights,
  exported as FBX.
- Basic maps keep the face on `Head` (`FACE = False`). Setting `FACE = True` animates jaw, lips and brows; check the
  mouth in game afterwards, because a model's mouth often sits lower than the game's face bones (`FACE_ALIGN`,
  `offset`).
- Many rips have their eyelids shut in the bind pose: `face.png` shows it. Open them with `EYES` (§8; examples in
  `docs/ejemplos/ts5_woody_ojos_cara.py` and `ts5_jessie_ojos_pestanas.py`).
- Texture sets: `d` diffuse, `n` normal (must share the diffuse map's UV layout), `orm` or `spec` (number) or
  `mask` + `mask_spec` (image), sizes as powers of two up to 1024. Every FBX material of a skinned mesh must be in
  `MATERIALS` (set name or `(r, g, b)`) or `SKIP_MATERIALS`, or the converter stops and names it.
- One mod per character archive: installing over another mod replaces it.

## Rules

- Do not ship, upload or send game files, or models the user has no rights to. Remind the user that publishing someone
  else's model needs its author's permission.
- Do not change files in `tools/` or `kit/` to make one model work; everything model-specific belongs in the map. If a
  tool really lacks an option, tell the user.
- Credit the tool as "TS3 Modding Tool by keyloor" in anything you prepare for publishing.
- When a step fails, show the user the last lines of the output and what you think it means before changing things.

## Going deeper

- Map tables, all options, examples: `docs/GUIA_MANUAL.md`, `docs/ejemplos/*.py` (real maps: eyes, lashes, face,
  several materials, colour palettes, split weights).
- How the automatic parts decide: the docstrings at the top of `kit/automap.py`, `kit/autotex.py` and `kit/kit.py`.
- Game formats (archives, `.oct`, vertex/index buffers): the appendix of `GUIA_MANUAL.md`; the most complete public
  documentation of this engine's formats is `FORMATS.md` in
  [DisneyInfinityTools](https://github.com/Kokonotcu/DisneyInfinityTools) (Disney Infinity runs on the same
  Octane engine; sections 2 and 3). [DisneyInfinityCreator](https://github.com/LucasLhomme/DisneyInfinityCreator)
  does for Disney Infinity 3.0 what this kit does for Toy Story 3. Read them as documentation; the kit does not use
  their code.
