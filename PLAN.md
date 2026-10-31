# Toy Story 3 Modding Tool — plan

**Toy Story 3 Modding Tool** (TS3 Modding Tool): una herramienta + guía para Nexus para modificar Toy Story 3 Complete
Edition sin saber programar. Empezó como «TS3 Character Kit» (solo personajes); desde el 30/10/2026 es la herramienta
general de modding del juego, con secciones:

| Sección | Estado | Base que ya tenemos |
|---|---|---|
| Personajes: tu modelo (FBX u OBJ) en lugar de Woody, Buzz o Jessie | Hecha (fases 1–5) | `kit/`, `tools/convert.py` |
| Música y sonidos | Próximamente (en la ventana, marcada así) | `tools/fmodbank.py`, el mod `mods/restored/` |
| Texturas (personajes, decals, niveles) | Próximamente | `tools/add_decals.py`, el mod `mods/buzz_original_decals/` |

La carpeta es `mods/ts3_modding_tool/` (antes `mods/character_kit/`, renombrada el 30/10/2026).

Autor de la herramienta: **keyloor** (se cambia en un solo sitio: `kit/about.py`).

## Qué recibe la gente en Nexus

| Archivo | Qué es |
|---|---|
| `Toy Story 3 Modding Tool.exe` | La app (Windows, no hace falta instalar Python) |
| `Guia/` | La guía del asistente en HTML (y PDF), con capturas |
| `docs/GUIA_MANUAL.md` | La guía para hacerlo **todo a mano**, sin nada automático: preparar el modelo, escribir el mapa tabla por tabla (con un mapa completo de Mixamo), leer el registro del convertidor, arreglos típicos, ojos cerrados, instalar, y un apéndice con los formatos del juego |
| `AGENTS.md` | Instrucciones para agentes de IA: todo lo necesario para que un agente lo haga solo, como lo hacemos aquí (el ciclo, qué comprobar en cada paso, los nombres de huesos del juego, las reglas) |
| `docs/ejemplos/` | Nuestros mapas reales como ejemplos: ojos y pestañas (TS5), varios materiales (CJ), paleta de colores (KH3 Buzz), pesos repartidos (KH3 Woody) |
| `CREDITS.md` | Autor (keyloor), referencias a DisneyInfinityTools y DisneyInfinityCreator, software de terceros |
| `skill/ts3-modding-tool/` | Una skill (`SKILL.md`) para quien quiera hacerlo con su agente de IA (Claude Code u otro que lea skills): los pasos, las opciones del mapa y las reglas |
| `LICENSE`, `NOTICE.md`, `docs/CREDITS.md` | Licencia (GPL v3 + condiciones añadidas) y créditos (ver abajo) |

No se incluye ningún archivo del juego ni ningún modelo de otros juegos: la app extrae lo que necesita de la copia del
juego de cada persona, y cada persona trae su modelo.

## Dos niveles

**Básico (el asistente):**
1. Carpeta del juego → la app extrae los archivos del personaje elegido.
2. Personaje a reemplazar: Woody, Buzz o Jessie.
3. FBX + carpeta de texturas.
4. Mapeo automático de huesos (`kit/automap.py`), con una tabla para corregir lo que haga falta.
5. Vista previa (cuerpo, primer plano, brazos abajo).
6. Instalar / Restaurar en el juego.
7. Exportar el pack para Nexus (instalador incluido, con el crédito "Hecho con TS3 Modding Tool de keyloor").

**Avanzado (sin límites):**
- El asistente guarda el mapa como un archivo `.py` normal, el mismo formato que usamos en nuestros mods. Quien sepa
  puede abrirlo y usar todas las opciones del convertidor: ojos (`EYE_MODE`, `LASHES`), cara (`FACE_ALIGN`,
  `FACE_BONES`), pesos repartidos (`{hueso: parte}`, `WEIGHT_RAMP`, `WEIGHT_SCALE`), varios materiales (`MATERIALS`,
  `TEXTURES`, colores sólidos), piezas que se conservan (`KEEP_PIECES`), escala por material…
