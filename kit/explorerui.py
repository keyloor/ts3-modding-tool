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

TEXT = {
    'es': dict(title='Explorador del juego', intro='Busca modelos, texturas y sonidos de tu copia del juego.',
               search='Buscar', all='Todos', refresh='Actualizar índice', inspect='Inspeccionar',
               preview='Vista previa', extract='Extraer…', export='Guardar vista previa…',
               glb='Exportar modelo GLB…', glb_done='Modelo exportado: %s\n\nPersonajes: ajuste normal o esqueleto original desde el proyecto. Objetos rígidos: usa «Exportar malla editable» para poder reinsertarlos.',
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
               audio_hint='Inspecciona un banco .assets.bank y elige una muestra. La escucha empieza al pulsar Reproducir.',
               audio_empty='Este banco no contiene muestras. Busca el archivo .assets.bank del mismo nombre.',
               audio_work='Decodificando la muestra… Puedes detener la operación.',
               audio_stopped='Detenido', audio_playing='Reproduciendo: %s',
               audio_info='%s · %d Hz · %d canales · %.2f s',
               audio_excerpt='Escucha de los primeros %.1f s de %.1f s.',
               kinds=('Archivo ZIP', 'OCT', 'Textura', 'Sonido', 'Malla', 'Texto', 'Otro')),
    'en': dict(title='Game explorer', intro='Find models, textures and sounds in your copy of the game.',
               search='Search', all='All', refresh='Refresh index', inspect='Inspect',
               preview='Preview', extract='Extract…', export='Save preview…',
               glb='Export GLB model…', glb_done='Model exported: %s\n\nCharacters: normal fitting or original skeleton from a project. Rigid objects: use Export editable mesh for reinsertion.',
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
               audio_hint='Inspect an .assets.bank and choose a sample. Audio starts only when you press Play.',
               audio_empty='This bank has no samples. Look for its matching .assets.bank file.',
               audio_work='Decoding sample… You can stop the operation.',
               audio_stopped='Stopped', audio_playing='Playing: %s',
               audio_info='%s · %d Hz · %d channels · %.2f s',
               audio_excerpt='Preview of the first %.1f s of %.1f s.',
               kinds=('ZIP archive', 'OCT', 'Texture', 'Sound', 'Mesh', 'Text', 'Other')),
}


