# Formato de mods y gestor (esquema 1)

La herramienta reconoce una carpeta o ZIP con `mod.json`, los packs antiguos con
`patches/manifest.txt` y las carpetas que reproducen `assets/` o `data_dx/`. Acepta una
carpeta contenedora dentro del ZIP. No ejecuta los `.bat`, `.ps1`, `.exe` ni `.py` del pack.

El gestor está disponible por línea de comandos y desde la pantalla «Mods instalados».
La interfaz y el soporte para arrastrar paquetes están implementados; su prueba manual
completa queda a cargo del usuario. La consulta de actualizaciones sigue pendiente.
Para automatización, salida JSON, planes y verificación, consulta [CLI.md](CLI.md).

## Uso

Desde la carpeta de la herramienta (con Python):

```text
python -I kit/kit.py mods inspect "C:/Downloads/Mi mod.zip"
python -I kit/kit.py mods install "C:/Downloads/Mi mod.zip" --game "D:/ruta/al/juego"
python -I kit/kit.py mods list --game "D:/ruta/al/juego"
python -I kit/kit.py mods remove autor.mi-mod --game "D:/ruta/al/juego"
python -I kit/kit.py mods recover --game "D:/ruta/al/juego"
```

Sin `--game`, se busca la instalación de Steam. `inspect` solo lee los metadatos; la
instalación valida también los parches y sus sumas de comprobación. `list` muestra los
identificadores necesarios para `remove`. En PowerShell, sin Python:

```powershell
& '.\TS3 Modding CLI.exe' mods inspect 'C:/Downloads/Mi mod.zip' --json
```

El ejecutable de consola devuelve el resultado directamente al terminal o al agente.
El juego debe estar cerrado para instalar, quitar o recuperar una operación interrumpida.

## mod.json

Ejemplo de un mod con un archivo de audio y un conjunto de parches:

```json
{
  "schema_version": 1,
  "id": "autor.mi-mod",
  "name": "Mi mod",
  "version": "1.0.0",
  "author": "Autor",
  "description": "Descripción del mod",
  "game": "ts3-pc",
  "requires": [],
  "conflicts": [],
  "credits": ["Créditos del contenido"],
  "patches": [{"manifest": "patches/manifest.txt"}],
  "files": [{"source": "audio/music.bank", "target": "data_dx/music.bank"}]
}
```

- `id`: identificador permanente, letras minúsculas ASCII, números, puntos, guiones y
  guiones bajos (hasta 128 caracteres). No debe cambiar al publicar otra versión.
- `version`: tres enteros sin ceros iniciales. `1` y `1.0` se normalizan a `1.0.0`.
  En el esquema 1 no se admiten versiones preliminares ni sufijos.
- `requires` y `conflicts`: listas de `{"id": "autor.otro", "version": ">=1.2.0"}`.
  Las condiciones admitidas son `*`, una versión exacta, `==versión` y `>=versión`.
  Una dependencia debe estar instalada; los conflictos se comprueban en ambas direcciones.
- `patches`: rutas a manifiestos generados por `build_release.py`. Sus `.txt` y `.bin`
  deben estar junto al manifiesto. Conservan el formato y los MD5 del instalador anterior.
- `files`: correspondencias explícitas entre archivos del paquete y destinos del juego.
- `credits`: lista de textos. `author` y `description` son textos y pueden estar vacíos.
- `update` es opcional: `{"github": "usuario/repositorio"}`. Se valida y conserva;
  esta primera implementación todavía no consulta GitHub ni descarga actualizaciones.
- `requires`, `conflicts`, `credits`, `patches` y `files` vacíos pueden omitirse.
  Debe haber al menos un parche o archivo. Se rechazan versiones de esquema desconocidas.

Todas las rutas son relativas. Los destinos se limitan a `assets/` y `data_dx/`. Se rechazan
rutas absolutas, `..`, dispositivos Windows, ADS, enlaces, junctions y entradas duplicadas
sin distinguir mayúsculas. Límites: 20 000 archivos, 512 MiB por archivo de paquete y
2 GiB de contenido total. Los metadatos del ZIP se verifican antes de leer sus entradas.

## Compatibilidad y exportación

`kit.py export` incorpora `mod.json` y conserva los instaladores anteriores. Al exportar por
primera vez, guarda un `mod_id` generado en `kit_project.json`; las siguientes exportaciones
del mismo proyecto lo reutilizan, aunque cambie el nombre. Para derivar un mod independiente,
asigna otro `mod_id` al proyecto copiado. El resto del formato de parches no cambia.

Los paquetes antiguos reciben un ID `legacy.<huella del contenido>` y versión `0.0.0`.
No se inventan el autor, créditos o dependencias. Un cambio de contenido cambia ese ID;
añade `mod.json` para darles identidad estable entre versiones.

## Restauración y límites de esta primera versión

El registro se guarda en `<juego>/TS3 Modding Tool/installed.json`, y las copias originales
en `objects/`, identificadas por SHA-256. Se restaura exactamente el estado anterior a la
instalación, que puede incluir cambios de otro instalador. Los archivos nuevos se eliminan
al quitar el mod. Las copias se conservan tras desinstalar; aún no hay limpieza automática.

Cada archivo del juego tiene un solo propietario en el gestor. Dos mods que cambian el
mismo ZIP se consideran incompatibles incluso si modifican entradas diferentes. No hay
sobrescritura forzada, prioridades ni actualización automática: primero hay que quitar
la versión anterior. Un mod requerido por otro no se puede quitar mientras ese otro siga instalado.

Si un archivo cambia fuera del gestor, se bloquea la desinstalación completa y se conservan
el registro y las copias. Los botones antiguos de instalar/restaurar proyectos también
rechazan los archivos que estén registrados en el gestor. Otros instaladores externos
no están sujetos a ese bloqueo.

Cada operación valida y prepara todos sus archivos antes de modificarlos. Un diario
`transaction.json` permite deshacer los cambios si falla una escritura o se interrumpe el
proceso. La próxima instalación/desinstalación recupera primero la operación pendiente;
`mods recover` lo hace explícitamente. Si hubo cambios externos después de la interrupción,
se detiene y conserva el diario para evitar sobrescribirlos. No se deben borrar las copias
ni editar el registro mientras haya una operación pendiente.

Estas garantías cubren errores e interrupciones del proceso; no sustituyen las garantías
del sistema de archivos ante una avería física o pérdida de alimentación.

## Comprobación

```text
python -I tests/test_mods.py
```

Las pruebas usan paquetes sintéticos y una carpeta temporal: exportación completa,
compatibilidad ZIP/carpeta, parches byte a byte, conflictos, dependencias, rutas peligrosas,
backups dañados, bloqueo concurrente y recuperación de instalación/desinstalación.
No requieren archivos del juego ni modifican los ajustes personales.
