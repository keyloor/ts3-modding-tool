# CLI para personas y agentes de IA

La consola usa el mismo gestor que la interfaz. No abre ventanas ni pide respuestas
interactivas. Los comandos del gestor tienen salida JSON, planes de instalación y
desinstalación, verificación y códigos de salida. Las pruebas visuales y dentro del juego
siguen siendo independientes de estos controles.

## Ejecutar

Con Python, desde la carpeta de la herramienta:

```text
python -I kit/cli.py mods capabilities --json
```

Sin Python, en PowerShell, desde la copia del escritorio o el paquete distribuido:

```powershell
& '.\TS3 Modding CLI.exe' mods capabilities --json
```

`TS3 Modding CLI.exe` es el ejecutable de consola: devuelve `stdout`, `stderr` y el código
de salida al proceso que lo llama. El `.exe` de la ventana sigue aceptando comandos por
compatibilidad, pero guarda sus mensajes en un archivo temporal; para automatizar usa la CLI.

`kit/kit.py mods ...` también admite este protocolo, y **los comandos de personajes también**
(`characters`, `doctor`, `make`, `adjust`, `diagnose`, `install`, `restore`, `export`): con
`--json` (en cualquier sitio de la línea) escriben un solo objeto JSON en stdout, con la misma
forma que los de `mods` y `command` = `kit.<comando>`; el progreso (la conversión de `make`) va
a stderr. Sin `--json` escriben texto, como siempre. Ver «Comandos de personajes» abajo.
Lo que se elige en la ventana (huesos, materiales, ajustes, articulaciones) se guarda en
`kit_project.json` del proyecto. Los ajustes y articulaciones se cambian con `kit.py adjust
PROYECTO` (`--info --json` dice qué se midió y qué se puede elegir; claves en `docs/AGENTS.md`),
y luego `kit.py make PROYECTO --remap` convierte. `kit.py diagnose PROYECTO --json` dice qué se ve mal y
con qué cambio se arregla (`--fix ID` lo aplica), como la pestaña Diagnóstico. La vista 3D no tiene equivalente: `make` deja
imágenes en `previews/` (y `compare.png`, la conversión anterior al lado), y `adjust --info`
da en números cuánto se estiró cada parte.

## Comandos de personajes (`--json`)

| Comando | `data` |
|---|---|
| `characters [--game J]` | `game`, `characters`: [{`name`, `state` (`original`, `changed_by_tool`, `changed_by_another_mod`, `unknown`), `archive`}] |
| `doctor [--game J]` | versiones, `preview_3d` {`ok`, ...}, `game`, `originals` {personaje: copia original o null} |
| `make PROYECTO [...]` | `character`, `map`, `out`, `report`, `previews` [rutas], `check_materials`, `diagnosis` (como `diagnose`), `installed` (con `--install`) |
| `adjust PROYECTO [...]` | `adjust`, `joints`, `versions`, `keys`; con `--info`, `info` (medidas y opciones) |
| `diagnose PROYECTO [--fix ID]` | `found` [{`id`, `level`, `message`, `args`, `fixes`, `see`}], `applied` |
| `install` / `restore PROYECTO` | `character`, `game`, `archive`, `backup` |
| `export PROYECTO --name N [...]` | `pack`, `zip`, `installer`, `mod_id` |

Códigos de error: `invalid_arguments` (salida 2), y con salida 3 `no_project`, `game_not_found`,
`game_running`, `no_character`, `not_converted`, `original_missing`, `not_installed`,
`check_failed` (el `.oct` no se relee igual: no instalar), `convert_failed`, `invalid_value`,
`invalid_model` (el modelo no sirve tal como está: `error.problem` dice qué —`split_skeleton`, `no_skin`,
`pose`, `not_humanoid`, `leg`, `arm`, `no_head`, `bad_choice`, `bad_file`— y `message` cómo arreglarlo),
`invalid_data`, `io_error`, `rejected`; `internal_error` (5) e `interrupted` (130).

## Flujo de un agente

1. Descubrir las capacidades con `mods capabilities --json`.
2. Inspeccionar el paquete con `mods inspect PAQUETE --json`. Esto lee metadatos; no
   comprueba todavía si se puede aplicar a una instalación concreta.
3. Preparar con `mods plan PAQUETE --game JUEGO --json`. Valida el contenido y los
   conflictos. Devuelve los archivos que cambiarán y un `ticket`.
4. Dentro del alcance autorizado por el usuario, aplicar con
   `mods install PAQUETE --game JUEGO --expect TICKET --json`.
