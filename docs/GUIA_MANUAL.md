# Guía manual: tu modelo en Toy Story 3, paso a paso y sin nada automático

*TS3 Modding Tool, de keyloor.*

Esta guía explica cómo poner un modelo propio en lugar de Woody, Buzz o Jessie **a mano**: sin el asistente, sin
`automap.py` y sin `autotex.py`. Tú escribes el mapa de huesos y de texturas, y el convertidor solo hace lo que el mapa
le dice. Sirve para entender qué hace el kit por dentro, para arreglar un modelo que el modo automático no resuelve
bien, y para ir más allá del modo básico (ojos, cara, ropa suelta…).

Al final hay un apéndice con los formatos del juego, para quien quiera escribir sus propias herramientas.

> El camino corto: `python -I <KIT>/kit/kit.py make <carpeta> --character woody --fbx mi_modelo.fbx --textures
> texturas` hace los pasos 2 a 6 en un comando y escribe un `map.py` que puedes retocar con esta guía. Si vuelves a
> ejecutar `make`, usa tu `map.py` tal como lo dejaste. También hay una ventana (`python -I <KIT>/kit/app.py`):
> en ella, marca «Modo avanzado» para que convierta con tu `map.py` hecho a mano.

---

## 0. Qué necesitas

- Toy Story 3 Complete Edition para PC (Steam) y **el juego cerrado** mientras instalas.
- Python 3.12 con `numpy` y `Pillow`: `pip install numpy pillow`.
- La carpeta `tools/` del kit: el convertidor y las herramientas de inspección.
- Un modelo **humanoide con esqueleto y piel** (cada vértice movido por huesos) en FBX, con sus texturas en PNG, TGA,
  JPG o DDS.
- Opcional: Blender, para preparar el modelo.

Todos los comandos se escriben desde la carpeta de tu proyecto, y `python -I` va siempre con `-I`. En esta guía
`<KIT>` es la carpeta del kit y `<JUEGO>` la del juego
(`C:\Program Files (x86)\Steam\steamapps\common\Toy Story 3 Complete Edition` en una instalación normal).

## 1. Preparar el modelo (Blender)

El juego mueve el modelo con **su propio esqueleto y sus propias animaciones**. El convertidor encaja tu modelo en ese
esqueleto, así que el modelo tiene que ser lo más parecido posible a un personaje de pie:

1. **Pose T o A**, de pie, mirando al frente. Si tiene los párpados cerrados en la pose de reposo, se arregla luego
   (sección 8).
2. **Escala y rotación aplicadas** (`Ctrl+A` → *All Transforms*), en el objeto y en el esqueleto.
3. **Una sola armadura.** Todas las mallas del personaje con un modificador *Armature* hacia ella.
4. Borra lo que no sea el personaje: cuerpos de física (*rigid bodies* de MMD), luces, cámaras, versiones de menos
   detalle (LOD1, LOD2…). Las mallas sin piel se ignoran solas, pero una copia repetida de una malla se convertiría dos
   veces.
5. **Exportar FBX** (binario): *Apply Transform* activado, *Add Leaf Bones* desactivado; *Forward* y *Up* como vengan
   (el convertidor lee los ejes que dice el archivo; compruébalo con `bones5.py` en el paso 3). Copia las texturas a
   una carpeta junto al FBX.

Tamaño: el juego mueve más de 70 huesos en Woody, pero cada pieza de la malla puede usar como mucho 40 (el convertidor
parte la malla solo). Un modelo de 20 000 a 50 000 triángulos va bien.

### Si tu modelo es un OBJ

Un `.obj` no trae esqueleto ni piel. La herramienta (ventana o `kit.py make`) le pone uno sola: mide el modelo
(entrepierna, cuello, hombros, puntas de los dedos), estira encima el esqueleto del personaje del juego y reparte los
pesos por cercanía. Las texturas salen del `.mtl`. Funciona con humanoides en pose T o A. Las manos y la cara se
mueven en bloque, con la mano y con la cabeza.

Si alguna articulación del esqueleto automático sale fuera de sitio (un codo, un hombro), en la ventana, Vista
previa → **Esqueleto de tu modelo**, se arrastra a su sitio (con simetría izquierda/derecha) y se vuelve a
convertir; queda guardado en el proyecto (`joints`).

