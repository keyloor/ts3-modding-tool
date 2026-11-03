# CLI para personas y agentes de IA

El gestor está disponible en ambas aplicaciones: `TS3 Modding CLI.exe mods ...` y
`TS3 Mod Loader CLI.exe mods ...` usan el mismo protocolo y registro. Desde Python,
`kit/loadercli.py` ofrece el gestor sin importar las dependencias de creación; `mods` es opcional en esa entrada.
El Loader no ofrece los comandos de personajes, exploración o edición de texturas.

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
| `model-info MODELO.glb\|MODELO.gltf` | Inspección sin juego ni extracción: mallas, vértices, triángulos, articulaciones, pieles, mallas estáticas, materiales, imágenes, huella y advertencias. |
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

Para actualizar o probar un pack regenerado con el **mismo `id`**, usa `--replace` en ambas operaciones:

```text
mods plan PAQUETE --replace --game JUEGO --json
mods install PAQUETE --replace --game JUEGO --expect TICKET --json
```

La revisión devuelve `action: "replace"`, `replaces` (metadatos instalados), `restores` (rutas que ya no
incluye el nuevo pack) y todos los cambios en `files`. `restores` puede incluir archivos añadidos que se
eliminarán. `files[].before/after` describe los bytes actuales y finales, mientras que el registro conserva
el respaldo anterior a la primera instalación. Se admite reconstruir la misma versión o bajar de versión
si las dependencias instaladas siguen siendo compatibles; una incompatibilidad devuelve `dependent_version`.
Los ciclos de dependencias se rechazan con `dependency_cycle`, para que siga siendo posible quitar los mods.
La operación es una sola transacción: si se interrumpe, `recover` devuelve la versión anterior instalada.
Sin `--replace`, el mismo ID sigue rechazándose con `already_installed`. No descarga actualizaciones ni
permite compartir destinos entre distintos IDs. Con un ID aún no instalado, `--replace` instala normalmente.

El ticket es una huella del destino, la operación, los metadatos, el contenido resultante
y los archivos previos. Si alguno cambia, `--expect` bloquea la operación. Un ticket de
instalación no sirve para desinstalar ni para otra carpeta del juego. No es una credencial
ni sustituye las instrucciones del usuario.

### Capas y prioridades entre mods

Ambas aplicaciones ofrecen «Prioridades de mods». La lista va de menor a mayor prioridad: gana el último.
Los nuevos mods se añaden al final; un reemplazo del mismo ID conserva su posición. La ventana revisa las
capas antes de instalar; desde CLI, compartir destinos requiere `--layer` explícito en plan e instalación:

```text
mods plan PAQUETE --layer --game JUEGO --json
mods install PAQUETE --layer --game JUEGO --expect TICKET --json
mods order --game JUEGO --json
mods order autor.base autor.encima --dry-run --game JUEGO --json
mods order autor.base autor.encima --expect TICKET --game JUEGO --json
```

`order` sin IDs solo consulta. Para cambiarlo, proporciona **todos los IDs instalados exactamente una vez**,
de menor a mayor prioridad. La revisión devuelve `order`, `shared` ({`path`, `mods` en ese orden, `rule`}),
los archivos actuales/finales y un ticket ligado al juego, al registro completo y a las capas. `mods list`
incluye `priority` (1 es la menor). `--layer` se puede combinar con `--replace`; los nuevos destinos compartidos
siguen requiriéndolo. Actualizar un destino ya compartido conserva su configuración.

Los parches de entradas distintas de un ZIP se combinan. Si dos cambian la misma entrada, gana la de mayor
prioridad **completa**: no se mezclan texturas individuales dentro de un mismo OCT. Un `files` que reemplaza
el ZIP completo sustituye las capas inferiores; los parches posteriores modifican sus entradas. Los parches
se validan contra la copia original guardada, por lo que un pack basado en un OCT ya modificado por otra capa
puede ser incompatible. `requires` conserva su significado de dependencia instalada; no fija la prioridad.

Quitar o reemplazar una capa reconstruye las restantes sin necesitar los paquetes descargados. El último
mod de cada destino restaura su copia original (o elimina el archivo si no existía). No se ignoran cambios
externos, conflictos declarados ni dependencias. Cada operación usa el mismo diario y recuperación que antes.
`verify` compara el archivo compuesto y revisa las copias y los `layers[].status`; una capa ocultada por otra
puede estar correctamente instalada. Fallos de copias o contenido impiden reconstrucciones que los necesiten.

