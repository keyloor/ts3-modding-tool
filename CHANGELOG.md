# Changelog

## Unreleased

- Game explorer in Spanish and English: cached ZIP directory index, search by name/type, archive contents tree,
  OCT inspection, texture sheets, FMOD sound lists, and a 3D view of the game's models: characters, objects,
  vehicles and whole levels, with their textures (cut-out trees and fences too).
- Extract files or complete archives into a new folder outside the game; export PNG previews. Existing output
  is never overwritten. Supports both duplicate-directory and older front-directory game ZIPs.
- `explore index/list/inspect/extract/preview` in the console CLI, with JSON output and paginated search.
- No animations, audio playback, texture editing or glTF export in this update. Materials are shown with their
  diffuse map only, so the game's lighting and effects look different.

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
