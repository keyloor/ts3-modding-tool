# Toy Story 3 Modding Tool

**by keyloor** — mod *Toy Story 3 Complete Edition* (PC, Steam) without programming.

Right now: **put your own 3D model in place of Woody, Buzz Lightyear or Jessie.** A rigged FBX, or an OBJ (the tool
gives it a skeleton). The tool fits it to the game's skeleton, matches its textures, shows you a preview, installs it
into your game (and takes it out again), and exports a pack with an installer for other players. Music, sounds and
textures are next.

> Work in progress (version 0.1). Fan-made, not affiliated with Disney, Pixar or Avalanche Software. No game files are
> included: the tool reads them from your own copy of the game.

## What it does

- **Bones**: finds the body in any humanoid rig by its shape (Mixamo, Unreal/Fortnite, 3ds Max Biped, games' rigs...),
  not by bone names, and maps it onto the game character. You can change any body part's bone in a table.
- **OBJ models**: no skeleton in the file? It measures the model (crotch, neck, shoulders, fingertips), stretches the
  game's skeleton over it and weights it.
- **Textures**: matches each material to its images by name (diffuse, normal, ORM/specular), or uses its colour.
- **Preview** next to the game's own character, with the game's joints drawn on it.
- **Install / restore** with a backup of the game's archive; refuses to build on an archive another mod changed, and
  finds the original in other installers' backups.
- **Export a Nexus pack**: an installer that puts only your changes into each player's own game.
- **Advanced**: everything is driven by a plain Python "map" file you can edit by hand, with every option of the
  converter (eyelids, face, split weights, colour palettes...).
- A window in Spanish and English, a command line, a `.exe` that needs no Python, a manual guide, and instructions plus
  a skill for AI agents.

## Use it

**With Python** (3.12):

```
pip install numpy pillow
python -I kit/app.py
```

Start screen → Characters → New project → pick the character, your model → Convert → look at the preview → Install.

Command line: `python -I kit/kit.py make work/my_model --character woody --fbx model.fbx --textures textures/`
(`python -I kit/kit.py --help` for the rest).

**Without Python**: `python -I kit/build_kit.py` builds `Toy Story 3 Modding Tool.exe` (needs PyInstaller); ready-made
builds will be on the releases page and on Nexus Mods.

## Repository

| Folder | What |
|---|---|
| `kit/` | The tool: `app.py` (window), `kit.py` (commands), `automap.py` (bones), `autotex.py` (textures), `objlib.py` (OBJ + automatic skeleton), `build_kit.py` (the .exe), `pack/` (installer templates) |
| `tools/` | Toy Story 3 / Octane formats: archives, `.oct`, FBX reader, the converter, previews, installer |
| `docs/` | `GUIA_MANUAL.md` (doing it all by hand, in Spanish), `AGENTS.md` (for AI agents), `ejemplos/` (real maps), `CREDITS.md` |
| `skill/` | A skill for AI agents (Claude Code and others) |

## Contributing

Fork, branch, pull request: see [CONTRIBUTING.md](CONTRIBUTING.md). `CLAUDE.md` explains how the pieces fit.

## License

Free software under the **GNU GPL v3** ([LICENSE](LICENSE)) with two added terms in [NOTICE.md](NOTICE.md): keep
"Toy Story 3 Modding Tool by keyloor" where the program shows it, and mark modified versions as modified. If you publish
a mod made with the tool, please credit it: *"Made with TS3 Modding Tool by keyloor"*.

---

## Español

**Toy Story 3 Modding Tool, de keyloor**: modifica *Toy Story 3 Complete Edition* (PC, Steam) sin programar. Por ahora:
pon tu propio modelo 3D (FBX con esqueleto, u OBJ) en lugar de Woody, Buzz Lightyear o Jessie, míralo en una vista
previa, instálalo en tu juego y exporta un pack para Nexus. Después vendrán música, sonidos y texturas.

Para usarla con Python: `pip install numpy pillow` y `python -I kit/app.py`. La guía para hacerlo todo a mano está en
`docs/GUIA_MANUAL.md`. Para aportar, mira [CONTRIBUTING.md](CONTRIBUTING.md). Licencia: GPL v3 + [NOTICE.md](NOTICE.md).
