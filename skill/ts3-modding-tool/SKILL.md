---
name: ts3-modding-tool
description: Create character replacements and manage mod packages for Toy Story 3 Complete Edition with TS3 Modding Tool by keyloor. Use for FBX/OBJ conversion, bone or texture adjustments, Nexus pack export, or inspecting, installing, verifying and removing existing TS3 mod packages through the CLI.
---

# TS3 Modding Tool (by keyloor)

The tool turns a humanoid model (rigged FBX, or OBJ: it estimates a skeleton) into the game's character files and puts them into the game's archive; the game's
skeleton and animations stay and the model is fitted onto them. Credit the tool as "TS3 Modding Tool by keyloor" in
anything you prepare for publishing.

`<KIT>` is the kit's folder (it holds `kit/`, `tools/`, `docs/`). **Before doing anything, read `<KIT>/docs/AGENTS.md`**
(in a release it may be at `<KIT>/AGENTS.md`): the full loop, what to check at each step, the game's bone names, the
rules. For any map table or manual fix, read `<KIT>/docs/GUIA_MANUAL.md` (Spanish; §4 tables, §5 the converter's log,
§7 common fixes, §8 closed eyes) and the real maps in `<KIT>/docs/ejemplos/`.

## Quick path (Python 3.12 with numpy and Pillow; always `python -I`)

For audio, `explore inspect PATH --game GAME --json` lists sample indices in `.assets.bank`.
`explore audio PATH [--member NAME] --track INDEX --seconds 30 --out NEW_DIRECTORY --game GAME --json`
exports a PCM16 mono/stereo `sample.wav` and `audio.json`. Limit 120 seconds; inspect `truncated` and
`decoded_seconds`. `--play` listens explicitly, Ctrl+C stops. Compressed samples use the selected game's
Windows FMOD 2.03 DLL; never copy it into packs. Events banks have no sample list; choose their
`.assets.bank` companion. This reads/exports audio, without modifying banks or simulating game events.

The separate player app, Toy Story 3 Mod Loader, accepts the same `mods ... --json` commands through
`TS3 Mod Loader CLI.exe` or `kit/loadercli.py`. Both apps share the registry/backups; no migration is needed.

For shared destinations, use `mods plan/install PACKAGE --layer` and its reviewed ticket. Combine with
`--replace` for same-ID updates. `mods order` reads priorities; `mods order ID... --dry-run` reviews every
installed ID once from lowest to highest, and `mods order ID... --expect TICKET` applies it. Last wins on
matching ZIP members or whole files; distinct patched members combine. A coinciding OCT is replaced whole,
without per-texture merging. New installs go last; replacements keep position; removing a layer rebuilds
the rest from stored snapshots. Review `order`, `shared` and `files`. Package/protocol schema stays 1;
registry migration to 2 is handled transactionally by current apps, never manually. External edits,
declared conflicts, missing dependencies and damaged required backups remain refusals.
Use the Modding Tool for character conversion, texture editing and exploration. Loader needs only stdlib/Tk.

For texture replacements: `kit/cli.py textures dump ARCHIVE [--member OCT] --out NEW_WORKSPACE --game GAME --json`.
Edit PNGs at the same size, then `textures build WORKSPACE --out NEW_PACK --id ID --name NAME --author AUTHOR
--game GAME --json`. It preserves DDS format/mips, updates OCT checksums and packages only changed OCT entries.
Install through the manager when authorized. Use the user's name/credit, keep the ID across versions, check
export errors, and keep the game-image workspace local. See `docs/CLI.md` for supported formats and limits.
`textures dump ARCHIVE [ARCHIVE ...] --shared --out NEW_WORKSPACE` groups byte-identical DDS textures into
one PNG across selected archives. Editing it updates every occurrence listed in index.json; unselected
archives are outside the scope. Without `--shared`, occurrences are independent. `--member` requires one
archive. Both old schema-1 and new schema-2 workspaces build with the same command. Read `png_files`,
`textures` (occurrences) and `archives` in reports. Preserve the workspace ID for regenerated packs.