El primer cambio con capas/orden guarda `installed.json` de esquema 2 y snapshots SHA-256 por capa. Los
registros anteriores se leen sin cambiarlos; la migración ocurre solo al confirmar una operación. El esquema
del paquete y del protocolo JSON siguen siendo 1. Usa versiones actuales de ambas aplicaciones con registros 2;
las versiones antiguas no los entienden. No edites el registro ni borres objetos. Preparación/snapshots nuevos
y archivos reconstruidos: hasta 2 GiB por operación; la primera migración puede necesitar copias adicionales.
Errores específicos: `unsupported_layer`, `invalid_registry`, `size_limit`; se conservan `file_conflict`
(falta `--layer`), `external_change`, `backup_damaged`, `plan_changed` y los de dependencias.

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
| `glb PATH [--member NAME] --out NEW_DIRECTORY` | A self-contained `model.glb`, `report.json` and README for a supported character, object or level. Without `--member`, uses the ZIP's main `<name>.oct`. |
| `audio PATH [--member NAME] --track INDEX --seconds N --out NEW_DIRECTORY [--play]` | Decode a selected sample to `sample.wav` and `audio.json`. Default index 0, first 30 seconds; maximum 120. `--play` listens to the exported WAV; Ctrl+C stops. |

### Sound playback and WAV excerpts

Inspect an `.assets.bank` first to obtain its `sounds[].index`, name, rate, channels and duration.
In the explorer, Inspect/Preview opens the Sounds tab; select a sample, choose a duration, then Play/Stop
or Save WAV. Playback is explicit and stops when changing samples/assets or leaving the explorer.

```text
python -I kit/cli.py explore inspect data_dx/sound/ui_UI_bank00.assets.bank --game GAME --json
python -I kit/cli.py explore audio data_dx/sound/ui_UI_bank00.assets.bank --track 0 --seconds 5 --out work/sound-preview --game GAME --json
```

Windows: compressed samples use **the selected game's existing `fmod.dll`**, FMOD 2.03 with matching
architecture. It is neither downloaded nor redistributed. A private process decodes offline, bounded by
30 seconds of wall time and 96 MiB decoded data; Stop cancels it. PCM16 banks also decode without FMOD.
Output is PCM16 WAV, mono/stereo; multichannel samples use a parity-average stereo downmix for inspection,
not the game's spatial mix. The export starts at sample zero, is capped by `--seconds`, and reports
`decoded_seconds`, `decoded_channels`, `truncated` and `decoder` in addition to source metadata.
Names are metadata only; output filenames are fixed. No bank editing, event simulation or reinsertion yet.
Export requires a new folder outside the game. CLI playback requires Windows.

Audio refusals: `no_audio` (events bank; choose the matching `.assets.bank`), `invalid_audio`,
`unsupported_audio`, `sample_not_found`, `decoder_unavailable`, `decoder_failed`, `source_changed`,
`size_limit`, and `invalid_arguments`. Inspecting banks never loads FMOD. Decode failure leaves no export.

### GLB model export (first part of the Blender workflow)

```text
python -I kit/cli.py explore glb assets/characters/woody/woody.zip --out work/woody-glb --game GAME --json
python -I kit/cli.py explore glb assets/worlds/westerntown.zip --member westerntown.oct --out work/town-glb --game GAME --json
```

In the explorer, select the ZIP or OCT and choose **Export GLB model**. Open `model.glb` in a glTF 2.0 editor
such as Blender. Rigged character GLB/glTF files can now be used as project inputs through normal fitting
(see below), or on their verified original skeleton with `--fit identity`. Static object/level reinsertion
uses the separate bounded rigid-mesh workspace below; unrestricted object/level reinsertion remains pending.
No game content, installed-mod records or backups are modified by export.

Includes positions, unit normals, UVs (top-left texture origin, unchanged), triangle/material groups and embedded
PNG diffuse maps at their original resolution, up to 8192 pixels per dimension. It uses Y up and metres.
Materials use rough, nonmetallic surfaces and the preview reader's alpha-cutout heuristic; game shaders,
normal/specular maps, lighting and animations are not reproduced. Missing/unsupported diffuse maps become plain
white materials. `report.json` lists warnings and the pieces omitted by the supported geometry reader.

