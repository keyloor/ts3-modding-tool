"""Live 3D preview: a converted character (or the game's own) drawn on the GPU and shown in a tkinter label.

  Character(dir, base)   reads <base>.oct + _0.vbuf + _0.ibuf: every piece's vertices with their game bones and
                         weights, the diffuse map of each material, the game skeleton (pivots, parents)
  Character.pose(...)    skins it on the CPU: turns bones about their pivots down the skeleton (arms down...), and
                         per-bone shape changes that don't pass to the children (the live Adjustments)
  Character.K            one number per vertex the view can colour by (View.colour_mode): bone_weight() for the
                         weights of some game bones, strain() for how far the conversion stretched each part
  View(label)            moderngl offscreen: draws into a framebuffer, reads it back, shows it as the label's image.
                         Left drag turns, right drag moves, the wheel zooms, a double click frames everything.

The bind pose of a game character is its model space (Y up, facing +Z, metres, its left at +x), so a pose is just
each bone's transform about its pivot, chained from parent to child. Without OpenGL 3.3 (some virtual machines, old
graphics cards) available() is False and the window keeps the still images.
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: F401  (puts the shared tools on sys.path)
import ts3model as T
import render as RD

_available = None


def available():
    global _available
    if _available is None:
        try:
            import moderngl
            moderngl.create_context(standalone=True).release()
            _available = True
        except Exception:
            _available = False
    return _available


# ------------------------------------------------------------------------------------------- the character
def rot(axis, deg):
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def about(M3, p):
    """4x4 (column vectors) doing M3 about point p"""
    m = np.eye(4); m[:3, :3] = M3; m[:3, 3] = p - M3 @ p
    return m


class Character:
    def __init__(self, d, base):
        f, bones, subs, remaps, ist, vst = T.load(os.path.join(d, base + '.oct'))
        vb = open(os.path.join(d, base + '_0.vbuf'), 'rb').read()
        ib = np.frombuffer(open(os.path.join(d, base + '_0.ibuf'), 'rb').read(), '<u2')
        self.names = [b['name'] for b in bones]
        self.index = {n: k for k, n in enumerate(self.names)}
        self.pivots = np.array([b['pivot'] for b in bones], float)
        bynode = {b['node']: k for k, b in enumerate(bones)}
        self.parent = np.array([bynode.get(b['parent'], -1) for b in bones])     # pre-order: parents come first
        byid = {b['id']: k for k, b in enumerate(bones)}
        P, N, UV, BI, BW, groups = [], [], [], [], [], {}
        n0 = 0
        for s in subs:
            sa, sb = vst[s['vs'][0]], vst[s['vs'][1]]
            v0 = np.frombuffer(vb, T.S0, sa['len'], sa['off'])
            if sb['width'] == 24:
                n = np.frombuffer(vb, T.S1, sb['len'], sb['off'])['n'][:, :3].astype(np.float32)
            else:                                   # as render.load_mesh: other widths keep the normal at 0 or 4
                raw = np.frombuffer(vb, 'u1', sb['len'] * sb['width'], sb['off']).reshape(sb['len'], sb['width'])
                noff = 0 if sb['width'] == 8 else 4
                n = raw[:, noff:noff + 8].copy().view('<f2')[:, :3].astype(np.float32)
            remap = remaps[s['sc']] if s['sc'] is not None else [0]
            look = np.array([byid.get(r, 0) for r in remap] + [0])
            st = ist[s['ist']]
            tri = ib[st['off'] // 2: st['off'] // 2 + st['len']].astype(np.int64)
            P.append(v0['p'].astype(np.float32)); N.append(n); UV.append(v0['uv'].astype(np.float32))
            BI.append(look[np.minimum(v0['bi'], len(look) - 1)]); BW.append(v0['bw'].astype(np.float32) / 255)
            groups.setdefault(s['mat'], []).append(tri + n0)
            n0 += len(v0)
        self.P0, self.N0, self.UV = np.concatenate(P), np.concatenate(N), np.concatenate(UV)
        self.BI, self.BW = np.concatenate(BI), np.concatenate(BW)
        self.groups = {m: np.concatenate(t).astype(np.uint32) for m, t in groups.items()}
        self.textures = {m: np.clip(a, 0, 255).astype(np.uint8) for m, a in RD.oct_textures(f).items()}
        self.P, self.N = self.P0, self.N0
        self.posed = self.pivots.copy()
        self.K = None

    def child_of(self, name):
        """the first child bone of name (its segment's end), or None"""
        k = self.index.get(name)
        kids = [j for j in range(len(self.names)) if self.parent[j] == k] if k is not None else []
        return kids[0] if kids else None

    def pose(self, turns=None, shapes=None):
        """turns {bone: (axis, degrees), a 3x3 about its pivot, or a 4x4} pass down to the children; shapes
        {bone: 4x4} only change the vertices on that bone (applied before its turn). Sets self.P, self.N and
        self.posed (bone pivots)."""
        turns, shapes = turns or {}, shapes or {}
        n = len(self.names)
        G = np.tile(np.eye(4), (n, 1, 1))
        for k in range(n):                        # parents before children (pre-order)
            t = turns.get(self.names[k])
            if t is None:
                local = np.eye(4)
            elif isinstance(t, tuple):
                local = about(rot(*t), self.pivots[k])
            else:
                local = t if np.shape(t) == (4, 4) else about(t, self.pivots[k])
            G[k] = (G[self.parent[k]] if self.parent[k] >= 0 else np.eye(4)) @ local
        self.posed = (G[:, :3, :3] @ self.pivots[:, :, None])[:, :, 0] + G[:, :3, 3]
        M = G.copy()
        for name, D in shapes.items():
            if name in self.index:
                M[self.index[name]] = M[self.index[name]] @ D
        Mv = M[self.BI]                                            # (vertices, 4 bones, 4, 4)
        W = self.BW / np.maximum(self.BW.sum(1, keepdims=True), 1e-6)
        ph = np.c_[self.P0, np.ones(len(self.P0), np.float32)]
        self.P = np.einsum('vk,vkij,vj->vi', W, Mv, ph)[:, :3].astype(np.float32)
        Rn = np.einsum('vk,vkij->vij', W, Mv[:, :, :3, :3])
        nn = np.einsum('vij,vj->vi', Rn, self.N0)
        self.N = (nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-6)).astype(np.float32)

    def bounds(self):
        return self.P.min(0), self.P.max(0)

    def bone_weight(self, names):
        """per vertex, how much these game bones move it (0..1)"""
        ids = [self.index[n] for n in names if n in self.index]
        W = self.BW / np.maximum(self.BW.sum(1, keepdims=True), 1e-6)
        return (W * np.isin(self.BI, ids)).sum(1).astype(np.float32)

    def strain(self, stretch):
        """per vertex, 0..1: how far the conversion stretched or squeezed the parts that move it; stretch is
        {game bone: factor} (1 = its own length; the converter's limits, 0.8 and 1.25, give 1)"""
        sev = np.zeros(len(self.names) + 1, np.float32)
        for n, k in stretch.items():
            if n in self.index and k > 0:
                sev[self.index[n]] = min(abs(math.log(k)) / math.log(1.25), 1.0)
        W = self.BW / np.maximum(self.BW.sum(1, keepdims=True), 1e-6)
        return (W * sev[self.BI]).sum(1).astype(np.float32)