To explore game assets, use `kit/cli.py explore list --game GAME --query TEXT --json` and follow
`next_offset`. `explore inspect PATH --member NAME` describes an asset. `explore preview` saves PNGs;
`explore extract` saves a member or a whole ZIP. Both require `--out NEW_DIRECTORY` outside the game.
See `docs/CLI.md` for all options. Read index/list errors. Previews draw any model or level as `model.png`.
The explorer reads installed content (possibly modded), never changes it, and extracted game files must not be shared.
`explore glb PATH [--member OCT] --out NEW_DIRECTORY --game GAME --json` exports a model for Blender as
`model.glb` plus a report. Includes supported geometry, UVs, original-resolution diffuse maps, pivot-based
bone hierarchy and skin weights; static pieces stay unskinned. Read `warnings`, `pieces_left_out` and
`materials_without_texture`. Original bone roll/rotation, game shaders and animations are not reconstructed.
Original-skeleton reinsertion is available explicitly; rigid editing uses a separate workspace. Keep game exports local.
Rigged GLB/glTF character inputs are accepted by `make PROJECT --model FILE --character CHARACTER --game GAME
--json` (`--fbx` remains an alias). Inspect first with `model-info FILE --json`, without a game or extraction.
All meshes must be skinned to a humanoid; static/mixed inputs are refused. Normal fitting applies, so this
is not an identity roundtrip. Project-owned textures use model-textures/<content-hash>; source edits refresh
them, user edits are preserved. Select a custom texture folder explicitly to override generated files.
No external URLs or paths outside the model directory; unsupported compression/morph/texture extensions
are refused. Read docs/CLI.md for the supported glTF subset and check diagnosis/previews before installation.

For a TS3 character exported and edited locally, use `make PROJECT --model FILE --character CHARACTER
--fit identity --game GAME --json`. It checks BoneIDs (or exact names without IDs), original pivots/hierarchy
and at most four distinct influences per vertex before preserving geometry at TS3 storage precision.
Keep the rest pose/armature. New/moved bones fail; saved proportion/joint/bone adjustments are inactive.
Materials/textures are rebuilt, so this does not preserve whole archives byte for byte. The window offers
Preserve original skeleton in step 3. `fit_mode` persists; default `normal` retains humanoid fitting.
Switching an existing map's mode requires `--remap` (overwrites hand edits: preserve them first).
Read make.data.fit_mode and adjust --info's verification report. In-game appearance remains a separate check.

Rigid objects: `meshes dump ARCHIVE --member OCT --out NEW_WORKSPACE --game GAME --json`, edit the GLB,
then `meshes build WORKSPACE [--model FILE] --out NEW_PACK --id ID --name NAME --author AUTHOR --game GAME
--json`. Use a dedicated mesh workspace (mesh.json); normal explore glb exports have no correspondence.
Keep triangles and `_TS3_VERTEX` point attributes; in Blender enable Mesh > Attributes on export.
Positions/normals/first UVs can change. Materials, indices, hidden data and collisions stay; collisions do
not follow shape edits. Missing IDs, shared buffer conflicts and changed topology are refused. No skins,
new topology or unrestricted level editing; <=250000 vertices per OCT. Build then use the manager's
plan/install workflow when authorized, preserving IDs for replacements. See docs/CLI.md for limits.

Optional new topology: `meshes build ... --topology replace` (GUI: unchecked-by-default Replace topology).
One selected visible lit rigid source piece, one unskinned replacement material; no vertex IDs required.
Supports adding/removing vertices/faces by appending separate streams and retaining original buffer bytes,
hidden pieces, materials and collisions. Refuses unknown/variable vertex data; max 65535 vertices and
1000000 triangles within source index width. Bounds expand; collisions do not follow the new shape.
Default preserve mode still checks original triangles/IDs. Review topology/counts in JSON and test visuals
separately. This is not simultaneous multi-piece/new-material/level creation. See docs/CLI.md.

