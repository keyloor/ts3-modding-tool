"""Texture tables for a map (TEXTURES, MATERIALS, SKIP_MATERIALS): which image each FBX material uses.

  python autotex.py <fbx> <textures dir>

For each material of a skinned mesh, in order:
  1. the texture the FBX links to it (its file name, found in the textures dir whatever the extension);
  2. a diffuse image whose name shares a word with the material ('22_hat_0' -> Woody_Hat_D.png), also through a few
     synonyms (skin ~ head ~ face, shoes ~ boots...); with a single diffuse image in the folder, that one;
  3. the material's own colour, if it isn't white or grey;
  4. else the biggest texture set, marked 'check' in the report and in the map.
A diffuse image's normal, ORM and specular images are the ones named the same but for the kind word
(Woody_Hat_D / Woody_Hat_N, T_Buzz_BC / T_Buzz_N / T_Buzz_ORM). Meshes that repeat another one exactly are left out.
"""
import os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401  (puts the shared tools on sys.path)
from fbxlib import props70
from objlib import open_scene as Scene                 # an FBX, or an OBJ (its .mtl links images and colours)
from automap import words

IMAGES = ('.png', '.tga', '.jpg', '.jpeg', '.bmp', '.dds')
KIND = {'d': 'd', 'bc': 'd', 'basecolor': 'd', 'base': 'd', 'color': 'd', 'colour': 'd', 'diffuse': 'd', 'diff': 'd',
        'albedo': 'd', 'alb': 'd', 'col': 'd', 'c': 'd',
        'n': 'n', 'nm': 'n', 'nrm': 'n', 'normal': 'n', 'nor': 'n', 'norm': 'n',
        'orm': 'orm', 's': 'spec', 'spec': 'spec', 'specular': 'spec', 'sp': 'spec',
        # images the converter has no use for
        'e': None, 'emissive': None, 'emit': None, 'ao': None, 'r': None, 'rough': None, 'roughness': None,
        'metal': None, 'metallic': None, 'm': None, 'mask': None, 'opacity': None, 'alpha': None, 'h': None,
        'height': None, 'disp': None}
GENERIC = {'t', 'tex', 'texture', 'mat', 'material', 'mi', 'new', 'lambert', 'phong', 'blinn', 'standard', 'surface',
           'default', 'sk', 'a', 'b'}
SYNONYMS = [{'skin', 'head', 'face', 'body'}, {'cloth', 'clothes', 'outfit', 'pants', 'legs', 'leg', 'jeans', 'trousers'},
            {'shirt', 'top', 'upper', 'torso', 'chest', 'vest', 'jacket'}, {'shoe', 'shoes', 'boot', 'boots', 'feet', 'foot'},
            {'hair'}, {'eye', 'eyes'}, {'hat', 'cap', 'helmet'}, {'hand', 'hands', 'glove', 'gloves'}]


def images(texdir):
    """{file: (kind, pairing key, words)} for every image in the folder"""
    out = {}
    for fn in sorted(os.listdir(texdir)):
        if not fn.lower().endswith(IMAGES):
            continue
        w = words(fn.split('.')[0])
        k = next((i for i in range(len(w) - 1, -1, -1) if w[i] in KIND), None)
        kind = KIND[w[k]] if k is not None else 'd'
        key = tuple('*' if i == k else x for i, x in enumerate(w))
        out[fn] = (kind, key, {x for i, x in enumerate(w) if i != k and not x.isdigit() and x not in GENERIC})
    return out


def find_file(name, texdir):
    """a linked texture's file in the folder: same name, or same name with another image extension"""
    base = os.path.basename(name.replace('\\', '/')).lower()
    stem = base.split('.')[0]
    files = os.listdir(texdir)
    for fn in files:
        if fn.lower() == base or fn.lower() == base + '.png':
            return fn
    for fn in files:
        if fn.lower().split('.')[0] == stem and fn.lower().endswith(IMAGES):
            return fn
    return None


def linked(scene):
    """{material name: {'d': file, 'n': file, ...}} from the textures the FBX connects to its materials"""
    out = {}
    for oid, o in scene.objects.items():
        if o.name != 'Material':
            continue
        for c, par, _, prop in scene.conn:
            if par != oid or c not in scene.objects or scene.objects[c].name != 'Texture':
                continue
            t = scene.objects[c]
            fn = t.get('RelativeFilename') or t.get('FileName')
            if not fn:
                continue
            p = (prop or '').lower()
            kind = 'n' if 'normal' in p or 'bump' in p else 'spec' if 'specular' in p else 'd' if 'diffuse' in p else None
            if kind:
                out.setdefault(scene.name(o), {}).setdefault(kind, fn.props[0])
    return out


