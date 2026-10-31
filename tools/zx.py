"""Extract files from a game archive: python zx.py <zip> <out dir> [substr ...] (default: everything)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install import read_zip, unpack
z, out, *flt = sys.argv[1:]
for e in read_zip(open(z, 'rb').read()):
    n = e['name'].decode('latin1')
    if flt and not any(s in n.lower() for s in flt):
        continue
    p = os.path.join(out, *n.split('/'))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(unpack(e))
    print('  ', n)