class ExplorerPane:
    def __init__(self, app):
        self.app, self.t = app, TEXT[app.lang]
        self.browser = Browser(app.settings['game'])
        self.index = None
        self.selected_key = None
        self.rows, self.children = {}, {}
        self.images, self.character, self.view, self.photo = {}, None, None, None
        self.player, self.audio_cancel, self.audio_timer = audiobank.Player(), None, None
        self.audio_samples, self.audio_key = [], None
        self.frame = f = ttk.Frame(app.body, padding=(22, 16))
        f.pack(fill='both', expand=True)
        bar = ttk.Frame(f); bar.pack(fill='x')
        self.button(bar, app.t('back'), app.show_home).pack(side='left', padx=(0, 16))
        ttk.Label(bar, text=self.t['title'], style='Title.TLabel').pack(side='left')
        ttk.Label(f, text=self.t['intro'], style='Sub.TLabel').pack(anchor='w', pady=(6, 2))
        ttk.Label(f, text=str(self.browser.game), style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        bar = ttk.Frame(f); bar.pack(fill='x')
        self.query = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<Return>', lambda e: self.filter())
        self.category = ttk.Combobox(bar, values=(self.t['all'], *self.t['kinds']), state='readonly', width=16)
        self.category.current(0); self.category.pack(side='left', padx=8)
        self.category.bind('<<ComboboxSelected>>', lambda e: self.filter())
        self.button(bar, self.t['search'], self.filter).pack(side='left')
        self.button(bar, self.t['refresh'], lambda: self.reload(True)).pack(side='left', padx=(8, 0))
        self.note = ttk.Label(f, wraplength=1040, style='Muted.TLabel')
        self.note.pack(anchor='w', pady=8)
        split = ttk.Panedwindow(f, orient='horizontal'); split.pack(fill='both', expand=True)
        left = ttk.Frame(split); right = ttk.Frame(split)
        split.add(left, weight=1); split.add(right, weight=1)
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=('size',), selectmode='browse')
        self.tree.heading('#0', text=self.t['path']); self.tree.column('#0', width=390, minwidth=180)
        self.tree.heading('size', text=self.t['size']); self.tree.column('size', width=75, stretch=False, anchor='e')
        self.tree.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(left, command=self.tree.yview); sy.grid(row=0, column=1, sticky='ns')
        sx = ttk.Scrollbar(left, orient='horizontal', command=self.tree.xview); sx.grid(row=1, column=0, sticky='ew')
        self.tree.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.tree.bind('<<TreeviewOpen>>', self.expand)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.selected())
        self.tree.bind('<Double-1>', lambda e: self.inspect())
        self.tree.bind('<Button-1>', lambda e: 'break' if app.busy else None)
        self.tree.bind('<Key>', lambda e: 'break' if app.busy else None)
        self.tabs = ttk.Notebook(right); self.tabs.pack(fill='both', expand=True, padx=(12, 0))
        details = ttk.Frame(self.tabs); previews = ttk.Frame(self.tabs)
        self.tabs.add(details, text=self.t['details']); self.tabs.add(previews, text=self.t['images'])
        self.detail = tk.Text(details, wrap='word', font=('Consolas', 10), width=45, state='disabled')
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
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(12, 0))
        self.actions = []
        for key, fn in (('inspect', self.inspect), ('preview', self.preview),
                        ('extract', self.extract), ('export', lambda: self.extract(True))):
            b = self.button(bar, self.t[key], fn); b.pack(side='left', padx=(0, 8)); self.actions.append(b)
        self.glb_button = self.button(bar, self.t['glb'], self.export_glb)
        self.glb_button.pack(side='left')
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(8, 4))
        self.dump_button = self.button(bar, self.t['tex_dump'], self.dump_textures)
        self.dump_button.pack(side='left', padx=(0, 8))
        self.button(bar, self.t['tex_many'], self.dump_many).pack(side='left', padx=(0, 8))
        self.button(bar, self.t['tex_build'], self.build_textures).pack(side='left')
        ttk.Label(f, text=self.t['tex_help'], style='Muted.TLabel', wraplength=1000).pack(anchor='w')
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(8, 4))
        self.mesh_button = self.button(bar, self.t['mesh_dump'], self.dump_mesh)
        self.mesh_button.pack(side='left', padx=(0, 8))
        self.button(bar, self.t['mesh_build'], self.build_mesh).pack(side='left')
        ttk.Label(f, text=self.t['mesh_help'], wraplength=1000, style='Muted.TLabel').pack(anchor='w')
        self.set_details(self.t['select'])
        self.reload()

    def button(self, parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        self.app.buttons.append(b)
        return b

    def set_details(self, text):
        self.detail.config(state='normal'); self.detail.delete('1.0', 'end')
        self.detail.insert('end', text); self.detail.config(state='disabled')

    def reload(self, refresh=False):
        if not self.app.busy:
            self.app.run(lambda: self.browser.index(refresh), self.loaded, on_error=self.failed)

    def loaded(self, index):
        self.index = index
        self.filter()
        if index['errors']:
            self.set_details('\n'.join(e['path'] + '\n' + e['message'] for e in index['errors']))
        self.app.status.set(self.app.t('ready'))

    def filter(self):
        if self.app.busy or self.index is None:
            return
        self.clear_preview()
        self.tree.delete(*self.tree.get_children())
        self.rows, self.children = {}, {}
        cat = self.category.current()
        query = self.query.get().strip()
        rows = self.browser.search(self.index, query, KINDS[cat - 1] if cat > 0 else None)
        # Unfiltered archives expand lazily: the complete game can have hundreds of thousands of members.
        filtered = bool(query or cat > 0)
        visible = rows if filtered else [r for r in rows if r['member'] is None]
        for row in (visible[:2000] if filtered else visible):
            iid = self.add('', row, row['path'] + (' / ' + row['member'] if row['member'] else ''))
            if not filtered and row['kind'] == 'archive':
                self.children[iid] = [dict(e, path=row['path']) for e in self.index['files'][row['path']]['entries']]
                if self.children[iid]:
                    self.tree.insert(iid, 'end', text='…')
        note = self.t['count'] % (len(rows), self.index['reused'])
        if filtered and len(visible) > 2000:
            note += '\n' + self.t['limited']
        if self.index['errors']:
            note += '\n' + self.t['errors'] % len(self.index['errors'])
        self.note.config(text=note)
        self.set_details(self.t['select'])
        self.selected()

    def add(self, parent, row, text):
        iid = self.tree.insert(parent, 'end', text=text, values=('%.1f' % (row['size'] / 1024),))
        self.rows[iid] = row
        return iid

    def expand(self, event=None):
        iid = self.tree.focus()
        if iid in self.children:
            self.tree.delete(*self.tree.get_children(iid))
            for row in self.children.pop(iid):
                self.add(iid, row, row['member'])

    def row(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def selected(self):
        row = self.row()
        key = (row['path'], row['member']) if row else None
        if key != self.selected_key:
            self.selected_key = key
            self.clear_preview()
            self.set_details((row['path'] + ('\n' + row['member'] if row['member'] else '') + '\n\n'
                              if row else '') + self.t['select'])
        for b in self.actions:
            b.state(['!disabled'] if row and not self.app.busy else ['disabled'])
        can_dump = row and ((row['member'] is None and row['path'].lower().endswith('.zip'))
                            or (row['member'] or '').lower().endswith('.oct'))
        self.dump_button.state(['!disabled'] if can_dump and not self.app.busy else ['disabled'])
        self.glb_button.state(['!disabled'] if can_dump and not self.app.busy else ['disabled'])
        can_mesh = row and row.get('member') and row['member'].lower().endswith('.oct')
        self.mesh_button.state(['!disabled'] if can_mesh and not self.app.busy else ['disabled'])
        self.audio_selected(stop=False)

    def inspect(self):
        row = self.row()
        if self.app.busy or not row:
            return
        self.clear_preview()
        self.tabs.select(0)
        self.app.run(lambda: self.browser.inspect(row['path'], row['member']),
                     self.details_ready, on_error=self.failed)

    def details_ready(self, result):
        self.set_details(json.dumps(result, indent=2, ensure_ascii=False))
        if result['kind'] == 'sound':
            self.audio_key = (result['path'], result['member'])
            self.audio_samples = result.get('sounds', [])
            for s in self.audio_samples:
                self.audio_list.insert('', 'end', iid=str(s['index']), text=s['name'], values=('%.2f s' % s['seconds'],))
            self.audio_note.config(text=self.t['audio_hint'] if self.audio_samples else self.t['audio_empty'])
            if self.audio_samples: self.audio_list.selection_set('0')
            self.tabs.select(self.audio_tab)
            self.audio_selected()
        self.app.status.set(self.app.t('ready'))

    def preview(self):
        row = self.row()
        if self.app.busy or not row:
            return
        if row['kind'] == 'sound':
            self.inspect(); return
        self.clear_preview()
        self.tabs.select(1)
        self.image_label.config(text=self.app.t('working'))
        self.app.run(lambda: self.browser.preview(row['path'], row['member']), self.preview_ready, on_error=self.failed)

    def preview_ready(self, result):
        self.images, self.character = result
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
                     lambda result: self.app.status.set(self.t['saved'] % result['output']), on_error=self.failed)

    def failed(self, message):
        self.set_details(message)
        self.tabs.select(0)
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
            self.set_details(self.t['glb_done'] % result['output'] + '\n\n' + json.dumps(result, ensure_ascii=False, indent=2))
            self.tabs.select(0); self.app.status.set(self.app.t('ready'))
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
            self.set_details(self.t['mesh_done'] % result['output']+'\n\n'+json.dumps(result,ensure_ascii=False,indent=2))
            self.tabs.select(0); self.app.status.set(self.app.t('ready'))
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
            self.set_details((self.t['mesh_piece_selected']%result['piece_name'])+self.t['mesh_topology_done'] % (result['vertices_before'],result['vertices_after'],
                             result['triangles_before'],result['triangles_after'],result['output']) if topology=='replace' else
                             self.t['mesh_pack_done'] % (result['vertices_changed'],result['output']))
            self.tabs.select(0); self.app.status.set(self.app.t('ready'))
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
                text += '\n\n' + json.dumps(result['errors'], ensure_ascii=False, indent=2)
            self.set_details(text); self.tabs.select(0)
            self.app.status.set(self.app.t('ready'))
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
            self.set_details(text); self.tabs.select(0); self.app.status.set(self.app.t('ready'))
        self.app.run(lambda: texpack.build(self.browser.game, folder, out, mod_id='textures.' + index['workspace_id'],
                                           name=name, author=author, version=version), done, on_error=self.failed)

    def clear_preview(self):
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
            self.audio_note.config(text=self.t['audio_info'] % (sample['name'], sample['rate'], sample['channels'], sample['seconds']))

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
        self.stop_audio(); self.audio_status.config(text=message)
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
        self.app.run(lambda: audiobank.export(self.browser, path, member, out, track, seconds),
                     lambda result: self.audio_status.config(text=self.t['saved'] % result['output']), on_error=self.audio_failed)


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
