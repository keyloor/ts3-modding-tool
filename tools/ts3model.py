"""Read a Toy Story 3 character (.oct + _0.vbuf + _0.ibuf): bones, materials, sub-geometries, vertices."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from octlib import Oct

S0 = np.dtype([('p', '<f4', 3), ('bi', 'u1', 4), ('bw', 'u1', 4), ('uv', '<f2', 2)])
S1 = np.dtype([('t', '<f2', 4), ('n', '<f2', 4), ('b', '<f2', 4)])


def pool(f, name):
    return f.children(f.find(name)[0])


def field(f, i, name, default=None):
    j = f.child(i, name)
    return default if j is None else f.value(j)


def mat44(v):
    return np.array(v, dtype=np.float64).reshape(4, 4)


def load(oct_path):
    f = Oct.load(oct_path)
    nodes = pool(f, 'SceneTreeNodePool')
    bones = []
    for k, i in enumerate(nodes):
        if field(f, i, 'Type', [''])[0] != 'Bone':
            continue
        bones.append(dict(node=k, rec=i, name=field(f, i, 'NodeName')[0], id=field(f, i, 'BoneID')[0],
                          parent=field(f, i, 'ParentNodeReferences')[0],
                          b2m=mat44(field(f, i, 'BoneToModelMatrix')), pivot=field(f, i, 'PivotPoint'),
                          end=field(f, i, 'BoneEndPoint'), nverts=field(f, i, 'NumAssignedVerts')[0]))
    subs = []
    for k, i in enumerate(nodes):
        if field(f, i, 'Type', [''])[0] == 'SubGeometryLit':
            subs.append(dict(node=k, rec=i, name=field(f, i, 'NodeName')[0], mat=field(f, i, 'MaterialReference')[0],
                             vs=field(f, i, 'VertexStreamReferences'), ist=field(f, i, 'IndexStreamReference')[0],
                             sc=field(f, i, 'SceneComponentReferences', [None])[0]))
    remaps = [field(f, i, 'RemapData') for i in pool(f, 'SceneComponentPool')]
    istreams = [dict(len=field(f, i, 'Length')[0], off=field(f, i, 'IndexBufferOffset')[0]) for i in pool(f, 'IndexStreamPool')]
    vstreams = [dict(len=field(f, i, 'Length')[0], width=field(f, i, 'Width')[0], off=field(f, i, 'VertexBufferOffset')[0])
                for i in pool(f, 'VertexStreamPool')]
    return f, bones, subs, remaps, istreams, vstreams


if __name__ == '__main__':
    d = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(os.path.normpath(d))
    f, bones, subs, remaps, ist, vst = load(os.path.join(d, base + '.oct'))
    vb = open(os.path.join(d, base + '_0.vbuf'), 'rb').read()
    ib = np.frombuffer(open(os.path.join(d, base + '_0.ibuf'), 'rb').read(), '<u2')
    byid = {b['id']: b for b in bones}
    bynode = {b['node']: b for b in bones}
    print(len(bones), 'bones; ids', sorted(byid)[:5], '...', max(byid))
    for b in bones[:30]:
        t = b['b2m']
        print('%3d id=%3d %-16s parent=%-3s pivot=%s  b2m_t=%s row3=%s' % (b['node'], b['id'], b['name'], b['parent'],
              np.round(b['pivot'], 3), np.round(t[:3, 3], 3), np.round(t[3], 3)))
    s0 = np.frombuffer(vb, S0, vst[0]['len'], vst[0]['off'])
    # what does a remap entry point at? take sub 0 (Neck) -> remap list; vertices fully weighted to one slot
    for s in subs[:4]:
        rm = remaps[s['sc']]
        idx = ib[ist[s['ist']]['off'] // 2: ist[s['ist']]['off'] // 2 + ist[s['ist']]['len']]
        v = s0[np.unique(idx)]
        print(s['name'], 'remap', rm)
        for slot in range(min(len(rm), 6)):
            m = (v['bi'][:, 0] == slot) & (v['bw'][:, 0] > 200)
            if m.any():
                c = v['p'][m].mean(0)
                near = sorted(bones, key=lambda b: np.linalg.norm(np.array(b['pivot']) - c))[:3]
                cand = byid.get(rm[slot]); cn = bynode.get(rm[slot])
                print('   slot %d -> %d  verts at %s  nearest pivots %s | as BoneID: %s | as node: %s' % (slot, rm[slot], np.round(c, 2),
                      [x['name'] for x in near], cand and cand['name'], cn and cn['name']))
