"""Task-oriented creator home and a separate character-project browser."""
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from about import AUTHOR, TOOL, VERSION

TEXT = {
    'es': dict(intro='Explora el juego, prepara tus cambios y gestiona tus mods.',
               choose='¿Qué quieres hacer?', game_ready='Juego detectado', game_missing='Selecciona tu juego',
               game_help='Elige la carpeta donde está instalado Toy Story 3.', folders='Carpetas',
               workspace_change='Cambiar carpeta de trabajo…', workspace_open='Abrir carpeta de trabajo',
               explorer='Explorar el juego', explorer_help='Busca archivos, mira vistas previas y guarda copias del contenido.',
               explorer_action='Explorar archivos', textures='Texturas',
               textures_help='Prepara imágenes PNG para editarlas y crea un pack de texturas.', textures_action='Editar texturas',
               models='Modelos y objetos', models_help='Exporta a Blender y modifica piezas de objetos rígidos.', models_action='Ver modelos',
               sounds='Música y sonidos', sounds_help='Escucha música, voces y efectos o guarda fragmentos WAV.', sounds_action='Escuchar sonidos',
               characters='Personajes', characters_help='Reemplaza personajes con tu modelo y retoma tus proyectos.', characters_action='Abrir personajes',
               mods='Gestionar mods', mods_help='Instala, verifica, ordena y quita tus paquetes de mods.', mods_action='Gestionar mods',
               character_intro='Crea un reemplazo de personaje o continúa un proyecto existente.',
               character_new='Nuevo proyecto de personaje…', character_open='Abrir proyecto de personaje…',
               recent='Proyectos recientes', project='Proyecto', character='Personaje', model='Modelo',
               open_selected='Abrir proyecto', select='Selecciona un proyecto para continuar.',
               no_recent='Todavía no hay proyectos. Crea uno o abre su carpeta.', unreadable='No se pudo leer el proyecto',
               models_intro='Selecciona un archivo y comprueba su vista previa. Editar prepara objetos rígidos; Más exporta a Blender.'),
    'en': dict(intro='Explore the game, prepare your changes and manage your mods.',
               choose='What would you like to do?', game_ready='Game found', game_missing='Select your game',
               game_help='Choose the folder where Toy Story 3 is installed.', folders='Folders',
               workspace_change='Change workspace folder…', workspace_open='Open workspace folder',
               explorer='Explore the game', explorer_help='Find files, view previews and save copies of game content.',
               explorer_action='Browse files', textures='Textures',
               textures_help='Prepare PNG images to edit and build a texture pack.', textures_action='Edit textures',
               models='Models and objects', models_help='Export to Blender and edit pieces of rigid objects.', models_action='View models',
               sounds='Music and sounds', sounds_help='Listen to music, voices and effects or save WAV excerpts.', sounds_action='Listen to sounds',
               characters='Characters', characters_help='Replace characters with your model and continue your projects.', characters_action='Open characters',
               mods='Manage mods', mods_help='Install, verify, reorder and remove your mod packages.', mods_action='Manage mods',
               character_intro='Create a character replacement or continue an existing project.',
               character_new='New character project…', character_open='Open character project…',
               recent='Recent projects', project='Project', character='Character', model='Model',
               open_selected='Open project', select='Select a project to continue.',
               no_recent='No projects yet. Create one or open its folder.', unreadable='The project could not be read',
               models_intro='Select a file and check its preview. Edit prepares rigid objects; More exports to Blender.'),
}

TASKS = ('explorer', 'textures', 'models', 'sounds', 'characters', 'mods')
BG, INK, MUTED, BORDER, BLUE, SOFT = '#F4F6F9', '#172B45', '#526277', '#DCE3EC', '#155DB1', '#E8F0FC'


