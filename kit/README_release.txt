Toy Story 3 Modding Tool                                                   version @@VERSION@@
by keyloor - for Toy Story 3 Complete Edition on PC (Steam)
======================================================================================================

Mod Toy Story 3 without programming. Now: put your own 3D model (rigged FBX, or OBJ) in place of Woody, Buzz or
Jessie, and make a Nexus pack of it. Music, sounds and textures: coming soon.

START
  Double-click "Toy Story 3 Modding Tool.exe" (no Python needed). If Windows warns about it, choose "More info" >
  "Run anyway". Some antivirus programs flag new, unsigned tools by mistake.

  The start screen finds the game through Steam and keeps your projects in Documents\Toy Story 3 Modding Tool.
  Characters > "New project", give it a name, then:
  1. Pick the character you replace: Woody, Buzz Lightyear, Jessie (or another under "Other").
  2. Choose your model (FBX or OBJ). Its textures folder is found next to it; "Change textures" if not.
  3. "Convert", and look at the Preview (the game's character on the left, yours on the right). "Check bones and
     materials" shows what the tool decided: double-click a row to change it, then convert again.
  4. "Install into the game" (game closed). "Restore original" undoes it. "Export pack for Nexus" makes an installer
     for other players, with only your changes.

YOUR MODEL
  A humanoid standing in a T or A pose. A rigged FBX (skeleton + skin) gives the best result; an OBJ gets a skeleton
  from the tool. Textures as PNG, TGA, JPG or DDS. Models from games often come with the eyelids shut: see the manual
  guide, section 8.

MORE
  docs\GUIA_MANUAL.md       every step by hand, all the map options, the game's formats (Spanish)
  docs\ejemplos\            real maps with eyes, face, several materials, colour palettes
  AGENTS.md, skill\         for doing it with an AI agent (Claude Code or others)
  kit\, tools\              the tool's Python source (command line: python -I kit\kit.py --help)
  LICENSE, NOTICE.md        free software (GNU GPL v3); NOTICE.md adds: keep "by keyloor", mark modified versions
  docs\CREDITS.md, licenses\  credits and the licenses of what the .exe carries inside
  Source code and contributions: https://github.com/keyloor/ts3-modding-tool

When you publish a mod made with the tool, put on its page: "Made with TS3 Modding Tool by keyloor".

------------------------------------------------------------------------------------------------------
ESPAÑOL

Modifica Toy Story 3 sin programar. Ahora: pon tu propio modelo 3D (FBX con esqueleto, u OBJ) en lugar de Woody,
Buzz o Jessie, y haz un pack para Nexus. Música, sonidos y texturas: próximamente.

EMPEZAR
  Doble clic en "Toy Story 3 Modding Tool.exe" (no hace falta Python). Si Windows avisa, elige "Más información" >
  "Ejecutar de todas formas". Algunos antivirus marcan por error las herramientas nuevas sin firma.

  La pantalla de inicio encuentra el juego por Steam y guarda tus proyectos en Documentos\Toy Story 3 Modding Tool.
  Personajes > "Nuevo proyecto", ponle un nombre, y luego:
  1. Elige el personaje que reemplazas: Woody, Buzz Lightyear, Jessie (u otro en "Otro").
  2. Elige tu modelo (FBX u OBJ). Su carpeta de texturas se busca junto a él; si no, "Cambiar texturas".
  3. "Convertir", y mira la Vista previa (el personaje del juego a la izquierda, el tuyo a la derecha). "Revisar
     huesos y materiales" enseña lo que decidió la herramienta: doble clic en una fila para cambiarla, y vuelve a
     convertir.
  4. "Instalar en el juego" (con el juego cerrado). "Restaurar original" lo deshace. "Exportar pack para Nexus" hace
     un instalador para otros jugadores, solo con tus cambios.

Si publicas un mod hecho con la herramienta, pon en su página: "Hecho con TS3 Modding Tool de keyloor".
