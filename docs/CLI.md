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

`kit/kit.py mods ...` también admite este protocolo. Los comandos anteriores de personajes
(`doctor`, `characters`, `make`, `install`, `restore`, `export`) funcionan desde la CLI con
sus argumentos habituales; **`--json` se aplica únicamente a los subcomandos `mods`**.
No se automatiza la edición de huesos o controles de la ventana con este protocolo.

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
python -I tests/test_cli.py
python -I tests/test_cli.py --exe "C:/ruta/TS3 Modding CLI.exe"
```

Usan paquetes sintéticos, carpetas temporales y ajustes aislados. La última orden comprueba
el ejecutable distribuido como un programa externo: argumentos, JSON, códigos de salida,
planes, instalación, verificación, conflictos y restauración. No requieren archivos del
juego. Estas pruebas no demuestran cómo se ve o se anima un mod dentro de Toy Story 3.
