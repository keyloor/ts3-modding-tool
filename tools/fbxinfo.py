import sys, os, numpy as np; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbxlib import Scene
s = Scene(sys.argv[1])
print('FBX', s.version, {k: v for k, v in s.settings.items() if k in ('UpAxis','UpAxisSign','FrontAxis','FrontAxisSign','CoordAxis','CoordAxisSign','UnitScaleFactor','OriginalUnitScaleFactor')})
for m in s.meshes():
    print('mesh', m['name'], 'cp', len(m['pos']), 'tris', len(m['tri']), 'mats', m['matnames'], 'mat ids', np.unique(m['mat']))
    print('  pos min', m['pos'].min(0).round(2), 'max', m['pos'].max(0).round(2))
    print('  uv', None if m['uv'] is None else m['uv'][0].shape, 'normals', None if m['normals'] is None else m['normals'][0].shape)
    sk = m['skin']; print('  clusters', len(sk))
    for c in sk[:60]:
        t = c['xlink'][3, :3]
        print('   %-24s nverts %5d  bind pos %s' % (c['bone'], len(c['idx']), t.round(2)))
