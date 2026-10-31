"""Models without a skeleton (.obj + .mtl): read them and give them one, so the rest of the kit uses them like a
rigged FBX.

An OBJ has no skeleton and no skin. They are made here from the model's shape and the game character's skeleton:
  1. the model is turned to Y up, facing +Z (an OBJ doesn't say: a model lying along Z is turned up; feet pointing to -Z
     mean it faces backwards) and set on the floor, centred;
  2. the game's skeleton is stretched onto it: the legs from the floor to the crotch, the torso and the head up to the
     top, the shoulders as wide as the hips allow, and each arm from its shoulder to the farthest point of that side
     (the fingertips), with the game's proportions along each limb;
  3. every vertex is weighted to its nearest bones (an arm's bones only past the clavicle, a leg's only below the
     hips, never the other side's), most to the nearest, at most 3.
automap.py then maps that skeleton like any other. Works for humanoids in a T or A pose; the hands and the face move
in one piece (with the hand / the head).

open_scene(path) is what the kit uses instead of fbxlib.Scene: an ObjScene for .obj files, an fbxlib.Scene otherwise.
use_game(dir, base) says which game character the skeleton comes from (automap.automap sets it).
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401  (puts the shared tools on sys.path)
import fbxlib
import ts3model as T

GAME = None                  # (game character dir, base name)
_cache = {}


def use_game(ts3dir, base):
    global GAME
    GAME = (os.path.abspath(ts3dir), base)


def open_scene(path):
    if not path.lower().endswith('.obj'):
        return fbxlib.Scene(path)
    key = (os.path.abspath(path), os.path.getmtime(path), GAME)
    if key not in _cache:
        _cache.clear()
        _cache[key] = ObjScene(path, GAME)
    return _cache[key]


# ------------------------------------------------------------------------------------------- reading
def read_mtl(path):
    """{material: {'colour': (r, g, b) 0..1, 'd' / 'n' / 'spec': image file}}"""
    mats, cur = {}, None
    for line in open(path, encoding='utf-8', errors='replace'):
        p = line.strip().split(None, 1)
        if len(p) < 2:
            continue
        k, rest = p[0].lower(), p[1].strip()
        if k == 'newmtl':
            cur = mats.setdefault(rest, {})
        elif cur is None:
            continue
        elif k == 'kd':
            try:
                cur['colour'] = tuple(float(x) for x in rest.split()[:3])
            except ValueError:
                pass
        elif k in ('map_kd', 'map_bump', 'bump', 'norm', 'map_ks'):
            fn = rest.split()[-1] if rest.startswith('-') else rest      # options ('-bm 1 file') come first
            cur.setdefault({'map_kd': 'd', 'map_ks': 'spec'}.get(k, 'n'), os.path.basename(fn.replace('\\', '/')))
    return mats


def read_obj(path):
    """positions, per-corner (position, uv, normal) indices, polygons as corner ranges, material per polygon"""
    V, VT, VN = [], [], []
    cv, ct, cn, poly, pmat = [], [], [], [], []
    matnames, mtl, cur = [], {}, 0
    for line in open(path, encoding='utf-8', errors='replace'):
        if not line or line[0] == '#':
            continue
        p = line.split()
        if not p:
            continue
        k = p[0]
        if k == 'v':
            V.append([float(x) for x in p[1:4]])
        elif k == 'vt':
            VT.append([float(x) for x in p[1:3]] if len(p) >= 3 else [float(p[1]), 0.0])
        elif k == 'vn':
            VN.append([float(x) for x in p[1:4]])
        elif k == 'f':
            start = len(cv)
            for c in p[1:]:
                s = (c.split('/') + ['', ''])[:3]
                cv.append(int(s[0]) - 1 if int(s[0]) > 0 else len(V) + int(s[0]))
                ct.append((int(s[1]) - 1 if int(s[1]) > 0 else len(VT) + int(s[1])) if s[1] else -1)
                cn.append((int(s[2]) - 1 if int(s[2]) > 0 else len(VN) + int(s[2])) if s[2] else -1)
            if len(cv) - start >= 3:
                poly.append((start, len(cv))); pmat.append(cur)
            else:
                del cv[start:], ct[start:], cn[start:]
        elif k == 'usemtl':
            name = line.split(None, 1)[1].strip() if len(p) > 1 else 'default'
            if name not in matnames:
                matnames.append(name)
            cur = matnames.index(name)
        elif k == 'mtllib':
            for fn in [line.split(None, 1)[1].strip()]:
                m = os.path.join(os.path.dirname(path), fn)
                if os.path.isfile(m):
                    mtl.update(read_mtl(m))
    if not V or not poly:
        raise ValueError('%s has no faces' % os.path.basename(path))
    return (np.array(V, float), np.array(VT, float).reshape(-1, 2), np.array(VN, float).reshape(-1, 3),
            np.array(cv), np.array(ct), np.array(cn), poly, np.array(pmat), matnames or ['default'], mtl)


# ------------------------------------------------------------------------------------------- the skeleton
def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def section(P, edges, axis, value):
    """where the mesh crosses the plane P[:, axis] = value: one point per edge that crosses it. Unlike the vertices
    near the plane, this works however big the triangles are (low-poly models have long, empty stretches)."""
    a, b = P[edges[:, 0]], P[edges[:, 1]]
    da, db = a[:, axis] - value, b[:, axis] - value
    m = da * db < 0
    t = da[m] / (da[m] - db[m])
    return a[m] + t[:, None] * (b[m] - a[m])


def arm_landmarks(P, edges, H, sd):
    """fingertip, shoulder and arm thickness of one side. The arm is followed inwards in vertical cuts through the
    mesh (from 70% of the fingertip's reach, where only the arm is), its centre tracked from cut to cut; the torso
    starts at the first cut whose points around that centre spread over more than 2.2 arm thicknesses. The shoulder
    joint sits half an arm thickness inside that. Works for T and lowered (A) arms; a drooping hand doesn't tilt it."""
    side = P[P[:, 0] * sd > 0]
    tip = side[np.argmax(side[:, 0] * sd)]
    tx = float(tip[0] * sd)
    step = 0.01 * H
    x = 0.7 * tx
    cut = section(P, edges, 0, sd * x)
    cut = cut[np.abs(cut[:, 1] - np.median(cut[:, 1])) < 0.15 * H] if len(cut) else cut
    if len(cut) < 2:
        return tip, np.array([sd * 0.25 * tx, tip[1], tip[2]]), 0.06 * H
    th = max(float(np.ptp(cut[:, 1])), 0.01 * H)        # the arm's thickness (taller if the arm is lowered)
    centres = [(x, float(cut[:, 1].min() + cut[:, 1].max()) / 2, float(cut[:, 2].mean()))]
    edge = None
    while x > 0.05 * H:
        x -= step
        cut = section(P, edges, 0, sd * x)
        if len(centres) >= 2:                            # where the arm's centre line is heading
            (x1, y1, _), (x2, y2, _) = centres[-2], centres[-1]
            pred = y2 + (y2 - y1) / (x2 - x1) * (x - x2)
        else:
            pred = centres[-1][1]
        near = cut[np.abs(cut[:, 1] - pred) < 3 * th] if len(cut) else cut
        arm = cut[np.abs(cut[:, 1] - pred) < max(0.8 * th, 0.02 * H)] if len(cut) else cut
        if len(near) >= 2 and np.ptp(near[:, 1]) > 2.2 * th and len(centres) >= 3:
            edge = x
            break
        if len(arm) >= 2:
            centres.append((x, float(arm[:, 1].min() + arm[:, 1].max()) / 2, float(arm[:, 2].mean())))
    xe, ye, ze = centres[-1] if edge is None else (edge, centres[-1][1], centres[-1][2])
    shoulder = np.array([sd * max(xe - 0.5 * th, 0.03 * H), ye, ze])
    return tip, shoulder, th


def narrowest(P, y0, H):
    """the height of the narrowest horizontal slice of points P (near the middle: no arms) between y0 and the top"""
    best = None
    for y in np.arange(y0 + 0.01 * H, 0.97 * H, 0.005 * H):
        sl = P[(np.abs(P[:, 1] - y) < 0.006 * H) & (np.abs(P[:, 0]) < 0.25 * H)]
        if len(sl) > 2 and (best is None or np.ptp(sl[:, 0]) < best[0]):
            best = (float(np.ptp(sl[:, 0])), float(y))
    return best[1] if best else y0 + 0.1 * H


def landmarks(P, tris, H):
    """what the model's own shape says: crotch height, neck (narrowest slice above the arms) height, and per side the
    fingertip, where the arm meets the torso and the arm's thickness"""
    out = {}
    # crotch: the lowest triangle crossing the middle plane (x = 0) above the shins
    tx = P[tris][:, :, 0]
    ty = P[tris][:, :, 1].mean(1)
    cross = (tx.min(1) < 0) & (tx.max(1) > 0) & (ty > 0.2 * H) & (np.ptp(tx, 1) < 0.15 * H)
    out['crotch'] = float(ty[cross].min()) if cross.any() else None
    edges = np.unique(np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), 1), axis=0)
    for sd, s in ((1, 'Left'), (-1, 'Right')):
        tip, shoulder, th = arm_landmarks(P, edges, H, sd)
        d = tip - shoulder
        out['tip' + s], out['dir' + s], out['shoulder' + s], out['arm' + s] = tip, d / np.linalg.norm(d), shoulder, th
    # neck: the narrowest horizontal cut between the shoulders and the top (only near the middle: no arms)
    sy = min(out['shoulderLeft'][1], out['shoulderRight'][1])
    best = None
    for y in np.arange(sy + 0.01 * H, 0.97 * H, 0.005 * H):
        cut = section(P, edges, 1, y)
        cut = cut[np.abs(cut[:, 0]) < 0.25 * H] if len(cut) else cut
        if len(cut) > 2:
            w = float(np.ptp(cut[:, 0]))
            if best is None or w < best[0]:
                best = (w, y)
    out['neck'] = best[1] if best else None
    return out