Para el mejor resultado, o para hacerlo **a mano**, ponle esqueleto tú:
- en Blender (Armature → *With Automatic Weights*);
- o subiéndolo a Mixamo (auto-rigger gratis), que devuelve un FBX con esqueleto.

Exporta ese FBX y sigue esta guía.

## 2. Sacar el personaje del juego

Cada personaje está en un `.zip` del juego:

| Personaje | Nombre base | Archivo |
|---|---|---|
| Woody | `woody` | `assets/characters/woody/woody.zip` |
| Buzz | `buzzlightyear` | `assets/characters/buzzlightyear/buzzlightyear.zip` |
| Jessie | `jessie` | `assets/characters/jessie/jessie.zip` |

Hay más variantes (Buzz alternativo, Buzz de dos jugadores…) en `<JUEGO>/assets/characters/`.

```
python -I <KIT>/tools/zx.py "<JUEGO>/assets/characters/woody/woody.zip" juego/woody
```

Eso deja en `juego/woody/` los archivos del personaje: `woody.oct` (esqueleto, materiales, texturas, animaciones),
`woody_0.vbuf` (vértices) y `woody_0.ibuf` (triángulos).

## 3. Mirar los dos esqueletos

**Tu modelo:**

```
python -I <KIT>/tools/fbxinfo.py mi_modelo.fbx
python -I <KIT>/tools/bones5.py mi_modelo.fbx
```

`fbxinfo.py` lista las mallas, sus materiales y sus huesos. `bones5.py` da cada hueso con su padre, cuántos vértices
mueve y su posición **ya girada como en el juego**: Y hacia arriba, mirando a +Z, y **la izquierda del personaje en +x**.
Si la mano "izquierda" sale en x negativa, el modelo está mirando hacia atrás: vuelve a exportarlo.

**El personaje del juego:**

```
python -I <KIT>/tools/ts3model.py juego/woody woody
```

Los huesos del juego que importan:

| Parte | Woody / Jessie | Buzz |
|---|---|---|
| Cadera, columna | `Hips`, `Spine1`, `Spine2`, `Spine3` | igual |
| Cuello, cabeza | `Neck`, `Head` | igual |
| Clavícula | `ClavicleLeft` | `SternumLeft` |
| Brazo, antebrazo, mano | `BicepLeft`, `ForearmLeft`, `HandLeft` | igual |
| Dedos | `Index1Left`, `Index2Left`, `Index3Left`, `Middle1Left`… `Thumb3Left` | `IndexLeft1`, `Index2Left`, `Index3Left`… (el primero cambia de orden) |
| Pierna | `ThighLeft`, `CalfLeft`, `FootLeft`, `ToesLeft` | igual |
| Cara | `Jaw`, `UpperLip`, `LowerLip`, `LipCornerLeft`, `BrowLeft`, `MiddleBrow` | además `EyeLeft`, `EyeLidTopLeft`, `EyeLidBtmLeft`; `MidddleBrow` (con tres d) |
| Extras | `Hat`, `Holster` | `WingLeft1`, `WingLeft2`, `Dome` | 
| Extras de Jessie | `Hat`, `Hair1`…`Hair4`, `eyeLeft`, `lidUpperLeft`, `jaw` (en minúscula) | |

Lo mismo con `Right` para el lado derecho. Usa siempre los nombres que salen en *tu* `ts3model.py`.

## 4. Escribir el mapa

El mapa es un archivo `.py` con tablas. Este es un mapa completo para un modelo de **Mixamo** sobre Woody, para
copiar y adaptar (en Mixamo los huesos se llaman `mixamorig:Hips`, `mixamorig:LeftArm`…; a veces `mixamorig1:`):

