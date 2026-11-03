"""Player-facing mod manager. All installation/backup behavior lives in the shared Store."""
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlsplit
import webbrowser

from about import AUTHOR, LOADER, TOOL, VERSION
from dropfiles import DropTarget
import gamepaths
import loaderprefs
from modfile import ModError
from modstore import Store, JOURNAL
import modupdate
import modpriorityui

TEXT = {
    'es': dict(subtitle='Tus mods, en un solo lugar.', game='Juego', found='Toy Story 3 detectado',
               missing='Elige la carpeta donde instalaste Toy Story 3.', change='Elegir carpeta…',
               install='Instalar mod…', folder='Instalar desde carpeta…', drop='También puedes arrastrar aquí un ZIP o una carpeta.',
               title='Mis mods', search='Buscar', name='Mod', version='Versión', author='Autor', state='Estado',
               active='Instalado', count='%d instalados', empty='Todavía no tienes mods instalados',
               empty_help='Elige un paquete ZIP o arrástralo a esta ventana para empezar.',
               no_match='No hay resultados', no_match_help='Prueba con otro nombre o autor.',
               select='Selecciona un mod', select_help='Aquí verás su descripción y las opciones para gestionarlo.',
               remove='Quitar mod', verify='Verificar archivos', files='Archivos que cambia', unknown='Sin indicar',
               updates='Buscar actualizaciones', page='Ver actualización', available='Actualización disponible',
               more='Más opciones', refresh='Recargar lista', about='Acerca de',
               scope='Compatible con la Modding Tool: ambas aplicaciones comparten tus mods y copias.',
               ready='Listo', working='Un momento…', busy='Espera a que termine la operación actual.',
               review='Revisar instalación', review_note='Cierra el juego antes de instalar. Guardaremos una copia de los archivos que cambien.',
               confirm='Instalar este mod', cancel='Cancelar', size='%d archivos · %.1f MiB',
               replace_review='Revisar reemplazo', replace_confirm='Reemplazar este mod',
               replace_note='Reemplaza la versión %s por la %s, conservando su prioridad y las copias originales.',
               replaced='«%s» se ha reemplazado.', restored_file='Restaurar estado anterior: %s',
               installed='«%s» está instalado.', removed='«%s» se ha quitado y sus archivos anteriores se han restaurado.',
               remove_question='¿Quitar «%s»? Se reconstruirán los mods restantes y se restaurarán los destinos sin capas.\n\nCierra Toy Story 3 primero.',
               pending='Hay un cambio interrumpido. Recupéralo antes de instalar o quitar mods.',
               recover='Recuperar cambios', recover_question='¿Restaurar el estado anterior al cambio interrumpido? Cierra el juego primero.',
               recovered='Recuperación terminada.', verified='Los archivos de «%s» y sus copias están correctos.',
               unhealthy='Algunos archivos o copias han cambiado. Consulta los detalles antes de quitar este mod.',
               new_updates='%d mods tienen una versión nueva. Selecciónalos para abrir su página.',
               no_updates='No hay versiones nuevas disponibles.', no_sources='Estos mods no indican una página de actualizaciones.',
               details='Ver detalles', error='No se pudo completar la operación', one='Elige un solo ZIP o carpeta cada vez.',
               failed_game='No encontramos el juego. Elige su carpeta (la que contiene assets y data_dx).',
               prefs='No se pudieron guardar tus preferencias. Puedes seguir usando esta sesión.',
               about_text='%s %s\nAutor: %s\n\nToy Story 3 Modding Tool by keyloor\nSoftware libre, GPL v3.\nAplicación de fans, sin afiliación con Disney/Pixar.\n\nInstala y restaura con el mismo gestor que la Modding Tool.',
               errors=dict(file_conflict='Otro mod ya cambia uno de estos archivos. Quítalo antes de instalar este paquete.',
                           external_change='Un archivo cambió fuera del gestor. Lo hemos conservado; no lo sobrescribas.',
                           already_installed='Este mod ya está instalado. Quítalo antes de instalar otra versión.',
                           game_running='Cierra Toy Story 3 y vuelve a intentarlo.',
                           missing_dependency='Falta otro mod que este paquete necesita.',
                           declared_conflict='Este paquete no es compatible con uno de tus mods instalados.',
                           dependent_installed='Primero quita los mods que dependen de este.',
                           dependent_version='La nueva versión no cumple lo que necesita otro mod instalado. Consulta los detalles.',
                           dependency_cycle='Estos mods dependerían uno del otro y no podrían quitarse. Consulta los detalles.',
                           backup_damaged='Falta una copia de seguridad o está dañada. Conserva los archivos y consulta los detalles.',
                           plan_changed='El paquete o el juego cambió desde la revisión. Elige el paquete otra vez.',
                           recovery_required='Hay un cambio interrumpido. Pulsa Recuperar cambios.',
                           game_not_found='Elige la carpeta de Toy Story 3 antes de continuar.',
                           io_error='No pudimos acceder a un archivo. Consulta los detalles y comprueba la carpeta elegida.')),
    'en': dict(subtitle='Your mods, all in one place.', game='Game', found='Toy Story 3 found',
               missing='Choose the folder where you installed Toy Story 3.', change='Choose folder…',
               install='Install mod…', folder='Install from folder…', drop='You can also drop a ZIP or folder here.',
               title='My mods', search='Search', name='Mod', version='Version', author='Author', state='Status',
               active='Installed', count='%d installed', empty='No mods installed yet',
               empty_help='Choose a ZIP package or drop it onto this window to get started.',
               no_match='No results', no_match_help='Try another name or author.',
               select='Select a mod', select_help='Its description and management options will appear here.',
               remove='Remove mod', verify='Verify files', files='Files it changes', unknown='Not specified',
               updates='Check for updates', page='View update', available='Update available',
               more='More options', refresh='Refresh list', about='About',
               scope='Works with the Modding Tool: both apps share your mods and backups.',
               ready='Ready', working='One moment…', busy='Wait for the current operation to finish.',
               review='Review installation', review_note='Close the game before installing. We will back up every file that changes.',
               confirm='Install this mod', cancel='Cancel', size='%d files · %.1f MiB',
               replace_review='Review replacement', replace_confirm='Replace this mod',
               replace_note='Replaces version %s with %s, keeping its priority and original backups.',
               replaced='“%s” was replaced.', restored_file='Restore previous state: %s',
               installed='“%s” is installed.', removed='“%s” was removed and its previous files were restored.',
               remove_question='Remove “%s”? Remaining mods will be rebuilt; targets with no layers return to their original state.\n\nClose Toy Story 3 first.',
               pending='An interrupted change needs recovery before you install or remove mods.',
               recover='Recover changes', recover_question='Restore the state before the interrupted change? Close the game first.',
               recovered='Recovery complete.', verified='The files and backups for “%s” are correct.',
               unhealthy='Some files or backups have changed. Read the details before removing this mod.',
               new_updates='%d mods have a newer version. Select them to open their release page.',
               no_updates='No newer versions are available.', no_sources='These mods do not provide an update source.',
               details='View details', error='The operation could not be completed', one='Choose one ZIP or folder at a time.',
               failed_game='Game not found. Choose its folder (the one containing assets and data_dx).',
               prefs='Your preferences could not be saved. You can keep using this session.',
               about_text='%s %s\nAuthor: %s\n\nToy Story 3 Modding Tool by keyloor\nFree software, GPL v3.\nFan-made, not affiliated with Disney/Pixar.\n\nInstalls and restores with the same manager as the Modding Tool.',
               errors=dict(file_conflict='Another mod already changes one of these files. Remove it before installing this package.',
                           external_change='A file changed outside the manager. It has been preserved; do not overwrite it.',
                           already_installed='This mod is already installed. Remove it before installing another version.',
                           game_running='Close Toy Story 3 and try again.',
                           missing_dependency='Another mod required by this package is missing.',
                           declared_conflict='This package conflicts with one of your installed mods.',
                           dependent_installed='Remove the mods that depend on this one first.',
                           dependent_version='The new version does not meet another installed mod’s requirements. Read the details.',
                           dependency_cycle='These mods would depend on each other and could not be removed. Read the details.',
                           backup_damaged='A backup is missing or damaged. Preserve the files and read the details.',
                           plan_changed='The package or game changed after review. Choose the package again.',
                           recovery_required='An interrupted change needs recovery. Choose Recover changes.',
                           game_not_found='Choose your Toy Story 3 folder before continuing.',
                           io_error='A file could not be accessed. Read the details and check the selected folder.')),
}

