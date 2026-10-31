"""List a model's skinned bones in the game's frame (Y up, facing +Z): python bones5.py <fbx>"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbxlib import Scene
s = Scene(sys.argv[1]); m = next(s.meshes()); A = s.to_yup()
allb = s.bones()
byid = {c['bone_id']: c for c in m['skin']}
mg = [c['xf'] @ c['xlink'] for c in m['skin'] if len(c['idx'])][0]
P = ((np.c_[m['pos'], np.ones(len(m['pos']))] @ mg)[:, :3]) @ A
print('mesh min', P.min(0).round(1), 'max', P.max(0).round(1))
for c in m['skin']:
    p = c['xlink'][3, :3] @ A
    par = allb.get(allb[c['bone_id']]['parent'], {}).get('name') if c['bone_id'] in allb else None
    print('%-18s parent %-14s verts %5d  at %s' % (c['bone'], par, len(c['idx']), np.round(p, 1)))
