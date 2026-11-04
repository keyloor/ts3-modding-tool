"""The explorer screen. File operations run through App.run, never on Tk's thread."""
import json
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox

from PIL import ImageTk
from explorer import Browser, KINDS
import viewer
import texpack
import meshpack
import audiobank
import explorerpresent as present

TEXT = {
    'es': dict(title='Explorador del juego', intro='Busca modelos, texturas y sonidos de tu copia del juego.',
               search='Buscar', all='Todos', refresh='Actualizar índice', inspect='Inspeccionar',
               preview='Vista previa', extract='Extraer…', export='Guardar vista previa…',
               glb='Exportar modelo GLB…', glb_done='Modelo exportado: %s\n\nPersonajes: ajuste normal o esqueleto original desde el proyecto. Objetos rígidos: usa «Editar → Preparar objeto para Blender» para poder reinsertarlos.',
               mesh_dump='Exportar malla editable…', mesh_build='Crear pack de malla…', mesh_title='Pack de malla',
               mesh_workspace='Elige la carpeta exportada (contiene mesh.json)', mesh_model='Elige el GLB/glTF editado',
               mesh_help='Objetos rígidos: exporta el OCT, edita el GLB y crea un pack. Conserva triángulos por defecto; el pack ofrece reemplazo de topología para una pieza. Colisiones originales.',
               mesh_done='Malla editable en: %s\n\nModo conservar: mantén triángulos y _TS3_VERTEX (Blender: Mesh > Attributes). Para añadir o quitar geometría, marca «Reemplazar topología» al crear el pack; requiere una pieza visible. Materiales y colisiones originales.',
               mesh_pack_done='Pack creado: %d vértices editados. Instálalo desde «Gestionar mods»: %s',
               mesh_topology='Reemplazar topología: permitir añadir o quitar vértices y triángulos',
               mesh_topology_help='Reemplaza una pieza elegida, conservando las demás y su material original. No requiere _TS3_VERTEX. Las colisiones originales se conservan.',
               mesh_piece='Pieza que reemplazas',mesh_piece_all='Modelo completo (conservar topología)',
               mesh_piece_auto='Automática (solo si hay una pieza)',mesh_piece_title='Elige la pieza que vas a editar',
               mesh_piece_hint='Exporta el modelo completo para retocar sin cambiar triángulos, o una pieza para reemplazar su geometría. Las demás piezas se conservan.',
               mesh_piece_required='Elige una pieza concreta para reemplazar. Una exportación parcial requiere «Reemplazar topología».',
               mesh_piece_selected='Pieza reemplazada: %s\n',
               mesh_piece_counts='%d vértices · %d triángulos',
               mesh_topology_done='Topología reemplazada: %d → %d vértices, %d → %d triángulos. Colisiones originales. Pack: %s',
               path='Archivo / contenido', size='KiB', details='Detalles', images='Vista previa',
               select='Selecciona un archivo y pulsa Inspeccionar o Vista previa.',
               count='%d resultados · %d archivos leídos desde caché',
               limited='Mostrando los primeros 2000. Escribe una búsqueda más específica.',
               errors='%d archivos no se pudieron indexar. Detalles en el panel.',
               folder='Elige dónde crear la carpeta de extracción', saved='Guardado en: %s',
               unsupported='Este archivo aún no tiene vista previa. Puedes inspeccionarlo o extraerlo.',
               tex_dump='Exportar texturas PNG…', tex_build='Crear pack de texturas…',
               tex_many='Exportar varios ZIP…', tex_pick='Elige archivos ZIP dentro de la carpeta del juego',
               tex_outside='Elige únicamente archivos ZIP de esta carpeta del juego.',
               tex_scope='%d archivos seleccionados. Solo se exportarán texturas de estos archivos.',
               tex_shared='Compartir un PNG entre texturas idénticas',
               tex_shared_help='Al editar ese PNG se reemplazarán todas sus apariciones idénticas en los archivos seleccionados. Desmárcalo para editar cada aparición por separado.',
               tex_continue='Exportar PNG', tex_cancel='Cancelar',
               tex_help='Texturas: exporta los PNG, edítalos conservando su tamaño y crea un pack desde esa carpeta.',
               tex_workspace='Elige la carpeta de texturas exportadas (contiene index.json)',
               tex_title='Pack de texturas', tex_name='Nombre del mod', tex_author='Tu nombre o crédito',
               tex_version='Versión', tex_fields='Indica el nombre, tu crédito y una versión como 1.0.0.',
               tex_done='%d texturas (%d editables) en %d PNG de %d archivos. Carpeta: %s',
               tex_pack_done='Pack creado: %d texturas en %d archivos. Instálalo desde «Gestionar mods»: %s',
               controls='Arrastra para girar · botón derecho para mover · rueda para acercar',
               audio='Sonidos', audio_name='Muestra', audio_length='Duración', audio_play='Reproducir',
               audio_stop='Detener', audio_save='Guardar WAV…', audio_limit='Límite de escucha (segundos)',
               audio_hint='Inspecciona un banco de audio y elige una muestra. La escucha empieza al pulsar Reproducir.',
               audio_empty='Este archivo no contiene muestras. Elige un banco de audio (.assets.bank o .fsb).',
               audio_work='Decodificando la muestra… Puedes detener la operación.',
               audio_stopped='Detenido', audio_playing='Reproduciendo: %s',
               audio_info='%s · %d Hz · %s · %.2f s', audio_channel='1 canal', audio_channels='%d canales',
               audio_excerpt='Escucha de los primeros %.1f s de %.1f s.',
               kinds=('Archivo ZIP', 'OCT', 'Textura', 'Sonido', 'Malla', 'Texto', 'Otro')),
    'en': dict(title='Game explorer', intro='Find models, textures and sounds in your copy of the game.',
               search='Search', all='All', refresh='Refresh index', inspect='Inspect',
               preview='Preview', extract='Extract…', export='Save preview…',
               glb='Export GLB model…', glb_done='Model exported: %s\n\nCharacters: normal fitting or original skeleton from a project. Rigid objects: use Edit → Prepare object for Blender for reinsertion.',
               mesh_dump='Export editable mesh…', mesh_build='Build mesh pack…', mesh_title='Mesh pack',
               mesh_workspace='Choose the exported folder (contains mesh.json)', mesh_model='Choose the edited GLB/glTF',
               mesh_help='Rigid objects: export the OCT, edit its GLB, build a pack. Triangles are preserved by default; the pack offers topology replacement for one piece. Original collisions.',
               mesh_done='Editable mesh in: %s\n\nPreserve mode: keep triangles and _TS3_VERTEX (Blender: Mesh > Attributes). To add/remove geometry, select Replace topology when building the pack; requires one visible piece. Original materials and collisions stay.',
               mesh_pack_done='Pack created: %d edited vertices. Install it through Manage mods: %s',
               mesh_topology='Replace topology: allow adding or removing vertices and triangles',
               mesh_topology_help='Replaces a selected piece, keeping the others and its original material. _TS3_VERTEX is not needed. Original collisions stay.',
               mesh_piece='Piece to replace',mesh_piece_all='Whole model (preserve topology)',
               mesh_piece_auto='Automatic (only with one piece)',mesh_piece_title='Choose the piece to edit',
               mesh_piece_hint='Export the whole model for edits with unchanged triangles, or one piece to replace its geometry. The other pieces stay.',
               mesh_piece_required='Choose a specific replacement piece. Partial exports require Replace topology.',
               mesh_piece_selected='Replaced piece: %s\n',
               mesh_piece_counts='%d vertices · %d triangles',
               mesh_topology_done='Topology replaced: %d → %d vertices, %d → %d triangles. Original collisions. Pack: %s',
               path='File / contents', size='KiB', details='Details', images='Preview',
               select='Select a file and choose Inspect or Preview.',
               count='%d results · %d files read from cache',
               limited='Showing the first 2000. Enter a more specific search.',
               errors='%d files could not be indexed. See the details panel.',
               folder='Choose where to create the extraction folder', saved='Saved to: %s',
               unsupported='This asset does not have a supported preview yet. You can inspect or extract it.',
               tex_dump='Export PNG textures…', tex_build='Build texture pack…',
               tex_many='Export multiple ZIPs…', tex_pick='Choose ZIP archives inside the game folder',
               tex_outside='Choose only ZIP archives inside this game folder.',
               tex_scope='%d archives selected. Only textures from these archives will be exported.',
               tex_shared='Share one PNG between identical textures',
               tex_shared_help='Editing that PNG replaces all its identical occurrences in the selected archives. Leave unchecked to edit each occurrence separately.',
               tex_continue='Export PNGs', tex_cancel='Cancel',
               tex_help='Textures: export PNGs, edit them at the same size, then build a pack from that folder.',
               tex_workspace='Choose the exported texture folder (contains index.json)',
               tex_title='Texture pack', tex_name='Mod name', tex_author='Your name or credit',
               tex_version='Version', tex_fields='Enter the name, your credit and a version such as 1.0.0.',
               tex_done='%d textures (%d editable) in %d PNGs from %d archives. Folder: %s',
               tex_pack_done='Pack created: %d textures in %d archives. Install it through Manage mods: %s',
               controls='Drag to orbit · right drag to pan · wheel to zoom',
               audio='Sounds', audio_name='Sample', audio_length='Duration', audio_play='Play',
               audio_stop='Stop', audio_save='Save WAV…', audio_limit='Preview limit (seconds)',
               audio_hint='Inspect an audio bank and choose a sample. Audio starts only when you press Play.',
               audio_empty='This file has no samples. Choose an audio bank (.assets.bank or .fsb).',
               audio_work='Decoding sample… You can stop the operation.',
               audio_stopped='Stopped', audio_playing='Playing: %s',
               audio_info='%s · %d Hz · %s · %.2f s', audio_channel='1 channel', audio_channels='%d channels',
               audio_excerpt='Preview of the first %.1f s of %.1f s.',
               kinds=('ZIP archive', 'OCT', 'Texture', 'Sound', 'Mesh', 'Text', 'Other')),
}