Select a component in compound objects with `meshes pieces ARCHIVE --member OCT` (or `meshes pieces
WORKSPACE`), using its OCT `node` index. `meshes dump ... --piece NODE` exports that piece and records its
default target; build it in replace mode. Whole-model workspaces may use `meshes build ... --topology
replace --piece NODE`. Keep only that replacement in the input GLB; other pieces/materials/collisions stay.
Missing selection remains an error for compound sources. Read piece and whole-model counts in JSON;
one piece per build, no simultaneous replacements or unrestricted levels. Source hashes/limits still apply.

For existing mod packages, use the CLI instead of the model-conversion steps below.
Read `<KIT>/docs/CLI.md` for the JSON contract, errors and command arguments. Discover with
`python -I <KIT>/kit/cli.py mods capabilities --json`, or `<KIT>/TS3 Modding CLI.exe mods capabilities --json`
without Python. Pass the game folder explicitly. Prepare with `mods plan`, review the
changes, then use `mods install --expect TICKET` within the user's authorized scope.
Use `mods verify` to check files and backups and `mods remove --dry-run` before removal.
To update/rebuild the same ID, use `mods plan PACKAGE --replace` then
`mods install PACKAGE --replace --expect TICKET`, with explicit `--game` and `--json`.
Review the installed metadata in `replaces`, retired targets in `restores`, and all `files`.
The transaction preserves original backups and recovers the old installed version after interruption.
Same-version rebuilds and compatible downgrades are allowed; incompatible dependent versions are blocked.
`mods updates` lists newer GitHub releases of installed mods (never downloads; ask before getting one).
Do not bypass conflicts or external changes by deleting the registry or backups.
The console executable provides stdout and exit codes; the GUI executable logs to a file.

```
python -I <KIT>/kit/kit.py doctor
python -I <KIT>/kit/kit.py characters
python -I <KIT>/tools/fbxinfo.py <fbx>
python -I <KIT>/kit/kit.py make work/<name> --character woody --fbx <fbx> --textures <textures dir>
#   read work/<name>/report.txt, open previews/body.png and previews/face.png, edit work/<name>/map.py if needed:
python -I <KIT>/kit/kit.py make work/<name>
#   or change the window's Adjustments without editing map.py, then convert with them:
#   every kit.py command takes --json: one {ok, command, data, error} object on stdout, progress on stderr
python -I <KIT>/kit/kit.py diagnose work/<name> --json          # what looks wrong, with fixes (--fix ID)
python -I <KIT>/kit/kit.py adjust work/<name> --info --json
python -I <KIT>/kit/kit.py adjust work/<name> --set head_cm=-3 --put props "<bone>=hand_right" --set smooth=2
python -I <KIT>/kit/kit.py make work/<name> --remap
python -I <KIT>/kit/kit.py install work/<name>
python -I <KIT>/kit/kit.py restore work/<name>
python -I <KIT>/kit/kit.py export work/<name> --name "<Mod name>" --author "<user>" --what "<one line>" --model-credits "<model author>"
#   the pack has no scripts (players install it with the tool); add --installer only if the user wants a .bat too
```

No Python? `"<KIT>/Toy Story 3 Modding Tool.exe" make work/<name>` takes the same commands (no console: read
`work/<name>/report.txt`).

Characters: `woody`, `buzzlightyear`, `jessie` (and the variants `characters` lists).

## Must-dos

- Read the report (limbs, head, `CHECK` materials, converter warnings) and fix `map.py` before installing.
- Open the preview PNGs and look at them yourself, then show them to the user.
- Install only with the user's go-ahead and the game closed; `restore` undoes it.
- Never claim it works in game until the user confirms with screenshots.
- Never share game files or models the user has no rights to.