5. Comprobar con `mods verify ID --game JUEGO --json`.

Pasa siempre la ruta del juego explícitamente al automatizar. Sin `--game`, se busca en
Steam. `plan` y `install --dry-run` hacen la misma preparación y no instalan nada.

El ticket es una huella del destino, la operación, los metadatos, el contenido resultante
y los archivos previos. Si alguno cambia, `--expect` bloquea la operación. Un ticket de
instalación no sirve para desinstalar ni para otra carpeta del juego. No es una credencial
ni sustituye las instrucciones del usuario.

Para quitar un mod:

```text
mods remove ID --game JUEGO --dry-run --json
mods remove ID --game JUEGO --expect TICKET_DE_DESINSTALACION --json
```

No combines `--expect` y `--dry-run`. Para explorar el estado:

```text
mods list --game JUEGO --json
mods show ID --game JUEGO --json
mods verify ID --game JUEGO --json
mods recover --game JUEGO --json
```

Para saber si hay versiones nuevas de los mods que declaran `update.github`:

```text
mods updates --game JUEGO --json
mods updates --game JUEGO --force --json
```

Devuelve por mod `installed`, `latest`, `update` (true si hay una versión mayor), `url` (la
página de la *release*) y `error` (sin conexión, sin *releases*...). Sin `--force` usa lo
consultado en las últimas 24 h (1 h si falló). Solo lee: descargar e instalar la versión nueva
es otro paso, con el permiso del usuario.

`verify` informa por archivo si está `ok`, `missing` o `modified`, y si su copia de seguridad
está `ok`, `missing`, `damaged` o `not_needed` (archivo creado por el mod). No repara nada.
`recover` sí modifica archivos: revierte una operación interrumpida. Las instalaciones y
desinstalaciones también intentan recuperar primero una transacción pendiente.

Los planes y las consultas pueden crear la carpeta del gestor y su archivo de bloqueo,
pero no cambian contenido del juego ni crean copias de seguridad. No borres el registro,
el diario ni las copias para forzar una operación rechazada.

## Ejemplo en PowerShell

```powershell
$ts3Cli = '.\TS3 Modding CLI.exe'
$ts3Game = 'D:\ruta\al\juego'
$ts3Pack = 'C:\Downloads\Mi mod.zip'

$ts3Plan = & $ts3Cli mods plan $ts3Pack --game $ts3Game --json | ConvertFrom-Json
if (-not $ts3Plan.ok) { throw $ts3Plan.error.message }
$ts3Plan.data.files  # Revisar lo que cambiará antes de aplicar.

$ts3Result = & $ts3Cli mods install $ts3Pack --game $ts3Game --expect $ts3Plan.data.ticket --json | ConvertFrom-Json
if (-not $ts3Result.ok) { throw $ts3Result.error.message }
& $ts3Cli mods verify $ts3Result.data.metadata.id --game $ts3Game --json
```

## Contrato JSON, versión 1

`--json` puede ir antes o después del subcomando. Se escribe **un único objeto JSON UTF-8
en una línea de stdout**, también si falla la operación. `--help` conserva la ayuda humana.

```json
{
  "schema_version": 1,
  "ok": true,
  "command": "mods.plan",
  "data": {},
  "error": null
}
```

En caso de error: `ok: false`, y `error` contiene `code` y `message`. `data` suele ser
`null`; en una verificación fallida contiene el informe completo para identificar los
archivos afectados. Los errores de argumentos usan `command: "mods"` si no se llegó a
resolver el subcomando. Las trazas de errores internos van a `stderr`, nunca mezcladas
con el JSON. Los códigos estables permiten tomar decisiones sin analizar el texto inglés.

| Salida | Significado |
|---|---|
| 0 | Operación correcta |
| 2 | Argumentos incorrectos |
| 3 | Operación rechazada o datos/archivos inválidos |
| 4 | La verificación detectó un archivo o copia que no coincide |
| 5 | Error interno inesperado |
| 130 | Interrupción del proceso |

Códigos de error relevantes: `invalid_arguments`, `invalid_mod`, `invalid_data`, `io_error`,
`game_not_found`, `game_running`, `game_file_missing`, `store_busy`, `recovery_required`,
`already_installed`, `not_installed`, `missing_dependency`, `dependent_installed`,
`declared_conflict`, `file_conflict`, `external_change`, `backup_damaged`, `plan_changed`,
`verification_failed`, `internal_error` e `interrupted`.

