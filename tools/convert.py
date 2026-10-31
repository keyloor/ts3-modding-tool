"""Put a rigged FBX character into a Toy Story 3 character file (.oct + _0.vbuf + _0.ibuf).

  python convert.py <ts3 dir> <base name> <fbx> <textures dir> <map .py file> <out dir>

The map file is the mod's per-character table module (see mods/ts5_characters/maps/buzz_map.py).

The game's skeleton, animation network and bind pose stay as they are; the FBX mesh is fitted onto that bind pose,
weighted to the game's bones, split into pieces of at most MAXB bones, and replaces every sub-geometry.

Textures: with no MATERIALS in the map, the first mesh of the file is used with one texture set found in the textures
dir by suffix (_BC, _N, _ORM). With MATERIALS, every skinned mesh is used and each FBX material goes to a texture set
of TEXTURES (one game material each), to a solid colour (r, g, b) or, listed in SKIP_MATERIALS, is left out.
"""
import importlib.util, io, os, struct, sys, zlib
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from octlib import Oct, Rec
from fbxlib import Scene
import ts3model as T

MAXB = 40          # bones per sub-geometry (the game's own pieces use up to 42)
TEX = 1024         # diffuse / normal map size
SPEC = 512


# ------------------------------------------------------------------------------------------- math
def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def rot_between(a, b):
    a, b = unit(a), unit(b)
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999:
        p = unit(np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]))
        return 2 * np.outer(p, p) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


# ------------------------------------------------------------------------------------------- fitting
def merge_meshes(scene, mp, log):
    """every skinned mesh of the file as one, already in the file's world (each mesh's own bind transform applied);
    normals and uvs per corner, 'mat' = FBX material name per triangle"""
    skip = set(getattr(mp, 'SKIP_MATERIALS', []))
    pos, cps, tris, nrm, uvs, mats, skin = [], [], [], [], [], [], {}
    ncp = ncorner = 0
    for m in scene.meshes():
        sk = m['skin'] or []
        if not any(len(c['idx']) for c in sk):
            continue
        names = np.array([m['matnames'][k] if k < len(m['matnames']) else '' for k in m['mat']], object)
        keep = np.array([n not in skip for n in names], bool)
        if not keep.any():
            log('  left out mesh %s (%s)' % (m['name'], ', '.join(sorted(set(names)))))
            continue
        c0 = [c for c in sk if len(c['idx'])][0]
        mg = c0['xf'] @ c0['xlink']
        R = mg[:3, :3] / np.linalg.norm(mg[:3, :3], axis=1, keepdims=True)
        nd, ns = m['normals']; ud, us = m['uv']
        pos.append((np.c_[m['pos'], np.ones(len(m['pos']))] @ mg)[:, :3])
        nrm.append(nd.reshape(-1, 3)[ns] @ R)
        uvs.append(ud.reshape(-1, 2)[us])
        cps.append(m['cp'] + ncp)
        tris.append(m['tri'][keep] + ncorner)
        mats.append(names[keep])
        for c in sk:
            s = skin.setdefault(c['bone'], dict(bone=c['bone'], idx=[], w=[], xf=np.eye(4), xlink=c['xlink']))
            s['idx'].append(c['idx'] + ncp); s['w'].append(c['w'])
        ncp += len(m['pos']); ncorner += len(m['cp'])
    for s in skin.values():
        s['idx'] = np.concatenate(s['idx']).astype(np.int64); s['w'] = np.concatenate(s['w'])
    nrm = np.concatenate(nrm); uv = np.concatenate(uvs)
    nmesh = len(mats)
    pos, cps, tris, mats = np.concatenate(pos), np.concatenate(cps), np.concatenate(tris), [np.concatenate(mats)]
    # SKIP_BONES: triangles whose corners all hang mostly on these bones are left out
    if getattr(mp, 'SKIP_BONES', None):
        w = np.zeros(ncp)
        for b in mp.SKIP_BONES:
            if b in skin:
                np.add.at(w, skin[b]['idx'], skin[b]['w'])
        keep = ~(w[cps[tris]] > 0.5).all(1)
        log('  left out %d triangles on %s' % ((~keep).sum(), ', '.join(mp.SKIP_BONES)))
        tris, mats = tris[keep], [mats[0][keep]]
    bad = ~np.isfinite(nrm).all(1)                     # broken normals in the file: the triangle's own instead
    for t in tris[bad[tris].any(1)]:
        p = pos[cps[t]]
        nrm[t[bad[t]]] = unit(np.cross(p[1] - p[0], p[2] - p[0]))
    if bad.any():
        log('  %d broken normals replaced' % bad.sum())
    return dict(name='%d meshes' % nmesh, pos=pos, cp=cps, tri=tris,
                normals=(nrm, np.arange(len(nrm))), uv=(uv, np.arange(len(uv))), mat=np.concatenate(mats),
                skin=list(skin.values()), mg=np.eye(4))


