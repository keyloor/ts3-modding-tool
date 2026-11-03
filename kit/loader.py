"""Toy Story 3 Mod Loader: the player application, or mod commands without opening a window."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from about import LOADER


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    package = args[0] if len(args) == 1 and os.path.exists(args[0]) else None
    if args and package is None:
        if sys.stdout is None:
            sys.stdout = sys.stderr = open(os.path.join(os.environ.get('TEMP', '.'), LOADER + '.log'), 'w', encoding='utf-8')
        from loadercli import main as console
        return console(args)
    import tkinter as tk
    from loaderui import LoaderApp
    root = tk.Tk()
    LoaderApp(root, package=package)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