class SourceModel:
    """an OBJ as the tool sees it before converting (turned up, on the floor) with its automatic skeleton, for the
    joints mode where the user drags the joints. Has what View draws: P, N, UV, groups, textures, posed, parent."""

    def __init__(self, path, game, joints, texdir):
        import objlib
        sc = objlib.ObjScene(path, game, joints)
        m = sc.mesh
        nd, ns = m['normals']; ud, us = m['uv']
        self.P0 = sc.P[m['cp']].astype(np.float32)                 # one vertex per corner
        self.N0 = nd.reshape(-1, 3)[ns].astype(np.float32)
        self.UV = ud.reshape(-1, 2)[us].astype(np.float32)
        self.UV[:, 1] = 1 - self.UV[:, 1]                          # OBJ v goes up; the images' rows go down
        self.groups = {int(k): m['tri'][m['mat'] == k].astype(np.uint32).ravel() for k in np.unique(m['mat'])}
        self.textures = {}
        for k in self.groups:
            name = sc.matnames[k] if k < len(sc.matnames) else ''
            fn = sc.mtl.get(name, {}).get('d')
            for d in (texdir, os.path.dirname(path)):
                if fn and d and os.path.isfile(os.path.join(d, fn)):
                    with Image.open(os.path.join(d, fn)) as im:
                        im = im.convert('RGB'); im.thumbnail((1024, 1024))
                        self.textures[k] = np.asarray(im)
                    break
        self.P, self.N = self.P0, self.N0
        self.K = None
        self.unit = 1.0
        self.names = list(sc.skel)
        self.index = {n: i for i, n in enumerate(self.names)}
        self.posed = np.array([sc.skel[n][1] for n in self.names], float)
        self.parent = np.array([self.index.get(sc.skel[n][0], -1) for n in self.names])

    def bounds(self):
        return self.P.min(0), self.P.max(0)