COLOURS = dict(bg='#F4F6F9', surface='#FFFFFF', ink='#172B45', muted='#526277',
               accent='#155DB1', hover='#104A90', border='#DCE3EC', soft='#E8F0FC',
               danger='#AC2430', warn='#8B4C00', success='#176343')


class LoaderApp:
    def __init__(self, root, package=None):
        self.root = root
        prefs = loaderprefs.read()
        self.lang = prefs.get('lang') if prefs.get('lang') in TEXT else 'es'
        self.game = prefs.get('game')
        self.records, self.updates = {}, {}
        self.health = {}
        self.pending = self.busy = False
        self.error_detail = ''
        self.drop_target = None
        self.queue = queue.Queue()
        self.pending_package = package
        root.title('%s — %s by %s' % (LOADER, TOOL, AUTHOR))
        root.geometry(os.environ.get('TS3TOOL_GEOMETRY', '1100x800'))
        root.minsize(940, 740)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-o>', lambda e: self.choose_package())
        root.bind('<Control-r>', lambda e: self.reload())
        self.styles()
        self.build()
        root.after(80, self.poll)
        self.reload()

    def t(self, key):
        return TEXT[self.lang][key]

    def styles(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('Loader.TFrame', background=COLOURS['bg'])
        s.configure('Card.TFrame', background=COLOURS['surface'], bordercolor=COLOURS['border'], relief='solid', borderwidth=1)
        s.configure('Loader.TLabel', font=('Segoe UI', 10), background=COLOURS['bg'], foreground=COLOURS['ink'])
        s.configure('Muted.Loader.TLabel', foreground=COLOURS['muted'])
        s.configure('Title.Loader.TLabel', font=('Segoe UI', 23, 'bold'))
        s.configure('Heading.Loader.TLabel', font=('Segoe UI', 14, 'bold'))
        s.configure('Card.TLabel', font=('Segoe UI', 10), background=COLOURS['surface'], foreground=COLOURS['ink'])
        s.configure('CardTitle.TLabel', font=('Segoe UI', 14, 'bold'), background=COLOURS['surface'], foreground=COLOURS['ink'])
        s.configure('Loader.TButton', font=('Segoe UI', 10), padding=(12, 9), background='white',
                    foreground=COLOURS['ink'], bordercolor=COLOURS['border'], lightcolor=COLOURS['border'],
                    darkcolor=COLOURS['border'], relief='solid', borderwidth=1)
        s.map('Loader.TButton', background=[('active', COLOURS['soft'])], foreground=[('disabled', COLOURS['muted'])])
        s.configure('Primary.Loader.TButton', foreground='white', background=COLOURS['accent'], borderwidth=0, padding=(18, 11))
        s.map('Primary.Loader.TButton', background=[('disabled', '#D4DFEE'), ('active', COLOURS['hover'])],
              foreground=[('disabled', COLOURS['muted'])])
        s.configure('Danger.Loader.TButton', foreground=COLOURS['danger'])
        s.configure('Loader.Treeview', font=('Segoe UI', 10), rowheight=48, borderwidth=0,
                    background='white', fieldbackground='white', foreground=COLOURS['ink'])
        s.configure('Loader.Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=(8, 12), background=COLOURS['bg'])
        s.map('Loader.Treeview', background=[('selected', COLOURS['soft'])], foreground=[('selected', COLOURS['ink'])])

    def button(self, parent, text, command, style='Loader.TButton'):
        b = ttk.Button(parent, text=text, command=command, style=style)
        self.controls.append(b)
        return b

    def build(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.controls = []
        self.root.configure(background=COLOURS['bg'])
        main = ttk.Frame(self.root, style='Loader.TFrame', padding=24)
        main.pack(fill='both', expand=True)
        header = ttk.Frame(main, style='Loader.TFrame'); header.pack(fill='x')
        title = ttk.Frame(header, style='Loader.TFrame'); title.pack(side='left')
        ttk.Label(title, text=LOADER, style='Title.Loader.TLabel').pack(anchor='w')
        ttk.Label(title, text=self.t('subtitle'), style='Muted.Loader.TLabel').pack(anchor='w', pady=(3, 0))
        self.language = ttk.Combobox(header, values=('Español', 'English'), state='readonly', width=10)
        self.language.current(0 if self.lang == 'es' else 1); self.language.pack(side='right', padx=(8, 0))
        self.language.bind('<<ComboboxSelected>>', lambda e: self.set_language())
        self.button(header, self.t('about'), self.about).pack(side='right')
        gamecard = ttk.Frame(main, style='Card.TFrame', padding=(16, 12)); gamecard.pack(fill='x', pady=(20, 16))
        self.game_button = self.button(gamecard, self.t('change'), self.choose_game)
        self.game_button.pack(side='right', padx=(16, 0))
        self.game_name = ttk.Label(gamecard, text=self.t('found') if self.game else self.t('game'), style='Card.TLabel')
        self.game_name.pack(anchor='w')
        self.game_path = ttk.Label(gamecard, text=self.game or self.t('missing'), style='Card.TLabel', wraplength=760)
        self.game_path.pack(anchor='w', pady=(3, 0))
        actions = ttk.Frame(main, style='Loader.TFrame'); actions.pack(fill='x')
        self.install_button = self.button(actions, self.t('install'), self.choose_package, 'Primary.Loader.TButton')
        self.install_button.pack(side='left')
        ttk.Label(actions, text=self.t('drop'), style='Muted.Loader.TLabel').pack(side='left', padx=14)
        more = ttk.Menubutton(actions, text=self.t('more'), style='Loader.TButton')
        menu = tk.Menu(more, tearoff=False)
        menu.add_command(label=self.t('folder'), command=lambda: self.choose_package(folder=True))
        menu.add_command(label=self.t('refresh'), command=self.reload)
        more.config(menu=menu); more.pack(side='right'); self.controls.append(more)
        self.update_button = self.button(actions, self.t('updates'), self.check_updates)
        self.update_button.pack(side='right', padx=(0, 8))
        self.notice = ttk.Frame(main, style='Loader.TFrame'); self.notice.pack(fill='x', pady=(10, 8))
        self.banner = ttk.Label(self.notice, style='Loader.TLabel', wraplength=840); self.banner.pack(side='left', fill='x', expand=True)
        self.recover_button = self.button(self.notice, self.t('recover'), self.recover)
        self.details_button = self.button(self.notice, self.t('details'), self.show_error)
        row = ttk.Frame(main, style='Loader.TFrame'); row.pack(fill='x', pady=(8, 10))
        ttk.Label(row, text=self.t('title'), style='Heading.Loader.TLabel').pack(side='left')
        self.counter = ttk.Label(row, style='Muted.Loader.TLabel'); self.counter.pack(side='left', padx=12)
        self.priority_button = self.button(row, modpriorityui.TEXT[self.lang]['title'], self.priorities)
        self.priority_button.pack(side='left', padx=(0, 8))
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(row, textvariable=self.search, width=27, font=('Segoe UI', 10))
        self.search_entry.pack(side='right')
        ttk.Label(row, text=self.t('search'), style='Loader.TLabel').pack(side='right', padx=8)
        self.search.trace_add('write', lambda *args: self.filter())
        pane = self.main_pane = ttk.Panedwindow(main, orient='horizontal'); pane.pack(fill='both', expand=True)
        left = ttk.Frame(pane, style='Card.TFrame'); right = ttk.Frame(pane, style='Card.TFrame', padding=18)
        pane.add(left, weight=3); pane.add(right, weight=1)
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=('priority', 'name', 'version', 'author', 'state'), show='headings',
                                 selectmode='browse', style='Loader.Treeview')
        for key, width in (('priority', 85), ('name', 210), ('version', 70), ('author', 90), ('state', 105)):
            self.tree.heading(key, text=modpriorityui.TEXT[self.lang]['priority'] if key == 'priority' else self.t(key))
            self.tree.column(key, width=width, minwidth=55, stretch=key == 'name')
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(left, command=self.tree.yview); scroll.grid(row=0, column=1, sticky='ns')
        self.tree.config(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.selected())
        self.tree.bind('<Button-1>', lambda e: 'break' if self.busy else None)
        self.tree.bind('<Key>', lambda e: 'break' if self.busy else None)
        self.tree.bind('<Delete>', lambda e: self.remove())
        self.empty = ttk.Frame(left, style='Card.TFrame', padding=28)
        self.empty_title = ttk.Label(self.empty, style='CardTitle.TLabel', wraplength=400)
        self.empty_title.pack(anchor='w', pady=(35, 10))
        self.empty_note = ttk.Label(self.empty, style='Card.TLabel', wraplength=400); self.empty_note.pack(anchor='w')
        detail_actions = tk.Frame(right, background=COLOURS['surface']); detail_actions.pack(side='bottom', fill='x')
        self.detail_title = ttk.Label(right, style='CardTitle.TLabel', wraplength=260); self.detail_title.pack(anchor='w')
        self.detail_meta = ttk.Label(right, style='Card.TLabel', wraplength=260); self.detail_meta.pack(anchor='w', pady=(6, 14))
        self.description = tk.Text(right, width=27, height=4, wrap='word', relief='flat', background='white',
                                   foreground=COLOURS['ink'], font=('Segoe UI', 10), state='disabled')
        self.description.pack(fill='x')
        ttk.Separator(right).pack(fill='x', pady=14)
        ttk.Label(right, text=self.t('files'), style='Card.TLabel').pack(anchor='w')
        self.file_list = tk.Text(right, width=27, height=5, wrap='word', relief='flat',
                                  background='white', foreground=COLOURS['muted'], font=('Segoe UI', 9), state='disabled')
        self.file_list.pack(fill='both', expand=True, pady=(6, 12))
        self.page_button = self.button(detail_actions, self.t('page'), self.open_update)
        self.verify_button = self.button(detail_actions, self.t('verify'), self.verify)
        self.verify_button.pack(fill='x', pady=(0, 8))
        self.remove_button = self.button(detail_actions, self.t('remove'), self.remove, 'Danger.Loader.TButton')
        self.remove_button.pack(fill='x')
        footer = ttk.Frame(main, style='Loader.TFrame'); footer.pack(side='bottom', fill='x', pady=(10, 0), before=pane)
        ttk.Label(footer, text='by %s · v%s' % (AUTHOR, VERSION), style='Muted.Loader.TLabel').pack(side='right')
        ttk.Label(footer, text=self.t('scope'), style='Muted.Loader.TLabel', wraplength=740).pack(side='left')
        self.status = tk.StringVar(value=self.t('ready'))
        ttk.Label(main, textvariable=self.status, style='Muted.Loader.TLabel').pack(side='bottom', anchor='w', pady=(8, 0), before=pane)
        self.spinner = ttk.Progressbar(main, mode='indeterminate', length=180)
        self.filter()
        self.refresh_controls()
        self.root.after_idle(self.setup_drop)

    def set_language(self):
        if self.busy:
            return
        self.lang = 'es' if self.language.current() == 0 else 'en'
        self.save_prefs(lang=self.lang)
        self.build()
        if self.pending:
            self.show_notice(self.t('pending'), warning=True)

    def save_prefs(self, **changes):
        try:
            loaderprefs.save(**changes)
        except (ValueError, OSError):
            self.status.set(self.t('prefs'))

    def run(self, job, done, failure=None):
        if self.busy:
            return
        self.busy = True
        self.status.set(self.t('working'))
        self.spinner.pack(side='bottom', anchor='w', pady=(4, 0), before=self.main_pane); self.spinner.start(12)
        self.refresh_controls()
        def worker():
            try:
                self.queue.put(('done', done, job()))
            except Exception as e:
                self.queue.put(('error', failure, e))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, callback, value = self.queue.get_nowait()
                if kind == 'drop':
                    self.dropped(value); continue
                self.busy = False
                self.spinner.stop(); self.spinner.pack_forget()
                self.status.set(self.t('ready'))
                if kind == 'done':
                    callback(value)
                elif callback:
                    callback(value)
                else:
                    self.failed(value)
                self.refresh_controls()
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def reload(self, notice=None, select_id=None, given=None):
        if self.busy or self.root.grab_current():
            return
        current = select_id or self.current_id()
        def read():
            try:
                game = gamepaths.find_game(given or self.game)
            except gamepaths.GameNotFound:
                if given:
                    raise
                game = gamepaths.find_game()
            store = Store(game)
            pending = store.path(JOURNAL).exists()
            rows = [] if pending else store.list()
            updates = modupdate.check(rows, str(store.path(modupdate.CACHE)), fetch=None)
            return game, pending, rows, updates
        def done(result):
            self.game, self.pending, rows, updates = result
            self.save_prefs(game=self.game)
            self.records = {r['metadata']['id']: r for r in rows}
            self.updates = {u['id']: u for u in updates}
            self.game_name.config(text=self.t('found')); self.game_path.config(text=self.game)
            self.filter(current)
            self.show_notice(self.t('pending') if self.pending else notice or '', warning=self.pending)
            if self.pending_package and not self.pending:
                package, self.pending_package = self.pending_package, None
                self.root.after_idle(lambda: self.choose_package(package))
        def failure(error):
            if isinstance(error, gamepaths.GameNotFound):
                if not given:
                    self.game = None
                    self.records = {}; self.updates = {}; self.filter()
                    self.game_name.config(text=self.t('game')); self.game_path.config(text=self.t('missing'))
                self.show_notice(self.t('failed_game'), warning=True)
            else:
                self.failed(error)
        self.run(read, done, failure)

    def choose_game(self):
        if self.busy or self.root.grab_current():
            return
        folder = filedialog.askdirectory(parent=self.root, title=self.t('change'), initialdir=self.game or None)
        if folder:
            self.reload(given=folder)

    def current_id(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def filter(self, select_id=None):
        if self.busy:
            return
        selected = select_id or self.current_id()
        text = self.search.get().casefold().strip()
        self.tree.delete(*self.tree.get_children())
        count = 0
        for mid, record in self.records.items():
            meta = record['metadata']
            if text and text not in ' '.join(str(meta.get(k, '')) for k in ('name', 'author', 'description')).casefold():
                continue
            state = self.t('available') if self.updates.get(mid, {}).get('update') else self.health.get(mid, self.t('active'))
            self.tree.insert('', 'end', iid=mid, values=(record.get('priority', 0), meta['name'], meta['version'], meta['author'] or self.t('unknown'), state))
            count += 1
        self.counter.config(text=self.t('count') % len(self.records))
        if count:
            self.empty.grid_remove(); self.tree.grid();
            if selected in self.tree.get_children():
                self.tree.selection_set(selected)
        else:
            self.tree.grid_remove(); self.empty.grid(row=0, column=0, sticky='nsew')
            self.empty_title.config(text=self.t('no_match') if text else self.t('empty'))
            self.empty_note.config(text=self.t('no_match_help') if text else self.t('empty_help'))
        self.selected()

    def selected(self):
        record = self.records.get(self.current_id())
        meta = record['metadata'] if record else None
        self.detail_title.config(text=meta['name'] if meta else self.t('select'))
        self.detail_meta.config(text=('%s · %s' % (meta['version'], meta['author'] or self.t('unknown'))) if meta else '')
        self.description.config(state='normal'); self.description.delete('1.0', 'end')
        self.description.insert('1.0', meta['description'] or self.t('active') if meta else self.t('select_help'))
        self.description.config(state='disabled')
        self.file_list.config(state='normal'); self.file_list.delete('1.0', 'end')
        if record:
            self.file_list.insert('1.0', '\n'.join(f['path'] for f in record['files']))
        self.file_list.config(state='disabled')
        self.refresh_controls()

    def refresh_controls(self):
        for button in self.controls:
            button.state(['disabled'] if self.busy else ['!disabled'])
        self.language.config(state='disabled' if self.busy else 'readonly')
        self.search_entry.state(['disabled'] if self.busy else ['!disabled'])
        ready = bool(self.game) and not self.pending and not self.busy
        self.install_button.state(['!disabled'] if ready else ['disabled'])
        self.update_button.state(['!disabled'] if ready and self.records else ['disabled'])
        self.priority_button.state(['!disabled'] if ready and len(self.records) > 1 else ['disabled'])
        selected = bool(self.current_id() in self.records)
        for b in (self.remove_button, self.verify_button):
            b.state(['!disabled'] if ready and selected else ['disabled'])
        self.recover_button.pack_forget()
        if self.pending:
            self.recover_button.pack(side='right', padx=(8, 0))
            self.recover_button.state(['disabled'] if self.busy else ['!disabled'])
        self.page_button.pack_forget()
        if self.updates.get(self.current_id(), {}).get('update'):
            self.page_button.pack(fill='x', before=self.verify_button, pady=(0, 8))

    def show_notice(self, text, warning=False):
        self.banner.config(text=text, foreground=COLOURS['warn'] if warning else COLOURS['success'])
        self.error_detail = ''
        self.details_button.pack_forget()

    def failed(self, error):
        code = getattr(error, 'code', 'io_error' if isinstance(error, OSError) else 'invalid_data')
        message = self.t('errors').get(code, self.t('error'))
        self.show_notice(message, warning=True)
        self.error_detail = str(error)
        self.details_button.pack(side='right', padx=(8, 0))
        if self.game:
            self.pending = Store(self.game).path(JOURNAL).exists()
        self.status.set(self.t('error'))

    def show_error(self):
        messagebox.showinfo(self.t('details'), self.error_detail, parent=self.root)

    def choose_package(self, source=None, folder=False):
        if self.busy or self.root.grab_current():
            return
        if not self.game:
            self.show_notice(self.t('failed_game'), warning=True); return
        if self.pending:
            self.show_notice(self.t('pending'), warning=True); return
        if source is None:
            source = filedialog.askdirectory(parent=self.root, title=self.t('folder')) if folder else filedialog.askopenfilename(
                parent=self.root, title=self.t('install'), filetypes=[('ZIP', '*.zip')])
        if source:
            source = os.path.abspath(source)
            game = self.game
            self.run(lambda: Store(game).preview(source, replace=True, layer=True), lambda plan: self.review(source, game, plan))

    def review(self, source, game, plan):
        meta = plan['metadata']
        replacing = bool(plan.get('replaces'))
        dialog = tk.Toplevel(self.root); dialog.title(self.t('replace_review' if replacing else 'review'))
        dialog.transient(self.root)
        dialog.geometry('680x560+%d+%d' % (self.root.winfo_rootx() + 80, self.root.winfo_rooty() + 60))
        dialog.minsize(600, 500)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=24, style='Loader.TFrame'); frame.pack(fill='both', expand=True)
        # Reserve the action and warning area before packing variable-length package content.
        bar = ttk.Frame(frame, style='Loader.TFrame'); bar.pack(side='bottom', fill='x')
        ttk.Label(frame, text=self.t('review_note'), wraplength=620, style='Loader.TLabel').pack(side='bottom', anchor='w', pady=14)
        ttk.Label(frame, text=meta['name'], style='Heading.Loader.TLabel', wraplength=590).pack(anchor='w')
        ttk.Label(frame, text='%s · %s' % (meta['version'], meta['author'] or self.t('unknown')), style='Muted.Loader.TLabel').pack(anchor='w', pady=(6, 14))
        if replacing:
            ttk.Label(frame, text=self.t('replace_note') % (plan['replaces']['version'], meta['version']),
                      wraplength=620, style='Loader.TLabel').pack(anchor='w', pady=(0, 10))
        if plan.get('layered'):
            ttk.Label(frame, text=modpriorityui.TEXT[self.lang]['install'] % (plan['order'].index(meta['id'])+1, len(plan['order'])),
                      wraplength=620, style='Loader.TLabel').pack(anchor='w', pady=(0, 10))
        description = tk.Text(frame, height=3, wrap='word', font=('Segoe UI', 10), relief='flat',
                              background=COLOURS['bg'], foreground=COLOURS['ink'])
        description.insert('1.0', meta['description']); description.config(state='disabled'); description.pack(fill='x')
        ttk.Label(frame, text=self.t('size') % (len(plan['files']), plan['bytes'] / 1048576), style='Muted.Loader.TLabel').pack(anchor='w', pady=10)
        file_frame = ttk.Frame(frame, style='Loader.TFrame'); file_frame.pack(fill='both', expand=True)
        files = tk.Text(file_frame, height=5, wrap='word', font=('Segoe UI', 10), relief='flat')
        scroll = ttk.Scrollbar(file_frame, command=files.yview); scroll.pack(side='right', fill='y')
        files.config(yscrollcommand=scroll.set)
        restored = set(plan.get('restores', []))
        files.insert('1.0', '\n'.join(self.t('restored_file') % f['path'] if f['path'] in restored else f['path'] for f in plan['files']))
        if plan.get('layered'):
            files.insert('end', '\n\n'+modpriorityui.summary(plan, self.lang, self.records.values()))
        files.config(state='disabled'); files.pack(side='left', fill='both', expand=True)
        def apply():
            dialog.destroy()
            self.run(lambda: Store(game).install(source, expected=plan['ticket'], replace=replacing, layer=True),
                     lambda m: self.reload(self.t('replaced' if replacing else 'installed') % m['name'], select_id=m['id']))
        ttk.Button(bar, text=self.t('replace_confirm' if replacing else 'confirm'), command=apply, style='Primary.Loader.TButton').pack(side='right')
        cancel = ttk.Button(bar, text=self.t('cancel'), command=dialog.destroy, style='Loader.TButton')
        cancel.pack(side='right', padx=8); cancel.focus_set()
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.update_idletasks()
        dialog.geometry('+%d+%d' % (self.root.winfo_rootx() + 80, self.root.winfo_rooty() + 60))

    def priorities(self):
        if self.busy or self.pending or len(self.records) < 2 or self.root.grab_current(): return
        records, game = list(self.records.values()), self.game
        ids = modpriorityui.OrderDialog(self.root, records, self.lang).result
        if ids is None: return
        def reviewed(plan):
            if modpriorityui.ReviewDialog(self.root, plan, records, self.lang).result:
                self.run(lambda: Store(game).order(ids, expected=plan['ticket']),
                         lambda _: self.reload(modpriorityui.TEXT[self.lang]['saved']))
        self.run(lambda: Store(game).preview_order(ids), reviewed)

    def remove(self):
        mid = self.current_id()
        if self.busy or self.pending or not mid:
            return
        game, meta = self.game, self.records[mid]['metadata']
        def reviewed(plan):
            if messagebox.askyesno(self.t('remove'), self.t('remove_question') % meta['name'], parent=self.root):
                self.run(lambda: Store(game).remove(mid, expected=plan['ticket']),
                         lambda m: self.reload(self.t('removed') % m['name']))
        self.run(lambda: Store(game).preview_remove(mid), reviewed)

    def verify(self):
        mid = self.current_id()
        if self.busy or self.pending or not mid:
            return
        game = self.game
        def done(report):
            self.show_notice(self.t('verified') % self.records[mid]['metadata']['name'] if report['valid'] else self.t('unhealthy'), warning=not report['valid'])
            if not report['valid']:
                self.error_detail = json.dumps(report, indent=2, ensure_ascii=False)
                self.details_button.pack(side='right', padx=(8, 0))
        self.run(lambda: Store(game).verify(mid), done)

    def recover(self):
        if self.busy or not self.pending:
            return
        if messagebox.askyesno(self.t('recover'), self.t('recover_question'), parent=self.root):
            game = self.game
            self.run(lambda: Store(game).recover(), lambda _: self.reload(self.t('recovered')))

    def check_updates(self):
        if self.busy or self.pending or not self.game:
            return
        records = list(self.records.values()); store = Store(self.game)
        def done(rows):
            self.updates = {r['id']: r for r in rows}; self.filter()
            failures = [r for r in rows if r['error']]
            found = sum(r['update'] for r in rows)
            if failures:
                self.failed(OSError('\n'.join('%s: %s' % (r['name'], r['error']) for r in failures)))
            else:
                self.show_notice(self.t('new_updates') % found if found else self.t('no_updates') if rows else self.t('no_sources'))
        self.run(lambda: modupdate.check(records, str(store.path(modupdate.CACHE))), done)

    def open_update(self):
        info = self.updates.get(self.current_id(), {})
        url = info.get('url', '')
        parsed = urlsplit(url)
        if info.get('update') and parsed.scheme == 'https' and parsed.hostname == 'github.com':
            webbrowser.open(url)

    def setup_drop(self):
        if os.name != 'nt':
            return
        hwnd = self.root.winfo_id()
        if self.drop_target and self.drop_target.hwnd == hwnd:
            return
        if self.drop_target:
            self.drop_target.close()
        try:
            self.drop_target = DropTarget(hwnd, lambda files: self.queue.put(('drop', None, files)))
        except OSError:
            self.drop_target = None

    def dropped(self, files):
        if self.busy or self.root.grab_current():
            self.status.set(self.t('busy')); return
        if len(files) != 1:
            self.show_notice(self.t('one'), warning=True); return
        self.choose_package(files[0])

    def about(self):
        messagebox.showinfo(self.t('about'), self.t('about_text') % (LOADER, VERSION, AUTHOR), parent=self.root)

    def close(self):
        if self.busy:
            self.status.set(self.t('busy')); return
        if self.drop_target:
            self.drop_target.close()
        self.root.destroy()