- La app puede cargar un mapa hecho a mano en lugar de generar uno.
- Todo se puede hacer también desde la línea de comandos (`kit.py`), para automatizar.
- La guía tiene un capítulo por opción avanzada, con ejemplos sacados de nuestros mods.

## Cómo se construye

- **El núcleo no cambia**: `tools/convert.py`, `render.py`, `install.py`, `build_release.py`, etc. La salida de
  `ts5_characters` tiene que seguir siendo idéntica byte a byte.
- **Capa nueva en `mods/ts3_modding_tool/kit/`**:
  - `automap.py`: FBX → mapa. Encuentra el esqueleto humano por la forma del esqueleto (cadera, piernas, columna,
    brazos, manos, dedos, cabeza) y usa los nombres de los huesos solo para desempatar, así que sirve con Mixamo,
    Fortnite, Unreal, GTA, KH3… sin una lista de nombres por cada rig. Los nombres de los huesos del juego también se
    resuelven solos (Buzz dice `SternumLeft` e `IndexLeft1`, Woody `ClavicleLeft` e `Index1Left`).
  - `kit.py`: los pasos en orden (extraer, mapear, convertir, comprobar, vista previa, instalar, exportar).
  - `app.py`: la interfaz (tkinter, que viene con Python: nada extra que instalar ni que licenciar).
  - Empaquetado con PyInstaller en una carpeta con el `.exe`.

## Fases

| # | Fase | Lista cuando |
|---|---|---|
| 1 ✅ | `automap.py` (esqueleto) | Genera mapas para los 6 FBX que tenemos (TS5 ×3, KH3 ×2, CJ) que coinciden con los nuestros en lo principal, y uno convertido pasa `rt.py` y se ve bien en la vista previa |
| 2 ✅ | Texturas automáticas | Lee qué textura usa cada material del FBX y escribe `MATERIALS`/`TEXTURES` solo |
| 3 ✅ | `kit.py` (línea de comandos) | Un comando hace todo, de FBX a juego instalado |
| 4 ✅ | `app.py` (interfaz) | El asistente completo, con la tabla de huesos editable y las vistas previas |
| 5 ✅ | `.exe` + exportar pack | El `.exe` funciona en un Windows sin Python; el pack exportado se instala con el instalador de siempre |
| 6 | Guía + skill | Guía en HTML + PDF en español e inglés, con capturas del asistente y del juego; la skill actualizada a los comandos finales (`kit.py`) y probada con un agente desde cero |
| 7 | Nexus | Página, imágenes, permisos, subida |

Resultado de la fase 1 (30/10/2026): en los 6 FBX el cuerpo (piernas, brazos, manos, dedos, cuello, cabeza) sale igual
que en nuestros mapas hechos a mano; los accesorios que el juego tiene (sombrero, funda, pelo de Jessie, alas de Buzz)
se reconocen por nombre; la cara queda en `Head` (modo básico). CJ convertido con el mapa automático pasa `rt.py` y se
ve igual que el hecho a mano en la vista previa (sin los dos retoques manuales: vaqueros más estrechos y cabeza 3,5 cm
más abajo). No probado en el juego.

Resultado de la fase 2 (30/10/2026): `kit/autotex.py` (o `automap.py ... <carpeta de texturas>`). Ninguno de nuestros
FBX enlaza sus texturas, así que empareja material ↔ imagen por nombre (con sinónimos: skin ~ head…), encuentra la
normal/ORM de cada imagen por su nombre, usa el color del material si no hay imagen, y quita mallas repetidas. CJ, KH3
Woody y TS5 Woody, convertidos **sin nada hecho a mano**, pasan `rt.py` y se ven como los nuestros en la vista previa.
KH3 Woody deja 2 materiales pequeños marcados "CHECK" (adivinados); KH3 Buzz (imágenes con nombres como `n_ts202_0d00`)
necesita el modo manual. Los dos Woody salen con los ojos cerrados, como vienen sus modelos: abrirlos es modo avanzado
(`EYES`), o una fase futura.