def styles():
    style = ttk.Style()
    style.configure('Home.TFrame', background=BG)
    for name in ('Home.TLabel', 'Home.Title.TLabel', 'Home.Muted.TLabel', 'Home.Small.TLabel', 'Home.Section.TLabel'):
        style.configure(name, background=BG, foreground=INK, font=('Segoe UI', 10))
    for name in ('Home.Card.TLabel', 'Home.CardTitle.TLabel', 'Home.CardNote.TLabel'):
        style.configure(name, background='white', foreground=INK, font=('Segoe UI', 10))
    style.configure('Home.Title.TLabel', font=('Segoe UI', 22, 'bold'))
    style.configure('Home.Muted.TLabel', foreground=MUTED, font=('Segoe UI', 10))
    style.configure('Home.Small.TLabel', foreground=MUTED, font=('Segoe UI', 9))
    style.configure('Home.Section.TLabel', font=('Segoe UI', 12, 'bold'))
    style.configure('Home.Card.TLabel', background='white', foreground=INK, font=('Segoe UI', 10))
    style.configure('Home.CardTitle.TLabel', font=('Segoe UI', 12, 'bold'))
    style.configure('Home.CardNote.TLabel', foreground=MUTED)
    style.configure('Home.Action.TButton', font=('Segoe UI', 10), padding=(10, 6))
    style.configure('Home.Treeview', rowheight=30, font=('Segoe UI', 10))


def button(app, parent, text, command):
    widget = ttk.Button(parent, text=text, command=command, style='Home.Action.TButton')
    app.buttons.append(widget)
    return widget


# Card icons: strokes on a 24-unit grid (round caps and joins), like an SVG icon set. Tk's canvas draws without
# anti-aliasing, so they are drawn with Pillow at SUPER times the size and reduced: smooth edges at any scale.
# ('line', x, y, ...) open path, ('shape', x, y, ...) closed path, ('circle', cx, cy, r),
# ('arc', cx, cy, rx, ry, from°, to°) (y down, so 180→360 is the upper half), ('box', x1, y1, x2, y2, radius).
ICONS = {
    'explorer': (('circle', 10.5, 10.5, 6.5), ('line', 15.4, 15.4, 20.5, 20.5)),
    'textures': (('box', 3.5, 3.5, 20.5, 20.5, 3), ('circle', 9, 9, 1.75),
                 ('line', 20.5, 15, 15.5, 10, 5, 20.5)),
    'models': (('shape', 12, 2.75, 20.25, 7.25, 20.25, 16.75, 12, 21.25, 3.75, 16.75, 3.75, 7.25),
               ('line', 3.75, 7.25, 12, 11.75, 20.25, 7.25), ('line', 12, 11.75, 12, 21.25)),
    'sounds': (('shape', 3.5, 9.5, 7.5, 9.5, 12.5, 5, 12.5, 19, 7.5, 14.5, 3.5, 14.5),
               ('arc', 12.5, 12, 4.25, 4.25, -48, 48), ('arc', 12.5, 12, 8, 8, -48, 48)),
    'characters': (('circle', 12, 7.75, 4), ('arc', 12, 21, 7.5, 7, 180, 360)),
    'mods': (('box', 3, 3.75, 21, 8.5, 1.5), ('box', 4.75, 8.5, 19.25, 20.5, 2), ('line', 10, 12.5, 14, 12.5)),
}
SUPER, TILE, GLYPH, STROKE = 8, 34, 22, 2.0


def icon_image(kind, size=TILE, ink=BLUE, tile=SOFT, back='white'):
    """The card icon as a Pillow image: the glyph centred on a rounded tile, `size` pixels square."""
    from PIL import Image, ImageDraw
    big = size*SUPER; k = big*GLYPH/TILE/24; off = (big - 24*k)/2; w = STROKE*k; r = w/2
    image = Image.new('RGB', (big, big), back); draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big-1, big-1), radius=big*0.27, fill=tile)
    at = lambda x, y: (off + x*k, off + y*k)
    def path(points, closed):
        if closed: points = points + points[:1]
        draw.line(points, fill=ink, width=round(w))
        for x, y in points: draw.ellipse((x-r, y-r, x+r, y+r), fill=ink)   # round caps and joins
    for name, *v in ICONS.get(kind, ICONS['mods']):
        if name in ('line', 'shape'):
            path([at(*v[i:i+2]) for i in range(0, len(v), 2)], name == 'shape')
        elif name == 'circle':
            (x, y), s = at(v[0], v[1]), v[2]*k + r
            draw.ellipse((x-s, y-s, x+s, y+s), outline=ink, width=round(w))
        elif name == 'arc':
            cx, cy, rx, ry, a, b = v; n = max(8, int(abs(b-a)/4))
            path([at(cx + rx*math.cos(math.radians(a + (b-a)*i/n)), cy + ry*math.sin(math.radians(a + (b-a)*i/n)))
                  for i in range(n+1)], False)
        elif name == 'box':
            (x1, y1), (x2, y2) = at(v[0], v[1]), at(v[2], v[3])
            draw.rounded_rectangle((x1-r, y1-r, x2+r, y2+r), radius=v[4]*k + r, outline=ink, width=round(w))
    return image.resize((size, size), Image.BOX)     # area average: no ringing halos around the strokes


