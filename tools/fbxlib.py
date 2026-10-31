"""Minimal FBX reader: node tree + the parts needed for a skinned mesh.

Binary 7.x files are the normal input.  A few older character releases, including
the CJ source used by the TS3 mods, use the equivalent ASCII 6.x syntax, so that
subset is read too.
"""
import re, struct, zlib
import numpy as np


class Node:
    __slots__ = ('name', 'props', 'kids')

    def __init__(self, name, props, kids):
        self.name, self.props, self.kids = name, props, kids

    def get(self, name):
        for k in self.kids:
            if k.name == name:
                return k
        return None

    def all(self, name):
        return [k for k in self.kids if k.name == name]

    def __repr__(self):
        return 'Node(%s, %r)' % (self.name, [p if not isinstance(p, np.ndarray) else 'arr%d' % len(p) for p in self.props][:4])


_ARR = {b'f': '<f4', b'd': '<f8', b'l': '<i8', b'i': '<i4', b'b': 'u1'}


def _prop(b, q):
    t = b[q:q + 1]; q += 1
    if t == b'Y': return struct.unpack_from('<h', b, q)[0], q + 2
    if t == b'C': return b[q] != 0, q + 1
    if t == b'I': return struct.unpack_from('<i', b, q)[0], q + 4
    if t == b'F': return struct.unpack_from('<f', b, q)[0], q + 4
    if t == b'D': return struct.unpack_from('<d', b, q)[0], q + 8
    if t == b'L': return struct.unpack_from('<q', b, q)[0], q + 8
    if t in _ARR:
        n, enc, clen = struct.unpack_from('<III', b, q); q += 12
        raw = b[q:q + clen]; q += clen
        if enc == 1:
            raw = zlib.decompress(raw)
        return np.frombuffer(raw, _ARR[t], n).copy(), q
    if t in (b'S', b'R'):
        n = struct.unpack_from('<I', b, q)[0]; q += 4
        v = b[q:q + n]; q += n
        return (v.decode('utf-8', 'replace') if t == b'S' else v), q
    raise ValueError('unknown FBX property type %r' % t)


def parse(path):
    b = open(path, 'rb').read()
    if not b.startswith(b'Kaydara FBX Binary'):
        return _parse_ascii(b, path)
    ver = struct.unpack_from('<I', b, 23)[0]
    wide = ver >= 7500
    hdr = 25 if wide else 13

    def node(q):
        if wide:
            end, nprops, plen = struct.unpack_from('<QQQ', b, q)
        else:
            end, nprops, plen = struct.unpack_from('<III', b, q)
        if end == 0:
            return None, q + hdr
        nl = b[q + hdr - 1]
        name = b[q + hdr:q + hdr + nl].decode('latin1')
        p = q + hdr + nl
        props = []
        for _ in range(nprops):
            v, p = _prop(b, p)
            props.append(v)
        kids = []
        while p < end:
            k, p = node(p)
            if k is None:
                break
            kids.append(k)
        return Node(name, props, kids), end

    top, q = [], 27
    while q < len(b) - hdr:
        n, q = node(q)
        if n is None:
            break
        top.append(n)
    return Node('', [], top), ver


_ASCII_KEY = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$')
_ASCII_VALUES = re.compile(r'"(?:[^"\\]|\\.)*"|[^,]+')