def fit(scene, mesh, bones3, mp, log):
    sk = mesh['skin']
    if 'mg' in mesh:
        mg = mesh['mg']
    else:
        mg = sk[[len(c['idx']) > 0 for c in sk].index(True)]['xf'] @ sk[[len(c['idx']) > 0 for c in sk].index(True)]['xlink']
    A = scene.to_yup()                                   # the file's world -> Y up, facing +Z
    P = (np.c_[mesh['pos'], np.ones(len(mesh['pos']))] @ mg)[:, :3] @ A
    R0 = (mg[:3, :3] / np.linalg.norm(mg[:3, :3], axis=1, keepdims=True)) @ A
    j5 = {c['bone']: c['xlink'][3, :3] @ A for c in sk}
    # JOINT_POS {model bone: (x, y, z)}: joints the user moved by hand (the file's units, Y up, facing +Z); they
    # only change where the bone's pivot is for the fit, the mesh and its weights stay the file's
    for k, v in getattr(mp, 'JOINT_POS', {}).items():
        if k in j5:
            j5[k] = np.asarray(v, float)
    if getattr(mp, 'JOINT_POS', None):
        log('  %d joints moved by hand' % len([k for k in mp.JOINT_POS if k in j5]))
    allb = scene.bones()
    byname = {b['name']: (oid, b) for oid, b in allb.items()}
    piv3 = {b['name']: np.array(b['pivot']) for b in bones3}
    cl = {c['bone']: c for c in sk}

    # open the eyes, around the eye centre (about the x axis), each vertex by its weight on the lid bones.
    # Angles are measured from straight ahead, up positive.
    #   'rotate': every lid vertex turns by EYE_OPEN_TOP / EYE_OPEN_BOTTOM degrees.
    #   'slide': the lid edge moves to EYE_TOP_EDGE / EYE_BOTTOM_EDGE and the lid skin between the edge and
    #            EYE_TOP_LIMIT / EYE_BOTTOM_LIMIT is squeezed, the skin past the limit stays; lid vertices that would
    #            end up inside the eyeball are pushed out over it.
    Rpre = np.tile(np.eye(3), (len(P), 1, 1))

    def lid_weight(bones_):
        w = np.zeros(len(P))
        for b in bones_:
            if b in cl:
                np.add.at(w, cl[b]['idx'], cl[b]['w'])
        return np.minimum(w, 1.0)

    def turn(i, a, e):
        c_, s_ = np.cos(a), np.sin(a)
        R = np.array([[1, 0, 0], [0, c_, -s_], [0, s_, c_]])
        P[i] = e + R @ (P[i] - e)
        Rpre[i] = R @ Rpre[i]

    parent = None

    def eyeball(seed, e, lids):
        """the eyeball: the mesh pieces (connected by triangles) centred on the eye, not counting the lids'"""
        nonlocal parent
        if parent is None:
            parent = np.arange(len(P))

            def root(a):
                while parent[a] != a:
                    parent[a] = parent[parent[a]]; a = parent[a]
                return a
            cps = mesh['cp'][mesh['tri']]
            for a, b, c_ in cps:
                ra, rb, rc = root(a), root(b), root(c_)
                parent[rb] = ra; parent[rc] = ra
            for a in range(len(P)):
                parent[a] = root(a)
        r_seed = float(np.median(np.linalg.norm(P[seed] - e, axis=1)))
        lid_pieces = set(parent[lids].tolist())
        keep = set()
        for k in set(parent[seed].tolist()):            # the iris' own pieces, unless joined to the face around it
            if np.linalg.norm(P[parent == k] - e, axis=1).max() < 1.5 * r_seed:
                keep.add(k)
        for k in np.unique(parent):
            if k in lid_pieces:
                continue
            v = P[parent == k]
            if len(v) >= 10 and np.linalg.norm(v.mean(0) - e) < 0.45 * r_seed and \
                    np.linalg.norm(v - e, axis=1).max() < 1.5 * r_seed:
                keep.add(k)
        ids = np.nonzero(np.isin(parent, list(keep)))[0]
        return ids if len(ids) else np.asarray(seed)

    mode = getattr(mp, 'EYE_MODE', 'rotate')
    for eye, tops, bots in getattr(mp, 'EYES', []):
        if eye not in j5:
            continue
        e = j5[eye]
        if mode == 'rotate':
            for bones_, deg in ((tops, mp.EYE_OPEN_TOP), (bots, -mp.EYE_OPEN_BOTTOM)):
                w = lid_weight(bones_)
                for i in np.nonzero(w)[0]:
                    turn(i, -np.radians(deg) * w[i], e)
            log('  opened %s: top lids %d deg, bottom lids %d deg' % (eye, mp.EYE_OPEN_TOP, mp.EYE_OPEN_BOTTOM))
            continue
        r_eye = float(np.median(np.linalg.norm(P[cl[eye]['idx']] - e, axis=1)))
        lid_ids = np.nonzero((lid_weight(tops) + lid_weight(bots)) > 0)[0]
        ball = eyeball(cl[eye]['idx'], e, lid_ids)      # the whole eyeball: the eye bone may carry only the iris
        log('  %s: eyeball %d points, reach %.2f..%.2f' % (eye, len(ball), np.linalg.norm(P[ball] - e, axis=1).min(),
                                                          np.linalg.norm(P[ball] - e, axis=1).max()))
        ev = P[ball] - e                                # the eyeball is not a sphere: its reach in each direction
        ev_r = np.linalg.norm(ev, axis=1); ev_u = ev / ev_r[:, None]

        def eye_reach(u):
            near = np.argsort(-(ev_u @ u))[:6]
            return float(ev_r[near].max())
        for bones_, edge, limit, top in ((tops, mp.EYE_TOP_EDGE, mp.EYE_TOP_LIMIT, True),
                                         (bots, mp.EYE_BOTTOM_EDGE, mp.EYE_BOTTOM_LIMIT, False)):
            w = lid_weight(bones_)
            ids = np.nonzero(w)[0]
            d = P[ids] - e
            ang = np.degrees(np.arctan2(d[:, 1], d[:, 2]))
            r = np.linalg.norm(d, axis=1)
            front = (np.abs(ang) < 100) & (r >= 0.95 * r_eye) & (w[ids] > 0.6)
            seam = float(np.percentile(ang[front], 3 if top else 97))     # where the shut lid's edge is now
            shift = edge - seam
            for k, i in enumerate(ids):
                t = ang[k]
                if abs(t) >= 100 or (top and t >= limit) or (not top and t <= limit):
                    continue
                if r[k] < 0.95 * r_eye and getattr(mp, 'EYE_KEEP_INNER', False):
                    continue                            # the lid's inner fold, hidden inside the eye: stays there
                if (top and t <= seam) or (not top and t >= seam):
                    t2 = t + shift
                else:                                   # squeeze the skin between the edge and the limit
                    t2 = limit + (t - limit) * (limit - seam - shift) / (limit - seam)
                turn(i, -np.radians((t2 - t) * w[i]), e)
                if r[k] >= 0.95 * r_eye:                # a lid on the eyeball stays on top of it
                    v = P[i] - e
                    n = np.linalg.norm(v)
                    need = 1.04 * max(r_eye, eye_reach(v / n))
                    if n < need:
                        P[i] = e + v * (need / n)
            log('  opened %s %s lid: edge %.0f -> %.0f deg, skin up to %.0f deg squeezed' % (eye, 'top' if top else 'bottom', seam, edge, limit))
            if os.environ.get('TS5_DEBUG_EYES'):
                d2 = P[ids] - e; n2 = np.linalg.norm(d2, axis=1); a2 = np.degrees(np.arctan2(d2[:, 1], d2[:, 2]))
                inside = [(round(float(a2[k])), round(float(n2[k] / eye_reach(d2[k] / n2[k])), 2), round(float(w[i]), 2), round(float(r[k] / r_eye), 2))
                          for k, i in enumerate(ids) if n2[k] < eye_reach(d2[k] / n2[k]) and abs(a2[k]) < 90]
                log('    inside the eye after: %d of %d (angle, r/reach, weight, r0/r_eye): %s' % (len(inside), len(ids), sorted(inside)[:40]))
            if top:
                top_ids, top_w = ids, w[ids]
        # lashes: each lash bone's part turns so its root sits on the opened upper lid's edge at the same x
        for lash in dict(getattr(mp, 'LASHES', [])).get(eye, []):
            if lash not in cl:
                continue
            li, lw = cl[lash]['idx'], cl[lash]['w']
            d = P[li] - e
            la = np.degrees(np.arctan2(d[:, 1], d[:, 2]))
            root = float(np.percentile(la[lw > 0.5], 10))
            lx0, lx1 = d[:, 0].min(), d[:, 0].max()
            dl = P[top_ids] - e
            near = (dl[:, 0] >= lx0 - 0.1 * r_eye) & (dl[:, 0] <= lx1 + 0.1 * r_eye) & (top_w > 0.6) & \
                   (np.linalg.norm(dl, axis=1) >= 0.95 * r_eye) & (np.abs(dl[:, 2]) > 0) & (dl[:, 2] > 0)
            if not near.any():
                continue
            lid_edge = float(np.percentile(np.degrees(np.arctan2(dl[near, 1], dl[near, 2])), 3))
            for k, i in enumerate(li):
                turn(i, -np.radians((lid_edge - root) * min(lw[k], 1.0)), e)
            log('  %s: root %.0f -> lid edge %.0f deg' % (lash, root, lid_edge))

    # overall size: least squares over the main joints (both skeletons stand on the floor at the origin)
    pairs = [(j5[a], piv3[b]) for a, b in mp.SCALE_JOINTS if a in j5]
    s = sum(float(np.dot(a, b)) for a, b in pairs) / sum(float(np.dot(a, a)) for a, _ in pairs)
    log('scale %.5f (model height %.2f -> %.3f)' % (s, P[:, 1].max(), P[:, 1].max() * s))

    xf = {}   # bone -> (M, p5, p3, R): v' = p3 + M (v - p5); R turns normals
    # torso: one block, per-axis scale and offset fitted to the landmarks
    L5 = np.array([j5[a] * s for a, _ in mp.LANDMARKS]); L3 = np.array([piv3[b] for _, b in mp.LANDMARKS])
    A = np.eye(3); off = np.zeros(3)
    for ax in range(3):
        x, y = L5[:, ax], L3[:, ax]
        if np.ptp(x) > 1e-3 and ax != 2:
            a, b = np.polyfit(x, y, 1)
            A[ax, ax] = float(np.clip(a, 0.8, 1.25)); off[ax] = float(np.mean(y - A[ax, ax] * x))
        else:
            off[ax] = float(np.mean(y - x))
    log('  torso block: scale %s, offset %s, landmark error %.3f' % (np.round(np.diag(A), 3), np.round(off, 3),
        np.abs(L5 @ A.T + off - L3).max()))
    # TORSO_SCALE (x, y, z): the map widens / lengthens / deepens the fitted block about the landmarks' middle
    if hasattr(mp, 'TORSO_SCALE'):
        c = L5.mean(0)
        for ax in range(3):
            a2 = A[ax, ax] * float(mp.TORSO_SCALE[ax])
            off[ax] += (A[ax, ax] - a2) * c[ax]
            A[ax, ax] = a2
        log('  torso block x %s -> scale %s' % (tuple(mp.TORSO_SCALE), np.round(np.diag(A), 3)))
    for k in mp.TORSO:
        xf[k] = (A, np.zeros(3), off, np.eye(3))

    # where the head goes: the move that best lines the face up with the game's face bones
    fa = [(a, b) for a, b in getattr(mp, 'FACE_ALIGN', []) if a in j5]
    face_off = np.mean([piv3[b] - j5[a] * s for a, b in fa], 0) if fa else None
    if fa:
        res = max(np.linalg.norm(piv3[b] - (j5[a] * s + face_off)) for a, b in fa)
        log('  face: head moved %s from the model, largest face-bone error %.3f' % (np.round(face_off, 3), res))

    # limbs, neck, head
    for k, (a, t, ta, opt) in mp.DRIVE.items():
        if k not in j5:
            log('  (model has no bone %s)' % k); continue
        p5 = j5[k] * s; p3 = piv3[t].copy()
        p3 += np.asarray(opt.get('offset', (0, 0, 0)))
        if opt.get('floor'):
            p3[1] = p5[1]
        if opt.get('face') and face_off is not None:
            p3 = p5 + face_off
        if a and a in j5:
            d5 = (j5[a] - j5[k]) * s
            q3 = piv3[ta].copy()
            q3 += np.asarray(opt.get('tip_offset', (0, 0, 0)))
            if opt.get('aim_floor'):
                q3[1] = j5[a][1] * s
            if opt.get('aim_face') and face_off is not None:
                q3 = j5[a] * s + face_off
            d3 = q3 - p3
            R = rot_between(d5, d3)
            # Most limbs should not be stretched too far.  A map can raise the
            # cap for an unusually short source neck or a deliberately stylised
            # rig, without changing the established conversions.
            kk = float(np.clip(np.linalg.norm(d3) / max(np.linalg.norm(d5), 1e-9),
                               0.8, opt.get('max_stretch', 1.25)))
            u = unit(d5)
            S = np.eye(3) + (kk - 1) * np.outer(u, u)
            ang = np.degrees(np.arccos(np.clip(np.dot(unit(d5), unit(d3)), -1, 1)))
            log('  %-12s -> %-14s turn %5.1f deg  stretch %.2f  move %.3f' % (k, t, ang, kk, np.linalg.norm(p3 - p5)))
        else:
            R, S = np.eye(3), np.eye(3)
            log('  %-12s -> %-14s move %.3f' % (k, t, np.linalg.norm(p3 - p5)))
        # GIRTH {model bone: k}: the map makes that part thicker / thinner across its segment (a part with no aim,
        # like the head, grows / shrinks as a whole about its pivot)
        if k in getattr(mp, 'GIRTH', {}):
            g = float(mp.GIRTH[k])
            S = S + (g - 1) * (np.eye(3) - np.outer(u, u)) if a and a in j5 else g * np.eye(3)
            log('  %-12s    girth x%.2f' % (k, g))
        xf[k] = (R @ S, p5, p3, R)

    def driver(name):
        cur = name
        while cur is not None:
            if cur in xf:
                return cur
            oid = byname[cur][0]
            par = allb[oid]['parent']
            cur = allb[par]['name'] if par in allb else None
        return mp.TORSO[0]

    ncp = len(P)
    newP = np.zeros((ncp, 3)); Rsum = np.zeros((ncp, 3, 3))
    W5 = np.zeros(ncp)
    w3 = {}
    for c in sk:
        if not len(c['idx']):
            continue
        M, p5, p3, R = xf[driver(c['bone'])]
        v = P[c['idx']] * s
        w = c['w'][:, None]
        newP[c['idx']] += w * ((v - p5) @ M.T + p3)
        Rsum[c['idx']] += w[:, :, None] * (R @ Rpre[c['idx']])
        W5[c['idx']] += c['w']
        tbs = mp.WEIGHTS.get(c['bone'])
        if tbs is None:
            tbs = mp.WEIGHTS[driver(c['bone'])] if driver(c['bone']) in mp.WEIGHTS else 'Hips'
            log('  weights of %s go to %s' % (c['bone'], tbs))
        # a game bone, or {game bone: share} to split a helper bone that moves part way between two joints;
        # WEIGHT_RAMP {model bone: (game bone a, game bone b, axis, at, bt)} goes from a to b along that axis of the
        # model (its own units, Y up) between at and bt, e.g. a sleeve from the chest to the arm
        ramp = getattr(mp, 'WEIGHT_RAMP', {}).get(c['bone'])
        if ramp:
            ga, gb, ax, at, bt = ramp
            share_b = np.clip((P[c['idx'], ax] - at) / (bt - at), 0, 1)
            shares = [(ga, 1 - share_b), (gb, share_b)]
        else:
            shares = tbs.items() if isinstance(tbs, dict) else [(tbs, 1.0)]
        for tb, share in shares:
            if not mp.FACE and tb in mp.FACE_BONES:
                tb = 'Head'
            if tb not in piv3:
                log('  the game has no bone %s: %s goes to Head' % (tb, c['bone']))
                tb = 'Head'
            w3.setdefault(tb, np.zeros(ncp))
            np.add.at(w3[tb], c['idx'], c['w'] * share)
    # bones whose game animation moves this model's parts too far: part of their weight goes to the head
    for tb, k in getattr(mp, 'WEIGHT_SCALE', {}).items():
        if tb in w3:
            w3.setdefault('Head', np.zeros(ncp))
            w3['Head'] += w3[tb] * (1 - k); w3[tb] *= k
            log('  %s moves %d%% as far' % (tb, k * 100))
    # WEIGHT_SMOOTH n: n passes averaging each point's game-bone weights with its neighbours' (softer bends)
    if getattr(mp, 'WEIGHT_SMOOTH', 0) and w3:
        e = mesh['cp'][mesh['tri']]
        e = np.r_[e[:, [0, 1]], e[:, [1, 2]], e[:, [2, 0]]]
        e = np.unique(np.sort(e, 1), axis=0)
        deg = np.bincount(e.ravel(), minlength=ncp).astype(float)
        names = list(w3)
        Wm = np.array([w3[n] for n in names])
        total = Wm.sum(0)
        for _ in range(int(mp.WEIGHT_SMOOTH)):
            acc = Wm.copy()
            np.add.at(acc.T, e[:, 0], Wm[:, e[:, 1]].T)
            np.add.at(acc.T, e[:, 1], Wm[:, e[:, 0]].T)
            Wm = acc / (1 + deg)
            Wm *= total / np.maximum(Wm.sum(0), 1e-12)
        w3 = dict(zip(names, Wm))
        log('  weights smoothed, %d passes' % int(mp.WEIGHT_SMOOTH))
    if (W5 < 0.99).any():
        used = np.zeros(ncp, bool); used[mesh['cp'][mesh['tri']]] = True
        log('  %d vertices without full weights (%d of them used, %d with none)' % (
            (W5 < 0.99).sum(), ((W5 < 0.99) & used).sum(), ((W5 == 0) & used).sum()))
    newP /= np.maximum(W5, 1e-9)[:, None]
    # Optional, per-material proportion correction after the skeleton fit.
    # This is useful for loose clothing in a source model; the game skeleton
    # should not have to be distorted just to narrow one garment.  Values are
    # (x, y, z), centred on the game hips.
    for material, scale in getattr(mp, 'MATERIAL_SCALE', {}).items():
        tri = mesh['tri'][mesh['mat'] == material]
        if not len(tri):
            continue
        ids = np.unique(mesh['cp'][tri])
        centre = piv3['Hips']
        newP[ids] = centre + (newP[ids] - centre) * np.asarray(scale)
        log('  scaled material %s by %s about Hips' % (material, scale))
    return newP, Rsum, R0, w3