def icon(parent, kind):
    from PIL import ImageTk
    scale = float(parent.tk.call('tk', 'scaling'))/(96/72)          # follow Tk's own scaling (1.0 at 96 dpi)
    photo = ImageTk.PhotoImage(icon_image(kind, max(TILE, round(TILE*scale))), master=parent)
    label = tk.Label(parent, image=photo, background='white', borderwidth=0, highlightthickness=0, takefocus=False)
    label.image = photo                                               # Tk keeps no reference of its own
    return label


def workspace_footer(app, parent, words):
    footer = ttk.Frame(parent, style='Home.TFrame'); footer.pack(fill='x', pady=(12, 0))
    options = ttk.Menubutton(footer, text=words['folders'], style='Home.Action.TButton')
    options.pack(side='right', padx=(14, 0)); app.buttons.append(options)
    menu = tk.Menu(options, tearoff=False)
    menu.add_command(label=words['workspace_change'], command=app.browse_workspace)
    menu.add_command(label=words['workspace_open'], command=app.open_workspace)
    options.config(menu=menu)
    label = ttk.Label(footer, text=app.t('workspace') % app.settings['workspace'], style='Home.Small.TLabel', wraplength=700)
    label.pack(side='left', fill='x', expand=True)
    footer.bind('<Configure>', lambda event: label.config(wraplength=max(200, event.width-120)))
    return footer


