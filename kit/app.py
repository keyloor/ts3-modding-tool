"""Toy Story 3 Modding Tool: the window. python app.py

A start screen (the game, found through Steam; the workspace folder; the tool's sections and recent projects), then a
character project in four steps: pick the character, pick the model (FBX or OBJ), convert and check, play or share.
It only calls kit.py's functions; the work runs in a thread and what it prints goes to the Log tab.
"""
import hashlib, json, os, queue, re, sys, threading, traceback, webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import paths
from about import CREDIT, TOOL, VERSION, AUTHOR
import automap as AM
import viewer as V
import kit as K
import modupdate
from dropfiles import DropTarget
from PIL import Image, ImageTk

SETTINGS = os.environ.get('TS3TOOL_SETTINGS') or os.path.join(os.path.expanduser('~'), '.ts3_modding_tool.json')
OLD_SETTINGS = os.path.join(os.path.expanduser('~'), '.ts3_character_kit.json')
MAIN = [('woody', 'Woody'), ('buzzlightyear', 'Buzz Lightyear'), ('jessie', 'Jessie')]   # pinned first

TEXT = {
    'es': dict(
        file='Archivo', home_menu='Inicio', quit='Salir', language='Idioma', help='Ayuda',
        guide='Guía manual', agents='Instrucciones para agentes de IA', about='Acerca de',
        by='de %s  ·  versión %s', game_found='Juego: %s', game_missing='No encontré Toy Story 3 Complete Edition.',
        game_looking='Buscando el juego…', change='Cambiar…', find_game='Buscar el juego…',
        workspace='Carpeta de trabajo: %s',
        mod_chars='Personajes', mod_chars_desc='Pon tu propio modelo (FBX u OBJ) en lugar de Woody, Buzz o Jessie.',
        mod_music='Música y sonidos', mod_music_desc='Cambia canciones y sonidos del juego.',
        mod_tex='Texturas', mod_tex_desc='Cambia texturas de personajes y niveles.', soon='Próximamente',
        mods_title='Mods instalados', mods_desc='Instala paquetes, revisa lo que cambian y quítalos con su copia de seguridad.',
        mods_open='Gestionar mods', mods_zip='Instalar mod…', mods_folder='Instalar desde carpeta…',
        mods_refresh='Actualizar lista', mods_remove='Quitar mod', mods_recover='Recuperar operación',
        mods_drop='Arrastra aquí un ZIP o una carpeta de mod, o usa los botones para elegirlo.',
        mods_no_drop='Usa los botones para elegir un ZIP o una carpeta de mod.',
        mods_empty='No hay mods instalados con este gestor.', mods_count='%d mods instalados',
        mods_scope='Esta lista muestra los mods instalados con el gestor. Los de otros instaladores no aparecen.',
        mods_select='Selecciona un mod para ver su descripción y los archivos que cambia.',
        mods_files='Archivos del juego', mods_author='Autor', mods_unknown='Sin indicar',
        mods_review='Revisar instalación', mods_confirm='Instalar este mod',
        mods_review_note='Cierra Toy Story 3 antes de instalar. Se guardará una copia de los archivos que se reemplacen.',
        mods_destination='Juego de destino: %s', mods_size='%d archivos · %.1f MiB',
        mods_remove_confirm='¿Quitar «%s»?\n\nSe restaurarán los archivos anteriores a su instalación. Cierra el juego primero.',
        mods_installed='«%s» está instalado.', mods_removed='«%s» se ha quitado.',
        mods_pending='Hay una operación interrumpida. Pulsa «Recuperar operación» antes de continuar.',
        mods_recovered='Recuperación terminada. Ya puedes gestionar tus mods.',
        mods_recover_confirm='¿Restaurar el estado anterior a la operación interrumpida? Cierra el juego primero.',
        mods_busy='Espera a que termine la operación actual.', mods_one='Suelta un solo ZIP o una sola carpeta cada vez.',
        mods_failed='No se pudo completar la operación. Revisa estos detalles:',
        mods_conflict='Otro mod ya cambia este archivo: %s',
        mods_dependency='Falta una dependencia: %s', mods_declared='Este paquete es incompatible con: %s',
        mods_existing='Este mod ya está instalado. Quítalo antes de instalar otra versión.',
        mods_dependent='Primero quita el mod que depende de él: %s',
        mods_external='El archivo cambió fuera del gestor. Se ha conservado: %s',
        mods_changed='El paquete o el juego cambió después de la revisión. Vuelve a elegir el paquete.',
        mods_closed='Cierra Toy Story 3 antes de cambiar los mods.',
        mods_check='Buscar actualizaciones', mods_open_update='Abrir página de la actualización',
        mods_update='Actualización', mods_update_new='%s disponible', mods_update_ok='Al día',
        mods_update_err='Sin respuesta', mods_update_line='Versión nueva %s: %s',
        mods_update_fail='No se pudo consultar GitHub (%s). Se reintentará más tarde.',
        mods_updates_found='Actualizaciones disponibles: %d. Selecciona el mod y abre su página para descargarla.',
        mods_updates_none='Los mods que avisan de actualizaciones están al día.',
        mods_updates_nothing='Ningún mod instalado indica dónde buscar actualizaciones.',
        new_project='Nuevo proyecto', open_other='Abrir otro…', recent='Proyectos recientes',
        no_recent='Todavía no hay proyectos.', project_name='Nombre del proyecto (por ejemplo, el del modelo):',
        bad_name='Usa letras, números, espacios o guiones.', back='← Inicio', open_folder='Abrir carpeta',
        open_map='Abrir map.py', advanced='Modo avanzado: usar mi map.py tal como está',
        step1='1 · Personaje que reemplazas', other='Otro:', step2='2 · Tu modelo',
        pick_model='Elegir modelo (FBX u OBJ)…', no_model='Ningún modelo elegido.', textures='Texturas: %s',
        no_textures='ninguna (colores lisos)', change_textures='Cambiar texturas…',
        obj_note='OBJ: no trae esqueleto; la herramienta le pone uno (humanoides en pose T o A).',
        step3='3 · Convertir y revisar', convert='Convertir', analyze='Revisar huesos y materiales',
        step4='4 · Juega o comparte', install='Instalar en el juego', restore='Restaurar original',
        export='Exportar pack para Nexus',
        next_char='Siguiente: elige el personaje que vas a reemplazar.',
        next_model='Siguiente: elige tu modelo (FBX u OBJ).',
        next_convert='Siguiente: pulsa «Convertir». Si quieres, revisa antes los huesos y materiales.',
        next_look='Mira la Vista previa. Si algo está mal, corrígelo en Huesos o Materiales y vuelve a convertir; '
                  'si está bien, instálalo en el juego.',
        tab_bones='Huesos', tab_mats='Materiales', tab_preview='Vista previa', tab_log='Registro', tab_adjust='Ajustes',
        adj_head_title='Cabeza y cuello',
        adj_help='Mueve la cabeza (y el final del cuello con ella) desde donde está la cabeza del personaje del juego. '
                 'Negativo = más abajo. Úsalo si el cuello sale estirado o aplastado.',
        adj_info='El cuello de tu modelo mide %.1f cm y el de %s %.1f cm: con el ajuste aplicado ahora se estira ×%.2f '
                 '(el convertidor permite de ×0,80 a ×1,25; más allá se deforma).',
        adj_none='Pulsa «Convertir» o «Revisar huesos y materiales» para medir el cuello de tu modelo.',
        adj_height='Altura de la cabeza', adj_natural='Cuello a su largo natural', adj_reset='Volver a 0',
        adj_apply='Aplicar y convertir',
        adj_prop_title='Proporciones',
        adj_prop_help='Ancho, alto y fondo del torso, tamaño de la cabeza y grosor de cuello, brazos y piernas. '
                      'El largo de brazos y piernas no se cambia: las articulaciones tienen que caer en las del '
                      'personaje para que sus animaciones doblen en el sitio correcto.',
        adj_torso_info='La herramienta ya ajusta el torso sola para llegar a los hombros y caderas del personaje: '
                       '%s %% de ancho y %s %% de alto. Lo de abajo se aplica encima de eso.',
        adj_torso_w='Torso: ancho', adj_torso_h='Torso: alto', adj_torso_d='Torso: fondo',
        adj_head_size='Cabeza: tamaño', adj_neck_thick='Cuello: grosor', adj_arms_thick='Brazos: grosor',
        adj_legs_thick='Piernas: grosor', adj_prop_reset='Todo a 100 %',
        adj_live='En vivo, mientras mueves los controles (aproximado: «Aplicar y convertir» da el resultado exacto)',
        adj_undo='↶ Deshacer', adj_redo='↷ Rehacer', adj_undone='Deshecho.', adj_redone='Rehecho.',
        adj_versions='Versiones:', adj_save_version='Guardar versión…', adj_load_version='Cargar',
        adj_version_name='Nombre de esta versión de los ajustes:',
        adj_version_saved='Versión «%s» guardada.',
        adj_version_loaded='Versión «%s» cargada. Pulsa «Aplicar y convertir» para verla.',
        adj_page_body='Cabeza y proporciones', adj_page_acc='Accesorios y ropa', adj_page_face='Ojos y cara',
        adj_page_weights='Pesos',
        adj_acc_help='Objetos sueltos de tu modelo (sombrero, bolsa, un arma, el pelo…): con qué parte del cuerpo se '
                     'mueven en el juego, o quitarlos del modelo. Doble clic para cambiar.',
        adj_garm_help='Estrecha o ensancha una prenda (un material de tu modelo) sin tocar lo demás. Doble clic.',
        adj_bone='Hueso de tu modelo', adj_place='Se mueve con', adj_auto_place='automático (%s)',
        adj_material='Material', adj_width='Ancho',
        places=dict(auto='Automático', hand_left='La mano izquierda', hand_right='La mano derecha', head='La cabeza',
                    chest='El pecho', hips='La cadera', out='Quitarlo del modelo'),
        adj_need_info='Pulsa «Revisar huesos y materiales» (paso 3) para ver aquí lo que tiene tu modelo.',
        adj_eyes_title='Ojos', adj_eyes_open='Abrir los párpados (si tu modelo los tiene cerrados)',
        adj_eye_top='Párpado de arriba', adj_eye_bottom='Párpado de abajo',
        adj_eyes_found='Ojos encontrados (huesos de párpado arriba + abajo): %s',
        adj_eyes_none='No se encontraron huesos de ojo y párpado por su nombre: con este modelo no hace nada.',
        adj_face_title='Cara', adj_face='Cara animada: mandíbula, labios y cejas se mueven con las del juego',
        adj_by_face='Colocar la cabeza por la cara (no por la articulación de la cabeza)',
        adj_face_found='Huesos de la cara encontrados: %s',
        adj_face_none='No se encontraron huesos de la cara (mandíbula, labios, cejas) por su nombre.',
        adj_weights_help='Qué hueso del juego mueve cada hueso de tu modelo. Doble clic para elegir otro o repartirlo '
                         'entre dos (un hueso de ayuda entre dos articulaciones). Los pesos en color: Vista previa → Pesos.',
        adj_game_bone='Hueso del juego', adj_how='Cómo', adj_by_hand='a mano',
        adj_smooth='Suavizar los pesos', adj_smooth_help='0 = como vienen; más = dobleces más suaves',
        adj_weight_first='Hueso del juego', adj_weight_second='Repartir con (opcional)',
        adj_weight_share='Parte del primero',
        pv_weights='Pesos', pv_weights_bone='Hueso del juego:', pv_strain='Marcar lo estirado en rojo',
        pv_side='Al lado:', pv_side_game='el original del juego', pv_side_prev='la conversión anterior',
        pv_weights_help='Azul oscuro: no lo mueve · verde: un poco · rojo: del todo',
        pv_3d='3D', pv_images='Imágenes', pv_tpose='Pose T', pv_armsdown='Brazos abajo (como en el juego)',
        pv_ghost='Original del juego al lado', pv_bones='Esqueleto del juego',
        pv_help='Arrastra: girar · clic derecho: mover · rueda: acercar · doble clic: encuadrar',
        pv_no_gl='Tu tarjeta gráfica no da OpenGL 3.3: solo hay imágenes fijas.',
        pv_joints='Esqueleto de tu modelo', joints_mirror='Simétrico (izquierda = derecha)',
        joints_reset='Volver al automático',
        joints_help='Arrastra un punto rojo para mover esa articulación; luego pulsa «Convertir».',
        joints_moved='Articulación movida. Pulsa «Convertir» para aplicarla.',
        joints_back='Esqueleto automático otra vez. Pulsa «Convertir» para aplicarlo.',
        joints_need_convert='Convierte el modelo una vez para poder mover su esqueleto.',
        role='Parte', model_bone='Hueso del modelo', how='Cómo', material='Material', triangles='Triángulos',
        uses='Usa', note='Nota', auto='automático', chosen='elegido', none='(ninguno)',
        back_auto='Volver a automático', ok='Aceptar', cancel='Cancelar', image='Imagen', colour='Color liso',
        pick_colour='Elegir color…', skip='Dejar fuera', working='Trabajando…', ready='Listo.',
        analyzed='Revisado: mira las pestañas Huesos y Materiales (doble clic para cambiar algo).',
        converted='Convertido. Mira la Vista previa.',
        check='Revisa estos materiales (no se encontró su imagen): %s',
        not_original='%s\n\n¿Construir encima de todas formas? (no recomendado)',
        hand_edited='Tu map.py tiene cambios hechos a mano. ¿Sobrescribirlo con lo que dicen las tablas?\n\n'
                    '(«No» convierte con tu map.py tal como está: modo avanzado.)',
        confirm_install='¿Instalar %s en el juego? Toy Story 3 tiene que estar cerrado.\n'
                        'La primera vez se guarda una copia del original junto al juego.',
        installed='Instalado. Abre el juego y juega con %s. «Restaurar original» lo deshace.',
        restored='Restaurado el %s original.', error='Error',
        preview_empty='Aún no hay vista previa: pulsa «Convertir».',
        drawing='Convirtiendo y dibujando la vista previa…\n(tarda unos segundos)',
        see_log='Los detalles están en la pestaña Registro.',
        advanced_note='Modo avanzado: las tablas no cambian tu map.py. Edítalo a mano (guía manual) y pulsa «Convertir».',
        pack_name='Nombre del mod', version='Versión', author='Tu nombre', what='Qué hace (una línea)',
        model_credits='Autor del modelo / permiso',
        exp_installer='Incluir también un instalador propio (.bat) para quien no tenga la herramienta',
        exp_installer_note='Sin él, el pack no lleva scripts: se instala arrastrándolo a TS3 Modding Tool y Nexus '
                           'no lo retiene para revisarlo. Con él, Nexus revisa cada subida a mano.',
        rights='Publica el modelo solo si su autor lo permite. El pack no lleva archivos del juego: solo tus cambios.',
        exported='Pack listo:\n%s\n\nSúbelo a Nexus con el crédito «Hecho con TS3 Modding Tool de keyloor».',
        no_game_first='Primero hace falta la carpeta del juego (Inicio → Buscar el juego).',
        sides={'Left': 'izq.', 'Right': 'der.'},
        notes={'linked in the FBX': 'enlazada en el modelo', 'by name': 'por el nombre', 'the only image': 'la única imagen',
               "the material's colour": 'color del material', 'check': 'REVISAR: adivinado', 'chosen': 'elegido',
               'left out (chosen)': 'fuera (elegido)'},
        roles={'pelvis': 'Cadera', 'chest': 'Pecho', 'neck': 'Cuello', 'head': 'Cabeza', 'clavicle': 'Clavícula',
               'shoulder': 'Hombro', 'elbow': 'Codo', 'hand': 'Mano', 'hip': 'Muslo', 'knee': 'Rodilla',
               'foot': 'Tobillo', 'toe': 'Dedos del pie'},
        about_text='%s\n\nCreada por %s.\n\nSi publicas un mod hecho con esta herramienta, pon en su página:\n'
                   '«Hecho con TS3 Modding Tool de %s».\n\nReferencias (solo como documentación): DisneyInfinityTools '
                   '(Kokonotcu) y DisneyInfinityCreator (LucasLhomme).\n\nHerramienta hecha por fans, sin relación con '
                   'Disney, Pixar ni Avalanche Software.'),
    'en': dict(
        file='File', home_menu='Start', quit='Quit', language='Language', help='Help',
        guide='Manual guide (Spanish)', agents='Instructions for AI agents', about='About',
        by='by %s  ·  version %s', game_found='Game: %s', game_missing='Toy Story 3 Complete Edition was not found.',
        game_looking='Looking for the game…', change='Change…', find_game='Find the game…',
        workspace='Workspace folder: %s',
        mod_chars='Characters', mod_chars_desc='Put your own model (FBX or OBJ) in place of Woody, Buzz or Jessie.',
        mod_music='Music and sounds', mod_music_desc="Change the game's songs and sounds.",
        mod_tex='Textures', mod_tex_desc='Change textures of characters and levels.', soon='Coming soon',
        mods_title='Installed mods', mods_desc='Install packages, review their changes and remove them using backups.',
        mods_open='Manage mods', mods_zip='Install mod…', mods_folder='Install from folder…',
        mods_refresh='Refresh list', mods_remove='Remove mod', mods_recover='Recover operation',
        mods_drop='Drop a mod ZIP or folder here, or use the buttons to choose one.',
        mods_no_drop='Use the buttons to choose a mod ZIP or folder.',
        mods_empty='No mods have been installed with this manager.', mods_count='%d installed mods',
        mods_scope='This list shows mods installed with the manager. Mods from other installers do not appear.',
        mods_select='Select a mod to see its description and the files it changes.',
        mods_files='Game files', mods_author='Author', mods_unknown='Not provided',
        mods_review='Review installation', mods_confirm='Install this mod',
        mods_review_note='Close Toy Story 3 before installing. A backup of replaced files will be kept.',
        mods_destination='Target game: %s', mods_size='%d files · %.1f MiB',
        mods_remove_confirm='Remove "%s"?\n\nFiles will return to their state before installation. Close the game first.',
        mods_installed='"%s" is installed.', mods_removed='"%s" has been removed.',
        mods_pending='An operation was interrupted. Press "Recover operation" before continuing.',
        mods_recovered='Recovery complete. You can manage your mods again.',
        mods_recover_confirm='Restore the state before the interrupted operation? Close the game first.',
        mods_busy='Wait for the current operation to finish.', mods_one='Drop one ZIP or folder at a time.',
        mods_failed='The operation could not be completed. Review these details:',
        mods_conflict='Another mod already changes this file: %s',
        mods_dependency='Missing dependency: %s', mods_declared='This package conflicts with: %s',
        mods_existing='This mod is already installed. Remove it before installing another version.',
        mods_dependent='Remove the dependent mod first: %s',
        mods_external='The file changed outside the manager and has been preserved: %s',
        mods_changed='The package or game changed after review. Choose the package again.',
        mods_closed='Close Toy Story 3 before changing mods.',
        mods_check='Check for updates', mods_open_update='Open the update page',
        mods_update='Update', mods_update_new='%s available', mods_update_ok='Up to date',
        mods_update_err='No answer', mods_update_line='New version %s: %s',
        mods_update_fail='GitHub could not be reached (%s). It will be retried later.',
        mods_updates_found='Updates available: %d. Select the mod and open its page to download it.',
        mods_updates_none='The mods that announce updates are up to date.',
        mods_updates_nothing='No installed mod says where to look for updates.',
        new_project='New project', open_other='Open another…', recent='Recent projects',
        no_recent='No projects yet.', project_name='Project name (for example, the model\'s):',
        bad_name='Use letters, digits, spaces or dashes.', back='← Start', open_folder='Open folder',
        open_map='Open map.py', advanced='Advanced mode: use my map.py as it is',
        step1='1 · Character you replace', other='Other:', step2='2 · Your model',
        pick_model='Choose model (FBX or OBJ)…', no_model='No model chosen.', textures='Textures: %s',
        no_textures='none (solid colours)', change_textures='Change textures…',
        obj_note='OBJ: it has no skeleton; the tool gives it one (humanoids in a T or A pose).',
        step3='3 · Convert and check', convert='Convert', analyze='Check bones and materials',
        step4='4 · Play or share', install='Install into the game', restore='Restore original',
        export='Export pack for Nexus',
        next_char='Next: choose the character you replace.', next_model='Next: choose your model (FBX or OBJ).',
        next_convert='Next: press "Convert". If you like, check the bones and materials first.',
        next_look='Look at the Preview. If something is wrong, fix it in Bones or Materials and convert again; '
                  'if it looks right, install it into the game.',
        tab_bones='Bones', tab_mats='Materials', tab_preview='Preview', tab_log='Log', tab_adjust='Adjustments',
        adj_head_title='Head and neck',
        adj_help="Moves the head (and the end of the neck with it) from where the game character's head is. "
                 'Negative = lower. Use it when the neck comes out stretched or squashed.',
        adj_info="Your model's neck is %.1f cm long and %s's %.1f cm: with the setting applied now it is stretched x%.2f "
                 '(the converter allows x0.80 to x1.25; beyond that it gets distorted).',
        adj_none="Press \"Convert\" or \"Check bones and materials\" to measure your model's neck.",
        adj_height='Head height', adj_natural='Neck at its own length', adj_reset='Back to 0',
        adj_apply='Apply and convert',
        adj_prop_title='Proportions',
        adj_prop_help="Width, height and depth of the torso, size of the head, thickness of neck, arms and legs. "
                      "Arm and leg length can't change: the joints must land on the character's so its animations "
                      'bend in the right place.',
        adj_torso_info="The tool already fits the torso to reach the character's shoulders and hips: "
                       '%s %% wide and %s %% tall. The values below apply on top of that.',
        adj_torso_w='Torso: width', adj_torso_h='Torso: height', adj_torso_d='Torso: depth',
        adj_head_size='Head: size', adj_neck_thick='Neck: thickness', adj_arms_thick='Arms: thickness',
        adj_legs_thick='Legs: thickness', adj_prop_reset='All to 100 %',
        adj_live='Live, while you move the controls (approximate: "Apply and convert" gives the exact result)',
        adj_undo='↶ Undo', adj_redo='↷ Redo', adj_undone='Undone.', adj_redone='Redone.',
        adj_versions='Versions:', adj_save_version='Save version…', adj_load_version='Load',
        adj_version_name='Name of this version of the adjustments:',
        adj_version_saved='Version "%s" saved.',
        adj_version_loaded='Version "%s" loaded. Press "Apply and convert" to see it.',
        adj_page_body='Head and proportions', adj_page_acc='Accessories and clothes', adj_page_face='Eyes and face',
        adj_page_weights='Weights',
        adj_acc_help="Your model's loose objects (hat, bag, a weapon, the hair...): which part of the body they move "
                     'with in the game, or left out of the model. Double click to change.',
        adj_garm_help="Makes one piece of clothing (one of your model's materials) narrower or wider. Double click.",
        adj_bone="Your model's bone", adj_place='Moves with', adj_auto_place='automatic (%s)',
        adj_material='Material', adj_width='Width',
        places=dict(auto='Automatic', hand_left='The left hand', hand_right='The right hand', head='The head',
                    chest='The chest', hips='The hips', out='Leave it out of the model'),
        adj_need_info='Press "Check bones and materials" (step 3) to see here what your model has.',
        adj_eyes_title='Eyes', adj_eyes_open='Open the eyelids (if your model has them shut)',
        adj_eye_top='Upper lid', adj_eye_bottom='Lower lid',
        adj_eyes_found='Eyes found (upper + lower lid bones): %s',
        adj_eyes_none='No eye and lid bones were found by name: with this model it does nothing.',
        adj_face_title='Face', adj_face="Animated face: jaw, lips and brows move with the game's",
        adj_by_face='Place the head by the face (not by the head joint)',
        adj_face_found='Face bones found: %s',
        adj_face_none='No face bones (jaw, lips, brows) were found by name.',
        adj_weights_help="Which game bone moves each of your model's bones. Double click to pick another or share it "
                         'between two (a helper bone between two joints). Weights in colour: Preview → Weights.',
        adj_game_bone='Game bone', adj_how='How', adj_by_hand='by hand',
        adj_smooth='Smooth the weights', adj_smooth_help='0 = as they are; more = softer bends',
        adj_weight_first='Game bone', adj_weight_second='Share with (optional)',
        adj_weight_share='Share of the first',
        pv_weights='Weights', pv_weights_bone='Game bone:', pv_strain='Mark stretched parts in red',
        pv_side='Beside it:', pv_side_game="the game's original", pv_side_prev='the conversion before',
        pv_weights_help="Dark blue: doesn't move it · green: a little · red: fully",
        pv_3d='3D', pv_images='Images', pv_tpose='T pose', pv_armsdown='Arms down (as in the game)',
        pv_ghost="The game's original beside it", pv_bones="The game's skeleton",
        pv_help='Drag: turn · right drag: move · wheel: zoom · double click: frame',
        pv_no_gl="Your graphics card doesn't offer OpenGL 3.3: only still images.",
        pv_joints="Your model's skeleton", joints_mirror='Mirror (left = right)', joints_reset='Back to automatic',
        joints_help='Drag a red dot to move that joint, then press "Convert".',
        joints_moved='Joint moved. Press "Convert" to apply it.',
        joints_back='Automatic skeleton again. Press "Convert" to apply it.',
        joints_need_convert="Convert the model once to be able to move its skeleton.",
        role='Part', model_bone='Model bone', how='How', material='Material', triangles='Triangles',
        uses='Uses', note='Note', auto='automatic', chosen='chosen', none='(none)',
        back_auto='Back to automatic', ok='OK', cancel='Cancel', image='Image', colour='Solid colour',
        pick_colour='Pick colour…', skip='Leave out', working='Working…', ready='Ready.',
        analyzed='Checked: see the Bones and Materials tabs (double-click to change something).',
        converted='Converted. Look at the Preview.',
        check='Check these materials (no image was found for them): %s',
        not_original='%s\n\nBuild on it anyway? (not recommended)',
        hand_edited='Your map.py has changes made by hand. Overwrite it with what the tables say?\n\n'
                    '("No" converts with your map.py as it is: advanced mode.)',
        confirm_install='Install %s into the game? Toy Story 3 must be closed.\n'
                        'The first time, a copy of the original is kept next to the game.',
        installed='Installed. Start the game and play as %s. "Restore original" undoes it.',
        restored='Restored the original %s.', error='Error',
        preview_empty='No preview yet: press "Convert".',
        drawing='Converting and drawing the preview…\n(it takes a few seconds)',
        see_log='The details are in the Log tab.',
        advanced_note='Advanced mode: the tables do not change your map.py. Edit it by hand (manual guide) and press "Convert".',
        pack_name='Mod name', version='Version', author='Your name', what='What it does (one line)',
        model_credits='Model author / permission',
        exp_installer="Also include its own installer (.bat) for players without the tool",
        exp_installer_note='Without it the pack holds no scripts: it is installed by dropping it on TS3 Modding Tool '
                           'and Nexus does not hold it for review. With it, Nexus reviews every upload by hand.',
        rights='Publish the model only if its author allows it. The pack has no game files: only your changes.',
        exported='Pack ready:\n%s\n\nUpload it to Nexus with the credit "Made with TS3 Modding Tool by keyloor".',
        no_game_first='The game folder is needed first (Start → Find the game).',
        sides={'Left': 'left', 'Right': 'right'},
        notes={'check': 'CHECK: guessed', 'linked in the FBX': 'linked in the model'},
        roles={'pelvis': 'Hips', 'chest': 'Chest', 'neck': 'Neck', 'head': 'Head', 'clavicle': 'Clavicle',
               'shoulder': 'Shoulder', 'elbow': 'Elbow', 'hand': 'Hand', 'hip': 'Thigh', 'knee': 'Knee',
               'foot': 'Ankle', 'toe': 'Toes'},
        about_text='%s\n\nMade by %s.\n\nIf you publish a mod made with this tool, put on its page:\n'
                   '"Made with TS3 Modding Tool by %s".\n\nReferences (documentation only): DisneyInfinityTools '
                   '(Kokonotcu) and DisneyInfinityCreator (LucasLhomme).\n\nFan-made tool, not affiliated with '
                   'Disney, Pixar or Avalanche Software.'),
}
OPTIONAL = {'neck', 'clavicleLeft', 'clavicleRight', 'toeLeft', 'toeRight'}
TAB_BONES, TAB_MATS, TAB_ADJUST, TAB_PREVIEW, TAB_LOG = range(5)


