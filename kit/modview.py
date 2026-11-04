"""Shared, read-only manager presentation. No store operations or authoring dependencies."""
import json
import unicodedata
import tkinter as tk
from tkinter import ttk

TEXT = {
    'es': dict(more='Opciones', search='Buscar', files='Archivos', state='Estado', waiting='Pendiente de recuperar',
               installed='Instalado', checked='Verificado', attention='Revisar archivos', update='Nueva versión',
               empty='Todavía no tienes mods instalados. Instala un ZIP o una carpeta para empezar.',
               no_match='No hay resultados. Prueba con otro nombre, autor o identificador.',
               verify='Verificar archivos', result='Ver resultado', title='Resultado de la verificación',
               good='Los archivos, las copias originales y los datos guardados están correctos.',
               bad='Hay archivos que necesitan revisión. Verificar no cambia ni repara el juego.',
               readonly='Resultado de esta comprobación. Si cambias archivos o prioridades, vuelve a verificar.',
               file='Archivo del juego', backup='Copia original', layers='Datos de los mods',
               ok='Correcto', modified='Modificado fuera del gestor', modified_short='Modificado', missing='No se encuentra',
               damaged='Dañado', not_needed='No necesaria', unknown='Sin comprobar', unused='No se usan',
               choose='Selecciona un archivo para ver los detalles.', technical='Detalles técnicos', close='Cerrar',
               layer='Datos guardados de %s: %s', original='Copia original: %s', current='Archivo del juego: %s',
               missing_help='No sobrescribas las copias. Conserva los archivos y revisa los elementos señalados antes de quitar o actualizar mods.',
               no_backup='El mod creó este archivo; no necesita una copia de un original anterior.'),
    'en': dict(more='Options', search='Search', files='Files', state='Status', waiting='Recovery needed',
               installed='Installed', checked='Verified', attention='Check files', update='Update available',
               empty='No mods installed yet. Install a ZIP or folder to get started.',
               no_match='No results. Try another name, author or identifier.',
               verify='Verify files', result='View result', title='Verification result',
               good='The files, original backups and stored mod data are correct.',
               bad='Some files need attention. Verification does not change or repair the game.',
               readonly='Result of this check. Verify again after changing files or priorities.',
               file='Game file', backup='Original backup', layers='Stored mod data',
               ok='Correct', modified='Changed outside the manager', modified_short='Modified', missing='Missing',
               damaged='Damaged', not_needed='Not needed', unknown='Not checked', unused='Not used',
               choose='Select a file to see its details.', technical='Technical details', close='Close',
               layer='Stored data for %s: %s', original='Original backup: %s', current='Game file: %s',
               missing_help='Preserve the backups and review the flagged items before removing or updating mods.',
               no_backup='The mod created this file; no previous original backup is needed.'),
}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def matches(metadata, query):
    haystack = normalized(' '.join(str(metadata.get(k, '')) for k in ('id', 'name', 'author', 'description')))
    return all(word in haystack for word in normalized(query).split())


def count(visible, total, lang):
    if visible != total:
        return ('%d de %d mods' if lang == 'es' else '%d of %d mods') % (visible, total)
    return '%d mod%s' % (total, '' if total == 1 else 's')


def file_valid(row):
    return (row.get('status') == 'ok' and row.get('backup_status') in ('ok', 'not_needed')
            and all(layer.get('status') == 'ok' for layer in row.get('layers', [])))


def valid(report):
    return report.get('valid') is True and all(file_valid(row) for row in report['files'])


def state(report, lang):
    return TEXT[lang]['installed' if report is None else 'checked' if valid(report) else 'attention']


def list_state(report, update, lang):
    if report and not valid(report): return state(report, lang)
    return TEXT[lang]['update'] if update else state(report, lang)


def summary(report, lang):
    words = TEXT[lang]
    total, issues = len(report['files']), sum(not file_valid(row) for row in report['files'])
    counts = (('%d archivo comprobado' if total == 1 else '%d archivos comprobados') if lang == 'es' else
              ('%d file checked' if total == 1 else '%d files checked')) % total
    if issues:
        counts += (' · %d con problemas' if lang == 'es' else ' · %d need attention') % issues
    return words['good' if valid(report) else 'bad'] + '\n' + counts


def status_text(status, lang):
    return TEXT[lang][status if status in ('ok', 'modified', 'missing', 'damaged', 'not_needed') else 'unknown']


def row_values(row, lang):
    layers = row.get('layers', [])
    states = [r.get('status') for r in layers]
    layer_state = ('unused' if not layers else 'ok' if all(s == 'ok' for s in states) else
                   'missing' if 'missing' in states else 'damaged' if 'damaged' in states else 'unknown')
    current = TEXT[lang]['modified_short'] if row.get('status') == 'modified' else status_text(row.get('status'), lang)
    return (row['path'], current, status_text(row.get('backup_status'), lang),
            TEXT[lang][layer_state])