```python
"""Mi modelo (Mixamo) -> Woody. Hecho a mano con TS3 Modding Tool de keyloor."""
P = 'mixamorig:'                     # el prefijo de los huesos de tu modelo

PREFIX = 'mio'                       # nombre de las piezas, materiales y texturas nuevas
KEEP_PIECES = []                     # piezas del juego que se quedan (para Buzz: ['JetPack_Flame'])

# el tronco se mueve como un bloque; se escala por ejes para que estas parejas coincidan
TORSO = [P + 'Hips', P + 'Spine', P + 'Spine1', P + 'Spine2']
LANDMARKS = [(P + 'Hips', 'Hips'), (P + 'LeftArm', 'BicepLeft'), (P + 'RightArm', 'BicepRight'),
             (P + 'Neck', 'Neck'), (P + 'LeftUpLeg', 'ThighLeft'), (P + 'RightUpLeg', 'ThighRight')]
# parejas que deciden el tamaño total
SCALE_JOINTS = LANDMARKS + [(P + 'Head', 'Head'),
                            (P + 'LeftForeArm', 'ForearmLeft'), (P + 'RightForeArm', 'ForearmRight'),
                            (P + 'LeftHand', 'HandLeft'), (P + 'RightHand', 'HandRight'),
                            (P + 'LeftLeg', 'CalfLeft'), (P + 'RightLeg', 'CalfRight')]
FACE_ALIGN = []

# hueso del modelo: (hueso al que apunta, hueso del juego, hueso del juego al que apunta, opciones)
DRIVE = {
    P + 'Neck': (P + 'Head', 'Neck', 'Head', {}),
    P + 'Head': (None, 'Head', None, {}),
}
WEIGHTS = {P + 'Hips': 'Hips', P + 'Spine': 'Spine1', P + 'Spine1': 'Spine2', P + 'Spine2': 'Spine3',
           P + 'Neck': 'Neck', P + 'Head': 'Head'}
for m, g in (('Left', 'Left'), ('Right', 'Right')):
    DRIVE.update({
        P + m + 'UpLeg': (P + m + 'Leg', 'Thigh' + g, 'Calf' + g, {}),
        P + m + 'Leg': (P + m + 'Foot', 'Calf' + g, 'Foot' + g, {'aim_floor': True}),
        P + m + 'Foot': (None, 'Foot' + g, None, {'floor': True}),
        P + m + 'Arm': (P + m + 'ForeArm', 'Bicep' + g, 'Forearm' + g, {}),
        P + m + 'ForeArm': (P + m + 'Hand', 'Forearm' + g, 'Hand' + g, {}),
        P + m + 'Hand': (P + m + 'HandMiddle1', 'Hand' + g, 'Middle1' + g, {}),
    })
    WEIGHTS.update({P + m + 'Shoulder': 'Clavicle' + g, P + m + 'Arm': 'Bicep' + g,
                    P + m + 'ForeArm': 'Forearm' + g, P + m + 'Hand': 'Hand' + g,
                    P + m + 'UpLeg': 'Thigh' + g, P + m + 'Leg': 'Calf' + g,
                    P + m + 'Foot': 'Foot' + g, P + m + 'ToeBase': 'Toes' + g})
    for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
        for k in '123':
            WEIGHTS[P + m + 'Hand' + f + k] = f + k + g        # en Buzz: f + g + k para k == '1'

FACE_BONES = set()
FACE = False

# texturas: un juego por imagen de color; n = normal, orm = oclusión/rugosidad/metal, spec = brillo 0..1
TEXTURES = {
    'cuerpo': dict(d='Body_D.png', n='Body_N.png', size=1024, nsize=512, spec=0.15),
}
# material del FBX -> juego de texturas, o (r, g, b) para un color liso
MATERIALS = {'Body': 'cuerpo'}
SKIP_MATERIALS = []
```

### Qué es cada tabla

- **`TORSO`**: los huesos del tronco: cadera, columna y todo lo que hay por encima de la cadera en el árbol. Se mueven
  juntos, como un bloque.
- **`LANDMARKS`**: parejas *(hueso tuyo, hueso del juego)*. El bloque del tronco se estira por ejes (entre 0,8 y 1,25)
  para que estos puntos coincidan.
- **`SCALE_JOINTS`**: parejas que dan el tamaño total (por mínimos cuadrados). Tu modelo acaba de la altura del
  personaje del juego.