# Keep authoring dialogs' precise format terms; the browser uses task-oriented labels.
TEXT['es'].update(refresh='Actualizar lista', path='Nombre', size='Tamaño', format='Formato', details='Información',
                  select='Selecciona un archivo de la lista para ver qué puedes hacer con él.',
                  extract='Guardar copia…', inspect='Ver información', preview='Vista previa',
                  tex_dump='Preparar imágenes para editar…', mesh_dump='Preparar objeto para Blender…',
                  glb='Exportar modelo para Blender…', create='Crear mod', options='Vista',
                  edit='Editar', more='Más', technical='Detalles técnicos',
                  show_technical='Mostrar archivos técnicos y nombres originales',
                  primary_sound='Ver sonidos', primary_oct='Ver modelo', primary_texture='Ver imagen',
                  check_preview='Comprobar vista', retry_preview='Reintentar', primary_images='Ver imágenes',
                  open_result='Abrir carpeta', result_ready='Archivos guardados',
                  result_missing='La carpeta ya no está disponible. Vuelve a exportar o comprueba si la moviste.',
                  build_images='Crear mod desde imágenes editadas…', build_model='Crear mod desde modelo editado…',
                  batch_images='Preparar imágenes de varios archivos…',
                  audio_hint='Elige un sonido y pulsa Reproducir. Puedes guardar una copia WAV.',
                  audio_empty='Este archivo contiene eventos o metadatos; no hay sonidos para escuchar.',
                  errors='%d archivos no se pudieron leer. Consulta «Más → Detalles técnicos».',
                  kinds=('Archivos con contenido', 'Modelos y texturas', 'Imágenes', 'Sonidos', 'Partes de modelos', 'Textos', 'Otros'))
TEXT['en'].update(refresh='Refresh list', path='Name', size='Size', format='Format', details='Information',
                  select='Select a file in the list to see what you can do with it.',
                  extract='Save a copy…', inspect='View information', preview='Preview',
                  tex_dump='Prepare images to edit…', mesh_dump='Prepare object for Blender…',
                  glb='Export model for Blender…', create='Create mod', options='View',
                  edit='Edit', more='More', technical='Technical details',
                  show_technical='Show technical files and original names',
                  primary_sound='View sounds', primary_oct='View model', primary_texture='View image',
                  check_preview='Check preview', retry_preview='Retry', primary_images='View images',
                  open_result='Open folder', result_ready='Files saved',
                  result_missing='The folder is no longer available. Export again or check whether you moved it.',
                  build_images='Create mod from edited images…', build_model='Create mod from edited model…',
                  batch_images='Prepare images from several archives…',
                  audio_hint='Choose a sound and press Play. You can save a WAV copy.',
                  audio_empty='This file contains events or metadata; there are no sounds to play.',
                  errors='%d files could not be read. Use More → Technical details.',
                  kinds=('Content archives', 'Models and textures', 'Images', 'Sounds', 'Model components', 'Text', 'Other'))