class SourceFBX:
    """an FBX as the converter sees it before converting (Y up, facing +Z, the file's units) with its body joints (the
    Bones tab's roles), for the joints mode. The joints are named by role ('elbowLeft'...) so the view can mirror
    them; keys turns a role back into the model bone that kit_project.json 'joints' names."""

    PARENT = {'chest': 'pelvis', 'neck': 'chest', 'head': 'neck', 'clavicle': 'chest', 'shoulder': 'clavicle',
              'elbow': 'shoulder', 'hand': 'elbow', 'hip': 'pelvis', 'knee': 'hip', 'foot': 'knee', 'toe': 'foot'}

    def __init__(self, path, body, joints, texdir=None, materials=None):
        import fbxlib
        import convert as CV
        scene = fbxlib.Scene(path)
        A = scene.to_yup()

        class Keep:                                           # every skinned mesh, nothing left out
            SKIP_MATERIALS = []
        m = CV.merge_meshes(scene, Keep, lambda *a: None)
        P = (m['pos'] @ A)
        h = float(np.ptp(P[:, 1])) or 1.0
        self.unit = 1.8 / h if not 0.5 < h < 5 else 1.0      # shown at about a person's size (files in cm...)
        P = P * self.unit
        nd, ns = m['normals']; ud, us = m['uv']
        self.P0 = P[m['cp']].astype(np.float32)                 # one vertex per corner
        n = nd.reshape(-1, 3)[ns] @ A
        self.N0 = (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)).astype(np.float32)
        self.UV = ud.reshape(-1, 2)[us].astype(np.float32)
        self.UV[:, 1] = 1 - self.UV[:, 1]
        names = sorted(set(m['mat']))
        self.groups = {k: m['tri'][m['mat'] == mat].astype(np.uint32).ravel() for k, mat in enumerate(names)}
        self.textures = {}
        if texdir and os.path.isdir(texdir):
            try:
                from autotex import autotex
                sets, mats, *_ = autotex(path, texdir, lambda *a: None, materials)
                for k, mat in enumerate(names):
                    d = sets.get(mats.get(mat), {}).get('d') if isinstance(mats.get(mat), str) else None
                    if d and os.path.isfile(os.path.join(texdir, d)):
                        with Image.open(os.path.join(texdir, d)) as im:
                            im = im.convert('RGB'); im.thumbnail((1024, 1024))
                            self.textures[k] = np.asarray(im)
            except Exception:
                pass                                          # grey is fine for moving joints
        self.P, self.N, self.K = self.P0, self.N0, None
        pos = {}
        for mesh in scene.meshes():
            for c in mesh['skin'] or []:
                if len(c['idx']) or c['bone'] not in pos:
                    pos[c['bone']] = c['xlink'][3, :3] @ A
        roles = []
        for role, bone in body.items():
            bone = bone[0] if isinstance(bone, list) and bone else bone
            base = role[:-4] if role.endswith('Left') else role[:-5] if role.endswith('Right') else role
            if isinstance(bone, str) and bone in pos and (base in self.PARENT or base == 'pelvis'):
                roles.append((role, bone))
        self.keys = dict(roles)
        self.names = [r for r, _ in roles]
        self.index = {n: i for i, n in enumerate(self.names)}
        self.posed = np.array([np.asarray((joints or {}).get(b, pos[b]), float) for _, b in roles]) * self.unit

        def parent(role):
            side = 'Left' if role.endswith('Left') else 'Right' if role.endswith('Right') else ''
            base = role[:-len(side)] if side else role
            up = self.PARENT.get(base)
            while up:
                cand = up + side if up in ('clavicle', 'shoulder', 'elbow', 'hand', 'hip', 'knee', 'foot') else up
                if cand in self.index:
                    return self.index[cand]
                up = self.PARENT.get(up)
            return -1
        self.parent = np.array([parent(r) for r in self.names])
        self.mirror_x = float(self.posed[self.index['pelvis'], 0]) if 'pelvis' in self.index else 0.0

    def bounds(self):
        return self.P.min(0), self.P.max(0)


