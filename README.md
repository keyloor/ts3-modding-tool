# Toy Story 3 Modding Tool

**by keyloor** — mod *Toy Story 3 Complete Edition* (PC, Steam) without programming.

Right now: **put your own 3D model in place of Woody, Buzz Lightyear or Jessie.** A rigged FBX, or an OBJ (the tool
gives it a skeleton). The tool fits it to the game's skeleton, matches its textures, shows you a preview, installs it
into your game (and takes it out again), and exports a pack for other players. Music, sounds and
textures are next.

**Game explorer**: start screen → Browse files. Search the game's archives and loose files, inspect OCT pools
and sound-bank track lists, view models and levels in 3D and textures in sheets, and extract assets or save PNG
previews to a new folder outside the game. Reads the currently installed content, including mods. Also available
as `kit.py explore ... --json`; see [docs/CLI.md](docs/CLI.md). The 3D view shows characters, objects and whole
levels with their colour textures; the game's lighting, effects and animations aren't reproduced.

> Work in progress (version 0.1). Fan-made, not affiliated with Disney, Pixar or Avalanche Software. No game files are
> included: the tool reads them from your own copy of the game.

## What it does

- **Bones**: finds the body in any humanoid rig by its shape (Mixamo, Unreal/Fortnite, 3ds Max Biped, games' rigs...),
  not by bone names, and maps it onto the game character. You can change any body part's bone in a table.
- **OBJ models**: no skeleton in the file? It measures the model (crotch, neck, shoulders, fingertips), stretches the
  game's skeleton over it and weights it.
- **Textures**: matches each material to its images by name (diffuse, normal, ORM/specular), or uses its colour.
- **Live 3D preview** (GPU): turn and zoom it with the mouse, see it with its arms down as the game animates it,
  next to the game's original, with the game's skeleton on it; the Adjustments show live while you move them.
  Still images when the graphics card has no OpenGL 3.3.
- **Move the joints** of an OBJ's automatic skeleton or an FBX's body by dragging them in the 3D view (mirrored
  left/right).
- **Adjustments**: head height and proportions; loose objects (hat, bag, weapon) with the hand, head, chest or hips,
  or left out; narrower / wider clothes; open shut eyelids, animated face, head placed by the face; weights by
  hand and smoothing; undo / redo, named versions, and the conversion before shown beside the new one.
- **See problems**: a Diagnosis tab that says in plain words what looks wrong (a stretched neck, a torso made much
  wider, parts at the stretch limit...) with a button that fixes it; the weights of any game bone in colour; the
  parts the conversion stretched in red. Overall size, shoulder / hip spacing and stretch limits per part.
- **Everything from the command line too** (`kit.py adjust`, `kit.py mods`), for scripts and AI agents.
- **Install / restore** with a backup of the game's archive; refuses to build on an archive another mod changed, and
  finds the original in other installers' backups.
- **Export a Nexus pack**: only your changes, which players drop on the tool to install (no scripts, so Nexus doesn't
  hold it for review); optionally with its own installer for players without the tool.
- **Advanced**: everything is driven by a plain Python "map" file you can edit by hand, with every option of the
  converter (eyelids, face, split weights, colour palettes...).
- A window in Spanish and English, a command line, a `.exe` that needs no Python, a manual guide, and instructions plus
  a skill for AI agents.

## Use it

**With Python** (3.12):

```
pip install numpy pillow moderngl
python -I kit/app.py
```

Start screen → Characters → New project → pick the character, your model → Convert → look at the preview → Install.

Command line: `python -I kit/kit.py make work/my_model --character woody --fbx model.fbx --textures textures/`
(`python -I kit/kit.py --help` for the rest).

**Mod manager**: start screen → Manage mods, or drop a mod ZIP/folder on the window. It installs exported packs and
folders/ZIPs with game files, with backups, interrupted-operation recovery and update notices (mods whose
`mod.json` names a GitHub repository). The same from the command line: `kit.py mods ...` (JSON output for scripts
and AI agents, [docs/CLI.md](docs/CLI.md)). See [format and usage (Spanish)](docs/MOD_FORMAT.md).

**Without Python**: `python -I kit/build_kit.py` builds `Toy Story 3 Modding Tool.exe` (needs PyInstaller); ready-made
builds will be on the releases page and on Nexus Mods.

### With an AI agent

An AI agent that can run commands and read files (Claude Code, Codex, Cursor...) can do the whole job for you: you
just tell it what you want.

1. Have the tool (this repository, or the release folder) and Python 3.12 with `pip install numpy pillow`. Without
   Python, the agent can use the `.exe`: it takes the same commands (`"Toy Story 3 Modding Tool.exe" make ...`).
2. Give the agent the instructions:
   - **Claude Code**: copy `skill/ts3-modding-tool/` into `%USERPROFILE%\.claude\skills\` (every project) or into
     `.claude\skills\` of your project. Claude loads it when you ask for something it covers.
   - **Other agents**: open them in the tool's folder; many read `AGENTS.md` by themselves (`docs/AGENTS.md` here, at
     the root of the release folder). If yours doesn't, say "read AGENTS.md first".
3. Ask in your own words, e.g. *"put `C:\Downloads\bopeep\BoPeep.fbx` in place of Jessie"*.

What the agent then does (`AGENTS.md` tells it): checks the model, converts it, reads the report, **looks at the
preview images** and fixes the map if something is off, and shows you the previews. It installs into the game only
when you say so (with the game closed), asks you for screenshots before saying it works, and before exporting a pack
asks you for its name, your credit and who made the model. It never shares game files or models you have no right to.

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
`docs/GUIA_MANUAL.md`.

**Explorador del juego**: Inicio → Explorar archivos. Busca en los ZIP y archivos sueltos, inspecciona texturas,
modelos y listas de sonidos, y extrae contenido a una carpeta nueva. Puedes guardar vistas previas PNG o usar
`kit.py explore` con salida JSON. Lee lo que tienes instalado; no modifica el juego. La vista 3D muestra personajes,
objetos y niveles enteros con sus texturas de color, sin las luces, efectos ni animaciones del juego.

**Con un agente de IA** (Claude Code, Codex, Cursor…): con Claude Code, copia `skill/ts3-modding-tool/` a
`%USERPROFILE%\.claude\skills\`; con otros agentes, ábrelos en la carpeta de la herramienta y que lean `AGENTS.md`
(`docs/AGENTS.md` aquí; en la raíz del paquete). Luego pídelo con tus palabras: *«pon este modelo en lugar de
Jessie»*. El agente convierte, mira las vistas previas, corrige lo que haga falta, instala solo si tú le dices y te
pide capturas del juego antes de dar nada por bueno. Para aportar, mira [CONTRIBUTING.md](CONTRIBUTING.md). Licencia: GPL v3 + [NOTICE.md](NOTICE.md).