# ------------------------------------------------------------------------------------------- vertices
def build_vertices(mesh, newP, Rsum, R0, w3, ids3):
    tri = mesh['tri']                                   # polygon-vertex (corner) indices, (n, 3)
    corners = tri.reshape(-1)
    cp = mesh['cp'][corners]
    nd, nsel = mesh['normals']; ud, usel = mesh['uv']
    nrm = nd.reshape(-1, 3)[nsel[corners]] @ R0         # mesh space -> world (rotation part of the bind)
    nrm = unit(np.einsum('nij,nj->ni', Rsum[cp], nrm))
    uv = ud.reshape(-1, 2)[usel[corners]].copy()
    uv[:, 1] = 1 - uv[:, 1]                             # game textures start at the top
    key = np.c_[cp, np.round(uv * 8192), np.round(nrm * 512)].astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    V = dict(cp=cp[first], uv=uv[first], n=nrm[first])
    V['p'] = newP[V['cp']]
    idx = inv.reshape(-1, 3)
    # tangent frame per vertex from the triangles
    p, t = V['p'], V['uv']
    a, b, c = idx[:, 0], idx[:, 1], idx[:, 2]
    e1, e2 = p[b] - p[a], p[c] - p[a]; d1, d2 = t[b] - t[a], t[c] - t[a]
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    du = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    dv = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    TT = np.zeros_like(p); BB = np.zeros_like(p)
    for k in range(3):
        np.add.at(TT, idx[:, k], du); np.add.at(BB, idx[:, k], dv)
    n = V['n']
    tg = unit(TT - n * (TT * n).sum(1, keepdims=True))
    bad = np.linalg.norm(tg, axis=1) < 0.5
    tg[bad] = unit(np.cross(n[bad], [0, 0, 1]) + 1e-6)
    bn = np.cross(tg, n)                                # the game stores B = T x N
    flip = (bn * BB).sum(1) < 0                         # mirrored UVs: keep B along dP/dv
    bn[flip] *= -1
    V['t'], V['b'] = tg, bn
    # game bone weights: top 4, summing to 255
    names = sorted(w3, key=lambda k: ids3[k])
    Wm = np.stack([w3[k][V['cp']] for k in names], 1)
    order = np.argsort(-Wm, axis=1)[:, :4]
    top = np.take_along_axis(Wm, order, 1)
    top = top / top.sum(1, keepdims=True)
    q = np.floor(top * 255).astype(int)
    q[:, 0] += 255 - q.sum(1)
    V['bid'] = np.array([ids3[k] for k in names])[order]   # game BoneIDs
    V['bw'] = q
    V['bid'][q == 0] = V['bid'][:, :1].repeat(4, 1)[q == 0]
    face = (np.cross(e1, e2) * (n[a] + n[b] + n[c])).sum(1)
    if (face < 0).mean() > 0.5:                         # wind triangles the way the game does
        idx = idx[:, [0, 2, 1]]
    return V, idx