ARMS_DOWN = {'BicepLeft': ((0, 0, 1), -70), 'BicepRight': ((0, 0, 1), 70)}   # about z: the left arm is at +x
TORSO_BONES = ('Hips', 'Spine1', 'Spine2', 'Spine3')
LANDMARK_BONES = ('Hips', 'BicepLeft', 'BicepRight', 'Neck', 'ThighLeft', 'ThighRight')
GIRTH_BONES = {'neck_pct': ('Neck',), 'arms_pct': ('BicepLeft', 'BicepRight', 'ForearmLeft', 'ForearmRight'),
               'legs_pct': ('ThighLeft', 'ThighRight', 'CalfLeft', 'CalfRight')}


def live_adjust(ch, applied, now):
    """turns and shapes that show, on an already converted character, roughly what the Adjustments values `now`
    would give next to the `applied` ones it was converted with (both as in kit_project.json's 'adjust'): the head
    moved and resized, the neck stretched to it, thicker / thinner limbs, the torso block scaled. 'Apply and convert'
    gives the exact result."""
    turns, shapes = {}, {}
    P = ch.pivots
    k = ch.index

    def val(d, key, default):
        return float(d.get(key, default))

    def seg(name):
        c = ch.child_of(name)
        return (P[k[name]], P[c]) if name in k and c is not None else None

    def across(name, g, along=1.0):
        s = seg(name)
        if s is None:
            return None
        u = s[1] - s[0]; L = np.linalg.norm(u); u = u / max(L, 1e-9)
        return about(np.eye(3) + (along - 1) * np.outer(u, u) + (g - 1) * (np.eye(3) - np.outer(u, u)), s[0])

    dy = (val(now, 'head_cm', 0) - val(applied, 'head_cm', 0)) / 100
    hs = val(now, 'head_pct', 100) / val(applied, 'head_pct', 100)
    if 'Head' in k and (abs(dy) > 1e-6 or abs(hs - 1) > 1e-6):
        p = P[k['Head']]
        m = np.eye(4); m[:3, :3] *= hs; m[:3, 3] = p - hs * p + (0, dy, 0)
        turns['Head'] = m
    for key, bones in GIRTH_BONES.items():
        g = val(now, key, 100) / val(applied, key, 100)
        for b in bones:
            along = 1.0
            if b == 'Neck' and seg('Neck') is not None and abs(dy) > 1e-6:
                L = np.linalg.norm(seg('Neck')[1] - seg('Neck')[0])
                along = max(L + dy, 0.2 * L) / L
            if abs(g - 1) > 1e-6 or abs(along - 1) > 1e-6:
                D = across(b, g, along)
                if D is not None:
                    shapes[b] = D
    for key, bones in (('shoulders_cm', ('BicepLeft', 'BicepRight')), ('hips_cm', ('ThighLeft', 'ThighRight'))):
        d = (val(now, key, 0) - val(applied, key, 0)) / 100
        for b in bones:
            if abs(d) > 1e-6 and b in k:
                if b.startswith('Bicep') and ch.parent[k[b]] >= 0:    # the arms down pose turns the biceps: move
                    b = ch.names[ch.parent[k[b]]]                    # the clavicle under it instead
                m = np.eye(4); m[0, 3] = d if b.endswith('Left') else -d     # the left side is at +x
                turns[b] = m
    t_now, t_app = now.get('torso', [100] * 3), applied.get('torso', [100] * 3)
    r = np.array([float(a) / float(b) for a, b in zip(t_now, t_app)])
    if np.abs(r - 1).max() > 1e-6:
        c = np.mean([P[k[n]] for n in LANDMARK_BONES if n in k], 0)
        D = np.eye(4); D[:3, :3] = np.diag(r); D[:3, 3] = c - r * c
        for b in TORSO_BONES:
            if b in k:
                shapes[b] = D
    return turns, shapes