Si aparece `plan_changed`, prepara y revisa un plan nuevo. Si aparece `external_change`,
conserva los cambios y las copias; no reintentes con una sobrescritura forzada. No hay modo
`--force` en el gestor. `store_busy` significa que otra operación mantiene el bloqueo.

## Verificación automática sin interfaz

Desde el código fuente:

```text
python -I tests/test_mods.py
python -I tests/test_adjust.py
python -I tests/test_model_errors.py
python -I tests/test_cli.py
python -I tests/test_cli.py --exe "C:/ruta/TS3 Modding CLI.exe"
```

Usan paquetes sintéticos, carpetas temporales y ajustes aislados. La última orden comprueba
el ejecutable distribuido como un programa externo: argumentos, JSON, códigos de salida,
planes, instalación, verificación, conflictos y restauración. No requieren archivos del
juego. Estas pruebas no demuestran cómo se ve o se anima un mod dentro de Toy Story 3.
# Game explorer

`explore` reads the current game files, including installed mods. It does not alter the game, mod registry,
backups, or settings. The index cache lives in `%LOCALAPPDATA%/TS3 Modding Tool/explorer/` (next to the settings
file when `TS3TOOL_SETTINGS` is set). Every command accepts `--game PATH` and `--json`.

```text
python -I kit/cli.py explore index --game "D:/Games/Toy Story 3" --json
python -I kit/cli.py explore list --game "D:/Games/Toy Story 3" --query woody --kind oct --json
python -I kit/cli.py explore inspect assets/characters/woody/woody.zip --member woody.oct --game "D:/Games/Toy Story 3" --json
python -I kit/cli.py explore extract assets/characters/woody/woody.zip --out work/extracted-woody --game "D:/Games/Toy Story 3" --json
python -I kit/cli.py explore preview assets/characters/woody/woody.zip --member woody.oct --out work/woody-preview --game "D:/Games/Toy Story 3" --json
```

Without Python, replace `python -I kit/cli.py` with `"TS3 Modding CLI.exe"`. `kit/kit.py explore` also works.

| Command | Result / options |
|---|---|
| `index` | Number of assets and physical files, reused cache entries, per-file errors. `--refresh` bypasses cache. |
| `list` | `items`, `total`, `offset`, `next_offset`; default limit 200. Use `--limit 1..10000`, `--offset N`, `--query TEXT`, `--kind archive/oct/texture/sound/mesh/text/other`. `--refresh` rebuilds the index. |
| `inspect PATH [--member NAME]` | ZIP entries, OCT pools/textures and bounded record dump (with `model`: vertices, triangles, pieces, pieces left out, materials, bones, size, for an OCT with geometry), image dimensions, FMOD track metadata, or a bounded text/hex preview. |
| `extract PATH [--member NAME] --out NEW_DIRECTORY` | One asset, or all members of a ZIP when member is omitted. Preserves member paths. |
| `preview PATH [--member NAME] --out NEW_DIRECTORY` | PNG image, texture sheets, and `model.png` (wide scenes also `model-top.png`). Without `--member`, a ZIP previews its main `<name>.oct`. Works without OpenGL. |

Paths are relative to the game, under `assets/` or `data_dx/`. Member names come from `list` or `inspect`.
`--out` must not exist and must be outside the game. Extraction is staged before the new folder is published;
it rejects traversal, links in source paths, conflicting member names, changed sources and oversized files
(512 MiB per asset, 2 GiB per archive). Each read checks the live directory; cached metadata cannot authorize extraction.
Old front-directory archives sometimes omit CRCs (zero); size is still checked and nonzero CRCs are verified.

JSON uses `{schema_version: 1, ok, command: "explore.<action>", data, error}`. Exit 0 = success,
2 = invalid arguments, 3 = invalid source/operation, 5 = unexpected error, 130 = interrupted.
Expected error codes include `game_not_found`, `not_found`, `invalid_path`, `invalid_mod` (shared path validator),
`invalid_data`, `unsupported_format`, `destination_exists`, `size_limit`, `source_changed`, and `io_error`.
An index can succeed with partial results: always read `data.errors`. `list.next_offset` is null at the end.

3D and PNG previews read any model's vertex layout: characters, objects, vehicles and whole levels, framed on the
bulk of the model (a level's sky and clouds stay out of the PNGs). They use each material's diffuse map only:
no game lighting, effects or animation.
Sound inspection lists tracks, rates, channels and durations; it does not play or export decoded audio.