Resultado de la fase 3 (30/10/2026): `kit/kit.py` con cuatro órdenes. `characters` encuentra el juego solo (registro de
Steam y sus bibliotecas) y marca los personajes que otro mod ya cambió. `make <proyecto>` extrae el personaje, escribe
`map.py`, convierte, comprueba byte a byte, dibuja `previews/body.png` y `face.png` y guarda `report.txt`; se niega a
trabajar sobre un archivo modificado por otro mod, y al repetirlo respeta el `map.py` editado. `install` y `restore`
guardan la copia del original junto al juego (`TS3 Modding Tool backup`). Probado con CJ y KH3 Woody, e
`install`/`restore` en una copia falsa de la carpeta del juego; no en el juego real, que ahora tiene otro mod en los
tres personajes.

Resultado de la fase 4 (30/10/2026): `kit/app.py`, una ventana (tkinter) en español e inglés (menú Idioma). Tiene:
- los campos del proyecto (juego encontrado solo, personaje en una lista, FBX, texturas);
- los botones 1. Analizar, 2. Convertir, 3. Instalar y Restaurar original;
- pestañas Huesos, Materiales, Vista previa (cuerpo y cara) y Registro.

En las tablas, doble clic cambia una parte del cuerpo (por ejemplo «la rodilla izquierda es este hueso») o un material
(otra imagen, un color, o dejarlo fuera). Lo elegido se guarda en `kit_project.json` y también vale para `kit.py make
--remap`. «Modo avanzado» usa el `map.py` tal como está; si ve que el `map.py` se cambió a mano, pregunta antes de
sobrescribirlo. «Acerca de» da tu crédito. Probado abriendo el proyecto de CJ, analizando, convirtiendo y con las
elecciones a mano (capturas de la ventana); Instalar/Restaurar desde la ventana no se probó contra el juego.
Falta la vista previa con los brazos bajados (fase 5 o después).

Resultado de la fase 5 (30/10/2026):

**Exportar pack** (`kit.py export`, botón «4. Exportar pack para Nexus»). Hace lo mismo que nuestros packs:
- los parches se generan con `tools/build_release.py` contra el archivo original del juego;
- el instalador es el mismo de CJ/TS5/KH3, convertido en plantilla (`kit/pack/`) con el nombre, la versión, el
  personaje y una línea de descripción;
- el README va en inglés y español, con el crédito del autor del mod, el del modelo y «Hecho con TS3 Modding Tool de
  keyloor»;
- sale también el zip.

Probado con PowerShell 5.1 en una carpeta falsa del juego: el MD5 tras instalar es el del manifiesto, desinstalar
devuelve el original byte a byte, y los acentos salen bien.

**El .exe** (`kit/build_kit.py`): sale `release/TS3 Modding Tool v0.1/` (73 MB) y su zip (31 MB). Lleva:
- `Toy Story 3 Modding Tool.exe`, hecho con PyInstaller; no hace falta Python;
- el código de `kit/` y `tools/`, para la línea de comandos y los agentes;
- `docs/`, `AGENTS.md`, `skill/`, `LICENSE` + `NOTICE.md` y `README.txt`;
- `licenses/`, con las de Python, numpy, Pillow y Tcl/Tk.

El `.exe` también acepta las órdenes de `kit.py` (`"Toy Story 3 Modding Tool.exe" make <proyecto>`). Así convirtió CJ igual
byte a byte que con Python, y la ventana abre. Sin firma digital: Windows SmartScreen y algún antivirus pueden avisar.

(Esa primera licencia propia se cambió el 31/10/2026 por GPL v3 + `NOTICE.md`: ver «Créditos y licencia».)

