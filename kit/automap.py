"""Write a converter map for a rigged humanoid FBX, without a hand-made table of bone names.

  python automap.py <fbx> <game character dir> <base name> <out map .py> [<textures dir>]

With a textures dir the map also gets TEXTURES / MATERIALS / SKIP_MATERIALS (autotex.py): every skinned mesh is used.
Without it, only the FBX's first mesh, with the images found by suffix (_BC, _N, _ORM) when converting.

The body is found by the skeleton's shape, in the game's frame (Y up, facing +Z, the character's left at +x):
  feet   the lowest skinned bone on each side
  hands  from the most lateral bone on each side, up to the first bone where 2+ chains branch (the fingers)
  hips   the common ancestor of both feet; chest: of both hands; the torso is everything above them
  legs   hip = first bone below the hips, knee = the bone nearest half way to the ankle, toe if it points forward
  arms   clavicle if it is short, then the shoulder; elbow = the bone nearest half way to the hand
  head   the biggest branch of the chest that is not an arm, followed down until a bone named 'head' or with 3+ branches
  fingers  the thumb starts nearest the wrist; the others by name, else front to back (index first)
Twist and helper bones between two joints take the upper joint's game bone; any other bone takes its nearest mapped
ancestor's. Face bones stay on Head (FACE = False): the jaw, lips and brows found by name are listed in FACE_BONES, so
FACE = True moves them with the game's face bones.

The game's bone names are looked up in that character's own skeleton (Buzz has SternumLeft and IndexLeft1 where
Woody has ClavicleLeft and Index1Left).
"""
import os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401  (puts the shared tools on sys.path)
import objlib
from objlib import open_scene as Scene                 # an FBX, or an OBJ given a skeleton (objlib.py)
import ts3model as T
from about import CREDIT

SIDES = ((1, 'Left'), (-1, 'Right'))
FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')
FINGER_WORDS = {'Thumb': {'thumb', 'thmb'}, 'Index': {'index', 'pointer', 'point', 'fore'},
                'Middle': {'middle', 'mid'}, 'Ring': {'ring'}, 'Pinky': {'pinky', 'pinkie', 'little', 'small'}}
# which fingers a hand with fewer than four (besides the thumb) has
FINGER_SETS = {1: ['Middle'], 2: ['Index', 'Middle'], 3: ['Index', 'Middle', 'Ring'],
               4: ['Index', 'Middle', 'Ring', 'Pinky']}
KEEP_BY_CHARACTER = {'buzz': ['JetPack_Flame']}       # game pieces a model usually lacks


