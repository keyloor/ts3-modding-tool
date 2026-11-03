Toy Story 3 Modding Tool                                                   version @@VERSION@@
by keyloor - for Toy Story 3 Complete Edition on PC (Steam)
======================================================================================================

Mod Toy Story 3 without programming. Now: put your own 3D model (rigged FBX, or OBJ) in place of Woody, Buzz or
Jessie, edit textures, preview sounds, and install, remove and share mods. Audio editing is planned.

JUST WANT TO INSTALL MODS?
  Use the separate "Toy Story 3 Mod Loader" download for the simpler player interface.
  This Modding Tool download is for creating mods. Its integrated manager and the Loader share the same
  installed-mod registry and backups, so your existing mods are available in both.
  Choose a newer or rebuilt package with the same ID to review and replace the installed version.
  Original backups are preserved. Files retired from the new pack return to their previous state.
  Interrupted replacements recover the previously installed version. Downloads remain manual.

MOD PRIORITIES
  Both apps offer Mod priorities: lower at the top, higher at the bottom; last wins on matching entries/files.
  New installs go last; updates keep position. Review before applying. Distinct ZIP patch members combine;
  a matching OCT is replaced as a whole, without per-texture merging. Removing a layer rebuilds the others
  from stored snapshots; the last removal restores original bytes. No downloaded package is needed again.
  CLI: mods plan/install PACKAGE --layer; mods order ID... --dry-run, then --expect TICKET.
  Use current versions of both apps with layered registries. External edits and declared conflicts stay blocked.

TEXTURES ACROSS WORLD VARIANTS
  Textures > Export multiple ZIPs creates one workspace for the selected game archives.
  Enable Share one PNG to edit identical DDS occurrences together; leave it off for separate edits.
  Build texture pack creates one pack with all changed archives. Existing workspaces still open.
  CLI: textures dump ARCHIVE [ARCHIVE ...] --shared --out NEW_WORKSPACE --game GAME --json

SOUND PREVIEWS
  Music and sounds > Listen to sounds opens the explorer. Inspect an .assets.bank, choose a sample,
  then Play/Stop or Save WAV. Excerpts start at the beginning, up to 120 seconds; no automatic playback.
  Compressed samples use the selected game's existing FMOD runtime on Windows, decoded in a separate process.
  No game DLL is included. Output is PCM16 mono/stereo. Bank editing/reinsertion remains planned.
  CLI: explore audio PATH --track 0 --seconds 30 --out NEW_DIRECTORY --game GAME --json

START
  Double-click "Toy Story 3 Modding Tool.exe" (no Python needed). If Windows warns about it, choose "More info" >
  "Run anyway". Some antivirus programs flag new, unsigned tools by mistake.
  The start screen finds the game through Steam and keeps your projects in Documents\Toy Story 3 Modding Tool.

EXPORT TO BLENDER (FIRST STEP)
  Explorer > choose a ZIP/OCT > Export GLB model creates model.glb and a report in a new folder.
  Geometry, UVs, diffuse maps and pivot-based skinning are included; static pieces stay outside the skin.
  Read report.json for omitted pieces and materials. Original bone roll/rotation, game shaders and animations
  are not reconstructed. Rigged character GLB/glTF files can be project inputs with normal fitting;
  or preserve their verified original skeleton. Rigid edits use the separate workspace below. Keep game exports local.
  CLI: explore glb PATH [--member OCT] --out NEW_DIRECTORY --game GAME --json

RIGID OBJECT EDITING
  Explorer > select an OCT member > Export editable mesh. Retouch model.glb without changing triangles
  or its _TS3_VERTEX point attribute (Blender export: Mesh > Attributes), then Build mesh pack.
  Keeps original materials, indices and collisions. Collisions do not follow shape edits.
  Shared buffer conflicts, missing IDs and changed topology are refused; limit 250000 visible vertices.
  Optional Replace topology (CLI --topology replace) allows adding/removing vertices and triangles for
  one visible lit source piece, one material, up to 65535 vertices. No _TS3_VERTEX is needed in that mode.
  Appends separate streams, preserving original buffers and hidden pieces; bounds expand conservatively.
  Compound objects can select one visible piece when exporting/building. CLI: meshes pieces WORKSPACE
  (or ARCHIVE --member OCT); dump/build --piece NODE. Piece-only workspaces require replace mode.
  Other pieces keep their geometry/UV/materials. One piece is replaced per build; source limits remain.
  This is not multi-piece/new-material/level creation. See docs/CLI.md; install the pack with the Loader.
  CLI: meshes dump ARCHIVE --member OCT --out NEW_WORKSPACE --game GAME --json
  CLI: meshes build WORKSPACE [--model FILE] --out NEW_PACK --id ID --name NAME --author AUTHOR --game GAME --json

