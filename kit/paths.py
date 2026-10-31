"""Where the kit and the shared tools are: the folder of 'Toy Story 3 Modding Tool.exe' when frozen (its modules are inside
it), <kit>/tools in a release run with Python, the workspace's tools/ while developing. Importing this module puts the
tools on sys.path."""
import os, sys

FROZEN = getattr(sys, 'frozen', False)
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(HERE)
if FROZEN:
    TOOLS = os.path.join(KIT, 'tools')
else:
    TOOLS = next(p for p in (os.path.join(KIT, 'tools'), os.path.normpath(os.path.join(KIT, '..', '..', 'tools')))
                 if os.path.isfile(os.path.join(p, 'convert.py')))
    for p in (HERE, TOOLS):
        if p not in sys.path:
            sys.path.insert(0, p)


def doc(name):
    """a document of the kit: at the kit's root in a release (AGENTS.md), else in docs/"""
    for p in (os.path.join(KIT, name), os.path.join(KIT, 'docs', name)):
        if os.path.exists(p):
            return p
    return os.path.join(KIT, 'docs', name)