Antes de publicar: probar con un modelo de Mixamo (el caso más común) y con alguien que no haya visto el proyecto.

## Créditos y licencia

- La herramienta la firmas tú: nombre en la ventana "Acerca de", en el `.exe`, en la guía y en cada pack que se
  exporte (el README del pack lleva "Hecho con TS3 Modding Tool de keyloor").
- Licencia (decidida el 31/10/2026, para que la comunidad pueda aportar): **GNU GPL v3** (`LICENSE`) con dos
  condiciones añadidas por su sección 7 (`NOTICE.md`): toda copia o versión modificada mantiene «Toy Story 3 Modding
  Tool by keyloor» donde la herramienta lo muestra, y una versión modificada que se publique dice que está modificada
  y por quién. Cualquiera puede ver el código, hacer un *fork* y proponer cambios (`CONTRIBUTING.md`); tú decides qué
  entra. Los mods hechos con la herramienta no quedan cubiertos por la licencia: el crédito en ellos se pide.
- Repositorio: `github.com/keyloor/ts3-modding-tool`, privado hasta que lo hagas público. La raíz del repositorio es
  `mods/ts3_modding_tool/` (con `tools/` dentro; el `tools/` del espacio de trabajo apunta ahí).
- El código es nuestro: no se usa código de los repositorios de la comunidad de Disney Infinity (solo se leyeron como
  documentación). Lo único de terceros que va dentro del `.exe` es Python, numpy y Pillow, cuyas licencias solo piden
  incluir sus avisos (`CREDITS.txt`); no piden crédito en la página.
- Los modelos son de sus dueños: la guía y la app avisan de que cada persona es responsable de tener permiso para
  publicar el modelo que convierte.

## Límites (se dicen en la guía y en Nexus)

- Solo reemplaza personajes que ya existen (Woody, Buzz, Jessie y sus variantes); el esqueleto y las animaciones son
  los del juego, así que el modelo tiene que ser humanoide y en pose T o A.
- Las animaciones son de juguetes: un modelo con proporciones muy distintas (muy alto, brazos muy cortos) se ajusta,
  pero puede verse raro en algunas animaciones.
- Dos mods que tocan el mismo personaje no pueden estar instalados a la vez.
- Cara y ojos: en modo básico se mueven con la cabeza (la boca no se anima); animarlos es modo avanzado.

Resultado de la ronda del 30/10/2026 (tras la fase 5, a pedido del usuario):
- **Modelos OBJ** (`kit/objlib.py`): un OBJ no trae esqueleto, así que la herramienta le pone uno.
  - Endereza el modelo (Z arriba, mirando hacia atrás) y lo apoya en el suelo.
  - Mide el modelo: la entrepierna (dónde la malla cruza el plano central), el cuello (el corte más estrecho) y el
    hombro (siguiendo el brazo desde la punta de los dedos hasta el torso).
  - Estira el esqueleto del personaje del juego sobre esas medidas y reparte los pesos por cercanía a cada hueso, sin
    pasar nunca al otro lado del cuerpo.
  - Después todo sigue igual que con un FBX; el `.mtl` da las texturas.
  - Probado con CJ y KH3 Woody pasados a OBJ (sin esqueleto, a otra escala, uno tumbado y girado): el esqueleto
    estimado queda a un 1–6 % de la altura del real; KH3 Woody desde OBJ se ve como desde FBX.
- **Ventana nueva**:
  - Pantalla de inicio: juego detectado solo, carpeta de trabajo (`Documentos\Toy Story 3 Modding Tool`), secciones
    de la herramienta, proyectos recientes, «Nuevo proyecto» (solo pide un nombre; crea `Personajes\<nombre>`).
  - En el proyecto, 4 pasos: Woody, Buzz Lightyear y Jessie fijados como botones grandes (las variantes en «Otro»),
    elegir modelo FBX u OBJ, Convertir, Instalar / Exportar / Restaurar.
  - Una línea azul dice el siguiente paso, y los botones se apagan hasta que se pueden usar.