def rig(P, game_dir, base, tris=None):
    """bones {name: (parent, position)} fitted to the model's points P (Y up, facing +Z, on the floor, centred) and
    skin weights {bone: (vertex indices, weights)}"""
    _, bones3, *_ = T.load(os.path.join(game_dir, base + '.oct'))
    lower = {b['name'].lower(): np.array(b['pivot'], float) for b in bones3}

    def G(*names):
        for n in names:
            if n.lower() in lower:
                return lower[n.lower()].copy()
        raise ValueError('the game character %s has no bone %s' % (base, names[0]))
    import render as RD
    GP = np.concatenate([p[0] for p in RD.load_mesh(game_dir, base)[0]])
    Hg, H = float(GP[:, 1].max()), float(P[:, 1].max())
    s0 = H / Hg
    out = {}
    lm = landmarks(P, tris, H) if tris is not None else {'crotch': None, 'neck': None}

    # legs: the hip joints a little above the crotch
    hip_g = G('ThighLeft')
    expect = hip_g[1] * s0
    hipY = lm['crotch'] + 0.035 * H if lm['crotch'] else expect
    if not 0.3 * H < hipY < 0.7 * H:               # a skirt or a robe hides the crotch: the game's proportions
        hipY = expect
    for sd, s in ((1, 'Left'), (-1, 'Right')):
        band = P[(P[:, 0] * sd > 0.01 * H) & (P[:, 1] > 0.45 * hipY) & (P[:, 1] < 0.6 * hipY)]
        hx = float(np.median(band[:, 0])) if len(band) else hip_g[0] * sd * s0
        hz = float(np.median(band[:, 2])) if len(band) else 0.0
        gt, gc, gf, go = G('Thigh' + s), G('Calf' + s), G('Foot' + s), G('Toes' + s)
        ky = hipY / gt[1]

        def leg(g):
            return np.array([hx + (g[0] - gt[0]) * s0, g[1] * ky, hz + (g[2] - gt[2]) * s0])
        out['Thigh' + s] = ('Hips', leg(gt))
        out['Calf' + s] = ('Thigh' + s, leg(gc))
        out['Foot' + s] = ('Calf' + s, leg(gf))
        out['Toes' + s] = ('Foot' + s, leg(go))

    # torso: the spine from the hips to the shoulders in the game's proportions; the neck from the shoulders to its
    # narrowest point, the head above it
    def middle_z(y):
        sl = P[(np.abs(P[:, 0]) < 0.08 * H) & (np.abs(P[:, 1] - y) < 0.03 * H)]
        return float(np.median(sl[:, 2])) if len(sl) else 0.0
    gh_, gb_ = G('Hips'), G('BicepLeft')
    sy = float(np.mean([lm['shoulderLeft'][1], lm['shoulderRight'][1]])) if 'shoulderLeft' in lm else \
        hipY + (gb_[1] - hip_g[1]) * s0
    hips_y = hipY + (gh_[1] - hip_g[1]) * s0
    neck_y = lm['neck'] if lm.get('neck') and lm['neck'] > sy else sy + 0.4 * (H - sy)
    # the neck and head joints where the game character has them, measured the same way: as fractions of the span
    # from its shoulders to the narrowest cut of its neck (Woody: the neck joint at 0.76 of it, the head 0.40 above)
    g_narrow = narrowest(GP, gb_[1], Hg)
    span_g, span = max(g_narrow - gb_[1], 1e-6), neck_y - sy
    f_neck = float(np.clip((G('Neck')[1] - gb_[1]) / span_g, 0.2, 1.0))
    f_head = float(np.clip((G('Head')[1] - g_narrow) / span_g, 0.0, 1.0))
    ys = {'Hips': hips_y, 'Neck': sy + f_neck * span, 'Head': neck_y + f_head * span}
    for n in ('Spine1', 'Spine2', 'Spine3'):
        ys[n] = hips_y + (G(n)[1] - gh_[1]) / (gb_[1] - gh_[1]) * (sy - hips_y)
    for n, par in (('Hips', None), ('Spine1', 'Hips'), ('Spine2', 'Spine1'), ('Spine3', 'Spine2'), ('Neck', 'Spine3'),
                   ('Head', 'Neck')):
        out[n] = (par, np.array([0.0, ys[n], middle_z(ys[n])]))

    # arms: from where each arm meets the torso to its farthest point (the fingertips), in the game's proportions
    for sd, s in ((1, 'Left'), (-1, 'Right')):
        gb, gfa, gh = G('Bicep' + s), G('Forearm' + s), G('Hand' + s)
        gtip = GP[np.argmax(GP[:, 0] * sd)]
        if 'tip' + s in lm:
            tip, sh = lm['tip' + s], lm['shoulder' + s].copy()
        else:
            side = P[P[:, 0] * sd > 0]
            tip = side[np.argmax(side[:, 0] * sd)]
            sh = np.array([gb[0] * s0, sy, out['Spine3'][1][2]])
        cl = np.array([sh[0] * 0.3, sh[1], sh[2]])
        L = np.linalg.norm(gtip - gb)
        fe, fh = np.linalg.norm(gfa - gb) / L, np.linalg.norm(gh - gb) / L
        out['Clavicle' + s] = ('Spine3', cl)
        out['Bicep' + s] = ('Clavicle' + s, sh)
        out['Forearm' + s] = ('Bicep' + s, sh + fe * (tip - sh))
        out['Hand' + s] = ('Forearm' + s, sh + fh * (tip - sh))
        out['_tip' + s] = (None, tip)

    # weights: each bone is the segment to its child (to the fingertip, the toe tip, the top of the head)
    ends = {'Hips': 'Spine1', 'Spine1': 'Spine2', 'Spine2': 'Spine3', 'Spine3': 'Neck', 'Neck': 'Head'}
    seg = {n: (out[n][1], out[ends[n]][1]) for n in ends}
    seg['Head'] = (out['Head'][1], np.array([0.0, H, out['Head'][1][2]]))
    for s in ('Left', 'Right'):
        seg['Clavicle' + s] = (out['Clavicle' + s][1], out['Bicep' + s][1])
        seg['Bicep' + s] = (out['Bicep' + s][1], out['Forearm' + s][1])
        seg['Forearm' + s] = (out['Forearm' + s][1], out['Hand' + s][1])
        seg['Hand' + s] = (out['Hand' + s][1], out['_tip' + s][1])
        seg['Thigh' + s] = (out['Thigh' + s][1], out['Calf' + s][1])
        seg['Calf' + s] = (out['Calf' + s][1], out['Foot' + s][1])
        foot, toe = out['Foot' + s][1], out['Toes' + s][1]
        seg['Foot' + s] = (foot, toe)
        seg['Toes' + s] = (toe, toe + (toe - foot) * 0.6)
    names = list(seg)
    D = np.stack([seg_dist(P, *seg[n]) for n in names], 1)
    x, y = P[:, 0], P[:, 1]
    for k, n in enumerate(names):
        if n.endswith(('Left', 'Right')):
            sd = 1 if n.endswith('Left') else -1
            ok = x * sd > -0.01 * H                                   # never the other side
            if n.startswith(('Clavicle', 'Bicep', 'Forearm', 'Hand')):
                ok &= x * sd > abs(out['Clavicle' + ('Left' if sd > 0 else 'Right')][1][0])
            else:
                ok &= y < hipY + 0.04 * H
            D[~ok, k] = np.inf
    W = 1 / np.maximum(D, 0.004 * H) ** 4
    top = np.argsort(-W, 1)[:, 3:]                                    # keep the 3 nearest
    np.put_along_axis(W, top, 0, 1)
    W /= W.sum(1, keepdims=True)
    W[W < 0.03] = 0
    W /= W.sum(1, keepdims=True)
    skin = {n: (np.nonzero(W[:, k])[0], W[np.nonzero(W[:, k])[0], k]) for k, n in enumerate(names)}
    return {n: v for n, v in out.items() if not n.startswith('_')}, skin