GLB / glTF CHARACTERS
  Choose a GLB/glTF as the project model. It needs a humanoid rig and all meshes skinned.
  Embedded/local PNG/JPEG textures are prepared inside the project. This uses normal character fitting,
  including adjustments and diagnosis. Step 3 > Preserve original skeleton (CLI: make --fit identity) verifies
  original joints/pivots and keeps edited geometry without proportion fitting. Saved fitting adjustments
  are inactive in that mode. Materials/textures are rebuilt, so archives are not byte-identical.
  See docs/CLI.md for requirements and storage precision; test appearance separately in game.
  CLI: model-info FILE --json
  CLI: make PROJECT --model FILE --character woody --game GAME --json

YOUR OWN CHARACTER
  Characters > "New project", give it a name, then:
  1. Pick the character you replace: Woody, Buzz Lightyear, Jessie (or another under "Other").
  2. Choose your model (FBX or OBJ). Its textures folder is found next to it; "Change textures" if not.
  3. "Convert", and look at the Preview: turn it with the mouse, see it with its arms down as the game moves it.
     The Diagnosis tab says what looks wrong and has a button that fixes it. The Adjustments tab has the rest:
     head and neck, proportions, size, accessories, clothes, eyes and face, weights (with undo). In the Preview,
     "Your model's skeleton" lets you drag a joint that is off.
  4. "Install into the game" (game closed). "Restore original" undoes it. "Export pack for Nexus" makes a pack
     with only your changes, which other players install by dropping it on this tool.
  Your model: a humanoid standing in a T or A pose. A rigged FBX (skeleton + skin) gives the best result; an OBJ
  gets a skeleton from the tool. Textures as PNG, TGA, JPG or DDS.

INSTALL OTHER MODS
  "Manage mods" on the start screen, then drag the mod's ZIP or folder onto the window (or "Install mod...").
  You see what it changes before it is installed; "Remove mod" puts the game's files back. It takes packs made
  with this tool, keyloor's mods, and mods that are copied into the game folder. "Check for updates" tells you
  when a mod has a newer version (it never downloads anything).

BROWSE THE GAME
  "Browse files" on the start screen opens the game explorer. Search by name and type, expand a ZIP, then
  inspect an asset or preview it: characters, objects and whole levels in 3D, textures in sheets. Sound banks
  show their track lists.
  "Extract" and "Save preview" create a new folder outside the game; existing output is never overwritten.
  Reads your installed content, including mods. The 3D view has colour textures, not the game's lights or effects.
  Command line: "TS3 Modding CLI.exe" explore --help (JSON output supported; see docs/CLI.md).

EDIT TEXTURES
  Textures > "Edit textures": select a ZIP or OCT and "Export PNG textures" to a new folder.
  Edit the PNGs in your image editor, keeping their size. "Build texture pack" reads that exported folder,
  asks for your mod name/credit/version and creates an installable folder with only the changed OCT files.
  Install/remove it through Manage mods. No game files are changed when exporting or building.
  Supports DXT1/3/5 and 32-bit RGB(A), with original mipmaps. One managed mod per archive; no priorities yet.
  CLI: "TS3 Modding CLI.exe" textures --help. See docs/CLI.md for the complete workflow.

WITH AN AI AGENT (Claude Code, Codex, Cursor...)
  The agent runs the tool for you; you just tell it what you want.
  1. Claude Code: copy the "skill\ts3-modding-tool" folder into %USERPROFILE%\.claude\skills\ . Other agents: open
     them in this folder; many read AGENTS.md by themselves (if not, tell yours "read AGENTS.md first").
  2. Ask in your own words: "put C:\Downloads\bopeep\BoPeep.fbx in place of Jessie".
  It converts, looks at the previews and the diagnosis, fixes what is off, installs only when you say so, and asks
  you for screenshots from the game before calling it done. It uses "TS3 Modding CLI.exe" (every command, with
  --json answers), or Python 3.12 + "pip install numpy pillow".

