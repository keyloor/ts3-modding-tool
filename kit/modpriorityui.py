"""Shared priority editor/review for the creator Tool and player Loader."""
import tkinter as tk
from tkinter import ttk, simpledialog

TEXT = {
    'es': dict(title='Prioridades de mods', priority='Prioridad', name='Mod',
               hint='Menor prioridad arriba; mayor prioridad abajo. El último gana cuando dos mods cambian la misma entrada de un ZIP o el mismo archivo completo.',
               lower='Menor prioridad', higher='Mayor prioridad', review='Revisar cambios', cancel='Cancelar',
               apply='Aplicar este orden', review_title='Revisar prioridades',
               note='Cierra el juego antes de aplicar. Se reconstruirán los archivos compartidos conservando los otros mods y las copias originales.',
               saved='Prioridades actualizadas.', order='Orden de menor a mayor prioridad:',
               shared='Archivos compartidos:', none='No hay archivos compartidos.',
               rule='Los parches combinan entradas distintas del ZIP. Una entrada coincidente (incluido un OCT completo) usa la de mayor prioridad. Un reemplazo de archivo completo sustituye lo que quede debajo.',
               install='Prioridad de este mod: %d de %d. Los nuevos mods van al final; al actualizar se conserva su posición.',
               restore='Al quitarlo se reconstruirán las capas restantes; el último mod devuelve el archivo a su estado original.'),
    'en': dict(title='Mod priorities', priority='Priority', name='Mod',
               hint='Lower priority at the top; higher priority at the bottom. The last mod wins when two mods change the same ZIP member or whole file.',
               lower='Lower priority', higher='Higher priority', review='Review changes', cancel='Cancel',
               apply='Apply this order', review_title='Review priorities',
               note='Close the game before applying. Shared files will be rebuilt, keeping other mods and original backups.',
               saved='Priorities updated.', order='Order from lowest to highest priority:',
               shared='Shared files:', none='There are no shared files.',
               rule='Patches combine distinct ZIP members. A matching member (including a whole OCT) uses the higher priority version. A whole-file replacement overrides everything below it.',
               install='This mod’s priority: %d of %d. New mods go last; updates keep their position.',
               restore='Removing it rebuilds the remaining layers; removing the last mod restores the original file.'),
}


def summary(plan, lang, records=()):
    words = TEXT[lang]
    names = {r['metadata']['id']: r['metadata']['name'] for r in records}
    meta = plan.get('metadata')
    if meta: names[meta['id']] = meta['name']
    lines = [words['rule'], '', words['order']]
    lines += ['%d. %s (%s)' % (i+1, names.get(mid, mid), mid) for i, mid in enumerate(plan.get('order', []))]
    affected = {r['path'] for r in plan.get('files', [])}
    shared = [r for r in plan.get('shared', []) if not affected or r['path'] in affected]
    lines += ['', words['shared']]
    lines += [r['path']+'\n  '+' → '.join(names.get(mid, mid) for mid in r['mods']) for r in shared] or [words['none']]
    return '\n'.join(lines)


class OrderDialog(simpledialog.Dialog):
    def __init__(self, parent, records, lang):
        self.records, self.words = records, TEXT[lang]
        self.ids = [r['metadata']['id'] for r in records]
        self.names = {r['metadata']['id']: r['metadata']['name'] for r in records}
        for mid in self.ids:
            if sum(r['metadata']['name'] == self.names[mid] for r in records) > 1:
                self.names[mid] += ' · '+mid
        super().__init__(parent, title=self.words['title'])

    def body(self, master):
        ttk.Label(master, text=self.words['hint'], wraplength=640).pack(anchor='w', padx=12, pady=12)
        frame = ttk.Frame(master); frame.pack(fill='both', expand=True, padx=12)
        self.tree = ttk.Treeview(frame, columns=('rank', 'name'), show='headings', selectmode='browse', height=10)
        self.tree.heading('rank', text=self.words['priority']); self.tree.column('rank', width=75, stretch=False)
        self.tree.heading('name', text=self.words['name']); self.tree.column('name', width=510, minwidth=200)
        self.tree.pack(side='left', fill='both', expand=True)
        sy = ttk.Scrollbar(frame, command=self.tree.yview); sy.pack(side='right', fill='y')
        self.tree.config(yscrollcommand=sy.set)
        bar = ttk.Frame(master); bar.pack(fill='x', padx=12, pady=12)
        self.up = ttk.Button(bar, text=self.words['lower'], command=lambda: self.move(-1)); self.up.pack(side='left')
        self.down = ttk.Button(bar, text=self.words['higher'], command=lambda: self.move(1)); self.down.pack(side='left', padx=8)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.controls())
        self.tree.bind('<Alt-Up>', lambda e: self.move(-1)); self.tree.bind('<Alt-Down>', lambda e: self.move(1))
        self.draw(self.ids[0] if self.ids else None)
        return self.tree

    def draw(self, selected):
        self.tree.delete(*self.tree.get_children())
        for i, mid in enumerate(self.ids): self.tree.insert('', 'end', iid=mid, values=(i+1, self.names[mid]))
        if selected: self.tree.selection_set(selected); self.tree.focus(selected); self.tree.see(selected)
        self.controls()

    def controls(self):
        selection = self.tree.selection(); at = self.ids.index(selection[0]) if selection else -1
        self.up.state(['!disabled'] if at > 0 else ['disabled'])
        self.down.state(['!disabled'] if 0 <= at < len(self.ids)-1 else ['disabled'])

    def move(self, by):
        selection = self.tree.selection()
        if selection:
            at = self.ids.index(selection[0]); to = at+by
            if 0 <= to < len(self.ids):
                self.ids[at], self.ids[to] = self.ids[to], self.ids[at]; self.draw(selection[0])
        return 'break'

    def buttonbox(self):
        bar = ttk.Frame(self); bar.pack(fill='x', padx=20, pady=(0, 14))
        ttk.Button(bar, text=self.words['review'], command=self.ok).pack(side='right')
        ttk.Button(bar, text=self.words['cancel'], command=self.cancel).pack(side='right', padx=8)
        self.bind('<Escape>', self.cancel)

    def apply(self): self.result = self.ids[:]


class ReviewDialog(simpledialog.Dialog):
    def __init__(self, parent, plan, records, lang):
        self.plan, self.records, self.lang, self.words = plan, records, lang, TEXT[lang]
        super().__init__(parent, title=self.words['review_title'])

    def body(self, master):
        ttk.Label(master, text=self.words['note'], wraplength=640).pack(anchor='w', padx=12, pady=12)
        frame = ttk.Frame(master); frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        listing = tk.Text(frame, width=78, height=18, wrap='word', font=('Segoe UI', 10))
        listing.insert('1.0', summary(self.plan, self.lang, self.records)); listing.config(state='disabled')
        listing.pack(side='left', fill='both', expand=True)
        sy = ttk.Scrollbar(frame, command=listing.yview); sy.pack(side='right', fill='y')
        listing.config(yscrollcommand=sy.set)
        return listing

    def buttonbox(self):
        bar = ttk.Frame(self); bar.pack(fill='x', padx=20, pady=(0, 14))
        ttk.Button(bar, text=self.words['apply'], command=self.ok).pack(side='right')
        cancel = ttk.Button(bar, text=self.words['cancel'], command=self.cancel); cancel.pack(side='right', padx=8)
        cancel.focus_set(); self.bind('<Escape>', self.cancel)

    def apply(self): self.result = True
