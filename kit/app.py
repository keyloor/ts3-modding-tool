"""Toy Story 3 Modding Tool: the window. python app.py

A start screen (the game, found through Steam; the workspace folder; the tool's sections and recent projects), then a
character project in four steps: pick the character, pick the model (FBX or OBJ), convert and check, play or share.
It only calls kit.py's functions; the work runs in a thread and what it prints goes to the Log tab.
"""
import hashlib, json, os, queue, re, sys, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import paths
from about import CREDIT, TOOL, VERSION, AUTHOR
import automap as AM
import kit as K
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
        self.chars = []
        self.photos = []
        self.game_state = 'looking'
        root.title('%s %s — %s' % (TOOL, VERSION, AUTHOR))
        root.geometry('1180x860')
        self.styles()
        self.screen = 'home'
        self.build()
        self.look_for_game(self.settings.get('game'))
        root.after(100, self.poll)

    # ------------------------------------------------------------------ settings, texts, styles
    def load_settings(self):
        for p in (SETTINGS, OLD_SETTINGS):
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
        for w in self.root.winfo_children():
            w.destroy()
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label=self.t('home_menu'), command=self.show_home)
        fm.add_command(label=self.t('new_project'), command=self.new_project)
        fm.add_command(label=self.t('open_other'), command=self.open_other)
        fm.add_separator(); fm.add_command(label=self.t('quit'), command=self.root.destroy)
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
        (self.build_project if self.screen == 'project' and self.work else self.build_home)()

    def clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        self.buttons = []
        for k in ('bones_tv', 'mats_tv', 'pv_body', 'log', 'nb'):
            self.__dict__.pop(k, None)

    def set_lang(self, lang):
        self.lang = lang
        self.save_settings()
        self.build()

    # ------------------------------------------------------------------ start screen
    def show_home(self):
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
        c.grid(row=0, column=0, rowspan=2, sticky='nsew', padx=(0, 12))
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
        for r, (k, d) in enumerate((('mod_music', 'mod_music_desc'), ('mod_tex', 'mod_tex_desc'))):
            s = ttk.Frame(cards, style='Card.TFrame', padding=16)
            s.grid(row=r, column=1, sticky='nsew', pady=(0, 12) if r == 0 else 0)
            ttk.Label(s, text=self.t(k), style='Head.TLabel', foreground='#888888').pack(anchor='w')
            ttk.Label(s, text=self.t(d), style='Muted.TLabel').pack(anchor='w', pady=(2, 6))
            ttk.Label(s, text=self.t('soon'), style='Muted.TLabel').pack(anchor='w')

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

        def failed(msg):
            self.game_state = 'missing'
            self.settings.pop('game', None)
            self.show_game()
        self.run(job, done, quiet=True, on_error=failed)

    def browse_game(self):
        d = filedialog.askdirectory(title=self.t('find_game'))
        if d:
            self.look_for_game(d)

    def browse_workspace(self):
        d = filedialog.askdirectory(title=self.t('workspace') % '')
        if d:
            self.settings['workspace'] = d
            self.save_settings()
            self.show_home()

    def new_project(self):
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
        d = filedialog.askdirectory(title=self.t('open_other'), initialdir=self.settings['workspace'])
        if d:
            self.open_project(d)

    # ------------------------------------------------------------------ project screen
    def open_project(self, d):
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
        pv = ttk.Frame(self.nb)
        self.nb.add(pv, text=self.t('tab_preview'))
        self.pv_body = ttk.Label(pv, text=self.t('preview_empty'), anchor='center')
        self.pv_body.pack(fill='both', expand=True)
        self.pv_face = ttk.Label(pv, anchor='center')
        self.pv_face.pack(fill='both', expand=True)
        self.pv_bar = ttk.Progressbar(pv, mode='indeterminate', length=320)   # packed while converting
        pv.bind('<Configure>', lambda e: self.busy or self.show_previews())
        lg = ttk.Frame(self.nb)
        self.nb.add(lg, text=self.t('tab_log'))
        self.log = tk.Text(lg, wrap='none', font=('Consolas', 9))
        sb = ttk.Scrollbar(lg, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); self.log.pack(fill='both', expand=True)
        self.refresh()
        if os.path.isfile(os.path.join(self.work, 'previews', 'body.png')):
            self.nb.select(TAB_PREVIEW)

    PROPORTIONS = (('torso_x', 'adj_torso_w'), ('torso_y', 'adj_torso_h'), ('torso_z', 'adj_torso_d'),
                   ('head_pct', 'adj_head_size'), ('neck_pct', 'adj_neck_thick'), ('arms_pct', 'adj_arms_thick'),
                   ('legs_pct', 'adj_legs_thick'))

    def build_adjust(self):
        """the Adjustments tab: fine-tuning that is written into map.py (head and neck, proportions; PLAN.md's roadmap
        has the rest)"""
        f = ttk.Frame(self.nb, padding=16)
        self.nb.add(f, text=self.t('tab_adjust'))
        f.columnconfigure(0, weight=1, uniform='adj'); f.columnconfigure(1, weight=1, uniform='adj')
        adj = self.proj.get('adjust', {})
        top = ttk.Frame(f); top.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        self.btn_apply = ttk.Button(top, text=self.t('adj_apply'), style='Big.TButton', command=self.apply_adjust)
        self.btn_apply.pack(side='left')
        self.adj_note = ttk.Label(top, wraplength=700, style='Muted.TLabel')
        self.adj_note.pack(side='left', padx=14)

        left = ttk.Frame(f); left.grid(row=1, column=0, sticky='nsew', padx=(0, 16))
        ttk.Label(left, text=self.t('adj_head_title'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(left, text=self.t('adj_help'), wraplength=500).pack(anchor='w', pady=(2, 8))
        self.adj_info = ttk.Label(left, wraplength=500, style='Hint.TLabel')
        self.adj_info.pack(anchor='w', pady=(0, 8))
        row = ttk.Frame(left); row.pack(anchor='w')
        ttk.Label(row, text=self.t('adj_height')).pack(side='left')
        self.head_cm = tk.DoubleVar(value=float(adj.get('head_cm', 0)))
        tk.Scale(row, variable=self.head_cm, from_=-15, to=15, resolution=0.1, orient='horizontal', length=260,
                 showvalue=False).pack(side='left', padx=10)
        ttk.Label(row, textvariable=self.head_cm, width=5).pack(side='left')
        ttk.Label(row, text='cm').pack(side='left')
        b = ttk.Frame(left); b.pack(anchor='w', pady=(10, 0))
        self.btn_natural = ttk.Button(b, text=self.t('adj_natural'), command=self.natural_neck)
        self.btn_natural.pack(side='left')
        ttk.Button(b, text=self.t('adj_reset'), command=lambda: self.head_cm.set(0)).pack(side='left', padx=8)

        right = ttk.Frame(f); right.grid(row=1, column=1, sticky='nsew')
        ttk.Label(right, text=self.t('adj_prop_title'), style='Head.TLabel').pack(anchor='w')
        ttk.Label(right, text=self.t('adj_prop_help'), wraplength=500).pack(anchor='w', pady=(2, 8))
        self.torso_info = ttk.Label(right, wraplength=500, style='Hint.TLabel')
        self.torso_info.pack(anchor='w', pady=(0, 6))
        grid = ttk.Frame(right); grid.pack(anchor='w')
        torso = adj.get('torso', [100, 100, 100])
        self.prop = {}
        for r, (key, label) in enumerate(self.PROPORTIONS):
            v = torso['xyz'.index(key[-1])] if key.startswith('torso') else adj.get(key, 100)
            self.prop[key] = tk.IntVar(value=int(round(float(v))))
            ttk.Label(grid, text=self.t(label)).grid(row=r, column=0, sticky='w')
            tk.Scale(grid, variable=self.prop[key], from_=50, to=150, resolution=1, orient='horizontal', length=240,
                     showvalue=False).grid(row=r, column=1, padx=8, pady=1)
            ttk.Label(grid, textvariable=self.prop[key], width=4, anchor='e').grid(row=r, column=2, sticky='e')
            ttk.Label(grid, text='%').grid(row=r, column=3, sticky='w')
        ttk.Button(right, text=self.t('adj_prop_reset'),
                   command=lambda: [v.set(100) for v in self.prop.values()]).pack(anchor='w', pady=(6, 0))


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

    def natural_neck(self):
        nf = self.info.get('neck') if self.info else None
        if nf:
            self.head_cm.set(nf['natural_cm'])

    def apply_adjust(self):
        """the tab's values into the project ('adjust'; only what isn't at its neutral value), then convert"""
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
        if not hasattr(self, 'hint') or not self.hint.winfo_exists():
            return
        p = self.proj
        model = p.get('fbx')
        self.model_lbl.config(text=os.path.basename(model) if model else self.t('no_model'))
        self.tex_lbl.config(text=self.t('textures') % (p.get('textures') or self.t('no_textures')))
        self.obj_lbl.config(text=self.t('obj_note') if model and model.lower().endswith('.obj') else '')
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
        ttk.Label(f, text=self.t('rights'), wraplength=420, foreground='#a04000').pack(anchor='w', pady=(4, 0))

        def go():
            vals = {k: v.get() for k, v in fields.items()}
            self.proj['pack'] = vals
            self.save_project()
            d.destroy()
            self.run(lambda: K.export_pack(self.work, vals['pack_name'], vals['version'], vals['author'],
                                           vals['what'], vals['model_credits']),
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
        paths_ = [os.path.join(self.work, 'previews', n) for n in ('body.png', 'face.png')]
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
    if len(sys.argv) > 1 and sys.argv[1] in ('characters', 'make', 'install', 'restore', 'export'):
        # '<tool>.exe make <project> ...': kit.py's commands without Python. The .exe has no console, so what they print
        # goes to %TEMP%\<tool>.log (make also writes <project>\report.txt)
        if sys.stdout is None:
            sys.stdout = sys.stderr = open(os.path.join(os.environ.get('TEMP', '.'), TOOL + '.log'), 'w', encoding='utf-8')
        K.main(sys.argv[1:])
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