- **Nombre**: Toy Story 3 Modding Tool. La copia del juego va a `TS3 Modding Tool backup` (la herramienta sigue
  reconociendo la de las pruebas, `TS3 Character Kit backup`). Ajustes en `~/.ts3_modding_tool.json` (lee los viejos).
- El release **no** se rehízo: el usuario lo está probando.

## Roadmap (pedido el 31/10/2026; nada de esto está hecho todavía)

Idea general: que la herramienta sea más técnica y manipulable sin obligar a editar `map.py` a mano. Todo lo que se
ajuste en la ventana se sigue escribiendo en `map.py`, que continúa siendo editable en modo avanzado.

### 1. Ajustes finos del personaje (pestaña «Ajustes» con controles y vista previa al momento)

**Hecho (31/10/2026): cabeza y cuello.** La pestaña Ajustes mide el cuello del modelo frente al del personaje (con el Woody de Wii: 5,2 cm frente a 10,6 cm, estirado ×2), tiene un control «Altura de la cabeza» y un botón «Cuello a su largo natural» que calcula el valor (−5,3 cm → ×1,01); se guarda en el proyecto (`adjust`) y se escribe en `map.py`.

**Hecho (31/10/2026): proporciones.** En la misma pestaña: ancho, alto y fondo del torso, tamaño de la cabeza y grosor de cuello, brazos y piernas (50–150 %), más cuánto ajusta ya la herramienta el torso sola (Woody de Wii: 124 % de ancho). El convertidor tiene dos opciones nuevas para eso, `TORSO_SCALE` y `GIRTH`; los mapas que no las usan salen idénticos byte a byte (comprobado con TS5 y CJ). El largo de brazos y piernas no se ajusta: las articulaciones tienen que caer en las del juego. El resto de esta sección sigue pendiente.

Caso que lo motivó: el Woody de Wii (OBJ, sin esqueleto) sobre Woody sale con el **cuello alargado**. El esqueleto
estimado del OBJ pone el cuello corto respecto al del juego, y el convertidor lo estira hasta su límite
(`Neck -> Neck stretch 1.25`) para llevar la cabeza a la articulación de la cabeza del juego; el torso además sale un
24 % más ancho (`torso block scale 1.239`). Hoy solo se arregla a mano en `map.py` (`offset` en la cabeza y
`tip_offset` en el cuello, como en `docs/ejemplos/cj_varios_materiales.py`).
- **Cabeza y cuello**: subir o bajar la cabeza, largo del cuello (sin estirar / estirar hasta X), colocar la cabeza
  por la cara (`FACE_ALIGN`) en vez de por la articulación.
- **Proporciones**: escala general, ancho y alto del torso, largo de brazos y piernas (límites de estiramiento por
  parte), separación de piernas y hombros.
- **Mover una articulación a mano** (sobre todo en OBJ): arrastrar en la vista previa hombro, codo, rodilla, cuello…
  del esqueleto estimado. **Hecho (31/10/2026) para OBJ**: modo «Esqueleto de tu modelo» en la Vista previa, puntos
  arrastrables, simetría izquierda/derecha, «Volver al automático»; se guarda en el proyecto (`joints`) y el
  esqueleto automático y sus pesos los usan al convertir. Pendiente: lo mismo para FBX (mover los huesos de su rig).
- **Ropa y accesorios**: estrechar o ensanchar una prenda (`MATERIAL_SCALE`), decidir si un objeto suelto (bastón,
  sombrero, arma) va con la mano, con la cabeza o fuera (`SKIP_BONES`).
- **Ojos y cara**: abrir párpados cerrados (detectar los huesos de párpado y proponer `EYES` solo), cara animada sí/no
  (`FACE`), alinear boca y cejas.
