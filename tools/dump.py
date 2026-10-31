import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from octlib import Oct
f = Oct.load(sys.argv[1]); skip = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else set()
i = 0
while i < len(f.recs):
    r = f.recs[i]
    if f.nm(r.name) in skip:
        print(f.describe(i), '... (%d records skipped)' % (f.end_of(i) - i)); i = f.end_of(i); continue
    print(f.describe(i)); i += 1