def words(name):
    """'mixamorig:LeftUpLeg' -> ['mixamorig', 'left', 'up', 'leg']"""
    return [w.lower() for w in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+', name)]


class Skeleton:
    """the FBX's bones: names, tree, and the bind position (game frame) and vertex count of every skinned one"""

    def __init__(self, fbx):
        scene = Scene(fbx)
        A = scene.to_yup()
        allb = scene.bones()
        self.parent = {b['name']: (allb[b['parent']]['name'] if b['parent'] in allb else None) for b in allb.values()}
        self.kids = {n: [] for n in self.parent}
        for n, p in self.parent.items():
            if p is not None:
                self.kids[p].append(n)
        self.pos, self.nv = {}, {}
        for m in scene.meshes():
            for c in m['skin'] or []:
                if c['bone'] not in self.parent:
                    continue
                self.nv[c['bone']] = self.nv.get(c['bone'], 0) + len(c['idx'])
                if len(c['idx']) or c['bone'] not in self.pos:
                    self.pos[c['bone']] = c['xlink'][3, :3] @ A
        self.skinned = {n for n, k in self.nv.items() if k > 0}
        if not self.skinned:
            raise ValueError('the FBX has no skinned mesh (no bone moves any vertex)')
        y = np.array([self.pos[n][1] for n in self.skinned])
        self.height = float(y.max() - y.min())
        self._count = {}

    def count(self, n):
        """skinned bones in n's subtree, n included"""
        if n not in self._count:
            self._count[n] = (n in self.skinned) + sum(self.count(k) for k in self.kids[n])
        return self._count[n]

    def branches(self, n):
        return [k for k in self.kids[n] if self.count(k)]

    def ancestors(self, n):
        out = []
        while n is not None:
            out.append(n); n = self.parent[n]
        return out

    def lca(self, a, b):
        up = set(self.ancestors(a))
        return next(n for n in self.ancestors(b) if n in up)

    def path(self, top, n):
        """bones from below top down to n"""
        out, start = [], n
        while n != top:
            if n is None:
                raise ValueError('%s is not below %s in the skeleton' % (start, top))
            out.append(n); n = self.parent[n]
        return out[::-1]

    def subtree(self, n):
        out = [n]
        for k in self.kids[n]:
            out += self.subtree(k)
        return out

    def chain(self, n):
        """n, then always the child with the most skinned bones: a finger, a neck"""
        out = [n]
        while self.branches(out[-1]):
            out.append(max(self.branches(out[-1]), key=self.count))
        return out


def game_names(bones3):
    lower = {b['name'].lower(): b['name'] for b in bones3}

    def find(*cands):
        for c in cands:
            if c.lower() in lower:
                return lower[c.lower()]
        return None
    return find


ROLES = ['pelvis', 'chest', 'neck', 'head'] + ['%s%s' % (r, s) for _, s in SIDES
                                               for r in ('clavicle', 'shoulder', 'elbow', 'hand', 'hip', 'knee', 'foot', 'toe')]


def find_body(sk, log, ov=None):
    """the body's bones; ov {role: model bone, or '' for none} replaces what is found (the app's bone table)"""
    H = sk.height
    P = sk.pos
    body = {}
    ov = ov or {}

    def pick(role, auto):
        if role not in ov:
            return auto
        v = ov[role] or None
        if v is not None and v not in sk.parent:
            raise ValueError('the model has no bone %r (given for %s)' % (v, role))
        if v is not None and v not in P:
            raise ValueError('%s (given for %s) moves no vertex' % (v, role))
        return v
    for sd, side in SIDES:
        on_side = [n for n in sk.skinned if P[n][0] * sd > 0.03 * H]
        if not on_side:
            raise ValueError('no bones on the %s side: is the model in a T or A pose, facing forward?' % side.lower())
        foot = min(on_side, key=lambda n: (round(P[n][1] / (0.01 * H)), -P[n][2]))
        tip = max(on_side, key=lambda n: P[n][0] * sd)
        hand = tip
        for n in sk.ancestors(tip)[1:]:         # 3+ fingers may reach far (Buzz's big hands: 16% of his height)
            d = np.linalg.norm(P.get(n, P[tip]) - P[tip])
            nb = len(sk.branches(n))
            if d > 0.3 * H:
                break
            if nb >= 3 or nb == 2 and d <= 0.15 * H:
                hand = n
                break
        body['foot_tip' + side] = pick('toe' + side, None) or pick('foot' + side, None) or foot
        body['hand' + side] = pick('hand' + side, hand)
    pelvis = pick('pelvis', sk.lca(body['foot_tipLeft'], body['foot_tipRight']))
    chest = pick('chest', sk.lca(body['handLeft'], body['handRight']))
    root = sk.lca(pelvis, chest)
    body.update(pelvis=pelvis, chest=chest, root=root)
    if chest in sk.ancestors(pelvis) and chest != root:
        raise ValueError('the hands branch off below the hips (%s, %s)' % (chest, pelvis))

    # legs
    for sd, side in SIDES:
        leg = [n for n in sk.path(pelvis, body['foot_tip' + side]) if n in P]
        hip = pick('hip' + side, leg[0])
        low = leg[-1]
        prev = leg[-2] if len(leg) > 2 else None
        if prev is not None and P[low][2] - P[prev][2] > 0.5 * abs(P[low][1] - P[prev][1]):
            foot, toe = prev, low
        else:
            foot, toe = low, None
        foot, toe = pick('foot' + side, foot), pick('toe' + side, toe)
        if toe and foot not in sk.ancestors(toe):
            raise ValueError('the %s toes (%s) are not below the foot (%s)' % (side.lower(), toe, foot))
        mid = [n for n in sk.path(hip, foot)[:-1] if n in P]
        if not mid:
            raise ValueError('the %s leg has no knee between %s and %s' % (side.lower(), hip, foot))
        half = (P[hip][1] + P[foot][1]) / 2
        knee = pick('knee' + side, min((n for n in mid if n in sk.skinned), key=lambda n: abs(P[n][1] - half),
                                       default=mid[0]))
        if knee not in mid:
            raise ValueError('the %s knee (%s) is not between %s and %s' % (side.lower(), knee, hip, foot))
        body.update({'hip' + side: hip, 'knee' + side: knee, 'foot' + side: foot, 'toe' + side: toe})

    # arms
    for sd, side in SIDES:
        hand = body['hand' + side]
        arm = [n for n in sk.path(chest, hand) if n in P]
        if len(arm) < 3:
            raise ValueError('the %s arm is too short (%s)' % (side.lower(), ' > '.join(arm)))
        # a clavicle is short next to the rest of the arm (Buzz's armour makes it long, so not next to the chest)
        clav = arm[0] if len(arm) >= 4 and \
            np.linalg.norm(P[arm[1]] - P[arm[0]]) < np.linalg.norm(P[hand] - P[arm[1]]) / 2.5 else None
        clav = pick('clavicle' + side, clav)
        shoulder = pick('shoulder' + side, arm[1] if clav else arm[0])
        if shoulder not in arm or clav and clav not in arm[:arm.index(shoulder)]:
            raise ValueError('the %s shoulder (%s) must be on the way from the chest to the hand, below the clavicle'
                             % (side.lower(), shoulder))
        mid = arm[arm.index(shoulder) + 1:-1]
        if not mid:
            raise ValueError('the %s arm has no elbow between %s and %s' % (side.lower(), shoulder, hand))
        half = (P[shoulder] + P[hand]) / 2
        elbow = pick('elbow' + side, min((n for n in mid if n in sk.skinned), key=lambda n: np.linalg.norm(P[n] - half),
                                         default=mid[0]))
        if elbow not in mid:
            raise ValueError('the %s elbow (%s) is not between %s and %s' % (side.lower(), elbow, shoulder, hand))
        body.update({'clavicle' + side: clav, 'shoulder' + side: shoulder, 'elbow' + side: elbow})

        # fingers
        # finger chains (a held prop, like Bo Peep's staff on 'Bip001_Prop1', is not a finger: it follows the hand)
        chains = [[n for n in sk.chain(b) if n in sk.skinned] for b in sk.branches(hand)
                  if not {'prop', 'weapon', 'item', 'attach', 'grip', 'gun', 'sword', 'staff'} & set(words(b))]
        chains = [c for c in chains if c]
        named, rest = {}, []
        for c in chains:
            w = set(sum((words(n) for n in c), []))
            f = next((f for f in FINGERS if FINGER_WORDS[f] & w and f not in named), None)
            if f:
                named[f] = c
            else:
                rest.append(c)
        if 'Thumb' not in named and len(rest) + len(named) >= 2 and rest:
            t = min(rest, key=lambda c: np.linalg.norm(P[c[0]] - P[hand]))
            named['Thumb'] = t; rest.remove(t)
        free = [f for f in FINGER_SETS.get(len(rest) + len([f for f in named if f != 'Thumb']), FINGERS[1:])
                if f not in named]
        for f, c in zip(free, sorted(rest, key=lambda c: -P[c[0]][2])):
            named[f] = c
        for f, c in named.items():
            body['finger_%s%s' % (f, side)] = c

    # neck and head: the biggest branch of the chest that is not an arm
    arms = {sk.path(chest, body['hand' + s])[0] for _, s in SIDES}
    top = [k for k in sk.branches(chest) if k not in arms]
    if not top:
        raise ValueError('nothing above the chest (%s) but the arms' % chest)
    cur = max(top, key=lambda k: (sk.count(k), P.get(k, np.zeros(3))[1]))
    neck = []
    while True:
        w = words(cur)
        if 'head' in w and not {'neck', 'top', 'end', 'nub'} & set(w):
            break
        br = sk.branches(cur)
        if len(br) >= 3 or not br:
            break
        neck.append(cur)
        cur = max(br, key=sk.count)
    head = pick('head', cur)
    if head != cur:
        neck = sk.path(chest, head)[:-1]
    neck = [n for n in neck if n in P]
    if 'neck' in ov:
        neck = [pick('neck', None)] if ov['neck'] else []
    body.update(neck=neck, head=head)
    return body


BODY_WORDS = {'hips', 'spine', 'neck', 'head', 'clavicle', 'sternum', 'bicep', 'forearm', 'hand', 'thigh', 'calf',
              'foot', 'toes', 'toe', 'leg', 'elbow', 'index', 'middle', 'midddle', 'ring', 'pinky', 'thumb', 'jaw',
              'lip', 'brow', 'eye', 'lid', 'btm', 'carry', 'attach', 'origin', 'main', 'body', 'pivot', 'root'}


def accessories(bones3, used):
    """the game character's extra bones (hat, holster, hair, wings...): {game bone: (its words but the side, side)}"""
    out = {}
    for b in bones3:
        w = set(words(b['name']))
        if b['name'] in used or w & BODY_WORDS:
            continue
        side = 'left' if 'left' in w else 'right' if 'right' in w else None
        out[b['name']] = (w - {'left', 'right'}, side)
    return out


def match_accessory(n, acc, P, height):
    w = set(words(n))
    side = None
    if n in P and abs(P[n][0]) > 0.01 * height:
        side = 'left' if P[n][0] > 0 else 'right'
    best = [(len(gw), g) for g, (gw, gs) in acc.items() if gw and gw <= w and (gs is None or gs == side)]
    return max(best)[1] if best else None


def face_roles(sk, head):
    """face bones by name (basic mode keeps them on Head): {model bone: game role}"""
    out = {}
    P = sk.pos
    hx = P[head][0] if head in P else 0
    for n in sk.subtree(head)[1:]:
        w = set(words(n))
        if n not in sk.skinned or w & {'adj', 'twist', 'roll', 'helper', 'end'}:
            continue
        side = 'Left' if P[n][0] - hx > 0.005 * sk.height else 'Right' if P[n][0] - hx < -0.005 * sk.height else ''
        if 'jaw' in w:
            out.setdefault('jaw', n)
        elif 'brow' in w or 'eyebrow' in w:
            out.setdefault('brow' + (side or 'Middle'), n)
        elif ('lip' in w or 'mouth' in w) and ({'corner', 'cor', 'edge'} & w):
            if side:
                out.setdefault('lipcorner' + side, n)
        elif 'lip' in w and not side:
            if w & {'upper', 'top', 'up'}:
                out.setdefault('upperlip', n)
            elif w & {'lower', 'bottom', 'bot', 'down'}:
                out.setdefault('lowerlip', n)
    return out


LID_TOP = {'upper', 'top', 'up', 'upr', 'upp'}
LID_BOTTOM = {'lower', 'bottom', 'bot', 'btm', 'down', 'lwr', 'low'}
PROP_WORDS = {'prop', 'weapon', 'item', 'attach', 'grip', 'gun', 'sword', 'staff'}
# where a loose object (a held prop, a hat, a bag...) can go: the window's Accessories choices -> game bone names
PROP_PLACES = {'hand_left': ('HandLeft',), 'hand_right': ('HandRight',), 'head': ('Head',),
               'chest': ('Spine3', 'Spine2'), 'hips': ('Hips',)}


def eye_bones(sk, head):
    """the model's eyes and lids by name, per side: {'Left': (eye bone, [top lid bones], [bottom lid bones])}"""
    P = sk.pos
    hx = P[head][0] if head in P else 0
    found = {}
    for n in sk.subtree(head)[1:]:
        if n not in P:
            continue
        w = set(words(n))
        side = 'Left' if P[n][0] - hx > 0.003 * sk.height else 'Right' if P[n][0] - hx < -0.003 * sk.height else None
        if side is None:
            continue
        e, tops, bots = found.setdefault(side, [None, [], []])
        if w & {'lid', 'eyelid'}:
            if w & LID_TOP:
                tops.append(n)
            elif w & LID_BOTTOM:
                bots.append(n)
        elif w & {'eye', 'eyeball'} and not w & {'brow', 'eyebrow', 'lash', 'eyelash', 'socket', 'target', 'look'}:
            if e is None or len(sk.ancestors(n)) < len(sk.ancestors(e)):
                found[side][0] = n
    return {s: tuple(v) for s, v in found.items() if v[0] and (v[1] or v[2])}


def extra_bones(sk, body, follows):
    """skinned bones that are no body joint (hair, clothes, props...): what the Accessories choices list"""
    joints = {b for b in body.values() if isinstance(b, str)}
    face_or_helper = {'eye', 'eyeball', 'lid', 'eyelid', 'brow', 'eyebrow', 'lash', 'eyelash', 'lip', 'mouth', 'jaw',
                      'cheek', 'nose', 'tongue', 'teeth', 'tooth', 'twist', 'adj', 'roll', 'helper'}
    out = [n for n in follows if n in sk.skinned and n not in joints and not set(words(n)) & face_or_helper]
    out += [n for n in sk.skinned if set(words(n)) & PROP_WORDS and n not in out and n not in joints]
    return sorted(out, key=lambda n: (len(sk.ancestors(n)), n))


def material_effect(f, subs):
    """the game material the new ones are cloned from: the converter's usual skin shader if this character has it
    (Woody, Buzz), else its 'qcf2' cousin (Jessie), else the shader most of the character's own pieces use"""
    effects = [T.field(f, i, 'Effect', [''])[0] for i in T.pool(f, 'MaterialPool')]
    for e in ('a_1_dmnsmqdrqcf_skin', 'a_1_dmnsmqdrqcf2_skin'):
        if e in effects:
            return e
    used = [effects[s['mat']] for s in subs if s['mat'] is not None and s['mat'] < len(effects)]
    return max(set(used), key=used.count) if used else effects[0]


def automap(fbx, ts3dir, base, log=print, overrides=None, adjust=None):
    """the map's tables for this FBX on that game character, and the roles found (for the app's bone table);
    overrides {role: model bone} replaces what is found (roles: ROLES); adjust {'head_cm': up (+) or down (-)} moves
    the head and the end of the neck from the game's head joint (the window's Adjustments tab)"""
    adjust = adjust or {}
    dy = float(adjust.get('head_cm') or 0) / 100      # game units are metres
    objlib.use_game(ts3dir, base)                      # an OBJ gets this character's skeleton
    sk = Skeleton(fbx)
    moved = {}                                         # an FBX's joints the user moved (an OBJ's: objlib.py)
    if not fbx.lower().endswith('.obj'):
        for n, v in objlib.JOINTS.items():
            if n in sk.pos:
                sk.pos[n] = moved[n] = np.asarray(v, float)
    f3, bones3, subs3, *_ = T.load(os.path.join(ts3dir, base + '.oct'))
    g = game_names(bones3)
    body = find_body(sk, log, overrides)
    P = sk.pos
    tables = dict(PREFIX='kit', KEEP_PIECES=next((v for k, v in KEEP_BY_CHARACTER.items() if base.startswith(k)), []),
                  MATERIAL_EFFECT=material_effect(f3, subs3))
    W = {}                     # model bone -> game bone
    roles = []                 # (role, model bone, game bone) for the report

    def put(role, bone, game):
        if bone is None:
            return
        if game is None:
            log('  the game has no bone for %s (%s): it goes to Head' % (role, bone))
            game = 'Head'
        W[bone] = game
        roles.append((role, bone, game))

    # torso
    hips = g('Hips')
    for n in sk.ancestors(body['root']) + sk.path(body['root'], body['pelvis']):
        W[n] = hips
    roles.append(('hips', body['pelvis'], hips))
    spine = sk.path(body['root'], body['chest'])
    ks = [min(k + 1, 3) for k in range(len(spine))] if len(spine) >= 3 else [2, 3][2 - len(spine):]
    for n, k in zip(spine, ks):
        put('spine', n, g('Spine%d' % k))
    tables['TORSO'] = sk.ancestors(body['root'])[::-1] + sk.path(body['root'], body['pelvis']) + spine

    neck = body['neck'][0] if body['neck'] else None
    for n in body['neck']:
        put('neck', n, g('Neck'))
    head = body['head']
    put('head', head, g('Head'))
    face = face_roles(sk, head)
    face_game = {}
    for role, n in face.items():
        if role.startswith('brow'):
            s = role[4:]
            t = g('Brow' + s, 'MiddleBrow', 'MidddleBrow', 'BrowMiddle') if s == 'Middle' else g('Brow' + s)
        elif role.startswith('lipcorner'):
            t = g('LipCorner' + role[9:])
        else:
            t = g({'jaw': 'Jaw', 'upperlip': 'UpperLip', 'lowerlip': 'LowerLip'}[role])
        if t:
            W[n] = t; face_game[n] = t
            roles.append(('face ' + role, n, t))

    drive = {}
    if neck:
        drive[neck] = (head, 'Neck', 'Head', {'tip_offset': (0.0, dy, 0.0)} if dy else {})
    drive[head] = (None, 'Head', None, {'offset': (0.0, dy, 0.0)} if dy else {})
    for sd, s in SIDES:
        hip, knee, foot, toe = (body[k + s] for k in ('hip', 'knee', 'foot', 'toe'))
        leg = sk.path(body['pelvis'], toe or foot)
        for n in leg[:leg.index(knee)]:
            put('thigh', n, g('Thigh' + s))
        for n in leg[leg.index(knee):leg.index(foot)]:
            put('calf', n, g('Calf' + s))
        put('foot', foot, g('Foot' + s))
        if toe:
            put('toes', toe, g('Toes' + s))
        drive[hip] = (knee, 'Thigh' + s, 'Calf' + s, {})
        drive[knee] = (foot, 'Calf' + s, 'Foot' + s, {'aim_floor': True})
        drive[foot] = (None, 'Foot' + s, None, {'floor': True})

        clav, shoulder, elbow, hand = (body[k + s] for k in ('clavicle', 'shoulder', 'elbow', 'hand'))
        arm = sk.path(body['chest'], hand)
        for n in arm[:arm.index(shoulder)]:
            put('clavicle', n, g('Clavicle' + s, 'Sternum' + s))
        for n in arm[arm.index(shoulder):arm.index(elbow)]:
            put('upper arm', n, g('Bicep' + s))
        for n in arm[arm.index(elbow):-1]:
            put('forearm', n, g('Forearm' + s))
        put('hand', hand, g('Hand' + s))
        aim = None
        for f in FINGERS:
            c = body.get('finger_%s%s' % (f, s))
            if not c:
                continue
            for k, n in enumerate(c):
                j = min(k, 2) + 1
                put('%s %d' % (f.lower(), j), n, g('%s%d%s' % (f, j, s), '%s%s%d' % (f, s, j)))
            if f in ('Middle', 'Index', 'Ring') and aim is None or f == 'Middle':
                aim = (c[0], g('Middle1' + s, 'Middle%s1' % s) if f == 'Middle' else
                       g('%s1%s' % (f, s), '%s%s1' % (f, s)))
        drive[shoulder] = (elbow, 'Bicep' + s, 'Forearm' + s, {})
        drive[elbow] = (hand, 'Forearm' + s, 'Hand' + s, {})
        drive[hand] = (aim[0], 'Hand' + s, aim[1], {}) if aim and aim[1] else (None, 'Hand' + s, None, {})

    # every other bone, parents first: a game accessory bone with its name (Hat, Holster, Hair1, WingLeft1), else the
    # joint it sits on (a helper bone), else its nearest mapped ancestor's game bone
    joints = {n for _, n, _ in roles if n in P and not _.startswith('face')}
    acc = accessories(bones3, set(W.values()))
    follows, notes = {}, {}
    for top in [n for n, p in sk.parent.items() if p is None]:
        for n in sk.subtree(top):
            if n in W:
                continue
            m = match_accessory(n, acc, P, sk.height)
            if m:
                W[n] = m; notes[n] = 'game bone with its name'
                roles.append(('accessory', n, m))
                continue
            if n not in sk.skinned:
                continue
            on = [j for j in joints if np.linalg.norm(P[j] - P[n]) < 0.004 * sk.height]
            if on:
                j = min(on, key=lambda j: (j in sk.ancestors(n), np.linalg.norm(P[j] - P[n])))
                W[n] = W[j]; notes[n] = 'sits on %s' % j
                continue
            up = next((a for a in sk.ancestors(n)[1:] if a in W), None)
            W[n] = W[up] if up else hips
            follows[n] = up
            notes[n] = 'follows %s' % up if up else 'no mapped parent'
    tables['LANDMARKS'] = [(body['pelvis'], hips), (body['shoulderLeft'], 'BicepLeft'),
                           (body['shoulderRight'], 'BicepRight'), (neck, 'Neck') if neck else (head, 'Head'),
                           (body['hipLeft'], 'ThighLeft'), (body['hipRight'], 'ThighRight')]
    sj = [(body['pelvis'], hips), (head, 'Head')] + ([(neck, 'Neck')] if neck else [])
    for _, s in SIDES:
        sj += [(body['shoulder' + s], 'Bicep' + s), (body['elbow' + s], 'Forearm' + s), (body['hand' + s], 'Hand' + s),
               (body['hip' + s], 'Thigh' + s), (body['knee' + s], 'Calf' + s), (body['foot' + s], 'Foot' + s)]
    tables['SCALE_JOINTS'] = [(a, b) for a, b in sj if a in P]
    neck_fit = measure_neck(P, neck, head, tables['SCALE_JOINTS'], bones3, dy)
    torso_fit = measure_torso(P, tables['LANDMARKS'], tables['SCALE_JOINTS'], bones3)
    # proportions from the window (percent): the torso block's size, and how thick each part is (GIRTH; the head's
    # is its size). Lengths stay the game's: the joints must land on the game's joints for its animations.
    ts = [float(x) / 100 for x in adjust.get('torso', (100, 100, 100))]
    if any(abs(x - 1) > 1e-6 for x in ts):
        tables['TORSO_SCALE'] = tuple(round(x, 3) for x in ts)
    girth = {}
    for key, bones in (('head_pct', [head]), ('neck_pct', [neck] if neck else []),
                       ('arms_pct', [body[k + s] for k in ('shoulder', 'elbow') for _, s in SIDES]),
                       ('legs_pct', [body[k + s] for k in ('hip', 'knee') for _, s in SIDES])):
        pct = float(adjust.get(key) or 100)
        if abs(pct - 100) > 1e-6:
            girth.update({b: round(pct / 100, 3) for b in bones})
    if girth:
        tables['GIRTH'] = girth
    if moved:
        tables['JOINT_POS'] = {n: tuple(round(float(x), 5) for x in v) for n, v in moved.items()}

    # loose objects (Accessories): {model bone: hand_left | hand_right | head | chest | hips | out}; the bone and
    # everything below it that is no body joint goes there, or is left out of the model (SKIP_BONES)
    extras = extra_bones(sk, body, follows)
    joint_bones = {b for b in body.values() if isinstance(b, str)}
    skip = []
    for n, place in (adjust.get('props') or {}).items():
        if n not in sk.parent:
            log('  accessories: the model has no bone %s' % n)
            continue
        part = [b for b in sk.subtree(n) if b not in joint_bones]
        if place == 'out':
            skip += [b for b in part if b in sk.skinned]
            notes.update({b: 'left out (Accessories)' for b in part})
        elif place in PROP_PLACES:
            t = g(*PROP_PLACES[place])
            for b in part:
                W[b] = t
                notes[b] = 'goes with %s (Accessories)' % t
        else:
            log('  accessories: unknown place %r for %s' % (place, n))
    if skip:
        tables['SKIP_BONES'] = skip
    # clothes narrower / wider (percent, across: x and z about the hips; the height stays)
    garments = {m: round(float(p) / 100, 3) for m, p in (adjust.get('garments') or {}).items()
                if abs(float(p) - 100) > 1e-6}
    if garments:
        tables['MATERIAL_SCALE'] = {m: (k, 1.0, k) for m, k in garments.items()}

    # weights by hand: {model bone: game bone | {game bone: share}}
    gnames = {b['name'] for b in bones3}
    for n, t in (adjust.get('weights') or {}).items():
        targets = t if isinstance(t, dict) else {t: 1.0}
        if n not in sk.parent or not targets or not all(x in gnames for x in targets):
            log('  weights: %s -> %s skipped (unknown bone)' % (n, t))
            continue
        tot = sum(float(v) for v in targets.values()) or 1.0
        W[n] = {x: round(float(v) / tot, 3) for x, v in targets.items()} if len(targets) > 1 else next(iter(targets))
        notes[n] = 'set by hand'
    if adjust.get('smooth'):
        tables['WEIGHT_SMOOTH'] = int(adjust['smooth'])

    # eyes: open shut lids by turning the lid bones' vertices about the eye (EYE_MODE 'rotate')
    eyes = eye_bones(sk, head)
    eo = adjust.get('eyes_open')
    if eo and eyes:
        tables['EYES'] = [eyes[s] for s in ('Left', 'Right') if s in eyes]
        tables['EYE_MODE'] = 'rotate'
        tables['EYE_OPEN_TOP'] = float(eo.get('top', 0))
        tables['EYE_OPEN_BOTTOM'] = float(eo.get('bottom', 0))
    elif eo:
        log('  eyes: no eye and lid bones found by name: they cannot be opened here')

    # the head placed by the face (its jaw, lips and brows on the game's) instead of by the head joint
    tables['FACE_ALIGN'] = []
    if adjust.get('head_by_face'):
        if len(face_game) >= 2:
            tables['FACE_ALIGN'] = sorted(face_game.items())
            if neck:
                drive[neck][3]['aim_face'] = True
            drive[head][3]['face'] = True
        else:
            log('  head by the face: fewer than 2 face bones found (jaw, lips, brows): the head joint is used')
    tables['DRIVE'] = drive
    tables['WEIGHTS'] = {n: W[n] for n in sorted(W, key=lambda n: (n not in sk.skinned, n)) if n in sk.skinned or n in drive}
    tables['FACE_BONES'] = set(face_game.values())
    tables['FACE'] = bool(adjust.get('face')) and bool(face_game)

    # checks the user should hear about
    for _, s in SIDES:
        toe, foot = body['toe' + s], body['foot' + s]
        if toe and P[toe][2] < P[foot][2]:
            log('  warning: the %s toes point backwards: the model may face -Z' % s.lower())
    if P[body['handLeft']][0] < 0:
        log('  warning: the left hand is at -x: the model may be facing backwards')
    return tables, dict(body=body, roles=roles, follows=follows, notes=notes, skeleton=sk, neck=neck_fit,
                        torso=torso_fit, extras=extras, eyes=eyes, face=face, moved=moved)


def model_scale(P, scale_joints, piv):
    """the converter's overall scale for the model: least squares over SCALE_JOINTS, as in convert.fit"""
    pairs = [(P[a], piv[b]) for a, b in scale_joints if b in piv]
    return sum(float(a @ b) for a, b in pairs) / sum(float(a @ a) for a, _ in pairs)


def measure_torso(P, landmarks, scale_joints, bones3):
    """how much the converter widens (x) and lengthens (y) the torso block on its own to reach the game's shoulders
    and hips (percent; as in convert.fit, which keeps it within 80..125)"""
    piv = {b['name']: np.array(b['pivot'], float) for b in bones3}
    lm = [(a, b) for a, b in landmarks if a in P and b in piv]
    if len(lm) < 3:
        return None
    s = model_scale(P, scale_joints, piv)
    L5 = np.array([P[a] * s for a, _ in lm]); L3 = np.array([piv[b] for _, b in lm])
    out = {}
    for ax, key in ((0, 'width_pct'), (1, 'height_pct')):
        if np.ptp(L5[:, ax]) > 1e-3:
            out[key] = round(float(np.clip(np.polyfit(L5[:, ax], L3[:, ax], 1)[0], 0.8, 1.25)) * 100)
    return out


def measure_neck(P, neck, head, scale_joints, bones3, dy):
    """the model's neck (neck joint to head joint) at the size the converter gives the model (its least-squares
    scale over SCALE_JOINTS, as in convert.fit), next to the game character's: how much the converter stretches it,
    and the head offset (cm) that would leave it at its own length"""
    piv = {b['name']: np.array(b['pivot'], float) for b in bones3}
    if not neck or head not in P or 'Neck' not in piv or 'Head' not in piv:
        return None
    s = model_scale(P, scale_joints, piv)
    model = float(np.linalg.norm(P[head] - P[neck])) * s
    game = float(np.linalg.norm(piv['Head'] - piv['Neck']))
    return dict(model_cm=round(model * 100, 1), game_cm=round(game * 100, 1),
                stretch=round((game + dy) / model, 2) if model else None,
                natural_cm=round((model - game) * 100, 1))


# ------------------------------------------------------------------------------------------- writing
def _r(v):
    return repr(v)


def write_map(tables, info, path, fbx, base):
    sk = info['skeleton']
    L = ['"""%s -> Toy Story 3 %s.' % (os.path.basename(fbx), base), '',
         'Made by %s (automatic bone mapping). It is a normal map file: edit it by hand to fine-tune' % CREDIT,
         'the conversion, with every option the converter has (see the kit\'s guide, "advanced").', '"""', '',
         'PREFIX = %r' % tables['PREFIX'],
         '# game pieces that stay (by name)',
         'KEEP_PIECES = %r' % tables['KEEP_PIECES'],
         '# the game material the new ones are cloned from (it must exist in this character\'s archive)',
         'MATERIAL_EFFECT = %r' % tables['MATERIAL_EFFECT'], '',
         '# moved as one block, scaled per axis so the LANDMARKS line up (model bone -> game bone)',
         'TORSO = %r' % tables['TORSO'], 'LANDMARKS = [']
    L += ['    %r,' % (p,) for p in tables['LANDMARKS']] + [']', '# joints that set the overall size', 'SCALE_JOINTS = [']
    L += ['    %r,' % (p,) for p in tables['SCALE_JOINTS']] + [']']
    L += ['# face features -> game face bones, to place the head by the face instead of by the head pivot',
          'FACE_ALIGN = %r' % tables['FACE_ALIGN'], '',
          '# model bone: (model bone it aims at, game bone, game bone it aims at, options)', 'DRIVE = {']
    L += ['    %r: %r,' % (k, v) for k, v in tables['DRIVE'].items()] + ['}', '']
    if 'TORSO_SCALE' in tables:
        L += ['# the torso block, wider / longer / deeper than fitted (x, y, z)',
              'TORSO_SCALE = %r' % (tables['TORSO_SCALE'],), '']
    if 'GIRTH' in tables:
        L += ['# thicker / thinner parts across their length (model bone: factor; the head\'s is its size)',
              'GIRTH = %r' % tables['GIRTH'], '']
    if 'JOINT_POS' in tables:
        L += ["# joints moved by hand (the file's units, Y up, facing +Z)", 'JOINT_POS = {']
        L += ['    %r: %r,' % kv for kv in tables['JOINT_POS'].items()] + ['}', '']
    if 'SKIP_BONES' in tables:
        L += ['# left out of the model: triangles hanging mostly on these bones',
              'SKIP_BONES = %r' % tables['SKIP_BONES'], '']
    if 'MATERIAL_SCALE' in tables:
        L += ['# clothes narrower / wider (material: (x, y, z) about the hips)',
              'MATERIAL_SCALE = %r' % tables['MATERIAL_SCALE'], '']
    if 'WEIGHT_SMOOTH' in tables:
        L += ["# passes averaging each point's weights with its neighbours'",
              'WEIGHT_SMOOTH = %r' % tables['WEIGHT_SMOOTH'], '']
    if 'EYES' in tables:
        L += ['# shut lids opened: (eye, top lid bones, bottom lid bones), turned by these angles (degrees)',
              'EYES = %r' % tables['EYES'], 'EYE_MODE = %r' % tables['EYE_MODE'],
              'EYE_OPEN_TOP = %r' % tables['EYE_OPEN_TOP'], 'EYE_OPEN_BOTTOM = %r' % tables['EYE_OPEN_BOTTOM'], '']
    L += ['# model bone -> game bone its vertices go to', 'WEIGHTS = {']
    for n, t in tables['WEIGHTS'].items():
        note = '  # ' + info['notes'][n] if n in info['notes'] else ''
        L.append('    %r: %r,%s' % (n, t, note))
    L += ['}']
    if 'TEXTURES' in tables:
        L += ['',
              '# texture sets: d diffuse, n normal, orm (occlusion, roughness, metal), spec (a value 0..1 or an image),',
              '# size / nsize / ssize in pixels (powers of two, at most 1024 for the game)', 'TEXTURES = {']
        L += ['    %r: %r,' % kv for kv in tables['TEXTURES'].items()] + ['}',
              '# FBX material -> texture set, or (r, g, b) for a solid colour', 'MATERIALS = {']
        for m, v in tables['MATERIALS'].items():
            why = tables['_tex_notes'].get(m, '')
            L.append('    %r: %r,%s' % (m, v, '  # CHECK: no image matched, guessed' if why == 'check' else
                                         '  # ' + why if why else ''))
        L += ['}', '# FBX materials left out', 'SKIP_MATERIALS = %r' % tables['SKIP_MATERIALS']]
    L += ['',
          '# face bones: they move with Head while FACE is False (True moves them with these game bones)',
          'FACE_BONES = %r' % (tables['FACE_BONES'] or 'set()'), 'FACE = %r' % tables['FACE'], '']
    text = '\n'.join(L).replace("FACE_BONES = 'set()'", 'FACE_BONES = set()')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def report(info, log=print):
    b = info['body']
    log('torso: %s (hips %s, chest %s)' % (b['root'], b['pelvis'], b['chest']))
    log('neck: %s   head: %s' % (', '.join(b['neck']) or '-', b['head']))
    nf = info.get('neck')
    if nf:
        log('  neck length: model %.1f cm, game %.1f cm: stretched x%.2f (the converter allows 0.80..1.25); '
            'head %+.1f cm keeps its own length' % (nf['model_cm'], nf['game_cm'], nf['stretch'], nf['natural_cm']))
    tf = info.get('torso')
    if tf:
        log('  torso fit: %s%% wide, %s%% tall to reach the game\'s shoulders and hips'
            % (tf.get('width_pct', 100), tf.get('height_pct', 100)))
    for _, s in SIDES:
        log('%-5s leg: %s > %s > %s > %s' % (s, b['hip' + s], b['knee' + s], b['foot' + s], b['toe' + s] or '-'))
        log('%-5s arm: %s > %s > %s > %s' % (s, b['clavicle' + s] or '-', b['shoulder' + s], b['elbow' + s], b['hand' + s]))
        log('      fingers: %s' % ', '.join('%s %s' % (f, b['finger_%s%s' % (f, s)][0]) for f in FINGERS
                                        if 'finger_%s%s' % (f, s) in b))
    face = [r for r in info['roles'] if r[0].startswith('face')]
    if face:
        log('face (on Head while FACE is False): %s' % ', '.join('%s=%s' % (r[0][5:], r[1]) for r in face))
    acc = [r for r in info['roles'] if r[0] == 'accessory']
    if acc:
        log('accessories: %s' % ', '.join('%s=%s' % (r[1], r[2]) for r in acc))
    log('%d other bones follow their parents' % len(info['follows']))


def add_textures(tables, fbx, texdir, log=print, overrides=None):
    """TEXTURES, MATERIALS and SKIP_MATERIALS from the FBX's materials and the images in texdir (autotex.py)"""
    from autotex import autotex
    sets, materials, skip, notes, tris = autotex(fbx, texdir, log, overrides)
    tables.update(TEXTURES=sets, MATERIALS=materials, SKIP_MATERIALS=skip, _tex_notes=notes, _tex_tris=tris)
    return [m for m, why in notes.items() if why == 'check']


if __name__ == '__main__':
    if len(sys.argv) not in (5, 6):
        sys.exit(__doc__)
    fbx, ts3dir, base, out = sys.argv[1:5]
    tables, info = automap(fbx, ts3dir, base)
    report(info)
    if len(sys.argv) == 6:
        check = add_textures(tables, fbx, sys.argv[5])
        if check:
            print('CHECK these materials, no image matched them: %s' % ', '.join(map(repr, check)))
    write_map(tables, info, out, fbx, base)
    print('wrote', out)