- **Pesos**: ver los pesos en color sobre el modelo, repartir un hueso de ayuda entre dos (`{hueso: parte}`), suavizar.
- **Deshacer / rehacer** y **comparar** dos versiones del ajuste.

### 2. Mejor vista previa

**Hecho (31/10/2026): vista 3D en vivo** (`kit/viewer.py`, moderngl, la misma técnica que DisneyInfinityCreator, con código propio). Se gira, mueve y acerca con el ratón; pose T o **brazos abajo**; el original del juego al lado y el esqueleto del juego encima; en la pestaña Ajustes, una vista en vivo que sigue los controles al instante (aproximada). Comando `doctor` para diagnosticar. Pendiente de esta sección: animaciones del juego y resaltar en rojo lo muy estirado.
- Vista 3D que se gira con el ratón (no solo frente/perfil).
- **Pose con los brazos bajados** (como anima el juego): ahí se ven los problemas de hombros y axilas.
- **Animaciones del juego en la vista previa** (andar, correr, saltar, atacar…), para ver el modelo moviéndose como
  en el juego antes de instalarlo. Viabilidad (mirado el 31/10/2026): el archivo de cada personaje trae sus
  animaciones como archivos sueltos (Woody: 308, en `characters/woody/motions/`, p. ej.
  `woody_motion_walk_normal.oct`, 6,7 KB); son `.oct`, que ya leemos y reescribimos byte a byte. Los fotogramas van
  en un `ClipDataBlock`, cuya cabecera y tablas (tiempos, descriptores, tablas muestreadas y constantes) documenta en
  parte el `FORMATS.md` de DisneyInfinityTools (§4.10, mismo motor). Falta: saber qué salida es qué hueso
  (`LayerBind` / `ConnectionTemplate`) y cómo están comprimidas las muestras. Es investigación; si sale, la vista 3D
  ya sabe mover el modelo con el esqueleto del juego (`viewer.Character.pose`), así que reproducirlas sería poner
  esas rotaciones fotograma a fotograma, con una lista para elegir la animación.
- Esqueleto del juego y del modelo superpuestos; resaltar en rojo las partes muy estiradas o giradas.

### 3. Diagnóstico en lenguaje normal
Convertir los números del registro en avisos con su arreglo propuesto, con un botón para aplicarlo: «El cuello se
estira al máximo: ¿bajar la cabeza 4 cm?», «El torso sale un 24 % más ancho: ¿limitar a 10 %?», «Este material no
encontró imagen», «Los ojos parecen cerrados: ¿abrirlos?».

### 4. Sección Texturas
- **Explorador de todas las texturas del juego**: personajes, escenarios, objetos, menús (las de los `.oct` de cada
  archivo; base: `tools/texpeek.py`, `tools/add_decals.py`, el mod `buzz_original_decals`).
- **Cambiar cualquier textura**: exportarla a PNG, editarla, volver a importarla (la herramienta hace el DDS con el
  formato y los mipmaps correctos) y verla en la vista previa.
- **Packs de texturas de la comunidad**: un formato de pack (carpeta o zip con un `manifest.json`: archivo del juego,
  textura, imagen, autor), instalar varios a la vez con orden de prioridad, avisar de conflictos, quitar uno sin tocar
  los demás, y exportar un pack para Nexus como ya se hace con los personajes.

### 5. Sección Música y sonidos
Con `tools/fmodbank.py` y el mod `restored` como base: lista de canciones y sonidos del juego con reproductor,
cambiar uno por un archivo propio (WAV/MP3/OGG, conversión automática), packs de sonido de la comunidad, exportar pack.

### 6. Gestor de mods
Ver qué hay instalado en cada archivo del juego (de la herramienta y de otros instaladores), activar/desactivar,
combinar varios a la vez (personaje + texturas + música), perfiles, «volver todo al original» y avisar cuando Steam
actualiza o verifica los archivos.