MORE
  docs\GUIA_MANUAL.md       every step by hand, all the map options, the game's formats (Spanish)
  docs\CLI.md, docs\MOD_FORMAT.md   the command line and the mod format (mod.json)
  docs\ejemplos\            real maps with eyes, face, several materials, colour palettes
  AGENTS.md, skill\         for doing it with an AI agent
  kit\, tools\              the tool's Python source (python -I kit\kit.py --help)
  LICENSE, NOTICE.md        free software (GNU GPL v3); NOTICE.md adds: keep "by keyloor", mark modified versions
  docs\CREDITS.md, licenses\  credits and the licenses of what the .exe carries inside
  Source code and contributions: https://github.com/keyloor/ts3-modding-tool

When you publish a mod made with the tool, put on its page: "Made with TS3 Modding Tool by keyloor".

------------------------------------------------------------------------------------------------------
ESPAÑOL

Modifica Toy Story 3 sin programar. Ahora: pon tu propio modelo 3D (FBX con esqueleto, u OBJ) en lugar de Woody,
Buzz o Jessie, edita texturas, escucha sonidos, e instala, quita y comparte mods. La edición de audio: próximamente.

EMPEZAR
  Doble clic en "Toy Story 3 Modding Tool.exe" (no hace falta Python). Si Windows avisa, elige "Más información" >
  "Ejecutar de todas formas". Algunos antivirus marcan por error las herramientas nuevas sin firma.
  La pantalla de inicio encuentra el juego por Steam y guarda tus proyectos en Documentos\Toy Story 3 Modding Tool.

TU PROPIO PERSONAJE
  Personajes > "Nuevo proyecto", ponle un nombre, y luego:
  1. Elige el personaje que reemplazas: Woody, Buzz Lightyear, Jessie (u otro en "Otro").
  2. Elige tu modelo (FBX u OBJ). Su carpeta de texturas se busca junto a él; si no, "Cambiar texturas".
  3. "Convertir", y mira la Vista previa: gírala con el ratón, mírala con los brazos abajo como la mueve el juego.
     La pestaña Diagnóstico dice qué se ve mal y tiene un botón que lo arregla. La pestaña Ajustes tiene el resto:
     cabeza y cuello, proporciones, tamaño, accesorios, ropa, ojos y cara, pesos (con deshacer). En la Vista
     previa, "Esqueleto de tu modelo" deja arrastrar una articulación que esté mal.
  4. "Instalar en el juego" (con el juego cerrado). "Restaurar original" lo deshace. "Exportar pack para Nexus" hace
     un pack solo con tus cambios, que otros jugadores instalan arrastrándolo a esta herramienta.

INSTALAR OTROS MODS
  "Gestionar mods" en la pantalla de inicio, y arrastra el ZIP o la carpeta del mod a la ventana (o "Instalar
  mod…"). Ves qué cambia antes de instalarlo; "Quitar mod" devuelve los archivos del juego. Acepta packs hechos con
  esta herramienta, los mods de keyloor y los mods que se copian en la carpeta del juego. "Buscar actualizaciones"
  avisa si un mod tiene versión nueva (nunca descarga nada).

CON UN AGENTE DE IA (Claude Code, Codex, Cursor...)
  El agente maneja la herramienta por ti; tú solo le dices lo que quieres.
  1. Claude Code: copia la carpeta "skill\ts3-modding-tool" a %USERPROFILE%\.claude\skills\ . Otros agentes: ábrelos
     en esta carpeta; muchos leen AGENTS.md solos (si no, dile al tuyo "lee primero AGENTS.md").
  2. Pídelo con tus palabras: "pon C:\Descargas\bopeep\BoPeep.fbx en lugar de Jessie".
  Convierte, mira las vistas previas y el diagnóstico, corrige lo que haga falta, instala solo si tú le dices y te
  pide capturas del juego antes de darlo por bueno. Usa "TS3 Modding CLI.exe" (todos los comandos, con respuestas
  --json), o Python 3.12 + "pip install numpy pillow".

Si publicas un mod hecho con la herramienta, pon en su página: "Hecho con TS3 Modding Tool de keyloor".
