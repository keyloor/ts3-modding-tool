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

For existing mod packages, use the CLI instead of the model-conversion steps below.
Read `<KIT>/docs/CLI.md` for the JSON contract, errors and command arguments. Discover with
`python -I <KIT>/kit/cli.py mods capabilities --json`, or `<KIT>/TS3 Modding CLI.exe mods capabilities --json`
without Python. Pass the game folder explicitly. Prepare with `mods plan`, review the
changes, then use `mods install --expect TICKET` within the user's authorized scope.
Use `mods verify` to check files and backups and `mods remove --dry-run` before removal.
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
python -I <KIT>/kit/kit.py adjust work/<name> --info --json
python -I <KIT>/kit/kit.py adjust work/<name> --set head_cm=-3 --put props "<bone>=hand_right" --set smooth=2
python -I <KIT>/kit/kit.py make work/<name> --remap
python -I <KIT>/kit/kit.py install work/<name>
python -I <KIT>/kit/kit.py restore work/<name>
python -I <KIT>/kit/kit.py export work/<name> --name "<Mod name>" --author "<user>" --what "<one line>" --model-credits "<model author>"
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