### 7. Más personajes y más formatos
- Probar y fijar las variantes (Buzz alterno, holográficos, 2 jugadores) y aplicar un modelo a todas las variantes
  de un personaje a la vez; personajes secundarios (Rex, Hamm, Slinky…).
- Más formatos de modelo: glTF/GLB (el habitual en Sketchfab), DAE, PMX (MMD); los que traen esqueleto pasan por el
  mapeo automático, los demás por el esqueleto automático.

### 8. Comunidad
- **Presets** por tipo de esqueleto (Mixamo, Fortnite/Unreal, Biped, MMD) y por modelo, compartibles: un proyecto se
  exporta sin el modelo (solo `map.py` y ajustes) para que otros con el mismo modelo lo reutilicen.
- Secciones nuevas como módulos que la comunidad pueda añadir.
- Traducciones a más idiomas desde archivos de texto.

### 9. Calidad y publicación
Pruebas automáticas con modelos libres (CC0) y GitHub Actions: `rt.py` byte a byte, los mapas de referencia, el
`.exe` compilado en cada versión y publicado en *Releases*.

### 10. Ideas sacadas de las herramientas de modding de otros juegos (investigado el 31/10/2026)

Lo que hacen bien otras herramientas y cómo encajaría en Toy Story 3. Nada de esto está hecho; el orden es de más útil
y más factible a menos.

**Gestión de mods** (Mod Organizer 2, r2modman / Thunderstore, Reloaded-II, Hedge Mod Manager, OpenKH Mod Manager):
- **Perfiles**: varias combinaciones de mods guardadas (por ejemplo «Woody de KH3 + canciones restauradas» y «todo
  original»), y cambiar entre ellas con un clic (Mod Organizer 2, r2modman).
- **Compartir un perfil** como archivo o como un código corto que otro pega en su herramienta y se le instala la misma
  combinación (los «share codes» de r2modman).
- **Vista de conflictos**: qué mod «gana» en cada archivo del juego cuando dos tocan el mismo personaje, y elegir el
  orden (Mod Organizer 2).
- **Instalar con un clic desde la web**: un enlace propio (`ts3mt://…`) que la herramienta abre; botones «Instalar con
  TS3 Modding Tool» en GameBanana o GitHub (el «1-Click» de Reloaded-II y Hedge Mod Manager). En Nexus haría falta su
  API y su permiso (`nxm://`).
- **Instalar un mod desde un repositorio de GitHub** escribiendo `usuario/repositorio` (OpenKH Mod Manager): encaja
  con que la comunidad ya tiene el repo de la herramienta.
- **Arrastrar y soltar** un `.zip` de cualquier mod de Toy Story 3 (los packs con instalador que ya exportamos, los
  antiguos de «copiar en la carpeta del juego») para que la herramienta lo instale y sepa quitarlo después.
- **Un formato de mod común** (un `manifest` con nombre, autor, versión, qué archivos toca, dependencias y dónde buscar
  actualizaciones) y **avisos de actualización** (Reloaded-II, el `mod.ini` de Hedge Mod Manager).
- **«Códigos»**: ajustes pequeños con casillas, sin crear un mod (la pestaña Codes de Hedge Mod Manager, con cosas
  como pantalla panorámica). Ver el punto de gráficos.

**Explorar y exportar el juego** (FModel, Noesis, AssetStudio; el volcado de texturas de Dolphin):
- **Explorador del juego**: todos los archivos (personajes, niveles, Toy Box, menús) en un árbol, con vista 3D de
  cualquier modelo u objeto, sus texturas y sus sonidos (FModel).
- **Exportar a glTF / OBJ** un personaje u objeto del juego con su esqueleto y texturas, para editarlo en Blender y
  volver a meterlo (FModel). Útil como base: retocar el Woody original en vez de empezar de cero; y la puerta a cambiar
  objetos que no son personajes (vehículos, accesorios).