def autotex(fbx, texdir, log=print, overrides=None):
    """(TEXTURES, MATERIALS, SKIP_MATERIALS, notes {material: why}, triangles per material); overrides
    {material: image file | (r, g, b) | 'skip'} replaces what is matched (the app's material table)"""
    scene = Scene(fbx)
    imgs = images(texdir) if texdir and os.path.isdir(texdir) else {}
    diffuse = [fn for fn, (k, _, _) in imgs.items() if k == 'd']
    common = set.intersection(*[imgs[fn][2] for fn in diffuse]) if len(diffuse) > 1 else set()

    # the skinned meshes' materials, their triangle counts, and repeated meshes
    tris, colour, skip, seen = {}, {}, [], []
    mcolour = {}
    for oid, o in scene.objects.items():
        if o.name == 'Material':
            p = props70(o)
            c = p.get('DiffuseColor') or p.get('Diffuse')
            mcolour[scene.name(o)] = [float(x) for x in c[-3:]] if c and len(c) >= 3 else None
    if hasattr(scene, 'material_colours'):
        mcolour.update(scene.material_colours())
    for m in scene.meshes():
        if not any(len(c['idx']) for c in m['skin'] or []):
            continue
        names = [m['matnames'][k] if k < len(m['matnames']) else '' for k in m['mat']]
        if getattr(scene, 'deduplicate_meshes', True):
            sig = np.sort(m['pos'], 0)                  # legacy FBX/OBJ duplicate heuristic stays unchanged
            if any(len(sig) == len(p) and len(m['tri']) == t and np.allclose(sig, p) for p, t in seen):
                for n in set(names):
                    if n not in skip:
                        skip.append(n)
                log('  mesh %s repeats another one: its materials are left out (%s)' % (m['name'], ', '.join(sorted(set(names)))))
                continue
            seen.append((sig, len(m['tri'])))
        for n in names:
            tris[n] = tris.get(n, 0) + 1
    tris = {n: k for n, k in tris.items() if n not in skip}
    links = scene.linked_textures() if hasattr(scene, 'linked_textures') else linked(scene)

    sets, materials, notes = {}, {}, {}

    def texture_set(d):
        """the set built on diffuse image d, with the normal / ORM / spec images named like it"""
        name = '_'.join(x for x in imgs[d][1] if x != '*') or 'tex'
        if name not in sets:
            ts = dict(d=d)
            for fn, (k, key, _) in imgs.items():
                if key == imgs[d][1] and k in ('n', 'orm', 'spec') and k not in ts:
                    ts[k] = fn
            with Image.open(os.path.join(texdir, d)) as im:
                side = max(im.size)
            size = 1 << max(7, min(10, side.bit_length() - 1))       # 128..1024
            ts['size'] = size
            if 'n' in ts:
                ts['nsize'] = max(256, size // 2)
            if 'spec' not in ts and 'orm' not in ts:
                ts['spec'] = 0.15
            elif 'spec' in ts:                          # a specular image: read as a grey mask
                ts['mask'] = ts.pop('spec')
                ts['mask_spec'] = (0.333, 0.333, 0.334, 0)
                ts['ssize'] = 512
            sets[name] = ts
        return name

    overrides = overrides or {}
    for mat in sorted(tris, key=lambda n: -tris[n]):
        v = overrides.get(mat)
        if v == 'skip':
            skip.append(mat); notes[mat] = 'left out (chosen)'
            continue
        if isinstance(v, str) and v in imgs:
            materials[mat] = texture_set(v); notes[mat] = 'chosen'
            continue
        if isinstance(v, (list, tuple)) and len(v) == 3:
            materials[mat] = tuple(int(x) for x in v); notes[mat] = 'chosen'
            continue
        if v is not None:
            log('  %r was chosen for %r but is not an image in the textures folder: matching it again' % (v, mat))
        lk = links.get(mat, {})
        d = find_file(lk['d'], texdir) if 'd' in lk and imgs else None
        if d:
            materials[mat] = texture_set(d); notes[mat] = 'linked in the FBX'
            n = find_file(lk['n'], texdir) if 'n' in lk else None
            if n and 'n' not in sets[materials[mat]]:          # a normal map the file links, not named like it
                sets[materials[mat]].update(n=n, nsize=max(256, sets[materials[mat]]['size'] // 2))
            continue
        mw = {x for x in words(mat) if not x.isdigit() and x not in GENERIC}
        score = {}
        for fn in diffuse:
            tw = imgs[fn][2] - common
            s = 2 * len(mw & tw) + sum(1 for g in SYNONYMS if g & mw and g & tw)
            if s:
                score[fn] = s
        if score:
            best = max(score, key=lambda fn: (score[fn], -len(imgs[fn][2])))
            materials[mat] = texture_set(best); notes[mat] = 'by name'
        elif len(diffuse) == 1:
            materials[mat] = texture_set(diffuse[0]); notes[mat] = 'the only image'
        elif mcolour.get(mat) and np.ptp(mcolour[mat]) > 0.05:
            materials[mat] = tuple(int(round(255 * min(max(x, 0), 1))) for x in mcolour[mat])
            notes[mat] = "the material's colour"
        else:
            notes[mat] = 'check'
    rest = [m for m in tris if m not in materials and m not in skip]
    if rest:
        if sets:
            biggest = max(sets, key=lambda s: sum(tris[m] for m, v in materials.items() if v == s))
            for m in rest:
                materials[m] = biggest
        else:
            for m in rest:
                c = mcolour.get(m) or [0.8, 0.8, 0.8]
                materials[m] = tuple(int(round(255 * min(max(x, 0), 1))) for x in c)
    for m in tris:
        log('  material %-24r %6d triangles -> %-20s (%s)' % (m, tris[m], materials.get(m, '-'), notes[m]))
    for n, ts in sets.items():
        log('  texture set %-14s %s' % (n, ', '.join('%s=%s' % kv for kv in ts.items())))
    if not imgs:
        log('  no images found%s: colours only' % (' in ' + texdir if texdir else ''))
    return sets, materials, skip, notes, tris


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    autotex(*sys.argv[1:])
