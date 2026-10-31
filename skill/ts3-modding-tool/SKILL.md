---
name: ts3-modding-tool
description: Put a custom 3D model (rigged FBX, or OBJ without skeleton) into Toy Story 3 Complete Edition (PC) in place of Woody, Buzz or Jessie with the TS3 Modding Tool by keyloor. Use when the user wants to mod Toy Story 3 with the TS3 Modding Tool, replace a Toy Story 3 character with their own model, fix how a converted model looks, tune its bone or texture map, install or uninstall it, or prepare it for Nexus.
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

```
python -I <KIT>/kit/kit.py characters
python -I <KIT>/tools/fbxinfo.py <fbx>
python -I <KIT>/kit/kit.py make work/<name> --character woody --fbx <fbx> --textures <textures dir>
#   read work/<name>/report.txt, open previews/body.png and previews/face.png, edit work/<name>/map.py if needed:
python -I <KIT>/kit/kit.py make work/<name>
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