# ------------------------------------------------------------------------------------------- the scene
class ObjScene:
    """the part of fbxlib.Scene the kit uses: meshes() (one mesh, skinned to the fitted skeleton), bones(),
    to_yup(); plus the .mtl's textures and colours for autotex"""

    def __init__(self, path, game):
        V, VT, VN, cv, ct, cn, poly, pmat, self.matnames, self.mtl = read_obj(path)
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.settings, self.objects, self.conn = {}, {}, []
        # Y up (the model's thinnest axis is front-back; with Y the thinnest it was lying along Z), on the floor
        ext = np.ptp(V, 0)
        R = np.eye(3)
        if ext[1] <= ext[0] and ext[1] <= ext[2]:
            R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)   # (x, y, z) -> (x, z, -y)
        P = V @ R
        N = VN @ R
        H = np.ptp(P[:, 1])
        P[:, 1] -= P[:, 1].min()
        # facing: the feet point forward, ahead of the shins
        feet = P[P[:, 1] < 0.04 * H]; shins = P[(P[:, 1] > 0.1 * H) & (P[:, 1] < 0.2 * H)]
        if len(feet) and len(shins) and np.median(feet[:, 2]) < np.median(shins[:, 2]):
            P[:, [0, 2]] *= -1; N[:, [0, 2]] *= -1
        P[:, 0] -= (P[:, 0].min() + P[:, 0].max()) / 2
        P[:, 2] -= np.median(P[P[:, 1] < 0.5 * H][:, 2]) if (P[:, 1] < 0.5 * H).any() else 0
        self.P = P
        # triangles (fans) over corners; normals per corner, computed when the file has none
        tri = np.array([(s, k, k + 1) for s, e in poly for k in range(s + 1, e - 1)], np.int64)
        self.tri_mat = np.repeat(pmat, [e - s - 2 for s, e in poly])
        if (cn < 0).any() or not len(N):
            fn = np.cross(P[cv[tri[:, 1]]] - P[cv[tri[:, 0]]], P[cv[tri[:, 2]]] - P[cv[tri[:, 0]]])
            vn = np.zeros_like(P)
            for k in range(3):
                np.add.at(vn, cv[tri[:, k]], fn)
            vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
            N, cn = vn, cv.copy()
        uv = VT if len(VT) else np.zeros((1, 2))
        ct = np.where(ct < 0, 0, ct) if len(VT) else np.zeros_like(cv)
        self.mesh = dict(name=self.name, pos=P, cp=cv, tri=tri, normals=(N.reshape(-1), cn), uv=(uv.reshape(-1), ct),
                         mat=self.tri_mat, matnames=self.matnames, model=None)
        if game:
            self.skel, skin = rig(P, *game, tris=cv[tri])
        else:                                   # no game character given: one bone moves everything
            self.skel, skin = {'Hips': (None, np.zeros(3))}, {'Hips': (np.arange(len(P)), np.ones(len(P)))}
        self.mesh['skin'] = []
        for n, (idx, w) in skin.items():
            xl = np.eye(4); xl[3, :3] = self.skel[n][1]
            self.mesh['skin'].append(dict(bone=n, bone_id=n, idx=idx, w=w, xf=np.linalg.inv(xl), xlink=xl))

    def to_yup(self):
        return np.eye(3)

    def meshes(self):
        yield self.mesh

    def bones(self):
        return {n: dict(name=n, parent=par, props={}, kind='LimbNode') for n, (par, _) in self.skel.items()}

    def linked_textures(self):
        return {m: {k: v for k, v in d.items() if k in ('d', 'n', 'spec')} for m, d in self.mtl.items()}

    def material_colours(self):
        return {m: list(d['colour']) for m, d in self.mtl.items() if 'colour' in d}
