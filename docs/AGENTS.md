# TS3 Modding Tool: instructions for AI agents

*TS3 Modding Tool by keyloor.* In a release this file sits at the kit's root; `<KIT>` is that folder (it holds
`kit/`, `tools/`, `docs/`). Read it fully before helping a user put a model into Toy Story 3. The user-facing guides
are `docs/GUIA_MANUAL.md` (manual, every map table explained) and the skill in `skill/ts3-modding-tool/`.

## What you are doing

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
`mods updates` says which installed mods have a newer GitHub release (`url` = its page); it never downloads.
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
`joints` (OBJ only): {bone of the automatic skeleton, e.g. 'ForearmLeft': [x, y, z]} replaces that estimated joint
(coordinates in the OBJ scene's frame: Y up, facing +Z, on the floor, centred, the model's own units); the window
writes it from the Preview tab's "Your model's skeleton" mode.
`adjust` also takes proportions, in percent: `torso` [x, y, z] (written as `TORSO_SCALE`), `head_pct` (head size),
`neck_pct`, `arms_pct`, `legs_pct` (thickness; written as `GIRTH`). Lengths can't change: joints stay on the game's.
The report's `torso fit: W% wide, H% tall` says how much the tool already reshapes the torso.
`adjust`: {'head_cm': up (+) / down (-)} moves the head and the end of the neck from the game's head joint (the
window's Adjustments tab). The report's line `neck length: model X cm, game Y cm: stretched xZ ...; head N cm keeps
its own length` says when to use it: a stretch beyond 1.25 means a long, distorted neck; set `head_cm` to N.

To publish: `kit.py export work/<name> --name "<Mod name>" --version 1.0 --author "<user>" --what "<one line>"
--model-credits "<model author>"` writes `work/<name>/pack/<Mod name> for TS3/` and its zip: an installer that puts
only the mod's files into each player's own archive, README with the credits. Ask the user for every field; never
invent the model's author or permission.

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