# ------------------------------------------------------------------------------------------- drawing
VERT = """
#version 330
uniform mat4 mvp;
uniform vec3 shift;
in vec3 in_pos; in vec3 in_nrm; in vec2 in_uv; in float in_k;
out vec3 v_nrm; out vec2 v_uv; out float v_k;
void main() { gl_Position = mvp * vec4(in_pos + shift, 1.0); v_nrm = in_nrm; v_uv = in_uv; v_k = in_k; }
"""
FRAG = """
#version 330
uniform sampler2D tex;
uniform bool use_tex;
uniform vec3 colour;
uniform int mode;
in vec3 v_nrm; in vec2 v_uv; in float v_k;
out vec4 f_colour;
void main() {
    vec3 n = normalize(v_nrm);
    float light = 0.35 + 0.55 * max(dot(n, normalize(vec3(0.4, 0.6, 0.8))), 0.0)
                       + 0.15 * max(dot(n, normalize(vec3(-0.6, 0.2, -0.5))), 0.0);
    vec3 c = use_tex ? texture(tex, v_uv).rgb : colour;
    if (mode == 1) c = mix(c, vec3(0.95, 0.08, 0.05), clamp(v_k, 0.0, 1.0) * 0.85);
    if (mode == 2) {                               // weights: dark blue (none) .. green .. yellow .. red (all)
        float k = clamp(v_k, 0.0, 1.0);
        c = k < 0.004 ? vec3(0.16, 0.2, 0.42) : k < 0.5 ? mix(vec3(0.1, 0.45, 0.9), vec3(0.2, 0.85, 0.3), k * 2.0)
                                              : mix(vec3(0.95, 0.85, 0.1), vec3(0.95, 0.12, 0.05), k * 2.0 - 1.0);
    }
    f_colour = vec4(c * light, 1.0);
}
"""
LINE_VERT = """
#version 330
uniform mat4 mvp;
uniform float psize;
in vec3 in_pos;
void main() { gl_Position = mvp * vec4(in_pos, 1.0); gl_PointSize = psize; }
"""
LINE_FRAG = """
#version 330
uniform vec3 colour;
out vec4 f_colour;
void main() { f_colour = vec4(colour, 1.0); }
"""


def perspective(fov, aspect, near, far):
    f = 1 / math.tan(math.radians(fov) / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]], 'f4')


