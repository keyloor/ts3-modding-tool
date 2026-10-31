import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from octlib import Oct
f = Oct.load(sys.argv[1])
for t in f.children(f.find('TexturePool')[0]):
    name = f.value(f.child(t,'Name'))[0]; d = f.recs[f.child(t,'Data')].items()[1]
    print('%-34s %8d %s' % (name, len(d), bytes(d[:40]).hex(' ')))
