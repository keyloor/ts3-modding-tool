"""Add textured, skinned decal planes to an existing TS3 character.

  python add_decals.py <source dir> <base> <map.py> <out dir>

The map names the character's existing diffuse texture and a source atlas, then
lists cropped atlas regions placed on unused locations in that diffuse texture.
Each decal becomes a two-triangle plane weighted to one existing game bone.
This is deliberately generic: characters define their artwork and placement in
their own map file.
"""
import importlib.util, io, os, shutil, struct, sys, zlib

import numpy as np
from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert as C
import ts3model as T


def load_map(path):
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    return mp


def trim_white(im):
    """Remove the blank atlas margin while preserving the decal's own white ink."""
    a = np.asarray(im.convert('RGB'))
    mask = np.any(a < 242, axis=2)
    yy, xx = np.nonzero(mask)
    if not len(xx):
        raise ValueError('decal crop is blank')
    # Two pixels preserve anti-aliased outline/shadow at the crop edge.
    return im.crop((max(0, xx.min() - 2), max(0, yy.min() - 2),
                    min(im.width, xx.max() + 3), min(im.height, yy.max() + 3)))


def main(src, base, mappath, out):
    mp = load_map(mappath)
    os.makedirs(out, exist_ok=True)
    for ext in ('.oct', '_0.vbuf', '_0.ibuf'):
        shutil.copyfile(os.path.join(src, base + ext), os.path.join(out, base + ext))

    octpath = os.path.join(out, base + '.oct')
    f, bones, subs, remaps, ist, vst = T.load(octpath)
    ids = {b['name']: b['id'] for b in bones}
    if mp.BONE not in ids:
        raise ValueError('game skeleton has no bone ' + mp.BONE)

    # Repaint only unused parts of an existing diffuse texture; its original
    # UVs continue to sample precisely the same image after resizing.
    tex_pool = T.pool(f, 'TexturePool')
    tex = next((i for i in tex_pool if T.field(f, i, 'Name')[0] == mp.TEXTURE), None)
    if tex is None:
        raise ValueError('texture %r not found' % mp.TEXTURE)
    data_rec = f.child(tex, 'Data')
    old_data = bytes(f.recs[data_rec].items()[1])
    base_im = Image.open(io.BytesIO(old_data)).convert('RGB').resize((mp.TEXTURE_SIZE, mp.TEXTURE_SIZE), Image.LANCZOS)
    source = Image.open(mp.ATLAS).convert('RGB')

    planes, canvas = [], base_im.copy()
    for d in mp.DECALS:
        crop = trim_white(source.crop(d['crop']))
        l, t, r, b = d['texture_rect']
        canvas.paste(crop.resize((r - l, b - t), Image.LANCZOS), (l, t))
        x, y, z = d['center']; w, h = d['size']
        # Corners are clockwise when viewed from the back (-Z): their normals
        # face outward and the game's back-face culling leaves them visible.
        p = [(x - w / 2, y - h / 2, z), (x - w / 2, y + h / 2, z),
             (x + w / 2, y + h / 2, z), (x + w / 2, y - h / 2, z)]
        u0, v0, u1, v1 = l / mp.TEXTURE_SIZE, t / mp.TEXTURE_SIZE, r / mp.TEXTURE_SIZE, b / mp.TEXTURE_SIZE
        if d.get('flip_u'):
            u0, u1 = u1, u0
        uv = [(u0, v1), (u0, v0), (u1, v0), (u1, v1)]
        planes.append((p, uv, d['name']))
    canvas.save(os.path.join(out, mp.PREVIEW_TEXTURE))

    # Build one tiny vertex-stream pair.  Its indices are local to the stream.
    n = 4 * len(planes)
    v0 = np.zeros(n, T.S0); v1 = np.zeros(n, T.S1); indices = []
    for k, (p, uv, _) in enumerate(planes):
        q = 4 * k
        v0['p'][q:q + 4] = p; v0['uv'][q:q + 4] = uv
        v0['bi'][q:q + 4, 0] = 0; v0['bw'][q:q + 4, 0] = 255
        v1['t'][q:q + 4, :3] = (1, 0, 0)
        v1['n'][q:q + 4, :3] = (0, 0, -1)
        v1['b'][q:q + 4, :3] = (0, 1, 0)
        indices += [q, q + 1, q + 2, q, q + 2, q + 3]

    vbpath, ibpath = os.path.join(out, base + '_0.vbuf'), os.path.join(out, base + '_0.ibuf')
    vb, ib = open(vbpath, 'rb').read(), open(ibpath, 'rb').read()
    voff, ioff = len(vb), len(ib)
    open(vbpath, 'wb').write(vb + v0.tobytes() + v1.tobytes())
    open(ibpath, 'wb').write(ib + np.asarray(indices, '<u2').tobytes())

    vs_pool, is_pool, sc_pool = T.pool(f, 'VertexStreamPool'), T.pool(f, 'IndexStreamPool'), T.pool(f, 'SceneComponentPool')
    node_pool, mat_pool = T.pool(f, 'SceneTreeNodePool'), T.pool(f, 'MaterialPool')
    template = next(s for s in subs if s['mat'] == mp.MATERIAL)

    # Build all replacement blocks before replacing a pool: record indexes in
    # an Oct file move whenever an earlier pool grows.  They are then written
    # back in reverse file order, matching the character converter's approach.
    # Stream and index records use current pool lengths as their new references.
    new_vrefs = [len(vs_pool), len(vs_pool) + 1]
    nv = []
    for block, key, off in ((C.block(f, vs_pool[template['vs'][0]]), new_vrefs[0], voff),
                            (C.block(f, vs_pool[template['vs'][1]]), new_vrefs[1], voff + n * 24)):
        C.set_key(f, block, str(key)); C.setv(f, block, 'Length', [n]); C.setv(f, block, 'VertexBufferOffset', [off]); nv.append(block)
    new_iref = len(is_pool); ni = C.block(f, is_pool[template['ist']])
    C.set_key(f, ni, str(new_iref)); C.setv(f, ni, 'Length', [len(indices)]); C.setv(f, ni, 'IndexBufferOffset', [ioff])

    new_scref = len(sc_pool); ns = C.block(f, sc_pool[template['sc']])
    C.set_key(f, ns, str(new_scref)); C.setv(f, ns, 'RemapData', [ids[mp.BONE]])

    # A cloned lit-subgeometry inherits the same decal material/effect; only
    # its buffers, skin remap and name differ.
    nn = C.block(f, node_pool[template['node']])
    C.set_key(f, nn, str(len(node_pool)))
    C.setv(f, nn, 'NodeName', [mp.NODE_NAME], names=True)
    C.setv(f, nn, 'VertexStreamReferences', new_vrefs)
    C.setv(f, nn, 'IndexStreamReference', [new_iref])
    C.setv(f, nn, 'SceneComponentReferences', [new_scref])
    centre = np.mean(np.asarray([p for p, _, _ in planes]).reshape(-1, 3), axis=0)
    C.setv(f, nn, 'BoundingCenter', list(map(float, centre)))
    # Pools are laid out in this order: IndexStream, VertexStream,
    # SceneComponent, SceneTreeNode.  Work backwards to keep every template
    # index valid while cloning it.
    C.replace_pool(f, 'SceneTreeNodePool', [nn])
    C.replace_pool(f, 'SceneComponentPool', [ns])
    C.replace_pool(f, 'VertexStreamPool', nv)
    C.replace_pool(f, 'IndexStreamPool', [ni])

    # Replace the existing diffuse bytes and update their CRC; keep the game
    # material and all other maps unchanged.
    new_data = C.dxt1(canvas, mp.TEXTURE_SIZE, old_data[:128])
    f.recs[data_rec].set_items(new_data)
    crc = zlib.crc32(new_data)
    f.recs[f.child(tex, 'DataCRC')].set_items([crc - (1 << 32) if crc >= (1 << 31) else crc])
    f.recs[f.child(T.pool(f, 'VertexBufferPool')[0], 'Size')].set_items([len(vb) + len(v0.tobytes()) + len(v1.tobytes())])
    f.recs[f.child(T.pool(f, 'IndexBufferPool')[0], 'Size')].set_items([len(ib) + len(indices) * 2])
    f.save(octpath)
    print('added %d decals (%d vertices, %d triangles) to %s' % (len(planes), n, len(indices) // 3, octpath))


if __name__ == '__main__':
    main(*sys.argv[1:5])
