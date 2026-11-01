Toy Story 3 Modding Tool                                                   version @@VERSION@@
by keyloor - for Toy Story 3 Complete Edition on PC (Steam)
======================================================================================================

Mod Toy Story 3 without programming. Now: put your own 3D model (rigged FBX, or OBJ) in place of Woody, Buzz or
Jessie, and install, remove and share mods. Music, sounds and textures: coming soon.

START
  Double-click "Toy Story 3 Modding Tool.exe" (no Python needed). If Windows warns about it, choose "More info" >
  "Run anyway". Some antivirus programs flag new, unsigned tools by mistake.
  The start screen finds the game through Steam and keeps your projects in Documents\Toy Story 3 Modding Tool.

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
Buzz o Jessie, e instala, quita y comparte mods. Música, sonidos y texturas: próximamente.

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
