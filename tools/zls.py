"""List files in game archives: python zls.py <zip>... [--filter substr]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install import read_zip
args = sys.argv[1:]
flt = None
if '--filter' in args:
    k = args.index('--filter'); flt = args[k + 1]; args = args[:k] + args[k + 2:]
for p in args:
    ents = read_zip(open(p, 'rb').read())
    print('==', os.path.basename(p), len(ents), 'files')
    for z in ents:
        n = z['name'].decode('latin1')
        if flt is None or flt in n.lower():
            print('  %9d %s' % (z['usize'], n))