def split(V, idx):
    """sub-geometries of at most MAXB bones; each gets its own copy of its vertices"""
    tb = [set(V['bid'][i][V['bw'][i] > 0]) | set(V['bid'][j][V['bw'][j] > 0]) | set(V['bid'][k][V['bw'][k] > 0])
          for i, j, k in idx]
    dom = V['bid'][idx[:, 0], 0]
    order = np.lexsort((np.arange(len(idx)), dom))
    groups, cur, bones = [], [], set()
    for t in order:
        if len(bones | tb[t]) > MAXB:
            groups.append((cur, bones)); cur, bones = [], set()
        cur.append(t); bones |= tb[t]
    groups.append((cur, bones))
    return groups


# ------------------------------------------------------------------------------------------- textures
def dds_header(template, w, h, mips, linear):
    hd = bytearray(template[:128])
    struct.pack_into('<IIII', hd, 12, h, w, linear, 0)
    struct.pack_into('<I', hd, 28, mips)
    return bytes(hd)


def mip_chain(im, size):
    im = im.convert('RGB').resize((size, size), Image.LANCZOS)
    out = [im]
    while out[-1].size[0] > 1:
        s = max(1, out[-1].size[0] // 2)
        out.append(out[-1].resize((s, s), Image.LANCZOS))
    return out


def dxt1(im, size, template):
    levels = mip_chain(im, size)
    body = b''
    for lv in levels:
        x = lv if lv.size[0] >= 4 else lv.resize((4, 4))
        bio = io.BytesIO(); x.save(bio, 'DDS', pixel_format='DXT1')
        body += bio.getvalue()[128:]
    return dds_header(template, size, size, len(levels), size * size // 2) + body


def bgrx(im, size, template):
    levels = mip_chain(im, size)
    body = b''
    for lv in levels:
        a = np.asarray(lv, dtype=np.uint8)
        x = np.zeros(a.shape[:2] + (4,), np.uint8); x[..., 0] = a[..., 2]; x[..., 1] = a[..., 1]; x[..., 2] = a[..., 0]
        body += x.tobytes()
    return dds_header(template, size, size, len(levels), size * 4) + body


# ------------------------------------------------------------------------------------------- .oct editing
def block(f, i):
    return [Rec(r.type, r.level, r.name, r.pay) for r in f.recs[i:f.end_of(i)]]


def set_key(f, blk, s):
    blk[0].pay = struct.pack('<H', f.add_name(s)) + blk[0].pay[2:]


def setv(f, blk, name, vals, names=False):
    for r in blk:
        if f.nm(r.name) == name and r.level == blk[0].level + 1:
            r.set_items([f.add_name(v) for v in vals] if names else vals)
            return r
    raise KeyError(name)


def subrec(f, blk, path):
    """record in a block by a path of names below its head"""
    lv = blk[0].level; i = 0
    for k, name in enumerate(path):
        while True:
            i += 1
            if i >= len(blk) or blk[i].level <= lv + k:
                raise KeyError('/'.join(path))
            if blk[i].level == lv + k + 1 and f.nm(blk[i].name) == name:
                break
    return blk[i]


def replace_pool(f, pool_name, new_children, keep=None):
    pi = f.find(pool_name)[0]
    kids = f.children(pi)
    old = [block(f, k) for k in kids]
    keep = old if keep is None else [old[k] for k in keep]
    flat = [r for b in keep + new_children for r in b]
    f.recs[pi + 1:f.end_of(pi)] = flat
    return len(keep)


SWATCH = 16                 # palette texture: pixels per solid colour


def mask_spec(ts, texdir):
    """specular (0..1 per pixel) from a mask texture: its R, G, B, A channels weighted by the set's 'mask_spec'"""
    mk = np.asarray(Image.open(os.path.join(texdir, ts['mask'])).convert('RGBA')).astype(np.float32) / 255
    return np.clip(mk @ np.array(ts['mask_spec'], np.float32), 0, 1)


def texture_sets(mp, mesh, texdir):
    """[(set name, settings)], set index per triangle. Solid colours go to one palette set and their corners' uvs onto
    their swatch (so this changes mesh['uv']): the map's (r, g, b) materials and, in sets with 'solid', the triangles
    whose uvs all sit on one texel (their colour is read there, then changed by the set's 'recolor'). On a texel they
    would take in the colours around it at a distance (mip maps); on a swatch they keep theirs."""
    if not hasattr(mp, 'MATERIALS'):
        def find(sfx):
            for fn in os.listdir(texdir):
                if ('_' + sfx + '.') in fn.lower():
                    return fn
            raise SystemExit('no %s texture in %s' % (sfx, texdir))
        return [('', dict(d=find('bc'), n=find('n'), orm=find('orm')))], np.zeros(len(mesh['tri']), int)
    names = list(mp.TEXTURES)
    uvd, uvs = mesh['uv']
    tri_set = np.full(len(mesh['tri']), -1)
    swatches = {}                                       # (r, g, b, spec) -> triangles
    for mname in np.unique(mesh['mat']):
        if mname not in mp.MATERIALS:
            raise SystemExit('FBX material %r is not in MATERIALS or SKIP_MATERIALS' % mname)
        v = mp.MATERIALS[mname]
        sel = np.nonzero(mesh['mat'] == mname)[0]
        if isinstance(v, str):
            tri_set[sel] = names.index(v)
        else:
            swatches.setdefault(tuple(int(x) for x in v) + (getattr(mp, 'COLOR_SPEC', 0.3),), []).append(sel)
    for k, n in enumerate(names):
        ts = mp.TEXTURES[n]
        if not ts.get('solid'):
            continue
        img = np.asarray(Image.open(os.path.join(texdir, ts['d'])).convert('RGB'))
        sel = np.nonzero(tri_set == k)[0]
        tu = uvd[uvs[mesh['tri'][sel]]]                 # (triangles, 3 corners, uv): all corners within 2 texels
        sel = sel[np.ptp(tu, axis=1).max(1) * max(img.shape[:2]) < 2]
        spec = mask_spec(ts, texdir) if ts.get('mask') else None
        u = uvd[uvs[mesh['tri'][sel, 0]]] % 1
        px = np.minimum((u[:, 0] * img.shape[1]).astype(int), img.shape[1] - 1)
        py = np.minimum(((1 - u[:, 1]) * img.shape[0]).astype(int), img.shape[0] - 1)
        cols = img[py, px].astype(int)
        sp = spec[np.minimum(py * spec.shape[0] // img.shape[0], spec.shape[0] - 1),
                  np.minimum(px * spec.shape[1] // img.shape[1], spec.shape[1] - 1)] if spec is not None \
            else np.full(len(sel), ts.get('spec', 0.2))
        for (r, g, b), new in ts.get('recolor', {}).items():
            cols[(cols == (r, g, b)).all(1)] = new
        keys = [tuple(c) + (round(float(s), 2),) for c, s in zip(cols.tolist(), sp)]
        for key in set(keys):
            swatches.setdefault(key, []).append(sel[[i for i, kk in enumerate(keys) if kk == key]])
        tri_set[sel] = -2
    sets = [(n, dict(mp.TEXTURES[n])) for n in names]
    if swatches:
        side = 8
        while side * side < len(swatches):
            side *= 2
        pal = Image.new('RGB', (side, side)); pspec = Image.new('L', (side, side))
        for k, (key, parts) in enumerate(swatches.items()):
            pal.putpixel((k % side, k // side), key[:3]); pspec.putpixel((k % side, k // side), int(255 * key[3]))
            tris = np.concatenate(parts)
            uvd[uvs[mesh['tri'][tris].reshape(-1)]] = ((k % side + 0.5) / side, 1 - (k // side + 0.5) / side)
            tri_set[tris] = len(names)
        big = side * SWATCH
        sets.append(('colors', dict(d=pal.resize((big, big), Image.NEAREST), size=big, nsize=16, ssize=big,
                                    spec_image=pspec.resize((big, big), Image.NEAREST).convert('RGB'))))
    used = sorted(set(tri_set.tolist()))
    return [sets[k] for k in used], np.searchsorted(used, tri_set)


def load_map(path):
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    return mp


def run(ts3dir, base, fbx, texdir, mappath, out):
    os.makedirs(out, exist_ok=True)
    lines = []

    def log(s):
        print(s); lines.append(s)
    mp = load_map(mappath)
    f, bones3, subs, remaps, ist, vst = T.load(os.path.join(ts3dir, base + '.oct'))
    ids3 = {b['name']: b['id'] for b in bones3}
    prefix = getattr(mp, 'PREFIX', 'ts5')
    scene = Scene(fbx)
    mesh = merge_meshes(scene, mp, log) if hasattr(mp, 'MATERIALS') else next(scene.meshes())
    log('FBX mesh %s: %d points, %d triangles, %d bones' % (mesh['name'], len(mesh['pos']), len(mesh['tri']), len(mesh['skin'])))
    sets, tri_set = texture_sets(mp, mesh, texdir)
    newP, Rsum, R0, w3 = fit(scene, mesh, bones3, mp, log)
    V, idx = build_vertices(mesh, newP, Rsum, R0, w3, ids3)
    groups = []                                         # (triangles, bones, texture set)
    for k in range(len(sets)):
        sel = np.nonzero(tri_set == k)[0]
        groups += [(sel[tris], bset, k) for tris, bset in split(V, idx[sel])]
    log('%d vertices, %d triangles, %d pieces (bones per piece: %s)' % (len(V['p']), len(idx), len(groups), [len(g[1]) for g in groups]))
    if len(sets) > 1:
        log('texture sets: %s' % ', '.join('%s (%d triangles)' % (n, (tri_set == k).sum()) for k, (n, _) in enumerate(sets)))

    # the game's pieces that stay (e.g. jetpack flames): every other lit piece is replaced
    keep_pat = [p.lower() for p in getattr(mp, 'KEEP_PIECES', [])]
    nodes = T.pool(f, 'SceneTreeNodePool')
    geos = [dict(node=k, rec=i, name=T.field(f, i, 'NodeName')[0], kind=T.field(f, i, 'Type')[0],
                 vs=T.field(f, i, 'VertexStreamReferences'), ist=T.field(f, i, 'IndexStreamReference')[0],
                 sc=T.field(f, i, 'SceneComponentReferences', [None])[0], parent=T.field(f, i, 'ParentNodeReferences')[0])
            for k, i in enumerate(nodes) if T.field(f, i, 'Type', [''])[0] in ('SubGeometryLit', 'SubGeometry')]
    kept = [g for g in geos if g['kind'] != 'SubGeometryLit' or any(p in g['name'].lower() for p in keep_pat)]
    gone = [g for g in geos if g not in kept]
    log('kept from the game: %s' % [g['name'] for g in kept])

    # vertex/index buffers: each piece its own vertices, one stream pair for all
    s0, s1, ibs, pieces = [], [], [], []
    base_v = 0; ioff = 0
    for tris, bset, tset in groups:
        pal = sorted(bset)
        slot = {b: i for i, b in enumerate(pal)}
        vs = np.unique(idx[tris])
        remap = {v: k for k, v in enumerate(vs)}
        loc = np.vectorize(remap.get)(idx[tris]) + base_v
        a0 = np.zeros(len(vs), T.S0); a1 = np.zeros(len(vs), T.S1)
        a0['p'] = V['p'][vs]; a0['uv'] = V['uv'][vs]; a0['bw'] = V['bw'][vs]
        a0['bi'] = np.vectorize(slot.get)(V['bid'][vs])
        for k, src in (('t', 't'), ('n', 'n'), ('b', 'b')):
            x = np.zeros((len(vs), 4)); x[:, :3] = V[src][vs]; a1[k] = x
        s0.append(a0); s1.append(a1)
        ib = loc.astype('<u2').reshape(-1); ibs.append(ib)
        pieces.append(dict(remap=pal, ioff=ioff, ilen=len(ib), center=V['p'][vs].mean(0), nv=len(vs), mat=tset))
        base_v += len(vs); ioff += ib.nbytes
    if base_v > 65535:
        raise SystemExit('too many vertices for 16-bit indices: %d' % base_v)
    s0 = np.concatenate(s0); s1 = np.concatenate(s1)
    vbuf = s0.tobytes() + s1.tobytes(); ibuf = b''.join(x.tobytes() for x in ibs)

    # the kept pieces' streams, index streams and skin remaps go after the new ones, their bytes copied as they are
    vb_old = open(os.path.join(ts3dir, base + '_0.vbuf'), 'rb').read()
    ib_old = open(os.path.join(ts3dir, base + '_0.ibuf'), 'rb').read()
    vs_pool, is_pool, sc_pool = T.pool(f, 'VertexStreamPool'), T.pool(f, 'IndexStreamPool'), T.pool(f, 'SceneComponentPool')
    vs_map, is_map, sc_map = {}, {}, {}
    kept_vs, kept_is, kept_sc = [], [], []
    for g in kept:
        for v in g['vs']:
            if v not in vs_map:
                vs_map[v] = 2 + len(kept_vs)
                st = vst[v]; n = st['len'] * st['width']
                b = block(f, vs_pool[v]); set_key(f, b, str(vs_map[v])); setv(f, b, 'VertexBufferOffset', [len(vbuf)])
                vbuf += vb_old[st['off']:st['off'] + n]; kept_vs.append(b)
        if g['ist'] not in is_map:
            is_map[g['ist']] = len(pieces) + len(kept_is)
            st = ist[g['ist']]
            b = block(f, is_pool[g['ist']]); set_key(f, b, str(is_map[g['ist']])); setv(f, b, 'IndexBufferOffset', [len(ibuf)])
            ibuf += ib_old[st['off']:st['off'] + st['len'] * 2]; kept_is.append(b)
        if g['sc'] is not None and g['sc'] not in sc_map:
            sc_map[g['sc']] = len(pieces) + len(kept_sc)
            b = block(f, sc_pool[g['sc']]); set_key(f, b, str(sc_map[g['sc']])); kept_sc.append(b)
    open(os.path.join(out, base + '_0.vbuf'), 'wb').write(vbuf)
    open(os.path.join(out, base + '_0.ibuf'), 'wb').write(ibuf)
    log('vbuf %d bytes, ibuf %d bytes, %d new vertices' % (len(vbuf), len(ibuf), base_v))

    # templates for the new records, chosen by what they hold
    def elems(i):
        return [T.field(f, e, 'Name')[0] for e in f.children(f.child(i, 'Elements'))]
    vt0 = [k for k, i in enumerate(vs_pool) if elems(i) == ['Position', 'BoneIndices', 'BlendWeights', 'Uv1'] and vst[k]['width'] == 24][0]
    vt1 = [k for k, i in enumerate(vs_pool) if elems(i) == ['Tangent', 'Normal', 'Binormal']][0]
    sub_tmpl = [g for g in gone if g['kind'] == 'SubGeometryLit' and vt1 in g['vs']][0]
    body = max(set(g['parent'] for g in gone), key=[g['parent'] for g in gone].count)

    # ---- .oct: in-place edits first, then pools from the back of the file to the front
    keep_nodes = [k for k in range(len(nodes)) if k not in {g['node'] for g in gone}]
    node_map = {old: new for new, old in enumerate(keep_nodes)}
    for i in (T.pool(f, 'AssociationPool') if f.find('AssociationPool') else []):
        j = f.child(i, 'SceneTreeNodeRef')
        if j is not None:
            f.recs[j].set_items([node_map[f.value(j)[0]]])
    tex_pool = T.pool(f, 'TexturePool'); mat_pool = T.pool(f, 'MaterialPool')
    n_tex, n_mat = len(tex_pool), len(mat_pool)
    new_nodes = []
    for k, pc in enumerate(pieces):
        b = block(f, nodes[sub_tmpl['node']])
        set_key(f, b, str(len(keep_nodes) + k))
        setv(f, b, 'ParentNodeReferences', [node_map[body]])
        setv(f, b, 'BoundingCenter', [float(x) for x in pc['center']])
        setv(f, b, 'NodeName', ['%s_%s_%d' % (prefix, base, k)], names=True)
        setv(f, b, 'MaterialReference', [n_mat + pc['mat']])
        setv(f, b, 'VertexStreamReferences', [0, 1])
        setv(f, b, 'IndexStreamReference', [k])
        setv(f, b, 'SceneComponentReferences', [k])
        new_nodes.append(b)
    # bones: assigned vertex counts and bounds (bone space)
    vid = np.zeros((len(s0), 4), int)                   # game BoneID of each vertex's 4 slots
    o = 0
    for pc in pieces:
        vid[o:o + pc['nv']] = np.array(pc['remap'])[s0['bi'][o:o + pc['nv']]]; o += pc['nv']
    for bn in bones3:
        rec = bn['rec']
        has = ((vid == bn['id']) & (s0['bw'] > 0)).any(1)
        domn = (vid[np.arange(len(s0)), np.argmax(s0['bw'], 1)] == bn['id'])
        f.recs[f.child(rec, 'NumAssignedVerts')].set_items([int(domn.sum())])
        if has.any():
            inv = np.linalg.inv(bn['b2m'])
            lp = (np.c_[s0['p'][has], np.ones(has.sum())] @ inv)[:, :3]
            bb = list(map(float, np.r_[lp.min(0), lp.max(0)]))
        else:
            bb = [0.0] * 6
        f.recs[f.child(rec, 'BoundingBox')].set_items(bb)
    # whole-model bounds
    lo, hi = s0['p'].min(0).astype(float), s0['p'].max(0).astype(float)
    for gi in [i for i in nodes if T.field(f, i, 'Type', [''])[0] == 'Geometry']:
        c = (lo + hi) / 2
        f.recs[f.child(gi, 'BoundingBox')].set_items(list(map(float, np.r_[lo, hi])))
        f.recs[f.child(gi, 'BoundingOBBCenter')].set_items(list(map(float, c)))
        f.recs[f.child(gi, 'BoundingOBBExtents')].set_items(list(map(float, (hi - lo) / 2)))
        f.recs[f.child(gi, 'BoundingSphereCenter')].set_items(list(map(float, c)))
        f.recs[f.child(gi, 'BoundingSphereRadius')].set_items([float(np.linalg.norm(s0['p'] - c, axis=1).max())])
    # the node pool: kept nodes renumbered (and their references), then the new pieces
    kn = []
    gk = {g['node']: g for g in kept}
    for k in keep_nodes:
        b = block(f, nodes[k]); set_key(f, b, str(node_map[k]))
        for ref in ('ParentNodeReferences', 'ParentGeometryReference'):
            old = [x for r in b if f.nm(r.name) == ref and r.level == b[0].level + 1 for x in r.items()[1]]
            if old:
                setv(f, b, ref, [node_map[x] for x in old])
        if k in gk:
            g = gk[k]
            setv(f, b, 'VertexStreamReferences', [vs_map[v] for v in g['vs']])
            setv(f, b, 'IndexStreamReference', [is_map[g['ist']]])
            if g['sc'] is not None:
                setv(f, b, 'SceneComponentReferences', [sc_map[g['sc']]])
        kn.append(b)
    replace_pool(f, 'SceneTreeNodePool', kn + new_nodes, keep=[])

    sc = []
    sc_tmpl = [i for i in sc_pool if T.field(f, i, 'Type', [''])[0] == 'SkinRemap'][0]
    for k, pc in enumerate(pieces):
        b = block(f, sc_tmpl); set_key(f, b, str(k)); setv(f, b, 'RemapData', pc['remap']); sc.append(b)
    replace_pool(f, 'SceneComponentPool', sc + kept_sc, keep=[])

    v0, v1 = block(f, vs_pool[vt0]), block(f, vs_pool[vt1])
    for k, (b, off) in enumerate(((v0, 0), (v1, len(s0) * 24))):
        set_key(f, b, str(k)); setv(f, b, 'Length', [len(s0)]); setv(f, b, 'VertexBufferOffset', [off])
    replace_pool(f, 'VertexStreamPool', [v0, v1] + kept_vs, keep=[])

    nis = []
    for k, pc in enumerate(pieces):
        b = block(f, is_pool[0]); set_key(f, b, str(k))
        setv(f, b, 'Length', [pc['ilen']]); setv(f, b, 'IndexBufferOffset', [pc['ioff']]); nis.append(b)
    replace_pool(f, 'IndexStreamPool', nis + kept_is, keep=[])

    f.recs[f.child(T.pool(f, 'IndexBufferPool')[0], 'Size')].set_items([len(ibuf)])
    f.recs[f.child(T.pool(f, 'VertexBufferPool')[0], 'Size')].set_items([len(vbuf)])

    # materials, one per texture set: a skin shader with diffuse, normal and specular maps that this character's
    # archive ships
    effect = getattr(mp, 'MATERIAL_EFFECT', 'a_1_dmnsmqdrqcf_skin')
    mtmpl = [i for i in mat_pool if T.field(f, i, 'Effect', [''])[0] == effect][0]
    nm_ = []
    for s, (sname, _) in enumerate(sets):
        m = block(f, mtmpl)
        set_key(f, m, str(n_mat + s))
        setv(f, m, 'Name', ['%s_%s%s' % (prefix.upper(), base, '_' + sname if sname else '')], names=True)
        uu = subrec(f, m, ['Uuid']); raw = bytearray(uu.items()[1]); raw[-1] ^= 0x5A + s; uu.set_items(bytes(raw))
        ent = [k for k, r in enumerate(m) if f.nm(r.name) == 'TextureEntry']
        for k in ent:
            tr = m[k + 1]; us = m[k + 2]
            u = f.nm(us.items()[1][0])
            tr.set_items([n_tex + 3 * s + {'diffuseMapA1': 0, 'normalMapA1': 1, 'specularMapA1': 2}[u]])
        nm_.append(m)
    replace_pool(f, 'MaterialPool', nm_)

    # textures: diffuse, normal, specular per set
    def tex_head(i):
        return bytes(f.recs[f.child(i, 'Data')].items()[1][:128])
    t_dxt = [i for i in tex_pool if tex_head(i)[84:88] == b'DXT1'][0]                  # a colour map
    t_raw = [i for i in tex_pool if struct.unpack_from('<I', tex_head(i), 88)[0] == 32][0]  # a 32-bit normal map
    tpl_d, tpl_n = tex_head(t_dxt), tex_head(t_raw)

    def image(v):
        return v if isinstance(v, Image.Image) else Image.open(os.path.join(texdir, v))
    nt = []
    for s, (sname, ts) in enumerate(sets):
        size, nsize, ssize = ts.get('size', TEX), ts.get('nsize', TEX), ts.get('ssize', SPEC)
        bc = image(ts['d'])
        nm = image(ts['n']) if ts.get('n') else Image.new('RGB', (nsize, nsize), (128, 128, 255))
        if ts.get('orm'):
            orm = np.asarray(image(ts['orm']).convert('RGB')).astype(np.float32) / 255
            spec = np.clip((1 - orm[..., 1]) ** 2 * orm[..., 0] * 0.9 + 0.05, 0, 1)
            spec_im = Image.fromarray((spec * 255).astype(np.uint8)).convert('RGB')
        elif ts.get('spec_image'):
            spec_im = ts['spec_image']
        elif ts.get('mask'):
            spec_im = Image.fromarray((mask_spec(ts, texdir) * 255).astype(np.uint8)).convert('RGB')
        else:
            spec_im = Image.new('RGB', (ssize, ssize), (int(255 * ts.get('spec', 0.2)),) * 3)
        datas = [('d', dxt1(bc, size, tpl_d), t_dxt), ('n', bgrx(nm, nsize, tpl_n), t_raw),
                 ('s', dxt1(spec_im, ssize, tpl_d), t_dxt)]
        for k, (sfx, data, tmpl_i) in enumerate(datas):
            b = block(f, tmpl_i); set_key(f, b, str(n_tex + 3 * s + k))
            nmv = '%s_%s_%s%s' % (prefix, base, sname + '_' if sname else '', sfx)
            setv(f, b, 'Name', [nmv], names=True)
            setv(f, b, 'SourceFilePath', ['characters\\%s\\%s.png' % (prefix, nmv)], names=True)
            setv(f, b, 'DataCRC', [zlib.crc32(data) - (1 << 32) if zlib.crc32(data) >= (1 << 31) else zlib.crc32(data)])
            subrec(f, b, ['Data']).set_items(data)
            nt.append(b)
    replace_pool(f, 'TexturePool', nt)
    f.save(os.path.join(out, base + '.oct'))
    log('wrote %s' % os.path.join(out, base + '.oct'))
    open(os.path.join(out, 'convert.log'), 'w').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    run(*sys.argv[1:7])