class Out:
    """stdout for the worker threads: lines go to the log tab"""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        self.q.put(('log', s))

    def flush(self):
        pass


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest() if os.path.isfile(path) else None


def documents():
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)     # CSIDL_PERSONAL: Documents
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        sys.stdout = sys.stderr = Out(self.q)
        self.settings = self.load_settings()
        self.lang = self.settings.get('lang', 'es')
        self.settings.setdefault('workspace', os.path.join(documents(), TOOL))
        self.work, self.proj = None, {}
        self.info = self.tables = None
        self.force = False
        self.busy = False
        self.drop_target = None
        self.mods_rows = {}
        self.mods_ready = self.mods_pending = False
        self.chars = []
        self.photos = []
        self.game_state = 'looking'
        root.title('%s %s — %s' % (TOOL, VERSION, AUTHOR))
        root.geometry('1180x860')
        root.minsize(960, 700)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-z>', lambda e: self.undo_key(-1))   # undo / redo in the Adjustments tab
        root.bind('<Control-y>', lambda e: self.undo_key(+1))
        self.styles()
        self.screen = 'home'
        self.build()
        self.look_for_game(self.settings.get('game'))
        root.after(100, self.poll)

    # ------------------------------------------------------------------ settings, texts, styles
    def load_settings(self):
        for p in ((SETTINGS,) if os.environ.get('TS3TOOL_SETTINGS') else (SETTINGS, OLD_SETTINGS)):
            try:
                s = json.load(open(p, encoding='utf-8'))
                if p == OLD_SETTINGS:
                    s = {'lang': s.get('lang', 'es'), 'recent': [s['project']] if s.get('project') else []}
                return s
            except Exception:
                continue
        return {}

    def save_settings(self):
        self.settings['lang'] = self.lang
        try:
            with open(SETTINGS, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=1)
        except OSError:
            pass

    def t(self, k):
        return TEXT[self.lang][k]

    def role_label(self, role):
        for s in ('Left', 'Right'):
            if role.endswith(s):
                return '%s (%s)' % (self.t('roles')[role[:-len(s)]], self.t('sides')[s])
        return self.t('roles')[role]

    def styles(self):
        st = ttk.Style()
        try:
            st.theme_use('vista')
        except tk.TclError:
            pass
        st.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        st.configure('Sub.TLabel', font=('Segoe UI', 10), foreground='#666666')
        st.configure('Head.TLabel', font=('Segoe UI', 13, 'bold'))
        st.configure('Muted.TLabel', foreground='#777777')
        st.configure('Hint.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#1a5fb4')
        st.configure('Big.TButton', font=('Segoe UI', 11), padding=(14, 8))
        st.configure('Char.Toolbutton', font=('Segoe UI', 11, 'bold'), padding=(12, 8))
        st.configure('Card.TFrame', relief='groove', borderwidth=2)
        st.configure('Card.TLabelframe.Label', font=('Segoe UI', 10, 'bold'))

    # ------------------------------------------------------------------ frame
    def build(self):
        self.release_views()
        for w in self.root.winfo_children():
            w.destroy()
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label=self.t('home_menu'), command=self.show_home)
        fm.add_command(label=self.t('new_project'), command=self.new_project)
        fm.add_command(label=self.t('open_other'), command=self.open_other)
        fm.add_command(label=self.t('mods_title'), command=self.show_mods)
        fm.add_separator(); fm.add_command(label=self.t('quit'), command=self.close)
        m.add_cascade(label=self.t('file'), menu=fm)
        lm = tk.Menu(m, tearoff=0)
        lm.add_command(label='Español', command=lambda: self.set_lang('es'))
        lm.add_command(label='English', command=lambda: self.set_lang('en'))
        m.add_cascade(label=self.t('language'), menu=lm)
        hm = tk.Menu(m, tearoff=0)
        hm.add_command(label=self.t('guide'), command=lambda: self.open_path(paths.doc('GUIA_MANUAL.md')))
        hm.add_command(label=self.t('agents'), command=lambda: self.open_path(paths.doc('AGENTS.md')))
        hm.add_separator(); hm.add_command(label=self.t('about'), command=self.about)
        m.add_cascade(label=self.t('help'), menu=hm)
        self.root.config(menu=m)
        self.status = tk.StringVar(value=self.t('ready'))
        bar = ttk.Frame(self.root, relief='sunken')
        bar.pack(fill='x', side='bottom')
        self.spinner = ttk.Progressbar(bar, mode='indeterminate', length=180)   # shown while something runs
        ttk.Label(bar, textvariable=self.status, padding=(10, 3)).pack(side='left', fill='x', expand=True)
        self.body = ttk.Frame(self.root)
        self.body.pack(fill='both', expand=True)
        self.buttons = []
        if self.screen == 'mods':
            self.build_mods()
        else:
            (self.build_project if self.screen == 'project' and self.work else self.build_home)()
        self.root.after_idle(self.setup_drop)

    def clear_body(self):
        self.release_views()
        for w in self.body.winfo_children():
            w.destroy()
        self.buttons = []
        for k in ('bones_tv', 'mats_tv', 'pv_body', 'log', 'nb'):
            self.__dict__.pop(k, None)

    def set_lang(self, lang):
        if self.busy:
            return
        self.lang = lang
        self.save_settings()
        self.build()

    # ------------------------------------------------------------------ start screen
    def show_home(self):
        if self.busy:
            return
        self.screen = 'home'
        self.clear_body()
        self.build_home()

    def build_home(self):
        f = ttk.Frame(self.body, padding=(28, 20))
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=TOOL, style='Title.TLabel').pack(anchor='w')
        ttk.Label(f, text=self.t('by') % (AUTHOR, VERSION), style='Sub.TLabel').pack(anchor='w', pady=(0, 14))

        g = ttk.Frame(f); g.pack(fill='x', pady=2)
        self.game_lbl = ttk.Label(g)
        self.game_lbl.pack(side='left')
        self.game_btn = ttk.Button(g, command=self.browse_game)
        self.game_btn.pack(side='left', padx=10)
        self.show_game()
        w = ttk.Frame(f); w.pack(fill='x', pady=2)
        ttk.Label(w, text=self.t('workspace') % self.settings['workspace']).pack(side='left')
        ttk.Button(w, text=self.t('change'), command=self.browse_workspace).pack(side='left', padx=10)
        ttk.Button(w, text=self.t('open_folder'), command=lambda: (os.makedirs(self.settings['workspace'], exist_ok=True),
                                                                   self.open_path(self.settings['workspace']))).pack(side='left')

        cards = ttk.Frame(f); cards.pack(fill='both', expand=True, pady=(18, 0))
        cards.columnconfigure(0, weight=3); cards.columnconfigure(1, weight=2)
        c = ttk.Frame(cards, style='Card.TFrame', padding=16)
        c.grid(row=0, column=0, rowspan=3, sticky='nsew', padx=(0, 12))
        ttk.Label(c, text=self.t('mod_chars'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(c, text=self.t('mod_chars_desc')).pack(anchor='w', pady=(2, 10))
        b = ttk.Frame(c); b.pack(fill='x')
        ttk.Button(b, text=self.t('new_project'), style='Big.TButton', command=self.new_project).pack(side='left')
        ttk.Button(b, text=self.t('open_other'), command=self.open_other).pack(side='left', padx=10)
        ttk.Label(c, text=self.t('recent'), style='Muted.TLabel').pack(anchor='w', pady=(14, 2))
        self.recent = [p for p in self.recent_projects()]
        lb = tk.Listbox(c, height=10, font=('Segoe UI', 10), activestyle='none', borderwidth=1)
        for p in self.recent:
            pj = K.load_project(p)
            char = dict(MAIN).get(pj.get('character'), pj.get('character') or '?')
            model = os.path.basename(pj.get('fbx') or '') or '-'
            lb.insert('end', '  %s   —   %s  ←  %s' % (os.path.basename(p), char, model))
        if not self.recent:
            lb.insert('end', '  ' + self.t('no_recent'))
        lb.pack(fill='both', expand=True)
        lb.bind('<Double-1>', lambda e: self.recent and lb.curselection() and self.open_project(self.recent[lb.curselection()[0]]))
        lb.bind('<Return>', lambda e: self.recent and lb.curselection() and self.open_project(self.recent[lb.curselection()[0]]))
        s = ttk.Frame(cards, style='Card.TFrame', padding=16)
        s.grid(row=0, column=1, sticky='nsew', pady=(0, 12))
        ttk.Label(s, text=self.t('mods_title'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(s, text=self.t('mods_desc'), wraplength=350).pack(anchor='w', pady=(2, 10))
        ttk.Button(s, text=self.t('mods_open'), style='Big.TButton', command=self.show_mods).pack(anchor='w')
        for r, (k, d) in enumerate((('mod_music', 'mod_music_desc'), ('mod_tex', 'mod_tex_desc')), start=1):
            s = ttk.Frame(cards, style='Card.TFrame', padding=16)
            s.grid(row=r, column=1, sticky='nsew', pady=(0, 12) if r == 1 else 0)
            ttk.Label(s, text=self.t(k), style='Head.TLabel', foreground='#888888').pack(anchor='w')
            ttk.Label(s, text=self.t(d), style='Muted.TLabel').pack(anchor='w', pady=(2, 6))
            ttk.Label(s, text=self.t('soon'), style='Muted.TLabel').pack(anchor='w')

    # ------------------------------------------------------------------ installed mods
    def setup_drop(self):
        if os.name != 'nt' or not self.root.winfo_exists():
            return
        hwnd = self.root.winfo_id()
        if self.drop_target and self.drop_target.hwnd == hwnd:
            return
        try:
            if self.drop_target:
                self.drop_target.close()
            self.drop_target = DropTarget(hwnd, lambda files: self.q.put(('drop', files)))
        except OSError:
            self.drop_target = None
        if self.screen == 'mods':
            self.mods_drop_lbl.config(text=self.t('mods_drop' if self.drop_target else 'mods_no_drop'))

    def close(self):
        if self.busy:
            self.status.set(self.t('mods_busy'))
            return
        if self.drop_target:
            self.drop_target.close()
        self.release_views()
        self.root.destroy()

    def dropped(self, files):
        if self.busy or self.root.grab_current():
            self.status.set(self.t('mods_busy'))
            return
        if len(files) != 1:
            messagebox.showinfo(self.t('mods_title'), self.t('mods_one'), parent=self.root)
            return
        if self.screen not in ('home', 'mods'):
            return
        if self.screen == 'home':
            self.show_mods(load=False)
        self.choose_package(files[0])

    def show_mods(self, load=True):
        if self.busy:
            return
        self.screen = 'mods'
        self.clear_body()
        self.build_mods(load)

    def build_mods(self, load=True):
        f = ttk.Frame(self.body, padding=(28, 20)); f.pack(fill='both', expand=True)
        top = ttk.Frame(f); top.pack(fill='x')
        self.mods_back = ttk.Button(top, text=self.t('back'), command=self.show_home)
        self.mods_back.pack(side='left', padx=(0, 16))
        ttk.Label(top, text=self.t('mods_title'), style='Title.TLabel').pack(side='left')
        ttk.Label(f, text=self.t('mods_scope'), style='Sub.TLabel').pack(anchor='w', pady=(8, 12))
        g = ttk.Frame(f); g.pack(fill='x')
        self.game_lbl = ttk.Label(g); self.game_lbl.pack(side='left')
        self.game_btn = ttk.Button(g, command=self.browse_game); self.game_btn.pack(side='left', padx=10)
        self.show_game()
        self.mods_drop_lbl = ttk.Label(f, text=self.t('mods_drop' if self.drop_target else 'mods_no_drop'),
                                       style='Hint.TLabel', padding=(12, 14), relief='groove')
        self.mods_drop_lbl.pack(fill='x', pady=16)
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(0, 12))
        self.mods_zip_btn = ttk.Button(bar, text=self.t('mods_zip'), command=self.choose_package)
        self.mods_folder_btn = ttk.Button(bar, text=self.t('mods_folder'), command=lambda: self.choose_package(folder=True))
        self.mods_reload_btn = ttk.Button(bar, text=self.t('mods_refresh'), command=self.reload_mods)
        self.mods_remove_btn = ttk.Button(bar, text=self.t('mods_remove'), command=self.remove_mod)
        self.mods_recover_btn = ttk.Button(bar, text=self.t('mods_recover'), command=self.recover_mods)
        self.mods_check_btn = ttk.Button(bar, text=self.t('mods_check'), command=self.check_updates)
        self.mods_page_btn = ttk.Button(bar, text=self.t('mods_open_update'), command=self.open_update)
        for b in (self.mods_zip_btn, self.mods_folder_btn, self.mods_reload_btn, self.mods_remove_btn,
                  self.mods_check_btn, self.mods_page_btn):
            b.pack(side='left', padx=(0, 8))
        self.mods_recover_btn.pack(side='right')
        self.buttons = [self.mods_back, self.game_btn, self.mods_zip_btn, self.mods_folder_btn,
                        self.mods_reload_btn, self.mods_remove_btn, self.mods_recover_btn,
                        self.mods_check_btn, self.mods_page_btn]
        pane = ttk.Frame(f); pane.pack(fill='both', expand=True)
        pane.rowconfigure(0, weight=1); pane.columnconfigure(0, weight=1)
        self.mods_tree = ttk.Treeview(pane, columns=('name', 'version', 'author', 'files', 'update'),
                                     show='headings',
                                     selectmode='browse', height=8)
        for key, label, width in (('name', 'pack_name', 320), ('version', 'version', 100),
                                  ('author', 'mods_author', 200), ('files', 'mods_files', 120),
                                  ('update', 'mods_update', 140)):
            self.mods_tree.heading(key, text=self.t(label))
            self.mods_tree.column(key, width=width, minwidth=80, stretch=key in ('name', 'author'))
        self.mods_tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(pane, orient='vertical', command=self.mods_tree.yview)
        scroll.grid(row=0, column=1, sticky='ns'); self.mods_tree.config(yscrollcommand=scroll.set)
        self.mods_tree.bind('<<TreeviewSelect>>', lambda e: self.mod_selected())
        self.mods_note = ttk.Label(f, text=self.t('working'), style='Muted.TLabel', wraplength=1000)
        self.mods_note.pack(anchor='w', pady=(8, 12))
        self.mods_details = tk.Text(f, height=7, wrap='word', font=('Segoe UI', 10), relief='flat',
                                    background='#f4f4f4', padx=12, pady=8)
        self.mods_details.pack(fill='x')
        self.set_mod_details(self.t('mods_select'))
        self.mods_rows, self.mods_updates = {}, {}
        self.mods_ready = self.mods_pending = False
        self.refresh_mod_controls()
        if load:
            self.reload_mods()

    def refresh_mod_controls(self):
        if self.screen != 'mods':
            return
        enabled = not self.busy and bool(self.settings.get('game'))
        for button in (self.mods_zip_btn, self.mods_folder_btn):
            button.state(['!disabled'] if enabled and not self.mods_pending else ['disabled'])
        self.mods_reload_btn.state(['!disabled'] if enabled else ['disabled'])
        selected = bool(self.mods_tree.selection())
        self.mods_remove_btn.state(['!disabled'] if enabled and self.mods_ready and selected else ['disabled'])
        self.mods_recover_btn.state(['!disabled'] if enabled and self.mods_pending else ['disabled'])
        self.mods_check_btn.state(['!disabled'] if enabled and self.mods_ready and self.mods_rows
                                  else ['disabled'])
        self.mods_page_btn.state(['!disabled'] if not self.busy and self.selected_update() else ['disabled'])

    def selected_update(self):
        sel = self.mods_tree.selection()
        info = self.mods_updates.get(sel[0]) if sel else None
        return info if info and info['update'] else None

    def set_mod_details(self, text):
        self.mods_details.config(state='normal')
        self.mods_details.delete('1.0', 'end'); self.mods_details.insert('1.0', text)
        self.mods_details.config(state='disabled')

    def mod_selected(self):
        if self.screen != 'mods':
            return
        sel = self.mods_tree.selection()
        mod = self.mods_rows.get(sel[0]) if sel else None
        text = self.t('mods_select')
        if mod:
            m = mod['metadata']
            text = '%s  %s\n%s\n\n%s:\n%s' % (m['name'], m['version'], m['description'],
                self.t('mods_files'), '\n'.join(r['path'] for r in mod['files']))
            info = self.mods_updates.get(m['id'])
            if info and info['update']:
                text = self.t('mods_update_line') % (info['latest'], info['url']) + '\n\n' + text
            elif info and info['error']:
                text = self.t('mods_update_fail') % info['error'] + '\n\n' + text
        self.set_mod_details(text)
        self.refresh_mod_controls()

    def reload_mods(self, notice=None):
        if self.busy or self.screen != 'mods':
            return
        game = self.settings.get('game')
        if not game:
            self.mods_note.config(text=self.t('no_game_first'))
            return
        selected = self.mods_tree.selection()
        def read():
            store = K.modstore.Store(game)
            pending = store.path(K.modstore.JOURNAL).exists()
            records = [] if pending else store.list()
            return pending, records, modupdate.check(records, str(store.path(modupdate.CACHE)), fetch=None)
        def done(result):
            self.mods_pending, records, updates = result
            self.mods_updates = {u['id']: u for u in updates}
            self.mods_ready = not self.mods_pending
            self.mods_rows = {r['metadata']['id']: r for r in records}
            self.mods_tree.delete(*self.mods_tree.get_children())
            for mid, r in self.mods_rows.items():
                m = r['metadata']
                self.mods_tree.insert('', 'end', iid=mid, values=(m['name'], m['version'],
                    m['author'] or self.t('mods_unknown'), len(r['files']), self.update_text(mid)))
            if selected and selected[0] in self.mods_rows:
                self.mods_tree.selection_set(selected[0])
            self.mod_selected()
            self.mods_note.config(text=self.t('mods_pending') if self.mods_pending else
                                  self.t('mods_count') % len(records) if records else self.t('mods_empty'))
            self.status.set(notice or self.t('ready'))
        self.run(read, done, on_error=self.mods_failed)

    def update_text(self, mid):
        info = self.mods_updates.get(mid)
        if not info:
            return ''
        if info['update']:
            return self.t('mods_update_new') % info['latest']
        return self.t('mods_update_err') if info['error'] else self.t('mods_update_ok')

    def check_updates(self):
        """asks GitHub now for every installed mod whose mod.json has update.github (never downloads)"""
        if self.busy or not self.mods_ready:
            return
        store = K.modstore.Store(self.settings['game'])
        records = list(self.mods_rows.values())
        def done(updates):
            self.mods_updates = {u['id']: u for u in updates}
            for mid in self.mods_rows:
                self.mods_tree.set(mid, 'update', self.update_text(mid))
            new = sum(u['update'] for u in updates)
            if not updates:
                note = self.t('mods_updates_nothing')
            elif new:
                note = self.t('mods_updates_found') % new
            elif all(u['error'] for u in updates):
                note = self.t('mods_update_fail') % updates[0]['error']
            else:
                note = self.t('mods_updates_none')
            self.mods_note.config(text=note)
            self.mod_selected()
            self.status.set(note)
        self.run(lambda: modupdate.check(records, str(store.path(modupdate.CACHE)), force=True), done,
                 on_error=self.mods_failed)

    def open_update(self):
        info = self.selected_update()
        if info and info['url'].startswith('https://github.com/'):
            webbrowser.open(info['url'])

    def mods_failed(self, msg):
        exact = {
            'mod is already installed; remove it before installing another version': 'mods_existing',
            'package or game changed since preview; review the package again': 'mods_changed',
            'close Toy Story 3 before changing mods': 'mods_closed',
            'interrupted operation: run mods recover first': 'mods_pending'}
        prefixes = {'file conflict: ': 'mods_conflict', 'missing dependency: ': 'mods_dependency',
                    'declared conflict with ': 'mods_declared', 'remove dependent mod first: ': 'mods_dependent',
                    'file changed outside the manager; kept untouched: ': 'mods_external'}
        translated = self.t(exact[msg]) if msg in exact else msg
        for prefix, key in prefixes.items():
            if msg.startswith(prefix):
                translated = self.t(key) % msg[len(prefix):]
                break
        self.status.set(self.t('error'))
        if self.screen == 'mods':
            try:
                self.mods_pending = K.modstore.Store(self.settings['game']).path(K.modstore.JOURNAL).exists()
            except (ValueError, OSError, KeyError):
                self.mods_pending = False
            self.mods_note.config(text=self.t('mods_pending') if self.mods_pending else translated)
            self.refresh_mod_controls()
        messagebox.showerror(self.t('error'), self.t('mods_failed') + '\n\n' + translated, parent=self.root)

    def choose_package(self, source=None, folder=False):
        if self.busy or self.root.grab_current():
            return
        game = self.settings.get('game')
        if not game:
            messagebox.showinfo(self.t('mods_title'), self.t('no_game_first'), parent=self.root)
            return
        if source is None:
            source = filedialog.askdirectory(title=self.t('mods_folder'), parent=self.root) if folder else \
                filedialog.askopenfilename(title=self.t('mods_zip'), filetypes=[('ZIP', '*.zip')], parent=self.root)
        if not source:
            return
        source = os.path.abspath(source)
        self.run(lambda: K.modstore.Store(game).preview(source),
                 lambda result: self.review_package(source, game, result), on_error=self.mods_failed)

    def review_package(self, source, game, result):
        meta = result['metadata']
        d, f = self.dialog(self.t('mods_review'))
        ttk.Label(f, text=meta['name'], style='Head.TLabel', wraplength=660).pack(anchor='w')
        ttk.Label(f, text='%s %s · %s: %s' % (self.t('version'), meta['version'], self.t('mods_author'),
            meta['author'] or self.t('mods_unknown')), wraplength=660).pack(anchor='w', pady=(3, 10))
        ttk.Label(f, text=meta['description'], wraplength=660).pack(anchor='w')
        ttk.Label(f, text=self.t('mods_destination') % game, wraplength=660).pack(anchor='w', pady=(12, 4))
        ttk.Label(f, text=self.t('mods_size') % (len(result['files']), result['bytes'] / 1024**2)).pack(anchor='w')
        items = tk.Text(f, width=80, height=min(8, len(result['files']) + 1), wrap='word')
        items.insert('1.0', '\n'.join(r['path'] for r in result['files']))
        items.config(state='disabled'); items.pack(fill='both', expand=True, pady=8)
        ttk.Label(f, text=self.t('mods_review_note'), wraplength=660).pack(anchor='w', pady=(0, 10))
        bar = ttk.Frame(f); bar.pack(fill='x')
        def dismiss():
            d.destroy()
            self.reload_mods()
        def install():
            d.destroy()
            self.run(lambda: K.modstore.Store(game).install(source, expected=result['ticket']),
                     lambda m: self.reload_mods(self.t('mods_installed') % m['name']), on_error=self.mods_failed)
        ttk.Button(bar, text=self.t('mods_confirm'), command=install).pack(side='right')
        cancel = ttk.Button(bar, text=self.t('cancel'), command=dismiss)
        cancel.pack(side='right', padx=8)
        d.bind('<Escape>', lambda e: dismiss())
        d.protocol('WM_DELETE_WINDOW', dismiss)
        self.status.set(self.t('mods_review'))

    def remove_mod(self):
        if self.busy:
            return
        sel = self.mods_tree.selection()
        if not sel or sel[0] not in self.mods_rows:
            return
        m = self.mods_rows[sel[0]]['metadata']
        game = self.settings['game']
        if messagebox.askyesno(self.t('mods_remove'), self.t('mods_remove_confirm') % m['name'], parent=self.root):
            self.run(lambda: K.modstore.Store(game).remove(m['id']),
                     lambda meta: self.reload_mods(self.t('mods_removed') % meta['name']), on_error=self.mods_failed)

    def recover_mods(self):
        if self.busy or not self.mods_pending:
            return
        game = self.settings['game']
        if messagebox.askyesno(self.t('mods_recover'), self.t('mods_recover_confirm'), parent=self.root):
            self.run(lambda: K.modstore.Store(game).recover(),
                     lambda _: self.reload_mods(self.t('mods_recovered')), on_error=self.mods_failed)

    def recent_projects(self):
        seen, out = set(), []
        root = os.path.join(self.settings['workspace'], 'Personajes')
        found = [os.path.join(root, d) for d in sorted(os.listdir(root))] if os.path.isdir(root) else []
        for p in self.settings.get('recent', []) + found:
            p = os.path.normpath(p)
            if p.lower() not in seen and os.path.isfile(os.path.join(p, 'kit_project.json')):
                seen.add(p.lower()); out.append(p)
        return out[:12]

    def show_game(self):
        if not hasattr(self, 'game_lbl') or not self.game_lbl.winfo_exists():
            return
        g = self.settings.get('game')
        if self.game_state == 'looking':
            self.game_lbl.config(text=self.t('game_looking')); self.game_btn.config(text=self.t('find_game'))
        elif g:
            self.game_lbl.config(text=self.t('game_found') % g); self.game_btn.config(text=self.t('change'))
        else:
            self.game_lbl.config(text=self.t('game_missing')); self.game_btn.config(text=self.t('find_game'))

    def look_for_game(self, given=None):
        self.game_state = 'looking'
        self.show_game()

        def job():
            g = K.find_game(given)
            return g, K.characters(g)

        def done(res):
            self.settings['game'], self.chars = res
            self.game_state = 'found'
            self.save_settings()
            self.show_game()
            if self.screen == 'project':
                self.fill_others()
            elif self.screen == 'mods':
                self.reload_mods()

        def failed(msg):
            self.game_state = 'missing'
            self.settings.pop('game', None)
            self.show_game()
        self.run(job, done, quiet=True, on_error=failed)

    def browse_game(self):
        if self.busy:
            return
        d = filedialog.askdirectory(title=self.t('find_game'))
        if d:
            self.look_for_game(d)

    def browse_workspace(self):
        if self.busy:
            return
        d = filedialog.askdirectory(title=self.t('workspace') % '')
        if d:
            self.settings['workspace'] = d
            self.save_settings()
            self.show_home()

    def new_project(self):
        if self.busy:
            return
        d, f = self.dialog(self.t('new_project'))
        ttk.Label(f, text=self.t('project_name')).pack(anchor='w')
        v = tk.StringVar()
        e = ttk.Entry(f, textvariable=v, width=44); e.pack(fill='x', pady=6); e.after(50, e.focus_set)       # once the dialog shows
        msg = ttk.Label(f, style='Muted.TLabel'); msg.pack(anchor='w')

        def go(*_):
            name = v.get().strip()
            if not re.fullmatch(r'[\w .()-]{1,60}', name):
                msg.config(text=self.t('bad_name')); return
            p = os.path.join(self.settings['workspace'], 'Personajes', name)
            os.makedirs(p, exist_ok=True)
            if not os.path.isfile(os.path.join(p, 'kit_project.json')):
                K.save_project(p, {'game': self.settings.get('game')} if self.settings.get('game') else {})
            d.destroy()
            self.open_project(p)
        e.bind('<Return>', go)
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=go).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)

    def open_other(self):
        if self.busy:
            return
        d = filedialog.askdirectory(title=self.t('open_other'), initialdir=self.settings['workspace'])
        if d:
            self.open_project(d)

    # ------------------------------------------------------------------ project screen
    def open_project(self, d):
        if self.busy:
            return
        self.work = os.path.abspath(d)
        self.proj = K.load_project(self.work)
        if not self.proj.get('game') and self.settings.get('game'):
            self.proj['game'] = self.settings['game']
        self.info = self.tables = None
        self.force = False
        rec = [p for p in self.settings.get('recent', []) if os.path.normpath(p).lower() != self.work.lower()]
        self.settings['recent'] = [self.work] + rec[:11]
        self.save_settings()
        self.screen = 'project'
        self.clear_body()
        self.build_project()

    def build_project(self):
        top = ttk.Frame(self.body, padding=(12, 10, 12, 4)); top.pack(fill='x')
        ttk.Button(top, text=self.t('back'), command=self.show_home).pack(side='left')
        ttk.Label(top, text=os.path.basename(self.work), style='Head.TLabel').pack(side='left', padx=12)
        ttk.Label(top, text=self.work, style='Muted.TLabel').pack(side='left')
        ttk.Button(top, text=self.t('open_folder'), command=lambda: self.open_path(self.work)).pack(side='right')
        ttk.Button(top, text=self.t('open_map'),
                   command=lambda: self.open_path(os.path.join(self.work, 'map.py'))).pack(side='right', padx=6)
        self.adv = tk.BooleanVar(value=bool(self.proj.get('advanced')))
        ttk.Checkbutton(top, text=self.t('advanced'), variable=self.adv, command=self.toggle_advanced).pack(side='right', padx=10)

        steps = ttk.Frame(self.body, padding=(12, 4)); steps.pack(fill='x')
        for k in range(4):
            steps.columnconfigure(k, weight=1, uniform='steps')
        s1 = ttk.LabelFrame(steps, text=self.t('step1'), padding=10, style='Card.TLabelframe')
        s1.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        self.char = tk.StringVar(value=self.proj.get('character') or '')
        for c, label in MAIN:
            ttk.Radiobutton(s1, text=label, value=c, variable=self.char, style='Char.Toolbutton',
                            command=self.char_chosen).pack(fill='x', pady=2)
        o = ttk.Frame(s1); o.pack(fill='x', pady=(6, 0))
        ttk.Label(o, text=self.t('other')).pack(side='left')
        self.other_box = ttk.Combobox(o, state='readonly', width=18)
        self.other_box.pack(side='left', fill='x', expand=True, padx=(6, 0))
        self.other_box.bind('<<ComboboxSelected>>', lambda e: (self.char.set(self.other_box.get()), self.char_chosen()))
        self.fill_others()

        s2 = ttk.LabelFrame(steps, text=self.t('step2'), padding=10, style='Card.TLabelframe')
        s2.grid(row=0, column=1, sticky='nsew', padx=6)
        ttk.Button(s2, text=self.t('pick_model'), style='Big.TButton', command=self.browse_model).pack(fill='x')
        self.model_lbl = ttk.Label(s2, wraplength=250); self.model_lbl.pack(anchor='w', pady=(8, 2))
        self.tex_lbl = ttk.Label(s2, wraplength=250, style='Muted.TLabel'); self.tex_lbl.pack(anchor='w')
        ttk.Button(s2, text=self.t('change_textures'), command=self.browse_textures).pack(anchor='w', pady=(6, 0))
        self.obj_lbl = ttk.Label(s2, wraplength=250, style='Muted.TLabel'); self.obj_lbl.pack(anchor='w', pady=(6, 0))

        s3 = ttk.LabelFrame(steps, text=self.t('step3'), padding=10, style='Card.TLabelframe')
        s3.grid(row=0, column=2, sticky='nsew', padx=6)
        self.btn_convert = ttk.Button(s3, text=self.t('convert'), style='Big.TButton', command=self.convert)
        self.btn_convert.pack(fill='x')
        self.btn_analyze = ttk.Button(s3, text=self.t('analyze'), command=self.analyze)
        self.btn_analyze.pack(fill='x', pady=(8, 0))

        s4 = ttk.LabelFrame(steps, text=self.t('step4'), padding=10, style='Card.TLabelframe')
        s4.grid(row=0, column=3, sticky='nsew', padx=(6, 0))
        self.btn_install = ttk.Button(s4, text=self.t('install'), style='Big.TButton', command=self.install)
        self.btn_install.pack(fill='x')
        self.btn_export = ttk.Button(s4, text=self.t('export'), command=self.export)
        self.btn_export.pack(fill='x', pady=(8, 0))
        self.btn_restore = ttk.Button(s4, text=self.t('restore'), command=self.restore)
        self.btn_restore.pack(fill='x', pady=(8, 0))
        self.buttons = [self.btn_convert, self.btn_analyze, self.btn_install, self.btn_export, self.btn_restore]

        self.hint = ttk.Label(self.body, style='Hint.TLabel', padding=(14, 6), wraplength=1100)
        self.hint.pack(fill='x')
        self.nb = ttk.Notebook(self.body)
        self.nb.pack(fill='both', expand=True, padx=12, pady=(0, 6))
        self.bones_tv = self.table(self.t('tab_bones'), (('role', 230), ('bone', 330), ('how', 120)),
                                   (self.t('role'), self.t('model_bone'), self.t('how')), self.edit_bone)
        self.mats_tv = self.table(self.t('tab_mats'), (('mat', 230), ('tris', 90), ('uses', 330), ('note', 200)),
                                  (self.t('material'), self.t('triangles'), self.t('uses'), self.t('note')), self.edit_material)
        self.build_adjust()
        self.build_preview()
        lg = ttk.Frame(self.nb)
        self.nb.add(lg, text=self.t('tab_log'))
        self.log = tk.Text(lg, wrap='none', font=('Consolas', 9))
        sb = ttk.Scrollbar(lg, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); self.log.pack(fill='both', expand=True)
        self.refresh()
        if os.path.isfile(os.path.join(self.work, 'previews', 'body.png')):
            self.nb.select(TAB_PREVIEW)
        self.load_view()
        c = self.proj.get('character')
        if c and self.proj.get('fbx') and os.path.isfile(os.path.join(self.work, 'out', c, c + '.oct'))                 and not self.proj.get('advanced'):         # measure it again for the tables and the Adjustments tab
            self.run(lambda: K.detect(self.work, self.proj, self.force, log=lambda *a: None),
                     lambda res: (setattr(self, 'tables', res[0]), setattr(self, 'info', res[1]), self.fill_tables()),
                     quiet=True)

    # ------------------------------------------------------------------ 3D preview
    def build_preview(self):
        """the Preview tab: the live 3D view (GPU) or the still images, a pose, the game's original beside it"""
        pv = ttk.Frame(self.nb)
        self.nb.add(pv, text=self.t('tab_preview'))
        gl = V.available()
        bar = ttk.Frame(pv, padding=(4, 4)); bar.pack(fill='x')
        self.pv_mode = tk.StringVar(value='3d' if gl else 'images')
        for val, key in (('3d', 'pv_3d'), ('images', 'pv_images'), ('weights', 'pv_weights'), ('joints', 'pv_joints')):
            rb = ttk.Radiobutton(bar, text=self.t(key), value=val, variable=self.pv_mode, style='Toolbutton',
                                 command=self.switch_preview)
            rb.pack(side='left')
            if val != 'images' and not gl:
                rb.state(['disabled'])
            if val == 'joints':
                self.rb_joints = rb
        ttk.Separator(bar, orient='vertical').pack(side='left', fill='y', padx=10)
        self.pose_var = tk.StringVar(value='down')
        for val, key in (('t', 'pv_tpose'), ('down', 'pv_armsdown')):
            ttk.Radiobutton(bar, text=self.t(key), value=val, variable=self.pose_var, style='Toolbutton',
                            command=self.live_pose).pack(side='left')
        self.ghost_on, self.bones_on = tk.BooleanVar(value=False), tk.BooleanVar(value=True)
        self.strain_on = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text=self.t('pv_side'), variable=self.ghost_on, command=self.view_flags).pack(side='left', padx=(12, 0))
        self.side_box = ttk.Combobox(bar, state='readonly', width=22,
                                     values=[self.t('pv_side_game'), self.t('pv_side_prev')])
        self.side_box.current(0)
        self.side_box.bind('<<ComboboxSelected>>', lambda e: (self.ghost_on.set(True), self.load_view(),
                                                              self.show_previews()))
        self.side_box.pack(side='left', padx=(2, 0))
        ttk.Checkbutton(bar, text=self.t('pv_bones'), variable=self.bones_on, command=self.view_flags).pack(side='left', padx=8)
        self.strain_cb = ttk.Checkbutton(bar, text=self.t('pv_strain'), variable=self.strain_on,
                                         command=lambda: self.live_pose())
        self.strain_cb.pack(side='left')
        if not gl:
            self.strain_cb.state(['disabled'])
        ttk.Label(pv, text=self.t('pv_help') if gl else self.t('pv_no_gl'), style='Muted.TLabel').pack(anchor='e', padx=6)
        self.wbar = ttk.Frame(pv, padding=(4, 0, 4, 4))           # shown in the weights mode
        ttk.Label(self.wbar, text=self.t('pv_weights_bone')).pack(side='left')
        self.wbone = tk.StringVar(value='Head')
        self.wbone_box = ttk.Combobox(self.wbar, textvariable=self.wbone, state='readonly', width=22)
        self.wbone_box.bind('<<ComboboxSelected>>', lambda e: self.live_pose())
        self.wbone_box.pack(side='left', padx=6)
        ttk.Label(self.wbar, text=self.t('pv_weights_help'), style='Muted.TLabel').pack(side='left', padx=8)
        self.jbar = ttk.Frame(pv, padding=(4, 0, 4, 4))           # shown in the joints mode
        self.mirror_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.jbar, text=self.t('joints_mirror'), variable=self.mirror_var,
                        command=lambda: setattr(self.view, 'mirror', bool(self.mirror_var.get()))).pack(side='left')
        ttk.Button(self.jbar, text=self.t('joints_reset'), command=self.reset_joints).pack(side='left', padx=10)
        ttk.Label(self.jbar, text=self.t('joints_help'), style='Hint.TLabel').pack(side='left', padx=6)
        self.pv_3d = tk.Label(pv, bg='#ebebeb', text=self.t('preview_empty'), font=('Segoe UI', 12))
        self.pv_imgs = ttk.Frame(pv)
        self.pv_body = ttk.Label(self.pv_imgs, text=self.t('preview_empty'), anchor='center')
        self.pv_body.pack(fill='both', expand=True)
        self.pv_face = ttk.Label(self.pv_imgs, anchor='center')
        self.pv_face.pack(fill='both', expand=True)
        self.pv_imgs.bind('<Configure>', lambda e: self.busy or self.show_previews())
        self.pv_bar = ttk.Progressbar(pv, mode='indeterminate', length=320)   # packed while converting
        self.view = V.View(self.pv_3d) if gl else None
        self.switch_preview()

    def switch_preview(self):
        for w in (self.pv_3d, self.pv_imgs, self.jbar, self.wbar):
            w.pack_forget()
        mode = self.pv_mode.get()
        if mode == 'joints' and not self.start_joints():
            mode = '3d' if self.view is not None else 'images'
            self.pv_mode.set(mode)
        if mode in ('3d', 'joints', 'weights') and self.view is not None:
            if mode == 'joints':
                self.jbar.pack(fill='x')
            elif mode == 'weights':
                self.wbar.pack(fill='x')
            elif self.view.on_joints is not None:                # back from the joints mode: the converted model
                self.view.on_joints, self.view.selected = None, None
                self.load_view()
            self.pv_3d.pack(fill='both', expand=True)
            if mode != 'joints':
                self.live_pose()                                 # its colours (weights, stretch)
            self.view.redraw()
        else:
            self.pv_imgs.pack(fill='both', expand=True)
            self.show_previews()

    def start_joints(self):
        """the joints mode: the model before converting with its skeleton (an OBJ's automatic one, an FBX's body
        joints as the Bones tab found them), the joints draggable"""
        c, model = self.proj.get('character'), self.proj.get('fbx') or ''
        if self.view is None or not model.lower().endswith(('.obj', '.fbx')):
            return False
        gdir = os.path.join(self.work, 'game', c or '-')
        if not c or not os.path.isfile(os.path.join(gdir, c + '.oct')):
            self.status.set(self.t('joints_need_convert'))
            return False
        if model.lower().endswith('.fbx') and not self.info:
            self.status.set(self.t('adj_need_info'))
            return False
        try:
            self.root.config(cursor='watch'); self.root.update_idletasks()
            if model.lower().endswith('.obj'):
                src = V.SourceModel(model, (gdir, c), self.proj.get('joints'), self.proj.get('textures'))
            else:
                src = V.SourceFBX(model, self.info['body'], self.proj.get('joints'), self.proj.get('textures'),
                                  self.proj.get('materials'))
        except Exception:
            print(traceback.format_exc())
            self.status.set(self.t('error'))
            return False
        finally:
            self.root.config(cursor='')
        self.view.on_joints, self.view.mirror, self.view.selected = self.joints_moved, bool(self.mirror_var.get()), None
        self.view.show_ghost, self.view.show_bones = False, True
        self.view.set_character(src)
        self.joint_keys = getattr(src, 'keys', None)        # an FBX's roles -> its bones
        self.joint_unit = src.unit                           # shown size -> the file's units
        self.status.set(self.t('joints_help'))
        return True

    def joints_moved(self, moved):
        keys = getattr(self, 'joint_keys', None) or {}
        u = getattr(self, 'joint_unit', 1.0)
        self.proj.setdefault('joints', {}).update({keys.get(k, k): [round(x / u, 5) for x in v]
                                                   for k, v in moved.items()})
        self.save_project()
        self.info = None
        self.status.set(self.t('joints_moved'))

    def reset_joints(self):
        self.proj.pop('joints', None)
        self.save_project()
        self.info = None
        if self.pv_mode.get() == 'joints':
            self.switch_preview()
        self.status.set(self.t('joints_back'))

    def views(self):
        return [v for v in (getattr(self, 'view', None), getattr(self, 'adj_view', None)) if v is not None]

    def release_views(self):
        for v in self.views():
            try:
                v.release()
            except Exception:
                pass
        self.view = self.adj_view = None
        self.ch = self.ghost_ch = None

    def load_view(self):
        """the converted character (and the game's original) into the 3D views, posed with the current choices"""
        self.ch = self.ghost_ch = None
        c = self.proj.get('character')
        out = os.path.join(self.work, 'out', c or '-')
        if not self.views():
            return
        if not c or not os.path.isfile(os.path.join(out, c + '.oct')):
            for v in self.views():
                v.set_character(None)
            return
        try:
            self.ch = V.Character(out, c)
            prev = getattr(self, 'side_box', None) is not None and self.side_box.current() == 1
            gdir = os.path.join(self.work, 'out_prev' if prev else 'game', c)    # beside it: the original or the last
            self.ghost_ch = V.Character(gdir, c) if os.path.isfile(os.path.join(gdir, c + '.oct')) else None
            self.strain = K.strain(self.work)
            if hasattr(self, 'wbone_box'):
                self.wbone_box.config(values=self.ch.names)
        except Exception:
            print('\n' + traceback.format_exc())
            self.ch = None
            return
        self.applied = json.loads(json.dumps(self.proj.get('adjust', {})))      # what out/ was converted with
        self.live_pose(new=True)

    PROPORTIONS = (('torso_x', 'adj_torso_w'), ('torso_y', 'adj_torso_h'), ('torso_z', 'adj_torso_d'),
                   ('head_pct', 'adj_head_size'), ('neck_pct', 'adj_neck_thick'), ('arms_pct', 'adj_arms_thick'),
                   ('legs_pct', 'adj_legs_thick'))
    PLACES = ('auto', 'hand_left', 'hand_right', 'head', 'chest', 'hips', 'out')

    def build_adjust(self):
        """the Adjustments tab: fine-tuning that is written into map.py (kit_project.json 'adjust', the same keys as
        'kit.py adjust'): head and proportions, accessories and clothes, eyes and face, weights; undo / redo and named
        versions; a live view of what can be shown without converting"""
        f = ttk.Frame(self.nb, padding=(16, 10))
        self.nb.add(f, text=self.t('tab_adjust'))
        f.columnconfigure(0, weight=2, uniform='adj'); f.columnconfigure(1, weight=1, uniform='adj')
        f.rowconfigure(1, weight=1)
        adj = self.proj.get('adjust', {})
        self._restoring = False
        top = ttk.Frame(f); top.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.btn_apply = ttk.Button(top, text=self.t('adj_apply'), style='Big.TButton', command=self.apply_adjust)
        self.btn_apply.pack(side='left')
        self.btn_undo = ttk.Button(top, text=self.t('adj_undo'), command=self.undo_adjust)
        self.btn_undo.pack(side='left', padx=(12, 4))
        self.btn_redo = ttk.Button(top, text=self.t('adj_redo'), command=self.redo_adjust)
        self.btn_redo.pack(side='left')
        ttk.Separator(top, orient='vertical').pack(side='left', fill='y', padx=12)
        ttk.Label(top, text=self.t('adj_versions')).pack(side='left')
        self.version_box = ttk.Combobox(top, state='readonly', width=16)
        self.version_box.pack(side='left', padx=6)
        ttk.Button(top, text=self.t('adj_load_version'), command=self.load_version).pack(side='left')
        ttk.Button(top, text=self.t('adj_save_version'), command=self.save_version).pack(side='left', padx=6)
        self.adj_note = ttk.Label(f, wraplength=700, style='Muted.TLabel')
        self.adj_nb = ttk.Notebook(f)
        self.adj_nb.grid(row=1, column=0, sticky='nsew', padx=(0, 14))

        # head and proportions
        body = ttk.Frame(self.adj_nb, padding=10)
        self.adj_nb.add(body, text=self.t('adj_page_body'))
        body.columnconfigure(0, weight=1, uniform='b'); body.columnconfigure(1, weight=1, uniform='b')
        left = ttk.Frame(body); left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        ttk.Label(left, text=self.t('adj_head_title'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(left, text=self.t('adj_help'), wraplength=320).pack(anchor='w', pady=(2, 8))
        self.adj_info = ttk.Label(left, wraplength=320, style='Hint.TLabel')
        self.adj_info.pack(anchor='w', pady=(0, 8))
        row = ttk.Frame(left); row.pack(anchor='w')
        ttk.Label(row, text=self.t('adj_height')).pack(side='left')
        self.head_cm = tk.DoubleVar(value=float(adj.get('head_cm', 0)))
        self.head_cm.trace_add('write', self.live_soon)          # the live view follows the slider
        tk.Scale(row, variable=self.head_cm, from_=-15, to=15, resolution=0.1, orient='horizontal', length=150,
                 showvalue=False).pack(side='left', padx=8)
        ttk.Label(row, textvariable=self.head_cm, width=5).pack(side='left')
        ttk.Label(row, text='cm').pack(side='left')
        b = ttk.Frame(left); b.pack(anchor='w', pady=(10, 0))
        self.btn_natural = ttk.Button(b, text=self.t('adj_natural'), command=self.natural_neck)
        self.btn_natural.pack(side='left')
        ttk.Button(b, text=self.t('adj_reset'), command=lambda: self.head_cm.set(0)).pack(side='left', padx=8)

        right = ttk.Frame(body); right.grid(row=0, column=1, sticky='nsew')
        ttk.Label(right, text=self.t('adj_prop_title'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(right, text=self.t('adj_prop_help'), wraplength=320).pack(anchor='w', pady=(2, 8))
        self.torso_info = ttk.Label(right, wraplength=320, style='Hint.TLabel')
        self.torso_info.pack(anchor='w', pady=(0, 6))
        grid = ttk.Frame(right); grid.pack(anchor='w')
        torso = adj.get('torso', [100, 100, 100])
        self.prop = {}
        for r, (key, label) in enumerate(self.PROPORTIONS):
            v = torso['xyz'.index(key[-1])] if key.startswith('torso') else adj.get(key, 100)
            self.prop[key] = tk.IntVar(value=int(round(float(v))))
            self.prop[key].trace_add('write', self.live_soon)
            ttk.Label(grid, text=self.t(label)).grid(row=r, column=0, sticky='w')
            tk.Scale(grid, variable=self.prop[key], from_=50, to=150, resolution=1, orient='horizontal', length=140,
                     showvalue=False).grid(row=r, column=1, padx=6, pady=1)
            ttk.Label(grid, textvariable=self.prop[key], width=4, anchor='e').grid(row=r, column=2, sticky='e')
            ttk.Label(grid, text='%').grid(row=r, column=3, sticky='w')
        ttk.Button(right, text=self.t('adj_prop_reset'),
                   command=lambda: [v.set(100) for v in self.prop.values()]).pack(anchor='w', pady=(6, 0))

        # accessories and clothes
        acc = ttk.Frame(self.adj_nb, padding=10)
        self.adj_nb.add(acc, text=self.t('adj_page_acc'))
        acc.columnconfigure(0, weight=3); acc.columnconfigure(1, weight=2); acc.rowconfigure(1, weight=1)
        self.adj_props = dict(adj.get('props', {}))
        self.adj_garments = dict(adj.get('garments', {}))
        ttk.Label(acc, text=self.t('adj_acc_help'), wraplength=360).grid(row=0, column=0, sticky='nw', padx=(0, 10))
        ttk.Label(acc, text=self.t('adj_garm_help'), wraplength=240).grid(row=0, column=1, sticky='nw')
        self.props_tv = self.small_table(acc, (('bone', 200), ('place', 170)), ('adj_bone', 'adj_place'), self.edit_prop)
        self.props_tv.master.grid(row=1, column=0, sticky='nsew', padx=(0, 10), pady=(6, 0))
        self.garm_tv = self.small_table(acc, (('mat', 170), ('pct', 70)), ('adj_material', 'adj_width'), self.edit_garment)
        self.garm_tv.master.grid(row=1, column=1, sticky='nsew', pady=(6, 0))

        # eyes and face
        face = ttk.Frame(self.adj_nb, padding=10)
        self.adj_nb.add(face, text=self.t('adj_page_face'))
        eo = adj.get('eyes_open') or {}
        ttk.Label(face, text=self.t('adj_eyes_title'), style='Head.TLabel').pack(anchor='w')
        self.eyes_on = tk.BooleanVar(value=bool(adj.get('eyes_open')))
        ttk.Checkbutton(face, text=self.t('adj_eyes_open'), variable=self.eyes_on).pack(anchor='w', pady=(4, 2))
        self.eye_top, self.eye_bot = tk.IntVar(value=int(eo.get('top', 15))), tk.IntVar(value=int(eo.get('bottom', 5)))
        for var, key in ((self.eye_top, 'adj_eye_top'), (self.eye_bot, 'adj_eye_bottom')):
            r = ttk.Frame(face); r.pack(anchor='w', padx=(22, 0))
            ttk.Label(r, text=self.t(key), width=18).pack(side='left')
            tk.Scale(r, variable=var, from_=0, to=45, resolution=1, orient='horizontal', length=160,
                     showvalue=False).pack(side='left', padx=6)
            ttk.Label(r, textvariable=var, width=3, anchor='e').pack(side='left')
            ttk.Label(r, text='°').pack(side='left')
        self.eyes_info = ttk.Label(face, wraplength=560, style='Hint.TLabel')
        self.eyes_info.pack(anchor='w', pady=(4, 14))
        ttk.Label(face, text=self.t('adj_face_title'), style='Head.TLabel').pack(anchor='w')
        self.face_on = tk.BooleanVar(value=bool(adj.get('face')))
        self.byface_on = tk.BooleanVar(value=bool(adj.get('head_by_face')))
        ttk.Checkbutton(face, text=self.t('adj_face'), variable=self.face_on).pack(anchor='w', pady=(4, 2))
        ttk.Checkbutton(face, text=self.t('adj_by_face'), variable=self.byface_on).pack(anchor='w', pady=2)
        self.face_info = ttk.Label(face, wraplength=560, style='Hint.TLabel')
        self.face_info.pack(anchor='w', pady=(4, 0))

        # weights
        wp = ttk.Frame(self.adj_nb, padding=10)
        self.adj_nb.add(wp, text=self.t('adj_page_weights'))
        wp.columnconfigure(0, weight=1); wp.rowconfigure(1, weight=1)
        self.adj_weights = dict(adj.get('weights', {}))
        ttk.Label(wp, text=self.t('adj_weights_help'), wraplength=600).grid(row=0, column=0, sticky='w')
        self.w_tv = self.small_table(wp, (('bone', 220), ('game', 220), ('how', 120)),
                                     ('adj_bone', 'adj_game_bone', 'adj_how'), self.edit_weight)
        self.w_tv.master.grid(row=1, column=0, sticky='nsew', pady=6)
        r = ttk.Frame(wp); r.grid(row=2, column=0, sticky='w')
        ttk.Label(r, text=self.t('adj_smooth')).pack(side='left')
        self.smooth_var = tk.IntVar(value=int(adj.get('smooth', 0)))
        tk.Scale(r, variable=self.smooth_var, from_=0, to=6, resolution=1, orient='horizontal', length=140,
                 showvalue=False).pack(side='left', padx=6)
        ttk.Label(r, textvariable=self.smooth_var, width=2).pack(side='left')
        ttk.Label(r, text=self.t('adj_smooth_help'), style='Muted.TLabel').pack(side='left', padx=6)
        for v in (self.eyes_on, self.eye_top, self.eye_bot, self.face_on, self.byface_on, self.smooth_var):
            v.trace_add('write', lambda *_: self.adj_touched())

        live = ttk.Frame(f); live.grid(row=0, column=1, rowspan=2, sticky='nsew')
        ttk.Label(live, text=self.t('adj_live'), style='Muted.TLabel', wraplength=320).pack(anchor='w', pady=(0, 4))
        self.adj_3d = tk.Label(live, bg='#ebebeb', text=self.t('preview_empty') if V.available() else self.t('pv_no_gl'),
                               wraplength=300)
        self.adj_3d.pack(fill='both', expand=True)
        self.adj_note.grid(row=2, column=0, sticky='w', pady=(6, 0))
        self.adj_view = V.View(self.adj_3d) if V.available() else None
        self.adj_hist, self.adj_pos, self._hist_job = [self.adjust_now()], 0, None
        self.fill_versions()

    def small_table(self, parent, cols, heads, on_edit):
        """a list with a scroll bar inside its own frame (tv.master), double click edits a row"""
        fr = ttk.Frame(parent)
        tv = ttk.Treeview(fr, columns=[c for c, _ in cols], show='headings', height=8)
        for (c, w), h in zip(cols, heads):
            tv.heading(c, text=self.t(h)); tv.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(fr, command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); tv.pack(fill='both', expand=True)
        tv.bind('<Double-1>', lambda e: on_edit(tv.focus()))
        return tv

    def adjust_now(self):
        """the Adjustments tab's values, in kit_project.json's 'adjust' form (neutral values left out)"""
        if not hasattr(self, 'prop'):
            return dict(self.proj.get('adjust', {}))
        adj = {}
        cm = round(float(self.head_cm.get()), 1)
        if cm:
            adj['head_cm'] = cm
        torso = [int(self.prop['torso_' + a].get()) for a in 'xyz']
        if torso != [100, 100, 100]:
            adj['torso'] = torso
        for key in ('head_pct', 'neck_pct', 'arms_pct', 'legs_pct'):
            if int(self.prop[key].get()) != 100:
                adj[key] = int(self.prop[key].get())
        for key, d in (('props', self.adj_props), ('garments', self.adj_garments), ('weights', self.adj_weights)):
            if d:
                adj[key] = json.loads(json.dumps(d))
        if self.eyes_on.get():
            adj['eyes_open'] = {'top': int(self.eye_top.get()), 'bottom': int(self.eye_bot.get())}
        if self.face_on.get():
            adj['face'] = True
        if self.byface_on.get():
            adj['head_by_face'] = True
        if int(self.smooth_var.get()):
            adj['smooth'] = int(self.smooth_var.get())
        return adj

    def set_adjust_ui(self, adj):
        """put an 'adjust' dict back into the tab's controls (undo, redo, a saved version)"""
        self._restoring = True
        try:
            self.head_cm.set(float(adj.get('head_cm', 0)))
            torso = adj.get('torso', [100, 100, 100])
            for key, _ in self.PROPORTIONS:
                self.prop[key].set(int(torso['xyz'.index(key[-1])] if key.startswith('torso') else adj.get(key, 100)))
            self.adj_props = dict(adj.get('props', {}))
            self.adj_garments = dict(adj.get('garments', {}))
            self.adj_weights = json.loads(json.dumps(adj.get('weights', {})))
            eo = adj.get('eyes_open') or {}
            self.eyes_on.set(bool(adj.get('eyes_open')))
            self.eye_top.set(int(eo.get('top', 15))); self.eye_bot.set(int(eo.get('bottom', 5)))
            self.face_on.set(bool(adj.get('face'))); self.byface_on.set(bool(adj.get('head_by_face')))
            self.smooth_var.set(int(adj.get('smooth', 0)))
        finally:
            self._restoring = False
        self.fill_adjust_lists()
        self.live_soon()

    # undo / redo: a snapshot of the tab after each change (a slider drag counts once)
    def adj_touched(self):
        if getattr(self, '_restoring', False) or not hasattr(self, 'adj_hist'):
            return
        if self._hist_job:
            self.root.after_cancel(self._hist_job)
        self._hist_job = self.root.after(500, self.record_adjust)

    def record_adjust(self):
        self._hist_job = None
        now = self.adjust_now()
        if now != self.adj_hist[self.adj_pos]:
            self.adj_hist = self.adj_hist[:self.adj_pos + 1] + [now]
            self.adj_pos = len(self.adj_hist) - 1
        self.undo_buttons()

    def undo_buttons(self):
        if hasattr(self, 'btn_undo') and self.btn_undo.winfo_exists():
            self.btn_undo.state(['!disabled'] if self.adj_pos > 0 else ['disabled'])
            self.btn_redo.state(['!disabled'] if self.adj_pos < len(self.adj_hist) - 1 else ['disabled'])

    def undo_adjust(self, step=-1):
        if not hasattr(self, 'adj_hist'):
            return
        if self._hist_job:
            self.root.after_cancel(self._hist_job)
            self.record_adjust()
        k = self.adj_pos + step
        if 0 <= k < len(self.adj_hist):
            self.adj_pos = k
            self.set_adjust_ui(self.adj_hist[k])
            self.status.set(self.t('adj_undone') if step < 0 else self.t('adj_redone'))
        self.undo_buttons()

    def redo_adjust(self):
        self.undo_adjust(+1)

    def undo_key(self, step):
        if self.screen == 'project' and hasattr(self, 'nb') and self.nb.winfo_exists() and \
                self.nb.index('current') == TAB_ADJUST and not isinstance(self.root.focus_get(), (tk.Entry, tk.Text)):
            self.undo_adjust(step)

    # named versions of the adjustments (kit_project.json 'adjust_versions', as 'kit.py adjust --save-version')
    def fill_versions(self):
        names = sorted(self.proj.get('adjust_versions', {}))
        self.version_box.config(values=names)
        if self.version_box.get() not in names:
            self.version_box.set(names[-1] if names else '')

    def save_version(self):
        name = simpledialog.askstring(TOOL, self.t('adj_version_name'), parent=self.root)
        if not name or not name.strip():
            return
        v = {'adjust': self.adjust_now()}
        if self.proj.get('joints'):
            v['joints'] = self.proj['joints']
        self.proj.setdefault('adjust_versions', {})[name.strip()] = v
        self.save_project()
        self.fill_versions(); self.version_box.set(name.strip())
        self.status.set(self.t('adj_version_saved') % name.strip())

    def load_version(self):
        name = self.version_box.get()
        v = self.proj.get('adjust_versions', {}).get(name)
        if not v:
            return
        if v.get('joints'):
            self.proj['joints'] = v['joints']
        else:
            self.proj.pop('joints', None)
        self.save_project()
        self.set_adjust_ui(v.get('adjust', {}))
        self.adj_touched()
        self.status.set(self.t('adj_version_loaded') % name)

    def live_pose(self, new=False):
        """pose the loaded character (T or arms down) with the Adjustments values shown live, and redraw"""
        self._live_job = None
        if getattr(self, 'ch', None) is None:
            return
        turns, shapes = V.live_adjust(self.ch, self.applied, self.adjust_now())
        down = getattr(self, 'pose_var', None) is not None and self.pose_var.get() == 'down'
        if down:
            turns = dict(V.ARMS_DOWN, **turns)
        self.ch.pose(turns, shapes)
        if self.ghost_ch is not None:
            self.ghost_ch.pose(V.ARMS_DOWN if down else None)
        self.colour_view()
        for v in self.views():
            if v.on_joints is not None:                          # the joints mode shows the model before converting
                continue
            if new:
                v.set_character(self.ch, self.ghost_ch)
                self.view_flags()
            else:
                v.update()

    def live_soon(self, *_):
        """a slider moved: show it in the 3D views shortly (not on every pixel of the drag)"""
        if getattr(self, '_live_job', None):
            self.root.after_cancel(self._live_job)
        self._live_job = self.root.after(30, self.live_pose)
        self.adj_touched()

    def colour_view(self):
        """the Preview's colours: one game bone's weights (Weights mode), or the stretched parts in red"""
        ch = getattr(self, 'ch', None)
        if ch is None or not hasattr(self, 'pv_mode'):
            return
        mode, k = 0, None
        if self.pv_mode.get() == 'weights':
            mode, k = 2, ch.bone_weight([self.wbone.get()])
        elif self.strain_on.get():
            mode, k = 1, ch.strain(getattr(self, 'strain', {}))
        ch.K = k
        if self.view is not None:
            self.view.colour_mode = mode

    def view_flags(self):
        """the Preview tab's choices; the Adjustments tab's live view shows only the character"""
        for v in self.views():
            if v.on_joints is not None:
                continue
            main = v is getattr(self, 'view', None)
            v.show_ghost = main and hasattr(self, 'ghost_on') and bool(self.ghost_on.get())
            v.show_bones = main and (not hasattr(self, 'bones_on') or bool(self.bones_on.get()))
            v.redraw()

    def fill_adjust(self):
        if not hasattr(self, 'adj_info') or not self.adj_info.winfo_exists():
            return
        nf = self.info.get('neck') if self.info else None
        if nf:
            char = dict(MAIN).get(self.proj.get('character'), self.proj.get('character'))
            self.adj_info.config(text=self.t('adj_info') % (nf['model_cm'], char, nf['game_cm'], nf['stretch']))
            self.btn_natural.config(text=self.t('adj_natural') + ' (%+.1f cm)' % nf['natural_cm'])
        else:
            self.adj_info.config(text=self.t('adj_none'))
            self.btn_natural.config(text=self.t('adj_natural'))
        tf = self.info.get('torso') if self.info else None
        self.torso_info.config(text=self.t('adj_torso_info') % (tf.get('width_pct', 100), tf.get('height_pct', 100))
                               if tf else '')
        self.adj_note.config(text=self.t('advanced_note') if self.proj.get('advanced') else '')
        for w in (self.btn_natural, self.btn_apply):
            w.state(['disabled'] if self.proj.get('advanced') or self.busy else ['!disabled'])
        self.fill_adjust_lists()
        self.undo_buttons()

    def fill_adjust_lists(self):
        """the accessories, clothes and weights lists, and what was found for the eyes and face"""
        if not hasattr(self, 'props_tv') or not self.props_tv.winfo_exists():
            return
        for tv in (self.props_tv, self.garm_tv, self.w_tv):
            tv.delete(*tv.get_children())
        info, tables = self.info, self.tables
        if not info or not tables:
            for tv in (self.props_tv, self.garm_tv, self.w_tv):
                tv.insert('', 'end', iid='-', values=(self.t('adj_need_info'),))
            self.eyes_info.config(text=self.t('adj_need_info')); self.face_info.config(text='')
            return
        W = tables['WEIGHTS']
        places = self.t('places')
        for k, bone in enumerate(info.get('extras', [])):
            p = self.adj_props.get(bone)
            self.props_tv.insert('', 'end', iid='p%d' % k, values=(bone, places[p] if p else
                                 self.t('adj_auto_place') % self.weight_text(W.get(bone))))
        skip = set(tables.get('SKIP_MATERIALS', []))
        for k, mat in enumerate(m for m in tables.get('_tex_tris', {}) if m not in skip):
            self.garm_tv.insert('', 'end', iid='g%d' % k, values=(mat, '%d %%' % int(self.adj_garments.get(mat, 100))))
        notes = info.get('notes', {})
        for k, bone in enumerate(sorted(W, key=str.lower)):
            mine = bone in self.adj_weights
            self.w_tv.insert('', 'end', iid='w%d' % k, values=(bone, self.weight_text(self.adj_weights[bone] if mine
                             else W[bone]), self.t('adj_by_hand') if mine else notes.get(bone, self.t('auto'))))
        eyes = info.get('eyes') or {}
        self.eyes_info.config(text=self.t('adj_eyes_found') % ', '.join('%s (%d + %d)' % (e, len(t), len(b))
                              for e, t, b in eyes.values()) if eyes else self.t('adj_eyes_none'))
        face = info.get('face') or {}
        self.face_info.config(text=self.t('adj_face_found') % ', '.join(sorted(face.values())) if face else
                              self.t('adj_face_none'))

    @staticmethod
    def weight_text(w):
        if isinstance(w, dict):
            return ' + '.join('%s %d%%' % (b, round(s * 100)) for b, s in w.items())
        return w or '-'

    def game_bones(self):
        """the game character's bone names (for the weights dialog)"""
        c = self.proj.get('character')
        try:
            _, bones3, *_ = AM.T.load(os.path.join(self.work, 'game', c, c + '.oct'))
            return [b['name'] for b in bones3]
        except Exception:
            return []

    def edit_prop(self, iid):
        if not iid or iid == '-':
            return
        bone = self.props_tv.set(iid, 'bone')
        places = self.t('places')
        d, f = self.dialog(bone)
        ttk.Label(f, text=self.t('adj_place')).pack(anchor='w')
        v = tk.StringVar(value=self.adj_props.get(bone, 'auto'))
        for key in self.PLACES:
            ttk.Radiobutton(f, text=places[key], value=key, variable=v).pack(anchor='w', pady=1)

        def done():
            if v.get() == 'auto':
                self.adj_props.pop(bone, None)
            else:
                self.adj_props[bone] = v.get()
            d.destroy()
            self.fill_adjust_lists(); self.adj_touched()
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=done).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)

    def edit_garment(self, iid):
        if not iid or iid == '-':
            return
        mat = self.garm_tv.set(iid, 'mat')
        d, f = self.dialog(mat)
        ttk.Label(f, text=self.t('adj_garm_help'), wraplength=320).pack(anchor='w')
        v = tk.IntVar(value=int(self.adj_garments.get(mat, 100)))
        r = ttk.Frame(f); r.pack(anchor='w', pady=8)
        tk.Scale(r, variable=v, from_=50, to=150, resolution=1, orient='horizontal', length=220,
                 showvalue=False).pack(side='left')
        ttk.Label(r, textvariable=v, width=4, anchor='e').pack(side='left')
        ttk.Label(r, text='%').pack(side='left')

        def done(val):
            if val == 100:
                self.adj_garments.pop(mat, None)
            else:
                self.adj_garments[mat] = val
            d.destroy()
            self.fill_adjust_lists(); self.adj_touched()
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=lambda: done(int(v.get()))).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)
        ttk.Button(bf, text=self.t('back_auto'), command=lambda: done(100)).pack(side='left')

    def edit_weight(self, iid):
        if not iid or iid == '-':
            return
        bone = self.w_tv.set(iid, 'bone')
        names = self.game_bones()
        if not names:
            return
        cur = self.adj_weights.get(bone) or self.tables['WEIGHTS'].get(bone)
        items = list(cur.items()) if isinstance(cur, dict) else [(cur, 1.0)]
        d, f = self.dialog(bone)
        a = tk.StringVar(value=items[0][0] if items[0][0] in names else names[0])
        b = tk.StringVar(value=items[1][0] if len(items) > 1 else '')
        share = tk.IntVar(value=int(round(items[0][1] * 100)) if len(items) > 1 else 100)
        ttk.Label(f, text=self.t('adj_weight_first')).pack(anchor='w')
        ttk.Combobox(f, textvariable=a, values=names, width=36, state='readonly').pack(fill='x', pady=(2, 8))
        ttk.Label(f, text=self.t('adj_weight_second')).pack(anchor='w')
        ttk.Combobox(f, textvariable=b, values=[''] + names, width=36, state='readonly').pack(fill='x', pady=(2, 8))
        r = ttk.Frame(f); r.pack(anchor='w')
        ttk.Label(r, text=self.t('adj_weight_share')).pack(side='left')
        tk.Scale(r, variable=share, from_=0, to=100, resolution=5, orient='horizontal', length=160,
                 showvalue=False).pack(side='left', padx=6)
        ttk.Label(r, textvariable=share, width=4, anchor='e').pack(side='left')
        ttk.Label(r, text='%').pack(side='left')

        def done(auto=False):
            if auto:
                self.adj_weights.pop(bone, None)
            elif b.get() and b.get() != a.get() and share.get() < 100:
                self.adj_weights[bone] = {a.get(): share.get() / 100, b.get(): 1 - share.get() / 100}
            else:
                self.adj_weights[bone] = a.get()
            d.destroy()
            self.fill_adjust_lists(); self.adj_touched()
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=done).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)
        ttk.Button(bf, text=self.t('back_auto'), command=lambda: done(True)).pack(side='left')

    def natural_neck(self):
        nf = self.info.get('neck') if self.info else None
        if nf:
            self.head_cm.set(nf['natural_cm'])

    def apply_adjust(self):
        """the tab's values into the project ('adjust'; only what isn't at its neutral value), then convert"""
        adj = self.adjust_now()
        if adj:
            self.proj['adjust'] = adj
        else:
            self.proj.pop('adjust', None)
        self.save_project()
        self.info = None                                  # measured again after the conversion
        self.convert()

    def fill_others(self):
        if not hasattr(self, 'other_box') or not self.other_box.winfo_exists():
            return
        main = {c for c, _ in MAIN}
        self.other_box.config(values=[c for c in self.chars if c not in main])
        cur = self.proj.get('character')
        self.other_box.set(cur if cur and cur not in main else '')

    def refresh(self):
        """labels, buttons and the next-step hint from the project's state"""
        self.refresh_mod_controls()
        if not hasattr(self, 'hint') or not self.hint.winfo_exists():
            return
        p = self.proj
        model = p.get('fbx')
        self.model_lbl.config(text=os.path.basename(model) if model else self.t('no_model'))
        self.tex_lbl.config(text=self.t('textures') % (p.get('textures') or self.t('no_textures')))
        self.obj_lbl.config(text=self.t('obj_note') if model and model.lower().endswith('.obj') else '')
        if getattr(self, 'rb_joints', None) is not None and self.rb_joints.winfo_exists():
            self.rb_joints.state(['!disabled'] if model and model.lower().endswith(('.obj', '.fbx')) and V.available()
                                 else ['disabled'])
        c = p.get('character')
        converted = bool(c) and os.path.isfile(os.path.join(self.work, 'out', c, c + '.oct'))
        can = bool(c and model)
        if not self.busy:
            for b, ok in ((self.btn_convert, can), (self.btn_analyze, can), (self.btn_install, converted),
                          (self.btn_export, converted), (self.btn_restore, bool(c))):
                b.state(['!disabled'] if ok else ['disabled'])
        self.hint.config(text=self.t('next_char') if not c else self.t('next_model') if not model else
                         self.t('next_look') if converted else self.t('next_convert'))
        self.fill_tables()

    def char_chosen(self):
        c = self.char.get()
        if c and c != self.proj.get('character'):
            self.proj['character'] = c
            self.proj.pop('bones', None)
            self.info = self.tables = None
            self.save_project()
        self.fill_others()
        self.refresh()

    def browse_model(self):
        f = filedialog.askopenfilename(title=self.t('pick_model'),
                                       filetypes=[('FBX / OBJ', '*.fbx *.FBX *.obj *.OBJ'), ('*', '*.*')])
        if f:
            self.proj['fbx'] = os.path.abspath(f)
            tex = K.guess_textures(f)
            if tex:
                self.proj['textures'] = tex
            for k in ('bones', 'materials'):
                self.proj.pop(k, None)
            self.info = self.tables = None
            self.save_project()
            self.refresh()

    def browse_textures(self):
        d = filedialog.askdirectory(title=self.t('change_textures'))
        if d:
            self.proj['textures'] = os.path.abspath(d)
            self.proj.pop('materials', None)
            self.tables = None
            self.save_project()
            self.refresh()

    def save_project(self):
        if self.work:
            K.save_project(self.work, self.proj)

    def toggle_advanced(self):
        self.proj['advanced'] = self.adv.get()
        self.save_project()
        if self.adv.get():
            self.status.set(self.t('advanced_note'))

    def ready(self):
        if not self.proj.get('game') and not self.settings.get('game'):
            messagebox.showinfo(TOOL, self.t('no_game_first')); return False
        self.proj.setdefault('game', self.settings.get('game'))
        return bool(self.proj.get('character') and self.proj.get('fbx'))

    # ------------------------------------------------------------------ actions
    def analyze(self):
        if self.ready():
            self.run(lambda: K.detect(self.work, self.proj, self.force), self.analyzed, retry=self.analyze)

    def analyzed(self, res):
        self.tables, self.info = res
        self.refresh()
        self.nb.select(0)
        self.status.set(self.t('analyzed'))

    def convert(self):
        if not self.ready():
            return
        mpath = os.path.join(self.work, 'map.py')
        remap = not self.proj.get('advanced')
        if remap and os.path.isfile(mpath) and self.proj.get('map_md5') and md5(mpath) != self.proj['map_md5']:
            if not messagebox.askyesno(TOOL, self.t('hand_edited')):
                remap = False
                self.adv.set(True); self.toggle_advanced()

        def job():
            check = K.build(self.work, self.proj, remap, self.force)
            if remap:
                self.proj['map_md5'] = md5(mpath)
                self.save_project()
            return check
        self.run(job, self.converted, retry=self.convert, preview=True)

    def converted(self, check):
        self.refresh()
        self.show_previews()
        if getattr(self, 'pv_mode', None) is not None and self.pv_mode.get() == 'joints':
            self.pv_mode.set('3d')                               # the converted result, with the moved joints
            self.view.on_joints, self.view.selected = None, None
            self.switch_preview()
        self.load_view()
        self.nb.select(TAB_PREVIEW)
        self.status.set(self.t('check') % ', '.join(check) if check else self.t('converted'))
        if self.info is None and not self.proj.get('advanced'):
            self.run(lambda: K.detect(self.work, self.proj, self.force, log=lambda *a: None),
                     lambda res: (setattr(self, 'tables', res[0]), setattr(self, 'info', res[1]), self.fill_tables()),
                     quiet=True)

    def install(self):
        if self.ready() and messagebox.askyesno(TOOL, self.t('confirm_install') % self.proj['character']):
            self.run(lambda: K.install_project(self.work),
                     lambda c: messagebox.showinfo(TOOL, self.t('installed') % c))

    def restore(self):
        if self.ready():
            self.run(lambda: K.restore_project(self.work),
                     lambda c: messagebox.showinfo(TOOL, self.t('restored') % c))

    def export(self):
        if not self.ready():
            return
        d, f = self.dialog(self.t('export'))
        last = self.proj.get('pack', {})
        fields = {}
        for k, default in (('pack_name', ''), ('version', '1.0'), ('author', ''), ('what', ''), ('model_credits', '')):
            ttk.Label(f, text=self.t(k)).pack(anchor='w')
            v = tk.StringVar(value=last.get(k, default))
            ttk.Entry(f, textvariable=v, width=60).pack(fill='x', pady=(0, 6))
            fields[k] = v
        inst = tk.BooleanVar(value=bool(last.get('installer')))
        ttk.Checkbutton(f, text=self.t('exp_installer'), variable=inst).pack(anchor='w', pady=(4, 0))
        ttk.Label(f, text=self.t('exp_installer_note'), wraplength=420, style='Muted.TLabel').pack(anchor='w', padx=(20, 0))
        ttk.Label(f, text=self.t('rights'), wraplength=420, foreground='#a04000').pack(anchor='w', pady=(4, 0))

        def go():
            vals = {k: v.get() for k, v in fields.items()}
            vals['installer'] = bool(inst.get())
            self.proj['pack'] = vals
            self.save_project()
            d.destroy()
            self.run(lambda: K.export_pack(self.work, vals['pack_name'], vals['version'], vals['author'],
                                           vals['what'], vals['model_credits'], vals['installer']),
                     lambda res: (messagebox.showinfo(TOOL, self.t('exported') % res[1]), self.open_path(os.path.dirname(res[1]))))
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=go).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)

    # ------------------------------------------------------------------ tables
    def table(self, title, cols, heads, on_edit):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=title)
        tv = ttk.Treeview(f, columns=[c for c, _ in cols], show='headings')
        for (c, w), h in zip(cols, heads):
            tv.heading(c, text=h); tv.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(f, command=tv.yview)
        tv.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); tv.pack(fill='both', expand=True)
        tv.bind('<Double-1>', lambda e: on_edit(tv.focus()))
        return tv

    def fill_tables(self):
        if not hasattr(self, 'bones_tv') or not self.bones_tv.winfo_exists():
            return
        for tv in (self.bones_tv, self.mats_tv):
            tv.delete(*tv.get_children())
        self.fill_adjust()
        if not self.info:
            return
        body, chosen = self.info['body'], self.proj.get('bones', {})
        for role in AM.ROLES:
            v = body.get(role)
            if role == 'neck':
                v = v[0] if v else None
            self.bones_tv.insert('', 'end', iid=role, values=(self.role_label(role), v or self.t('none'),
                                                              self.t('chosen') if role in chosen else self.t('auto')))
        notes, tris = self.tables.get('_tex_notes', {}), self.tables.get('_tex_tris', {})
        sets = self.tables.get('TEXTURES', {})
        for mat in tris:
            v = self.tables['MATERIALS'].get(mat)
            uses = self.t('skip') if v is None else sets[v]['d'] if isinstance(v, str) else 'RGB %s' % (v,)
            self.mats_tv.insert('', 'end', iid='m' + str(len(self.mats_tv.get_children())),
                                values=(mat, tris[mat], uses, self.t('notes').get(notes.get(mat, ''), notes.get(mat, ''))))

    def dialog(self, title):
        """a small window over the middle of the main one (once its contents are in)"""
        d = tk.Toplevel(self.root)
        d.withdraw()
        d.title(title); d.transient(self.root)
        f = ttk.Frame(d, padding=14); f.pack(fill='both', expand=True)

        def centre():
            d.update_idletasks()
            r = self.root
            x = r.winfo_rootx() + (r.winfo_width() - d.winfo_reqwidth()) // 2
            y = r.winfo_rooty() + (r.winfo_height() - d.winfo_reqheight()) // 3
            d.geometry('+%d+%d' % (max(0, x), max(0, y)))
            d.deiconify(); d.grab_set(); d.focus_set()
        d.after(0, centre)
        return d, f

    def edit_bone(self, role):
        if not role or not self.info:
            return
        bones = sorted(self.info['skeleton'].skinned, key=str.lower)
        if role in OPTIONAL:
            bones = [self.t('none')] + bones
        d, f = self.dialog(self.role_label(role))
        v = tk.StringVar(value=self.bones_tv.set(role, 'bone'))
        ttk.Label(f, text=self.t('model_bone')).pack(anchor='w')
        ttk.Combobox(f, textvariable=v, values=bones, width=45, state='readonly').pack(fill='x', pady=6)

        def done(val):
            ch = self.proj.setdefault('bones', {})
            if val is None:
                ch.pop(role, None)
            else:
                ch[role] = '' if val == self.t('none') else val
            d.destroy()
            self.save_project()
            self.analyze()
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=lambda: done(v.get())).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)
        ttk.Button(bf, text=self.t('back_auto'), command=lambda: done(None)).pack(side='left')

    def edit_material(self, iid):
        if not iid or not self.tables:
            return
        mat = self.mats_tv.set(iid, 'mat')
        tex = self.proj.get('textures')
        imgs = sorted(fn for fn in os.listdir(tex) if fn.lower().endswith(K.IMAGES)) if tex and os.path.isdir(tex) else []
        d, f = self.dialog(mat)
        mode = tk.StringVar(value='image')
        img = tk.StringVar(value=imgs[0] if imgs else '')
        col = [None]
        ttk.Radiobutton(f, text=self.t('image'), variable=mode, value='image').pack(anchor='w')
        ttk.Combobox(f, textvariable=img, values=imgs, width=45, state='readonly').pack(fill='x', padx=(20, 0), pady=4)
        ttk.Radiobutton(f, text=self.t('colour'), variable=mode, value='colour').pack(anchor='w')

        def pick():
            c = colorchooser.askcolor(parent=d)[0]
            if c:
                col[0] = [int(x) for x in c]; mode.set('colour')
        ttk.Button(f, text=self.t('pick_colour'), command=pick).pack(anchor='w', padx=(20, 0), pady=4)
        ttk.Radiobutton(f, text=self.t('skip'), variable=mode, value='skip').pack(anchor='w')

        def done(auto=False):
            ch = self.proj.setdefault('materials', {})
            if auto:
                ch.pop(mat, None)
            elif mode.get() == 'image' and img.get():
                ch[mat] = img.get()
            elif mode.get() == 'colour' and col[0]:
                ch[mat] = col[0]
            elif mode.get() == 'skip':
                ch[mat] = 'skip'
            d.destroy()
            self.save_project()
            self.analyze()
        bf = ttk.Frame(f); bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text=self.t('ok'), command=done).pack(side='right')
        ttk.Button(bf, text=self.t('cancel'), command=d.destroy).pack(side='right', padx=6)
        ttk.Button(bf, text=self.t('back_auto'), command=lambda: done(True)).pack(side='left')

    # ------------------------------------------------------------------ previews
    def show_previews(self):
        if not hasattr(self, 'pv_body') or not self.pv_body.winfo_exists():
            return
        self.photos = []
        side_prev = getattr(self, 'side_box', None) is not None and self.side_box.current() == 1 and \
            os.path.isfile(os.path.join(self.work, 'previews', 'compare.png'))
        paths_ = [os.path.join(self.work, 'previews', n) for n in ('compare.png' if side_prev else 'body.png',
                                                                   'face.png')]
        if not os.path.isfile(paths_[0]):
            self.pv_body.config(image='', text=self.t('preview_empty')); self.pv_face.config(image='')
            return
        w = max(200, self.nb.winfo_width() - 20)
        h = max(150, (self.nb.winfo_height() - 40) // 2)
        for lbl, p in zip((self.pv_body, self.pv_face), paths_):
            if not os.path.isfile(p):
                continue
            im = Image.open(p)
            k = min(w / im.width, h / im.height)
            ph = ImageTk.PhotoImage(im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS))
            self.photos.append(ph)
            lbl.config(image=ph, text='')

    # ------------------------------------------------------------------ work in the background
    def run(self, fn, done, retry=None, quiet=False, on_error=None, preview=False):
        """fn in a thread, then done(result) here. While it runs: buttons off, the spinner in the status bar, and
        (preview) the Preview tab says it is being drawn, with its own moving bar"""
        if self.busy:
            return
        self.busy = True
        for b in self.buttons:
            b.state(['disabled'])
        if not quiet:
            self.status.set(self.t('working'))
            self.spinner.pack(side='right', padx=8, pady=2)
            self.spinner.start(12)
            if hasattr(self, 'nb') and self.nb.winfo_exists():
                self.nb.select(TAB_PREVIEW if preview else TAB_LOG)
                if preview:
                    self.photos = []
                    self.pv_body.config(image='', text=self.t('drawing'), font=('Segoe UI', 12))
                    self.pv_face.config(image='')
                    for v in self.views():               # the 3D views show the same note until the new model
                        v.set_character(None)
                        v.label.config(text=self.t('drawing'))
                    self.pv_bar.pack(pady=(0, 40)); self.pv_bar.start(12)

        def work():
            try:
                self.q.put(('done', (done, fn())))
            except K.KitError as e:
                self.q.put(('kiterror', (str(e), retry, quiet, on_error)))
            except BaseException as e:            # SystemExit too: the converter stops with one
                self.q.put(('error', (str(e) or type(e).__name__, traceback.format_exc(), quiet, on_error)))
        threading.Thread(target=work, daemon=True).start()

    def stop_spinners(self):
        self.spinner.stop(); self.spinner.pack_forget()
        if hasattr(self, 'pv_bar') and self.pv_bar.winfo_exists():
            self.pv_bar.stop(); self.pv_bar.pack_forget()
            if not self.photos:
                self.show_previews()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == 'drop':
                    self.dropped(val)
                    continue
                if kind == 'log':
                    if hasattr(self, 'log') and self.log.winfo_exists():
                        self.log.insert('end', val); self.log.see('end')
                    continue
                self.busy = False
                self.stop_spinners()
                if kind == 'done':
                    val[0](val[1])
                elif kind == 'kiterror':
                    msg, retry, quiet, on_error = val
                    self.status.set(msg)
                    if on_error:
                        on_error(msg)
                    elif quiet:
                        print('\n' + msg)
                    elif 'not the game\'s original' in msg and retry and not self.force:
                        if messagebox.askyesno(TOOL, self.t('not_original') % msg):
                            self.force = True
                            retry()
                    else:
                        messagebox.showerror(self.t('error'), msg)
                else:
                    msg, tb, quiet, on_error = val
                    print('\n' + tb)                      # the whole story goes to the Log tab
                    if on_error:
                        on_error(msg)
                    elif not quiet:
                        self.status.set(msg)
                        messagebox.showerror(self.t('error'), '%s\n\n%s' % (msg, self.t('see_log')))
                if not self.busy:
                    for b in self.buttons:
                        b.state(['!disabled'])
                    self.refresh()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    # ------------------------------------------------------------------ misc
    def open_path(self, p):
        if os.path.exists(p):
            os.startfile(p)

    def about(self):
        messagebox.showinfo(self.t('about'), self.t('about_text') % (CREDIT, AUTHOR, AUTHOR))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('characters', 'doctor', 'make', 'install', 'restore', 'export', 'mods'):
        # '<tool>.exe make <project> ...': kit.py's commands without Python. The .exe has no console, so what they print
        # goes to %TEMP%\<tool>.log (make also writes <project>\report.txt)
        if sys.stdout is None:
            sys.stdout = sys.stderr = open(os.path.join(os.environ.get('TEMP', '.'), TOOL + '.log'), 'w', encoding='utf-8')
        raise SystemExit(K.main(sys.argv[1:]))
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