Skinned pieces include bone names/IDs, parent hierarchy, normalized four-influence weights and inverse bind
matrices. The rest skeleton is reconstructed from absolute pivots and local pivot differences; original bone
rotations/roll are not reconstructed. Static pieces remain outside the skin, including OCTs with both kinds.
Do not interpret a structurally valid export as a finished roundtrip or as proof of the result in game.

The standard JSON response (`command: explore.glb`) includes `output`, `files`, `vertices` (sum of compacted
primitive vertices), `source_vertices`, `triangles`, `bones`, `materials`, `images`, `materials_without_texture`,
`pieces_left_out`, `warnings`, source `path/member` and `credit`. The folder must be new and outside the game;
the GLB is staged and all source file signatures (including loose vertex/index buffers) are checked before
publishing. Limits: 5 million source vertices, 65535 bones, 512 MiB GLB. Game assets remain local.

Developer validation uses the [glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
and the [official Khronos validator](https://github.com/KhronosGroup/glTF-Validator), as a development-only tool:

```text
python -I tests/test_gltf.py --artifacts build/gltf-checks
npm.cmd install --prefix build/gltf-validator --no-save --ignore-scripts gltf-validator@2.0.0-dev.3.10
node tests/validate_gltf.cjs build/gltf-checks
```

The application and its exports do not need Node.js or the validator. Tests use synthetic geometry; never
add real game exports to the repository or upload them as CI fixtures.

### GLB/glTF character input

```text
python -I kit/cli.py model-info "C:/Models/character.glb" --json
python -I kit/cli.py make work/my-character --character woody --model "C:/Models/character.glb" --game GAME --json
```

The model picker accepts `.fbx`, `.obj`, `.glb` and `.gltf`. `--model` is an alias for the existing `--fbx`
option, and projects retain the `fbx` field for compatibility. Normal fitting needs a humanoid skin and
every mesh in the selected scene must be skinned: static or mixed files are refused before conversion, so
pieces cannot silently disappear. Use `model-info` to inspect static models or levels; use OBJ if automatic
rigging of a humanoid is desired. The usual bone mapping, fitting, adjustment, previews, pack export and mod
manager apply. Normal fitting can change proportions. To edit a character exported from this game and keep
its geometry on the original skeleton, explicitly select the following mode. Inspect previews and test in game separately.

#### Preserve the original skeleton

```text
python -I kit/cli.py make work/edited-woody --character woody --model "C:/Models/edited-woody.glb" --fit identity --game GAME --json
# Changing an existing project's mode requires regenerating its map (overwrites map edits):
python -I kit/cli.py make work/edited-woody --fit normal --remap --json
```

The window's step 3 offers **Preserve original skeleton**. `make --fit normal|identity` persists
`kit_project.json.fit_mode`; absent means `normal`, preserving existing projects. Identity accepts only
GLB/glTF with every mesh skinned, including nonhumanoid rigs if they match the chosen character.
It matches each source joint by integer `extras.ts3BoneId`, or its exact unique name when the ID is absent.
An unknown/present ID never falls back to a name. Source joints cannot merge into one game bone; pivots
must match within 0.00001 m and the hierarchy must agree after skipping absent/unweighted ancestors.
New bones, moved pivots, reparenting and more than four distinct positive influences per vertex are refused.
Names may change if BoneIDs survive the editor; otherwise retain the game names. Retain the rest pose,
scale and armature when exporting from your editor. Validate against the same original target character.

Identity skips humanoid fitting, `DRIVE`, proportion/joint/face adjustments and weight smoothing; saved
project adjustments/bone overrides remain available when returning to normal mode. The Adjustments tab,
joint dragging and bone remapping are inactive. Materials remain editable. Source positions, winding and
UVs are retained at TS3 storage precision (float32 positions, float16 UVs/normals); normalized weights are
quantized to four bytes summing to 255. Original byte weights survive export/import. The target's original
skeleton matrices, IDs, hierarchy and animation network remain; only geometry counts/bounds are updated.
Tangents, piece ordering, materials and texture encoding are rebuilt by the converter. Colour-palette or
explicit material edits may remap UVs. This is not byte-identical archive preservation or animation import.
The GLB exporter still represents bones by pivots, without reconstructing original bone roll/rotations.

Generated identity maps explicitly contain `IDENTITY = True`. A reused map must agree with the project mode;
`map_mode_mismatch` asks for `--remap`. Do not overwrite a hand-edited map without retaining its edits.
Skeleton/weight validation runs before rotating a previous successful `out/` directory. JSON `make.data`
includes `fit_mode`; `adjust --info` includes the verification report under `info.identity` and no normal
fit strain. `diagnose` still reports guessed materials. Tests: `tests/test_identity.py [--exe CLI]`.

The reader supports glTF 2.0 GLB binary chunks, JSON with local buffers, and base64 data URIs. It reads the
selected/default scene, matrix/TRS node transforms, mirrored winding, inverse-transpose normals, triangle
lists/strips/fans, sparse/interleaved accessors and normalized byte/short UVs/weights. Skinning includes
inverse bind matrices and up to eight source weight slots; the game converter retains its limit of four
bone influences. Default joint poses are baked into source geometry; animation clips are ignored. UVs are
adapted to the existing converter contract so the game's top-left texture origin is preserved.

PNG/JPEG diffuse and normal images are extracted only into the project's `model-textures/<content-hash>/`
folder. Base colour factors are baked into diffuse PNGs in linear colour space; other PBR shading does not
transfer to the game. Generated textures refresh when source content changes. Existing generated files are
validated and never overwritten if edited; select that edited folder explicitly with Change textures or
`--textures`. Reading/model-info never extracts files or changes user settings. A chosen texture override
folder is preserved. Direct links use the generated `material_NNNN_d/n.png` names.

Unsupported inputs are refused with a useful error: required extensions other than `KHR_materials_unlit`,
Draco/Meshopt compression, morph targets, nonwhite vertex colours, texture transforms, extra texture UV
sets, nonunit normal-map scale, nontriangle primitives and more than eight skin slots. Missing/zero normals
are regenerated and reported. `model-info` returns `command: kit.model-info` with the standard JSON envelope;
errors retain `invalid_data`, `invalid_path`, `unsupported_format`, `size_limit` or `io_error` as appropriate.

Resources must be local files inside the model's folder or base64 data; no remote/absolute URIs, traversal,
symlinks/junctions in resource paths or external downloads. Limits: 512 MiB per file, 1 GiB read resources,
32 MiB JSON, 20000 nodes, 5 million imported vertices, 4096 images/materials and 8192 pixels per image side.
The parser checks byte bounds, component layouts, node cycles, skeleton references and finite transforms.
Ordinary FBX/OBJ routing and converter output rules remain unchanged. Tests: `tests/test_gltflib.py [--exe CLI]`.

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
Sound inspection lists sample metadata; `explore audio` exports decoded WAV excerpts and optionally plays them.

## Texture workspaces and packs

The same commands work with `kit/cli.py`, `kit/kit.py`, or `TS3 Modding CLI.exe`. All take `--json` and
`--game GAME`. Exporting/building reads the game; installation is a separate mod-manager operation.

```text
python -I kit/cli.py textures dump assets/characters/woody/woody.zip --member woody.oct --out work/woody-textures --game GAME --json
# Edit some PNGs in work/woody-textures with your image editor, keeping their dimensions.
python -I kit/cli.py textures build work/woody-textures --out work/my-texture-pack --id myname.woody-textures --name "My textures" --author "My name" --version 1.0.0 --game GAME --json
python -I kit/cli.py mods plan work/my-texture-pack --game GAME --json
python -I kit/cli.py mods install work/my-texture-pack --game GAME --expect TICKET --json
```

`textures dump ARCHIVE [ARCHIVE ...] --out NEW_FOLDER [--member OCT] [--shared]` exports all readable TexturePool
images from one or more selected game ZIPs. `--member` selects one OCT and requires exactly one archive;
otherwise every OCT is exported. Default PNG paths remain stable: archive/member/index_name.png.
`index.json` records the source archive hash, each OCT/DDS/PNG hash, dimensions, format, mip count and editability.
`data.errors` reports unreadable images; readable formats without an encoder are exported with `editable: false`.
The workspace contains game images and is for local editing, not redistribution.

For a texture repeated across world variants, select the archives together and opt into `--shared`:

```text
python -I kit/cli.py textures dump assets/worlds/westerntown.zip assets/worlds/wt_trendy.zip --shared --out work/toybox-textures --game GAME --json
```

Shared mode writes one PNG per **byte-identical DDS**, under `shared/CRC32_SHA256.png`. Editing it replaces
every matching occurrence listed in the workspace, only in the selected archives. Different DDS formats,
headers or mipmaps remain separate even if they look the same; CRC collisions cannot combine different DDS.
Deleting a shared PNG skips its whole group. Leave `--shared` off for independent edits of each occurrence.
The GUI offers «Export multiple ZIPs» and an unchecked-by-default shared-PNG option with the same scope.
Single-archive/default exports still write schema 1. Multi-archive/shared workspaces write schema 2,
with `archives: [{path, sha256, md5}]`, `mode: separate|shared` and an `archive` field on each texture row.
Both schemas remain readable; existing workspaces are never migrated or rewritten.

`textures build WORKSPACE --out NEW_FOLDER --id ID --name NAME --author AUTHOR [--version 1.0.0]` compares PNG
hashes. Unchanged or deleted PNGs are ignored; edited PNGs replace their corresponding DDS. Supported encoders:
DXT1/DXT3/DXT5 and byte-aligned 32-bit RGB(A). Dimensions, header, alpha capability and original mip count stay
the same. Cubemaps, volume textures, padded rows and other pixel formats cannot be edited yet. The builder
updates DataCRC and checks OCT read/write equality. If any selected source archive has changed, export a new
workspace. Only archives containing edited textures enter the pack. All patches are prepared in a temporary
folder and published together, so a later archive failure cannot leave a partial pack.

The output is a data-only mod folder (`mod.json`, patches, README); drag it onto the tool or use `mods install`.
It contains changed OCT entries only, never complete game archives or the exported PNG workspace. Packs built
from installed mods require the same source OCT baseline in the receiving game. Install shared archives with
`mods plan/install --layer` and inspect the priority order. Distinct members compose; a coinciding OCT uses
the higher priority OCT as a whole. Per-texture merging inside one OCT is not implemented.
Keep `--id` unchanged when creating a new version of the same pack. The window derives a stable ID from the workspace.

Both output folders must be new and outside the game. Pack output must also be outside the workspace.
Limits: 256 source archives per workspace, 512 MiB per source archive for pack building, 20000 exported texture
occurrences, 64 MiB per edited PNG, 2 GiB of edited PNGs/replacement OCTs/patch payload, 8192 pixels per dimension.
No texture upscaling in this version. Cross-mod priorities use the shared manager described above.

JSON has the standard envelope, with `command: textures.dump` or `textures.build`; exit codes match `explore`.
`dump.data` contains `output`, `textures` (occurrences), `png_files`, `archives`, `shared`, `editable`, `errors`;
`build.data` contains `output`, `textures` (changed occurrences), `png_files` (edited images), `archives` (patched
archives), `oct_files`, `metadata`. Expected refusals include `nothing_changed`, `source_changed`, `size_mismatch`,
`unsupported_format`, `destination_exists`, `invalid_path`, `size_limit`, `invalid_data`, and `invalid_mod`.

## Rigid mesh workspaces and packs

```text
python -I kit/cli.py meshes dump assets/objects/example.zip --member example.oct --out work/object-mesh --game GAME --json
# Edit model.glb, preserving its triangles and _TS3_VERTEX point attribute.
python -I kit/cli.py meshes build work/object-mesh --model work/object-mesh/edited.glb --out work/object-pack --id myname.object --name "My object" --author "My name" --game GAME --json
python -I kit/cli.py mods plan work/object-pack --game GAME --json
python -I kit/cli.py mods install work/object-pack --expect TICKET --game GAME --json
```

The explorer offers **Export editable mesh** on an OCT member inside a ZIP, then **Build mesh pack**.
This is a separate export from `explore glb`: only the editable workspace writes `_TS3_VERTEX`
correspondence. It contains `model.glb`, `mesh.json`, `report.json` and instructions. Keep game exports local.
`--member` is required. `build --model FILE` is optional; by default it reads the workspace's `model.glb`.
The GUI lets you select the edited file. Keep the workspace ID/mod ID across versions; use the manager's
existing `--replace` workflow for later builds. Building/exporting never installs anything.

Supported edits are positions, normals and first UVs on visible **rigid** geometry, retaining its exact
triangle connectivity. Vertex/triangle order may change; correspondence and face multiplicity are checked.
Do not add/delete vertices/faces, subdivide, decimate, remesh or change triangulation. Preserve the
`_TS3_VERTEX` float point attribute. In Blender, enable **Data > Mesh > Attributes** on glTF export;
see the [Blender manual](https://docs.blender.org/manual/en/5.0/addons/import_export/scene_gltf2.html).
Editor-created seam duplicates must agree on each original vertex's position/normal/UV. Missing IDs,
conflicting splits or topology changes cause a refusal; the builder never guesses by vertex order.
Blender visual roundtrip testing remains pending; a validator pass does not verify editor preservation.

The builder reloads the live source, checks the archive/OCT hashes, transforms edits back into each
original stream's local coordinates, and changes only its supported float32/float16 fields. It preserves
indices, material/texture assignment, unknown attributes, hidden/unsupported pieces and gameplay data.
GLB material edits are ignored; use texture workspaces for textures. Tangents/binormals on incident faces
are rebuilt when those streams exist. Changes below 1e-6 m in positions, 2e-6 in normalized normals and
2e-7 in UVs are ignored to avoid re-export noise. Storage rounding can also produce `nothing_changed`.
Shared buffer instances must request identical local-space values; edits overlapping hidden/unexported
streams are refused. Original bounding boxes, sphere radii and oriented extents expand as needed and never
shrink. Centers/axes stay, with conservative OBB expansion enclosing both axis conventions.
**Collisions do not follow shape edits**: collision buffers, navigation and gameplay remain unchanged.
Preserve mode does not support skins, position-only collision meshes, combined/unknown bounding-sphere
records, new topology, or unrestricted level reconstruction. Explicit topology replacement is described below. Small rigid OCTs inside levels
may qualify; a complete level often exceeds the limits or contains unsupported/shared geometry.

Limits: one OCT from one ZIP, 250000 visible vertices, 512 MiB source archive/buffers, standard bounded
GLB/glTF input resources (see above). Archives/OCTs must still match export time; otherwise export again.
Destinations must be new/outside the game, with pack output outside the workspace. Output is staged and
published only after final source checks. Packs use the existing patch/backup protocol and exclusive
archive ownership. Inspect with `mods plan`; remove with `mods remove ID` to restore baseline bytes.

JSON uses the standard envelope with `command: meshes.dump|meshes.build`, exit 0/2/3/5/130.
Dump returns source/workspace metadata, vertex/triangle counts and omitted pieces. Build returns metadata,
`vertices_changed`, `bounds_expanded` and changed archive member names in `files`. Refusals include
`missing_correspondence`, `topology_changed`, `shared_vertex_conflict`, `source_changed`, `nothing_changed`,
`unsupported_format`, `invalid_data`, `invalid_path`, `destination_exists` and `size_limit`.
Tests: `python -I tests/test_meshes.py [--exe CLI]`; no game assets in fixtures.

### Replace one rigid piece's topology

```text
python -I kit/cli.py meshes build work/object-mesh --model work/new-shape.glb --topology replace --out work/object-topology-pack --id myname.object --name "My object" --author "My name" --game GAME --json
```

In **Build mesh pack**, tick **Replace topology**. It is unchecked by default; CLI default is
`--topology preserve`. Use the existing mesh workspace to identify and verify the source. Replace mode
accepts an unskinned GLB/glTF with added/deleted vertices and faces; `_TS3_VERTEX` is not required and any
old/interpolated correspondence attributes are ignored. A new input can contain several meshes/primitives
if all use the same material. They are combined onto the source piece's original material. Texture/PBR
changes in the replacement are ignored; collisions, animations and gameplay remain original.

Without an explicit selection, the source OCT must have **exactly one visible rigid piece**. For compound
objects select the visible lit piece by node index (see below); otherwise `ambiguous_target` refuses to guess.
Hidden/omitted and unselected visible pieces remain on their original
streams, even if they previously shared buffers with the replaced piece. Node/association references and
original material/texture pools stay. The builder appends separately aligned vertex/index data and cloned
streams, then points only the selected piece at them. Original buffer prefixes remain byte-identical;
old unused data is retained. Each build starts from the verified original workspace source, avoiding
growth from repeatedly modifying a previous build.

Supported source attributes: Position float32x3; first UV float32x2/float16x2; Normal/Tangent/Binormal
float32x3 or float16x4. The source layout/stride is reused, tangent frames regenerated, source matrices
applied inversely. Unknown attributes, duplicate UV layouts, nonempty scene-component references, variable
extra components or variable padding are refused; their values cannot be reconstructed for new vertices.
Missing source UV storage cannot accept a nonzero replacement UV set. All original bounding volumes are
expanded conservatively to include the geometry **after storage rounding**, retaining original centers.
Combined unknown `BoundingSphere` records or invalid/nonorthogonal OBB axes are refused.

Limits: 65535 imported vertices, 1000000 triangles, original index width (a byte-index source is limited
to 256 referenced vertices), 512 MiB of replacement buffers. The existing source/workspace/GLTF limits
also apply. Skins, replacing several pieces in one build, new materials, collision changes and unrestricted level
creation remain pending. Test appearance in game separately; Blender visual roundtrip is not yet verified.

Build JSON adds `topology: replace`, `vertices_before/after`, `triangles_before/after`. For `preserve`,
`topology` is also reported. An explicit replacement can rebuild unchanged geometry; it is not a
byte-identical no-op. Install/replace/remove through the existing manager, preserving the same mod ID.
Tests: `python -I tests/test_meshtopo.py [--exe CLI]` covers geometry growth/shrinkage, transformed targets,
hidden aliases, bounds, layouts, limits and transactional restoration.

### Select a piece in a compound object

```text
python -I kit/cli.py meshes pieces assets/objects/example.zip --member example.oct --game GAME --json
# Or inspect a previously exported workspace:
python -I kit/cli.py meshes pieces work/object-mesh --game GAME --json
# Use a node index returned by pieces, not its ordinal or an ambiguous name:
python -I kit/cli.py meshes dump assets/objects/example.zip --member example.oct --piece 4 --out work/piece-4 --game GAME --json
python -I kit/cli.py meshes build work/piece-4 --model work/edited-piece.glb --topology replace --out work/piece-pack --id myname.object --name "My object" --author "My name" --game GAME --json
# An existing whole-model workspace can instead choose the target explicitly at build time:
python -I kit/cli.py meshes build work/object-mesh --model work/edited-piece.glb --topology replace --piece 4 --out work/piece-pack-2 --id myname.object --name "My object" --author "My name" --game GAME --json
```

`meshes pieces SOURCE [--member OCT]` returns `archive`, `member`, and `pieces`: each has `node`, `name`,
original `material` index, `vertices`, `triangles`, `supported_layout` and `reason`. These are fresh reads,
not trusted cached offsets. Workspace queries verify export-time source hashes. `supported_layout` reports
structural eligibility; remaining padding/component/input checks run when building. Only exported visible
rigid pieces are listed; hidden nodes are not replacement targets. Duplicate names are safe because selection
uses the OCT node index, stable only while the verified source is unchanged.

In the explorer, **Export editable mesh** offers the whole model or a specific piece when several are
visible. Whole-model export retains the preserve-mode workflow. A selected-piece export contains only that
piece's triangles/material and records its default `piece` in mesh.json. Such a workspace requires
`--topology replace`; the GUI preselects its node and mode. Old workspaces remain readable. The pack dialog
also offers an explicit piece selector for whole-model workspaces. Automatic selection still works for a
single-piece source; compound sources must choose a node. Pass `--piece` only with replace mode.

The edited GLB must contain the replacement for the chosen piece, not the entire compound object. It can
add/remove geometry within existing replacement limits and uses that piece's original material. Shared
visible instances are detached only for the selected node. Original buffer regions, all other node/stream
references, materials/textures and collision data remain. Before publishing, the builder reloads the result
and checks the selected piece's counts plus unselected visible pieces' positions, UVs and material assignments.
One piece is replaced per pack build; simultaneous multi-piece edits and unrestricted level work remain pending.
The whole-source 250000-vertex/512 MiB limits still apply, even to partial exports.

Build JSON includes `piece_node`, `piece_name`, `pieces_preserved` (other visible pieces), per-piece
`vertices_before/after`, `triangles_before/after`, and `model_vertices_before/after`,
`model_triangles_before/after`. Invalid/nonvisible nodes return `piece_not_found`; invalid selectors or
preserve-mode partial workspaces return `invalid_arguments`. Tests: `tests/test_meshselect.py [--exe CLI]`.