class ExplorerPane:
    def __init__(self, app, mode='all'):
        self.app, self.t = app, TEXT[app.lang]
        self.browser = Browser(app.settings['game'])
        self.index = None
        self.selected_key = None
        self.last_info, self.last_error = None, None
        self.preview_states = {}
        self.result_folder = None
        self.rows, self.children = {}, {}
        self.images, self.character, self.view, self.photo = {}, None, None, None
        self.player, self.audio_cancel, self.audio_timer = audiobank.Player(), None, None
        self.audio_samples, self.audio_key = [], None
        self.frame = f = ttk.Frame(app.body, padding=(22, 16))
        f.pack(fill='both', expand=True)
        from homeui import TEXT as HOME_TEXT
        words = HOME_TEXT[app.lang]
        title, intro = self.t['title'], self.t['intro']
        if mode == 'textures': title, intro = words['textures'], self.t['tex_help']
        elif mode == 'models': title, intro = words['models'], words['models_intro']
        elif mode == 'sounds': title, intro = words['sounds'], words['sounds_help']
        bar = ttk.Frame(f); bar.pack(fill='x')
        self.button(bar, app.t('back'), app.show_home).pack(side='left', padx=(0, 16))
        ttk.Label(bar, text=title, style='Title.TLabel').pack(side='left')
        create = self.menu_button(bar, self.t['create'])
        create.pack(side='right')
        menu = tk.Menu(create, tearoff=False)
        menu.add_command(label=self.t['build_images'], command=self.build_textures)
        menu.add_command(label=self.t['build_model'], command=self.build_mesh)
        menu.add_separator()
        menu.add_command(label=self.t['batch_images'], command=self.dump_many)
        create.config(menu=menu)
        ttk.Label(f, text=intro, style='Sub.TLabel', wraplength=900).pack(anchor='w', pady=(6, 2))
        ttk.Label(f, text=str(self.browser.game), style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        bar = ttk.Frame(f); bar.pack(fill='x')
        self.query = tk.StringVar()
        ttk.Label(bar, text=self.t['search']).pack(side='left', padx=(0, 8))
        entry = self.search_entry = ttk.Entry(bar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', lambda e: self.filter())
        self.category = ttk.Combobox(bar, values=(self.t['all'], *self.t['kinds']), state='readonly', width=16)
        self.category.current({'textures': 2, 'models': 2, 'sounds': 4}.get(mode, 0)); self.category.pack(side='left', padx=8)
        self.category.bind('<<ComboboxSelected>>', lambda e: self.filter())
        self.button(bar, self.t['search'], self.filter).pack(side='left')
        options = self.menu_button(bar, self.t['options']); options.pack(side='left', padx=8)
        self.technical_files = tk.BooleanVar(value=False)
        menu = tk.Menu(options, tearoff=False)
        menu.add_checkbutton(label=self.t['show_technical'], variable=self.technical_files, command=self.filter)
        menu.add_command(label=self.t['refresh'], command=lambda: self.reload(True))
        options.config(menu=menu)
        self.note = ttk.Label(f, wraplength=1040, style='Muted.TLabel')
        self.note.pack(anchor='w', pady=8)
        split = ttk.Panedwindow(f, orient='horizontal'); split.pack(fill='both', expand=True)
        left = ttk.Frame(split); right = ttk.Frame(split)
        split.add(left, weight=1); split.add(right, weight=1)
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=('format', 'preview', 'size'), selectmode='browse')
        self.tree.heading('#0', text=self.t['path']); self.tree.column('#0', width=180, minwidth=150)
        self.tree.heading('format', text=self.t['format']); self.tree.column('format', width=80, stretch=False)
        self.tree.heading('preview', text=self.t['preview']); self.tree.column('preview', width=115, stretch=False)
        self.tree.heading('size', text=self.t['size']); self.tree.column('size', width=75, stretch=False, anchor='e')
        self.tree.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(left, command=self.tree.yview); sy.grid(row=0, column=1, sticky='ns')
        sx = ttk.Scrollbar(left, orient='horizontal', command=self.tree.xview); sx.grid(row=1, column=0, sticky='ew')
        self.tree.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.bind('<<TreeviewOpen>>', self.expand)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.selected())
        self.tree.bind('<Double-1>', lambda e: self.open_selected())
        self.tree.bind('<Return>', self.open_selected)
        self.tree.bind('<Alt-Return>', lambda e: self.technical_details())
        self.tree.bind('<Control-f>', lambda e: entry.focus_set())
        self.tree.bind('<Button-1>', lambda e: 'break' if app.busy else None)
        self.tree.bind('<Key>', lambda e: 'break' if app.busy else None)
        self.location = ttk.Label(right, wraplength=420, style='Muted.TLabel')
        self.location.pack(fill='x', padx=(12, 0), pady=(0, 8))
        self.preview_note = ttk.Label(right, wraplength=420)
        self.preview_note.pack(fill='x', padx=(12, 0), pady=(0, 8))
        bar = ttk.Frame(right); bar.pack(fill='x', padx=(12, 0), pady=(0, 10))
        self.primary = self.button(bar, self.t['preview'], self.open_selected)
        self.copy_button = self.button(bar, self.t['extract'], self.extract)
        self.edit_button = self.menu_button(bar, self.t['edit'])
        self.edit_menu = tk.Menu(self.edit_button, tearoff=False); self.edit_button.config(menu=self.edit_menu)
        self.more_button = self.menu_button(bar, self.t['more'])
        self.more_menu = tk.Menu(self.more_button, tearoff=False); self.more_button.config(menu=self.more_menu)
        self.toolbar_layout = None
        def wrap_notes(event):
            width = max(180, event.width-24)
            self.location.config(wraplength=width); self.preview_note.config(wraplength=width)
        right.bind('<Configure>', wrap_notes)
        self.tabs = ttk.Notebook(right); self.tabs.pack(fill='both', expand=True, padx=(12, 0))
        self.details_tab = details = ttk.Frame(self.tabs)
        self.preview_tab = previews = ttk.Frame(self.tabs)
        self.tabs.add(details, text=self.t['details']); self.tabs.add(previews, text=self.t['images'])
        self.result_bar = ttk.Frame(details, padding=(12, 8))
        self.result_note = ttk.Label(self.result_bar, text=self.t['result_ready'])
        self.result_note.pack(side='left', fill='x', expand=True)
        self.result_button = self.button(self.result_bar, self.t['open_result'], self.open_result)
        self.result_button.pack(side='right', padx=(12, 0))
        self.detail = tk.Text(details, wrap='word', font=('Segoe UI', 10), width=42, state='disabled', padx=12, pady=12)
        self.detail.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(details, command=self.detail.yview); scroll.pack(side='right', fill='y')
        self.detail.config(yscrollcommand=scroll.set)
        self.image_name = ttk.Combobox(previews, state='readonly')
        self.image_name.pack(fill='x', padx=8, pady=8)
        self.image_name.bind('<<ComboboxSelected>>', lambda e: self.show_image())
        self.canvas = ttk.Frame(previews); self.canvas.pack(fill='both', expand=True)
        self.image_label = ttk.Label(self.canvas, anchor='center', wraplength=400)
        self.image_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.canvas.bind('<Configure>', lambda e: self.fit_image())
        ttk.Label(previews, text=self.t['controls'], style='Muted.TLabel', wraplength=400).pack(pady=8)
        self.audio_tab = audio = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(audio, text=self.t['audio'])
        self.audio_note = ttk.Label(audio, text=self.t['audio_hint'], wraplength=420)
        self.audio_note.pack(anchor='w', fill='x', pady=(0, 10))
        listing = ttk.Frame(audio); listing.pack(fill='both', expand=True)
        self.audio_list = ttk.Treeview(listing, columns=('duration',), selectmode='browse', height=8)
        self.audio_list.heading('#0', text=self.t['audio_name']); self.audio_list.column('#0', width=230, minwidth=100)
        self.audio_list.heading('duration', text=self.t['audio_length'])
        self.audio_list.column('duration', width=90, stretch=False, anchor='e')
        self.audio_list.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(listing, command=self.audio_list.yview); scroll.pack(side='right', fill='y')
        self.audio_list.config(yscrollcommand=scroll.set)
        self.audio_list.bind('<<TreeviewSelect>>', lambda e: self.audio_selected())
        self.audio_list.bind('<Button-1>', lambda e: 'break' if app.busy else None)
        self.audio_list.bind('<Key>', lambda e: 'break' if app.busy else None)
        controls = ttk.Frame(audio); controls.pack(fill='x', pady=(12, 8))
        ttk.Label(controls, text=self.t['audio_limit']).pack(side='left')
        self.audio_seconds = ttk.Combobox(controls, values=(5, 15, 30, 60, 120), state='readonly', width=6)
        self.audio_seconds.set('30'); self.audio_seconds.pack(side='right')
        controls = ttk.Frame(audio); controls.pack(fill='x')
        # Stop stays usable while App.run disables the remaining controls during decoding.
        self.audio_play = self.button(controls, self.t['audio_play'], self.play_audio)
        self.audio_play.pack(side='left', padx=(0, 8))
        self.audio_stop = ttk.Button(controls, text=self.t['audio_stop'], command=self.stop_audio)
        self.audio_stop.pack(side='left', padx=(0, 8))
        self.audio_save = self.button(controls, self.t['audio_save'], self.save_audio)
        self.audio_save.pack(side='left')
        self.audio_progress = ttk.Progressbar(audio, maximum=1)
        self.audio_progress.pack(fill='x', pady=(12, 6))
        self.audio_status = ttk.Label(audio, text=self.t['audio_stopped'], wraplength=420)
        self.audio_status.pack(anchor='w', fill='x')
        self.audio_selected()
        self.set_details(self.t['select'])
        self.reload()

    def button(self, parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        self.app.buttons.append(b)
        return b

    def menu_button(self, parent, text):
        b = ttk.Menubutton(parent, text=text)
        self.app.buttons.append(b)
        return b

    def set_details(self, text):
        self.detail.config(state='normal'); self.detail.delete('1.0', 'end')
        self.detail.insert('end', text); self.detail.config(state='disabled')

    def show_result(self, text, result):
        self.last_info, self.last_error = result, None
        self.clear_result()
        folder = Path(result['output']) if result.get('output') else None
        if folder is not None and folder.is_dir():
            self.result_folder = folder
            self.result_note.config(text=self.t['result_ready'])
            self.result_bar.pack(side='bottom', fill='x', before=self.detail)
        self.set_details(text); self.tabs.select(self.details_tab)
        self.app.status.set(self.app.t('ready'))

    def clear_result(self):
        self.result_folder = None
        self.result_bar.pack_forget()

    def open_result(self):
        if self.app.busy or self.result_folder is None: return
        if self.result_folder.is_dir():
            try: self.app.open_path(str(self.result_folder))
            except OSError as error: self.failed(str(error))
        else:
            self.result_note.config(text=self.t['result_missing'], wraplength=300)
            self.result_button.state(['disabled'])
            self.app.status.set(self.app.t('error'))

    def reload(self, refresh=False):
        if not self.app.busy:
            self.app.run(lambda: self.browser.index(refresh), self.loaded, on_error=self.failed)

    def loaded(self, index):
        self.index = index
        self.preview_states = {}
        self.filter()
        self.app.status.set(self.app.t('ready'))

    def filter(self):
        if self.app.busy or self.index is None:
            return
        self.clear_preview()
        self.tree.delete(*self.tree.get_children())
        self.rows, self.children = {}, {}
        self.selected_key, self.last_info, self.last_error = None, None, None
        cat = self.category.current()
        query = self.query.get().strip()
        rows = self.browser.search(self.index, category=KINDS[cat - 1] if cat > 0 else None,
                                   playable=cat == 4 and not self.technical_files.get())
        rows = [row for row in rows if present.matches(row, query, self.app.lang)]
        # Unfiltered archives expand lazily: the complete game can have hundreds of thousands of members.
        filtered = bool(query or cat > 0)
        visible = rows if filtered else [r for r in rows if r['member'] is None]
        groups = {}
        for row in (visible[:2000] if filtered else visible):
            group = present.group(row, self.app.lang)
            if group not in groups: groups[group] = self.tree.insert('', 'end', text=group, open=True)
            iid = self.add(groups[group], row)
            if row['kind'] == 'archive' and row['member'] is None:
                self.children[iid] = [dict(e, path=row['path']) for e in self.index['files'][row['path']]['entries']]
                if self.children[iid]:
                    self.tree.insert(iid, 'end', text='…')
        note = present.count(len(visible), self.app.lang)
        if filtered and len(visible) > 2000:
            note += '\n' + self.t['limited']
        if self.index['errors']:
            note += '\n' + self.t['errors'] % len(self.index['errors'])
        self.note.config(text=note)
        self.tree.yview_moveto(0)
        self.set_details(self.t['select'])
        self.selected()

    def add(self, parent, row):
        entries = self.index['files'][row['path']]['entries'] if row['member'] is None else None
        hint = self.preview_states.get((row['path'], row['member']), present.preview_kind(row, entries))
        row = dict(row, preview_hint=hint)
        text = (row['member'] or row['path']) if self.technical_files.get() else present.name(row)
        iid = self.tree.insert(parent, 'end', text=text, values=(present.extension(row) or '—', present.preview_text(row, self.app.lang), present.size(row['size'], self.app.lang)))
        self.rows[iid] = row
        return iid

    def expand(self, event=None):
        iid = self.tree.focus()
        if iid in self.children:
            self.tree.delete(*self.tree.get_children(iid))
            for row in self.children.pop(iid):
                self.add(iid, row)

    def row(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def selected(self):
        row = self.row()
        key = (row['path'], row['member']) if row else None
        if key != self.selected_key:
            self.selected_key = key
            self.last_info, self.last_error = None, None
            self.clear_preview()
            self.set_details(present.summary(row, self.app.lang) if row else self.t['select'])
            self.tabs.select(self.details_tab)
        self.location.config(text=(row['path'] + ('\n↳ ' + row['member'] if row['member'] else '')) if row else '')
        self.preview_note.config(text=present.preview_text(row, self.app.lang, detail=True) if row else '')
        actions = present.actions(row)
        label = self.t['inspect']
        if row and 'audio' in actions: label = self.t['primary_sound']
        elif row and 'preview' in actions:
            hint = present.preview_kind(row)
            label = (self.t['check_preview'] if hint == 'check' else self.t['retry_preview'] if hint == 'error' else
                     self.t['primary_images'] if hint == 'images' else self.t['primary_oct'] if hint == 'model' else
                     self.t['primary_texture'] if hint == 'image' else self.t['preview'])
        self.primary.config(text=label)
        buttons = (self.primary, self.copy_button, self.edit_button, self.more_button)
        layout = (bool(row), bool(row), 'tex_dump' in actions or 'mesh_dump' in actions, True)
        if layout != self.toolbar_layout:
            for button in buttons: button.pack_forget()
            for button, visible in zip(buttons, layout):
                if visible: button.pack(side='left', padx=(0, 6))
            self.toolbar_layout = layout
        for button in buttons:
            button.state(['disabled'] if self.app.busy else ['!disabled'])
        self.edit_menu.delete(0, 'end'); self.more_menu.delete(0, 'end')
        for action, fn in (('tex_dump', self.dump_textures), ('mesh_dump', self.dump_mesh)):
            if action in actions: self.edit_menu.add_command(label=self.t[action], command=fn)
        for action, fn in (('glb', self.export_glb), ('export', lambda: self.extract(True))):
            if action in actions: self.more_menu.add_command(label=self.t[action], command=fn)
        if self.more_menu.index('end') is not None: self.more_menu.add_separator()
        self.more_menu.add_command(label=self.t['technical'], command=self.technical_details)
        for tab, visible in ((self.preview_tab, 'preview' in actions), (self.audio_tab, 'audio' in actions)):
            if visible: self.tabs.add(tab)
            else: self.tabs.hide(tab)
        self.audio_selected(stop=False)

    def open_selected(self, event=None):
        row = self.row()
        if self.app.busy: return 'break'
        if row:
            if 'preview' in present.actions(row): self.preview()
            else: self.inspect()
        elif event is not None and event.type.name == 'KeyPress':
            iid = self.tree.focus()
            if iid: self.tree.item(iid, open=not self.tree.item(iid, 'open')); self.expand()
        return 'break' if event is not None and event.type.name == 'KeyPress' else None

    def technical_details(self):
        if self.app.busy: return
        self.tabs.select(self.details_tab)
        if self.last_error: self.set_details(self.last_error)
        elif self.last_info: self.set_details(json.dumps(self.last_info, indent=2, ensure_ascii=False))
        elif self.row(): self.inspect(technical=True)
        else: self.set_details(json.dumps(self.index.get('errors', []) if self.index else [], indent=2, ensure_ascii=False))

    def inspect(self, technical=False):
        row = self.row()
        if self.app.busy or not row:
            return
        self.clear_preview()
        self.tabs.select(self.details_tab)
        def failed(message):
            if row['kind'] == 'sound': self.record_preview('error')
            self.failed(message)
        self.app.run(lambda: self.browser.inspect(row['path'], row['member']),
                     lambda result: self.details_ready(result, technical), on_error=failed)

    def details_ready(self, result, technical=False):
        self.last_info, self.last_error = result, None
        self.set_details(json.dumps(result, indent=2, ensure_ascii=False) if technical else present.summary(result, self.app.lang, result))
        if result['kind'] == 'sound':
            self.record_preview('audio' if result.get('sounds') else 'none')
            self.audio_key = (result['path'], result['member'])
            self.audio_samples = result.get('sounds', [])
            for s in self.audio_samples:
                self.audio_list.insert('', 'end', iid=str(s['index']), text=s['name'], values=('%.2f s' % s['seconds'],))
            self.audio_note.config(text=self.t['audio_hint'] if self.audio_samples else self.t['audio_empty'])
            if self.audio_samples: self.audio_list.selection_set('0')
            if not technical: self.tabs.select(self.audio_tab)
            self.audio_selected()
        self.app.status.set(self.app.t('ready'))

    def preview(self):
        row = self.row()
        if self.app.busy or not row:
            return
        if row['kind'] == 'sound':
            self.inspect(); return
        self.clear_preview()
        self.tabs.select(self.preview_tab)
        self.image_label.config(text=self.app.t('working'))
        def failed(message):
            self.record_preview('error'); self.failed(message)
        self.app.run(lambda: self.browser.preview(row['path'], row['member']), self.preview_ready, on_error=failed)

    def record_preview(self, hint):
        if self.selected_key is None: return
        self.preview_states[self.selected_key] = hint
        for iid, row in self.rows.items():
            if (row['path'], row['member']) == self.selected_key:
                row['preview_hint'] = hint
                self.tree.set(iid, 'preview', present.preview_text(row, self.app.lang))

    def preview_ready(self, result):
        self.last_error = None
        self.images, self.character = result
        self.record_preview('model' if self.character is not None else 'images' if self.images else 'none')
        choices = list(self.images)
        self.image_name.config(values=choices)
        if choices:
            self.image_name.set('model' if 'model' in choices else choices[0])
            self.show_image()
        else:
            self.image_label.config(text=self.t['unsupported'])
        self.app.status.set(self.app.t('ready'))

    def show_image(self):
        if self.view:
            self.view.release(); self.view = None
        self.image_label.destroy()
        self.image_label = ttk.Label(self.canvas, anchor='center', wraplength=400)
        self.image_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        if self.image_name.get() == 'model' and self.character is not None and viewer.available():
            try:
                self.view = viewer.View(self.image_label)
                self.view.set_character(self.character)
                return
            except Exception:
                if self.view:
                    self.view.release(); self.view = None
        self.fit_image()

    def fit_image(self):
        im = self.images.get(self.image_name.get())
        if im is not None and self.view is None:
            im = im.copy()
            im.thumbnail((max(64, self.canvas.winfo_width() - 12), max(64, self.canvas.winfo_height() - 12)))
            self.photo = ImageTk.PhotoImage(im)
            self.image_label.config(image=self.photo, text='')

    def extract(self, preview=False):
        row = self.row()
        if self.app.busy or not row:
            return
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent:
            return
        name = Path(row['member'] or row['path']).stem + ('-preview' if preview else '-extracted')
        out = Path(parent) / name
        n = 2
        while out.exists():
            out = Path(parent) / (name + '-' + str(n)); n += 1
        self.app.run(lambda: self.browser.export(row['path'], row['member'], out, preview),
                     lambda result: self.show_result(self.t['saved'] % result['output'], result), on_error=self.failed)

    def failed(self, message):
        self.clear_result()
        self.last_error = str(message)
        self.set_details(present.error(str(message), self.app.lang))
        self.tabs.select(self.details_tab)
        self.app.status.set(self.app.t('error'))

    def export_glb(self):
        row = self.row()
        if self.app.busy or not row:
            return
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent:
            return
        stem = Path(row['member'] or row['path']).stem + '-glb'
        out, n = Path(parent) / stem, 2
        while out.exists():
            out = Path(parent) / (stem + '-' + str(n)); n += 1
        def done(result):
            self.show_result(self.t['glb_done'] % result['output'], result)
        self.app.run(lambda: self.browser.export_glb(row['path'], row['member'], out), done, on_error=self.failed)

    def dump_mesh(self):
        row = self.row()
        if self.app.busy or not row or not (row.get('member') or '').lower().endswith('.oct'): return
        self.app.run(lambda:meshpack.list_pieces(self.browser.game,row['path'],row['member']),
                     lambda info:self.dump_mesh_part(row,info),on_error=self.failed)

    def dump_mesh_part(self,row,info):
        piece=None
        if len(info['pieces'])>1:
            choice=MeshPieceDialog(self.app.root,self.t,info['pieces'])
            if choice.result is None:return
            piece=choice.result['piece']
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent: return
        stem = Path(row['member']).stem+'-mesh'+('-piece-'+str(piece) if piece is not None else '')
        out = Path(parent)/stem; n = 2
        while out.exists(): out = Path(parent)/(stem+'-'+str(n)); n += 1
        def done(result):
            self.show_result(self.t['mesh_done'] % result['output'], result)
        self.app.run(lambda: meshpack.dump(self.browser.game,row['path'],row['member'],out,piece=piece),done,on_error=self.failed)

    def build_mesh(self):
        if self.app.busy: return
        folder = filedialog.askdirectory(title=self.t['mesh_workspace'],parent=self.app.root)
        if not folder: return
        try: _, index = meshpack.workspace(folder)
        except (ValueError,OSError) as e: self.failed(str(e)); return
        self.app.run(lambda:meshpack.pieces(self.browser.game,folder),
                     lambda info:self.mesh_pack_details(folder,index,info),on_error=self.failed)

    def mesh_pack_details(self,folder,index,info):
        model = filedialog.askopenfilename(title=self.t['mesh_model'],initialdir=folder,initialfile='model.glb',
                                          filetypes=[('GLB / glTF','*.glb *.gltf'),('*','*.*')],parent=self.app.root)
        if not model: return
        words = dict(self.t,tex_title=self.t['mesh_title'],allow_topology=True,
                     piece_rows=info['pieces'],default_piece=index.get('piece'))
        dialog = TexturePackDialog(self.app.root,words)
        if not dialog.result: return
        name,author,version,topology,piece = dialog.result
        parent = filedialog.askdirectory(title=self.t['folder'],parent=self.app.root)
        if not parent: return
        import re
        stem = (re.sub('[^A-Za-z0-9 _-]','_',name).strip()[:80] or 'mesh')+'-pack'
        out = Path(parent)/stem; n = 2
        while out.exists(): out = Path(parent)/(stem+'-'+str(n)); n += 1
        def done(result):
            text = ((self.t['mesh_piece_selected']%result['piece_name'])+self.t['mesh_topology_done'] % (result['vertices_before'],result['vertices_after'],
                             result['triangles_before'],result['triangles_after'],result['output']) if topology=='replace' else
                             self.t['mesh_pack_done'] % (result['vertices_changed'],result['output']))
            self.show_result(text, result)
        self.app.run(lambda: meshpack.build(self.browser.game,folder,out,mod_id='meshes.'+index['workspace_id'],
                                           name=name,author=author,version=version,model=model,topology=topology,piece=piece),done,on_error=self.failed)

    def dump_textures(self):
        row = self.row()
        if self.app.busy or not row:
            return
        self.export_textures([row['path']], row['member'])

    def dump_many(self):
        if self.app.busy:
            return
        files = filedialog.askopenfilenames(title=self.t['tex_pick'], parent=self.app.root,
                                          initialdir=self.browser.game / 'assets', filetypes=[('ZIP', '*.zip')])
        if not files:
            return
        try:
            archives = [Path(path).resolve().relative_to(self.browser.game).as_posix() for path in files]
            texpack.archive_paths(archives)
        except ValueError:
            self.failed(self.t['tex_outside']); return
        self.export_textures(archives)

    def export_textures(self, archives, member=None):
        options = TextureExportDialog(self.app.root, self.t, archives)
        if options.result is None:
            return
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent:
            return
        stem = Path(member or archives[0]).stem + '-textures' if len(archives) == 1 else 'texture-workspace'
        out = Path(parent) / stem
        n = 2
        while out.exists():
            out = Path(parent) / (stem + '-' + str(n)); n += 1
        def done(result):
            text = self.t['tex_done'] % (result['textures'], result['editable'], result['png_files'], result['archives'], result['output'])
            if result['errors']:
                text += '\n\n' + self.t['errors'] % len(result['errors'])
            self.show_result(text, result)
        self.app.run(lambda: texpack.dump(self.browser.game, archives, out, member, shared=options.result), done, on_error=self.failed)

    def build_textures(self):
        if self.app.busy:
            return
        folder = filedialog.askdirectory(title=self.t['tex_workspace'], parent=self.app.root)
        if not folder:
            return
        try:
            _, index = texpack.workspace(folder)
            import re
            if not re.fullmatch('[0-9a-f]{32}', index.get('workspace_id', '')):
                raise ValueError(self.t['tex_workspace'])
        except (ValueError, OSError) as e:
            self.failed(str(e)); return
        dialog = TexturePackDialog(self.app.root, self.t)
        if not dialog.result:
            return
        name, author, version = dialog.result
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent:
            return
        import re
        safe = re.sub('[^A-Za-z0-9 _-]', '_', name).strip()[:80] or 'texture-pack'
        out = Path(parent) / (safe + '-pack')
        n = 2
        while out.exists():
            out = Path(parent) / (safe + '-pack-' + str(n)); n += 1
        def done(result):
            text = self.t['tex_pack_done'] % (result['textures'], result['archives'], result['output'])
            self.show_result(text, result)
        self.app.run(lambda: texpack.build(self.browser.game, folder, out, mod_id='textures.' + index['workspace_id'],
                                           name=name, author=author, version=version), done, on_error=self.failed)

    def clear_preview(self):
        self.clear_result()
        self.stop_audio()
        self.audio_samples, self.audio_key = [], None
        self.audio_list.delete(*self.audio_list.get_children())
        self.audio_note.config(text=self.t['audio_hint'])
        self.audio_selected(stop=False)
        if self.view:
            self.view.release(); self.view = None
        self.images, self.character, self.photo = {}, None, None
        self.image_name.set(''); self.image_name.config(values=())
        # Remove View's mouse/resize callbacks along with its released GL context.
        self.image_label.destroy()
        self.image_label = ttk.Label(self.canvas, anchor='center', wraplength=400)
        self.image_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    def close(self):
        self.stop_audio()
        if self.view:
            self.view.release(); self.view = None

    def audio_selected(self, stop=True):
        if stop: self.stop_audio()
        selection = self.audio_list.selection()
        valid = bool(selection and self.audio_samples and self.audio_key == self.selected_key)
        for button in (self.audio_play, self.audio_save):
            button.state(['!disabled'] if valid and not self.app.busy else ['disabled'])
        if valid and not self.app.busy and stop:
            sample = self.audio_samples[int(selection[0])]
            channels = self.t['audio_channel'] if sample['channels'] == 1 else self.t['audio_channels'] % sample['channels']
            self.audio_note.config(text=self.t['audio_info'] % (sample['name'], sample['rate'], channels, sample['seconds']))

    def stop_audio(self):
        if self.audio_cancel is not None: self.audio_cancel.set()
        if self.audio_timer is not None:
            self.app.root.after_cancel(self.audio_timer); self.audio_timer = None
        self.player.stop()
        self.audio_progress['value'] = 0
        self.audio_status.config(text=self.t['audio_stopped'])
        self.audio_stop.state(['disabled'])

    def play_audio(self):
        selection = self.audio_list.selection()
        if self.app.busy or not selection or self.audio_key != self.selected_key: return
        self.stop_audio()
        path, member = self.audio_key
        track, seconds = int(selection[0]), int(self.audio_seconds.get())
        cancel = self.audio_cancel = threading.Event()
        self.audio_status.config(text=self.t['audio_work']); self.audio_stop.state(['!disabled'])
        def done(result):
            self.app.status.set(self.app.t('ready'))
            if cancel.is_set(): return
            data, report = result
            try: self.player.play(data)
            except (ValueError, OSError, RuntimeError) as e: self.audio_failed(str(e)); return
            self.audio_status.config(text=self.t['audio_playing'] % report['name'])
            if report['truncated']:
                self.audio_note.config(text=self.t['audio_excerpt'] % (report['decoded_seconds'], report['seconds']))
            started, duration = time.monotonic(), report['decoded_seconds']
            self.audio_progress['maximum'] = duration
            def tick():
                self.audio_timer = None
                elapsed = time.monotonic()-started
                if elapsed >= duration: self.stop_audio(); return
                self.audio_progress['value'] = elapsed
                self.audio_timer = self.app.root.after(100, tick)
            tick()
        def failed(message):
            if not cancel.is_set(): self.audio_failed(message)
            else: self.app.status.set(self.app.t('ready'))
        self.app.run(lambda: audiobank.decode(self.browser, path, member, track, seconds, cancel), done, on_error=failed)

    def audio_failed(self, message):
        self.clear_result()
        self.stop_audio(); self.audio_status.config(text=audiobank.error_text(message, self.app.lang))
        self.app.status.set(self.app.t('error'))

    def save_audio(self):
        selection = self.audio_list.selection()
        if self.app.busy or not selection or self.audio_key != self.selected_key: return
        parent = filedialog.askdirectory(title=self.t['folder'], parent=self.app.root)
        if not parent: return
        self.stop_audio()
        path, member = self.audio_key; track = int(selection[0]); seconds = int(self.audio_seconds.get())
        stem = Path(member or path).stem+'-sample-'+str(track); out, n = Path(parent)/stem, 2
        while out.exists(): out = Path(parent)/(stem+'-'+str(n)); n += 1
        def done(result):
            self.audio_status.config(text=self.t['saved'] % result['output'])
            self.show_result(self.t['saved'] % result['output'], result)
        self.app.run(lambda: audiobank.export(self.browser, path, member, out, track, seconds), done, on_error=self.audio_failed)


class TextureExportDialog(simpledialog.Dialog):
    def __init__(self, parent, words, archives):
        self.words, self.archives = words, archives
        super().__init__(parent, title=words['tex_dump'])

    def body(self, master):
        ttk.Label(master, text=self.words['tex_scope'] % len(self.archives), wraplength=620).pack(anchor='w', padx=10, pady=10)
        listing = tk.Text(master, width=75, height=min(5, len(self.archives)), wrap='word', relief='flat')
        listing.insert('1.0', '\n'.join(self.archives)); listing.config(state='disabled'); listing.pack(fill='x', padx=10)
        self.shared = tk.BooleanVar(value=False)
        option = ttk.Checkbutton(master, text=self.words['tex_shared'], variable=self.shared)
        option.pack(anchor='w', padx=10, pady=(16, 8))
        ttk.Label(master, text=self.words['tex_shared_help'], wraplength=620).pack(anchor='w', padx=10, pady=(0, 12))
        return option

    def buttonbox(self):
        bar = ttk.Frame(self); bar.pack(fill='x', padx=16, pady=(0, 12))
        ttk.Button(bar, text=self.words['tex_continue'], command=self.ok).pack(side='right')
        ttk.Button(bar, text=self.words['tex_cancel'], command=self.cancel).pack(side='right', padx=8)
        self.bind('<Return>', self.ok); self.bind('<Escape>', self.cancel)

    def apply(self):
        self.result = self.shared.get()


def piece_labels(rows,words):
    return ['%d: %s · '%(r['node'],r['name'])+words['mesh_piece_counts']%(r['vertices'],r['triangles']) for r in rows]


class MeshPieceDialog(simpledialog.Dialog):
    def __init__(self,parent,words,rows):
        self.words,self.rows=words,rows
        super().__init__(parent,title=words['mesh_piece_title'])
    def body(self,master):
        ttk.Label(master,text=self.words['mesh_piece_hint'],wraplength=540).pack(anchor='w',padx=10,pady=10)
        self.choice=ttk.Combobox(master,state='readonly',width=72,
                                values=[self.words['mesh_piece_all']]+piece_labels(self.rows,self.words))
        self.choice.current(0);self.choice.pack(fill='x',padx=10,pady=8);return self.choice
    def validate(self):
        at=self.choice.current()-1
        if at>=0 and not self.rows[at]['supported_layout']:
            messagebox.showerror(self.words['mesh_piece_title'],self.rows[at]['reason'],parent=self);return False
        return True
    def apply(self):
        at=self.choice.current()-1;self.result=dict(piece=self.rows[at]['node'] if at>=0 else None)


class TexturePackDialog(simpledialog.Dialog):
    def __init__(self, parent, words):
        self.words = words
        super().__init__(parent, title=words['tex_title'])

    def body(self, master):
        self.fields = []
        for i, (key, default) in enumerate((('tex_name', ''), ('tex_author', ''), ('tex_version', '1.0.0'))):
            ttk.Label(master, text=self.words[key]).grid(row=i, column=0, sticky='w', padx=8, pady=6)
            value = ttk.Entry(master, width=40); value.insert(0, default)
            value.grid(row=i, column=1, padx=8, pady=6); self.fields.append(value)
        if self.words.get('allow_topology'):
            self.topology=tk.BooleanVar(value=self.words.get('default_piece') is not None)
            ttk.Checkbutton(master,text=self.words['mesh_topology'],variable=self.topology).grid(
                row=3,column=0,columnspan=2,sticky='w',padx=8,pady=(16,6))
            ttk.Label(master,text=self.words['mesh_topology_help'],wraplength=500).grid(
                row=4,column=0,columnspan=2,sticky='w',padx=8,pady=(0,10))
            self.piece_rows=self.words.get('piece_rows',[])
            ttk.Label(master,text=self.words['mesh_piece']).grid(row=5,column=0,sticky='w',padx=8,pady=6)
            self.piece_box=ttk.Combobox(master,state='readonly',width=45,
                values=[self.words['mesh_piece_auto']]+piece_labels(self.piece_rows,self.words))
            at=next((i+1 for i,r in enumerate(self.piece_rows) if r['node']==self.words.get('default_piece')),0)
            self.piece_box.current(at);self.piece_box.grid(row=5,column=1,sticky='ew',padx=8,pady=6)
            def toggle(*args):self.piece_box.state(['!disabled','readonly'] if self.topology.get() else ['disabled'])
            self.topology.trace_add('write',toggle);toggle()
        return self.fields[0]

    def validate(self):
        values = [f.get().strip() for f in self.fields]
        from modfile import version
        try:
            if not all(values):
                raise ValueError()
            version(values[2])
        except ValueError:
            messagebox.showerror(self.words['tex_title'], self.words['tex_fields'], parent=self)
            return False
        if self.words.get('allow_topology'):
            at=self.piece_box.current()-1
            if (self.topology.get() and at<0 and len(self.piece_rows)>1) or (
                self.words.get('default_piece') is not None and not self.topology.get()):
                messagebox.showerror(self.words['tex_title'],self.words['mesh_piece_required'],parent=self);return False
            if self.topology.get() and at>=0 and not self.piece_rows[at]['supported_layout']:
                messagebox.showerror(self.words['tex_title'],self.piece_rows[at]['reason'],parent=self);return False
        return True

    def apply(self):
        self.result = [f.get().strip() for f in self.fields]
        if self.words.get('allow_topology'):
            at=self.piece_box.current()-1
            self.result+=['replace' if self.topology.get() else 'preserve',
                          self.piece_rows[at]['node'] if self.topology.get() and at>=0 else None]