class HomePane:
    def __init__(self, app):
        styles(); words = TEXT[app.lang]
        frame = ttk.Frame(app.body, style='Home.TFrame', padding=(26, 18)); frame.pack(fill='both', expand=True)
        header = ttk.Frame(frame, style='Home.TFrame'); header.pack(fill='x')
        ttk.Label(header, text=TOOL, style='Home.Title.TLabel').pack(side='left')
        ttk.Label(header, text=app.t('by') % (AUTHOR, VERSION), style='Home.Small.TLabel').pack(side='right', padx=(12, 0))
        ttk.Label(frame, text=words['intro'], style='Home.Muted.TLabel').pack(anchor='w', pady=(4, 12))
        game = tk.Frame(frame, background='white', highlightbackground=BORDER, highlightthickness=1, padx=14, pady=9)
        game.pack(fill='x', pady=(0, 12))
        app.game_btn = button(app, game, '', app.browse_game); app.game_btn.pack(side='right', padx=(16, 0))
        app.game_lbl = ttk.Label(game, style='Home.CardTitle.TLabel'); app.game_lbl.pack(anchor='w')
        app.home_game_path = ttk.Label(game, style='Home.CardNote.TLabel', wraplength=700)
        app.home_game_path.pack(anchor='w', pady=(3, 0))
        game.bind('<Configure>', lambda event: app.home_game_path.config(wraplength=max(200, event.width-190)))
        app.show_game()
        ttk.Label(frame, text=words['choose'], style='Home.Section.TLabel').pack(anchor='w', pady=(0, 8))
        grid = ttk.Frame(frame, style='Home.TFrame'); grid.pack(fill='both', expand=True)
        for column in range(3): grid.columnconfigure(column, weight=1, uniform='home-cards')
        for row in range(2): grid.rowconfigure(row, weight=1, uniform='home-cards')
        actions = (app.show_explorer, app.show_textures, app.show_models, app.show_sounds, app.show_characters, app.show_mods)
        for i, (task, action) in enumerate(zip(TASKS, actions)):
            card = tk.Frame(grid, background='white', highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
            card.grid(row=i//3, column=i%3, sticky='nsew', padx=(0 if i%3 == 0 else 6, 0 if i%3 == 2 else 6),
                      pady=(0, 6) if i < 3 else (6, 0))
            heading = tk.Frame(card, background='white'); heading.pack(fill='x')
            icon(heading, task).pack(side='left', padx=(0, 10))
            title = ttk.Label(heading, text=words[task], style='Home.CardTitle.TLabel', wraplength=230)
            title.pack(side='left', fill='x', expand=True)
            button(app, card, words[task+'_action'], action).pack(side='bottom', anchor='w', pady=(8, 0))
            note = ttk.Label(card, text=words[task+'_help'], style='Home.CardNote.TLabel', wraplength=230)
            note.pack(anchor='w', fill='x', pady=(8, 0))
            def wrap(event, note=note, title=title):
                note.config(wraplength=max(140, event.width-30)); title.config(wraplength=max(100, event.width-72))
            card.bind('<Configure>', wrap)
        # Reserve footer space while keeping keyboard traversal in visual order.
        footer = workspace_footer(app, frame, words); footer.pack_configure(side='bottom', before=grid)


def recent_rows(paths, names, lang):
    """Read-only projection; a broken recent project remains visible without blocking navigation."""
    rows = []
    for path in paths:
        try:
            data = json.loads((Path(path)/'kit_project.json').read_text(encoding='utf-8'))
            if not isinstance(data, dict) or any(data.get(k) is not None and not isinstance(data[k], str) for k in ('fbx', 'character')):
                raise ValueError('Invalid project fields')
            character = data.get('character') or '—'
            rows.append(dict(path=path, name=Path(path).name, character=names.get(character, character),
                             model=Path(data['fbx']).name if data.get('fbx') else '—', readable=True))
        except (OSError, ValueError):
            rows.append(dict(path=path, name=Path(path).name, character='—', model=TEXT[lang]['unreadable'], readable=False))
    return rows


class CharactersPane:
    def __init__(self, app, names):
        styles(); words = TEXT[app.lang]
        frame = ttk.Frame(app.body, style='Home.TFrame', padding=(26, 18)); frame.pack(fill='both', expand=True)
        header = ttk.Frame(frame, style='Home.TFrame'); header.pack(fill='x')
        button(app, header, app.t('back'), app.show_home).pack(side='left', padx=(0, 16))
        ttk.Label(header, text=words['characters'], style='Home.Title.TLabel').pack(side='left')
        ttk.Label(frame, text=words['character_intro'], style='Home.Muted.TLabel').pack(anchor='w', pady=(8, 18))
        actions = ttk.Frame(frame, style='Home.TFrame'); actions.pack(fill='x', pady=(0, 20))
        button(app, actions, words['character_new'], app.new_project).pack(side='left', padx=(0, 8))
        button(app, actions, words['character_open'], app.open_other).pack(side='left')
        ttk.Label(frame, text=words['recent'], style='Home.Section.TLabel').pack(anchor='w', pady=(0, 8))
        area = ttk.Frame(frame, style='Home.TFrame'); area.pack(fill='both', expand=True)
        self.tree = tree = ttk.Treeview(area, columns=('character', 'model'), selectmode='browse', style='Home.Treeview')
        tree.heading('#0', text=words['project']); tree.column('#0', width=300, minwidth=180)
        for key, width in (('character', 170), ('model', 300)):
            tree.heading(key, text=words[key]); tree.column(key, width=width, minwidth=120)
        tree.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(area, command=tree.yview); scroll.pack(side='right', fill='y'); tree.config(yscrollcommand=scroll.set)
        self.rows = rows = recent_rows(app.recent_projects(), names, app.lang)
        for i, row in enumerate(rows): tree.insert('', 'end', iid=str(i), text=row['name'], values=(row['character'], row['model']))
        note = ttk.Label(frame, text=words['select'] if rows else words['no_recent'], style='Home.Muted.TLabel', wraplength=850)
        note.pack(anchor='w', pady=(10, 8))
        bar = ttk.Frame(frame, style='Home.TFrame'); bar.pack(fill='x')
        open_button = button(app, bar, words['open_selected'], lambda: self.open(app))
        open_button.pack(side='left'); open_button.state(['disabled'])
        def selected(event=None):
            selection = tree.selection(); row = rows[int(selection[0])] if selection else None
            note.config(text=row['path'] if row else words['select'])
            open_button.state(['!disabled'] if row and row['readable'] and not app.busy else ['disabled'])
        tree.bind('<<TreeviewSelect>>', selected)
        tree.bind('<Double-1>', lambda event: self.open(app)); tree.bind('<Return>', lambda event: self.open(app))
        tree.bind('<Button-1>', lambda event: 'break' if app.busy else None)
        tree.bind('<Key>', lambda event: 'break' if app.busy else None)
        footer = workspace_footer(app, frame, words); footer.pack_configure(side='bottom', before=area)

    def open(self, app):
        selection = self.tree.selection()
        if selection and not app.busy:
            row = self.rows[int(selection[0])]
            if row['readable']: app.open_project(row['path'])