def look_at(eye, target, up=(0, 1, 0)):
    z = eye - target; z /= np.linalg.norm(z)
    x = np.cross(up, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.eye(4, dtype='f4'); m[0, :3], m[1, :3], m[2, :3] = x, y, z
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class _Mesh:
    """one character on the GPU: a vertex buffer it can rewrite (posing) and one draw per material"""

    def __init__(self, ctx, prog, ch):
        self.ctx, self.prog, self.ch = ctx, prog, ch
        self.vbo = ctx.buffer(reserve=len(ch.P0) * 36)
        self.update()
        self.draws = []
        for m, idx in ch.groups.items():
            ibo = ctx.buffer(idx.tobytes())
            vao = ctx.vertex_array(prog, [(self.vbo, '3f 3f 2f 1f', 'in_pos', 'in_nrm', 'in_uv', 'in_k')], ibo)
            tex = None
            if m in ch.textures:
                img = ch.textures[m]
                tex = ctx.texture((img.shape[1], img.shape[0]), 3, np.ascontiguousarray(img).tobytes())
                tex.build_mipmaps()
            self.draws.append((vao, tex, ibo))

    def update(self):
        k = self.ch.K if getattr(self.ch, 'K', None) is not None else np.zeros(len(self.ch.P), np.float32)
        self.vbo.write(np.ascontiguousarray(np.c_[self.ch.P, self.ch.N, self.ch.UV, k].astype('f4')).tobytes())

    def draw(self, shift=(0, 0, 0), colour=None, mode=0):
        self.prog['shift'].value = tuple(shift)
        self.prog['mode'].value = mode
        for vao, tex, _ in self.draws:
            plain = colour is not None or tex is None or mode == 2
            self.prog['use_tex'].value = not plain
            self.prog['colour'].value = colour or (0.78, 0.78, 0.78)
            if tex is not None and not plain:
                tex.use(0)
            vao.render()

    def release(self):
        for vao, tex, ibo in self.draws:
            vao.release(); ibo.release()
            if tex is not None:
                tex.release()
        self.vbo.release()


class View:
    """the 3D preview in a tkinter label: the character, optionally the game's original beside it and the skeleton"""

    def __init__(self, label, background=(0.92, 0.92, 0.92)):
        import moderngl
        self.mgl = moderngl
        self.label, self.bg = label, background
        self.ctx = moderngl.create_context(standalone=True)
        self.prog = self.ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
        self.lprog = self.ctx.program(vertex_shader=LINE_VERT, fragment_shader=LINE_FRAG)
        self.mesh = self.ghost = None
        self.show_ghost, self.show_bones = False, True
        self.colour_mode = 0           # 1: the character's K as red over it (stretch); 2: K as heat (weights)
        self.yaw, self.pitch, self.dist, self.target = 20.0, 8.0, 3.0, np.array([0, 0.9, 0], 'f4')
        self.fbo, self.size, self.photo, self._pending = None, (0, 0), None, False
        self.on_joints = None          # joints mode: called with {bone: position} when a dragged joint is let go
        self.mirror = True             # joints mode: a Left joint moves its Right twin too (mirrored in x)
        self.selected, self._drag, self._moved, self._M = None, None, {}, None
        label.bind('<ButtonPress-1>', self._press); label.bind('<ButtonPress-3>', self._press)
        label.bind('<B1-Motion>', self._orbit); label.bind('<B3-Motion>', self._pan)
        label.bind('<ButtonRelease-1>', self._release)
        label.bind('<MouseWheel>', self._zoom); label.bind('<Double-Button-1>', lambda e: self.frame())
        label.bind('<Configure>', lambda e: self.redraw())

    # -------------------------------------------------------------- content
    def set_character(self, ch, ghost=None):
        for m in (self.mesh, self.ghost):
            if m is not None:
                m.release()
        self.mesh = _Mesh(self.ctx, self.prog, ch) if ch is not None else None
        self.ghost = _Mesh(self.ctx, self.prog, ghost) if ghost is not None else None
        if ch is None:
            self.photo = None
            self.label.config(image='')                  # the label's own text shows again
        self.frame()

    def update(self):
        """the characters' vertices changed (a new pose or a live adjustment)"""
        for m in (self.mesh, self.ghost):
            if m is not None:
                m.update()
        self.redraw()

    def frame(self):
        if self.mesh is None:
            return self.redraw()
        lo, hi = self.mesh.ch.bounds()
        self.target = ((lo + hi) / 2).astype('f4')
        self.dist = float(max(hi - lo)) * 1.6 + 0.2
        self.redraw()

    # -------------------------------------------------------------- mouse
    def _press(self, e):
        self._last = (e.x, e.y)
        self._drag = None
        if self.on_joints is not None and self.mesh is not None and self._M is not None and e.num == 1:
            pts = self._screen(self.mesh.ch.posed)
            d = np.hypot(pts[:, 0] - e.x, pts[:, 1] - e.y)
            if d.min() < 14:                                       # a click on a joint drags it
                self._drag = self.selected = int(np.argmin(d))
                self.redraw()

    def _screen(self, pts):
        w, h = self.size
        c = np.c_[pts, np.ones(len(pts))] @ self._M.T
        n = c[:, :3] / c[:, 3:4]
        return np.c_[(n[:, 0] + 1) / 2 * w, (1 - n[:, 1]) / 2 * h, n[:, 2]]

    def _drag_joint(self, e):
        ch = self.mesh.ch
        k = self._drag
        w, h = self.size
        z = self._screen(ch.posed[k:k + 1])[0, 2]                  # keep its depth: move it across the screen
        p = np.linalg.inv(self._M) @ np.array([e.x / w * 2 - 1, 1 - e.y / h * 2, z, 1.0])
        ch.posed[k] = p[:3] / p[3]
        self._moved[ch.names[k]] = ch.posed[k].copy()
        name = ch.names[k]
        twin = name[:-4] + 'Right' if name.endswith('Left') else name[:-5] + 'Left' if name.endswith('Right') else None
        mx = getattr(ch, 'mirror_x', 0.0)                         # the body's middle (an FBX may be off x = 0)
        if self.mirror and twin in ch.index:
            ch.posed[ch.index[twin]] = ch.posed[k] * (-1, 1, 1) + (2 * mx, 0, 0)
            self._moved[twin] = ch.posed[ch.index[twin]].copy()
        elif self.mirror and twin is None:                         # a middle joint stays in the middle
            ch.posed[k][0] = mx
            self._moved[name] = ch.posed[k].copy()
        self.redraw()

    def _release(self, e):
        if self._drag is not None and self._moved and self.on_joints is not None:
            self.on_joints({n: [float(x) for x in v] for n, v in self._moved.items()})
        self._drag, self._moved = None, {}

    def _orbit(self, e):
        if self._drag is not None:
            return self._drag_joint(e)
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        self.yaw -= dx * 0.5
        self.pitch = float(np.clip(self.pitch + dy * 0.4, -85, 85))
        self.redraw()

    def _pan(self, e):
        dx, dy = e.x - self._last[0], e.y - self._last[1]
        self._last = (e.x, e.y)
        view = look_at(self._eye(), self.target)
        k = self.dist * 0.0015
        self.target = (self.target - view[0, :3] * dx * k + view[1, :3] * dy * k).astype('f4')
        self.redraw()

    def _zoom(self, e):
        self.dist = float(np.clip(self.dist * (0.9 if e.delta > 0 else 1.1), 0.2, 20))
        self.redraw()

    def _eye(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        return (self.target + self.dist * np.array([math.sin(y) * math.cos(p), math.sin(p),
                                                    math.cos(y) * math.cos(p)])).astype('f4')

    # -------------------------------------------------------------- drawing
    def redraw(self):
        if not self._pending:                     # draw once, when tkinter is idle
            self._pending = True
            self.label.after_idle(self._render)

    def _render(self):
        self._pending = False
        if not self.label.winfo_exists() or self.mesh is None:
            return
        w, h = max(self.label.winfo_width(), 64), max(self.label.winfo_height(), 64)
        if (w, h) != self.size:
            if self.fbo is not None:
                self.fbo.release()
            self.fbo = self.ctx.simple_framebuffer((w, h), components=3, samples=0)
            self.size = (w, h)
        self.fbo.use()
        self.ctx.viewport = (0, 0, w, h)
        self.fbo.clear(*self.bg, 1.0)
        self.ctx.enable(self.mgl.DEPTH_TEST)
        self._M = perspective(40, w / h, 0.05, 100) @ look_at(self._eye(), self.target)
        mvp = self._M.T.copy()
        self.prog['mvp'].write(mvp.tobytes())
        if self.mesh is not None:
            self.mesh.draw(mode=self.colour_mode)
            if self.ghost is not None and self.show_ghost:
                lo, hi = self.mesh.ch.bounds()
                self.ghost.draw(shift=(-(hi[0] - lo[0]) * 0.75 - 0.3, 0, 0), colour=(0.72, 0.72, 0.74))
            if self.show_bones:
                self._bones(mvp)
        img = Image.frombytes('RGB', (w, h), self.fbo.read(components=3, alignment=1)).transpose(Image.FLIP_TOP_BOTTOM)
        self.photo = ImageTk.PhotoImage(img)
        self.label.config(image=self.photo, text='')

    def _bones(self, mvp):
        ch = self.mesh.ch
        pts = [(ch.posed[k], ch.posed[p]) for k, p in enumerate(ch.parent) if p >= 0]
        if not pts:
            return
        self.ctx.disable(self.mgl.DEPTH_TEST)
        self.ctx.enable(self.mgl.PROGRAM_POINT_SIZE)
        self.lprog['mvp'].write(mvp.tobytes())
        lines = self.ctx.buffer(np.array(pts, 'f4').reshape(-1, 3).tobytes())
        dots = self.ctx.buffer(ch.posed.astype('f4').tobytes())
        big = 12.0 if self.on_joints is not None else 6.0
        for buf, mode, colour in ((lines, self.mgl.LINES, (0.95, 0.55, 0.1)), (dots, self.mgl.POINTS, (0.85, 0.05, 0.05))):
            vao = self.ctx.vertex_array(self.lprog, [(buf, '3f', 'in_pos')])
            self.lprog['colour'].value = colour
            self.lprog['psize'].value = big
            vao.render(mode)
            vao.release()
        if self.on_joints is not None and self.selected is not None and self.selected < len(ch.posed):
            sel = self.ctx.buffer(ch.posed[self.selected].astype('f4').tobytes())
            vao = self.ctx.vertex_array(self.lprog, [(sel, '3f', 'in_pos')])
            self.lprog['colour'].value = (0.1, 0.75, 0.2)
            self.lprog['psize'].value = 16.0
            vao.render(self.mgl.POINTS)
            vao.release(); sel.release()
        lines.release(); dots.release()
        self.ctx.enable(self.mgl.DEPTH_TEST)

    def release(self):
        for m in (self.mesh, self.ghost):
            if m is not None:
                m.release()
        if self.fbo is not None:
            self.fbo.release()
        self.ctx.release()