- **Volcado completo de texturas** con nombres estables, como Dolphin, para que un pack de texturas sea simplemente
  una carpeta con esos nombres (amplía el punto 4).
- **Texturas HD opcionales** reescaladas con IA a partir de las originales, como hacen las comunidades de packs HD de
  emuladores. Pesado (modelos de IA grandes): mejor como complemento aparte.

**Crear** (Sims 4 Studio, Blockbench):
- **Recolorear** la ropa de un personaje del juego (cambiar el color de la camisa de Woody, el traje de Buzz) sin
  necesitar un modelo nuevo, como los «recolors» de Sims 4 Studio. Pocas horas de trabajo y muy pedido.
- **Conexión con tu editor de imágenes**: «Editar en…» abre la textura en Photoshop/GIMP/Krita y, al guardar, la vista
  3D se actualiza sola (Blockbench).
- **Arreglos en lote**: reconvertir todos los proyectos de golpe cuando salga una versión nueva de la herramienta que
  mejore algo (los «batch fixes» de Sims 4 Studio).
- **Tienda de plugins**: secciones, formatos o arreglos que la comunidad publica y se instalan desde la herramienta
  (Blockbench).

**Gráficos y compatibilidad** (los «graphic packs» de Cemu, PCGamingWiki):
- Para Toy Story 3 en PC solo existe un arreglo de 1920×1080 de 2020 y un parche para un error de `KERNEL32.DLL` en
  Windows nuevos; **no hay ultrawide ni desbloqueo de FPS**. Hueco real: investigar el ejecutable y la configuración
  y ofrecerlo como casillas y preajustes (resolución, panorámica, FPS, campo de visión), al estilo de los graphic packs.
- Detectar y explicar problemas conocidos del juego en Windows modernos.

**Jugar distinto** (Archipelago, randomizers):
- **Randomizer**: mezclar premios del Toy Box, misiones o aspectos de personajes. A largo plazo, una conexión con
  Archipelago (multimundo). El tracker del 100 % (`toy-story-3-tracker`) ya sabe leer la partida, que es la base.
- **Editor de partida**: el tracker lee la partida; escribirla (desbloquear cosas) sería otra sección, con copia de
  seguridad siempre.

**Plataformas**: Linux / Steam Deck (Proton), como Hedge Mod Manager 8. La herramienta es Python + tkinter, así que
la base es portable; lo que habría que adaptar es la instalación (hoy usa rutas y PowerShell de Windows).

Fuentes: OpenKH Mod Manager ([openkh.dev](https://openkh.dev), [ejemplo de mod por GitHub](https://github.com/SuperfieldCU/ConsistentLocalizationDDDHGSUI));
[Reloaded-II](https://github.com/Reloaded-Project/Reloaded-II/releases/tag/0.11.0);
[Hedge Mod Manager](https://github.com/thesupersonic16/HedgeModManager);
[Mod Organizer 2](https://geckwiki.com/index.php?title=MO);
[r2modman / Thunderstore](https://docs.rs/thunderstore-engine/0.1.0/src/thunderstore_engine/profile/portability.rs.html);
[FModel](https://github.com/4sval/FModel/releases/tag/aug-2026);
[Dolphin, texturas por hash](https://forums.dolphin-emu.org/Thread-texture-dumping-details);
[Cemu graphic packs](https://github.com/topics/wiiu-emulator);
[Sims 4 Studio, batch fixes](https://simscommunity.info/2018/09/03/the-sims-4-how-to-run-a-batch-fix-with-sims-4-studio/);
[Blockbench](https://gamefromscratch.com/blockbench-3d-modelling-application-review/);
[Toy Story 3, arreglo 1920×1080](https://www.gamepressure.com/download/toy-story-3-the-video-game-1920x1080-fix-mod/z512819);
[PCGamingWiki](https://community.pcgamingwiki.com/tags/toy%20story/);
[Archipelago](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/world%20api.md).
