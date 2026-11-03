# Changelog

## 0.2

Two downloads from now on: **Toy Story 3 Mod Loader** for players, and **Toy Story 3 Modding Tool** for creators. Both
share the same mods, backups and game detection: a mod installed with one can be managed with the other.

**Mod Loader** (new): one page with your installed mods, search, install by dropping a ZIP or folder, review before
installing, remove, verify files, recover an interrupted operation, update notices. Spanish and English.

**Mod priorities** (both apps): mods can now share a game archive. Number them, review and apply: mods changing
different files inside an archive combine; when two change the same file, the higher priority wins whole. Removing or
reordering rebuilds the rest without their downloads, and removing the last restores the original bytes. Updating a mod
replaces it in place, with no need to uninstall first. Two packs changing different textures of the same `.oct` don't
combine yet: the higher priority's `.oct` wins.

**Game explorer** (new): search every archive of the game, see models and whole levels in 3D with their textures,
texture sheets, extract anything to a new folder (the game is never changed), and save PNG previews.

**Sounds** (new): list a bank's samples, play and stop them, save WAV excerpts. Compressed samples decode with the FMOD
already in your copy of the game; no game DLL is distributed. Editing or reinserting audio isn't available yet.

**Textures** (new): export PNGs from one or several archives, edit them at the same size, build a data-only mod pack.
Keeps DXT1/3/5 and 32-bit formats, alpha and mip counts. Optional single PNG for textures repeated between archives.

**Blender workflow** (new): export any model as GLB with skeleton, weights, UVs and textures; bring characters back
over their original skeleton; edit rigid objects (positions, normals, UVs) or replace one piece's geometry and build a
mod pack from them. Character input now also takes GLB and glTF, next to FBX and OBJ.

**Also**: clear "invalid model" messages that say how to fix the model.

Everything can also be done from the command line with JSON answers (`TS3 Modding CLI.exe`, `TS3 Mod Loader CLI.exe`).

**Not checked inside the game yet**: edited textures, GLB character reinsertion, edited rigid objects and mod
priorities were tested on files and copies of the game's archives, not played. Reports are welcome.
Not available yet: animations of the game in the preview, audio editing, collisions and free level editing.

## 0.1 (first public version)

Toy Story 3 Modding Tool by keyloor, for Toy Story 3 Complete Edition on PC (Steam).

**Characters**: put your own humanoid model in place of Woody, Buzz Lightyear or Jessie.
- Rigged FBX (Mixamo, Unreal / Fortnite, 3ds Max Biped, games' rigs...) or OBJ (the tool gives it a skeleton).
  Bones and textures are found automatically; the Bones and Materials tabs let you change what it chose.
- Live 3D preview: turn it, arms down as the game animates it, the game's original or your previous conversion
  beside it, the game's skeleton, any game bone's weights in colour, stretched parts in red.
- Adjustments: head height and the neck's length; torso, head, neck, arm and leg proportions; overall size,
  shoulder and hip spacing, how far each part may stretch; loose objects (hat, bag, weapon) with a hand, the head,
  chest or hips, or left out; narrower / wider clothes; open shut eyelids, animated face, head placed by the face;
  weights by hand and smoothing. Undo / redo and named versions.
- Move the joints by dragging them in the 3D view (FBX and OBJ, mirrored left / right).
- Diagnosis: what looks wrong in plain words, with a button that fixes it.
- Install into the game and restore the original, with a backup of the game's archive.
- Export a pack for Nexus: only your changes, installed by dropping it on the tool (no scripts, so Nexus doesn't
  hold it for review), optionally with its own installer for players without the tool.

**Mod manager**: drop a mod ZIP or folder on the window to install it.
- Packs with `mod.json`, packs made with keyloor's mods' release builder, and "copy into the game folder" packs.
- Shows what each mod changes before installing; removes it with its backups; recovers an interrupted operation.
- Tells you when a mod has a newer version on GitHub (mods whose `mod.json` names a repository). Never downloads.

**Command line and AI agents**: `TS3 Modding CLI.exe` (or `python -I kit/kit.py`) does everything the window does,
with `--json` answers for scripts and AI agents. `AGENTS.md` and `skill/` explain how to use it with Claude Code,
Codex, Cursor and others; `docs/GUIA_MANUAL.md` (Spanish) shows every step by hand.

Not yet: music and sounds, textures, a game explorer (see `PLAN.md`).