def file_details(row, lang, names=None):
    words, names = TEXT[lang], names or {}
    lines = [row['path'], words['current'] % status_text(row.get('status'), lang),
             words['original'] % status_text(row.get('backup_status'), lang)]
    if row.get('backup_status') == 'not_needed': lines.append(words['no_backup'])
    lines += [words['layer'] % (names.get(r['id'], r['id']), status_text(r.get('status'), lang)) for r in row.get('layers', [])]
    if not file_valid(row): lines.extend(('', words['missing_help']))
    return '\n'.join(lines)


class VerificationDialog(tk.Toplevel):
    """Same bilingual report in both products; raw hashes/JSON require an explicit action."""
    def __init__(self, parent, report, lang, records=()):
        super().__init__(parent)
        words = TEXT[lang]
        self.title(words['title']); self.transient(parent)
        self.geometry('860x580+%d+%d' % (parent.winfo_rootx()+30, parent.winfo_rooty()+30))
        self.minsize(700, 480)
        frame = ttk.Frame(self, padding=18); frame.pack(fill='both', expand=True)
        bar = ttk.Frame(frame); bar.pack(side='bottom', fill='x', pady=(12, 0))
        close = ttk.Button(bar, text=words['close'], command=self.destroy); close.pack(side='right')
        ttk.Button(bar, text=words['technical'], command=lambda: self.technical(report, words)).pack(side='left')
        heading = ttk.Label(frame, text=report['metadata']['name'], font=('Segoe UI', 14, 'bold'), wraplength=800)
        heading.pack(anchor='w')
        note = ttk.Label(frame, text=summary(report, lang), wraplength=800); note.pack(anchor='w', pady=(8, 6))
        context = ttk.Label(frame, text=words['readonly'], wraplength=800); context.pack(anchor='w', pady=(0, 12))
        frame.bind('<Configure>', lambda e: [label.config(wraplength=max(200, e.width-36)) for label in (heading, note, context)])
        listing = ttk.Frame(frame); listing.pack(fill='both', expand=True)
        listing.rowconfigure(0, weight=1); listing.columnconfigure(0, weight=1)
        tree = ttk.Treeview(listing, columns=('file', 'backup', 'layers'), selectmode='browse', height=7)
        tree.heading('#0', text=words['file']); tree.column('#0', width=320, minwidth=150)
        for key, width in (('file', 150), ('backup', 145), ('layers', 145)):
            tree.heading(key, text=words['state'] if key == 'file' else words[key])
            tree.column(key, width=width, minwidth=90, stretch=False)
        tree.grid(row=0, column=0, sticky='nsew')
        sy = ttk.Scrollbar(listing, command=tree.yview); sy.grid(row=0, column=1, sticky='ns')
        sx = ttk.Scrollbar(listing, orient='horizontal', command=tree.xview); sx.grid(row=1, column=0, sticky='ew')
        tree.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        details = ttk.Frame(frame); details.pack(fill='x', pady=(12, 0))
        detail = tk.Text(details, height=6, wrap='word', font=('Segoe UI', 10), state='disabled')
        detail.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(details, command=detail.yview); scroll.pack(side='right', fill='y')
        detail.config(yscrollcommand=scroll.set)
        names = {r['metadata']['id']: r['metadata']['name'] for r in records}
        def selected(event=None):
            selection = tree.selection()
            text = file_details(report['files'][int(selection[0])], lang, names) if selection else words['choose']
            detail.config(state='normal'); detail.delete('1.0', 'end'); detail.insert('end', text); detail.config(state='disabled')
        for i, row in enumerate(report['files']):
            path, current, backup, layers = row_values(row, lang)
            tree.insert('', 'end', iid=str(i), text=path, values=(current, backup, layers))
        tree.bind('<<TreeviewSelect>>', selected)
        if report['files']:
            first = next((i for i, row in enumerate(report['files']) if not file_valid(row)), 0)
            tree.selection_set(str(first)); tree.see(str(first))
        selected()
        self.bind('<Escape>', lambda event: self.destroy()); self.grab_set(); close.focus_set()

    def technical(self, report, words):
        dialog = tk.Toplevel(self); dialog.title(words['technical']); dialog.transient(self)
        dialog.geometry('760x500+%d+%d' % (self.winfo_rootx()+20, self.winfo_rooty()+20))
        def close():
            dialog.destroy(); self.grab_set()
        ttk.Button(dialog, text=words['close'], command=close).pack(side='bottom', pady=10)
        text = tk.Text(dialog, wrap='word', font=('Consolas', 10))
        scroll = ttk.Scrollbar(dialog, command=text.yview); scroll.pack(side='right', fill='y')
        text.config(yscrollcommand=scroll.set); text.pack(fill='both', expand=True)
        text.insert('1.0', json.dumps(report, ensure_ascii=False, indent=2)); text.config(state='disabled')
        dialog.protocol('WM_DELETE_WINDOW', close); dialog.bind('<Escape>', lambda event: close()); dialog.grab_set()
