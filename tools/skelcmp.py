"""Compare the skeletons of two TS3 characters: python skelcmp.py <a.oct> <b.oct>"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts3model as T
a = T.load(sys.argv[1])[1]; b = T.load(sys.argv[2])[1]
print(len(a), 'vs', len(b), 'bones')
A = {x['name']: x for x in a}; B = {x['name']: x for x in b}
only = set(A) ^ set(B)
if only:
    print('names only in one:', sorted(only))
bad = 0
for n in A:
    if n not in B:
        continue
    x, y = A[n], B[n]
    d = np.abs(np.array(x['pivot']) - np.array(y['pivot'])).max()
    m = np.abs(x['b2m'] - y['b2m']).max()
    if x['id'] != y['id'] or d > 1e-4 or m > 1e-4 or A.get(n)['parent'] != B[n]['parent']:
        bad += 1
        print('  %-18s id %s/%s pivot diff %.5f b2m diff %.5f parent %s/%s' % (n, x['id'], y['id'], d, m, x['parent'], y['parent']))
print('SAME skeleton' if not bad and not only else '%d differences' % bad)
