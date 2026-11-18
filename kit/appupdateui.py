"""Non-blocking application-update notice shared by the Tool and Loader."""
import queue
import threading
from tkinter import ttk
import webbrowser

import appupdate

TEXT = {
    'es': dict(check='Buscar actualizaciones de la aplicación', checking='Buscando una nueva versión de la aplicación…',
               available='%s %s está disponible. Tienes %s.', download='Descargar en GitHub',
               current='No hay una versión más nueva de %s. Tienes %s.',
               failed='No se pudo comprobar la versión de la aplicación. Inténtalo de nuevo cuando tengas conexión.'),
    'en': dict(check='Check for application updates', checking='Checking for a new application version…',
               available='%s %s is available. You have %s.', download='Download on GitHub',
               current='No newer version of %s is available. You have %s.',
               failed='Could not check the application version. Try again when you have a connection.'),
}


class Notice:
    def __init__(self, root, product, language):
        self.root, self.product, self.language = root, product, language
        self.queue = queue.Queue()
        self.checking = self.manual = False
        self.force_pending = False
        self.result = self.panel = None
        root.after(1200, self.check)

    def text(self, key):
        return TEXT[self.language()][key]

    def mount(self, parent):
        slot = ttk.Frame(parent)
        slot.pack(fill='x')
        self.panel = ttk.Frame(slot, padding=(12, 8))
        self.download = ttk.Button(self.panel, text=self.text('download'),
                                   command=lambda: webbrowser.open(appupdate.RELEASES))
        self.label = ttk.Label(self.panel, wraplength=690)
        self.label.pack(side='left', fill='x', expand=True)
        self.render()

    def render(self):
        if self.panel is None:
            return
        result = self.result or {}
        available = bool(result.get('update')) and not result.get('error')
        if not available and not self.manual:
            self.panel.pack_forget()
            return
        if self.checking:
            text = self.text('checking')
        elif result.get('error'):
            text = self.text('failed')
        elif available:
            text = self.text('available') % (self.product, result['latest'], result['installed'])
        else:
            text = self.text('current') % (self.product, result['installed'])
        self.label.config(text=text)
        self.download.config(text=self.text('download'))
        if available and not self.checking:
            self.download.pack(side='right', padx=(12, 0))
        else:
            self.download.pack_forget()
        self.panel.pack(fill='x')

    def check(self, force=False):
        self.manual = self.manual or force
        if self.checking:
            self.force_pending = self.force_pending or force
            self.render()
            return
        self.checking = True
        self.render()

        def worker():
            try:
                result = appupdate.check(force=force)
            except Exception as e:
                result = {'error': str(e) or type(e).__name__}
            self.queue.put(result)

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self.poll)

    def poll(self):
        try:
            self.result = self.queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll)
            return
        self.checking = False
        if self.force_pending:
            self.force_pending = False
            self.check(force=True)
            return
        self.render()