- **`DRIVE`**: los huesos que se giran y estiran hasta su sitio en el juego. `('Brazo', 'Codo', 'BicepLeft',
  'ForearmLeft')` quiere decir: el segmento del brazo al codo se gira para apuntar como el del juego, se estira a su
  largo (entre 0,8 y 1,25; `max_stretch` sube el límite) y se pone en su pivote. Opciones:
  - `floor`: el pie conserva su altura (no se hunde ni flota);
  - `aim_floor`: la rodilla apunta a un pie que se queda en el suelo;
  - `offset` / `tip_offset`: mueve el pivote o la punta (en metros), por ejemplo la cabeza un poco más abajo;
  - `face` / `aim_face`: pone la cabeza según `FACE_ALIGN` (la cara) en lugar de según el pivote de la cabeza.

  Cualquier hueso que no esté en `TORSO` ni en `DRIVE` sigue a su antepasado más cercano que sí esté: los dedos van
  con la mano y la cara con la cabeza.
- **`WEIGHTS`**: a qué hueso del juego van los vértices de cada hueso tuyo. Puede ser un hueso, o
  `{'BicepLeft': 0.5, 'ForearmLeft': 0.5}` para repartir un hueso de ayuda (los de giro del codo, por ejemplo). Un
  hueso tuyo que no esté en la tabla usa el de su antepasado en `DRIVE`/`TORSO`. Un hueso del juego que no exista va a
  `Head`. El convertidor avisa de las dos cosas.
- **`FACE_BONES` / `FACE`**: los huesos de la cara del juego que usas en `WEIGHTS`. Con `FACE = False` sus vértices van
  a `Head` (la cara no se anima, pero tampoco se deforma). Con `True` la boca y las cejas se mueven con las animaciones
  del juego.
- **`TEXTURES`**: cada juego de texturas se convierte en un material del juego con 3 texturas: color (DXT1), normal y
  brillo. `d` es la imagen de color; `n` la normal (si falta, se usa una plana); `orm` una imagen
  oclusión-rugosidad-metal (Unreal/Fortnite), o `spec` un número de 0 a 1, o una imagen de brillo con
  `mask='Body_S.png', mask_spec=(0.333, 0.333, 0.334, 0)` (cuánto cuenta cada canal R, G, B, A); `size`, `nsize`,
  `ssize` el tamaño en píxeles (potencias de dos, hasta 1024).
- **`TORSO_SCALE`** `(x, y, z)` (opcional): hace el bloque del tronco más ancho, alto o profundo que lo que ajustó
  la herramienta, alrededor de su centro: `(0.85, 1, 1)` = 15 % más estrecho.
- **`GIRTH`** `{hueso del modelo: factor}` (opcional): engorda o adelgaza esa parte a lo ancho, sin cambiar su
  largo (que es el del juego). En un hueso sin dirección, como la cabeza, cambia su tamaño entero:
  `{'Head': 1.15, 'BicepLeft': 0.8}`.
- **`MATERIALS`**: cada material del FBX (los nombres salen en `fbxinfo.py`) va a un juego de `TEXTURES`, a un color
  `(r, g, b)` o a `SKIP_MATERIALS` para dejarlo fuera. Si a un material del FBX no le das ninguna de las tres, el
  convertidor se para y te dice cuál.

> **Ojo con las normales:** la imagen normal tiene que tener la misma distribución que la de color. Las vistas previas
> no usan la normal, así que una normal equivocada solo se nota en el juego (manchas de luz raras). Si dudas, quítala.

Sin `MATERIALS` (el modo de los mods de TS5) solo se usa la primera malla del FBX, y las texturas se buscan por final
de nombre: `_BC`, `_N` y `_ORM`.

## 5. Convertir y comprobar

```
python -I <KIT>/tools/convert.py juego/woody woody mi_modelo.fbx texturas mi_mapa.py salida/woody
python -I <KIT>/tools/rt.py salida/woody/woody.oct
```

`rt.py` tiene que decir **byte-exact**: el archivo se lee y se vuelve a escribir igual. Si no, no lo instales.

El convertidor escribe lo que hizo en pantalla y en `salida/woody/convert.log`:

| Línea | Qué mirar |
|---|---|
| `scale 0.0237 (model height 71.4 -> 1.690)` | La altura final en metros. Woody mide unos 1,7 en sus unidades |
| `torso block: scale [...], landmark error 0.043` | Un error de más de 0,05 indica que algún `LANDMARKS` está mal emparejado |
| `Arm -> BicepLeft turn 12.0 deg stretch 1.10` | Giros de más de 40° o estiramientos al límite (0,80 o 1,25) indican un hueso mal emparejado |
| `weights of X go to Y` | Huesos tuyos que no estaban en `WEIGHTS` y a dónde fueron |
| `the game has no bone X: ... goes to Head` | Un nombre del juego mal escrito, o un hueso que ese personaje no tiene |
| `N vertices without full weights` | Vértices sin piel completa en el FBX: revisa la piel en Blender |
| `N pieces (bones per piece: [...])` | En cuántas piezas se partió la malla |

## 6. Vista previa

```
python -I <KIT>/tools/render.py salida/woody woody vista.png oct --compare juego/woody
python -I <KIT>/tools/angles.py salida/woody woody oct cara.png 0 1.6 0.08 0.5 0 35 80
```

`render.py` dibuja el original del juego a la izquierda y tu modelo a la derecha, de frente y de lado. Los puntos rojos
son las articulaciones del juego: hombros, codos, rodillas, tobillos y cabeza deberían caer dentro de tu modelo, en su
sitio. `angles.py` hace primeros planos desde varios ángulos: `x y z` del centro (en metros; la cara de Woody está
hacia `0 1.6 0.08`), el tamaño del recuadro (`0.5`) y los giros en grados (`0 35 80`).

La vista previa muestra la pose de reposo, con los brazos abiertos. En el juego se anima con los brazos bajados, así que
los hombros y las axilas solo se pueden juzgar en el juego.

## 7. Problemas típicos y cómo arreglarlos

| Se ve así | Arreglo en el mapa |
|---|---|
| La cabeza flota o se hunde, o el cuello sale estirado | `offset` en el `DRIVE` de la cabeza y `tip_offset` igual en el del cuello, p. ej. `(0, -0.035, 0)`. En la ventana: pestaña **Ajustes** → «Cuello a su largo natural» lo calcula solo |
| Un brazo o una pierna sale demasiado corto o largo | Revisa la pareja en `SCALE_JOINTS`; si es a propósito, `max_stretch` en su `DRIVE` |
| El torso sale muy ancho o estrecho, la cabeza muy grande o pequeña, brazos o piernas muy gruesos | `TORSO_SCALE` y `GIRTH`. En la ventana: pestaña **Ajustes** → Proporciones |
| Ropa ancha que atraviesa las piernas al andar | `MATERIAL_SCALE = {'material': (0.85, 1.0, 0.9)}` estrecha esa prenda alrededor de la cadera |
| Una manga se queda pegada al pecho, o tira del pecho | Pesos de ese hueso de ayuda: `{'Spine3': 0.3, 'BicepLeft': 0.7}`, o `WEIGHT_RAMP` |
| Algo se mueve demasiado (la boca, una cola…) | `WEIGHT_SCALE = {'Jaw': 0.5}`: ese hueso mueve solo la mitad |
| Un trozo del modelo no hace falta (un arma, un escudo) | Su material en `SKIP_MATERIALS`, o sus huesos en `SKIP_BONES` |
| Partes con un color liso salen manchadas de otros colores | En su juego de texturas `solid=True`: lo que usa un solo píxel de la imagen pasa a una paleta |
| Buzz sin llamas en la mochila | `KEEP_PIECES = ['JetPack_Flame']` |
| Luces raras en el juego | Quita la `n` de ese juego de texturas |

## 8. Ojos cerrados

Muchos modelos de juegos (Fortnite, KH3) vienen con los párpados cerrados en la pose de reposo. Se abren girando los
vértices de los párpados alrededor del centro del ojo:

```python
EYES = [('OjoIzq', ['ParpadoSupIzq'], ['ParpadoInfIzq']),       # (hueso del ojo, huesos de arriba, huesos de abajo)
        ('OjoDer', ['ParpadoSupDer'], ['ParpadoInfDer'])]
EYE_MODE = 'rotate'                    # cada párpado gira un ángulo fijo
EYE_OPEN_TOP, EYE_OPEN_BOTTOM = 32, 14  # grados
```

Si girarlos todo mete la piel del párpado en la ceja, usa `EYE_MODE = 'slide'`. Ese modo mueve solo el borde del
párpado (`EYE_TOP_EDGE`, `EYE_BOTTOM_EDGE`, en grados desde el frente) y comprime la piel hasta `EYE_TOP_LIMIT` /
`EYE_BOTTOM_LIMIT`. `LASHES` pone las pestañas sobre el borde abierto. Hay ejemplos completos en `ejemplos/`
(TS5 Woody y Jessie).

## 9. Instalar y desinstalar

Con el juego cerrado:

```
python -I <KIT>/tools/install.py install "<JUEGO>" assets/characters/woody/woody.zip salida/woody
python -I <KIT>/tools/install.py restore "<JUEGO>" assets/characters/woody/woody.zip
```

La primera vez guarda una copia del archivo original en `<KIT>/game/backup/`, y `restore` la devuelve. (`kit.py
install` guarda la suya junto al juego, en `TS3 Modding Tool backup`: restaura siempre con lo mismo que usaste para
instalar.) Solo puede haber **un mod por personaje**: instalar otro sobre el mismo archivo reemplaza el anterior.

## 10. Publicarlo

Si el modelo no es tuyo, publica solo si su autor lo permite. Nunca subas archivos del juego. Un pack para Nexus lleva
solo tus cambios y un instalador que los aplica sobre la copia del juego de cada persona; el kit lo genera (fase 5 del
plan). Pon en la página: "Hecho con TS3 Modding Tool de keyloor".

---

## Apéndice: los formatos del juego

Para escribir herramientas propias. Todo está en little-endian.

- **Archivos `.zip`**: el directorio central y el registro final van al principio y otra vez al final. Cada entrada
  lleva un campo extra `KF` (0x464B, 19 bytes) = `"MD5"` + MD5 del archivo descomprimido. Si el MD5 no coincide, el
  juego no carga el archivo.
- **`.oct`** (formato *tuple* del motor Octane de Avalanche): cabecera de 0x3C bytes (magic 0x45017629, f32 1.1, tamaño
  de la tabla de nombres, tamaño de los datos, número de registros), tabla de nombres separada por NUL, y registros
  `u16 flag, u16 nombre` + datos. El tipo es `flag & 0x3FF` y el nivel `flag >> 10`; los registros forman un árbol en
  preorden. Lo que importa para un personaje: `TexturePool` (DDS en `Data`, `DataCRC` = crc32 del DDS), `MaterialPool`,
  `VertexBufferPool`/`IndexBufferPool`, `VertexStreamPool`/`IndexStreamPool`, `SceneComponentPool` (`RemapData`: los
  huesos de cada pieza), `SceneTreeNodePool` (huesos, geometría y piezas `SubGeometryLit`) y `AssociationPool`. La red
  de animación (`SubNetworkPool`) no se toca.
- **Vértices** (`_0.vbuf`): flujo 0 = posición f32×3, índices de hueso u8×4 (dentro de la lista de la pieza), pesos
  u8×4 que suman 255, uv f16×2 (v desde arriba); flujo 1 = tangente, normal y binormal en f16×4 con w = 0. **Índices**
  (`_0.ibuf`): u16, relativos al flujo de vértices de la pieza. Pose de reposo: Y arriba, mirando a +Z, en metros, la
  izquierda del personaje en +x.

La documentación más completa del formato `.oct` y de los `.zip` de este motor es el `FORMATS.md` de
[DisneyInfinityTools](https://github.com/Kokonotcu/DisneyInfinityTools) (Disney Infinity usa el mismo motor; secciones
2 y 3). [DisneyInfinityCreator](https://github.com/LucasLhomme/DisneyInfinityCreator) hace para Disney Infinity 3.0 lo
mismo que este kit para Toy Story 3. El código del kit es propio: esos proyectos se usaron como lectura y referencia.
