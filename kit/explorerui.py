"""The explorer screen. File operations run through App.run, never on Tk's thread."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog

from PIL import ImageTk
from explorer import Browser, KINDS
import viewer

TEXT = {
    'es': dict(title='Explorador del juego', intro='Busca modelos, texturas y sonidos de tu copia del juego.',
               search='Buscar', all='Todos', refresh='Actualizar índice', inspect='Inspeccionar',
               preview='Vista previa', extract='Extraer…', export='Guardar vista previa…',
               path='Archivo / contenido', size='KiB', details='Detalles', images='Vista previa',
               select='Selecciona un archivo y pulsa Inspeccionar o Vista previa.',
               count='%d resultados · %d archivos leídos desde caché',
               limited='Mostrando los primeros 2000. Escribe una búsqueda más específica.',
               errors='%d archivos no se pudieron indexar. Detalles en el panel.',
               folder='Elige dónde crear la carpeta de extracción', saved='Guardado en: %s',
               unsupported='Este archivo aún no tiene vista previa. Puedes inspeccionarlo o extraerlo.',
               controls='Arrastra para girar · botón derecho para mover · rueda para acercar',
               kinds=('Archivo ZIP', 'OCT', 'Textura', 'Sonido', 'Malla', 'Texto', 'Otro')),
    'en': dict(title='Game explorer', intro='Find models, textures and sounds in your copy of the game.',
               search='Search', all='All', refresh='Refresh index', inspect='Inspect',
               preview='Preview', extract='Extract…', export='Save preview…',
               path='File / contents', size='KiB', details='Details', images='Preview',
               select='Select a file and choose Inspect or Preview.',
               count='%d results · %d files read from cache',
               limited='Showing the first 2000. Enter a more specific search.',
               errors='%d files could not be indexed. See the details panel.',
               folder='Choose where to create the extraction folder', saved='Saved to: %s',
               unsupported='This asset does not have a supported preview yet. You can inspect or extract it.',
               controls='Drag to orbit · right drag to pan · wheel to zoom',
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
        bar = ttk.Frame(f); bar.pack(fill='x', pady=(12, 0))
        self.actions = []
        for key, fn in (('inspect', self.inspect), ('preview', self.preview),
                        ('extract', self.extract), ('export', lambda: self.extract(True))):
            b = self.button(bar, self.t[key], fn); b.pack(side='left', padx=(0, 8)); self.actions.append(b)
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
        self.app.status.set(self.app.t('ready'))

    def preview(self):
        row = self.row()
        if self.app.busy or not row:
            return
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

    def clear_preview(self):
        if self.view:
            self.view.release(); self.view = None
        self.images, self.character, self.photo = {}, None, None
        self.image_name.set(''); self.image_name.config(values=())
        # Remove View's mouse/resize callbacks along with its released GL context.
        self.image_label.destroy()
        self.image_label = ttk.Label(self.canvas, anchor='center', wraplength=400)
        self.image_label.place(relx=0, rely=0, relwidth=1, relheight=1)

    def close(self):
        if self.view:
            self.view.release(); self.view = None
