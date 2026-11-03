# Formato de mods y gestor (esquema 1)

La herramienta reconoce una carpeta o ZIP con `mod.json`, los packs antiguos con
`patches/manifest.txt` y las carpetas que reproducen `assets/` o `data_dx/`. Acepta una
carpeta contenedora dentro del ZIP. No ejecuta los `.bat`, `.ps1`, `.exe` ni `.py` del pack.

El gestor está disponible por línea de comandos y desde la pantalla «Mods instalados».
En la ventana se puede arrastrar un ZIP o una carpeta de mod desde el Explorador. Los mods
con `update` avisan de versiones nuevas («Buscar actualizaciones» o `mods updates`).
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
- `update` es opcional: `{"github": "usuario/repositorio"}`. La herramienta compara la
  versión instalada con la última *release* de ese repositorio (su etiqueta, `v1.2` o `1.2.0`)
  y avisa con el enlace a su página. Nunca descarga nada; cada repositorio se consulta como
  mucho una vez al día (caché en `<juego>/TS3 Modding Tool/updates.json`).
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

Los paquetes antiguos reciben un ID `legacy.<huella del contenido>`. Su nombre y versión se
leen como texto (nunca se ejecuta nada): `$Name` / `$Version` de su instalador `.ps1`, si no la
primera línea del `README.txt` («Restored Songs for Toy Story 3      version 1.1»), si no el nombre
del ZIP o carpeta («… v1.1»); sin ninguno, `0.0.0`. Los ya instalados conservan lo que se
registró al instalarlos: para ver su versión, quítalos y vuelve a instalarlos.
No se inventan el autor, créditos o dependencias. Un cambio de contenido cambia ese ID;
añade `mod.json` para darles identidad estable entre versiones.

## Restauración y límites de esta primera versión

El registro se guarda en `<juego>/TS3 Modding Tool/installed.json`, y las copias originales
en `objects/`, identificadas por SHA-256. Se restaura exactamente el estado anterior a la
instalación, que puede incluir cambios de otro instalador. Los archivos nuevos se eliminan
al quitar el mod. Las copias se conservan tras desinstalar; aún no hay limpieza automática.

El gestor admite capas con prioridad revisada. En CLI, compartir un destino nuevo requiere
`mods plan/install --layer`; sin esa opción se mantiene el rechazo de conflictos de archivo.
Los parches de entradas distintas de un ZIP se combinan; si coinciden, gana la entrada completa del último
mod. No se mezclan texturas dentro de un mismo OCT. Los reemplazos de archivo completo sustituyen las
capas inferiores; los parches posteriores modifican ese archivo. No hay sobrescritura forzada de cambios
externos ni descarga automática de actualizaciones. Un paquete del mismo ID se
puede reemplazar desde ambas aplicaciones, o con `mods plan/install --replace`: se revisan las versiones,
se conservan los respaldos de la primera instalación y se restauran los destinos retirados del nuevo pack.
Los parches se aplican sobre aquel respaldo, no encima de la versión instalada. Una transacción fallida
o interrumpida vuelve a la versión anterior instalada, incluido su registro. Se validan tanto las nuevas
dependencias/conflictos como los requisitos de los mods que ya dependen de él. Se permiten packs
regenerados con la misma versión y bajadas compatibles; no se reemplazan otros IDs.
Un mod requerido por otro no se puede quitar mientras ese otro siga instalado.

`mods order` consulta el orden; `mods order ID... --dry-run` revisa uno nuevo, con todos los IDs instalados
de menor a mayor prioridad, y `mods order ID... --expect TICKET` lo aplica. Ambas ventanas tienen
«Prioridades de mods», botones para mover una capa y revisión antes de confirmar. Los nuevos mods van
al final; reemplazarlos conserva su posición. Quitar una capa reconstruye las restantes. El último devuelve
el archivo a su estado anterior a la primera instalación, incluido contenido externo que ya existía.

Los paquetes siguen siendo esquema 1. Los registros instalados de esquema 1 se convierten al 2 solo al
confirmar una operación con capas/orden: se conserva el respaldo `before`, cada salida independiente se guarda
en `objects/` y los archivos registran `kind` (`file`/`archive`), `payload` (SHA-256 de esa salida) y `after`
(SHA-256 del archivo compuesto actual). La lista `mods` define el orden. Las filas compartidas deben tener
la misma ruta, copia original y resultado. El gestor conserva los objetos tras desinstalar y no depende del
paquete original para reconstruir. Usa versiones actualizadas de ambas aplicaciones: las anteriores no leen
el registro 2. Preparación de snapshots nuevos y reconstrucción: 2 GiB por operación. No edites estos datos.

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