def _ascii_value(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        # FBX paths commonly contain Windows backslashes.  They are literal
        # path separators here, not Python-style ``\\U`` escapes.
        return v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    if v in ('T', 'Y'):
        return True
    if v in ('F', 'N'):
        return False
    try:
        return float(v) if any(c in v for c in '.eE') else int(v)
    except ValueError:
        return v


def _ascii_props(raw):
    """Parse one comma-separated ASCII-FBX property list."""
    raw = raw.strip()
    if raw.startswith('*'):
        raw = raw.split(None, 1)[1] if ' ' in raw else ''
    vals = [_ascii_value(x) for x in _ASCII_VALUES.findall(raw) if x.strip()]
    if len(vals) > 1 and all(isinstance(x, (int, float, np.number)) for x in vals):
        return [np.asarray(vals, dtype=np.float64 if any(isinstance(x, float) for x in vals) else np.int64)]
    return vals


def _parse_ascii(b, path):
    """Read the simple, line-oriented ASCII FBX 6.x form written by FBX SDK.

    The converter only needs the scene graph, mesh layers and skin clusters.  The
    representation deliberately matches ``parse`` above, so the rest of this
    module does not distinguish the source format.
    """
    try:
        text = b.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('not a supported FBX: %s' % path) from exc
    if 'FBX' not in text[:256]:
        raise ValueError('not a supported FBX: %s' % path)

    # Large numeric values wrap across lines without another ``name:`` prefix.
    # Make each of them part of the leaf line that introduced it.
    logical = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(';'):
            continue
        if _ASCII_KEY.match(line) or stripped in ('{', '}'):
            logical.append(line)
        elif logical:
            logical[-1] += stripped

    root = Node('', [], [])
    stack = [root]
    for line in logical:
        stripped = line.strip()
        if stripped == '}':
            if len(stack) == 1:
                raise ValueError('unmatched closing brace in %s' % path)
            stack.pop()
            continue
        match = _ASCII_KEY.match(line)
        if not match:
            continue
        name, raw = match.groups()
        raw = raw.strip()
        opened = raw.endswith('{')
        if opened:
            raw = raw[:-1].strip()
        node = Node(name, _ascii_props(raw), [])
        stack[-1].kids.append(node)
        if opened:
            stack.append(node)
    if len(stack) != 1:
        raise ValueError('unclosed node in %s' % path)
    version = 6100 if 'FBX 6.' in text[:256] else 0
    return root, version


def props70(n):
    """Properties70/Properties60 -> {name: values}"""
    out = {}
    p = (n.get('Properties70') or n.get('Properties60')) if n else None
    for k in (p.kids if p else []):
        # ASCII 6.x Properties60 omits the fourth (flags) field that 7.x
        # Properties70 carries before the values.
        out[k.props[0]] = k.props[4:] if len(k.props) >= 5 else k.props[3:]
    return out


def _layer(geo, lname, key, idxkey, polyvert_idx, cp_idx):
    """per polygon-vertex values of a LayerElement"""
    le = geo.get(lname)
    if le is None:
        return None
    data = le.get(key).props[0]
    mapping = le.get('MappingInformationType').props[0]
    ref = le.get('ReferenceInformationType').props[0]
    if ref in ('IndexToDirect', 'Index') and le.get(idxkey) is not None:
        idx = le.get(idxkey).props[0]
    else:
        idx = None
    if mapping == 'ByPolygonVertex':
        sel = np.arange(len(polyvert_idx)) if idx is None else idx
    elif mapping in ('ByVertice', 'ByVertex'):
        sel = cp_idx if idx is None else idx[cp_idx]
    else:
        raise ValueError('%s mapping %s not handled' % (lname, mapping))
    return data, sel


class Scene:
    def __init__(self, path):
        self.root, self.version = parse(path)
        objs = self.root.get('Objects')
        # This old SDK export places GlobalSettings at the end of Objects.
        # Newer binary exports keep it at the document root.
        gsnode = self.root.get('GlobalSettings') or (objs.get('GlobalSettings') if objs else None)
        gs = props70(gsnode)
        self.settings = gs
        self.objects = {o.props[0]: o for o in objs.kids if o.props}
        self.conn = []  # (child, parent, kind, prop)
        for c in self.root.get('Connections').kids:
            self.conn.append((c.props[1], c.props[2], c.props[0], c.props[3] if len(c.props) > 3 else None))

    def to_yup(self):
        """3x3 matrix (row-vector convention) turning this file's world into Y up, character facing +Z"""
        up = int(self.settings.get('UpAxis', [1])[0]); ups = float(self.settings.get('UpAxisSign', [1])[0])
        fr = int(self.settings.get('FrontAxis', [2])[0]); frs = float(self.settings.get('FrontAxisSign', [1])[0])
        Y = np.zeros(3); Y[up] = ups
        Z = np.zeros(3); Z[fr] = frs
        X = np.cross(Y, Z)
        return np.stack([X, Y, Z], 1)        # world row vector @ M -> (x, y, z) in the game's frame

    def kind(self, o):
        return o.props[2] if len(o.props) > 2 else (o.props[1] if len(o.props) > 1 else '')

    def name(self, o):
        raw = o.props[1] if len(o.props) > 2 else o.props[0]
        return raw.split('\x00')[0].split('::')[-1]

    def children_of(self, pid, objname=None):
        out = []
        for c, p, k, _ in self.conn:
            if p == pid and c in self.objects and (objname is None or self.objects[c].name == objname):
                out.append(c)
        return out

    def parents_of(self, cid):
        return [p for c, p, k, _ in self.conn if c == cid]

    def meshes(self):
        """yield dict per Geometry: positions, triangles (per-corner arrays), uvs, normals, material per tri, skin"""
        for gid, g in self.objects.items():
            # FBX 7.x puts mesh data in a Geometry object.  The older 6.x
            # ASCII writer used by CJ stores it directly in the mesh Model.
            if self.kind(g) != 'Mesh' or g.name not in ('Geometry', 'Model') or g.get('Vertices') is None:
                continue
            pos = g.get('Vertices').props[0].reshape(-1, 3)
            pvi = g.get('PolygonVertexIndex').props[0]
            cp = np.where(pvi < 0, ~pvi, pvi)
            ends = np.where(pvi < 0)[0]
            starts = np.concatenate([[0], ends[:-1] + 1])
            # triangulate as fans; corner index lists
            tri, tri_poly = [], []
            for pi, (s, e) in enumerate(zip(starts, ends)):
                for k in range(s + 1, e):
                    tri.append((s, k, k + 1)); tri_poly.append(pi)
            tri = np.array(tri, dtype=np.int64); tri_poly = np.array(tri_poly)
            nrm = _layer(g, 'LayerElementNormal', 'Normals', 'NormalsIndex', pvi, cp)
            uv = _layer(g, 'LayerElementUV', 'UV', 'UVIndex', pvi, cp)
            matl = g.get('LayerElementMaterial')
            if matl is not None:
                m = matl.get('Materials').props[0]
                mat = m[tri_poly] if matl.get('MappingInformationType').props[0] == 'ByPolygon' else np.zeros(len(tri), int)
            else:
                mat = np.zeros(len(tri), int)
            # model that owns the geometry, and its materials in order
            models = ([gid] if g.name == 'Model' else
                      [p for p in self.parents_of(gid) if p in self.objects and self.objects[p].name == 'Model'])
            mats = []
            if models:
                mats = [self.name(self.objects[c]) for c in self.children_of(models[0], 'Material')]
            skin = self.skin_of(gid, len(pos))
            yield dict(name=self.name(g), pos=pos, cp=cp, tri=tri, normals=nrm, uv=uv, mat=mat, matnames=mats,
                       model=models[0] if models else None, skin=skin)

    def skin_of(self, gid, ncp):
        for d in self.children_of(gid, 'Deformer'):
            if self.kind(self.objects[d]) != 'Skin':
                continue
            clusters = []
            for c in self.children_of(d, 'Deformer'):
                cl = self.objects[c]
                bones = [b for b in self.children_of(c, 'Model')]
                if not bones:
                    continue
                ix = cl.get('Indexes'); w = cl.get('Weights')
                clusters.append(dict(bone=self.name(self.objects[bones[0]]), bone_id=bones[0],
                                     idx=ix.props[0] if ix else np.zeros(0, int), w=w.props[0] if w else np.zeros(0),
                                     xf=cl.get('Transform').props[0].reshape(4, 4),
                                     xlink=cl.get('TransformLink').props[0].reshape(4, 4)))
            return clusters
        return None

    def bones(self):
        out = {}
        for oid, o in self.objects.items():
            if o.name == 'Model' and self.kind(o) in ('LimbNode', 'Root', 'Null'):
                par = [p for p in self.parents_of(oid) if p in self.objects and self.objects[p].name == 'Model']
                out[oid] = dict(name=self.name(o), parent=par[0] if par else None, props=props70(o), kind=self.kind(o))
        return out
