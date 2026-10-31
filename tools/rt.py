import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from octlib import Oct
for p in sys.argv[1:]:
    b = open(p,'rb').read(); f = Oct.parse(b)
    print(os.path.basename(p), len(f.recs), f.count_field, 'byte-exact' if f.to_bytes()==b else 'DIFFERENT')
